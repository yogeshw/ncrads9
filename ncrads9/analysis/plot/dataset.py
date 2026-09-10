# NCRADS9 - NCRA DS9-like FITS Viewer
# Copyright (C) 2026 Yogesh Wadadekar
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
One curve on a plot, and reading one out of an analysis task's output.

DS9's four data formats are `xy`, `xyex`, `xyey` and `xyexey` -- two, three
or four numbers per line, the extras being error bars on x, on y, or on both
(`ds9/doc/ref/analysis.html`, `$plot`).

`$plot(stdin)` puts a header on the front, which `parse_stdin` reads. Its
shape is not obvious and is worth stating: the first line is a list whose
*last* word is the data format, the two before it the y and x axis labels,
and everything before that, joined, the title (`AnalysisPlotStdin`,
`ds9/library/analysis.tcl:1003`). Reading it left to right instead would
break every title containing a space.

Two escapes travel in the same stream. `$BEGINTEXT` ... `$ENDTEXT` at the
head is prose to show in a text window rather than plot, and `$ERROR`
anywhere means the task failed and the whole output is a message. Both exist
so one analysis task can report either a plot or a problem down one pipe.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from ..task_file import tcl_split

#: The marker shapes DS9's Shape cascade offers, mapped to matplotlib's.
SHAPES: dict[str, str] = {
    "none": "",
    "circle": "o",
    "square": "s",
    "diamond": "D",
    "plus": "+",
    "cross": "x",
    "triangle": "^",
    "arrow": ">",
}

#: The colours DS9 offers per dataset, in its menu's order.
COLORS: tuple[str, ...] = (
    "black",
    "white",
    "red",
    "green",
    "blue",
    "cyan",
    "magenta",
    "yellow",
)

#: The order a second and later dataset is coloured in. White is left out:
#: it is a colour a user may choose, but never one to hand out, since the
#: plot's background is white and an invisible curve reads as a missing one.
CYCLE: tuple[str, ...] = ("black", "red", "blue", "green", "magenta", "cyan", "yellow")

#: The line widths it offers.
WIDTHS: tuple[int, ...] = (0, 1, 2, 3, 4)

#: The marker sizes it offers.
SIZES: tuple[int, ...] = (2, 3, 4, 5, 6, 7, 8, 9, 10)

#: What a dataset gets if nothing says otherwise.
DEFAULT_COLOR = "black"
DEFAULT_WIDTH = 1
DEFAULT_SHAPE = "circle"
DEFAULT_SIZE = 4

#: The marker that says the rest of the output is prose, not data.
TEXT_BEGIN = "$BEGINTEXT"
TEXT_END = "$ENDTEXT"

#: The two markers that say the task failed.
ERROR_MARKERS = ("$ERROR", "ERROR:")


class PlotDataError(ValueError):
    """Output that cannot be read as plot data, for the reason given."""


class DataFormat(Enum):
    """How many numbers a line holds, and which are error bars."""

    XY = "xy"
    XYEX = "xyex"
    XYEY = "xyey"
    XYEXEY = "xyexey"

    @property
    def columns(self) -> int:
        """How many numbers a line of this format has."""
        return {"xy": 2, "xyex": 3, "xyey": 3, "xyexey": 4}[self.value]

    @property
    def has_x_error(self) -> bool:
        """Whether it carries an error on x."""
        return self in (DataFormat.XYEX, DataFormat.XYEXEY)

    @property
    def has_y_error(self) -> bool:
        """Whether it carries an error on y."""
        return self in (DataFormat.XYEY, DataFormat.XYEXEY)


@dataclass
class Dataset:
    """One curve, and how it is drawn.

    Attributes:
        name: What the legend calls it.
        x, y: The points.
        x_error, y_error: Error bars, empty when the format had none.
        color, width, shape, size: DS9's per-dataset appearance.
        show: Whether it is drawn at all -- DS9's per-dataset Show.
        fill: Whether a bar dataset's bars are filled.
    """

    name: str = "Data"
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    x_error: list[float] = field(default_factory=list)
    y_error: list[float] = field(default_factory=list)
    color: str = DEFAULT_COLOR
    width: int = DEFAULT_WIDTH
    shape: str = DEFAULT_SHAPE
    size: int = DEFAULT_SIZE
    show: bool = True
    fill: bool = True

    def __len__(self) -> int:
        return len(self.x)

    @property
    def marker(self) -> str:
        """The matplotlib marker for this dataset's shape."""
        return SHAPES.get(self.shape, "o")

    def bounds(self) -> tuple[float, float, float, float] | None:
        """The data's extent, as (x0, x1, y0, y1), or None if it is empty."""
        if not self.x or not self.y:
            return None
        return (min(self.x), max(self.x), min(self.y), max(self.y))

    def to_text(self, data_format: DataFormat | None = None) -> str:
        """Write the dataset back out in DS9's column format."""
        chosen = data_format or self.data_format
        lines = []
        for index in range(len(self.x)):
            row = [self.x[index], self.y[index]]
            if chosen.has_x_error:
                row.append(self.x_error[index] if index < len(self.x_error) else 0.0)
            if chosen.has_y_error:
                row.append(self.y_error[index] if index < len(self.y_error) else 0.0)
            lines.append(" ".join(f"{value:g}" for value in row))
        return "\n".join(lines)

    @property
    def data_format(self) -> DataFormat:
        """Which format this dataset's columns amount to."""
        if self.x_error and self.y_error:
            return DataFormat.XYEXEY
        if self.x_error:
            return DataFormat.XYEX
        if self.y_error:
            return DataFormat.XYEY
        return DataFormat.XY


@dataclass
class PlotData:
    """What one analysis task's output amounted to.

    Attributes:
        dataset: The points, if there were any.
        title, x_label, y_label: From the `$plot(stdin)` header.
        message: Prose to show in a text window instead of, or beside, the
            plot -- from `$BEGINTEXT` or from `$ERROR`.
        failed: True when the output said `$ERROR`, so there is no plot.
    """

    dataset: Dataset | None = None
    title: str = ""
    x_label: str = ""
    y_label: str = ""
    message: str = ""
    failed: bool = False


def parse_data(
    text: str,
    data_format: DataFormat | str = DataFormat.XY,
    name: str = "Data",
) -> Dataset:
    """Read columns of numbers into a dataset.

    Args:
        text: The task's output, one point per line.
        data_format: How many columns to expect.
        name: What to call the dataset.

    Returns:
        The dataset. Lines that are blank, commented, or short of the
        format's columns are skipped -- a task that prints a stray header
        line should still plot.

    Raises:
        PlotDataError: If nothing in the text was a point.
    """
    chosen = DataFormat(data_format) if isinstance(data_format, str) else data_format
    dataset = Dataset(name=name)

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.replace(",", " ").split()
        if len(parts) < chosen.columns:
            continue
        try:
            numbers = [float(part) for part in parts[: chosen.columns]]
        except ValueError:
            continue
        if not all(math.isfinite(number) for number in numbers[:2]):
            continue

        dataset.x.append(numbers[0])
        dataset.y.append(numbers[1])
        if chosen.has_x_error:
            dataset.x_error.append(abs(numbers[2]))
        if chosen.has_y_error:
            dataset.y_error.append(abs(numbers[-1]))

    if not dataset.x:
        raise PlotDataError("no plottable points in the task's output")
    return dataset


def parse_stdin(text: str, name: str = "Data") -> PlotData:
    """Read `$plot(stdin)` output: a header line, then the columns.

    Handles the two escapes that travel in the same stream -- `$ERROR` and
    `$BEGINTEXT` ... `$ENDTEXT` -- before looking for a header at all.
    """
    body = text
    message = ""

    for marker in ERROR_MARKERS:
        position = body.find(marker)
        if position >= 0:
            return PlotData(message=body[position:].strip(), failed=True)

    if body.lstrip().startswith(TEXT_BEGIN):
        body = body.lstrip()[len(TEXT_BEGIN) :].lstrip("\n")
        end = body.find(TEXT_END)
        if end < 0:
            # No end marker: it is all prose, and there is no plot in it.
            return PlotData(message=body.strip())
        message = body[:end].strip()
        body = body[end + len(TEXT_END) :].lstrip("\n")

    header, _, columns = body.partition("\n")
    # The header is a Tcl list, so a multi-word axis label is braced --
    # `{X Axis}` is one element. Splitting on whitespace would turn a
    # two-word label into two, and shift the format off the end.
    words = tcl_split(header)
    if len(words) < 4 or not columns.strip():
        raise PlotDataError(
            "expected a header of 'title x-label y-label format' followed by data, "
            f"got {header.strip()[:40]!r}"
        )

    # The format is the *last* word, the labels the two before it, and
    # everything earlier is the title -- which is how a title with spaces
    # in it survives.
    try:
        data_format = DataFormat(words[-1].lower())
    except ValueError as exc:
        raise PlotDataError(f"unknown plot data format {words[-1]!r}") from exc

    return PlotData(
        dataset=parse_data(columns, data_format, name=name),
        title=" ".join(words[:-3]),
        x_label=words[-3],
        y_label=words[-2],
        message=message,
    )
