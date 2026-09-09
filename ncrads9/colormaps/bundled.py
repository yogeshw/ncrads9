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
The colormaps DS9 bundles, and the categories its Color menu groups them in.

DS9 ships 168 colour tables in `ds9/cmaps/` -- 46 in its own `.sao` control
point format and 122 as plain `.lut` triple lists -- and its Color menu puts
them on ten cascades: h5utils, four Matplotlib groups, Cubehelix, Gist,
Topographic, Scientific Colour Maps and Solar Colormaps. The membership below
is DS9's own, read out of the `icolorbar(<category>,cmaps)` lists in
`ds9/library/colorbar.tcl`, so the menus match entry for entry.

Three departures from those lists, each because DS9's data and DS9's menus do
not quite agree:

* Six topographic tables (`tpsfhf`, `tpsfhm`, `tpusarf`, `tpusarm`,
  `tpushuf`, `tpushum`) are shipped but appear on no cascade. They are put on
  Topographic, which is plainly where they belong.
* `turbo` and `twilight` appear only under a legacy top-level name in DS9.
  They are put on Matplotlib Sequential and Matplotlib Cyclic respectively,
  by what they are.
* `viridis`, `inferno`, `magma` and `plasma` are shipped as files *and* exist
  as NCRADS9 built-ins under the same names. The files are not bundled: the
  same tables are on Matplotlib Uniform as `mpl_viridis` and friends, which
  is the name DS9's menu uses, and one name resolving to two sources is a bug
  waiting to happen.

Loading is lazy. Reading 164 files at startup costs about a second and almost
none of them will be looked at, so a table is parsed the first time it is
asked for and then cached.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from functools import cache, lru_cache
from pathlib import Path

from .colormap import Colormap
from .lut_parser import parse_lut_file
from .sao_parser import parse_sao_file

#: Where the bundled tables live.
DATA_DIRECTORY = Path(__file__).resolve().parent / "data"

#: Category label -> its colormap names, both in DS9's order.
CATEGORIES: dict[str, tuple[str, ...]] = {
    "h5utils": (
        "h5_autumn",
        "h5_bluered",
        "h5_bone",
        "h5_cool",
        "h5_copper",
        "h5_dkbluered",
        "h5_gray",
        "h5_green",
        "h5_hot",
        "h5_hsv",
        "h5_jet",
        "h5_pink",
        "h5_spring",
        "h5_summer",
        "h5_winter",
        "h5_yarg",
        "h5_yellow",
    ),
    "Matplotlib Uniform": (
        "mpl_viridis",
        "mpl_plasma",
        "mpl_inferno",
        "mpl_magma",
        "mpl_cividis",
    ),
    "Matplotlib Sequential": (
        "mpl_Greys",
        "mpl_Purples",
        "mpl_Blues",
        "mpl_Greens",
        "mpl_Oranges",
        "mpl_Reds",
        "mpl_YlOrBr",
        "mpl_YlOrRd",
        "mpl_OrRd",
        "mpl_PuRd",
        "mpl_RdPu",
        "mpl_BuPu",
        "mpl_GnBu",
        "mpl_PuBu",
        "mpl_YlGnBu",
        "mpl_PuBuGn",
        "mpl_BuGn",
        "mpl_YlGn",
        "turbo",
    ),
    "Matplotlib Diverging": (
        "mpl_PiYG",
        "mpl_PRGn",
        "mpl_BrBG",
        "mpl_PuOr",
        "mpl_RdGy",
        "mpl_RdBu",
        "mpl_RdYlBu",
        "mpl_RdYlGn",
        "mpl_coolwarm",
        "mpl_bwr",
        "mpl_seismic",
    ),
    "Matplotlib Cyclic": (
        "mpl_twilight",
        "mpl_hsv",
        "twilight",
    ),
    "Cubehelix": (
        "ch05m151008",
        "ch05m151010",
        "ch05m151012",
        "ch05m151410",
        "ch05p151010",
        "ch20m151010",
        "cubehelix0",
        "cubehelix1",
    ),
    "Gist": (
        "gist_earth",
        "gist_heat",
        "gist_rainbow",
        "gist_yarg",
        "gist_gray",
        "gist_ncar",
        "gist_stern",
    ),
    "Topographic": (
        "tpglarf",
        "tpglhcf",
        "tpglhwf",
        "tpglpof",
        "tpglarm",
        "tpglhcm",
        "tpglhwm",
        "tpglpom",
        "tpsfhf",
        "tpsfhm",
        "tpusarf",
        "tpusarm",
        "tpushuf",
        "tpushum",
    ),
    "Scientific Colour Maps": (
        "scm_acton",
        "scm_bam",
        "scm_bamO",
        "scm_bamako",
        "scm_batlow",
        "scm_batlowK",
        "scm_batlowW",
        "scm_berlin",
        "scm_bilbao",
        "scm_broc",
        "scm_brocO",
        "scm_buda",
        "scm_bukavu",
        "scm_cork",
        "scm_corkO",
        "scm_davos",
        "scm_devon",
        "scm_fes",
        "scm_glasgow",
        "scm_greyC",
        "scm_hawaii",
        "scm_imola",
        "scm_lajolla",
        "scm_lapaz",
        "scm_lipari",
        "scm_lisbon",
        "scm_managua",
        "scm_navia",
        "scm_nuuk",
        "scm_oleron",
        "scm_oslo",
        "scm_roma",
        "scm_romaO",
        "scm_tofino",
        "scm_tokyo",
        "scm_turku",
        "scm_vanimo",
        "scm_vik",
        "scm_vikO",
    ),
    "Solar Colormaps": (
        "solar_soho_171",
        "solar_soho_195",
        "solar_soho_284",
        "solar_soho_304",
        "solar_soho_lasco2",
        "solar_soho_lasco3",
        "solar_sdo_94",
        "solar_sdo_131",
        "solar_sdo_171",
        "solar_sdo_193",
        "solar_sdo_211",
        "solar_sdo_304",
        "solar_sdo_335",
        "solar_sdo_1600",
        "solar_sdo_1700",
        "solar_sdo_4500",
        "solar_stereo_171",
        "solar_stereo_195",
        "solar_stereo_284",
        "solar_stereo_304",
        "solar_stereo_cor1",
        "solar_stereo_cor2",
        "solar_stereo_hi1",
        "solar_stereo_hi2",
        "solar_trace_171",
        "solar_trace_195",
        "solar_trace_284",
        "solar_trace_1216",
        "solar_trace_1550",
        "solar_trace_1600",
        "solar_trace_1700",
        "solar_iris_1330",
        "solar_iris_1400",
        "solar_iris_1600",
        "solar_iris_2796",
        "solar_iris_2832",
        "solar_iris_5000",
        "solar_sdo_hmi_color",
        "solar_yohkoh_sxt",
        "solar_rhessi",
        "solar_solo_lya1216",
    ),
}

#: The label DS9 gives the cascade holding colormaps the user has loaded.
USER_CATEGORY = "User"

#: Every bundled name, for membership tests. Names are as DS9 spells them;
#: lookups are case-insensitive.
BUNDLED: frozenset[str] = frozenset(name for names in CATEGORIES.values() for name in names)


#: Prefixes DS9 puts on a table's name to say where it came from. Stripped
#: for the menu label, since the cascade already says which family it is.
_LABEL_PREFIXES: tuple[str, ...] = ("h5_", "mpl_", "scm_", "solar_", "gist_")


def colormap_label(name: str) -> str:
    """How a bundled colormap reads on its cascade.

    DS9 shows the bare table name with its family prefix removed -- `Broc`
    rather than `scm_broc` -- because the cascade the entry sits on already
    says which family it belongs to.

    Args:
        name: The colormap's name.

    Returns:
        The label, with the family prefix dropped and underscores turned
        into spaces.
    """
    label = name
    for prefix in _LABEL_PREFIXES:
        if label.startswith(prefix):
            label = label[len(prefix) :]
            break
    return label.replace("_", " ")


def category_of(name: str) -> str | None:
    """Which cascade a colormap is on.

    Args:
        name: The colormap's name.

    Returns:
        The category label, or None if the name is not bundled.
    """
    for label, names in CATEGORIES.items():
        if name in names:
            return label
    return None


@lru_cache(maxsize=1)
def _index() -> dict[str, Path]:
    """Lowercased colormap name -> its file.

    Names are matched without regard to case, because DS9 matches them that
    way and because the menu registers its actions under a lowercased key
    while eighteen of the bundled files are mixed-case (`mpl_Greys`,
    `scm_batlowK`). Without this, every mixed-case cascade entry would be a
    menu item that could not be applied. `.sao` wins over `.lut` when both
    exist, as DS9's own loader has it.
    """
    index: dict[str, Path] = {}
    if not DATA_DIRECTORY.is_dir():
        return index
    for suffix in (".lut", ".sao"):
        for path in DATA_DIRECTORY.glob(f"*{suffix}"):
            index[path.stem.lower()] = path
    return index


def path_of(name: str) -> Path | None:
    """The file a bundled colormap is stored in.

    Args:
        name: The colormap's name, in any case.

    Returns:
        Its path, or None when there is no such file.
    """
    return _index().get(name.strip().lower())


@cache
def load(name: str) -> Colormap | None:
    """Read one bundled colormap, parsing it on first use.

    Args:
        name: The colormap's name.

    Returns:
        The colormap, or None when the name is not bundled or its file
        cannot be parsed. A broken file gives None rather than raising, so a
        damaged installation loses one menu entry rather than the menu.
    """
    path = path_of(name)
    if path is None:
        return None
    parse = parse_sao_file if path.suffix.lower() == ".sao" else parse_lut_file
    try:
        # Named after the file, not after the spelling asked for, so a
        # case-insensitive hit still reports DS9's own name.
        return parse(path, name=path.stem)
    except Exception:
        return None


def available() -> tuple[str, ...]:
    """Every bundled colormap whose file is actually present."""
    return tuple(name for name in BUNDLED if path_of(name) is not None)
