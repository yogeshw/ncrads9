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
Every preference, as a table: what it is called, what it holds, where it
belongs.

DS9's Preferences window is a list of 29 topics down the left and a page
of controls for each (`prefsdialog.tcl`). Writing 29 pages of widgets by
hand is how a preferences dialog comes to disagree with the preferences it
edits; so here each preference is one row -- key, topic, label, kind,
default -- and the dialog is a renderer over the table. Adding a
preference is adding a row.

The topics are DS9's own, in DS9's order, so someone who knows where a
setting lives in DS9 finds it in the same place here.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: DS9's preference topics, in the order its list shows them
#: (`prefsdialog.tcl:57`).
TOPICS: tuple[str, ...] = (
    "General",
    "Precision",
    "Startup",
    "Menus and Buttons",
    "Panner",
    "Magnifier",
    "3D",
    "Bin",
    "Zoom",
    "Scale",
    "Color",
    "Region",
    "Annulus",
    "Panda",
    "Illustrate",
    "Analysis",
    "Pixel Table",
    "Graph",
    "Contour",
    "Smooth",
    "Catalog",
    "NRES",
    "Plot",
    "VO",
    "Print",
    "Page Setup",
    "Coordinates",
    "Examine",
    "HTTP",
    "Bindings",
)

#: The kinds of control a preference can be.
KINDS: tuple[str, ...] = ("bool", "int", "float", "text", "choice", "color")


@dataclass(frozen=True)
class Preference:
    """One preference.

    Attributes:
        key: What it is called in the preferences file.
        topic: Which page of the dialog it appears on.
        label: What the page calls it.
        kind: One of `KINDS`.
        default: What it is when nothing has been set.
        choices: For `choice`, what it can be.
        minimum, maximum: For `int` and `float`.
        step: For `float`, how much an arrow changes it.
        suffix: What follows the number -- "minutes", "pixels".
        note: One line under the control, where a setting needs one.
    """

    key: str
    topic: str
    label: str
    kind: str
    default: Any
    choices: tuple[str, ...] = ()
    minimum: float = 0.0
    maximum: float = 10_000.0
    step: float = 1.0
    suffix: str = ""
    note: str = ""
    #: Filled in by `by_topic`, so the dialog need not sort.
    order: int = field(default=0, compare=False)


def _preference(*args, **kwargs) -> Preference:
    """One row, for brevity in the table below."""
    return Preference(*args, **kwargs)


#: Every preference. The comment on each group says which of DS9's pages
#: it is, and where a setting is ours rather than DS9's it says so.
PREFERENCES: tuple[Preference, ...] = (
    # -- General (`PrefsDialogGeneral`) -------------------------------------
    _preference("autoload_fits_regions", "General", "Autoload FITS regions", "bool", True),
    _preference("confirm_dialogs", "General", "Enable confirmation dialogs", "bool", True),
    _preference(
        "prompt_for_hdu",
        "General",
        "Ask which extension to load",
        "bool",
        True,
        note="DS9 never asks; it applies its own algorithm and takes the first.",
    ),
    _preference("autosave", "General", "Auto recovery", "bool", True),
    _preference(
        "autosave_interval",
        "General",
        "Auto recovery interval",
        "int",
        5,
        minimum=1,
        maximum=600,
        suffix="minutes",
    ),
    _preference(
        "language",
        "General",
        "Language",
        "choice",
        "en",
        choices=("en", "cs", "da", "de", "es", "fr", "ja", "pt", "zh"),
        note="Takes effect the next time the application starts.",
    ),
    _preference(
        "theme",
        "General",
        "Theme",
        "choice",
        "System",
        choices=("System", "Light", "Dark"),
    ),
    _preference("background_color", "General", "Background color", "color", "#000000"),
    _preference(
        "nan_color",
        "General",
        "Blank/Inf/NaN color",
        "color",
        "#ffffff",
        note="What a pixel with no value is painted, cropped-out pixels included.",
    ),
    _preference("restore_session", "General", "Restore the last session", "bool", False),
    _preference("check_updates", "General", "Check for updates", "bool", True),
    _preference("recent_files_count", "General", "Recent files", "int", 10, minimum=1, maximum=50),
    _preference("data_directory", "General", "Data directory", "text", ""),
    _preference("export_directory", "General", "Export directory", "text", ""),
    # -- Precision (`PrefsDialogPrecision`) ---------------------------------
    _preference("precision_linear", "Precision", "Linear", "int", 8, minimum=1, maximum=17),
    _preference("precision_degrees", "Precision", "Degrees", "int", 8, minimum=1, maximum=17),
    _preference("precision_hms", "Precision", "HMS", "int", 3, minimum=1, maximum=17),
    _preference("precision_dms", "Precision", "DMS", "int", 2, minimum=1, maximum=17),
    _preference("precision_arcmin", "Precision", "ArcMin", "int", 3, minimum=1, maximum=17),
    _preference("precision_arcsec", "Precision", "ArcSec", "int", 3, minimum=1, maximum=17),
    # -- Startup (`PrefsDialogStartup`) -------------------------------------
    _preference(
        "startup_layout",
        "Startup",
        "Layout",
        "choice",
        "horizontal",
        choices=("horizontal", "vertical", "basic", "advanced"),
    ),
    _preference("startup_info", "Startup", "Show the information panel", "bool", True),
    _preference("startup_panner", "Startup", "Show the panner", "bool", True),
    _preference("startup_magnifier", "Startup", "Show the magnifier", "bool", True),
    _preference("startup_buttons", "Startup", "Show the button bar", "bool", True),
    _preference("startup_colorbar", "Startup", "Show the colorbar", "bool", True),
    # -- Menus and Buttons (`PrefsDialogMenu`) ------------------------------
    _preference("buttons_visible", "Menus and Buttons", "Show the button bar", "bool", True),
    _preference("icons_visible", "Menus and Buttons", "Show the icon bar", "bool", False),
    # -- Panner and Magnifier -----------------------------------------------
    _preference("panner_compass", "Panner", "Show the compass", "bool", True),
    _preference("panner_wcs_compass", "Panner", "Show the WCS compass", "bool", True),
    _preference("magnifier_zoom", "Magnifier", "Zoom", "int", 4, minimum=1, maximum=32),
    _preference("magnifier_cursor", "Magnifier", "Show the cursor", "bool", True),
    # -- 3D (`PrefsDialog3d`) ------------------------------------------------
    _preference("three_d_method", "3D", "Method", "choice", "mip", choices=("mip", "aip")),
    _preference(
        "three_d_background", "3D", "Background", "choice", "none", choices=("none", "azimuth", "elevation")
    ),
    _preference("three_d_border", "3D", "Show the border", "bool", True),
    _preference("three_d_highlite", "3D", "Highlight the current slice", "bool", True),
    _preference("three_d_compass", "3D", "Show the compass", "bool", False),
    # -- Bin, Zoom, Scale, Color --------------------------------------------
    _preference("bin_buffer_size", "Bin", "Buffer size", "int", 1024, minimum=128, maximum=16384),
    _preference("bin_function", "Bin", "Function", "choice", "average", choices=("average", "sum")),
    _preference(
        "zoom_default", "Zoom", "Default zoom", "choice", "fit", choices=("fit", "1", "2", "4", "user")
    ),
    _preference("zoom_preserve_pan", "Zoom", "Preserve the pan during a load", "bool", False),
    _preference(
        "default_scale",
        "Scale",
        "Default scale",
        "choice",
        "Linear",
        choices=("Linear", "Log", "Sqrt", "Squared", "Asinh", "Sinh", "Histogram"),
    ),
    _preference(
        "default_clip",
        "Scale",
        "Default limits",
        "choice",
        "MinMax",
        choices=("MinMax", "ZScale", "ZMax", "Percent", "User"),
    ),
    _preference("scale_use_datasec", "Scale", "Use DATASEC", "bool", True),
    _preference(
        "default_colormap",
        "Color",
        "Default colormap",
        "choice",
        "grey",
        choices=(
            "grey",
            "red",
            "green",
            "blue",
            "a",
            "b",
            "bb",
            "he",
            "i8",
            "aips0",
            "sls",
            "hsv",
            "heat",
            "cool",
            "rainbow",
            "standard",
            "staircase",
            "color",
        ),
    ),
    _preference("invert_colormap", "Color", "Invert the colormap", "bool", False),
    _preference("colorbar_numerics", "Color", "Show the colorbar numbers", "bool", True),
    # -- Region, Annulus, Panda ----------------------------------------------
    _preference(
        "region_shape",
        "Region",
        "Default shape",
        "choice",
        "circle",
        choices=(
            "circle",
            "ellipse",
            "box",
            "polygon",
            "point",
            "line",
            "vector",
            "text",
            "ruler",
            "compass",
            "projection",
            "annulus",
            "panda",
            "epanda",
            "bpanda",
            "composite",
            "segment",
        ),
    ),
    _preference("region_color", "Region", "Default color", "color", "#00ff00"),
    _preference("region_width", "Region", "Default width", "int", 1, minimum=1, maximum=8),
    _preference(
        "region_format",
        "Region",
        "Default format",
        "choice",
        "ds9",
        choices=("ds9", "ciao", "saotng", "saoimage", "pros", "xy"),
    ),
    _preference(
        "region_system", "Region", "Default system", "choice", "image", choices=("image", "physical", "wcs")
    ),
    _preference("region_auto_centroid", "Region", "Auto centroid", "bool", False),
    _preference("annulus_inner", "Annulus", "Inner radius", "float", 15.0, maximum=100000.0),
    _preference("annulus_outer", "Annulus", "Outer radius", "float", 30.0, maximum=100000.0),
    _preference("annulus_count", "Annulus", "Annuli", "int", 1, minimum=1, maximum=512),
    _preference("panda_angles", "Panda", "Angles", "int", 4, minimum=1, maximum=512),
    _preference("panda_annuli", "Panda", "Annuli", "int", 1, minimum=1, maximum=512),
    # -- Illustrate ----------------------------------------------------------
    _preference("illustrate_color", "Illustrate", "Default color", "color", "#00ffff"),
    _preference("illustrate_width", "Illustrate", "Default width", "int", 1, minimum=1, maximum=8),
    _preference(
        "illustrate_shape",
        "Illustrate",
        "Default shape",
        "choice",
        "circle",
        choices=("circle", "ellipse", "box", "polygon", "line", "text", "image"),
    ),
    # -- Analysis, Pixel Table, Graph ----------------------------------------
    _preference("analysis_log", "Analysis", "Log commands", "bool", False),
    _preference("pixel_table_size", "Pixel Table", "Size", "choice", "5", choices=("3", "5", "7", "9")),
    _preference("graph_method", "Graph", "Method", "choice", "average", choices=("average", "sum")),
    _preference("graph_thickness", "Graph", "Thickness", "int", 1, minimum=1, maximum=64),
    _preference("graph_log", "Graph", "Logarithmic", "bool", False),
    # -- Contour, Smooth -----------------------------------------------------
    _preference("contour_method", "Contour", "Method", "choice", "block", choices=("block", "smooth")),
    _preference("contour_levels", "Contour", "Levels", "int", 5, minimum=1, maximum=512),
    _preference("contour_smoothness", "Contour", "Smoothness", "int", 4, minimum=1, maximum=32),
    _preference("contour_color", "Contour", "Color", "color", "#00ff00"),
    _preference(
        "smooth_function",
        "Smooth",
        "Function",
        "choice",
        "gaussian",
        choices=("boxcar", "tophat", "gaussian", "elliptic"),
    ),
    _preference("smooth_radius", "Smooth", "Radius", "int", 3, minimum=1, maximum=64),
    # -- Catalog, NRES, Plot, VO ---------------------------------------------
    _preference(
        "catalog_server",
        "Catalog",
        "Server",
        "choice",
        "cds",
        choices=("cds", "sao", "eso", "cadc", "adac", "iucaa"),
    ),
    _preference("catalog_max_rows", "Catalog", "Maximum rows", "int", 5000, minimum=1, maximum=1_000_000),
    _preference(
        "catalog_symbol_shape",
        "Catalog",
        "Symbol",
        "choice",
        "circle",
        choices=("circle", "box", "diamond", "cross", "x", "arrow", "boxcircle"),
    ),
    _preference("catalog_symbol_color", "Catalog", "Symbol color", "color", "#00ff00"),
    _preference("nres_server", "NRES", "Server", "choice", "sao", choices=("sao", "cds")),
    _preference("plot_style", "Plot", "Style", "choice", "line", choices=("line", "bar", "scatter")),
    _preference("plot_grid", "Plot", "Show the grid", "bool", True),
    _preference("plot_legend", "Plot", "Show the legend", "bool", True),
    _preference("vo_method", "VO", "Method", "choice", "xpa", choices=("xpa", "samp")),
    _preference("vo_delay", "VO", "Delay", "int", 15, minimum=1, maximum=600, suffix="seconds"),
    # -- Print and Page Setup ------------------------------------------------
    _preference(
        "print_destination", "Print", "Destination", "choice", "printer", choices=("printer", "file")
    ),
    _preference("print_command", "Print", "Command", "text", "lp"),
    _preference("print_level", "Print", "PostScript level", "choice", "2", choices=("1", "2", "3")),
    _preference("print_color", "Print", "Color", "choice", "rgb", choices=("rgb", "cmyk", "gray")),
    _preference(
        "print_resolution",
        "Print",
        "Resolution",
        "choice",
        "150",
        choices=("53", "72", "75", "86", "96", "150", "300", "600"),
    ),
    _preference(
        "page_orientation",
        "Page Setup",
        "Orientation",
        "choice",
        "portrait",
        choices=("portrait", "landscape"),
    ),
    _preference(
        "page_size",
        "Page Setup",
        "Size",
        "choice",
        "letter",
        choices=("letter", "legal", "tabloid", "poster", "a4", "other", "othermm"),
    ),
    _preference("page_scale", "Page Setup", "Scale", "float", 100.0, minimum=1.0, maximum=1000.0, suffix="%"),
    # -- Coordinates and Examine ---------------------------------------------
    _preference(
        "coord_system",
        "Coordinates",
        "System",
        "choice",
        "wcs",
        choices=("image", "physical", "amplifier", "detector", "wcs"),
    ),
    _preference(
        "coord_sky",
        "Coordinates",
        "Sky frame",
        "choice",
        "fk5",
        choices=("fk4", "fk5", "icrs", "galactic", "ecliptic"),
    ),
    _preference(
        "coord_format", "Coordinates", "Format", "choice", "sexagesimal", choices=("degrees", "sexagesimal")
    ),
    _preference("examine_mode", "Examine", "Mode", "choice", "new", choices=("new", "current")),
    _preference("examine_zoom", "Examine", "Zoom", "float", 4.0, minimum=0.1, maximum=64.0),
    # -- HTTP ----------------------------------------------------------------
    _preference("http_proxy", "HTTP", "Proxy host", "text", ""),
    _preference("http_proxy_port", "HTTP", "Proxy port", "int", 0, minimum=0, maximum=65535),
    _preference("http_timeout", "HTTP", "Timeout", "int", 30, minimum=1, maximum=600, suffix="seconds"),
    _preference("http_user_agent", "HTTP", "User agent", "text", ""),
    # -- Performance: ours, not DS9's, because ours has a GPU backend -------
    _preference(
        "use_gpu",
        "General",
        "Use the GPU renderer",
        "bool",
        True,
        note="Ours rather than DS9's: DS9 has no GPU backend.",
    ),
    _preference("tile_size", "General", "GPU tile size", "int", 512, minimum=64, maximum=4096),
    _preference(
        "cache_size_mb", "General", "Cache size", "int", 1000, minimum=100, maximum=100_000, suffix="MB"
    ),
    _preference("worker_threads", "General", "Worker threads", "int", 4, minimum=1, maximum=64),
    _preference("anti_aliasing", "General", "Anti-aliasing", "bool", True),
)


def defaults() -> dict[str, Any]:
    """Every preference's key and default."""
    return {preference.key: preference.default for preference in PREFERENCES}


def by_key() -> dict[str, Preference]:
    """Every preference by key."""
    return {preference.key: preference for preference in PREFERENCES}


def by_topic() -> dict[str, list[Preference]]:
    """The preferences of each topic, in the order they were written.

    Only topics that have something in them, so the dialog's list does not
    offer empty pages.
    """
    found: dict[str, list[Preference]] = {}
    for preference in PREFERENCES:
        found.setdefault(preference.topic, []).append(preference)
    return {topic: found[topic] for topic in TOPICS if topic in found}
