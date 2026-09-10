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
        aliases: Other names DS9 registers for the same point.
        summary: One line, for `xpaget ds9 xpa` to list.
    """

    name: str
    get: Callable[[Any], str] | None = None
    set: Callable[[Any, list[str]], str | None] | None = None
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


def _load_as(kind: str):
    """A point that loads a file through one `Open as` entry."""

    def apply(window, args: list[str]) -> str | None:
        if not args:
            return "a filename is needed"
        window.file.open_as(kind, str(args[-1]))
        return None

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
    AccessPoint("mecube", set=_load_as("mecube"), summary="load a multi-extension cube"),
    AccessPoint("multiframe", set=_load_as("meframes"), summary="load extensions as frames"),
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
    AccessPoint("vo", set=_show_window("vo.show_dialog"), summary="the virtual observatory tool"),
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
    window.file.open_url(str(args[0]))
    return None


def _about(window) -> str:
    """What DS9's `about` answers with: the credits."""
    from ... import __version__

    return f"NCRADS9 {__version__}\nA PyQt6 reimplementation of SAOImageDS9"


def _version(window) -> str:
    """The version, as DS9's `version` answers."""
    from ... import __version__

    return f"ncrads9 {__version__}"


#: Every point this table knows, in the order the groups were written.
ALL_POINTS: tuple[AccessPoint, ...] = (
    *DISPLAY_POINTS,
    *FRAME_POINTS,
    *FILE_POINTS,
    *TOOL_POINTS,
    *TOOL_WINDOW_POINTS,
    *APP_POINTS,
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
