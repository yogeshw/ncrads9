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
DS9's contour file format: reading it, writing it, and passing it around.

"A contour file is an ASCII file containing a header, global properties,
coordinate system, contour levels, and contour points"
(`ds9/doc/ref/contour.html`):

    # Contour file format: DS9 version 7.5
    global color=green width=1 dash=1 dashlist=8 3
    image
    level=15.78775 color=pink width=2 dash=yes
    (202.4836 47.2238
     202.4834 47.2239)
    (...)

A level's own attributes override the globals for that level only, and
"contours are not closed" -- each parenthesised block is an open polyline,
which is why nothing here joins the last point to the first.

The same text is what Copy and Paste Contours move between frames (M7-22).
Going through the file format rather than through a private structure means
a contour copied from one frame and pasted into another is exactly a
contour saved and loaded, and there is one thing to get right instead of
two.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

#: The header DS9 writes, and the version it claims.
HEADER = "# Contour file format: DS9 version 7.5"

#: The coordinate systems a contour file may declare.
SYSTEMS: frozenset[str] = frozenset(
    {
        "image",
        "physical",
        "amplifier",
        "detector",
        "fk4",
        "b1950",
        "fk5",
        "j2000",
        "icrs",
        "galactic",
        "ecliptic",
        "linear",
        *(f"wcs{letter}" for letter in "abcdefghijklmnopqrstuvwxyz"),
        "wcs",
    }
)

#: The properties a `global` or `level=` line may carry.
PROPERTIES: tuple[str, ...] = ("color", "width", "dash", "dashlist")

#: What a contour gets when nothing says otherwise.
DEFAULT_COLOR = "green"
DEFAULT_WIDTH = 1


class ContourFileError(ValueError):
    """A contour file that cannot be read, for the reason given."""


@dataclass
class ContourLevel:
    """One level, its appearance, and the curves at it.

    Attributes:
        value: The level's data value.
        color: Its colour.
        width: Its line width.
        dash: Whether it is dashed.
        dashlist: The dash pattern, as DS9 writes it -- "8 3".
        contours: The open polylines at this level, each a list of (x, y).
    """

    value: float
    color: str = DEFAULT_COLOR
    width: int = DEFAULT_WIDTH
    dash: bool = False
    dashlist: str = ""
    contours: list[list[tuple[float, float]]] = field(default_factory=list)

    @property
    def points(self) -> int:
        """How many points this level's curves hold in total."""
        return sum(len(contour) for contour in self.contours)


@dataclass
class ContourSet:
    """A whole contour file.

    Attributes:
        system: The coordinate system the points are in.
        levels: The levels, in file order.
        globals: The `global` properties, which levels inherit.
    """

    system: str = "image"
    levels: list[ContourLevel] = field(default_factory=list)
    globals: dict[str, str] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.levels)

    def __bool__(self) -> bool:
        return bool(self.levels)

    @property
    def values(self) -> list[float]:
        """The level values, in order."""
        return [level.value for level in self.levels]

    def paths(self) -> list[list[list[tuple[float, float]]]]:
        """The curves, grouped by level, as the overlay wants them."""
        return [level.contours for level in self.levels]


def _flag(value: str) -> bool:
    """Read one of DS9's booleans, which it writes several ways.

    `dash=1`, `dash=yes` and `dash=true` all appear; its own documentation
    uses two of them in one example.
    """
    return str(value).strip().lower() in ("1", "yes", "true", "on")


def _properties(text: str) -> dict[str, str]:
    """Read `key = value` pairs off a `global` or `level=` line.

    `dashlist` takes two numbers separated by a space, so a value runs to
    the next recognised keyword rather than to the next space.
    """
    found: dict[str, str] = {}
    keywords = "|".join((*PROPERTIES, "level"))
    pattern = re.compile(rf"\b({keywords})\s*=\s*(.*?)(?=\s+(?:{keywords})\s*=|$)", re.IGNORECASE)
    for match in pattern.finditer(text):
        found[match.group(1).lower()] = match.group(2).strip()
    return found


def parse(text: str) -> ContourSet:
    """Read a DS9 contour file.

    Args:
        text: The file's contents.

    Returns:
        The levels and their curves.

    Raises:
        ContourFileError: If a coordinate block cannot be read as numbers.
    """
    result = ContourSet()
    current: ContourLevel | None = None
    open_points: list[tuple[float, float]] | None = None
    buffer: list[str] = []

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue

        if open_points is None and line.startswith("#"):
            continue

        lowered = line.lower()
        if open_points is None and lowered.startswith("global"):
            result.globals.update(_properties(line))
            continue
        if open_points is None and lowered in SYSTEMS:
            result.system = lowered
            continue
        if open_points is None and lowered.startswith("level"):
            properties = _properties(line)
            if "level" not in properties:
                continue
            try:
                value = float(properties["level"])
            except ValueError as exc:
                raise ContourFileError(f"line {number}: {properties['level']!r} is not a level") from exc
            current = _level(value, result.globals, properties)
            result.levels.append(current)
            continue

        # A coordinate block, which may run over several lines.
        if open_points is None:
            if not line.startswith("("):
                continue
            open_points = []
            buffer = []
            line = line[1:]

        closed = ")" in line
        buffer.append(line.split(")", 1)[0] if closed else line)
        if not closed:
            continue

        points = _points(" ".join(buffer), number)
        if current is None:
            # Points before any `level=` line: DS9 has no level to put them
            # on, and neither do we, so they open one at zero.
            current = _level(0.0, result.globals, {})
            result.levels.append(current)
        if len(points) > 1:
            current.contours.append(points)
        open_points = None
        buffer = []

    return result


def _level(value: float, globals_: dict[str, str], properties: dict[str, str]) -> ContourLevel:
    """Build a level, its own properties overriding the globals."""
    merged = {**globals_, **properties}
    try:
        width = int(float(merged.get("width", DEFAULT_WIDTH)))
    except ValueError:
        width = DEFAULT_WIDTH
    return ContourLevel(
        value=value,
        color=merged.get("color", DEFAULT_COLOR),
        width=width,
        dash=_flag(merged.get("dash", "0")),
        dashlist=merged.get("dashlist", ""),
    )


def _points(text: str, line_number: int) -> list[tuple[float, float]]:
    """Read a coordinate block into (x, y) pairs.

    Raises:
        ContourFileError: If it does not hold pairs of numbers.
    """
    words = text.replace(",", " ").split()
    if len(words) % 2:
        # An odd count means a truncated pair; the last number is dropped
        # rather than making the whole file unreadable.
        words = words[:-1]
    try:
        numbers = [float(word) for word in words]
    except ValueError as exc:
        raise ContourFileError(f"line {line_number}: not a coordinate list") from exc
    return [(numbers[index], numbers[index + 1]) for index in range(0, len(numbers), 2)]


def to_text(contours: ContourSet, include_header: bool = True) -> str:
    """Write a contour set in DS9's format.

    Args:
        contours: The levels and curves.
        include_header: Whether to write DS9's version header.

    Returns:
        The file's contents.
    """
    lines: list[str] = []
    if include_header:
        lines.append(HEADER)
    if contours.globals:
        lines.append("global " + " ".join(f"{key}={value}" for key, value in contours.globals.items()))
    lines.append(contours.system)

    for level in contours.levels:
        attributes = [f"level={level.value:.8g}", f"color={level.color}", f"width={level.width}"]
        if level.dash:
            attributes.append("dash=1")
            if level.dashlist:
                attributes.append(f"dashlist={level.dashlist}")
        lines.append(" ".join(attributes))

        for contour in level.contours:
            if len(contour) < 2:
                continue
            # Ten significant figures, not eight: a right ascension near
            # 200 degrees written as `%.8g` loses its last digit, which is
            # a tenth of an arcsecond, and a saved contour drifts off the
            # feature it was drawn on.
            body = "\n ".join(f"{x:.10g} {y:.10g}" for x, y in contour)
            lines.append(f"({body})")

    return "\n".join(lines) + "\n"


def from_paths(
    paths,
    values,
    system: str = "image",
    color: str = DEFAULT_COLOR,
    width: int = DEFAULT_WIDTH,
    dash: bool = False,
) -> ContourSet:
    """Build a contour set from the arrays the generator produces.

    Args:
        paths: One list of point arrays per level, as `find_contours`
            returns -- each row (row, column), which is numpy's order and
            the reverse of a contour file's (x, y).
        values: The level values.
        system: The coordinate system to record.
        color, width, dash: The appearance to record for every level.

    Returns:
        The contour set.
    """
    result = ContourSet(system=system)
    for index, level_paths in enumerate(paths):
        value = float(values[index]) if index < len(values) else 0.0
        level = ContourLevel(value=value, color=color, width=width, dash=dash)
        for path in level_paths:
            points = _as_points(path)
            if len(points) > 1:
                level.contours.append(points)
        result.levels.append(level)
    return result


def _as_points(path) -> list[tuple[float, float]]:
    """One contour path as (x, y) pairs, whatever shape it arrived in.

    `skimage.measure.find_contours` gives (row, column) pairs, which is
    (y, x); the file format is (x, y). Getting this backwards writes a
    contour file whose curves are the transpose of the picture.
    """
    import numpy as np

    array = np.asarray(path, dtype=float)
    if array.ndim == 2 and array.shape[1] == 2:
        return [(float(row[1]), float(row[0])) for row in array]
    if array.ndim == 2 and array.shape[0] == 2:
        # A pair of coordinate arrays, which is what the scipy fallback
        # produces: (x_values, y_values).
        return [(float(x), float(y)) for x, y in zip(array[0], array[1], strict=False)]
    return []


def to_paths(contours: ContourSet):
    """The overlay's shape: one array of (row, column) pairs per curve.

    The inverse of `from_paths`, so a loaded contour draws exactly where a
    computed one would.
    """
    import numpy as np

    return [
        [np.array([(y, x) for x, y in contour], dtype=float) for contour in level.contours]
        for level in contours.levels
    ]


def load(path: str | Path) -> ContourSet:
    """Read a contour file.

    Raises:
        ContourFileError: If it cannot be parsed.
        OSError: If it cannot be read.
    """
    return parse(Path(path).read_text())


def save(path: str | Path, contours: ContourSet) -> None:
    """Write a contour file.

    Raises:
        OSError: If it cannot be written.
    """
    Path(path).write_text(to_text(contours))
