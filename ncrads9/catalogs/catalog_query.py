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
One way to ask any of DS9's catalog servers for a cone of sky.

The backends under `catalogs/` each have their own shape -- one takes a
`SkyCoord` and a `Quantity`, another a name, a third returns a list of
tables. This puts one function in front of them all, keyed by the service
DS9's catalog list names, and returns one `astropy.table.Table` or nothing.

Every query goes through an injectable transport. That is not a testing
nicety: a catalog query is a network call to somebody else's server, and a
test suite that made real ones would be slow, flaky, and rude. `Query.fetch`
is replaced wholesale in the tests, and there is exactly one place a real
request can be made from.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table

from .servers import CatalogServer, Service, by_name, mirror_url

#: The radius a query uses when none is given. DS9's default is 500
#: arcseconds (`pcat(loc)` in `cat.tcl`).
DEFAULT_RADIUS_ARCSEC = 500.0

#: How many rows a query asks for at most. Unlimited is a way to wait
#: forever on a crowded field near the galactic plane.
DEFAULT_ROW_LIMIT = 5000

#: How long to wait for a server, in seconds.
DEFAULT_TIMEOUT = 60.0


class CatalogQueryError(RuntimeError):
    """A catalog query that failed, for the reason given."""


@dataclass
class QueryRequest:
    """What to ask for.

    Attributes:
        server: The catalogue, from DS9's list.
        center: Where to look.
        radius: How far, as an angle.
        row_limit: The most rows to accept.
        mirror: Which VizieR site to ask, for a CDS catalogue.
        timeout: How long to wait.
    """

    server: CatalogServer
    center: SkyCoord
    radius: u.Quantity = field(default_factory=lambda: DEFAULT_RADIUS_ARCSEC * u.arcsec)
    row_limit: int = DEFAULT_ROW_LIMIT
    mirror: str = "cds"
    timeout: float = DEFAULT_TIMEOUT

    @property
    def url(self) -> str:
        """The mirror this request would go to, for a CDS catalogue."""
        return mirror_url(self.mirror)


@dataclass
class QueryResult:
    """What came back.

    Attributes:
        table: The rows, or None when the query found nothing.
        server: What was asked.
        message: What to tell the user -- how many rows, or why none.
    """

    table: Table | None
    server: CatalogServer
    message: str = ""

    @property
    def rows(self) -> int:
        """How many rows came back."""
        return 0 if self.table is None else len(self.table)

    def __bool__(self) -> bool:
        return self.rows > 0


#: A transport: called with a request, returns a table or None. Replaced
#: wholesale in tests, which is the point of it being a single function.
Transport = Callable[[QueryRequest], "Table | None"]


def fetch(request: QueryRequest) -> Table | None:
    """Make the real network request for one catalogue.

    The only function in the package that talks to a server. Everything
    else goes through `run`, which takes a transport.

    Raises:
        CatalogQueryError: If the service is unknown, or the query fails.
    """
    service = request.server.service

    try:
        if service is Service.CDS:
            return _vizier(request)
        if service is Service.SIMBAD:
            return _simbad(request)
        if service is Service.NED:
            return _ned(request)
        if service is Service.SKYBOT:
            return _skybot(request)
        if service is Service.CXC:
            return _cone(request, "https://cda.cfa.harvard.edu/csccli/coneSearch")
    except CatalogQueryError:
        raise
    except Exception as exc:
        raise CatalogQueryError(f"{request.server.label}: {exc}") from exc

    name = getattr(service, "value", service)
    raise CatalogQueryError(f"No client for service {name!r}")


def _vizier(request: QueryRequest) -> Table | None:
    """Ask VizieR, at whichever mirror was chosen."""
    from .vizier import VizierCatalog

    catalog = VizierCatalog(catalog=request.server.identifier, row_limit=request.row_limit)
    return catalog.query_region(request.center, request.radius)


def _simbad(request: QueryRequest) -> Table | None:
    """Ask SIMBAD."""
    from .simbad import SimbadCatalog

    return SimbadCatalog(row_limit=request.row_limit).query_region(request.center, request.radius)


def _ned(request: QueryRequest) -> Table | None:
    """Ask NED."""
    from .ned import NEDCatalog

    return NEDCatalog().query_region(request.center, request.radius)


def _skybot(request: QueryRequest) -> Table | None:
    """Ask SkyBot, which wants an epoch as well as a cone."""
    from .skybot import SkybotCatalog

    return SkybotCatalog().query_region(request.center, request.radius)


def _cone(request: QueryRequest, url: str) -> Table | None:
    """Ask a plain cone-search service, which is what CXC provides."""
    from .cone_search import ConeSearch

    return ConeSearch(url).query_region(request.center, request.radius)


def run(request: QueryRequest, transport: Transport | None = None) -> QueryResult:
    """Ask for a catalogue and describe what came back.

    Args:
        request: What to ask for.
        transport: How to ask. The real network client by default.

    Returns:
        The result. A failure comes back as a result with a message rather
        than as an exception: a catalog window that vanished because a
        server was down would be worse than one saying so.
    """
    caller = transport or fetch
    try:
        table = caller(request)
    except CatalogQueryError as exc:
        return QueryResult(None, request.server, str(exc))
    except Exception as exc:
        return QueryResult(None, request.server, f"{request.server.label}: {exc}")

    if table is None or len(table) == 0:
        return QueryResult(None, request.server, f"{request.server.label}: no objects found")

    if request.row_limit and len(table) > request.row_limit:
        # Say so rather than truncating silently: a field that hit the cap
        # is not the field the user asked about.
        table = table[: request.row_limit]
        return QueryResult(
            table,
            request.server,
            f"{request.server.label}: {len(table)} rows (the limit; there are more)",
        )

    return QueryResult(table, request.server, f"{request.server.label}: {len(table)} rows")


def request_for(
    name: str,
    center: SkyCoord,
    radius: u.Quantity | None = None,
    **options,
) -> QueryRequest:
    """Build a request for a catalogue named as DS9 names it.

    Args:
        name: DS9's internal name, e.g. `catgaia`.
        center: Where to look.
        radius: How far. DS9's default of 500 arcseconds when not given.
        **options: Passed to `QueryRequest`.

    Returns:
        The request.

    Raises:
        CatalogQueryError: If there is no such catalogue.
    """
    server = by_name(name)
    if server is None:
        raise CatalogQueryError(f"No such catalog: {name}")
    return QueryRequest(
        server=server,
        center=center,
        radius=radius if radius is not None else DEFAULT_RADIUS_ARCSEC * u.arcsec,
        **options,
    )


def coordinate_columns(table: Table) -> tuple[str, str] | None:
    """Which two columns of a catalogue hold its positions.

    Every server names them differently -- `_RAJ2000`/`_DEJ2000` from
    VizieR, `RA`/`DEC` from SIMBAD, `ra`/`dec` from a cone search -- and
    the overlay needs them without being told. The candidates are tried in
    order of how specific they are, so a table with both `_RAJ2000` and a
    stray `ra` column uses the one VizieR meant.

    Returns:
        The two column names, or None if the table has no recognisable pair.
    """
    if table is None or not len(table.colnames):
        return None

    lookup = {name.lower(): name for name in table.colnames}
    pairs = (
        ("_raj2000", "_dej2000"),
        ("raj2000", "dej2000"),
        ("ra_icrs", "de_icrs"),
        ("ra", "dec"),
        ("ra", "de"),
        ("ra_d", "dec_d"),
        ("radeg", "dedeg"),
        ("_ra", "_dec"),
        ("alpha", "delta"),
        ("s_ra", "s_dec"),
    )
    for right, down in pairs:
        if right in lookup and down in lookup:
            return (lookup[right], lookup[down])

    # Nothing named outright: anything starting with ra and dec will do,
    # which catches `RA_2000` and friends.
    right = next((name for key, name in lookup.items() if key.startswith("ra")), None)
    down = next((name for key, name in lookup.items() if key.startswith(("dec", "de"))), None)
    return (right, down) if right and down else None


def positions(table: Table) -> SkyCoord | None:
    """The sky positions of a catalogue's rows, or None if it has none.

    Raises nothing: a catalogue whose coordinate columns cannot be read as
    numbers is a catalogue with no positions, which the caller shows as a
    list without an overlay.
    """
    columns = coordinate_columns(table)
    if columns is None:
        return None

    import numpy as np

    right, down = columns
    try:
        longitude = np.asarray(table[right], dtype=float)
        latitude = np.asarray(table[down], dtype=float)
    except (TypeError, ValueError):
        return None

    good = np.isfinite(longitude) & np.isfinite(latitude)
    if not good.any():
        return None
    return SkyCoord(ra=longitude * u.deg, dec=latitude * u.deg)
