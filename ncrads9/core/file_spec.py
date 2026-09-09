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
DS9's file-specification syntax: `foo.fits[2][100:200,*,4]`.

DS9 and funtools let a filename carry the extension, an image or cube
subsection, binning columns and a row filter, all in square brackets, so that
one string names exactly what to display. The grammar is set out in
`ds9/doc/ref/file.html` under FITS Image and FITS Binary Events Table:

    filename
    filename[ext]
    filename[ext][sect]
    filename[sect]
    filename[ext,sect]
    filename[ext][bin][sect]        (and the other orderings)

    ext:  extension name | extension number
    sect: [x,y] | [x,y,block] | [x,y,z] | [x,y,block,z]
          where each axis is  lo:hi  |  dim@centre  |  *
          plus the combined  dim@xcentre@ycentre  form for x and y at once,
          and a trailing `p` to read the numbers as physical rather than
          image coordinates
    bin:  [bin=colx,coly] | [bin=colx,coly,colz] | [bin=colz]
          each optionally followed by a filter; also spelled key= or binkey=
    filter: any expression, e.g. ccd_id==3&&energy>4000

Parsing is separated from applying so that the syntax can be tested without
a FITS file, and so the XPA `file` access point (M8) and the command line can
share one parser. `FileSpec.apply_section` is the only part that needs an
array.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

#: The keywords that introduce a binning group. DS9 accepts all three.
BIN_KEYWORDS: tuple[str, ...] = ("bin", "binkey", "key")

#: Columns DS9 bins on when only the third is named, as in `[bin=pha]`.
DEFAULT_BIN_COLUMNS: tuple[str, str] = ("x", "y")

#: Characters that make a bracket group a row filter rather than a section
#: or an extension name.
FILTER_CHARACTERS = frozenset("<>=!&|")

#: An extension may be named or numbered; nothing else is a bare identifier.
_EXTENSION = re.compile(r"^[A-Za-z_][\w.\-]*$|^\d+$")
_RANGE = re.compile(r"^(-?\d+):(-?\d+)$")
_CENTRED = re.compile(r"^(\d+)@(-?\d+(?:\.\d+)?)$")
_CENTRED_XY = re.compile(r"^(\d+)@(-?\d+(?:\.\d+)?)@(-?\d+(?:\.\d+)?)$")
_INTEGER = re.compile(r"^\d+$")


class FileSpecError(ValueError):
    """A file specification that cannot be parsed."""


@dataclass(frozen=True)
class AxisSpec:
    """One axis of a subsection.

    Bounds are one-based and inclusive, as FITS and DS9 count pixels. A
    wildcard axis carries no bounds and takes the array's own extent when
    resolved.
    """

    lo: int | None = None
    hi: int | None = None

    @property
    def is_wildcard(self) -> bool:
        """True for DS9's `*`, meaning the whole axis."""
        return self.lo is None and self.hi is None

    @classmethod
    def wildcard(cls) -> AxisSpec:
        """DS9's `*`."""
        return cls()

    @classmethod
    def between(cls, lo: int, hi: int) -> AxisSpec:
        """DS9's `lo:hi`, in either order."""
        return cls(min(lo, hi), max(lo, hi))

    @classmethod
    def centred(cls, width: int, centre: float) -> AxisSpec:
        """DS9's `dim@centre`: `width` pixels centred on `centre`.

        The box runs from `centre - width // 2` and is `width` pixels long,
        so the centre pixel is always inside it and an even width takes its
        extra pixel below the centre. DS9's only documented example,
        `[256@512@512]`, comes out as 384:639 under this rule.

        The tie-breaking for an even width is a choice: DS9's own source does
        not spell it out anywhere findable, and either side is defensible.
        What matters is that it is fixed -- rounding `centre - (width-1)/2`
        instead would put an even-width box one pixel further down for an odd
        centre than for an even one, because Python rounds halves to even.

        Raises:
            FileSpecError: If `width` is not positive.
        """
        if width < 1:
            raise FileSpecError(f"section width must be positive, got {width}")
        lo = int(math.floor(centre)) - width // 2
        return cls(lo, lo + width - 1)

    def resolve(self, length: int) -> tuple[int, int]:
        """Clip to an axis of `length` pixels.

        Args:
            length: The axis's extent in pixels.

        Returns:
            One-based inclusive (lo, hi), clipped to [1, length].
        """
        if self.is_wildcard:
            return 1, length
        lo = max(1, min(int(self.lo or 1), length))
        hi = max(1, min(int(self.hi or length), length))
        return min(lo, hi), max(lo, hi)

    def __str__(self) -> str:
        return "*" if self.is_wildcard else f"{self.lo}:{self.hi}"


@dataclass(frozen=True)
class Section:
    """An image or cube subsection, with an optional block factor."""

    x: AxisSpec = field(default_factory=AxisSpec.wildcard)
    y: AxisSpec = field(default_factory=AxisSpec.wildcard)
    z: AxisSpec | None = None
    block: int = 1
    #: True when the numbers are physical rather than image coordinates,
    #: which DS9 marks with a trailing `p`.
    physical: bool = False

    def __str__(self) -> str:
        parts = [str(self.x), str(self.y)]
        if self.block != 1:
            parts.append(str(self.block))
        if self.z is not None:
            parts.append(str(self.z))
        return ",".join(parts) + ("p" if self.physical else "")


@dataclass(frozen=True)
class BinSpec:
    """How to turn a FITS binary table into an image."""

    #: Two columns for the image axes, or three to bin on a value column.
    columns: tuple[str, ...] = DEFAULT_BIN_COLUMNS
    #: A row filter given inside the bin group, as DS9's
    #: `[bin=colx,coly,filter]` allows.
    filter: str = ""
    #: The keyword this was written with, so `__str__` round-trips.
    keyword: str = "bin"

    def __str__(self) -> str:
        parts = [*self.columns]
        if self.filter:
            parts.append(self.filter)
        return f"{self.keyword}=" + ",".join(parts)


@dataclass(frozen=True)
class FileSpec:
    """A parsed DS9 file specification."""

    path: Path
    #: Extension number or EXTNAME, or None for DS9's default search.
    extension: int | str | None = None
    section: Section | None = None
    bin: BinSpec | None = None
    #: Row filters, in the order given. Several groups may each carry one.
    filters: tuple[str, ...] = ()

    @property
    def has_specification(self) -> bool:
        """True when anything was given in brackets."""
        return bool(self.extension is not None or self.section or self.bin or self.filters)

    @property
    def filter_expression(self) -> str:
        """Every filter, including the bin group's, joined with `&&`."""
        parts = [*self.filters]
        if self.bin is not None and self.bin.filter:
            parts.append(self.bin.filter)
        return "&&".join(parts)

    def __str__(self) -> str:
        """Rebuild the specification, so parsing round-trips."""
        text = str(self.path)
        if self.extension is not None:
            text += f"[{self.extension}]"
        if self.bin is not None:
            text += f"[{self.bin}]"
        if self.section is not None:
            text += f"[{self.section}]"
        for expression in self.filters:
            text += f"[{expression}]"
        return text


def _split_groups(text: str) -> tuple[str, list[str]]:
    """Split a specification into its path and its bracket groups.

    A path may itself contain brackets -- `/data/[run3]/foo.fits` -- so the
    split is taken at the first `[` from which the rest of the string is
    nothing but balanced bracket groups. That is the only reading under which
    every bracket belongs to the specification.

    Args:
        text: The whole specification.

    Returns:
        (path, group contents without their brackets).

    Raises:
        FileSpecError: If a bracket is left unclosed.
    """
    for index, character in enumerate(text):
        if character != "[":
            continue
        groups = _parse_groups(text[index:])
        if groups is not None:
            return text[:index], groups
    if "[" in text and "]" not in text:
        raise FileSpecError(f"unclosed '[' in {text!r}")
    return text, []


def _parse_groups(text: str) -> list[str] | None:
    """Read `text` as a run of `[...]` groups, or None if it is not one."""
    groups: list[str] = []
    position = 0
    while position < len(text):
        if text[position] != "[":
            return None
        depth = 0
        for end in range(position, len(text)):
            if text[end] == "[":
                depth += 1
            elif text[end] == "]":
                depth -= 1
                if depth == 0:
                    groups.append(text[position + 1 : end])
                    position = end + 1
                    break
        else:
            return None
    return groups


def _is_filter(token: str) -> bool:
    """Whether a token is a row filter rather than a name or a range."""
    return any(character in FILTER_CHARACTERS for character in token)


def _axis(token: str) -> AxisSpec | None:
    """Parse one section axis, or None if the token is not an axis."""
    token = token.strip()
    if token == "*":
        return AxisSpec.wildcard()
    match = _RANGE.match(token)
    if match:
        return AxisSpec.between(int(match.group(1)), int(match.group(2)))
    match = _CENTRED.match(token)
    if match:
        return AxisSpec.centred(int(match.group(1)), float(match.group(2)))
    return None


def _parse_section(tokens: list[str]) -> Section | None:
    """Parse a section from its comma-separated tokens.

    Returns None when the tokens are not a section, so the caller can try the
    other readings. DS9's orderings are `x,y`, `x,y,block`, `x,y,z` and
    `x,y,block,z`, with `dim@xcentre@ycentre` standing in for `x,y`.
    """
    if not tokens:
        return None

    physical = False
    tokens = list(tokens)
    if tokens[-1].endswith(("p", "P")) and not _is_filter(tokens[-1]):
        stripped = tokens[-1][:-1]
        # A bare "p" would leave an empty token; that is not a section.
        if not stripped:
            return None
        tokens[-1] = stripped
        physical = True

    combined = _CENTRED_XY.match(tokens[0])
    if combined is not None:
        width = int(combined.group(1))
        x = AxisSpec.centred(width, float(combined.group(2)))
        y = AxisSpec.centred(width, float(combined.group(3)))
        rest = tokens[1:]
    else:
        if len(tokens) < 2:
            return None
        first, second = _axis(tokens[0]), _axis(tokens[1])
        if first is None or second is None:
            return None
        x, y, rest = first, second, tokens[2:]

    if len(rest) > 2:
        return None

    block = 1
    z: AxisSpec | None = None
    for token in rest:
        token = token.strip()
        if _INTEGER.match(token) and z is None:
            # A bare integer here is the block factor; a z range has a colon
            # or an @, so the two cannot be confused.
            block = int(token)
            continue
        axis = _axis(token)
        if axis is None:
            return None
        z = axis

    return Section(x=x, y=y, z=z, block=max(1, block), physical=physical)


def _parse_bin(tokens: list[str], keyword: str) -> BinSpec:
    """Parse a bin group's tokens.

    `[bin=colz]` bins DS9's default `x` and `y` columns on `colz`. A token
    carrying a comparison operator is a filter, not a column, which is how
    `[bin=x,y,pha]` and `[bin=colx,coly,filter]` are told apart.
    """
    columns = [token.strip() for token in tokens if token.strip() and not _is_filter(token)]
    filters = [token.strip() for token in tokens if _is_filter(token)]
    if not columns:
        raise FileSpecError(f"{keyword}= needs at least one column")
    if len(columns) == 1:
        columns = [*DEFAULT_BIN_COLUMNS, columns[0]]
    if len(columns) > 3:
        raise FileSpecError(f"{keyword}= takes at most three columns, got {len(columns)}")
    return BinSpec(
        columns=tuple(columns),
        filter="&&".join(filters),
        keyword=keyword,
    )


def _extension(token: str) -> int | str | None:
    """Parse an extension number or name, or None if it is neither."""
    token = token.strip()
    if not _EXTENSION.match(token):
        return None
    return int(token) if token.isdigit() else token


def _split_tokens(group: str) -> list[str]:
    """Split a group on commas that are not inside parentheses."""
    tokens: list[str] = []
    depth = 0
    current: list[str] = []
    for character in group:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        if character == "," and depth == 0:
            tokens.append("".join(current))
            current = []
            continue
        current.append(character)
    tokens.append("".join(current))
    return tokens


def parse(specification: str) -> FileSpec:
    """Parse a DS9 file specification.

    Args:
        specification: A path, optionally followed by bracket groups.

    Returns:
        The parsed specification. A plain path yields a `FileSpec` whose
        every optional field is unset.

    Raises:
        FileSpecError: If a group cannot be read, or contradicts an earlier
            one (two extensions, say).
    """
    text = specification.strip()
    # A whole specification is often quoted to get it past the shell.
    for quote in ('"', "'"):
        if len(text) > 1 and text.startswith(quote) and text.endswith(quote):
            text = text[1:-1].strip()

    path_text, groups = _split_groups(text)
    if not path_text:
        raise FileSpecError(f"no filename in {specification!r}")

    extension: int | str | None = None
    section: Section | None = None
    bin_spec: BinSpec | None = None
    filters: list[str] = []

    def set_extension(value: int | str) -> None:
        nonlocal extension
        if extension is not None:
            raise FileSpecError(f"two extensions given in {specification!r}")
        extension = value

    def set_section(value: Section) -> None:
        nonlocal section
        if section is not None:
            raise FileSpecError(f"two sections given in {specification!r}")
        section = value

    def set_bin(value: BinSpec) -> None:
        nonlocal bin_spec
        if bin_spec is not None:
            raise FileSpecError(f"two bin groups given in {specification!r}")
        bin_spec = value

    for group in groups:
        content = group.strip()
        if not content:
            continue
        tokens = _split_tokens(content)

        # `[ext,sect]` and `[ext,bin]`: DS9 allows the extension to share a
        # group with what follows it.
        leading = _extension(tokens[0]) if len(tokens) > 1 else None
        if leading is not None:
            keyword = _bin_keyword(tokens[1])
            if keyword is not None:
                set_extension(leading)
                set_bin(_parse_bin([tokens[1].split("=", 1)[1], *tokens[2:]], keyword))
                continue
            nested = _parse_section(tokens[1:])
            if nested is not None:
                set_extension(leading)
                set_section(nested)
                continue

        keyword = _bin_keyword(tokens[0])
        if keyword is not None:
            set_bin(_parse_bin([tokens[0].split("=", 1)[1], *tokens[1:]], keyword))
            continue

        parsed_section = _parse_section(tokens)
        if parsed_section is not None:
            set_section(parsed_section)
            continue

        if len(tokens) == 1:
            single = _extension(tokens[0])
            if single is not None:
                set_extension(single)
                continue

        if all(_is_filter(token) for token in tokens):
            # Funtools reads a comma inside a filter group as `and`.
            filters.append("&&".join(token.strip() for token in tokens))
            continue

        raise FileSpecError(f"cannot parse {group!r} in {specification!r}")

    return FileSpec(
        path=Path(path_text),
        extension=extension,
        section=section,
        bin=bin_spec,
        filters=tuple(filters),
    )


def _bin_keyword(token: str) -> str | None:
    """The bin keyword a token opens with, or None."""
    if "=" not in token:
        return None
    keyword = token.split("=", 1)[0].strip().lower()
    return keyword if keyword in BIN_KEYWORDS else None
