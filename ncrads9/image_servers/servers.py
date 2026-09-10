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
The image servers DS9 fetches cutouts from, and the queries they take.

Eight of them, each with its own CGI and its own idea of how to ask -- which
is why this is a table of URLs and parameter builders rather than one
protocol. The endpoints and the parameter names are DS9's own, taken from
`ds9/library/{sao,eso,stsci,skyview,vla,nvss,vlss,2mass}.tcl`, and they
differ in every way they could: `r`/`d` at one, `ra`/`dec` at another,
`Position` as one comma-separated string at a third; sizes in degrees,
arcminutes or pixels; the survey named in the path at VLA and in a
parameter everywhere else.

The plan called this replacing "the NotImplementedError skeletons in
image_servers/dss.py, eso.py". Those files were never written -- only
`sia_client.py` existed -- so this is the whole thing rather than a
replacement.

Author: Yogesh Wadadekar

"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlencode


class Protocol(Enum):
    """How a server hands over its image.

    Most of DS9's CGIs answer with the FITS file itself. SDSS has no such
    endpoint -- its cutout service returns a JPEG -- so its FITS images come
    through SIAP, which answers with a VOTable of links to fetch one from.
    """

    #: The URL returns the FITS file.
    DIRECT = "direct"
    #: The URL returns a VOTable listing images; fetch one of those.
    SIA = "sia"


class SizeUnit(Enum):
    """What a server wants its cutout size in."""

    DEGREES = "degrees"
    ARCMIN = "arcmin"
    PIXELS = "pixels"


@dataclass(frozen=True)
class Survey:
    """One survey a server offers.

    Attributes:
        label: What the menu shows.
        value: What the server is sent.
    """

    label: str
    value: str


@dataclass
class ImageServer:
    """One image server.

    Attributes:
        name: Its internal name, which XPA uses.
        label: What the menu shows.
        url: The endpoint, or a template with `{survey}` in it for VLA,
            which names the survey in the path rather than in a parameter.
        size_unit: What its size parameters are in.
        protocol: Whether the URL returns FITS or a list of images.
        surveys: What it offers, if it offers a choice.
        build: Called with (longitude, latitude, width, height, survey) and
            returning the query parameters.
    """

    name: str
    label: str
    url: str
    size_unit: SizeUnit
    protocol: Protocol = Protocol.DIRECT
    surveys: tuple[Survey, ...] = ()
    build: Callable[..., list[tuple[str, str]]] = field(default=lambda **kwargs: [])
    #: Whether the server takes an output size in pixels separately from
    #: the sky size, which only SkyView does.
    takes_pixels: bool = False

    def default_survey(self) -> str:
        """The survey a query uses when none is chosen."""
        return self.surveys[0].value if self.surveys else ""

    def query(
        self,
        longitude: float,
        latitude: float,
        width: float,
        height: float,
        survey: str = "",
        pixels: tuple[int, int] | None = None,
    ) -> str:
        """The full URL for one cutout.

        Args:
            longitude: Right ascension in degrees.
            latitude: Declination in degrees.
            width: The cutout width, in this server's `size_unit`.
            height: Its height.
            survey: Which survey, or empty for the default.
            pixels: How big the returned image should be, for the servers
                that take that separately from the sky size. SkyView is
                the only one, and DS9 gives it its own `pixels` rule.

        Returns:
            The URL to fetch.
        """
        chosen = survey or self.default_survey()
        parameters = self.build(
            longitude=longitude,
            latitude=latitude,
            width=width,
            height=height,
            survey=chosen,
            pixels=pixels or (SKYVIEW_PIXELS, SKYVIEW_PIXELS),
        )
        endpoint = self.url.format(survey=chosen)
        separator = "&" if "?" in endpoint else "?"
        return f"{endpoint}{separator}{urlencode(parameters)}"


# -- the query builders, one per server ----------------------------------------
#
# Each is DS9's `formatQuery` call from the corresponding `.tcl`, with the
# parameter names and their order preserved -- some of these CGIs are
# particular about both.


def _sao(longitude, latitude, width, height, survey, **_rest):
    """SAO's DSS at CfA (`sao.tcl:102`). Sizes in arcminutes."""
    return [
        ("r", f"{longitude:g}"),
        ("d", f"{latitude:g}"),
        ("e", "J2000"),
        ("w", f"{width:g}"),
        ("h", f"{height:g}"),
        ("c", "gz"),
    ]


def _eso(longitude, latitude, width, height, survey, **_rest):
    """ESO's DSS (`eso.tcl:105`). Sizes in arcminutes."""
    return [
        ("ra", f"{longitude:g}"),
        ("dec", f"{latitude:g}"),
        ("equinox", "J2000"),
        ("x", f"{width:g}"),
        ("y", f"{height:g}"),
        ("mime-type", "application/x-fits"),
        ("Sky-Survey", survey),
    ]


def _stsci(longitude, latitude, width, height, survey, **_rest):
    """STScI's DSS (`stsci.tcl:120`). Sizes in arcminutes."""
    return [
        ("r", f"{longitude:g}"),
        ("d", f"{latitude:g}"),
        ("e", "J2000"),
        ("w", f"{width:g}"),
        ("h", f"{height:g}"),
        ("f", "fits"),
        ("c", "gz"),
        ("v", survey),
    ]


def _skyview(longitude, latitude, width, height, survey, pixels=None, **_rest):
    """SkyView (`skyview.tcl:574`).

    Position is one comma-separated pair and Size likewise, and Pixels is
    the output image's dimensions rather than the sky size -- which is why
    this server's `size_unit` is degrees and its pixel count is a separate
    argument, as DS9's `skyview pixels <w> <h>` rule is.
    """
    return [
        ("Position", f"{longitude:g},{latitude:g}"),
        ("Survey", survey),
        ("Size", f"{width:g},{height:g}"),
        ("Pixels", "{},{}".format(*(pixels or (SKYVIEW_PIXELS, SKYVIEW_PIXELS)))),
        ("Return", "FITS"),
    ]


def _vla(longitude, latitude, width, height, survey, **_rest):
    """The VLA cutout servers (`vla.tcl:111`).

    RA and Dec go in one `RA` parameter separated by a space, and the
    survey is part of the path, not a parameter.
    """
    return [
        (".submit", "Extract the Cutout"),
        ("RA", f"{longitude:g} {latitude:g}"),
        ("Equinox", "J2000"),
        ("ImageSize", f"{width:g}"),
        ("MaxInt", "10"),
        (".cgifields", "ImageType"),
        ("ImageType", "FITS Image"),
    ]


def _nvss(longitude, latitude, width, height, survey, **_rest):
    """NVSS (`nvss.tcl:95`). Sizes in degrees, cells in arcseconds."""
    return [
        ("submit", "Submit!"),
        ("Equinox", "J2000"),
        ("PolType", "I"),
        ("RA", f"{longitude:g}"),
        ("Dec", f"{latitude:g}"),
        ("Size", f"{width:g} {height:g}"),
        ("Cells", "15.0 15.0"),
        ("MAPROJ", "SIN"),
        ("Type", "image/x-fits"),
        ("rotate", "0.0"),
    ]


def _vlss(longitude, latitude, width, height, survey, **_rest):
    """VLSS (`vlss.tcl:95`), which differs from NVSS in its cell size."""
    return [
        ("submit", "Submit"),
        ("Equinox", "J2000"),
        ("RA", f"{longitude:g}"),
        ("Dec", f"{latitude:g}"),
        ("Size", f"{width:g} {height:g}"),
        ("Cells", "25.0 25.0"),
        ("MAPROJ", "SIN"),
        ("rotate", "0.0"),
        ("Type", "image/x-fits"),
    ]


def _twomass(longitude, latitude, width, height, survey, **_rest):
    """2MASS at IPAC (`2mass.tcl:102`).

    `objstr` takes a position as text, and `size` is in arcseconds -- the
    one server here that does, which is why it converts.
    """
    return [
        ("objstr", f"{longitude:g} {latitude:g}"),
        ("size", f"{max(1.0, width * 60.0):g}"),
        ("band", survey),
    ]


def _sia(longitude, latitude, width, height, survey, **_rest):
    """A Simple Image Access query, which is what SDSS's FITS images take.

    `POS` is a comma-separated pair and `SIZE` a sky size in degrees; the
    reply is a VOTable of images rather than an image.
    """
    parameters = [
        ("POS", f"{longitude:g},{latitude:g}"),
        ("SIZE", f"{width:g},{height:g}"),
        ("FORMAT", "image/fits"),
    ]
    if survey:
        parameters.append(("BAND", survey))
    return parameters


#: How many pixels across SkyView is asked for. Its `Size` is the sky area
#: and `Pixels` the image, so one of them has to be chosen here.
SKYVIEW_PIXELS = 512

#: DS9's STScI DSS surveys (`stsci.tcl:54`).
STSCI_SURVEYS: tuple[Survey, ...] = (
    Survey("POSS2/UKSTU Red", "poss2ukstu_red"),
    Survey("POSS2/UKSTU Infrared", "poss2ukstu_ir"),
    Survey("POSS2/UKSTU Blue", "poss2ukstu_blue"),
    Survey("POSS1 Blue", "poss1_blue"),
    Survey("POSS1 Red", "poss1_red"),
    Survey("Quick-V", "quickv"),
)

#: ESO's (`eso.tcl`).
ESO_SURVEYS: tuple[Survey, ...] = (
    Survey("DSS1", "DSS1"),
    Survey("DSS2 Red", "DSS2-red"),
    Survey("DSS2 Blue", "DSS2-blue"),
    Survey("DSS2 Infrared", "DSS2-infrared"),
)

#: 2MASS's three bands (`2mass.tcl:53`).
TWOMASS_SURVEYS: tuple[Survey, ...] = (
    Survey("J Band", "j"),
    Survey("H Band", "h"),
    Survey("K Band", "k"),
)

#: The VLA cutout servers (`vla.tcl`), whose name goes in the path.
VLA_SURVEYS: tuple[Survey, ...] = (
    Survey("FIRST", "first"),
    Survey("Stripe 82", "stripe82"),
    Survey("GPS", "gps"),
)

#: A handful of SkyView's surveys. It offers over a hundred and sixty; these
#: are the ones DS9 puts at the head of its menu, and the dialog lets any
#: other be typed.
SKYVIEW_SURVEYS: tuple[Survey, ...] = (
    Survey("DSS", "dss"),
    Survey("DSS1 Blue", "dss1b"),
    Survey("DSS1 Red", "dss1r"),
    Survey("DSS2 Blue", "dss2b"),
    Survey("DSS2 Red", "dss2r"),
    Survey("DSS2 Infrared", "dss2ir"),
    Survey("2MASS J", "2massj"),
    Survey("2MASS H", "2massh"),
    Survey("2MASS K", "2massk"),
    Survey("SDSS g", "sdssg"),
    Survey("SDSS r", "sdssr"),
    Survey("SDSS i", "sdssi"),
    Survey("GALEX Near UV", "galexnear"),
    Survey("GALEX Far UV", "galexfar"),
    Survey("WISE 3.4", "wise34"),
    Survey("WISE 22", "wise22"),
    Survey("IRAS 100 micron", "iris100"),
    Survey("NVSS", "nvss"),
    Survey("ROSAT All-Sky", "rassint"),
    Survey("Fermi 5", "fermi5"),
)

#: The servers, in the order DS9's Image Servers menu has them.
SERVERS: tuple[ImageServer, ...] = (
    ImageServer(
        name="dsssao",
        label="DSS (SAO)",
        url="https://lweb.cfa.harvard.edu/archive/dss",
        size_unit=SizeUnit.ARCMIN,
        build=_sao,
    ),
    ImageServer(
        name="dsseso",
        label="DSS (ESO)",
        url="https://archive.eso.org/dss/dss",
        size_unit=SizeUnit.ARCMIN,
        surveys=ESO_SURVEYS,
        build=_eso,
    ),
    ImageServer(
        name="dssstsci",
        label="DSS (STScI)",
        url="https://stdatu.stsci.edu/cgi-bin/dss_search",
        size_unit=SizeUnit.ARCMIN,
        surveys=STSCI_SURVEYS,
        build=_stsci,
    ),
    ImageServer(
        name="twomass",
        label="2MASS (IPAC)",
        url="https://irsa.ipac.caltech.edu/cgi-bin/Oasis/2MASSImg/nph-2massimg",
        size_unit=SizeUnit.ARCMIN,
        surveys=TWOMASS_SURVEYS,
        build=_twomass,
    ),
    ImageServer(
        name="sdss",
        label="SDSS",
        url="https://skyserver.sdss.org/dr18/SkyserverWS/SIAP/getSIAP",
        size_unit=SizeUnit.DEGREES,
        protocol=Protocol.SIA,
        build=_sia,
    ),
    ImageServer(
        name="skyview",
        label="SkyView (HEASARC)",
        url="https://skyview.gsfc.nasa.gov/cgi-bin/images",
        size_unit=SizeUnit.DEGREES,
        surveys=SKYVIEW_SURVEYS,
        build=_skyview,
        takes_pixels=True,
    ),
    ImageServer(
        name="vla",
        label="VLA (NRAO)",
        url="https://third.ucllnl.org/cgi-bin/{survey}cutout",
        size_unit=SizeUnit.ARCMIN,
        surveys=VLA_SURVEYS,
        build=_vla,
    ),
    ImageServer(
        name="nvss",
        label="NVSS (NRAO)",
        url="https://www.cv.nrao.edu/cgi-bin/postage.pl",
        size_unit=SizeUnit.DEGREES,
        build=_nvss,
    ),
    ImageServer(
        name="vlss",
        label="VLSS (NRAO)",
        url="https://www.cv.nrao.edu/cgi-bin/newVLSSpostage.pl",
        size_unit=SizeUnit.DEGREES,
        build=_vlss,
    ),
)


def by_name(name: str) -> ImageServer | None:
    """One server by its internal name."""
    wanted = str(name).strip().lower()
    return next((server for server in SERVERS if server.name == wanted), None)
