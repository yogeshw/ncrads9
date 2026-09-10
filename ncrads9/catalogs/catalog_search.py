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
Searching VizieR's own index of catalogues.

"you can search for other catalogs based on title, keywords, mission,
wavelength, and object type" (`ds9/doc/ref/catalog.html`). The query is
DS9's, from `CATCDSSrch` (`ds9/library/catcdssrchdialog.tcl:310`): the
`viz-bin/votable` endpoint with `-meta`, which asks for catalogue
descriptions rather than rows, and `-source`, `-words`, `-kw.Wavelength`,
`-kw.Mission` and `-kw.Astronomy` as the filters.

The keyword lists are DS9's too. They are worth having in full rather than
letting the user type: VizieR matches them exactly, and `X-ray` typed as
`xray` returns nothing with no hint why.

As everywhere else in this package, the fetch is injectable, so the search
can be tested without asking CDS anything.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlencode

from astropy.table import Table

from .servers import DEFAULT_MIRROR, mirror_url

#: The path DS9 asks for a metadata search on.
SEARCH_PATH = "/viz-bin/votable"

#: How many catalogue descriptions to ask for, as DS9 does.
MAX_RESULTS = 1000

#: How long to wait, in seconds.
DEFAULT_TIMEOUT = 60.0

#: The wavelength ranges DS9 offers (`catcdssrch.tcl:13`).
WAVELENGTHS: tuple[str, ...] = (
    "Radio",
    "IR",
    "optical",
    "UV",
    "EUV",
    "X-ray",
    "Gamma-ray",
)

#: The missions it offers, in its order.
MISSIONS: tuple[str, ...] = (
    "AKARI",
    "ANS",
    "ASCA",
    "BeppoSAX",
    "CGRO",
    "Chandra",
    "COBE",
    "Copernicus",
    "CoRoT",
    "Einstein",
    "ESO",
    "EUVE",
    "EXOSAT",
    "FAUST",
    "Fermi",
    "FUSE",
    "GALEX",
    "GINGA",
    "GRANAT",
    "Herschel",
    "HEAO",
    "Hipparcos",
    "HST",
    "HUT",
    "INTEGRAL",
    "IRAS",
    "ISO",
    "IUE",
    "Kepler",
    "MSX",
    "NuSTAR",
    "OAO-2",
    "ORFEUS",
    "Planck",
    "ROSAT",
    "RXTE",
    "SAS-1",
    "SAS-2",
    "SMM",
    "SOHO",
    "Spitzer",
    "STEREO",
    "Suzaku",
    "Swift",
    "TD1",
    "UIT",
    "ULYSSES",
    "WISE",
    "WMAP",
    "WUPPE",
    "XMM",
)

#: And the astronomy keywords, likewise.
ASTRONOMY: tuple[str, ...] = (
    "Abundances",
    "Ages",
    "AGN",
    "Associations",
    "Atomic_Data",
    "Binaries:cataclysmic",
    "Binaries:eclipsing",
    "Binaries:spectroscopic",
    "BL_Lac_objects",
    "Blue_objects",
    "Clusters_of_galaxies",
    "Constellations",
    "Diameters",
    "Earth",
    "Ephemerides",
    "Equivalent_widths",
    "Extinction",
    "Galaxies",
    "Galaxies:Markarian",
    "Galaxies:spectra",
    "Globular_Clusters",
    "Gravitational_lensing",
    "HII_regions",
    "Interstellar_Medium",
    "Magnetic_fields",
    "Masers",
    "Masses",
    "_META_",
    "Models",
    "Multiple_Stars",
    "Nebulae",
    "Nonstellar",
    "Novae",
    "Obs_Log",
    "Open_Clusters",
    "Orbits",
    "Parallaxes",
    "Photometry",
    "Photometry:intermediate-band",
    "Photometry:narrow-band",
    "Photometry:surface",
    "Photometry:wide-band",
    "Planetary_Nebulae",
    "Planets+Asteroids",
    "Polarization",
    "Positional_Data",
    "Proper_Motions",
    "Pulsars",
    "QSOs",
    "Redshifts",
    "Rotational_Velocities",
    "Seyfert_Galaxies",
    "Spectral_Classification",
    "Spectrophotometry",
    "Spectroscopy",
    "Stars",
    "Stars:early-type",
    "Stars:Emission",
    "Stars:late-type",
    "Stars:peculiar",
    "Stars:variable",
    "Stars:white_dwarf",
    "Stars:WR",
    "Sun",
    "SuperNovae",
    "SuperNovae_Remnants",
    "Velocities",
    "YSOs",
)

#: What DS9 shows in a keyword menu for "do not filter on this".
NO_KEYWORD = "none"


class SearchError(RuntimeError):
    """A catalogue search that failed, for the reason given."""


@dataclass
class SearchRequest:
    """What to search for.

    Attributes:
        source: A catalogue identifier or part of one, DS9's `-source`.
        words: Free text to match against titles and descriptions.
        wavelength, mission, astronomy: The three keyword filters. Empty,
            or "none", means do not filter on it.
        mirror: Which VizieR site to ask.
        limit: How many descriptions to accept.
        timeout: How long to wait.
    """

    source: str = ""
    words: str = ""
    wavelength: str = ""
    mission: str = ""
    astronomy: str = ""
    mirror: str = DEFAULT_MIRROR
    limit: int = MAX_RESULTS
    timeout: float = DEFAULT_TIMEOUT

    @property
    def empty(self) -> bool:
        """Whether the request would ask for everything VizieR has.

        Worth refusing: a search with no terms is a download of twenty
        thousand catalogue descriptions and no way to read them.
        """
        return not any(
            _wanted(value)
            for value in (self.source, self.words, self.wavelength, self.mission, self.astronomy)
        )

    def query(self) -> str:
        """The query string, exactly as DS9 builds it."""
        parameters: list[tuple[str, str]] = [
            ("-out.max", str(self.limit)),
            ("-out.form", "VOTable"),
        ]
        if _wanted(self.source):
            parameters.append(("-source", self.source.strip()))
        if _wanted(self.words):
            parameters.append(("-words", self.words.strip()))
        if _wanted(self.wavelength):
            parameters.append(("-kw.Wavelength", self.wavelength.strip()))
        if _wanted(self.mission):
            parameters.append(("-kw.Mission", self.mission.strip()))
        if _wanted(self.astronomy):
            parameters.append(("-kw.Astronomy", self.astronomy.strip()))
        # `-meta` is a bare flag, not a pair: it asks for catalogue
        # descriptions instead of catalogue rows.
        return "-meta&" + urlencode(parameters)

    def url(self) -> str:
        """The whole URL the search would fetch."""
        return f"{mirror_url(self.mirror)}{SEARCH_PATH}?{self.query()}"


@dataclass
class SearchResult:
    """What the search found.

    Attributes:
        table: The catalogue descriptions, or None.
        message: What to tell the user.
        found: The identifiers found, in order, for a menu.
    """

    table: Table | None = None
    message: str = ""
    found: list[tuple[str, str]] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.found)


def _wanted(value: str) -> bool:
    """Whether a field asks for anything."""
    text = (value or "").strip()
    return bool(text) and text.lower() != NO_KEYWORD


#: A fetcher: called with a URL, returns the VOTable text.
Fetcher = Callable[[str, float], str]


def fetch(url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Retrieve a search URL. The only function here that uses the network.

    Raises:
        SearchError: If the request fails.
    """
    from urllib.error import URLError
    from urllib.request import urlopen

    if not url.lower().startswith(("http://", "https://")):
        raise SearchError(f"not an http URL: {url}")
    try:
        with urlopen(url, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except (URLError, OSError, ValueError) as exc:
        raise SearchError(f"could not reach the catalog server: {exc}") from exc


def search(request: SearchRequest, fetcher: Fetcher | None = None) -> SearchResult:
    """Search VizieR's index of catalogues.

    Args:
        request: What to search for.
        fetcher: How to fetch. The real client by default.

    Returns:
        The result. A failure comes back as a message rather than as an
        exception, as everywhere else in this package.
    """
    if request.empty:
        return SearchResult(message="Enter something to search for")

    caller = fetcher or fetch
    try:
        text = caller(request.url(), request.timeout)
    except SearchError as exc:
        return SearchResult(message=str(exc))
    except Exception as exc:
        return SearchResult(message=f"could not reach the catalog server: {exc}")

    try:
        table = _parse(text)
    except Exception as exc:
        return SearchResult(message=f"could not read the server's reply: {exc}")

    if table is None or not len(table):
        return SearchResult(message="No catalogs found")

    found = _identifiers(table)
    return SearchResult(table=table, message=f"{len(found)} catalogs found", found=found)


def _parse(text: str) -> Table | None:
    """Read the VOTable the search returns."""
    import io

    from astropy.io.votable import parse as parse_votable

    votable = parse_votable(io.BytesIO(text.encode("utf-8")))
    for table in votable.iter_tables():
        if table.array is not None and len(table.array):
            return table.to_table(use_names_over_ids=True)
    return None


def _identifiers(table: Table) -> list[tuple[str, str]]:
    """The (identifier, title) pairs in a search result.

    VizieR's metadata reply names these differently between versions, so
    the first recognisable column of each kind is used rather than a fixed
    name -- a search that returned rows and then showed none of them would
    be the worst outcome here.
    """
    lookup = {name.lower(): name for name in table.colnames}
    identifier = next(
        (lookup[key] for key in ("name", "catid", "catalog", "id", "table") if key in lookup),
        table.colnames[0] if table.colnames else None,
    )
    title = next(
        (lookup[key] for key in ("title", "description", "explanations") if key in lookup),
        identifier,
    )
    if identifier is None:
        return []

    found: list[tuple[str, str]] = []
    for row in table:
        key = str(row[identifier]).strip()
        label = str(row[title]).strip() if title else key
        if key:
            found.append((key, label))
    return found
