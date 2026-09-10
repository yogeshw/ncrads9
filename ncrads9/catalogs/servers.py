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
The catalogs DS9 offers, and the servers they come from.

Transcribed from `icat(def)` in `ds9/library/cat.tcl:48` -- forty-odd
catalogues in six sections, each naming the service that answers for it and,
for the VizieR ones, the catalogue identifier to ask for. The sections are
DS9's own and in its order, because the Analysis -> Catalogs menu is built
straight from this list.

The mirrors are `icat(site)` from the same file. They matter: VizieR is
answered by a dozen sites and a user in India should not be querying
Strasbourg.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Service(Enum):
    """Which service answers for a catalogue."""

    #: VizieR, at CDS. Most of the list.
    CDS = "cds"
    SIMBAD = "simbad"
    NED = "ned"
    SKYBOT = "skybot"
    #: The Chandra Source Catalog's own server at CXC.
    CXC = "cxc"


@dataclass(frozen=True)
class CatalogServer:
    """One entry on DS9's Catalogs menu.

    Attributes:
        label: What the menu shows.
        name: DS9's internal name, e.g. `catgaia`. Kept because it is what
            its XPA `catalog` command takes.
        service: Which service answers.
        identifier: The VizieR catalogue id, where there is one.
        section: Which of DS9's six groups it belongs to.
    """

    label: str
    name: str
    service: Service
    identifier: str = ""
    section: str = ""


#: DS9's VizieR mirrors, from `icat(site)`.
MIRRORS: tuple[tuple[str, str], ...] = (
    ("CDS, Strasbourg, France", "cds"),
    ("CFA, Harvard, USA", "sao"),
    ("ADAC, Tokyo, Japan", "adac"),
    ("IUCAA, Pune, India", "iucaa"),
    ("INASAN, Moscow, Russia", "inasan"),
    ("Bejing, China", "bejing"),
    ("SAAO, South Africa", "saao"),
    ("Cambridge, UK", "cambridge"),
)

#: The default mirror, which is DS9's `pcat(server)`.
DEFAULT_MIRROR = "cds"

#: The base URL of each mirror's VizieR service.
MIRROR_URLS: dict[str, str] = {
    "cds": "https://vizier.cds.unistra.fr",
    "sao": "https://vizier.cfa.harvard.edu",
    "adac": "http://vizier.nao.ac.jp",
    "iucaa": "http://vizier.iucaa.in",
    "inasan": "http://vizier.inasan.ru",
    "bejing": "http://vizier.china-vo.org",
    "saao": "http://viziersaao.chpc.ac.za",
    "cambridge": "http://vizier.ast.cam.ac.uk",
}

#: The catalogues, in DS9's order and grouping (`cat.tcl:48`).
CATALOGS: tuple[CatalogServer, ...] = (
    CatalogServer("NED", "catned", Service.NED, "", "Database"),
    CatalogServer("SIMBAD", "catsimbad", Service.SIMBAD, "", "Database"),
    CatalogServer("DENIS", "catdenis", Service.CDS, "B/denis", "Database"),
    CatalogServer("SkyBot", "catskybot", Service.SKYBOT, "", "Database"),
    CatalogServer("AAVSO", "cataavso", Service.CDS, "B/vsx", "Optical"),
    CatalogServer("AC 2000.2", "catac", Service.CDS, "I/275/ac2002", "Optical"),
    CatalogServer("ASCC-2.5", "catascss", Service.CDS, "I/280A/ascc01", "Optical"),
    CatalogServer("Carlsberg Meridian 14", "catcmc", Service.CDS, "I/304", "Optical"),
    CatalogServer("GAIA DR1", "catgaia1", Service.CDS, "I/337/gaia", "Optical"),
    CatalogServer("GAIA DR2", "catgaia", Service.CDS, "I/345/gaia2", "Optical"),
    CatalogServer("GSC 2.2", "catgsc2", Service.CDS, "I/271/out", "Optical"),
    CatalogServer("GSC 2.3", "catgsc", Service.CDS, "I/305/out", "Optical"),
    CatalogServer("NOMAD", "catnomad", Service.CDS, "I/297/out", "Optical"),
    CatalogServer("PPMX", "catppmx", Service.CDS, "I/312", "Optical"),
    CatalogServer("SAO J2000", "catsao", Service.CDS, "I/131A/sao", "Optical"),
    CatalogServer("SDSS Release 7", "catsdss7", Service.CDS, "II/294", "Optical"),
    CatalogServer("SDSS Release 9", "catsdss9", Service.CDS, "V/139", "Optical"),
    CatalogServer("SDSS Release 12", "catsdss", Service.CDS, "V/147", "Optical"),
    CatalogServer("Tycho-2", "cattycho", Service.CDS, "I/259/tyc2", "Optical"),
    CatalogServer("USNO-A2.0", "catua2", Service.CDS, "I/252/out", "Optical"),
    CatalogServer("USNO-B1.0", "catub1", Service.CDS, "I/284/out", "Optical"),
    CatalogServer("USNO UCAC2", "catucac2", Service.CDS, "I/289/out", "Optical"),
    CatalogServer("USNO UCAC4", "catucac4", Service.CDS, "I/322A", "Optical"),
    CatalogServer("USNO UCAC5", "catucac", Service.CDS, "I/340", "Optical"),
    CatalogServer("USNO URAT1", "caturat1", Service.CDS, "I/329", "Optical"),
    CatalogServer("2MASS Point Sources", "cat2mass", Service.CDS, "II/246/out", "Infrared"),
    CatalogServer("IRAS Point Sources", "catiras", Service.CDS, "II/125/main", "Infrared"),
    CatalogServer("Chandra Source 1.1", "catcsc11", Service.CDS, "IX/45/csc11", "High Energy"),
    CatalogServer("Chandra Source 2.0", "catcsc20", Service.CDS, "IX/57/csc2master", "High Energy"),
    CatalogServer("Chandra Source Current", "catcsc", Service.CXC, "Current Release", "High Energy"),
    CatalogServer("XMM-Newton 4XMM-DR13 Source", "catxmm", Service.CDS, "IX/69", "High Energy"),
    CatalogServer("Second ROSAT PSPC", "catrosat", Service.CDS, "IX/30", "High Energy"),
    CatalogServer("FIRST Survey", "catfirst", Service.CDS, "VIII/71/first", "Radio"),
    CatalogServer("NVSS", "catnvss", Service.CDS, "VIII/65/nvss", "Radio"),
    CatalogServer("Chandra Archive", "catchandralog", Service.CDS, "B/chandra/chandra", "Observation Logs"),
    CatalogServer("CFHT Exposures", "catcfhtlog", Service.CDS, "B/cfht/chfht", "Observation Logs"),
    CatalogServer("ESO Science Archive", "catesolog", Service.CDS, "B/eso/safcat", "Observation Logs"),
    CatalogServer("HST Archive", "cathstlog", Service.CDS, "B/hst/hstlog", "Observation Logs"),
    CatalogServer("XMM Observation", "catxmmlog", Service.CDS, "B/xmm/xmmlog", "Observation Logs"),
)

#: The sections, in DS9's order.
SECTIONS: tuple[str, ...] = (
    "Database",
    "Optical",
    "Infrared",
    "High Energy",
    "Radio",
    "Observation Logs",
)


def by_name(name: str) -> CatalogServer | None:
    """One catalogue by DS9's internal name, e.g. `catgaia`."""
    wanted = str(name).strip().lower()
    for entry in CATALOGS:
        if entry.name == wanted:
            return entry
    return None


def in_section(section: str) -> tuple[CatalogServer, ...]:
    """The catalogues in one of DS9's sections, in order."""
    return tuple(entry for entry in CATALOGS if entry.section == section)


def mirror_url(mirror: str) -> str:
    """The base URL of one VizieR mirror, falling back to CDS."""
    return MIRROR_URLS.get(str(mirror).strip().lower(), MIRROR_URLS[DEFAULT_MIRROR])
