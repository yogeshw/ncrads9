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
DS9's XPA access points, as a table rather than a method each.

DS9 registers 145 of them (`ds9/library/xpa.tcl`, counting its aliases),
and almost every one is the same shape: read something the application
already knows, or hand an argument to something it already does. Writing a
method per point would be 145 near-identical methods and a fifth of the
codebase; this is a table of what each point reads and what it sets, over
the controllers that hold the real behaviour.

An entry's `get` is called with the window and returns text -- what
`xpaget` answers. Its `set` is called with the window and the argument
list and returns None for success or a message for failure. A point with
no `set` is read-only, and one with no `get` answers with what it is set
to where that makes sense.

The complicated points -- `file`, `regions`, `prism`, `3d`, `frame`,
`analysis` -- keep the hand-written handlers they already had in
`xpa_commands.py`: their grammars are real grammars, not a value each.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

#: What `xpaget` answers for a boolean, as DS9 answers it.
YES = "yes"
NO = "no"


def on_off(value: Any) -> str:
    """One boolean as DS9 writes it back."""
    return YES if value else NO


def as_bool(value: Any) -> bool | None:
    """One of DS9's booleans, or None if it is not one."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


@dataclass(frozen=True)
class AccessPoint:
    """One XPA access point.

    Attributes:
        name: What `xpaget` and `xpaset` call it.
        get: Called with the window; returns the text to answer with.
        set: Called with the window and the arguments; returns None for
            success or a message saying what was wrong.
        query: Called with the window and the arguments for a read that
            takes them -- `xpaget ds9 dsssao size`, `xpaget ds9 iexam
            coordinate image`. Where a point has both, `query` answers a
            read with arguments and `get` a bare one.
        aliases: Other names DS9 registers for the same point.
        summary: One line, for `xpaget ds9 xpa` to list.
    """

    name: str
    get: Callable[[Any], str] | None = None
    set: Callable[[Any, list[str]], str | None] | None = None
    query: Callable[[Any, list[str]], str] | None = None
    aliases: tuple[str, ...] = ()
    summary: str = ""

    @property
    def names(self) -> tuple[str, ...]:
        """Every name this point answers to."""
        return (self.name, *self.aliases)


# -- the helpers the table is written with ----------------------------------------


def trigger(action_name: str, summary: str = "") -> Callable[[Any, list[str]], str | None]:
    """A point that triggers one menu action, whatever its arguments.

    DS9 has a good few of these -- `iconify`, `raise`, `update` -- where
    the access point is exactly the menu entry.
    """

    def apply(window, _args: list[str]) -> str | None:
        action = getattr(window.menu_bar, action_name, None)
        if action is None:
            return f"{action_name} is not available"
        action.trigger()
        return None

    apply.summary = summary  # type: ignore[attr-defined]
    return apply


def call(path: str, summary: str = "") -> Callable[[Any, list[str]], str | None]:
    """A point that calls one controller method with its arguments.

    Args:
        path: `controller.method`, looked up on the window.
        summary: One line for the listing.
    """

    def apply(window, args: list[str]) -> str | None:
        target = _resolve(window, path)
        if target is None:
            return f"{path} is not available"
        target(*args)
        return None

    apply.summary = summary  # type: ignore[attr-defined]
    return apply


def read(path: str, formatter: Callable[[Any], str] = str) -> Callable[[Any], str]:
    """A point that reads one attribute or calls one no-argument method."""

    def value(window) -> str:
        found = _resolve(window, path)
        if callable(found):
            found = found()
        return formatter(found)

    return value


def flag(path: str, setter: str) -> tuple[Callable[[Any], str], Callable[[Any, list[str]], str | None]]:
    """A yes/no point: reads a flag, sets it through a method."""

    def value(window) -> str:
        found = _resolve(window, path)
        # A path can name a method -- `isChecked` -- and a bound method is
        # always truthy, so a getter that did not call it would answer yes
        # to everything.
        if callable(found):
            found = found()
        return on_off(found)

    def apply(window, args: list[str]) -> str | None:
        wanted = as_bool(args[0]) if args else True
        if wanted is None:
            return f"{args[0]} is not yes or no"
        target = _resolve(window, setter)
        if target is None:
            return f"{setter} is not available"
        target(wanted)
        return None

    return (value, apply)


def choice(
    path: str,
    setter: str,
    allowed: tuple[str, ...],
) -> tuple[Callable[[Any], str], Callable[[Any, list[str]], str | None]]:
    """A point that takes one of a fixed set of words."""

    def value(window) -> str:
        found = _resolve(window, path)
        if callable(found):
            found = found()
        return str(getattr(found, "value", found))

    def apply(window, args: list[str]) -> str | None:
        if not args:
            return f"one of {', '.join(allowed)} is needed"
        wanted = str(args[0]).lower()
        if wanted not in allowed:
            return f"{args[0]} is not one of {', '.join(allowed)}"
        target = _resolve(window, setter)
        if target is None:
            return f"{setter} is not available"
        target(wanted)
        return None

    return (value, apply)


def _resolve(window, path: str):
    """Walk a dotted path from the window, or None if it is not there."""
    found: Any = window
    for part in path.split("."):
        found = getattr(found, part, None)
        if found is None:
            return None
    return found


# -- (a) display -------------------------------------------------------------------
#
# DS9's own grouping, as TODO lists it: what the data looks like on the
# screen. Each point is the same thing the menu does.

DISPLAY_POINTS: tuple[AccessPoint, ...] = (
    AccessPoint(
        "zscale",
        get=lambda window: _zscale_text(window),
        set=lambda window, args: _zscale(window, args),
        summary="the zscale parameters: contrast, sample, line",
    ),
    AccessPoint(
        "minmax",
        get=lambda window: _minmax_text(window),
        set=lambda window, args: _minmax(window, args),
        summary="how min/max is found: scan, sample, datamin or irafmin",
    ),
    AccessPoint(
        "invert",
        *flag("invert_colormap", "color.set_inverted"),
        summary="whether the colormap is inverted",
    ),
    AccessPoint(
        "block",
        get=read("frame_manager.current_frame.block_factor"),
        set=lambda window, args: _block(window, args),
        summary="the block factor, or in, out, to fit, match, lock",
    ),
    AccessPoint(
        "smooth",
        *flag("menu_bar.action_smooth.isChecked", "analysis.set_smooth"),
        summary="whether the display is smoothed",
    ),
    AccessPoint(
        "grid",
        *flag("analysis.grid_config.visible", "analysis.set_grid"),
        summary="whether the coordinate grid is drawn",
    ),
    AccessPoint(
        "contour",
        *flag("menu_bar.action_contours.isChecked", "analysis.set_contours"),
        aliases=("contours",),
        summary="whether contours are drawn",
    ),
    AccessPoint(
        "orient",
        get=lambda window: _orient_text(window),
        set=lambda window, args: _orient(window, args),
        summary="the flip: none, x, y or xy",
    ),
    AccessPoint(
        "align",
        *flag("frame_manager.current_frame.align_wcs", "zoom.set_align_wcs"),
        summary="whether the frame is aligned to WCS north",
    ),
    AccessPoint(
        "rotate",
        get=read("frame_manager.current_frame.rotation", lambda value: f"{float(value or 0):g}"),
        set=lambda window, args: _rotate(window, args),
        summary="the rotation in degrees, or `to <deg>`",
    ),
    AccessPoint(
        "crop",
        get=lambda window: _crop_text(window),
        set=lambda window, args: _crop(window, args),
        summary="the crop: centre and size, or `reset`",
    ),
    AccessPoint(
        "magnifier",
        get=lambda window: on_off(window.menu_bar.action_view_magnifier.isChecked()),
        set=lambda window, args: _panel(window, args, "magnifier"),
        summary="whether the magnifier is shown",
    ),
    AccessPoint(
        "panner",
        get=lambda window: on_off(window.menu_bar.action_view_panner.isChecked()),
        set=lambda window, args: _panel(window, args, "panner"),
        summary="whether the panner is shown",
    ),
    AccessPoint(
        "mask",
        get=lambda window: on_off(getattr(window.analysis, "mask_layer", None) is not None),
        set=lambda window, args: _mask(window, args),
        summary="the mask: a file to load, or `clear`",
    ),
)


# -- (b) frames --------------------------------------------------------------------

FRAME_POINTS: tuple[AccessPoint, ...] = (
    AccessPoint(
        "single",
        get=lambda window: on_off(window._frame_display_mode == "single"),
        set=lambda window, _args: window.frame_controller.set_display_mode("single"),
        summary="show one frame at a time",
    ),
    AccessPoint(
        "tile",
        get=lambda window: on_off(window._frame_display_mode == "tile"),
        set=lambda window, args: _tile(window, args),
        summary="tile the frames, or `tile mode grid|column|row`",
    ),
    AccessPoint(
        "blink",
        get=lambda window: on_off(window._frame_display_mode == "blink"),
        set=lambda window, args: _blink(window, args, "blink"),
        summary="blink the frames, or `blink interval <seconds>`",
    ),
    AccessPoint(
        "fade",
        get=lambda window: on_off(window._frame_display_mode == "fade"),
        set=lambda window, args: _blink(window, args, "fade"),
        summary="fade between the frames, or `fade interval <seconds>`",
    ),
    AccessPoint(
        "first",
        set=lambda window, _args: window.frame_controller.first(),
        summary="go to the first frame",
    ),
    AccessPoint(
        "last",
        set=lambda window, _args: window.frame_controller.last(),
        summary="go to the last frame",
    ),
    AccessPoint(
        "next",
        set=lambda window, _args: window.frame_controller.next(),
        summary="go to the next frame",
    ),
    AccessPoint(
        "prev",
        set=lambda window, _args: window.frame_controller.previous(),
        summary="go to the previous frame",
    ),
    AccessPoint(
        "slice",
        get=read("frame_manager.current_frame.slice_index", lambda value: str(int(value or 0) + 1)),
        set=lambda window, args: _slice(window, args),
        summary="which slice of a cube is shown, counting from one",
    ),
    AccessPoint(
        "cube",
        get=read("frame_manager.current_frame.slice_index", lambda value: str(int(value or 0) + 1)),
        aliases=("datacube",),
        set=lambda window, args: _slice(window, args),
        summary="which slice of a cube is shown",
    ),
    AccessPoint(
        "lock",
        get=lambda window: _lock_text(window),
        set=lambda window, args: _lock(window, args),
        summary="lock a scope across frames: frame, crosshair, crop, slice, ...",
    ),
    AccessPoint(
        "match",
        set=lambda window, args: _match(window, args),
        summary="match a scope across frames",
    ),
)


def _integer(window, args: list[str], path: str, what: str) -> str | None:
    """One integer argument, handed to a controller method."""
    if not args:
        return f"{what} is needed"
    try:
        value = int(float(args[0]))
    except ValueError:
        return f"{args[0]} is not a number"
    target = _resolve(window, path)
    if target is None:
        return f"{path} is not available"
    target(value)
    return None


def _rotate(window, args: list[str]) -> str | None:
    """`rotate <deg>` turns by an amount; `rotate to <deg>` sets the angle."""
    if not args:
        return "an angle is needed"
    words = [str(word).lower() for word in args]
    absolute = words[0] == "to"
    numbers = words[1:] if absolute else words
    if not numbers:
        return "an angle is needed"
    try:
        degrees = float(numbers[0])
    except ValueError:
        return f"{numbers[0]} is not an angle"
    frame = window.frame_manager.current_frame
    current = 0.0 if frame is None else float(getattr(frame, "rotation", 0.0))
    window.zoom.set_rotation(degrees if absolute else current + degrees)
    return None


def _crop_text(window) -> str:
    """The crop as DS9 reports it: centre then size, or the whole image."""
    crop = window.crop.region()
    if crop is None:
        shape = window.crop.shape()
        if shape is None:
            return "0 0 0 0"
        return f"{shape[1] / 2:g} {shape[0] / 2:g} {shape[1]:g} {shape[0]:g}"
    centre = crop.center
    return f"{centre[0]:g} {centre[1]:g} {crop.width:g} {crop.height:g}"


def _crop(window, args: list[str]) -> str | None:
    """`crop <x> <y> <w> <h>`, or `crop reset`."""
    if not args:
        return "a centre and a size are needed"
    if str(args[0]).lower() == "reset":
        window.crop.reset()
        return None
    if len(args) < 4:
        return "a centre and a size are needed"
    try:
        x, y, width, height = (float(value) for value in args[:4])
    except ValueError:
        return "the centre and size have to be numbers"
    from ...frames.crop import CropRegion

    window.crop.set_region(CropRegion.from_center(x, y, width, height))
    return None


def _mask(window, args: list[str]) -> str | None:
    """`mask <file>` loads one; `mask clear` removes it."""
    if not args:
        return "a mask file or `clear` is needed"
    if str(args[0]).lower() == "clear":
        window.analysis.clear_mask()
        return None
    return None if window.analysis.load_mask(str(args[0])) else "the mask could not be loaded"


def _tile(window, args: list[str]) -> str | None:
    """`tile`, `tile yes|no`, or `tile mode grid|column|row`."""
    words = [str(word).lower() for word in args]
    if words and words[0] == "mode":
        if len(words) < 2:
            return "grid, column or row is needed"
        window.frame_controller.set_tile_arrangement(words[1])
        # DS9's `tile mode` says how to tile, which implies tiling.
        window.frame_controller.set_display_mode("tile")
        return None
    wanted = as_bool(words[0]) if words else True
    if wanted is False:
        window.frame_controller.set_display_mode("single")
        return None
    window.frame_controller.set_display_mode("tile")
    return None


def _blink(window, args: list[str], mode: str) -> str | None:
    """`blink`, `blink yes|no`, or `blink interval <seconds>`."""
    words = [str(word).lower() for word in args]
    if words and words[0] == "interval":
        if len(words) < 2:
            return "an interval in seconds is needed"
        try:
            seconds = float(words[1])
        except ValueError:
            return f"{words[1]} is not a number of seconds"
        setter = (
            window.frame_controller.set_blink_interval
            if mode == "blink"
            else window.frame_controller.set_fade_interval
        )
        setter(int(seconds * 1000))
        return None
    wanted = as_bool(words[0]) if words else True
    window.frame_controller.set_display_mode(mode if wanted else "single")
    return None


def _slice(window, args: list[str]) -> str | None:
    """`slice <n>`, counting from one as DS9's cube dialog does."""
    if not args:
        return "a slice number is needed"
    try:
        wanted = int(float(args[0]))
    except ValueError:
        return f"{args[0]} is not a slice number"
    window.frame_controller.set_slice(wanted - 1)
    return None


def _lock_text(window) -> str:
    """Every lock scope and what it is set to."""
    scopes = getattr(window, "_frame_lock_scope", {})
    flags = getattr(window, "_frame_lock_flags", {})
    lines = [f"{name} {value}" for name, value in sorted(scopes.items())]
    lines.extend(f"{name} {on_off(value)}" for name, value in sorted(flags.items()))
    return "\n".join(lines)


def _lock(window, args: list[str]) -> str | None:
    """`lock <scope> <system>` or `lock <flag> yes|no`."""
    if not args:
        return "a scope is needed"
    scope = str(args[0]).lower()
    rest = [str(word).lower() for word in args[1:]]

    if scope in getattr(window, "_frame_lock_scope", {}):
        system = rest[0] if rest else "wcs"
        window.frame_controller.set_lock_scope(scope, system)
        return None
    if scope in getattr(window, "_frame_lock_flags", {}):
        wanted = as_bool(rest[0]) if rest else True
        window.frame_controller.set_lock_flag(scope, bool(wanted))
        return None
    return f"{args[0]} is not something that locks"


def _match(window, args: list[str]) -> str | None:
    """`match <scope> [<system>]`, over the same scopes as the lock."""
    if not args:
        return "a scope is needed"
    scope = str(args[0]).lower()
    system = str(args[1]).lower() if len(args) > 1 else "wcs"
    controller = window.frame_controller

    if scope == "frame":
        (controller.match_wcs if system == "wcs" else controller.match_image)()
        return None
    if scope == "crosshair":
        window.crosshair.match(system)
        return None
    if scope == "crop":
        window.crop.match(system)
        return None
    if scope == "3d":
        window.frame_3d.match()
        return None
    matcher = getattr(controller, f"match_{scope}", None)
    if matcher is None:
        return f"{args[0]} is not something that matches"
    matcher()
    return None


def _zscale_text(window) -> str:
    """The zscale parameters, as `xpaget zscale <name>` asks for them."""
    settings = window.scale.settings
    return "\n".join(
        [
            f"contrast {settings.contrast:g}",
            f"sample {settings.samples}",
            f"line {settings.samples_per_line}",
        ]
    )


def _zscale(window, args: list[str]) -> str | None:
    """`zscale`, or `zscale contrast|sample|line <value>`."""
    if not args:
        window.scale.set_limit_mode("zscale")
        return None
    name = str(args[0]).lower()
    fields = {"contrast": "contrast", "sample": "samples", "line": "samples_per_line"}
    if name not in fields:
        return f"{args[0]} is not a zscale parameter"
    if len(args) < 2:
        return f"a value for {name} is needed"
    try:
        value = float(args[1]) if name == "contrast" else int(float(args[1]))
    except ValueError:
        return f"{args[1]} is not a number"
    window.scale.update(**{fields[name]: value})
    return None


def _minmax_text(window) -> str:
    """The min/max method and its sample interval."""
    settings = window.scale.settings
    method = getattr(settings.method, "value", settings.method)
    return f"mode {method}\ninterval {settings.sample_increment}"


def _minmax(window, args: list[str]) -> str | None:
    """`minmax <method>`, `minmax mode <method>`, `interval #` or `rescan`."""
    methods = ("scan", "sample", "datamin", "irafmin")
    if not args:
        window.scale.set_limit_mode("minmax")
        return None

    word = str(args[0]).lower()
    if word in methods:
        window.scale.set_minmax_method(word)
        return None
    if word == "mode":
        if len(args) < 2 or str(args[1]).lower() not in methods:
            return f"one of {', '.join(methods)} is needed"
        window.scale.set_minmax_method(str(args[1]).lower())
        return None
    if word == "interval":
        if len(args) < 2:
            return "an interval is needed"
        try:
            window.scale.update(sample_increment=int(float(args[1])))
        except ValueError:
            return f"{args[1]} is not a number"
        return None
    if word == "rescan":
        window.scale.invalidate()
        return None
    return f"{args[0]} is not a minmax setting"


def _block(window, args: list[str]) -> str | None:
    """`block <n>`, `block to <n>`, `in`, `out`, `to fit`, `match`, `lock`."""
    analysis = window.analysis
    words = [str(word).lower() for word in args]
    if not words:
        return "a block factor is needed"

    if words[0] == "in":
        analysis.block_in()
        return None
    if words[0] == "out":
        analysis.block_out()
        return None
    if words[0] == "match":
        window.frame_controller.match_block()
        return None
    if words[0] == "lock":
        wanted = as_bool(words[1]) if len(words) > 1 else True
        window.frame_controller.set_lock_flag("block", bool(wanted))
        return None
    if words[0] == "to":
        if len(words) < 2:
            return "a block factor is needed"
        if words[1] == "fit":
            analysis.block_fit()
            return None
        words = words[1:]

    try:
        # DS9 takes one factor or two; ours blocks both axes alike, so the
        # first is what counts and a second is accepted and ignored.
        factor = int(float(words[0]))
    except ValueError:
        return f"{words[0]} is not a block factor"
    analysis.set_block(factor)
    return None


# -- (d) tools ---------------------------------------------------------------------

TOOL_POINTS: tuple[AccessPoint, ...] = (
    AccessPoint(
        "pixeltable",
        get=lambda window: on_off(window.analysis.pixel_table_open()),
        set=lambda window, args: _pixel_table(window, args),
        summary="show or hide the pixel table",
    ),
    AccessPoint(
        "notes",
        get=read("notes.text"),
        set=lambda window, args: _notes(window, args),
        summary="the session notes: append, insert, clear, load, save",
    ),
    AccessPoint(
        "nameserver",
        get=lambda window: str(getattr(window, "_last_resolved_name", "")),
        set=lambda window, args: _nameserver(window, args),
        summary="resolve an object name and pan to it",
    ),
    AccessPoint(
        "illustrate",
        get=lambda window: on_off(window.illustrate.layer.visible),
        set=lambda window, args: _illustrate(window, args),
        summary="the illustrate layer: show, open, save, list, delete",
    ),
)


# -- (e) application ---------------------------------------------------------------

APP_POINTS: tuple[AccessPoint, ...] = (
    AccessPoint(
        "width",
        get=lambda window: str(window.image_viewer.width()),
        set=lambda window, args: _size(window, args, "width"),
        summary="the width of the image display",
    ),
    AccessPoint(
        "height",
        get=lambda window: str(window.image_viewer.height()),
        set=lambda window, args: _size(window, args, "height"),
        summary="the height of the image display",
    ),
    AccessPoint(
        "iconify",
        get=lambda window: on_off(window.isMinimized()),
        set=lambda window, args: _iconify(window, args),
        summary="minimise the window",
    ),
    AccessPoint(
        "raise",
        set=lambda window, _args: _raise(window),
        summary="raise the window",
    ),
    AccessPoint(
        "lower",
        set=lambda window, _args: window.lower(),
        summary="lower the window",
    ),
    AccessPoint(
        "nan",
        get=read("nan_color"),
        set=lambda window, args: _nan(window, args),
        summary="the colour blank, infinite and NaN pixels are drawn in",
    ),
    AccessPoint(
        "preserve",
        get=lambda window: _preserve_text(window),
        set=lambda window, args: _preserve(window, args),
        summary="what survives a load: pan, regions",
    ),
    AccessPoint(
        "mode",
        get=read("edit_mode"),
        set=lambda window, args: _mode(window, args),
        summary="what the first mouse button does",
    ),
    AccessPoint(
        "crosshair",
        get=lambda window: _cursor_text(window),
        set=lambda window, args: _crosshair(window, args),
        summary="where the crosshair is, in image pixels",
    ),
    AccessPoint(
        "cursor",
        get=lambda window: _cursor_text(window),
        set=lambda window, args: _cursor(window, args),
        summary="move the crosshair, in image pixels",
    ),
    AccessPoint(
        "cd",
        get=lambda _window: str(_cwd()),
        set=lambda window, args: _cd(window, args),
        summary="the working directory",
    ),
    AccessPoint(
        "pagesetup",
        get=lambda window: _pagesetup_text(window),
        set=lambda window, args: _pagesetup(window, args),
        summary="the page: orient, scale, size",
    ),
    AccessPoint(
        "psprint",
        set=lambda window, args: _psprint(window, args),
        aliases=("print",),
        summary="print, to the printer or to a file",
    ),
    AccessPoint(
        "sleep",
        set=lambda _window, args: _sleep(args),
        summary="wait a number of seconds",
    ),
    AccessPoint(
        "update",
        set=lambda window, _args: window.display.display(),
        summary="redraw now",
    ),
    AccessPoint(
        "backup",
        set=lambda window, args: _one_file(window, args, "session.backup", "a backup file"),
        summary="write a backup",
    ),
    AccessPoint(
        "restore",
        set=lambda window, args: _one_file(window, args, "session.restore", "a backup file"),
        summary="read a backup",
    ),
    AccessPoint(
        "header",
        set=lambda window, _args: window.file.show_header(),
        summary="show the FITS header",
    ),
    AccessPoint(
        "movie",
        set=lambda window, args: _movie(window, args),
        aliases=("savempeg",),
        summary="write a movie of the frames or the slices",
    ),
    AccessPoint(
        "saveimage",
        set=lambda window, args: _saveimage(window, args),
        summary="write the rendered view as a picture",
    ),
)


def _shown(window, args: list[str], setter: str) -> str | None:
    """DS9's `yes|no|open|close` shape, which several tools take."""
    words = [str(word).lower() for word in args]
    if not words or words[0] in ("open", "yes"):
        wanted = True
    elif words[0] in ("close", "no"):
        wanted = False
    else:
        found = as_bool(words[0])
        if found is None:
            return f"{args[0]} is not yes, no, open or close"
        wanted = found
    target = _resolve(window, setter)
    if target is None:
        return f"{setter} is not available"
    target(wanted)
    return None


def _notes(window, args: list[str]) -> str | None:
    """`notes append|insert <text>`, `clear`, `load <file>`, `save <file>`."""
    if not args:
        window.notes.show_dialog()
        return None
    word = str(args[0]).lower()
    rest = " ".join(str(value) for value in args[1:])
    if word == "append":
        window.notes.append(rest)
        return None
    if word == "insert":
        window.notes.insert(rest)
        return None
    if word == "clear":
        window.notes.clear()
        return None
    if word == "load":
        return None if window.notes.load(rest) else f"could not read {rest}"
    if word == "save":
        return None if window.notes.save(rest) else f"could not write {rest}"
    return f"{args[0]} is not a notes command"


def _nameserver(window, args: list[str]) -> str | None:
    """`nameserver <object>` resolves a name and pans to it."""
    if not args:
        window.analysis.resolve_object_name()
        return None
    name = " ".join(str(value) for value in args)
    if str(args[0]).lower() == "name" and len(args) > 1:
        name = " ".join(str(value) for value in args[1:])
    return window.analysis.resolve_name(name)


def _illustrate(window, args: list[str]) -> str | None:
    """`illustrate show|open|save|list|delete`."""
    if not args:
        return "a command is needed"
    word = str(args[0]).lower()
    controller = window.illustrate
    rest = [str(value) for value in args[1:]]

    if word == "show":
        wanted = as_bool(rest[0]) if rest else True
        controller.set_visible(bool(wanted))
        return None
    if word in ("open", "load"):
        if not rest:
            return "a file is needed"
        return None if controller.load(rest[0]) else f"could not read {rest[0]}"
    if word == "save":
        if not rest:
            return "a file is needed"
        return None if controller.save(rest[0]) else f"could not write {rest[0]}"
    if word == "list":
        controller.list_all()
        return None
    if word in ("delete", "deleteall"):
        controller.delete_all()
        return None
    return f"{args[0]} is not an illustrate command"


def _size(window, args: list[str], which: str) -> str | None:
    """`width <n>` and `height <n>` size the *image display*.

    Which is what DS9 sizes, not the whole window: the difference is the
    panels and the menu bar, so the window is grown by however much the
    display is short of what was asked for.
    """
    if not args:
        return "a size in pixels is needed"
    try:
        value = max(1, int(float(args[0])))
    except ValueError:
        return f"{args[0]} is not a size"

    viewer = window.image_viewer
    window_size = window.size()
    if which == "width":
        window.resize(window_size.width() + (value - viewer.width()), window_size.height())
    else:
        window.resize(window_size.width(), window_size.height() + (value - viewer.height()))
    return None


def _iconify(window, args: list[str]) -> str | None:
    """`iconify` toggles; `iconify yes|no` says which."""
    wanted = as_bool(args[0]) if args else not window.isMinimized()
    if wanted is None:
        return f"{args[0]} is not yes or no"
    if wanted:
        window.showMinimized()
    else:
        window.showNormal()
    return None


def _nan(window, args: list[str]) -> str | None:
    """`nan <colour>`: what a blank pixel is painted."""
    if not args:
        return "a colour is needed"
    window.nan_color = str(args[0])
    window.display.display()
    return None


def _preserve_text(window) -> str:
    """What survives a load."""
    return "\n".join(f"{name} {on_off(value)}" for name, value in sorted(window._preserve.items()))


def _preserve(window, args: list[str]) -> str | None:
    """`preserve pan|regions yes|no`."""
    if not args:
        return "pan or regions is needed"
    what = str(args[0]).lower()
    if what not in window._preserve:
        return f"{args[0]} is not something that is preserved"
    wanted = as_bool(args[1]) if len(args) > 1 else True
    window.file.set_preserve(what, bool(wanted))
    return None


def _mode(window, args: list[str]) -> str | None:
    """`mode <name>`: what the first mouse button does."""
    if not args:
        return "a mode is needed"
    wanted = str(args[0]).lower()
    if wanted not in window.menu_bar.edit_mode_actions:
        return f"{args[0]} is not a pointer mode"
    window.edit.set_mode(wanted)
    return None


def _cursor_text(window) -> str:
    """Where the crosshair is, in image pixels."""
    placed = window.crosshair.position()
    if placed is None:
        return "0 0"
    return f"{placed[0]:g} {placed[1]:g}"


def _cursor(window, args: list[str]) -> str | None:
    """`cursor <x> <y>`: move the crosshair there."""
    if len(args) < 2:
        return "an x and a y are needed"
    try:
        x, y = float(args[0]), float(args[1])
    except ValueError:
        return "the position has to be two numbers"
    window.crosshair.move_to(x, y)
    return None


def _cwd():
    """The working directory."""
    from pathlib import Path

    return Path.cwd()


def _cd(window, args: list[str]) -> str | None:
    """`cd <directory>`."""
    import os

    if not args:
        return "a directory is needed"
    try:
        os.chdir(str(args[0]))
    except OSError as exc:
        return str(exc)
    return None


def _pagesetup_text(window) -> str:
    """The page as DS9 reports it."""
    page = window.file.print_settings.page
    return "\n".join(
        [
            f"orient {page.orientation.value}",
            f"scale {page.scale:g}",
            f"size {page.paper_size.value}",
        ]
    )


def _pagesetup(window, args: list[str]) -> str | None:
    """`pagesetup orient|scale|size <value>`."""
    from dataclasses import replace as _replace

    from ...printing.page_setup import Orientation, PaperSize

    if len(args) < 2:
        return "orient, scale or size and a value are needed"
    what, value = str(args[0]).lower(), str(args[1]).lower()
    page = window.file.print_settings.page

    if what == "orient":
        if value not in [choice.value for choice in Orientation]:
            return f"{value} is not an orientation"
        page = _replace(page, orientation=Orientation(value))
    elif what == "scale":
        try:
            page = _replace(page, scale=float(value))
        except ValueError:
            return f"{value} is not a scale"
    elif what == "size":
        if value not in [choice.value for choice in PaperSize]:
            return f"{value} is not a page size"
        page = _replace(page, paper_size=PaperSize(value))
    else:
        return f"{args[0]} is not a page setting"

    window.file.print_settings = _replace(window.file.print_settings, page=page)
    return None


def _psprint(window, args: list[str]) -> str | None:
    """`psprint`, `psprint filename <file>`, `psprint destination file`."""
    from dataclasses import replace as _replace

    from ...printing.print_engine import Destination

    settings = window.file.print_settings
    words = [str(word) for word in args]
    if words:
        first = words[0].lower()
        if first in ("filename", "file") and len(words) > 1:
            settings = _replace(settings, destination=Destination.FILE, filename=words[1])
        elif first == "destination" and len(words) > 1:
            wanted = words[1].lower()
            if wanted not in ("printer", "file"):
                return f"{words[1]} is not printer or file"
            settings = _replace(settings, destination=Destination(wanted))
        elif first == "command" and len(words) > 1:
            settings = _replace(settings, command=" ".join(words[1:]))
        elif first == "resolution" and len(words) > 1:
            try:
                settings = _replace(settings, resolution=int(float(words[1])))
            except ValueError:
                return f"{words[1]} is not a resolution"
        elif first == "level" and len(words) > 1:
            try:
                settings = _replace(settings, level=int(float(words[1])))
            except ValueError:
                return f"{words[1]} is not a level"
        elif first == "color" and len(words) > 1:
            settings = _replace(settings, color_model=words[1].lower())
        else:
            settings = _replace(settings, destination=Destination.FILE, filename=words[0])
        window.file.print_settings = settings
        if first in ("destination", "command", "resolution", "level", "color"):
            return None

    return None if window.file.print_image(window.file.print_settings) else "the print failed"


def _sleep(args: list[str]) -> str | None:
    """`sleep [#]`: DS9 has it so a script can wait for a load."""
    import time

    try:
        seconds = float(args[0]) if args else 1.0
    except ValueError:
        return f"{args[0]} is not a number of seconds"
    time.sleep(max(0.0, min(seconds, 60.0)))
    return None


def _one_file(window, args: list[str], path: str, what: str) -> str | None:
    """A point that takes one filename and hands it to a controller."""
    if not args:
        return f"{what} is needed"
    target = _resolve(window, path)
    if target is None:
        return f"{path} is not available"
    return None if target(str(args[0])) else f"{what} failed"


def _movie(window, args: list[str]) -> str | None:
    """`movie <file>`, or `movie slice|frame <file>`."""
    words = [str(word) for word in args]
    if not words:
        return "a file is needed"
    action = "frame"
    if words[0].lower() in ("slice", "frame", "3d"):
        action = words[0].lower()
        words = words[1:]
    if not words:
        return "a file is needed"
    kind = "mpeg" if words[0].lower().endswith((".mpg", ".mp4", ".mpeg")) else "gif"
    made = window.file.create_movie(words[0], {"type": kind, "action": action, "delay": 10})
    return None if made else "the movie could not be written"


def _saveimage(window, args: list[str]) -> str | None:
    """`saveimage <file>`, in whatever format the name asks for."""
    if not args:
        return "a file is needed"
    from pathlib import Path

    from ...io import raster

    path = Path(str(args[0]))
    suffix = path.suffix.lower()
    formats = {suffix: name for name, suffixes in raster.FORMATS.items() for suffix in suffixes}
    pixmap = window.file.current_pixmap()
    if pixmap is None:
        return "there is no image to save"

    if suffix in (".eps", ".ps"):
        return None if window.file._save_eps(pixmap, str(path)) else "the image could not be saved"
    if suffix in formats:
        return (
            None
            if window.file._save_image_raster(formats[suffix], pixmap, str(path))
            else "the image could not be saved"
        )
    return f"{suffix or path.name} is not a format saveimage writes"


def _raise(window) -> None:
    """Bring the window to the front, as DS9's `raise` does."""
    window.raise_()
    window.activateWindow()


def _panel(window, args: list[str], name: str) -> str | None:
    """One of the View menu's panels, shown or hidden."""
    words = [str(word).lower() for word in args]
    if not words or words[0] in ("yes", "open"):
        wanted = True
    elif words[0] in ("no", "close"):
        wanted = False
    else:
        found = as_bool(words[0])
        if found is None:
            return f"{args[0]} is not yes, no, open or close"
        wanted = found
    window.view.set_panel(name, wanted)
    return None


def _pixel_table(window, args: list[str]) -> str | None:
    """`pixeltable [yes|no|open|close]`."""
    words = [str(word).lower() for word in args]
    wanted = True
    if words:
        if words[0] in ("no", "close"):
            wanted = False
        elif words[0] not in ("yes", "open"):
            found = as_bool(words[0])
            if found is None:
                return f"{args[0]} is not yes, no, open or close"
            wanted = found
    if wanted:
        window.analysis.show_pixel_table()
    else:
        window.analysis.close_pixel_table()
    return None


def _orient_text(window) -> str:
    """The flip as DS9 names it."""
    frame = window.frame_manager.current_frame
    if frame is None:
        return "none"
    flipped_x = bool(getattr(frame, "flip_x", False))
    flipped_y = bool(getattr(frame, "flip_y", False))
    if flipped_x and flipped_y:
        return "xy"
    if flipped_x:
        return "x"
    if flipped_y:
        return "y"
    return "none"


def _orient(window, args: list[str]) -> str | None:
    """`orient none|x|y|xy`."""
    if not args:
        return "none, x, y or xy is needed"
    wanted = str(args[0]).lower()
    if wanted not in ("none", "x", "y", "xy"):
        return f"{args[0]} is not an orientation"
    window.zoom.set_orientation(wanted)
    return None


# -- the rest of DS9's list ---------------------------------------------------------
#
# Points that are one line each: a file to load, a window to show, a value
# to read. The loaders all go through the File controller's own entries, so
# what XPA does and what the menu does cannot drift apart.


def _open_fits(window, args: list[str]) -> str | None:
    """Load a plain FITS file, which DS9's `sfits` and `memf` end up doing.

    DS9's `sfits` takes a header file and a data file, and `memf` a shared
    memory segment; both are ways of getting at a FITS image, and once it
    is a file on disk there is one way to open it. The shared-memory form
    proper is the `shm` point.
    """
    if not args:
        return "a filename is needed"
    path = str(args[-1])
    try:
        window.file.open_file(filepath=path)
    except Exception as exc:
        return f"could not open {path}: {exc}"
    return None


def _load_as(kind: str):
    """A point that loads a file through one `Open as` entry."""

    def apply(window, args: list[str]) -> str | None:
        if not args:
            return "a filename is needed"
        return window.file.open_as(kind, str(args[-1]))

    return apply


def _import_as(kind: str):
    """A point that loads a file through one Import entry."""

    def apply(window, args: list[str]) -> str | None:
        if not args:
            return "a filename is needed"
        return None if window.file.import_file(kind, str(args[-1])) else f"{args[-1]} could not be imported"

    return apply


def _export_as(kind: str):
    """A point that writes a file through one Export entry."""

    def apply(window, args: list[str]) -> str | None:
        if not args:
            return "a filename is needed"
        return None if window.file.export_file(kind, str(args[-1])) else f"{args[-1]} could not be written"

    return apply


def _show_window(path: str):
    """A point that opens one tool window."""

    def apply(window, _args: list[str]) -> str | None:
        target = _resolve(window, path)
        if target is None:
            return f"{path} is not available"
        target()
        return None

    return apply


FILE_POINTS: tuple[AccessPoint, ...] = (
    AccessPoint("array", set=_import_as("array"), summary="load a raw array"),
    AccessPoint("nrrd", set=_import_as("nrrd"), summary="load a NRRD file"),
    AccessPoint("envi", set=_import_as("envi"), summary="load an ENVI file"),
    AccessPoint("gif", set=_import_as("gif"), summary="load a GIF"),
    AccessPoint("tiff", set=_import_as("tiff"), aliases=("tif",), summary="load a TIFF"),
    AccessPoint("jpeg", set=_import_as("jpeg"), aliases=("jpg",), summary="load a JPEG"),
    AccessPoint("png", set=_import_as("png"), summary="load a PNG"),
    AccessPoint("export", set=lambda window, args: _export(window, args), summary="export the frame"),
    AccessPoint("rgbimage", set=_load_as("rgb_image"), summary="load an RGB image"),
    AccessPoint("rgbcube", set=_load_as("rgb_cube"), summary="load an RGB cube"),
    AccessPoint("hsvimage", set=_load_as("hsv_image"), summary="load an HSV image"),
    AccessPoint("hsvcube", set=_load_as("hsv_cube"), summary="load an HSV cube"),
    AccessPoint("hlsimage", set=_load_as("hls_image"), summary="load an HLS image"),
    AccessPoint("hlscube", set=_load_as("hls_cube"), summary="load an HLS cube"),
    AccessPoint("rgbarray", set=_import_as("rgb_array"), summary="load an RGB array"),
    AccessPoint("hsvarray", set=_import_as("hsv_array"), summary="load an HSV array"),
    AccessPoint("hlsarray", set=_import_as("hls_array"), summary="load an HLS array"),
    AccessPoint("mecube", set=_load_as("mef_cube"), summary="load a multi-extension cube"),
    AccessPoint("multiframe", set=_load_as("mef_frames"), summary="load extensions as frames"),
    AccessPoint(
        "mosaicimagewcs",
        set=_load_as("mosaic_wcs"),
        aliases=("mosaicwcs", "mosaicimage", "mosaic"),
        summary="load a WCS mosaic",
    ),
    AccessPoint(
        "mosaicimageiraf",
        set=_load_as("mosaic_iraf"),
        aliases=("mosaiciraf",),
        summary="load an IRAF mosaic",
    ),
    AccessPoint(
        "mosaicimagewfpc2",
        set=_load_as("mosaic_wfpc2"),
        summary="load a WFPC2 mosaic",
    ),
    AccessPoint("smosaicwcs", set=_load_as("mosaic_wcs_segment"), summary="load a WCS mosaic segment"),
    AccessPoint(
        "smosaiciraf",
        set=_load_as("mosaic_iraf_segment"),
        aliases=("smosaic",),
        summary="load an IRAF mosaic segment",
    ),
    AccessPoint("url", set=lambda window, args: _url(window, args), summary="load a file from a URL"),
)


TOOL_WINDOW_POINTS: tuple[AccessPoint, ...] = (
    AccessPoint(
        "catalog", set=_show_window("catalog.show_dialog"), aliases=("cat",), summary="the catalogue tool"
    ),
    AccessPoint(
        "footprint",
        set=_show_window("catalog.show_footprint_dialog"),
        aliases=("fp",),
        summary="the footprint tool",
    ),
    AccessPoint(
        "vo",
        set=_show_window("vo.show_registry"),
        summary="the virtual observatory tool: the registry of services",
    ),
    AccessPoint(
        "shm",
        get=lambda window: _shm_text(window),
        set=lambda window, args: _shm(window, args),
        summary="load an image out of shared memory",
    ),
    AccessPoint(
        "iis",
        get=lambda window: _iis_text(window),
        set=lambda window, args: _iis(window, args),
        summary="the IIS server for IRAF: filename, start, stop",
    ),
    AccessPoint(
        "iexam",
        get=lambda window: examine(window, []),
        query=lambda window, args: examine(window, args),
        set=lambda window, args: None,
        aliases=("imexam",),
        summary="wait for a click and answer with what was asked for",
    ),
    AccessPoint(
        "samp",
        get=lambda window: _samp_text(window),
        set=lambda window, args: _samp(window, args),
        summary="SAMP: connect, disconnect, broadcast, hub start|stop",
    ),
    AccessPoint("prefs", set=_show_window("edit.show_preferences"), summary="the preferences dialog"),
    AccessPoint("about", get=lambda window: _about(window), summary="what this is"),
    AccessPoint("version", get=lambda window: _version(window), summary="the version"),
)


def _export(window, args: list[str]) -> str | None:
    """`export <format> <file>`, as DS9's Export cascade offers."""
    words = [str(word) for word in args]
    if len(words) < 2:
        return "a format and a filename are needed"
    kind = (
        words[0].lower().replace("array", "_array")
        if words[0].lower().endswith("array")
        else words[0].lower()
    )
    return None if window.file.export_file(kind, words[1]) else f"{words[1]} could not be written"


def _url(window, args: list[str]) -> str | None:
    """`url <address>`: load a file over HTTP."""
    if not args:
        return "a URL is needed"
    return window.file.open_url(str(args[0]))


def _about(window) -> str:
    """What DS9's `about` answers with: the credits."""
    from ... import __version__

    return f"NCRADS9 {__version__}\nA PyQt6 reimplementation of SAOImageDS9"


def _version(window) -> str:
    """The version, as DS9's `version` answers."""
    from ... import __version__

    return f"ncrads9 {__version__}"


# -- the image servers -------------------------------------------------------------
#
# DS9 has one point per server and they all share a grammar (`xpa.html`):
# a name to resolve, a position, a size, a survey, `save`, `frame`,
# `update`, and open or close. One helper builds them all rather than nine
# near-identical entries.


def _server_point(name: str, server: str, summary: str) -> AccessPoint:
    """One image server's access point."""

    def apply(window, args: list[str]) -> str | None:
        return _image_server(window, server, args)

    def value(window) -> str:
        return _image_server_read(window, server, [])

    def ask(window, args: list[str]) -> str:
        return _image_server_read(window, server, args)

    return AccessPoint(name, get=value, query=ask, set=apply, summary=summary)


IMAGE_SERVER_POINTS: tuple[AccessPoint, ...] = (
    _server_point("dsssao", "dsssao", "the DSS at SAO"),
    _server_point("dsseso", "dsseso", "the DSS at ESO"),
    _server_point("dssstsci", "dssstsci", "the DSS at STScI"),
    _server_point("dss", "dsssao", "the DSS, DS9's short name for the SAO one"),
    _server_point("2mass", "twomass", "2MASS"),
    _server_point("skyview", "skyview", "SkyView at HEASARC"),
    _server_point("vla", "vla", "the VLA FIRST survey"),
    _server_point("nvss", "nvss", "the NVSS"),
    _server_point("vlss", "vlss", "the VLSS"),
)


def _image_server_read(window, server: str, args: list[str]) -> str:
    """What an image-server point answers.

    DS9 reads `name`, `coord`, `size`, `survey`, `save` and `frame` off
    the dialog; a bare read answers with the position, since that is what
    the point is chiefly about.
    """
    controller = window.image_servers
    what = args[0].lower() if args else "coord"
    options = controller.options(server)
    if what in ("save", "frame", "update"):
        return options[what]

    dialog = controller._dialogs.get(server)
    if dialog is None:
        # Nothing open: answer for where a cutout would be centred, which
        # is the frame's centre, as the dialog would have been.
        if what in ("coord", "coordinate"):
            centre = controller.frame_center()
            return "0 0" if centre is None else f"{centre[0]:g} {centre[1]:g}"
        return ""
    if what == "name":
        return dialog.object_name()
    if what == "survey":
        return dialog.survey()
    if what == "pixels":
        pixels = dialog.pixels()
        return "" if pixels is None else f"{pixels[0]} {pixels[1]}"
    if what == "size":
        width, height = dialog.size()
        return f"{width:g} {height:g} {dialog.server.size_unit.value}"
    longitude, latitude = dialog.center()
    return f"{longitude:g} {latitude:g}"


def _image_server(window, server: str, args: list[str]) -> str | None:
    """DS9's image-server grammar, which every server shares.

    `<object>`, `name <object>|clear`, `<ra> <dec>`, `size <w> <h>
    <unit>`, `pixels <w> <h>`, `survey <name>`, `save yes|no`, `frame
    new|current`, `update frame|crosshair`, `open|close`, and a bare call
    to fetch what the dialog is set to.

    Which of these fetch and which only set is DS9's own division, from
    the grammar in `ds9/parsers/dssesoparser.tac`: a bare call, a name, a
    position and an update all end in `IMGSVRApply`, and `size`, `save`,
    `frame`, `survey` and `name clear` do not.
    """
    from ...image_servers.servers import by_name

    definition = by_name(server)
    if definition is None:
        return f"{server} is not an image server we have"

    words = [str(word) for word in args]
    controller = window.image_servers
    options = controller.options(server)

    if words and words[0].lower() == "close":
        dialog = controller._dialogs.get(server)
        if dialog is not None:
            dialog.close()
        return None

    dialog = controller.show_dialog(server)
    if dialog is None:
        return f"{server} could not be opened"
    if not words:
        # A bare set fetches what the dialog holds, DS9's first rule.
        return _fetch_from(window, dialog)
    if words[0].lower() == "open":
        return None

    first = words[0].lower()
    rest = words[1:]

    if first == "name":
        if not rest:
            return "an object name is needed"
        if rest[0].lower() == "clear":
            dialog.set_name("")
            return None
        controller.resolve(" ".join(rest), dialog)
        return _fetch_from(window, dialog)

    if first in ("size", "pixels"):
        if len(rest) < 2:
            return "a width and a height are needed"
        try:
            width, height = float(rest[0]), float(rest[1])
        except ValueError:
            return f"the {first} has to be two numbers"
        if first == "pixels":
            # SkyView's alone: how big the returned image is, which is a
            # different thing from how much sky it covers.
            if not dialog.set_pixels(int(width), int(height)):
                return f"{server} has no separate image size in pixels"
            return None
        unit = rest[2] if len(rest) > 2 else "degrees"
        dialog.set_size(width, height, unit)
        return None

    if first == "survey":
        if not rest:
            return "a survey is needed"
        if not definition.surveys:
            # DS9's SAO DSS point has no `survey` rule either: that
            # endpoint serves one survey.
            return f"{server} offers no choice of survey"
        return None if dialog.set_survey(rest[0]) else f"{rest[0]} is not a survey {server} offers"

    if first == "save":
        wanted = as_bool(rest[0]) if rest else None
        if wanted is None:
            return "save takes yes or no"
        options["save"] = YES if wanted else NO
        return None

    if first == "frame":
        if not rest or rest[0].lower() not in ("new", "current"):
            return "frame takes new or current"
        options["frame"] = rest[0].lower()
        return None

    if first == "update":
        if not rest or rest[0].lower() not in ("frame", "crosshair"):
            return "update takes frame or crosshair"
        options["update"] = rest[0].lower()
        # DS9 re-centres on the frame or the crosshair and then fetches.
        centre = (
            controller.frame_center()
            if rest[0].lower() == "frame"
            else _crosshair_world(window) or controller.frame_center()
        )
        if centre is None:
            return "there is no WCS to take a position from"
        dialog.set_center(*centre)
        return _fetch_from(window, dialog)

    # Two numbers: a position in fk5, degrees or sexagesimal as DS9 takes.
    if len(words) >= 2:
        position = _fk5(words[0], words[1])
        if position is not None:
            dialog.set_center(*position)
            return _fetch_from(window, dialog)

    # Anything else is an object name, which DS9 resolves and fetches.
    controller.resolve(" ".join(words), dialog)
    return _fetch_from(window, dialog)


def _crosshair_world(window) -> tuple[float, float] | None:
    """Where the crosshair is in degrees, or None if it is nowhere useful."""
    placed = window.crosshair.position()
    handler = getattr(window.frame_manager.current_frame, "wcs_handler", None)
    if placed is None or handler is None or not getattr(handler, "is_valid", False):
        return None
    longitude, latitude = handler.pixel_to_world(placed[0], placed[1])
    return (float(longitude), float(latitude))


def _fk5(longitude: str, latitude: str) -> tuple[float, float] | None:
    """One fk5 position, in degrees or in sexagesimal, or None.

    DS9's examples give both -- `00:42:44.404 +41:16:08.78` as readily as
    `10.68 41.27` -- so both are read here.
    """
    try:
        return (float(longitude), float(latitude))
    except ValueError:
        pass
    if ":" not in longitude and ":" not in latitude:
        return None
    from astropy.coordinates import SkyCoord

    try:
        coordinate = SkyCoord(longitude, latitude, unit=("hourangle", "deg"), frame="fk5")
    except Exception:
        return None
    return (float(coordinate.ra.deg), float(coordinate.dec.deg))


def _fetch_from(window, dialog) -> str | None:
    """Fetch what a server dialog is set to, as DS9's bare set does."""
    longitude, latitude = dialog.center()
    width, height = dialog.size()
    window.image_servers.retrieve(dialog.server, longitude, latitude, width, height, dialog.survey(), dialog)
    return None


# -- what was left of DS9's list --------------------------------------------------

REMAINING_POINTS: tuple[AccessPoint, ...] = (
    AccessPoint(
        "analysis",
        get=lambda window: _analysis_text(window),
        set=lambda window, args: _analysis(window, args),
        summary="the external analysis tasks: load, clear, task, message",
    ),
    AccessPoint(
        "background",
        get=read("preferences.get", lambda _value: ""),
        set=lambda window, args: _background(window, args),
        aliases=("bg",),
        summary="the colour behind the image",
    ),
    AccessPoint(
        "data",
        get=lambda window: _data(window, []),
        query=lambda window, args: _data(window, args),
        summary="a box of data values",
    ),
    AccessPoint(
        "graph",
        get=lambda window: _graph_text(window),
        set=lambda window, args: _graph(window, args),
        summary="the cut graphs: grid, log, method, size, thickness",
    ),
    AccessPoint(
        "precision",
        get=lambda window: _precision_text(window),
        set=lambda window, args: _precision(window, args),
        summary="how many digits a coordinate is shown to",
    ),
    AccessPoint(
        "theme",
        get=read("preferences.get", lambda _value: ""),
        set=lambda window, args: _theme(window, args),
        summary="the application's theme",
    ),
    AccessPoint(
        "threads",
        get=lambda window: str(window.preferences.get("worker_threads", 4)),
        set=lambda window, args: _threads(window, args),
        summary="how many threads the threaded work uses",
    ),
    AccessPoint(
        "console",
        set=lambda window, args: _console(window, args),
        aliases=("tcl",),
        summary="the Python console, where DS9 has a TCL one",
    ),
    AccessPoint(
        "source",
        set=lambda window, args: _source(window, args),
        summary="run a script file in the console",
    ),
    AccessPoint(
        "view",
        get=lambda window: _view_text(window),
        set=lambda window, args: _view(window, args),
        summary="the panels and the layout",
    ),
    AccessPoint(
        "plot",
        get=lambda window: _plot_text(window),
        set=lambda window, args: _plot(window, args),
        summary="the plot windows",
    ),
    AccessPoint(
        "xpa",
        get=lambda window: window.xpa.information(),
        set=lambda window, args: _xpa(window, args),
        summary="XPA itself: information, connect, disconnect",
    ),
    AccessPoint(
        "savefits",
        set=lambda window, args: _savefits(window, args),
        summary="write the current frame as FITS",
    ),
    AccessPoint(
        "sfits",
        set=lambda window, args: _open_fits(window, args),
        aliases=("memf",),
        summary="load a FITS file (DS9's split and in-memory forms load the same way)",
    ),
    AccessPoint(
        "region",
        get=lambda window: _region_text(window),
        set=lambda window, args: _region(window, args),
        aliases=("regions",),
        summary="the regions: load, save, list, delete, colour, shape",
    ),
    AccessPoint(
        "rgb",
        get=lambda window: str(getattr(window.frame_manager.current_frame, "rgb_current_channel", "")),
        set=lambda window, args: _colour_frame(window, args, "rgb"),
        summary="the RGB frame and its channel",
    ),
    AccessPoint(
        "hsv",
        get=lambda window: str(getattr(window.frame_manager.current_frame, "rgb_current_channel", "")),
        set=lambda window, args: _colour_frame(window, args, "hsv"),
        summary="the HSV frame and its channel",
    ),
    AccessPoint(
        "hls",
        get=lambda window: str(getattr(window.frame_manager.current_frame, "rgb_current_channel", "")),
        set=lambda window, args: _colour_frame(window, args, "hls"),
        summary="the HLS frame and its channel",
    ),
    AccessPoint(
        "srgbcube",
        set=_load_as("rgb_cube"),
        summary="load an RGB cube (DS9's split form loads the same way)",
    ),
    AccessPoint(
        "bin",
        get=lambda window: _bin_text(window),
        set=lambda window, args: _bin(window, args),
        summary="binning a table into an image",
    ),
    AccessPoint(
        "sia",
        set=lambda window, args: _sia(window, args),
        summary="Simple Image Access: one of the image servers, or the VO registry",
    ),
    AccessPoint(
        "web",
        set=lambda window, args: _web(window, args),
        summary="open a URL in a browser",
    ),
    AccessPoint(
        "pspagesetup",
        get=lambda window: _pagesetup_text(window),
        set=lambda window, args: _pagesetup(window, args),
        summary="the page, as DS9's PostScript name for it",
    ),
)


# -- the helpers the last of the table needs ---------------------------------------


def _analysis_text(window) -> str:
    """What `xpaget ds9 analysis` answers: the tasks that are loaded."""
    tasks = window.analysis_tasks.loaded_tasks()
    return "\n".join(f"{index} {task.label}" for index, task in enumerate(tasks))


def _analysis(window, args: list[str]) -> str | None:
    """DS9's `analysis`: the external tasks, and its message dialogs.

    `analysis [<task number>] [<filename>] [task <n>|<name>] [load <file>]
    [clear] [entry <message>] [message ok|okcancel|yesno <message>] [text]`.
    """
    controller = window.analysis_tasks
    words = [str(word) for word in args]
    if not words:
        return "analysis needs a task, a file, or a command"

    first = words[0].lower()
    rest = words[1:]

    if first == "clear":
        controller.clear_commands()
        # DS9's `clear load <filename>` clears and then loads.
        if rest and rest[0].lower() == "load":
            return _analysis(window, rest)
        return None

    if first == "load":
        if not rest:
            return "a file to load is needed"
        return None if controller.load_commands(" ".join(rest)) else f"could not load {rest[0]}"

    if first == "task":
        if not rest:
            return "a task number or name is needed"
        return controller.run_named(" ".join(rest))

    if first == "text":
        controller.show_text_window()
        return None

    if first == "entry":
        # A read masquerading as a write in DS9's grammar; the answer goes
        # nowhere, so this just asks and drops it, as `xpaset` can only
        # report success or failure.
        controller._entry(" ".join(rest))
        return None

    if first == "message":
        if len(rest) < 2 or rest[0].lower() not in ("ok", "okcancel", "yesno"):
            return "message takes ok, okcancel or yesno and a message"
        controller._message(rest[0].lower(), " ".join(rest[1:]))
        return None

    if first == "filedialog":
        if not rest or rest[0].lower() not in ("open", "save"):
            return "filedialog takes open or save"
        controller._file_dialog(rest[0].lower())
        return None

    # A bare number is a task index; anything else is a file to load.
    if first.isdigit():
        return controller.run_named(first)
    return None if controller.load_commands(" ".join(words)) else f"could not load {words[0]}"


def _background(window, args: list[str]) -> str | None:
    """DS9's `bg`: what is painted behind the image."""
    if not args:
        return "a colour is needed"
    colour = str(args[0])
    window.preferences.set("background_color", colour)
    window._apply_background_color(colour)
    return None


def _data(window, args: list[str]) -> str:
    """DS9's `data`: a box of values, with or without their coordinates.

    `data <coordsys> [<skyframe>] <x> <y> <width> <height> [yes|no]`, where
    the trailing flag strips the coordinates and leaves the values.
    """
    import numpy as np

    frame = window.frame_manager.current_frame
    image = getattr(frame, "image_data", None) if frame is not None else None
    if image is None:
        return ""

    words = [str(word) for word in args]
    # The coordinate system and the sky frame are words, the geometry
    # numbers; splitting on that is simpler than knowing every system's
    # name, and it is what makes the optional sky frame optional.
    numbers: list[float] = []
    strip = True
    for word in words:
        try:
            numbers.append(float(word))
        except ValueError:
            flag = as_bool(word)
            if flag is not None and len(numbers) >= 4:
                strip = flag
    if len(numbers) < 4:
        return ""

    x, y, width, height = numbers[:4]
    # DS9 gives the lower-left corner in FITS coordinates, which count
    # from one at the centre of the first pixel.
    left = int(round(x)) - 1
    bottom = int(round(y)) - 1
    right = left + max(1, int(round(width)))
    top = bottom + max(1, int(round(height)))
    left, bottom = max(0, left), max(0, bottom)
    right = min(image.shape[1], right)
    top = min(image.shape[0], top)
    if right <= left or top <= bottom:
        return ""

    box = np.asarray(image[bottom:top, left:right], dtype=float)
    lines = []
    for row_index, row in enumerate(box):
        for column_index, value in enumerate(row):
            if strip:
                lines.append(f"{value:g}")
            else:
                lines.append(f"{left + column_index + 1} {bottom + row_index + 1} {value:g}")
    return "\n".join(lines)


def _graph_text(window) -> str:
    """Which cut graphs are shown, as DS9's `graph` answers."""
    state = window.view_state
    if state.graph_horizontal and state.graph_vertical:
        return "both"
    if state.graph_horizontal:
        return "horizontal"
    if state.graph_vertical:
        return "vertical"
    return "none"


def _graph(window, args: list[str]) -> str | None:
    """DS9's `graph`: the horizontal and vertical cut graphs.

    `[grid yes|no] [log yes|no] [method average|sum] [size <n>]
    [thickness <n>] [open|close]`, plus the `horizontal|vertical|both|none`
    our View menu offers, which DS9 spells `view graph`.
    """
    words = [str(word) for word in args]
    if not words:
        return "graph needs a setting"

    first = words[0].lower()
    rest = words[1:]
    graphs = (window.horizontal_graph, window.vertical_graph)

    wanted = {"none": "", "horizontal": "h", "vertical": "v", "both": "hv", "open": "hv", "close": ""}
    if first in wanted:
        # Through the View controller rather than straight at the widgets:
        # it keeps the view state, the menu tick and the widget in step,
        # and `xpaget ds9 graph` reads that state back.
        window.view.set_graph_visible("horizontal", "h" in wanted[first])
        window.view.set_graph_visible("vertical", "v" in wanted[first])
        return None

    if first in ("grid", "log"):
        wanted = as_bool(rest[0]) if rest else None
        if wanted is None:
            return f"{first} takes yes or no"
        for graph in graphs:
            getattr(graph, f"set_{first}")(wanted)
        return None

    if first == "method":
        if not rest or rest[0].lower() not in ("average", "sum"):
            return "method takes average or sum"
        for graph in graphs:
            graph.set_method(rest[0].lower())
        return None

    if first in ("size", "thickness"):
        try:
            value = int(float(rest[0]))
        except (IndexError, ValueError):
            return f"{first} takes a number"
        for graph in graphs:
            getattr(graph, f"set_{first}")(value)
        return None

    if first in ("font", "fontsize", "fontweight", "fontslant"):
        # The cut graphs draw their axes with the widget's own font, which
        # has no separate setting; saying so beats reporting success.
        return "the cut graphs have no separate font setting"

    return f"graph does not take {first}"


def _precision_text(window) -> str:
    """DS9's `precision`: the digit counts, in its own order."""
    store = window.preferences
    return " ".join(
        str(store.get(f"precision_{name}", default))
        for name, default in (
            ("linear", 8),
            ("degrees", 8),
            ("hms", 3),
            ("dms", 2),
            ("arcmin", 3),
            ("arcsec", 3),
        )
    )


def _precision(window, args: list[str]) -> str | None:
    """DS9's `precision`: how many digits a coordinate is written to.

    DS9 takes its six numbers positionally -- linear, degrees, hms, dms,
    arcmin, arcsec -- and a `<name> <value>` pair is accepted too, which
    is a good deal easier to write by hand.
    """
    order = ("linear", "degrees", "hms", "dms", "arcmin", "arcsec")
    words = [str(word) for word in args]
    if not words:
        return "precision needs a number"

    if words[0].lower() in order:
        if len(words) < 2:
            return f"precision {words[0]} needs a number"
        try:
            value = int(float(words[1]))
        except ValueError:
            return f"{words[1]} is not a number of digits"
        window.preferences.set(f"precision_{words[0].lower()}", value)
        return None

    try:
        values = [int(float(word)) for word in words]
    except ValueError:
        return "precision takes numbers, or a name and a number"
    for name, value in zip(order, values, strict=False):
        window.preferences.set(f"precision_{name}", value)
    return None


def _theme(window, args: list[str]) -> str | None:
    """The application's theme, which DS9 spells with a capital."""
    if not args:
        return "a theme is needed"
    name = str(args[0]).capitalize()
    from ...ui.controllers.edit import THEMES

    if name not in THEMES:
        return f"{args[0]} is not a theme: {', '.join(THEMES)}"
    window.preferences.set("theme", name)
    window.edit.apply_theme(name)
    return None


def _threads(window, args: list[str]) -> str | None:
    """How many threads the threaded work may use."""
    if not args:
        return "a number of threads is needed"
    try:
        count = int(float(str(args[0])))
    except ValueError:
        return f"{args[0]} is not a number of threads"
    if count < 1:
        return "at least one thread is needed"
    window.preferences.set("worker_threads", count)
    return None


def _console(window, args: list[str]) -> str | None:
    """DS9's `console` and `tcl`, in the language this is written in.

    DS9 runs Tcl, being written in it; this runs Python for the same
    reason. A bare call opens the console and anything else is a line to
    run in it -- `xpaset -p ds9 tcl "print(1)"` arrives here as the line
    alone, its own name having been stripped by the dispatcher.

    `source` is a point of its own rather than an alias of this: an alias
    could not tell which name it had been called by, and running a file
    is not the same as running a line.
    """
    console = window.file.show_console()
    if console is None:
        return "the console could not be opened"
    words = [str(word) for word in args]
    if not words:
        return None
    if words[0].lower() in ("open", "close"):
        if words[0].lower() == "close":
            console.close()
        return None
    console.run(" ".join(words))
    return None


def _source(window, args: list[str]) -> str | None:
    """DS9's `source`: run a script file. Its Tcl, our Python."""
    if not args:
        return "a script to run is needed"
    from pathlib import Path

    path = " ".join(str(word) for word in args)
    if not Path(path).is_file():
        return f"there is no script at {path}"
    console = window.file.show_console()
    if console is None:
        return "the console could not be opened"
    console.run_script(path)
    return None


#: DS9's `view` names for our info-panel fields, where the two differ.
_VIEW_FIELDS = {"units": "bunit", "keyword": "keyword"}

#: What `view <system>` covers, DS9's alternate WCS letters included.
_VIEW_SYSTEMS = ("wcs", "physical", "image", "detector", "amplifier", "frame")


def _view_text(window) -> str:
    """Which panels are shown, as `xpaget ds9 view` answers."""
    from ...ui.layout.view_state import PANEL_NAMES

    state = window.view_state
    parts = [f"layout {state.layout.value}"]
    parts += [f"{name} {on_off(getattr(state, name))}" for name in PANEL_NAMES]
    return "\n".join(parts)


def _view(window, args: list[str]) -> str | None:
    """DS9's `view`: the panels, the layout and the information fields."""
    from ...ui.layout.view_state import INFO_FIELDS, PANEL_NAMES, ViewLayout

    words = [str(word) for word in args]
    if not words:
        return "view needs a setting"

    first = words[0].lower()
    rest = words[1:]

    if first == "layout":
        if not rest:
            return "layout needs a name"
        try:
            window.view.set_layout(ViewLayout(rest[0].lower()))
        except ValueError:
            return f"{rest[0]} is not a layout"
        return None

    if first == "keyvalue":
        window.view.info_panel.keyword_entry.setText(" ".join(rest))
        window.view.refresh_info()
        return None

    if first == "graph":
        # `view graph horizontal|vertical yes|no`.
        if not rest or rest[0].lower() not in ("horizontal", "vertical"):
            return "view graph takes horizontal or vertical"
        wanted = as_bool(rest[1]) if len(rest) > 1 else True
        if wanted is None:
            return "view graph takes yes or no"
        window.view.set_graph_visible(rest[0].lower(), wanted)
        return None

    if first in ("rgb", "hls", "hsv"):
        # `view rgb red yes|no`: which channel of a colour frame is drawn,
        # which is the colour controller's business rather than the View
        # menu's.
        if not rest:
            return f"view {first} needs a channel"
        wanted = as_bool(rest[1]) if len(rest) > 1 else True
        if wanted is None:
            return f"view {first} takes yes or no"
        return _channel_view(window, rest[0].lower(), wanted)

    wanted = as_bool(rest[0]) if rest else True
    if wanted is None:
        return f"view {first} takes yes or no"

    name = _VIEW_FIELDS.get(first, first)
    if name in PANEL_NAMES:
        window.view.set_panel(name, wanted)
        return None
    if name in INFO_FIELDS:
        window.view.set_info_field(name, wanted)
        return None
    # `view wcsa` ... `view wcsz`, which our fields spell `wcs_a`.
    if first.startswith("wcs") and len(first) == 4:
        window.view.set_info_field(f"wcs_{first[3]}", wanted)
        return None
    if first in _VIEW_SYSTEMS:
        window.view.set_info_field(first, wanted)
        return None
    return f"view does not know {first}"


def _channel_view(window, channel: str, shown: bool) -> str | None:
    """Show or hide one channel of an RGB, HSV or HLS frame."""
    return window.frame_controller.set_channel_visible(channel, shown)


def _plot_text(window) -> str:
    """What `xpaget ds9 plot` answers: the plots open, current last."""
    plots = window.analysis.plots()
    current = window.analysis.current_plot()
    return "\n".join(
        f"{index + 1} {plot.state.title or 'Plot'}{' *' if plot is current else ''}"
        for index, plot in enumerate(plots)
    )


def _plot(window, args: list[str]) -> str | None:
    """DS9's `plot`: the plot windows.

    The subset that is about plots rather than about Tcl channels:
    `[line|bar]`, `[line|bar <filename> [<format>]]`, `load <file>
    <format>`, `save <file>`, `current <ref>`, `stats yes|no`, `list
    yes|no`, `close`.
    """
    from ...analysis.plot import DataFormat, PlotDataError, PlotStyle

    words = [str(word) for word in args]
    controller = window.analysis
    formats = {value.value for value in DataFormat}

    if not words:
        controller.open_plot_tool()
        return None

    first = words[0].lower()
    rest = words[1:]

    if first in ("line", "bar", "scatter"):
        style = PlotStyle(first)
        # `plot line <filename> [<format>]`: a file makes a plot with
        # something in it, no file an empty one.
        paths = [word for word in rest if word.lower() not in formats]
        if not paths:
            controller.open_plot_tool(style)
            return None
        plot = controller.open_plot_tool(style)
        chosen = next((word for word in rest if word.lower() in formats), DataFormat.XY.value)
        return _plot_load(plot, paths[0], chosen)

    plot = controller.current_plot()
    if plot is None:
        return "no plot is open"

    if first == "gui":
        plot.raise_()
        plot.activateWindow()
        return None
    if first == "close":
        plot.close()
        return None
    if first == "load":
        if not rest:
            return "a file to load is needed"
        chosen = rest[1] if len(rest) > 1 and rest[1].lower() in formats else DataFormat.XY.value
        return _plot_load(plot, rest[0], chosen)
    if first == "save":
        if not rest:
            return "a file to save to is needed"
        try:
            plot.state.save(rest[0])
        except (OSError, PlotDataError) as exc:
            return str(exc)
        return None
    if first == "current":
        if not rest:
            return "a plot to make current is needed"
        if rest[0].lower() in ("graph", "dataset"):
            # One graph per window here, so `current graph` is a no-op;
            # `current dataset <n>` picks which curve the rest acts on.
            if rest[0].lower() == "dataset" and len(rest) > 1 and rest[1].isdigit():
                plot.select_dataset(int(rest[1]) - 1)
            return None
        return None if controller.set_current_plot(rest[0]) else f"no plot called {rest[0]}"
    if first in ("stats", "list"):
        wanted = as_bool(rest[0]) if rest else True
        if wanted is None:
            return f"plot {first} takes yes or no"
        if wanted:
            plot.show_statistics() if first == "stats" else plot.list_data()
        return None
    if first == "duplicate":
        plot.duplicate_dataset()
        return None
    if first == "delete":
        if rest and rest[0].lower() == "dataset":
            plot.delete_dataset()
        return None
    if first == "print":
        plot.print_plot()
        return None
    if first == "layout":
        # One graph per plot window, so DS9's grid/row/column/strip
        # layouts have nothing to arrange.
        return "this plot holds one graph, so it has no layout"
    return f"plot does not take {first}"


def _plot_load(plot, path: str, data_format: str) -> str | None:
    """Read a column file into a plot window."""
    from pathlib import Path

    from ...analysis.plot import PlotDataError

    try:
        text = Path(path).read_text()
    except OSError as exc:
        return str(exc)
    try:
        plot.add_dataset_from(text, data_format, name=Path(path).stem)
    except PlotDataError as exc:
        return str(exc)
    return None


def _xpa(window, args: list[str]) -> str | None:
    """DS9's `xpa`: `connect`, `disconnect` and `info`."""
    words = [str(word).lower() for word in args]
    if not words or words[0] == "info":
        window.xpa.show_information()
        return None
    if words[0] == "connect":
        return None if window.xpa.start() else "XPA could not be started"
    if words[0] == "disconnect":
        window.xpa.stop()
        return None
    return f"xpa does not take {words[0]}"


def _savefits(window, args: list[str]) -> str | None:
    """Write the current frame to a FITS file, DS9's `savefits`."""
    if not args:
        return "a file to write is needed"
    return window.file.save_fits_to(str(args[0]))


def _region_text(window) -> str:
    """What `xpaget ds9 regions` answers: the regions, as DS9 writes them."""
    return window.region.listing()


def _region(window, args: list[str]) -> str | None:
    """DS9's `region`, the useful part of a very long grammar.

    `[<filename>] [load [all] <file>] [save [select] <file>] [list]
    [delete [select]] [select all|none|invert] [show yes|no] [showtext
    yes|no] [shape <shape>] [color <color>] [width <n>] [format <format>]
    [move front|back] [centroid] [group new] [template <file>]`. The rest
    -- the per-group commands, the marker command language -- is left to
    the Region menu, where it has a dialog of its own.
    """
    from ...regions.region_formats import RegionFormat

    controller = window.region
    words = [str(word) for word in args]
    if not words:
        return "region needs a file or a command"

    first = words[0].lower()
    rest = words[1:]

    if first == "load":
        # `load all <file>` loads into every frame; ours loads into the
        # current one and says so rather than pretending.
        append = bool(rest) and rest[0].lower() == "all"
        paths = rest[1:] if append else rest
        if not paths:
            return "a region file is needed"
        return controller.load_file(paths[0], append=False)

    if first == "save":
        selected = bool(rest) and rest[0].lower() == "select"
        paths = rest[1:] if selected else rest
        if not paths:
            return "a file to save to is needed"
        return controller.save_file(paths[0], selected_only=selected)

    if first == "list":
        selected = bool(rest) and rest[0].lower() == "select"
        controller._show_listing(
            controller.selection() if selected else controller._regions(),
            "Selected Regions" if selected else "Regions",
        )
        return None

    if first == "delete":
        if rest and rest[0].lower() == "select":
            controller.delete_selection()
            return None
        if rest and rest[0].lower() == "load":
            # DS9's `delete load <file>`: clear, then load.
            controller.clear_regions()
            return controller.load_file(rest[1]) if len(rest) > 1 else "a region file is needed"
        controller.clear_regions()
        return None

    if first == "select":
        which = rest[0].lower() if rest else "all"
        if which in ("all", "none", "invert"):
            getattr(controller, f"select_{which}")()
            return None
        if which in ("front", "back"):
            getattr(controller, f"bring_{which}" if which == "front" else "send_back")()
            return None
        return "select takes all, none, invert, front or back"

    if first == "move":
        if not rest or rest[0].lower() not in ("front", "back"):
            return "move takes front or back"
        getattr(controller, f"move_{rest[0].lower()}")()
        return None

    if first in ("show", "showtext"):
        wanted = as_bool(rest[0]) if rest else None
        if wanted is None:
            return f"{first} takes yes or no"
        if first == "show":
            controller.set_show_regions(wanted)
        else:
            controller.set_show_text(wanted)
        return None

    if first == "shape":
        if not rest:
            return "a shape is needed"
        controller.set_shape(rest[0].lower())
        return None

    if first == "color":
        if not rest:
            return "a colour is needed"
        controller.set_color(rest[0].lower())
        return None

    if first == "width":
        try:
            controller.set_width(int(float(rest[0])))
        except (IndexError, ValueError):
            return "width takes a number"
        return None

    if first == "fontsize":
        try:
            controller.set_font_size(int(float(rest[0])))
        except (IndexError, ValueError):
            return "fontsize takes a number"
        return None

    if first == "font":
        if not rest:
            return "a font is needed"
        controller.set_font_family(rest[0].lower())
        return None

    if first == "format":
        if not rest:
            return "a format is needed"
        try:
            window.preferences.set("region_format", RegionFormat(rest[0].lower()).value)
        except ValueError:
            return f"{rest[0]} is not a region format"
        return None

    if first in ("system", "sky", "skyformat"):
        # The coordinate system a listing is written in is the window's,
        # which the WCS menu owns; pointing at it beats a silent no-op.
        return f"region {first} follows the WCS menu, which sets it for the whole window"

    if first == "centroid":
        if rest and rest[0].lower() == "auto":
            wanted = as_bool(rest[1]) if len(rest) > 1 else True
            if wanted is None:
                return "centroid auto takes yes or no"
            controller.set_auto_centroid(wanted)
            return None
        controller.centroid()
        return None

    if first == "group" and rest and rest[-1].lower() == "new":
        controller.new_group()
        return None

    if first == "template":
        if not rest:
            return "a template file is needed"
        controller.load_template(rest[0])
        return None

    if first == "savetemplate":
        return "savetemplate asks where to write; use the Region menu"

    if first == "composite":
        controller.create_composite()
        return None

    if first == "dissolve":
        controller.dissolve_composite()
        return None

    if first == "epsilon":
        try:
            window.preferences.set("region_epsilon", int(float(rest[0])))
        except (IndexError, ValueError):
            return "epsilon takes a number"
        return None

    if first == "command":
        # DS9's marker command language: a region in the same syntax a
        # region file uses, which the parser already reads.
        return _region_command(window, " ".join(rest))

    # A bare word is a file to load, which is DS9's first form.
    return controller.load_file(words[0])


def _region_command(window, text: str) -> str | None:
    """Add regions written in DS9's own syntax, `region command ...`."""
    from ...regions.region_parser import RegionParser

    if not text.strip():
        return "a region to add is needed"
    try:
        regions = RegionParser().parse_string(_as_region_file(text))
    except Exception as exc:
        return f"could not read that region: {exc}"
    if not regions:
        return f"nothing in {text!r} was a region"

    frame = window.frame_manager.current_frame
    if frame is None:
        return "no frame to add a region to"
    with window.undo.regions("Add Region"):
        frame.regions = [*frame.regions, *regions]
    window.region.show_frame_regions(frame)
    return None


#: The shapes DS9's marker command language names, so a command written
#: in it can be told from a region file's own syntax.
_MARKER_SHAPES = frozenset(
    {
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
    }
)


def _as_region_file(text: str) -> str:
    """DS9's marker command language, rewritten as a region file.

    `region command` is given a region in DS9's marker syntax, which puts
    its arguments after the shape with spaces -- `circle 100 100 20` --
    and separates several with semicolons. A region file parenthesises and
    commas them and puts each on its own line. Both are accepted here,
    since a caller reaching for `region command` is as likely to paste a
    line out of a region file.
    """
    lines = []
    for statement in text.replace("\n", ";").split(";"):
        line = statement.strip()
        if not line:
            continue
        words = line.split()
        if "(" in line or words[0].lower() not in _MARKER_SHAPES:
            lines.append(line)
            continue
        # `circle 100 100 20 # color=red` -> `circle(100,100,20) # color=red`
        body, marker, trailing = line.partition("#")
        words = body.split()
        shape, arguments = words[0], words[1:]
        rewritten = f"{shape}({','.join(arguments)})"
        lines.append(f"{rewritten} {marker}{trailing}" if marker else rewritten)
    return "\n".join(lines)


def _colour_frame(window, args: list[str], kind: str) -> str | None:
    """DS9's `rgb`, `hsv` and `hls`: make such a frame, and pick a channel.

    `[] [<channel>] [channel [<channel>]] [view <channel> [yes|no]]
    [system <coordsys>] [lock <what> [yes|no]] [open|close]`.
    """
    words = [str(word) for word in args]
    controller = window.frame_controller

    if not words or words[0].lower() == "open":
        controller.new_frame_of_type(kind)
        return None

    first = words[0].lower()
    rest = words[1:]

    if first == "close":
        controller.delete_current()
        return None

    frame = window.frame_manager.current_frame
    if frame is None or frame.frame_type != kind:
        found = "no frame" if frame is None else frame.frame_type
        return f"the current frame is {found}, not {kind}"
    channels = frame.rgb_channels

    if first == "channel":
        if not rest:
            return None
        if rest[0].lower() not in channels:
            return f"{rest[0]} is not a channel: {', '.join(channels)}"
        return controller.set_channel(rest[0].lower())
        return None

    if first == "view":
        if not rest:
            return "view needs a channel"
        wanted = as_bool(rest[1]) if len(rest) > 1 else True
        if wanted is None:
            return "view takes yes or no"
        return _channel_view(window, rest[0].lower(), wanted)

    if first == "system":
        if not rest:
            return "system needs a coordinate system"
        return _lock(window, ["wcs", rest[0]])

    if first == "lock":
        return _lock(window, rest)

    if first in channels:
        return controller.set_channel(first)
    return f"{kind} does not take {first}"


def _bin_text(window) -> str:
    """How a table is being binned, as `xpaget ds9 bin` answers."""
    settings = window.bin.settings
    columns = window.bin.columns
    return (
        f"function {settings.function.value} factor {settings.factor:g} "
        f"buffersize {settings.buffer_size} depth {settings.depth} "
        f"cols {' '.join(columns.columns)}"
    )


def _bin(window, args: list[str]) -> str | None:
    """DS9's `bin`: turning a FITS table into an image.

    `[about <x> <y>|center] [buffersize <n>] [cols <x> <y>] [colsz <x> <y>
    <z>] [factor <n>] [depth <n>] [filter <string>|clear] [function
    average|sum] [in] [out] [to fit] [open|close]`.
    """
    from dataclasses import replace

    controller = window.bin
    words = [str(word) for word in args]
    if not words:
        return "bin needs a setting"

    first = words[0].lower()
    rest = words[1:]

    if first in ("in", "out"):
        getattr(controller, f"bin_{first}")()
        return None
    if first == "to" and rest and rest[0].lower() == "fit":
        controller.bin_fit()
        return None
    if first == "fit":
        controller.bin_fit()
        return None
    if first == "open":
        controller.show_dialog()
        return None
    if first == "close":
        return None

    if first == "function":
        if not rest:
            return "function takes average or sum"
        controller.set_function(rest[0].lower())
        return None

    if first == "factor":
        try:
            controller.set_factor(float(rest[0]))
        except (IndexError, ValueError):
            return "factor takes a number"
        return None

    if first == "buffersize":
        try:
            controller.set_buffer_size(int(float(rest[0])))
        except (IndexError, ValueError):
            return "buffersize takes a number"
        return None

    if first == "depth":
        try:
            controller.update(depth=max(1, int(float(rest[0]))))
        except (IndexError, ValueError):
            return "depth takes a number"
        return None

    if first == "filter":
        if rest and rest[0].lower() == "clear":
            controller.update(filter="")
            return None
        controller.update(filter=" ".join(rest))
        return None

    if first in ("cols", "colsz"):
        wanted = 3 if first == "colsz" else 2
        if len(rest) < wanted:
            return f"{first} takes {wanted} column names"
        window.bin_spec = replace(window.bin_spec, columns=tuple(rest[:wanted]))
        controller.rebin()
        return None

    if first == "about":
        # DS9 bins about a point; ours bins about the table's own extent,
        # which is what `about center` asks for anyway.
        if rest and rest[0].lower() == "center":
            return None
        return "binning about a chosen point is not implemented; `bin about center` is the default"

    if first == "lock":
        return _lock(window, ["bin", *rest])

    if first == "match":
        return _match(window, ["bin"])

    return f"bin does not take {first}"


#: DS9's SIA service names, mapped to the image server that serves them
#: here. DS9 lists ten; these are the ones we have a server for, and the
#: rest are in the VO registry the bare point opens.
_SIA_SERVICES = {"2mass": "twomass", "sdss": "sdss", "skyview": "skyview"}


def _sia(window, args: list[str]) -> str | None:
    """DS9's `sia`: Simple Image Access.

    `sia [<service>]` opens the server for one of DS9's named services
    where we have one, and the VO registry otherwise -- which is where
    the services we do not have a dedicated dialog for are reached. The
    position, size and retrieve rules are the image-server ones, since
    for the services we do have, that dialog is the search.
    """
    words = [str(word) for word in args]
    if not words or words[0].lower() in ("open", "update"):
        window.vo.show_registry()
        return None

    first = words[0].lower()
    if first in _SIA_SERVICES:
        return _image_server(window, _SIA_SERVICES[first], words[1:])

    # The rules that act on "the last search created", which for us is
    # whichever server dialog is open.
    open_servers = [name for name in _SIA_SERVICES.values() if name in window.image_servers._dialogs]
    if not open_servers:
        return f"no SIA search is open; name one of {', '.join(sorted(_SIA_SERVICES))} first"
    server = open_servers[-1]

    if first == "radius":
        if len(words) < 2:
            return "a radius is needed"
        # A radius is half a side, so a search of radius r covers 2r.
        try:
            radius = float(words[1])
        except ValueError:
            return "the radius has to be a number"
        unit = words[2] if len(words) > 2 else "degrees"
        return _image_server(window, server, ["size", str(radius * 2), str(radius * 2), unit])
    if first in ("name", "coordinate", "close", "save", "retrieve"):
        rule = {"coordinate": "", "retrieve": ""}.get(first, first)
        return _image_server(window, server, ([rule] if rule else []) + words[1:])
    if first in ("cancel", "clear", "print", "export", "current", "crosshair", "sky", "skyformat", "system"):
        return f"sia {first} belongs to DS9's own search window, which we reach through the servers"
    return f"we have no SIA service called {first}"


def _web(window, args: list[str]) -> str | None:
    """DS9's `web`: show a URL. Ours opens the system browser."""
    words = [str(word) for word in args]
    if not words:
        window.analysis.open_web_browser()
        return None
    if words[0].lower() == "new" and len(words) > 2:
        # `web new <name> <url>`: DS9 names its internal browser windows;
        # the system browser has no names, so the URL is what matters.
        return _url(window, words[2:])
    if words[0].lower() in ("clear", "close", "click"):
        return "the system browser has no windows for us to drive"
    return _url(window, words)


#: Every point this table knows, in the order the groups were written.
ALL_POINTS: tuple[AccessPoint, ...] = (
    *DISPLAY_POINTS,
    *FRAME_POINTS,
    *FILE_POINTS,
    *TOOL_POINTS,
    *TOOL_WINDOW_POINTS,
    *APP_POINTS,
    *IMAGE_SERVER_POINTS,
    *REMAINING_POINTS,
)


def by_name() -> dict[str, AccessPoint]:
    """Every name, alias included, to the point that answers to it."""
    found: dict[str, AccessPoint] = {}
    for point in ALL_POINTS:
        for name in point.names:
            found[name.lower()] = point
    return found


def _crosshair(window, args: list[str]) -> str | None:
    """`crosshair <x> <y>`, or `crosshair lock <system>|none`."""
    words = [str(word) for word in args]
    if words and words[0].lower() == "lock":
        system = words[1].lower() if len(words) > 1 else "wcs"
        window.crosshair.set_locked(system != "none", system)
        return None
    if words and words[0].lower() == "match":
        window.crosshair.match(words[1].lower() if len(words) > 1 else "wcs")
        return None
    return _cursor(window, words)


def _samp_text(window) -> str:
    """What `xpaget samp` answers: whether we are connected, and to what."""
    return window.samp.information()


def _samp(window, args: list[str]) -> str | None:
    """`samp connect|disconnect|image|table|hub start|stop`."""
    words = [str(word).lower() for word in args]
    if not words:
        return "connect, disconnect, image, table or hub is needed"

    controller = window.samp
    if words[0] == "connect":
        return None if controller.connect_hub() else "could not connect to a SAMP hub"
    if words[0] == "disconnect":
        controller.disconnect_hub()
        return None
    if words[0] in ("image", "table"):
        # `samp image broadcast` and `samp image <client>`, as DS9 has it.
        recipient = None
        if len(words) > 1 and words[1] != "broadcast":
            recipient = str(args[1])
        return None if controller.broadcast(words[0], recipient) else f"the {words[0]} was not sent"
    if words[0] == "hub":
        what = words[1] if len(words) > 1 else "start"
        if what == "start":
            return None if controller.start_hub() else "the hub could not be started"
        if what == "stop":
            controller.stop_hub()
            return None
        if what in ("web", "webprofile"):
            wanted = as_bool(words[2]) if len(words) > 2 else True
            controller.web_profile = bool(wanted)
            return None
        return f"{what} is not a hub command"
    return f"{args[0]} is not a SAMP command"


def _iis_text(window) -> str:
    """`iis filename` answers the file an IIS frame is showing."""
    return window.iis.filename()


def _iis(window, args: list[str]) -> str | None:
    """`iis filename <file> [#]`, `iis start|stop`."""
    words = [str(word) for word in args]
    if not words:
        return "filename, start or stop is needed"
    first = words[0].lower()

    if first == "filename":
        if len(words) < 2:
            return "a filename is needed"
        frame = int(float(words[2])) if len(words) > 2 else None
        window.iis.set_filename(words[1], frame)
        return None
    if first == "start":
        port = int(float(words[1])) if len(words) > 1 else 5137
        return None if window.iis.start(port) else "the IIS server could not be started"
    if first == "stop":
        window.iis.stop()
        return None
    return f"{words[0]} is not an IIS command"


def examine(window, args: list[str]) -> str:
    """DS9's interactive examine: wait for a click, then answer.

    `iexam [button|key|any] coordinate <sys> [<sky>] [<format>]`,
    `iexam [...] data [w] [h]`, or a macro string.
    """
    words = [str(word) for word in args]
    # DS9 takes an event kind first -- button, key or any. Ours is always
    # a button, since a key event needs the keyboard grab DS9's cursor
    # mode takes; the word is accepted and ignored.
    if words and words[0].lower() in ("button", "key", "any"):
        words = words[1:]

    if not words:
        return window.iis.examine("coordinate", "image")

    first = words[0].lower()
    if first == "coordinate":
        rest = [word.lower() for word in words[1:]]
        system = rest[0] if rest else "image"
        sky = "fk5"
        sky_format = "degrees"
        if system not in ("image", "physical", "amplifier", "detector", "wcs"):
            # `iexam coordinate fk5` is DS9's shorthand for a WCS frame.
            sky = system
            system = "wcs"
            rest = rest[1:] if rest else []
        else:
            rest = rest[1:] if rest else []
        for word in rest:
            if word in ("degrees", "sexagesimal"):
                sky_format = word
            else:
                sky = word
        return window.iis.examine("coordinate", system, sky, sky_format)

    if first == "data":
        width = int(float(words[1])) if len(words) > 1 else 1
        height = int(float(words[2])) if len(words) > 2 else width
        return window.iis.examine("data", width=width, height=height)

    return window.iis.examine(macro=" ".join(str(word) for word in args))


def _shm_text(window) -> str:
    """What `xpaget shm` answers: which kinds of segment can be read."""
    from ...io import shared_memory

    kinds = shared_memory.available()
    return "\n".join(f"{name} {on_off(value)}" for name, value in sorted(kinds.items()))


def _shm(window, args: list[str]) -> str | None:
    """`shm [key|shmid|name] <id> [fits|<array spec>]`.

    DS9's grammar with one addition: `name`, for a POSIX segment, since
    that is the kind Python can always read. See `io/shared_memory.py`.
    """
    from ...io import shared_memory

    words = [str(word) for word in args]
    if not words:
        return "a segment is needed"

    # DS9 puts the payload kind first -- `shm fits key 102` -- and allows
    # it to be left out.
    payload = "fits"
    if words[0].lower() in ("fits", "array"):
        payload = words[0].lower()
        words = words[1:]

    kind = "name"
    if words and words[0].lower() in shared_memory.KINDS:
        kind = words[0].lower()
        words = words[1:]
    if not words:
        return "a segment is needed"

    identifier = words[0]
    rest = words[1:]

    try:
        if payload == "array":
            if not rest:
                return "a raw array needs its dimensions"
            data = shared_memory.read_array(identifier, rest[0], kind)
        else:
            data = shared_memory.read_fits(identifier, kind)
    except shared_memory.SharedMemoryError as exc:
        return str(exc)
    except Exception as exc:
        return f"cannot read {identifier}: {exc}"

    name = rest[-1] if payload == "fits" and rest else f"shm:{identifier}"
    window.display.load_array(data, name=str(name))
    return None
