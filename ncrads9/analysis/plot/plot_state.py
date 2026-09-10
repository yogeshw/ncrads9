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
Everything a plot window is showing, apart from the window.

Kept separate so a plot can be built, saved to a file, read back and tested
without a display -- which is also what DS9's Backup and Restore of a plot
amount to (`ds9/library/plotbackup.tcl`).

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .axis import Axis
from .dataset import CYCLE, DataFormat, Dataset, parse_data


class PlotStyle(Enum):
    """DS9's three plot kinds."""

    LINE = "line"
    BAR = "bar"
    SCATTER = "scatter"


class LegendPosition(Enum):
    """Where DS9's Legend cascade can put the key."""

    RIGHT = "right"
    LEFT = "left"
    TOP = "top"
    BOTTOM = "bottom"
    PLOT_AREA = "plotarea"

    @property
    def matplotlib(self) -> str:
        """The `loc` matplotlib wants for this position."""
        return {
            "right": "center right",
            "left": "center left",
            "top": "upper center",
            "bottom": "lower center",
            "plotarea": "best",
        }[self.value]


#: The version stamped into a saved plot, so a later format can be told apart.
FORMAT_VERSION = 1


@dataclass
class PlotState:
    """One plot: its datasets, its axes, and how it is drawn.

    Attributes:
        title: The plot's title.
        style: Line, bar or scatter.
        x_axis, y_axis: The two axes.
        datasets: The curves, in the order added.
        show_legend: Whether the key is drawn.
        legend_position: Where.
        legend_title: The key's own title.
    """

    title: str = ""
    style: PlotStyle = PlotStyle.LINE
    x_axis: Axis = field(default_factory=Axis)
    y_axis: Axis = field(default_factory=Axis)
    datasets: list[Dataset] = field(default_factory=list)
    show_legend: bool = True
    legend_position: LegendPosition = LegendPosition.RIGHT
    legend_title: str = ""

    def add(self, dataset: Dataset) -> Dataset:
        """Add a dataset, giving it a distinct colour if it has the default.

        Two curves in the same black are one curve as far as a reader is
        concerned, so a second dataset takes the next colour along.
        """
        from .dataset import DEFAULT_COLOR

        if dataset.color == DEFAULT_COLOR and self.datasets:
            dataset.color = CYCLE[len(self.datasets) % len(CYCLE)]
        if not dataset.name or dataset.name == "Data":
            dataset.name = f"Data {len(self.datasets) + 1}"
        self.datasets.append(dataset)
        return dataset

    def remove(self, index: int) -> None:
        """Delete one dataset.

        Raises:
            IndexError: If there is none at `index`.
        """
        del self.datasets[index]

    def duplicate(self, index: int) -> Dataset:
        """Copy one dataset, as DS9's Duplicate Dataset does.

        Raises:
            IndexError: If there is none at `index`.
        """
        from dataclasses import replace as _replace

        original = self.datasets[index]
        copy = _replace(
            original,
            name=f"{original.name} copy",
            x=list(original.x),
            y=list(original.y),
            x_error=list(original.x_error),
            y_error=list(original.y_error),
        )
        self.datasets.append(copy)
        return copy

    @property
    def visible(self) -> list[Dataset]:
        """The datasets actually drawn."""
        return [dataset for dataset in self.datasets if dataset.show and len(dataset)]

    def bounds(self) -> tuple[float, float, float, float] | None:
        """The extent of every visible dataset together, or None if empty."""
        boxes = [dataset.bounds() for dataset in self.visible]
        boxes = [box for box in boxes if box is not None]
        if not boxes:
            return None
        return (
            min(box[0] for box in boxes),
            max(box[1] for box in boxes),
            min(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )

    # -- saving and restoring ------------------------------------------------

    def to_dict(self) -> dict:
        """The whole plot as plain data."""
        return {
            "version": FORMAT_VERSION,
            "title": self.title,
            "style": self.style.value,
            "x_axis": self.x_axis.to_dict(),
            "y_axis": self.y_axis.to_dict(),
            "show_legend": self.show_legend,
            "legend_position": self.legend_position.value,
            "legend_title": self.legend_title,
            "datasets": [
                {
                    "name": dataset.name,
                    "x": dataset.x,
                    "y": dataset.y,
                    "x_error": dataset.x_error,
                    "y_error": dataset.y_error,
                    "color": dataset.color,
                    "width": dataset.width,
                    "shape": dataset.shape,
                    "size": dataset.size,
                    "show": dataset.show,
                    "fill": dataset.fill,
                }
                for dataset in self.datasets
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> PlotState:
        """Read a plot back from saved data."""
        state = cls(
            title=str(data.get("title", "")),
            style=PlotStyle(data.get("style", PlotStyle.LINE.value)),
            x_axis=Axis.from_dict(data.get("x_axis", {})),
            y_axis=Axis.from_dict(data.get("y_axis", {})),
            show_legend=bool(data.get("show_legend", True)),
            legend_position=LegendPosition(data.get("legend_position", LegendPosition.RIGHT.value)),
            legend_title=str(data.get("legend_title", "")),
        )
        for entry in data.get("datasets", ()):
            state.datasets.append(
                Dataset(
                    name=str(entry.get("name", "Data")),
                    x=[float(value) for value in entry.get("x", ())],
                    y=[float(value) for value in entry.get("y", ())],
                    x_error=[float(value) for value in entry.get("x_error", ())],
                    y_error=[float(value) for value in entry.get("y_error", ())],
                    color=str(entry.get("color", "black")),
                    width=int(entry.get("width", 1)),
                    shape=str(entry.get("shape", "circle")),
                    size=int(entry.get("size", 4)),
                    show=bool(entry.get("show", True)),
                    fill=bool(entry.get("fill", True)),
                )
            )
        return state

    def save(self, path: str | Path) -> None:
        """Write the plot to a file, DS9's Backup.

        Raises:
            OSError: If it cannot be written.
        """
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> PlotState:
        """Read a plot back, DS9's Restore.

        Raises:
            ValueError: If the file is not a saved plot.
            OSError: If it cannot be read.
        """
        data = json.loads(Path(path).read_text())
        if not isinstance(data, dict) or "datasets" not in data:
            raise ValueError("not a saved plot")
        return cls.from_dict(data)

    # -- data files ------------------------------------------------------------

    def load_data(
        self,
        text: str,
        data_format: DataFormat | str = DataFormat.XY,
        name: str = "Data",
    ) -> Dataset:
        """Add a dataset from columns of numbers, DS9's Load Data.

        Raises:
            PlotDataError: If nothing in the text was a point.
        """
        return self.add(parse_data(text, data_format, name=name))

    def list_data(self) -> str:
        """Every dataset as text, DS9's List Data."""
        blocks = []
        for dataset in self.datasets:
            blocks.append(f"# {dataset.name} ({dataset.data_format.value})")
            blocks.append(dataset.to_text())
        return "\n".join(blocks)
