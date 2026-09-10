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
The numbers along a coordinate grid's axes, and DS9's format for them.

DS9 takes AST's format specification, and the characters are worth setting
out because they are not `printf`'s (`ds9/doc/ref/grid.html`, Numeric
Formats):

    +   prefix a plus sign to positive values
    z   pad the first field with leading zeros
    i   separate fields with a colon -- the default
    b   separate fields with a blank
    l   separate fields with a letter: h/d, m, s
    g   as `l`, but with the separators as superscripts
    d   include a degrees field, and express the angle in degrees
    h   express the angle as time, with an hours field
    m   include a minutes field
    s   include a seconds field
    t   express as time; equivalent to `h` on its own
    .N  give N decimal places on the last field

"All of the above format specifiers are case-insensitive. If several
characters make conflicting requests (e.g. if both 'i' and 'b' appear), then
the character occurring last takes precedence, except that 'd' and 'h'
always override 't'." Both rules are implemented and tested; without the
last-one-wins rule, `ib` and `bi` would mean the same thing, and they do
not.

DS9's own defaults are `d.3` for degrees and `hms.1` / `dms.1` for
sexagesimal, and a plain `printf`-style spec (`%.7g`) is passed through, as
its documentation allows.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

#: DS9's default format for a longitude in each style.
DEFAULT_LONGITUDE_FORMAT = {"sexagesimal": "hms.1", "degrees": "d.3"}

#: And for a latitude, which is never expressed in hours.
DEFAULT_LATITUDE_FORMAT = {"sexagesimal": "dms.1", "degrees": "d.3"}

#: The separator each of DS9's separator characters asks for.
SEPARATORS = {"i": ":", "b": " "}

#: The letters `l` and `g` use, per field, for an angle and for a time.
DEGREE_LETTERS = ("d", "m", "s")
TIME_LETTERS = ("h", "m", "s")

#: How many decimals `.` with an asterisk gives.
DEFAULT_DECIMALS = 1


class LabelPosition(Enum):
    """Which edge of the image a label sits on."""

    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


@dataclass(frozen=True)
class Label:
    """One number on an axis.

    Attributes:
        text: The formatted number.
        x, y: Where it goes, in image pixels.
        position: Which edge it belongs to, which decides its alignment.
    """

    text: str
    x: float
    y: float
    position: LabelPosition


@dataclass(frozen=True)
class NumericFormat:
    """One parsed DS9 format specification.

    Attributes:
        as_time: Express the angle in hours rather than degrees.
        fields: How many sexagesimal fields to show -- 1 for degrees only,
            2 to include minutes, 3 to include seconds.
        separator: What goes between fields: ":", " ", or "" for letters.
        letters: Use h/d, m, s as separators.
        superscript: `g` -- letters, marked for drawing as superscripts.
        plus: Prefix a plus sign to positive values.
        zeros: Pad the first field with leading zeros.
        decimals: Decimal places on the last field.
        printf: A plain printf spec, when the string was one; the rest of
            the fields are then unused.
    """

    as_time: bool = False
    fields: int = 1
    separator: str = ":"
    letters: bool = False
    superscript: bool = False
    plus: bool = False
    zeros: bool = False
    decimals: int = 0
    printf: str | None = None


#: A plain printf spec, which DS9 passes to C's printf unchanged.
_PRINTF = re.compile(r"^%[#0\-+ ]*\d*(?:\.\d+)?[eEfgGd]$")


def parse_format(spec: str) -> NumericFormat:
    """Read one of DS9's format specifications.

    Args:
        spec: The specification, e.g. `hms.1`, `+zdms.2`, `%1.7G`, or empty.

    Returns:
        The parsed format. An empty specification comes back as degrees
        with no decimals, which the callers override with their own default.
    """
    text = (spec or "").strip()
    if not text:
        return NumericFormat()
    if _PRINTF.match(text):
        return NumericFormat(printf=text)

    decimals = 0
    decimal_point = text.find(".")
    if decimal_point >= 0:
        tail = text[decimal_point + 1 :]
        decimals = DEFAULT_DECIMALS if tail.startswith("*") else _leading_int(tail)
        text = text[:decimal_point]

    lowered = text.lower()
    plus = "+" in text
    zeros = "z" in lowered

    # Last one wins among the separator characters, which is DS9's rule and
    # the reason this scans rather than testing membership.
    separator = ":"
    letters = False
    superscript = False
    for character in lowered:
        if character in SEPARATORS:
            separator, letters, superscript = SEPARATORS[character], False, False
        elif character == "l":
            separator, letters, superscript = "", True, False
        elif character == "g":
            separator, letters, superscript = "", True, True

    # `d` and `h` always override `t`; `h` and `t` both mean time.
    as_time = ("h" in lowered or "t" in lowered) and "d" not in lowered

    fields = 1
    if "s" in lowered:
        fields = 3
    elif "m" in lowered:
        fields = 2
    # "This request is ignored if 'd' or 'h' is given, unless a minutes
    # field is also included" -- so `ds` is degrees, and `dms` is three.
    if "s" in lowered and "m" not in lowered and ("d" in lowered or "h" in lowered):
        fields = 1

    return NumericFormat(
        as_time=as_time,
        fields=fields,
        separator=separator,
        letters=letters,
        superscript=superscript,
        plus=plus,
        zeros=zeros,
        decimals=decimals,
    )


def _leading_int(text: str) -> int:
    """The integer at the start of a string, or zero."""
    match = re.match(r"\d+", text)
    return int(match.group()) if match else 0


def format_coordinate(value: float, spec: str) -> str:
    """Format one coordinate in degrees, per a DS9 format specification.

    Args:
        value: The coordinate, in degrees.
        spec: The specification. Empty gives plain degrees.

    Returns:
        The formatted string.
    """
    return format_parsed(value, parse_format(spec))


def format_parsed(value: float, chosen: NumericFormat) -> str:
    """Format one coordinate with an already-parsed specification."""
    if chosen.printf is not None:
        return _printf(value, chosen.printf)

    number = float(value)
    negative = number < 0
    number = abs(number)
    if chosen.as_time:
        number /= 15.0

    parts, remainder = _fields(number, chosen.fields)
    text = _join(parts, remainder, chosen, chosen.decimals)
    sign = "-" if negative else ("+" if chosen.plus else "")
    return f"{sign}{text}"


def _fields(number: float, count: int) -> tuple[list[int], float]:
    """Split a value into whole fields and a fractional remainder.

    Rounding is deliberately not done here: rounding 59.96 seconds to 60.0
    has to carry into the minutes, and that is `_join`'s problem once it
    knows how many decimals it is keeping.
    """
    if count <= 1:
        return ([], number)
    whole = [int(number)]
    remainder = (number - whole[0]) * 60.0
    if count >= 3:
        whole.append(int(remainder))
        remainder = (remainder - whole[1]) * 60.0
    return (whole, remainder)


def _join(parts: list[int], last: float, chosen: NumericFormat, decimals: int) -> str:
    """Assemble the fields, carrying a rounded last field upwards.

    59.96 seconds at one decimal is 60.0, which is not a time; it has to
    become the next minute. Without this a grid label can read 12:34:60.0.
    """
    rounded = round(last, decimals)
    carried = list(parts)
    if carried and rounded >= 60.0:
        rounded -= 60.0
        carried[-1] += 1
        for index in range(len(carried) - 1, 0, -1):
            if carried[index] >= 60:
                carried[index] -= 60
                carried[index - 1] += 1

    widths = [2] * len(carried)
    if carried and not chosen.zeros:
        widths[0] = 0

    pieces = [
        f"{value:0{width}d}" if width else str(value) for value, width in zip(carried, widths, strict=True)
    ]
    tail = (
        f"{rounded:0{3 + decimals if decimals else 2}.{decimals}f}"
        if carried
        else (f"{rounded:.{decimals}f}")
    )
    pieces.append(tail)

    if not chosen.letters:
        return chosen.separator.join(pieces) if chosen.separator else "".join(pieces)

    letters = TIME_LETTERS if chosen.as_time else DEGREE_LETTERS
    marked = []
    for index, piece in enumerate(pieces):
        letter = letters[index] if index < len(letters) else ""
        # `g` asks for the separator as a superscript; the caller draws it,
        # and marking it is all that can be done in a plain string.
        marked.append(f"{piece}^{letter}^" if chosen.superscript and letter else f"{piece}{letter}")
    return "".join(marked)


def _printf(value: float, spec: str) -> str:
    """Apply a C printf specification, as DS9's documentation allows."""
    try:
        if spec.lower().endswith("d"):
            return spec % int(round(value))
        return spec % float(value)
    except (TypeError, ValueError):
        return f"{value:g}"


def default_format(spec: str, latitude: bool, sky_format: str) -> str:
    """The format to use, falling back to DS9's default for the style.

    Args:
        spec: What the user set, possibly empty.
        latitude: Whether this axis is a latitude, which is never in hours.
        sky_format: "sexagesimal" or "degrees".
    """
    if spec.strip():
        return spec
    defaults = DEFAULT_LATITUDE_FORMAT if latitude else DEFAULT_LONGITUDE_FORMAT
    return defaults.get(sky_format, "d.3")


def nice_spacing(span: float, target: int, sexagesimal: bool) -> float:
    """A round interval that divides `span` into about `target` steps.

    Args:
        span: The range to cover, in degrees.
        target: About how many lines are wanted.
        sexagesimal: Choose an interval that is round in minutes and
            seconds rather than in decimal degrees -- a grid labelled
            00:01:23 every 0.02 degrees is unreadable.

    Returns:
        The interval, in degrees. Never zero: a zero interval is an
        infinite loop in every caller.
    """
    if span <= 0 or target <= 0:
        return 1.0

    wanted = span / target
    candidates = _SEXAGESIMAL_STEPS if sexagesimal else _DECIMAL_STEPS
    for step in candidates:
        if step >= wanted:
            return step

    # Larger than every candidate: fall back to a decade of degrees.
    decade = 10.0 ** math.ceil(math.log10(wanted))
    return max(decade, 1e-9)


#: Round intervals in degrees, for a decimal grid.
_DECIMAL_STEPS: tuple[float, ...] = tuple(
    value * 10.0**power for power in range(-6, 3) for value in (1.0, 2.0, 5.0)
)

#: Round intervals for a sexagesimal grid: seconds, then minutes, then
#: degrees, at the steps a reader expects to see.
_SEXAGESIMAL_STEPS: tuple[float, ...] = (
    *(seconds / 3600.0 for seconds in (0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 20, 30)),
    *(minutes / 60.0 for minutes in (1, 2, 5, 10, 15, 20, 30)),
    *(float(degrees) for degrees in (1, 2, 5, 10, 15, 20, 30, 45, 60, 90)),
)
