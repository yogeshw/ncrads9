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
Matching two catalogues by position.

DS9's Catalog Match (`ds9/library/catmatch.tcl`) takes two loaded
catalogues, a radius, and one of three functions: `1and2` for the rows that
appear in both, `1not2` for the rows of the first with no counterpart, and
`2not1` for the reverse. `1and2` can return the columns of both catalogues
or only the first's, and can be asked for unique pairs -- at most one row of
each catalogue in the result.

"Unique" is the part worth stating. Without it a crowded field gives a row
for every pair within the radius, so one star in the first catalogue can
appear five times against five neighbours in the second. With it each row of
each catalogue appears once, keeping its closest counterpart -- which is
what anyone comparing two catalogues actually means, and is why DS9 offers
it as a checkbox rather than as the default.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from enum import Enum

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.table import Table, hstack

from .catalog_query import positions

#: The radius a match uses when none is given, in arcseconds.
DEFAULT_RADIUS_ARCSEC = 5.0


class MatchError(ValueError):
    """Two catalogues that cannot be matched, for the reason given."""


class MatchFunction(Enum):
    """DS9's three match functions."""

    BOTH = "1and2"
    FIRST_ONLY = "1not2"
    SECOND_ONLY = "2not1"


class MatchReturn(Enum):
    """Which columns a `1and2` match returns."""

    BOTH = "1and2"
    FIRST = "1only"


#: What the two catalogues' columns are prefixed with when both are kept.
#: A prefix rather than a suffix so the pairs read together in a table
#: whose columns are shown in order.
PREFIXES = ("1_", "2_")


def match(
    first: Table,
    second: Table,
    radius: u.Quantity | float = DEFAULT_RADIUS_ARCSEC,
    function: MatchFunction | str = MatchFunction.BOTH,
    columns: MatchReturn | str = MatchReturn.BOTH,
    unique: bool = True,
) -> Table:
    """Match two catalogues by sky position.

    Args:
        first: The first catalogue.
        second: The second.
        radius: How close two rows must be to count as the same object. A
            plain number is taken as arcseconds.
        function: One of DS9's three.
        columns: For a `1and2` match, whether to return both catalogues'
            columns or only the first's.
        unique: Whether each row of each catalogue may appear once only,
            keeping its closest counterpart.

    Returns:
        The matched rows, with a `separation` column in arcseconds for a
        `1and2` match. An empty table when nothing matched -- with the
        columns the result would have had, so a caller can show it.

    Raises:
        MatchError: If either catalogue has no positions to match on.
    """
    chosen = MatchFunction(function) if isinstance(function, str) else function
    wanted = MatchReturn(columns) if isinstance(columns, str) else columns
    separation = radius if isinstance(radius, u.Quantity) else float(radius) * u.arcsec

    left = positions(first)
    right = positions(second)
    if left is None:
        raise MatchError("the first catalog has no sky positions to match on")
    if right is None:
        raise MatchError("the second catalog has no sky positions to match on")

    pairs = _pairs(left, right, separation, unique)

    if chosen is MatchFunction.FIRST_ONLY:
        return _without(first, {index for index, _other, _distance in pairs})
    if chosen is MatchFunction.SECOND_ONLY:
        return _without(second, {other for _index, other, _distance in pairs})

    return _joined(first, second, pairs, wanted)


def _pairs(
    left: SkyCoord,
    right: SkyCoord,
    radius: u.Quantity,
    unique: bool,
) -> list[tuple[int, int, float]]:
    """Every pair within the radius, closest first, optionally made unique.

    Through the module-level `search_around_sky`, not the method: the
    method returns *the argument's* indices first and `self`'s second,
    which is the reverse of what it reads like, and two catalogues of the
    same length hide the mistake completely.
    """
    from astropy.coordinates import search_around_sky

    left_index, right_index, distance, _three = search_around_sky(left, right, radius)
    found = [
        (int(a), int(b), float(d.to_value(u.arcsec)))
        for a, b, d in zip(left_index, right_index, distance, strict=True)
    ]
    # Closest first, so "keep the first pair for each row" keeps the best.
    found.sort(key=lambda pair: pair[2])

    if not unique:
        return sorted(found, key=lambda pair: (pair[0], pair[1]))

    taken_left: set[int] = set()
    taken_right: set[int] = set()
    kept: list[tuple[int, int, float]] = []
    for index, other, gap in found:
        if index in taken_left or other in taken_right:
            continue
        taken_left.add(index)
        taken_right.add(other)
        kept.append((index, other, gap))
    return sorted(kept, key=lambda pair: pair[0])


def _without(table: Table, matched: set[int]) -> Table:
    """The rows of a table that are not in `matched`."""
    keep = np.array([index not in matched for index in range(len(table))], dtype=bool)
    return table[keep]


def _joined(
    first: Table,
    second: Table,
    pairs: list[tuple[int, int, float]],
    wanted: MatchReturn,
) -> Table:
    """The matched rows, side by side or first-only."""
    if not pairs:
        # An empty result still needs its columns, or the caller has
        # nothing to show and no way to say what was asked.
        empty = first[:0] if wanted is MatchReturn.FIRST else _template(first, second)
        empty["separation"] = np.array([], dtype=float)
        return empty

    left_rows = [index for index, _other, _gap in pairs]
    right_rows = [other for _index, other, _gap in pairs]
    gaps = [gap for _index, _other, gap in pairs]

    if wanted is MatchReturn.FIRST:
        result = Table(first[left_rows])
        result["separation"] = gaps
        return result

    left = _prefixed(first[left_rows], PREFIXES[0])
    right = _prefixed(second[right_rows], PREFIXES[1])
    result = hstack([left, right], join_type="exact")
    result["separation"] = gaps
    return result


def _template(first: Table, second: Table) -> Table:
    """The columns a both-catalogues result would have, with no rows."""
    return hstack(
        [_prefixed(first[:0], PREFIXES[0]), _prefixed(second[:0], PREFIXES[1])],
        join_type="exact",
    )


def _prefixed(table: Table, prefix: str) -> Table:
    """A copy of a table with every column name prefixed.

    Both catalogues have an `RA` and a `Jmag`; joining them without this
    silently keeps one of each.
    """
    renamed = Table(table)
    for name in list(renamed.colnames):
        renamed.rename_column(name, f"{prefix}{name}")
    return renamed
