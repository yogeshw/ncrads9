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
Colour tags: painting a range of the colorbar a solid colour.

DS9 lets you mark a stretch of the colorbar and give it one flat colour, so
that everything in that range of values stands out -- the sky in grey and
anything above a threshold in red, say. A tag is a start, a stop and a
colour name (`ColorTag` in `tksao/colorbar/colortag.C`), tags are held per
frame, and DS9's Colormap Parameters dialog can load, save and delete them.

Positions run from 0 at the bottom of the colorbar to 1 at the top, which is
where DS9 keeps them too: a tag marks a place in the *colour table*, so
changing the clip limits moves which data it covers, and changing the
colormap does not move the tag.

The file format is DS9's: one tag per line, `start stop colour`. A line
beginning with `#` is a comment and anything after the third field is
ignored, so a `#rrggbb` colour and a trailing comment can coexist. DS9 writes
the numbers as colour-table levels rather than plainly normalised, which for
its default 256-level table is the same thing.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

#: The colours DS9's tag menu offers, and their RGB.
TAG_COLORS: dict[str, tuple[float, float, float]] = {
    "black": (0.0, 0.0, 0.0),
    "white": (1.0, 1.0, 1.0),
    "red": (1.0, 0.0, 0.0),
    "green": (0.0, 1.0, 0.0),
    "blue": (0.0, 0.0, 1.0),
    "cyan": (0.0, 1.0, 1.0),
    "magenta": (1.0, 0.0, 1.0),
    "yellow": (1.0, 1.0, 0.0),
}

#: What an unrecognised colour name falls back to.
DEFAULT_TAG_COLOR = "red"


class ColorTagError(ValueError):
    """A colour tag that cannot be read, for the reason given."""


def parse_color(name: str) -> tuple[float, float, float]:
    """Turn a colour name or `#rrggbb` into RGB in 0..1.

    Args:
        name: One of `TAG_COLORS`, or a six-digit hex triple with or without
            its leading `#`.

    Returns:
        (red, green, blue).

    Raises:
        ColorTagError: If the name is neither.
    """
    text = str(name).strip().lower()
    if text in TAG_COLORS:
        return TAG_COLORS[text]

    hexadecimal = text[1:] if text.startswith("#") else text
    if len(hexadecimal) == 6:
        try:
            return tuple(int(hexadecimal[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]
        except ValueError as exc:
            raise ColorTagError(f"not a colour: {name!r}") from exc
    raise ColorTagError(f"not a colour: {name!r}; expected #rrggbb or one of {', '.join(sorted(TAG_COLORS))}")


@dataclass(frozen=True)
class ColorTag:
    """One stretch of the colorbar, painted flat.

    Attributes:
        start: Where the tag begins, 0 at the bottom of the colorbar.
        stop: Where it ends. Swapped with `start` if it is smaller.
        color: A name from `TAG_COLORS`, or `#rrggbb`.
    """

    start: float
    stop: float
    color: str = DEFAULT_TAG_COLOR

    def __post_init__(self) -> None:
        low, high = sorted((float(self.start), float(self.stop)))
        object.__setattr__(self, "start", max(0.0, min(low, 1.0)))
        object.__setattr__(self, "stop", max(0.0, min(high, 1.0)))
        parse_color(self.color)

    @property
    def rgb(self) -> tuple[float, float, float]:
        """The tag's colour as RGB in 0..1."""
        return parse_color(self.color)

    def contains(self, position: float) -> bool:
        """Whether a colorbar position falls inside the tag."""
        return self.start <= float(position) <= self.stop

    def __str__(self) -> str:
        return f"{self.start:.6g} {self.stop:.6g} {self.color}"


class ColorTagSet:
    """The tags on one frame's colorbar, in the order they were added."""

    def __init__(self, tags: list[ColorTag] | None = None) -> None:
        """
        Args:
            tags: Tags to start with.
        """
        self._tags: list[ColorTag] = list(tags or ())

    def __len__(self) -> int:
        return len(self._tags)

    def __iter__(self):
        return iter(self._tags)

    def __bool__(self) -> bool:
        return bool(self._tags)

    @property
    def tags(self) -> tuple[ColorTag, ...]:
        """The tags, oldest first."""
        return tuple(self._tags)

    def add(self, tag: ColorTag) -> ColorTag:
        """Add a tag and return it."""
        self._tags.append(tag)
        return tag

    def replace(self, index: int, tag: ColorTag) -> None:
        """Replace one tag.

        Raises:
            IndexError: If there is no tag at `index`.
        """
        self._tags[index] = tag

    def remove(self, index: int) -> None:
        """Delete one tag.

        Raises:
            IndexError: If there is no tag at `index`.
        """
        del self._tags[index]

    def clear(self) -> None:
        """Delete every tag, which is DS9's Delete Color Tag."""
        self._tags.clear()

    def index_at(self, position: float) -> int | None:
        """Which tag covers a colorbar position.

        The most recently added wins, since that is the one drawn on top.

        Args:
            position: 0 at the bottom of the colorbar, 1 at the top.

        Returns:
            The tag's index, or None if no tag covers the position.
        """
        for index in range(len(self._tags) - 1, -1, -1):
            if self._tags[index].contains(position):
                return index
        return None

    def apply(self, colors: NDArray[np.floating]) -> NDArray[np.floating]:
        """Paint the tags onto a colour table.

        Args:
            colors: An (n, 3) table of RGB in 0..1.

        Returns:
            A new table with each tag's range replaced by its flat colour.
            The input is returned unchanged, and uncopied, when there are no
            tags -- which is the usual case and worth not copying for.
        """
        if not self._tags or colors is None or len(colors) == 0:
            return colors

        painted = np.array(colors, dtype=np.float64, copy=True)
        count = painted.shape[0]
        for tag in self._tags:
            low = int(np.floor(tag.start * (count - 1)))
            high = int(np.ceil(tag.stop * (count - 1)))
            painted[low : high + 1] = tag.rgb
        return painted

    # -- DS9's tag files -----------------------------------------------------

    def to_text(self) -> str:
        """The tags in DS9's file format, one per line."""
        return "".join(f"{tag}\n" for tag in self._tags)

    @classmethod
    def from_text(cls, text: str) -> ColorTagSet:
        """Read DS9's tag file format.

        Args:
            text: The file's contents. Blank lines are skipped, a line
                starting with `#` is a comment, and anything after the third
                field on a line is ignored -- which is how a trailing comment
                works without a rule of its own. Stripping from the first `#`
                instead would eat a `#rrggbb` colour, which is exactly what
                it used to do.

        Returns:
            The tags found.

        Raises:
            ColorTagError: If a line is not `start stop colour`.
        """
        tags: list[ColorTag] = []
        for number, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                raise ColorTagError(f"line {number}: expected 'start stop colour', got {raw!r}")
            try:
                start, stop = float(parts[0]), float(parts[1])
            except ValueError as exc:
                raise ColorTagError(f"line {number}: {parts[0]!r} and {parts[1]!r} are not numbers") from exc
            color = parts[2] if len(parts) > 2 else DEFAULT_TAG_COLOR
            tags.append(ColorTag(start, stop, color))
        return cls(tags)

    @classmethod
    def load(cls, path: str | Path) -> ColorTagSet:
        """Read a tag file.

        Raises:
            ColorTagError: If the file cannot be read or parsed.
            OSError: If it cannot be opened.
        """
        return cls.from_text(Path(path).read_text())

    def save(self, path: str | Path) -> None:
        """Write a tag file.

        Raises:
            OSError: If it cannot be written.
        """
        Path(path).write_text(self.to_text())
