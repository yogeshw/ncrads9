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
DS9's name servers: an object name to a sky position.

`NSVRServerMenuItems` in `ds9/library/nsvr.tcl` offers six -- NED, SIMBAD
and VizieR, each at SAO or at CDS -- and every one is a Sesame service.
Sesame is asked for the one database, at the one site, through astropy.

Like the catalogue queries, the network call is a single function and every
caller can hand in its own, so nothing here has to be tested against a live
server.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Callable

from astropy.coordinates import SkyCoord

#: DS9's name servers, label and value, in its menu's order.
SERVERS: tuple[tuple[str, str], ...] = (
    ("NED@SAO", "ned-sao"),
    ("NED@CDS", "ned-cds"),
    ("SIMBAD@SAO", "simbad-sao"),
    ("SIMBAD@CDS", "simbad-cds"),
    ("VIZIER@SAO", "vizier-sao"),
    ("VIZIER@CDS", "vizier-cds"),
)

#: DS9's default, `pnres(server)`.
DEFAULT_SERVER = "simbad-cds"

#: Each site's Sesame service.
SESAME_URLS = {
    "sao": "http://vizier.cfa.harvard.edu/viz-bin/nph-sesame/",
    "cds": "https://cds.unistra.fr/cgi-bin/nph-sesame/",
}

#: A resolver: called with (name, server), returns the position. Replaced
#: in tests.
Resolver = Callable[[str, str], SkyCoord]


class NameResolveError(RuntimeError):
    """A name that could not be resolved, for the reason given."""


def label_for(server: str) -> str:
    """The menu label for a server value."""
    return next((label for label, value in SERVERS if value == server), server)


def fetch(name: str, server: str = DEFAULT_SERVER) -> SkyCoord:
    """Ask Sesame. The only function here that talks to a server."""
    from astropy.coordinates import name_resolve

    database, _sep, site = str(server).partition("-")
    database = database if database in ("ned", "simbad", "vizier") else "simbad"
    url = SESAME_URLS.get(site, SESAME_URLS["cds"])
    with name_resolve.sesame_database.set(database), name_resolve.sesame_url.set([url]):
        return SkyCoord.from_name(name)


def resolve(name: str, server: str = DEFAULT_SERVER, resolver: Resolver | None = None) -> SkyCoord:
    """Resolve an object name.

    Raises:
        NameResolveError: If there is no name, or the server cannot find it.
    """
    query = str(name).strip()
    if not query:
        raise NameResolveError("an object name is needed")
    try:
        return (resolver or fetch)(query, server)
    except NameResolveError:
        raise
    except Exception as exc:
        raise NameResolveError(f"{label_for(server)} could not resolve {query}: {exc}") from exc
