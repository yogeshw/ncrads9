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
The WCS keywords of a header, as text: DS9's `.wcs` files.

DS9 lets a frame's WCS be replaced, extended or put back as it was -- from
the WCS Parameters dialog, from `xpaset ds9 wcs replace foo.wcs`, from the
command line -- and reads and writes it as a plain list of FITS keywords,
one per line (`wcs.tcl`: `WCSToVar`, `WCSFromVar`, `WCSSaveFile`)::

    CTYPE1  = 'RA---TAN'
    CRVAL1  = 202.48 / reference value
    CTYPE1A = 'GLON-TAN'

This module is that text format and the header surgery around it, kept
apart from Qt so the dialog, the XPA access point and the tests share one
reading of a `.wcs` file.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from astropy.io import fits

#: Letters FITS allows on an alternate WCS description, lower case as DS9
#: spells its systems (`wcsa`..`wcsz`).
ALTERNATE_LETTERS: tuple[str, ...] = tuple("abcdefghijklmnopqrstuvwxyz")

#: Every keyword that describes a WCS, with an optional alternate letter.
#: The observation date is deliberately not here: it is DS9's too, on the
#: dialog, but it describes the observation, and replacing a WCS must not
#: delete the date the file was taken.
_WCS_KEYWORD_RE = re.compile(
    r"^(?:WCSNAME|WCSAXES|RADESYS|RADECSYS|EQUINOX|EPOCH|LATPOLE|LONPOLE|LONGPOLE"
    r"|CTYPE\d|CRPIX\d|CRVAL\d|CUNIT\d|CDELT\d|CROTA\d"
    r"|CD\d_\d|PC\d_\d|PC0\d_0\d|PC00\d00\d|PS\d_\d+|PV\d_\d+"
    r"|A_ORDER|B_ORDER|AP_ORDER|BP_ORDER|A_DMAX|B_DMAX"
    r"|A_\d+_\d+|B_\d+_\d+|AP_\d+_\d+|BP_\d+_\d+)[A-Z]?$"
)

#: Keywords DS9's dialog carries which are not part of the WCS proper.
DATE_KEYWORDS: tuple[str, ...] = ("MJD-OBS", "DATE-OBS")

#: Keywords whose value is a string, and is written quoted. Everything else
#: on the dialog is a number.
_STRING_KEYWORD_RE = re.compile(r"^(?:WCSNAME|RADESYS|RADECSYS|CTYPE\d|CUNIT\d|PS\d_\d+|DATE-OBS)[A-Z]?$")


def is_wcs_keyword(name: str, dates: bool = False) -> bool:
    """Whether one keyword belongs to a WCS description.

    Args:
        name: The keyword, in any case.
        dates: Count `MJD-OBS` and `DATE-OBS` as well, as DS9's dialog does.
    """
    key = name.strip().upper()
    if dates and key in DATE_KEYWORDS:
        return True
    return bool(_WCS_KEYWORD_RE.match(key))


def _normalise_key(key: str) -> str:
    """DS9's spelling fixes (`WCSToVar`): old keyword names to new ones."""
    key = key.strip().upper()
    if key == "LONGPOLE":
        return "LONPOLE"
    if key == "RADECSYS":
        return "RADESYS"
    match = re.match(r"^PC0([1-9])_0([1-9])([A-Z]?)$", key) or re.match(
        r"^PC00([1-9])00([1-9])([A-Z]?)$", key
    )
    if match:
        return f"PC{match.group(1)}_{match.group(2)}{match.group(3)}"
    return key


def _strip_value(raw: str) -> str:
    """One card's value, without its comment, quotes or padding.

    A comment starts at a slash, but a date has slashes in it too, so --
    as DS9 does -- a value with more than one slash is cut at the first
    " /" instead.
    """
    if raw.lstrip().startswith("'"):
        # A quoted string ends at its closing quote; a slash inside it is
        # part of the value.
        body = raw.lstrip()[1:]
        end = body.find("'")
        value = body if end < 0 else body[:end]
        return value.strip()
    parts = raw.split("/")
    if len(parts) <= 2:
        value = parts[0]
    else:
        cut = raw.find(" /")
        value = raw[:cut] if cut > 0 else parts[0]
    return value.strip().strip("'").strip()


def parse_wcs_text(text: str) -> dict[str, str]:
    """Read DS9's `.wcs` text into keyword -> value.

    Accepts a keyword per line, or -- as DS9 does -- a FITS header block
    with no newlines at all, cut into 80-character cards. Lines that are not
    a WCS keyword (comments, `END`, anything else) are skipped.

    Returns:
        Upper-case keywords and their values as text, in the order read.
    """
    lines = text.splitlines()
    if len(lines) == 1 and len(text) > 80:
        lines = [text[index : index + 80] for index in range(0, len(text), 80)]

    values: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            continue
        name, _, rest = line.partition("=")
        key = _normalise_key(name)
        if not is_wcs_keyword(key, dates=True):
            continue
        values[key] = _strip_value(rest)
    return values


def _typed(key: str, value: str) -> str | int | float:
    """A dialog's text as the FITS value it stands for."""
    if _STRING_KEYWORD_RE.match(key):
        return value
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def values_to_header(values: Mapping[str, str]) -> fits.Header:
    """Turn keyword -> text into a header, numbers as numbers.

    Empty values are dropped, as DS9's `WCSFromVar` drops them: a blank
    field on the dialog means "not set", not "set to nothing".
    """
    header = fits.Header()
    for key, value in values.items():
        text = str(value).strip()
        if text == "":
            continue
        header[_normalise_key(key)] = _typed(key.upper(), text)
    return header


def header_values(header: Mapping | fits.Header | None, dates: bool = True) -> dict[str, str]:
    """The WCS keywords of a header, as keyword -> text.

    Args:
        header: A FITS header, a plain mapping, or None.
        dates: Include `MJD-OBS` and `DATE-OBS`.
    """
    if header is None:
        return {}
    values: dict[str, str] = {}
    for key in list(header.keys()):
        name = str(key).upper()
        if not is_wcs_keyword(name, dates=dates):
            continue
        value = header[key]
        if isinstance(value, bool):
            text = "T" if value else "F"
        elif isinstance(value, float):
            text = repr(value)
        else:
            text = str(value).strip()
        values[_normalise_key(name)] = text
    return values


def extract_wcs(header: Mapping | fits.Header | None, dates: bool = True) -> fits.Header:
    """A header holding only the WCS keywords of another."""
    return values_to_header(header_values(header, dates=dates))


def format_wcs_text(header: Mapping | fits.Header | None) -> str:
    """The WCS keywords of a header as DS9 saves them: one card a line."""
    cards = extract_wcs(header).cards
    return "".join(f"{str(card).rstrip()}\n" for card in cards)


def _as_header(header: Mapping | fits.Header | None) -> fits.Header:
    """A copy of a header, or of a plain mapping, as an astropy header."""
    if header is None:
        return fits.Header()
    if isinstance(header, fits.Header):
        return header.copy()
    made = fits.Header()
    for key, value in header.items():
        try:
            made[str(key)] = value
        except (ValueError, KeyError):
            continue
    return made


def _remove(header: fits.Header, keys: Iterable[str]) -> None:
    """Delete every card named in `keys`, however many times it appears."""
    for key in list(keys):
        while key in header:
            del header[key]


def replace_wcs(
    header: Mapping | fits.Header | None,
    new: Mapping | fits.Header,
    dates: bool = False,
) -> fits.Header:
    """DS9's `wcs replace`: a copy of `header` with its WCS swapped for `new`.

    Every WCS keyword of the old header goes, primary and alternates alike,
    as DS9's replacement is of the whole WCS and not of one letter; then
    `new`'s are added.

    Args:
        header: The image header.
        new: The replacement WCS keywords.
        dates: Also clear `MJD-OBS` and `DATE-OBS` first. A reset uses this
            so a date the user typed into the dialog goes back too.
    """
    result = _as_header(header)
    _remove(result, [key for key in result if is_wcs_keyword(str(key), dates=dates)])
    return append_wcs(result, new)


def append_wcs(header: Mapping | fits.Header | None, new: Mapping | fits.Header) -> fits.Header:
    """DS9's `wcs append`: a copy of `header` with `new`'s keywords added.

    A keyword already there takes the new value; the rest are left alone.
    """
    result = _as_header(header)
    incoming = new if isinstance(new, fits.Header) else values_to_header(new)
    for card in incoming.cards:
        result[card.keyword] = card.value
    return result
