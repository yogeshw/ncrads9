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
Footprint servers: which observations cover a patch of sky.

DS9's two (`ifp(def)` in `ds9/library/fp.tcl:22`) -- Chandra's at CfA and
the Hubble Legacy Archive's at STScI -- both answer a cone search with a
VOTable whose rows carry a polygon per observation and the instrument that
took it.

A footprint is a catalogue with a shape instead of a position, so it is
loaded as a catalogue -- filterable, sortable, listable like any other --
and its polygons are drawn as regions rather than as symbols. That is what
DS9 does too: its `fpreg.tcl` turns footprints into regions.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlencode

from astropy.table import Table

#: How long to wait for a footprint server, in seconds.
DEFAULT_TIMEOUT = 60.0

#: DS9's default search radius for footprints, in arcminutes (`fp.tcl:16`).
DEFAULT_RADIUS_ARCMIN = 15.0


class FootprintError(RuntimeError):
    """A footprint query that failed, for the reason given."""


@dataclass(frozen=True)
class FootprintServer:
    """One footprint server.

    Attributes:
        name: Its internal name, as DS9 names it.
        label: What the menu shows.
        url: The cone-search endpoint.
        instruments: The instruments it can be filtered to.
    """

    name: str
    label: str
    url: str
    instruments: tuple[str, ...] = ()


#: DS9's footprint servers, from `fp.tcl:22`.
SERVERS: tuple[FootprintServer, ...] = (
    FootprintServer(
        name="fpcxc",
        label="Chandra (NASA/CXC)",
        url="https://cxcfps.cfa.harvard.edu/cgi-bin/cda/footprint/get_vo_table.pl",
        instruments=("ACIS-S", "ACIS-I", "HRC-S", "HRC-I"),
    ),
    FootprintServer(
        name="fphla",
        label="Hubble Legacy Archive (STScI)",
        url="https://hla.stsci.edu/cgi-bin/hlaSIAP.cgi/footprint/get_vo_table.pl",
        instruments=(
            "ACS",
            "ACSGrism",
            "WFPC2",
            "WFPC2-PC",
            "NICMOS",
            "NICGrism",
            "WFC3",
            "COS",
            "STIS",
            "FOS",
            "GHRS",
        ),
    ),
)


def by_name(name: str) -> FootprintServer | None:
    """One footprint server by name."""
    wanted = str(name).strip().lower()
    return next((server for server in SERVERS if server.name == wanted), None)


@dataclass
class FootprintRequest:
    """What footprints to ask for.

    Attributes:
        server: Which server.
        longitude, latitude: Where, in degrees.
        radius_arcmin: How far around it to look.
        instruments: Which instruments to accept. Empty means all of them.
        timeout: How long to wait.
    """

    server: FootprintServer
    longitude: float
    latitude: float
    radius_arcmin: float = DEFAULT_RADIUS_ARCMIN
    instruments: tuple[str, ...] = ()
    timeout: float = DEFAULT_TIMEOUT

    def url(self) -> str:
        """The URL this request would fetch."""
        parameters = [
            ("RA", f"{self.longitude:g}"),
            ("DEC", f"{self.latitude:g}"),
            ("SR", f"{self.radius_arcmin / 60.0:g}"),
        ]
        for instrument in self.instruments:
            parameters.append(("inst", instrument))
        return f"{self.server.url}?{urlencode(parameters)}"


#: A fetcher: called with (url, timeout), returning the VOTable text.
Fetcher = Callable[[str, float], str]


def fetch(url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Retrieve a footprint query. The only network call here.

    Raises:
        FootprintError: If the request fails.
    """
    from urllib.error import URLError
    from urllib.request import urlopen

    if not url.lower().startswith(("http://", "https://")):
        raise FootprintError(f"not an http URL: {url}")
    try:
        with urlopen(url, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except (URLError, OSError, ValueError) as exc:
        raise FootprintError(f"could not reach the footprint server: {exc}") from exc


@dataclass
class FootprintResult:
    """What a footprint query found.

    Attributes:
        table: The rows, or None.
        polygons: One list of (longitude, latitude) vertices per row that
            had a readable polygon.
        message: What to tell the user.
    """

    table: Table | None = None
    polygons: list[list[tuple[float, float]]] = field(default_factory=list)
    message: str = ""

    def __bool__(self) -> bool:
        return bool(self.polygons)


def query(request: FootprintRequest, fetcher: Fetcher | None = None) -> FootprintResult:
    """Ask a footprint server what covers a patch of sky.

    Returns:
        The result. A failure comes back as a message, as elsewhere.
    """
    caller = fetcher or fetch
    try:
        text = caller(request.url(), request.timeout)
    except FootprintError as exc:
        return FootprintResult(message=str(exc))
    except Exception as exc:
        return FootprintResult(message=f"could not reach the footprint server: {exc}")

    try:
        table = _parse(text)
    except Exception as exc:
        return FootprintResult(message=f"could not read the server's reply: {exc}")

    if table is None or not len(table):
        return FootprintResult(message=f"{request.server.label}: nothing covers that position")

    polygons = extract_polygons(table)
    return FootprintResult(
        table=table,
        polygons=polygons,
        message=f"{request.server.label}: {len(table)} observations, {len(polygons)} outlines",
    )


def _parse(text: str) -> Table | None:
    """Read the VOTable a footprint server returns."""
    import io

    from astropy.io.votable import parse as parse_votable

    votable = parse_votable(io.BytesIO(text.encode("utf-8")))
    for table in votable.iter_tables():
        if table.array is not None and len(table.array):
            return table.to_table(use_names_over_ids=True)
    return None


#: The columns a footprint's outline may arrive in. Both servers use one of
#: these; they do not agree on which.
POLYGON_COLUMNS: tuple[str, ...] = ("regionstcs", "stcs", "s_region", "polygon", "footprint")

#: A run of numbers in an STC-S polygon.
_NUMBERS = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def extract_polygons(table: Table) -> list[list[tuple[float, float]]]:
    """The outlines in a footprint table, one list of vertices per row.

    The outline arrives as STC-S -- `Polygon J2000 10.1 41.2 10.2 41.2 ...`
    -- so the shape word and the frame are skipped and the numbers taken in
    pairs. A row whose outline cannot be read is left out rather than making
    the whole result unusable: the table still lists the observation, it
    just is not drawn.
    """
    lookup = {name.lower(): name for name in table.colnames}
    column = next((lookup[key] for key in POLYGON_COLUMNS if key in lookup), None)
    if column is None:
        return []

    found: list[list[tuple[float, float]]] = []
    for row in table:
        vertices = parse_stcs(str(row[column]))
        if len(vertices) >= 3:
            found.append(vertices)
    return found


def parse_stcs(text: str) -> list[tuple[float, float]]:
    """Read the vertices out of an STC-S polygon.

    Returns:
        The (longitude, latitude) pairs, or an empty list if the string is
        not a polygon this understands.
    """
    if "polygon" not in text.lower():
        return []
    body = text.lower().split("polygon", 1)[1]

    # Drop the frame, if it is named: `J2000` and `ICRS` are words, and
    # `J2000` holds digits that a plain number scan reads as a declination
    # of two thousand.
    tokens = [token for token in body.replace(",", " ").split() if token]
    tokens = [token for token in tokens if not token[:1].isalpha()]

    numbers: list[float] = []
    for token in tokens:
        for match in _NUMBERS.findall(token):
            numbers.append(float(match))
    if len(numbers) % 2:
        numbers = numbers[:-1]
    return [(numbers[index], numbers[index + 1]) for index in range(0, len(numbers), 2)]
