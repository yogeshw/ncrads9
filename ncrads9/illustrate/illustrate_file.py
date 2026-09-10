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
DS9's illustrate file format, read and written.

    # Illustrate file format: DS9 version 1.0
    global color = cyan fill = no width = 1 dash = no
    global font = helvetica fontsize = 12 fontweight = normal fontslant = roman
    circle 100 200 20 # color = red width = 2

One element per line, its geometry first and its properties after a `#`,
with only what differs from the globals written (`illustratecommand.tcl:305`).

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from .elements import (
    DEFAULT_COLOR,
    DEFAULT_FONT,
    DEFAULT_FONT_SIZE,
    DEFAULT_FONT_SLANT,
    DEFAULT_FONT_WEIGHT,
    DEFAULT_JUSTIFY,
    DEFAULT_WIDTH,
    Box,
    Circle,
    Element,
    Ellipse,
    Image,
    Line,
    Polygon,
    Style,
    Text,
)

#: What DS9 writes at the top of every illustrate file.
HEADER = (
    "# Illustrate file format: DS9 version 1.0\n"
    f"global color = {DEFAULT_COLOR} fill = no width = {DEFAULT_WIDTH} dash = no\n"
    f"global font = {DEFAULT_FONT} fontsize = {DEFAULT_FONT_SIZE} "
    f"fontweight = {DEFAULT_FONT_WEIGHT} fontslant = {DEFAULT_FONT_SLANT}"
)

#: `key = value` in a property tail or a `global` line. The value runs to
#: the next key, so `line = 1 0` keeps both of its numbers.
_PROPERTY = re.compile(r"(\w+)\s*=\s*([^=]*?)(?=\s+\w+\s*=|$)")

#: Everything the globals and the property tails can set.
DEFAULTS: dict[str, object] = {
    "color": DEFAULT_COLOR,
    "fill": False,
    "width": DEFAULT_WIDTH,
    "dash": False,
    "font": DEFAULT_FONT,
    "fontsize": DEFAULT_FONT_SIZE,
    "fontweight": DEFAULT_FONT_WEIGHT,
    "fontslant": DEFAULT_FONT_SLANT,
    "angle": 0.0,
    "justify": DEFAULT_JUSTIFY,
    "line": (False, False),
}


class IllustrateFileError(ValueError):
    """A line that is not an illustration."""


def serialise(elements: list[Element]) -> str:
    """The elements as an illustrate file, header and all."""
    lines = [HEADER]
    lines.extend(element.to_line() for element in elements)
    return "\n".join(lines) + "\n"


def save(path: str | Path, elements: list[Element]) -> None:
    """Write the elements to a file."""
    Path(path).write_text(serialise(elements), encoding="utf-8")


def load(path: str | Path) -> list[Element]:
    """Read the elements from a file."""
    return parse(Path(path).read_text(encoding="utf-8"))


def parse(text: str) -> list[Element]:
    """Read an illustrate file's text.

    A line that cannot be understood is skipped rather than raising: DS9's
    own writer has a stray bracket in the line shape's width
    (`illustrateline.tcl:127`), and a file that is mostly good is worth
    reading.
    """
    globals_: dict[str, object] = dict(DEFAULTS)
    elements: list[Element] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("global"):
            globals_.update(_properties(line[len("global") :], globals_))
            continue
        try:
            element = _element(line, globals_)
        except (IllustrateFileError, ValueError, IndexError):
            continue
        if element is not None:
            elements.append(element)
    return elements


def _properties(text: str, defaults: dict[str, object]) -> dict[str, object]:
    """The `key = value` pairs in a globals line or a property tail."""
    found: dict[str, object] = {}
    for key, value in _PROPERTY.findall(text):
        key = key.lower()
        if key not in DEFAULTS:
            continue
        # DS9's writer leaves a stray bracket in one place; nothing is lost
        # by ignoring characters that cannot belong to any of these values.
        cleaned = value.strip().rstrip(")").strip()
        found[key] = _value(key, cleaned, defaults)
    return found


def _value(key: str, text: str, defaults: dict[str, object]) -> object:
    """One property's value, in the type that property has."""
    if key in ("fill", "dash"):
        return text.lower() in ("1", "yes", "true")
    if key == "width":
        return int(float(text))
    if key == "fontsize":
        return int(float(text))
    if key == "angle":
        return float(text)
    if key == "line":
        parts = text.split()
        return (bool(int(float(parts[0]))), bool(int(float(parts[1])))) if len(parts) >= 2 else (False, False)
    return text or str(defaults.get(key, ""))


def _style(properties: dict[str, object]) -> Style:
    """The drawing style out of a property set."""
    return Style(
        color=str(properties["color"]),
        fill=bool(properties["fill"]),
        width=int(properties["width"]),  # type: ignore[arg-type]
        dash=bool(properties["dash"]),
    )


def _element(line: str, globals_: dict[str, object]) -> Element | None:
    """One line of the file as an element."""
    body, _, tail = line.partition("#")
    properties = dict(globals_)
    properties.update(_properties(tail, globals_))

    # shlex, so a text element's quoted words -- and a path with a space in
    # it -- survive being split.
    try:
        words = shlex.split(body.strip())
    except ValueError:
        words = body.split()
    if not words:
        return None

    kind = words[0].lower()
    numbers = words[1:]
    style = _style(properties)

    if kind == "circle":
        x, y, radius = (float(value) for value in numbers[:3])
        return Circle(style=style, x=x, y=y, radius=radius)

    if kind in ("ellipse", "box"):
        x, y, r1, r2 = (float(value) for value in numbers[:4])
        maker = Ellipse if kind == "ellipse" else Box
        return maker(style=style, x=x, y=y, radius1=r1, radius2=r2)

    if kind in ("polygon", "line"):
        values = [float(value) for value in numbers]
        if len(values) < 4:
            raise IllustrateFileError(f"{kind} needs at least two points")
        points = list(zip(values[0::2], values[1::2], strict=False))
        if kind == "polygon":
            return Polygon(style=style, points=points)
        first, last = properties["line"]  # type: ignore[misc]
        return Line(style=style, points=points, arrow_first=first, arrow_last=last)

    if kind == "text":
        x, y = float(numbers[0]), float(numbers[1])
        words_of_text = numbers[2] if len(numbers) > 2 else ""
        return Text(
            style=style,
            x=x,
            y=y,
            text=words_of_text.replace("\\n", "\n"),
            font=str(properties["font"]),
            font_size=int(properties["fontsize"]),  # type: ignore[arg-type]
            font_weight=str(properties["fontweight"]),
            font_slant=str(properties["fontslant"]),
            angle=float(properties["angle"]),  # type: ignore[arg-type]
            justify=str(properties["justify"]),
        )

    if kind == "image":
        x, y = float(numbers[0]), float(numbers[1])
        path = numbers[2] if len(numbers) > 2 else ""
        width = float(numbers[3]) if len(numbers) > 3 else 0.0
        height = float(numbers[4]) if len(numbers) > 4 else 0.0
        return Image(style=style, x=x, y=y, path=path, width=width, height=height)

    raise IllustrateFileError(f"unknown shape: {kind}")
