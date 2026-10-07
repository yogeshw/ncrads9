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

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

#: The sky frames DS9 names, for the reads that take one.
SKY_FRAMES = frozenset({"fk4", "fk5", "icrs", "galactic", "ecliptic", "b1950", "j2000"})

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


# -- reads that take a key -----------------------------------------------------------
#
# A good third of DS9's reads name the one setting they want -- `xpaget ds9
# minmax interval`, `xpaget ds9 tile grid gap`, `xpaget ds9 lock crop`.
# Without a `query` the table answered every one of those with the point's
# bare read: the whole listing, or worse a single unrelated value, which a
# script cannot tell from a right answer.


def _keyed(
    table: Callable[[Any], dict[str, str]], bare: str | None = None
) -> Callable[[Any, list[str]], str]:
    """A read that answers one key out of a table of settings.

    Args:
        table: Called with the window; maps each key DS9 names -- `grid
            gap`, several words where DS9 has several -- to its answer.
        bare: The key a read with no arguments answers. None answers with
            every key and value, one per line.
    """

    def ask(window, args: list[str]) -> str:
        values = table(window)
        words = [str(word).lower() for word in args]
        if not words:
            if bare is not None:
                return values[bare]
            return "\n".join(f"{key} {value}" for key, value in values.items() if key)
        for count in range(len(words), 0, -1):
            key = " ".join(words[:count])
            if key in values:
                return values[key]
        # Raised rather than returned: the dispatcher turns it into an
        # error reply, and an error is what an unknown key deserves.
        raise ValueError(f"there is no {' '.join(words)} to read")

    return ask


def _minmax_table(window) -> dict[str, str]:
    settings = window.scale.settings
    return {
        "mode": str(getattr(settings.method, "value", settings.method)),
        "interval": str(settings.sample_increment),
    }


def _zscale_table(window) -> dict[str, str]:
    settings = window.scale.settings
    return {
        "contrast": f"{settings.contrast:g}",
        "sample": str(settings.samples),
        "line": str(settings.samples_per_line),
    }


def _preserve_table(window) -> dict[str, str]:
    table = {name: on_off(value) for name, value in sorted(window._preserve.items())}
    # DS9 still parses `preserve scale`, and always answers no.
    table.setdefault("scale", NO)
    return table


def _pagesetup_table(window) -> dict[str, str]:
    page = window.file.print_settings.page
    return {"orient": page.orientation.value, "scale": f"{page.scale:g}", "size": page.paper_size.value}


#: DS9's lock and match names, where ours differ.
_LOCK_NAMES = {"scalelimits": "scale_limits", "axes": "axes_order", "axis": "axes_order"}


def _lock_table(window) -> dict[str, str]:
    table = dict(getattr(window, "_frame_lock_scope", {}))
    flags = getattr(window, "_frame_lock_flags", {})
    table.update({name: on_off(value) for name, value in flags.items()})
    for theirs, ours in _LOCK_NAMES.items():
        if ours in flags:
            table[theirs] = on_off(flags[ours])
    return table


def _blink_table(window, mode: str) -> dict[str, str]:
    milliseconds = window._blink_timer.interval() if mode == "blink" else window._fade_interval_ms
    return {"": on_off(window._frame_display_mode == mode), "interval": f"{milliseconds / 1000:g}"}


def _tile_table(window) -> dict[str, str]:
    settings = window.frame_controller.tile_settings
    return {
        "": on_off(window._frame_display_mode == "tile"),
        "mode": str(window._tile_arrangement_mode),
        "grid mode": "manual" if settings.manual else "automatic",
        "grid direction": str(settings.direction),
        "grid layout": f"{settings.columns} {settings.rows}",
        "grid gap": str(settings.gap),
    }


def _view_table(window) -> dict[str, str]:
    from ...ui.layout.view_state import INFO_FIELDS, PANEL_NAMES

    state = window.view_state
    table = {"layout": state.layout.value}
    table.update({name: on_off(getattr(state, name)) for name in PANEL_NAMES})
    table["graph horizontal"] = on_off(state.graph_horizontal)
    table["graph vertical"] = on_off(state.graph_vertical)
    for name in INFO_FIELDS:
        table[name] = on_off(state.info_fields.get(name, False))
    table["units"] = table["bunit"]
    for suffix in "abcdefghijklmnopqrstuvwxyz":
        table[f"wcs{suffix}"] = table[f"wcs_{suffix}"]
    entry = getattr(getattr(window.view, "info_panel", None), "keyword_entry", None)
    table["keyvalue"] = entry.text() if entry is not None else ""
    frame = window.frame_manager.current_frame
    shown = getattr(frame, "rgb_view", None) if frame is not None else None
    if shown and getattr(frame, "rgb_channels", None):
        for name, key in _channel_keys(window, frame).items():
            table[f"{frame.frame_type} {name}"] = on_off(shown.get(key, True))
    return table


# -- (a) display -------------------------------------------------------------------
#
# DS9's own grouping, as TODO lists it: what the data looks like on the
# screen. Each point is the same thing the menu does.

DISPLAY_POINTS: tuple[AccessPoint, ...] = (
    AccessPoint(
        "zscale",
        get=lambda window: _zscale_text(window),
        query=_keyed(_zscale_table),
        set=lambda window, args: _zscale(window, args),
        summary="the zscale parameters: contrast, sample, line",
    ),
    AccessPoint(
        "minmax",
        get=lambda window: _minmax_table(window)["mode"],
        query=_keyed(_minmax_table, bare="mode"),
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
        query=_keyed(
            lambda window: {
                "": str(getattr(window.frame_manager.current_frame, "block_factor", 1)),
                "lock": on_off(window.frame_controller.block_is_locked()),
            },
            bare="",
        ),
        set=lambda window, args: _block(window, args),
        summary="the block factor, or in, out, to fit, match, lock",
    ),
    AccessPoint(
        "smooth",
        get=lambda window: on_off(window.menu_bar.action_smooth.isChecked()),
        query=_keyed(lambda window: _smooth_table(window), bare=""),
        set=lambda window, args: _smooth(window, args),
        summary="the smoothing: yes|no, function, radius, sigma, angle, lock",
    ),
    AccessPoint(
        "grid",
        get=lambda window: on_off(window.analysis.grid_config.visible),
        query=_keyed(lambda window: _grid_table(window), bare=""),
        set=lambda window, args: _grid(window, args),
        summary="the coordinate grid and its parameters",
    ),
    AccessPoint(
        "contour",
        get=lambda window: on_off(window.menu_bar.action_contours.isChecked()),
        query=lambda window, args: _contour_text(window, args),
        set=lambda window, args: _contour(window, args),
        aliases=("contours",),
        summary="the contours: levels, method, colour, load, save, copy, paste",
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
        query=lambda window, args: _crop_text(window, args),
        set=lambda window, args: _crop(window, args),
        summary="the crop: centre and size, or `reset`",
    ),
    AccessPoint(
        "magnifier",
        get=lambda window: on_off(window.menu_bar.action_view_magnifier.isChecked()),
        query=_keyed(
            lambda window: {
                "": on_off(window.menu_bar.action_view_magnifier.isChecked()),
                "zoom": str(window.magnifier_panel._zoom_factor),
            },
            bare="",
        ),
        set=lambda window, args: _magnifier(window, args),
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
        query=_keyed(lambda window: _mask_table(window), bare=""),
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
        query=_keyed(_tile_table, bare=""),
        set=lambda window, args: _tile(window, args),
        summary="tile the frames, or `tile mode grid|column|row`",
    ),
    AccessPoint(
        "blink",
        get=lambda window: on_off(window._frame_display_mode == "blink"),
        query=_keyed(lambda window: _blink_table(window, "blink"), bare=""),
        set=lambda window, args: _blink(window, args, "blink"),
        summary="blink the frames, or `blink interval <seconds>`",
    ),
    AccessPoint(
        "fade",
        get=lambda window: on_off(window._frame_display_mode == "fade"),
        query=_keyed(lambda window: _blink_table(window, "fade"), bare=""),
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
        query=_keyed(lambda window: _cube_table(window), bare=""),
        aliases=("datacube",),
        set=lambda window, args: _cube(window, args),
        summary="which slice of a cube is shown",
    ),
    AccessPoint(
        "lock",
        get=lambda window: _lock_text(window),
        query=_keyed(_lock_table),
        set=lambda window, args: _lock(window, args),
        summary="lock a scope across frames: frame, crosshair, crop, slice, ...",
    ),
    AccessPoint(
        "match",
        set=lambda window, args: _match(window, args),
        summary="match a scope across frames",
    ),
)


#: DS9's `contour` settings, mapped to the keys the contour dialog and
#: `update_contours` use. DS9 spells them one way, the dialog another, and
#: this is the one place the two names meet.
_CONTOUR_KEYS = {
    "color": "color",
    "colour": "color",
    "width": "line_width",
    "nlevels": "num_levels",
    "smooth": "smoothness",
    "method": "contour_method",
    "scale": "scale",
    "mode": "mode",
    "scope": "scope",
    "limits": "limits",
    "levels": "levels",
}

#: The settings DS9's Generate reads. Changing one regenerates the levels
#: (`ContourCmdGenerateDialog`), so an explicit list set earlier is dropped.
_CONTOUR_GENERATORS = ("num_levels", "smoothness", "scale", "mode", "scope", "limits", "log_exp")


def _contour_settings(window) -> dict:
    """The contour settings, made if there are none yet."""
    if window._contour_settings is None:
        window.analysis.set_contours(True)
    return window._contour_settings or {}


def _contour_text(window, args: list[str]) -> str:
    """What `xpaget ds9 contour <what>` answers."""
    if not args:
        return on_off(window.menu_bar.action_contours.isChecked())

    what = str(args[0]).lower()
    settings = window._contour_settings or {}

    if what in ("wcs", "image", "physical") or what.startswith("wcs"):
        # `xpaget ds9 contour wcs fk5`: the contours themselves, written
        # in that system, which is what DS9 answers with.
        contours = window.analysis.current_contour_set()
        if contours is None:
            return ""
        from ...analysis import contour_file

        return contour_file.to_text(contours)
    if what == "levels":
        levels = window._contour_levels
        return " ".join(f"{value:g}" for value in levels) if levels is not None else ""
    if what == "dash":
        return on_off(str(settings.get("line_style", "Solid")).lower() != "solid")
    if what == "smooth":
        return str(settings.get("smoothness", 4))
    if what == "width":
        return f"{float(settings.get('line_width', 1)):g}"
    if what == "nlevels":
        return str(settings.get("num_levels", 5))
    if what == "limits":
        limits = settings.get("limits")
        if not limits and window._contour_levels:
            limits = (min(window._contour_levels), max(window._contour_levels))
        return f"{float(limits[0]):g} {float(limits[1]):g}" if limits else ""
    if what == "log":
        return f"{float(settings.get('log_exp', 1000)):g}"
    if what in _CONTOUR_KEYS:
        return str(settings.get(_CONTOUR_KEYS[what], ""))
    return on_off(window.menu_bar.action_contours.isChecked())


def _contour(window, args: list[str]) -> str | None:
    """DS9's `contour`, which is a good deal more than a yes or a no.

    `[yes|no] [clear] [generate] [load <file>] [save <file>] [copy]
    [paste] [color <c>] [width <n>] [dash yes|no] [smooth <n>]
    [method block|smooth] [nlevels <n>] [scale <s>] [mode <m>]
    [scope local|global] [limits <low> <high>] [levels <v>...]
    [open|close]`.
    """
    from ...analysis.contour import normalize_mode, normalize_scale

    words = [str(word) for word in args]
    controller = window.analysis
    if not words:
        controller.set_contours(True)
        return None

    first = words[0].lower()
    rest = words[1:]

    shown = as_bool(first)
    if shown is not None and not rest:
        controller.set_contours(shown)
        return None

    if first == "clear":
        controller.set_contours(False)
        return None
    if first == "generate":
        # DS9 regenerates the levels from the parameters, then draws them.
        if window._contour_settings is not None:
            window._contour_settings.pop("levels", None)
        controller.update_contours()
        return None
    if first == "open":
        controller.show_contour_dialog()
        return None
    if first == "close":
        return None
    if first == "copy":
        controller.copy_contours()
        return None
    if first == "paste":
        # `paste wcs red 2 no` names a system, colour, width and dash;
        # what is on the clipboard already carries its own, so the extra
        # words are DS9's way of overriding them and are applied after.
        controller.paste_contours()
        return _contour_style(window, rest)
    if first == "convert":
        # DS9's Convert to Polygons: each contour becomes a polygon region.
        controller.contours_to_polygons()
        return None

    if first == "load":
        # `load levels <file>` reads just the level values.
        paths = [word for word in rest if word.lower() != "levels"]
        if not paths:
            return "a contour file is needed"
        if "levels" in [word.lower() for word in rest]:
            return _contour_levels_file(window, paths[0], write=False)
        return controller.load_contour_file(paths[0])

    if first == "save":
        paths = [word for word in rest if word.lower() not in ("levels", "wcs", "image", "physical")]
        if not paths:
            return "a file to write is needed"
        if "levels" in [word.lower() for word in rest]:
            return _contour_levels_file(window, paths[0], write=True)
        return controller.save_contour_file(paths[0])

    settings = _contour_settings(window)

    if first == "dash":
        wanted = as_bool(rest[0]) if rest else None
        if wanted is None:
            return "dash takes yes or no"
        settings["line_style"] = "Dashed" if wanted else "Solid"
        controller.apply_contours(settings)
        return None

    if first == "levels":
        # DS9's own example braces the list -- `contour levels {1 2 3}` --
        # which arrives as `{1`, `2`, `3}`.
        rest = [word.strip("{}\"'") for word in " ".join(rest).replace(",", " ").split()]
        try:
            values = [float(word) for word in rest if word]
        except ValueError:
            return "levels takes numbers"
        if not values:
            return "at least one level is needed"
        settings["levels"] = values
        settings["num_levels"] = len(values)
        controller.apply_contours(settings)
        return None

    if first == "limits":
        if len(rest) < 2:
            return "limits takes a low and a high"
        try:
            settings["limits"] = (float(rest[0]), float(rest[1]))
        except ValueError:
            return "limits takes two numbers"
        # DS9's `ContourCmdLimits`: typed limits are User mode.
        settings["mode"] = "user"
        settings.pop("levels", None)
        controller.apply_contours(settings)
        return None

    if first == "log":
        # `contour log exp 1000`.
        try:
            settings["log_exp"] = float(rest[-1])
        except (IndexError, ValueError):
            return "log takes an exponent"
        settings.pop("levels", None)
        controller.apply_contours(settings)
        return None

    if first in _CONTOUR_KEYS:
        if not rest:
            return f"contour {first} needs a value"
        key = _CONTOUR_KEYS[first]
        value: object = " ".join(rest)
        if key in ("line_width", "num_levels", "smoothness"):
            try:
                value = float(rest[0]) if key == "line_width" else max(1, int(float(rest[0])))
            except ValueError:
                return f"contour {first} takes a number"
        elif key == "contour_method":
            value = str(rest[0]).lower()
            if value not in ("block", "smooth"):
                return "method takes block or smooth"
        elif key == "scale":
            value = normalize_scale(rest[0])
        elif key == "mode":
            value = normalize_mode(rest[0])
            # DS9's `ContourModeDialog`: the limits come from the new mode.
            if value != "user":
                settings.pop("limits", None)
        elif key == "scope":
            value = "global" if str(rest[0]).lower() == "global" else "local"
        settings[key] = value
        if key in _CONTOUR_GENERATORS:
            settings.pop("levels", None)
        controller.apply_contours(settings)
        return None

    return f"contour does not take {first}"


def _contour_style(window, words: list[str]) -> str | None:
    """The colour, width and dash DS9's `contour paste` may carry."""
    if not words:
        return None
    settings = _contour_settings(window)
    for word in words:
        if word.lower() in ("wcs", "image", "physical") or word.lower().startswith("wcs"):
            continue
        flag = as_bool(word)
        if flag is not None:
            settings["line_style"] = "Dashed" if flag else "Solid"
            continue
        try:
            settings["line_width"] = float(word)
        except ValueError:
            settings["color"] = word
    window.analysis.apply_contours(settings)
    return None


def _contour_levels_file(window, path: str, write: bool) -> str | None:
    """DS9's `contour load|save levels <file>`: the level values alone.

    A plain list of numbers, one per line, which is what DS9's `.lev`
    files hold -- not the contour paths a `.ctr` file holds.
    """
    from pathlib import Path

    if write:
        levels = window._contour_levels
        if levels is None:
            return "there are no contour levels to save"
        try:
            Path(path).write_text("\n".join(f"{value:g}" for value in levels) + "\n")
        except OSError as exc:
            return f"cannot write {path}: {exc}"
        return None

    try:
        text = Path(path).read_text()
    except OSError as exc:
        return f"cannot read {path}: {exc}"
    values = []
    for word in text.replace(",", " ").split():
        try:
            values.append(float(word))
        except ValueError:
            continue
    if not values:
        return f"{path} holds no levels"
    settings = _contour_settings(window)
    settings["levels"] = values
    settings["num_levels"] = len(values)
    window.analysis.apply_contours(settings)
    return None


def _smooth_table(window) -> dict[str, str]:
    """DS9's smoothing settings, from ours.

    DS9 gives a kernel a radius, and ours a size across: a radius of r is
    a kernel 2r + 1 pixels wide.
    """
    settings = window._smooth_settings
    kernel = str(settings.get("kernel_type", "Gaussian")).lower()
    function = "elliptic" if kernel == "gaussian" and settings.get("elliptical") else kernel
    radius = max(1, (int(settings.get("kernel_size", 5)) - 1) // 2)
    sigma = float(settings.get("sigma", 2.0))
    return {
        "": on_off(window.menu_bar.action_smooth.isChecked()),
        "lock": on_off(window.frame_controller.is_locked("smooth")),
        "function": function,
        "radius": str(radius),
        "radiusminor": str(int(settings.get("minor_radius", radius))),
        "sigma": f"{sigma:g}",
        "sigmaminor": f"{float(settings.get('minor_sigma', sigma)):g}",
        "angle": f"{float(settings.get('position_angle', 0.0)):g}",
    }


def _smooth(window, args: list[str]) -> str | None:
    """DS9's `smooth`: `[yes|no]`, `open|close`, `match`, `lock yes|no`,
    `function boxcar|tophat|gaussian|elliptic`, `radius <n>`, `radiusminor
    <n>`, `sigma <n>`, `sigmaminor <n>` and `angle <deg>`.

    Every word but yes and no used to be refused as "not yes or no".
    """
    words = [str(word).lower() for word in args]
    analysis = window.analysis
    if not words:
        analysis.set_smooth(True)
        return None
    first, rest = words[0], words[1:]
    wanted = as_bool(first)
    if wanted is not None:
        analysis.set_smooth(wanted)
        return None
    if first == "open":
        analysis.show_smooth_dialog()
        return None
    if first == "close":
        return None
    if first == "match":
        window.frame_controller.match_smooth()
        return None
    if first == "lock":
        return _lock(window, ["smooth", *rest])

    settings = dict(window._smooth_settings)
    if first == "function":
        kernels = {"boxcar": "Boxcar", "tophat": "Tophat", "gaussian": "Gaussian", "elliptic": "Gaussian"}
        if not rest or rest[0] not in kernels:
            return f"function takes one of {', '.join(kernels)}"
        settings["kernel_type"] = kernels[rest[0]]
        settings["elliptical"] = rest[0] == "elliptic"
    elif first in ("radius", "radiusminor", "sigma", "sigmaminor", "angle"):
        try:
            value = float(rest[0])
        except (IndexError, ValueError):
            return f"smooth {first} takes a number"
        if first == "radius":
            radius = max(1, int(value))
            settings["kernel_size"] = 2 * radius + 1
            settings["major_radius"] = radius
        elif first == "radiusminor":
            settings["minor_radius"] = max(1, int(value))
        elif first == "sigma":
            settings["sigma"] = value
            settings["major_sigma"] = value
        elif first == "sigmaminor":
            settings["minor_sigma"] = value
        else:
            settings["position_angle"] = value
    else:
        return f"smooth does not take {first}"

    window._smooth_settings = settings
    if window.menu_bar.action_smooth.isChecked():
        window.display.display()
    return None


def _grid_table(window) -> dict[str, str]:
    """DS9's grid settings, as `xpaget ds9 grid <what>` answers them."""
    config = window.analysis.grid_config
    table = {
        "": on_off(config.visible),
        "type": config.grid_type.value,
        "system": config.system,
        "sky": config.sky,
        "skyformat": config.sky_format,
        "format1": config.x_format,
        "format2": config.y_format,
        "axes type": config.axes_placement.value,
        "numerics type": config.numerics_placement.value,
        "numerics vertical": on_off(config.vertical_text),
        "title text": config.title,
        "labels text1": config.x_title,
        "labels text2": config.y_title,
    }
    for name, element in config.elements.items():
        table[name] = on_off(element.show)
        table[f"{name} color"] = element.color
        table[f"{name} width"] = str(element.width)
        table[f"{name} dash"] = on_off(element.style != "solid")
        table[f"{name} font"] = element.font
        table[f"{name} fontsize"] = str(element.font_size)
        table[f"{name} fontweight"] = element.font_weight
        table[f"{name} fontslant"] = element.font_slant
    return table


def _grid(window, args: list[str]) -> str | None:
    """DS9's `grid`: `[yes|no]`, `type`, `system`, `sky`, `skyformat`,
    `format1|format2`, `<element> [yes|no]`, `<element> color|width|dash|
    font|fontsize|fontweight|fontslant <value>`, `axes|numerics type`,
    `numerics vertical`, `title|labels text`, `reset`, `load`, `save`,
    `open|close`.

    Everything but yes and no used to be refused as "not yes or no".
    """
    from dataclasses import replace

    from ...grid.grid_config import ELEMENTS, GridConfig, GridType, Placement

    words = [str(word) for word in args]
    analysis = window.analysis
    if not words:
        analysis.set_grid(True)
        return None
    first, rest = words[0].lower(), words[1:]
    wanted = as_bool(first)
    if wanted is not None:
        analysis.set_grid(wanted)
        return None
    if first == "open":
        analysis.show_grid_dialog()
        return None
    if first == "close":
        return None

    config = analysis.grid_config.copy()
    value = rest[0] if rest else ""
    if first == "load":
        if not rest:
            return "a grid file is needed"
        try:
            loaded = GridConfig.load(rest[0])
        except (OSError, ValueError) as exc:
            return f"cannot read {rest[0]}: {exc}"
        analysis.apply_grid_settings(replace(loaded, visible=config.visible))
        return None
    if first == "save":
        if not rest:
            return "a file to write is needed"
        try:
            config.save(rest[0])
        except OSError as exc:
            return f"cannot write {rest[0]}: {exc}"
        return None
    if first == "reset":
        config = replace(GridConfig(), visible=config.visible)
    elif first == "type" and not rest:
        return "type takes analysis or publication"
    elif first == "type":
        try:
            config.grid_type = GridType(value.lower())
        except ValueError:
            return f"{value} is not analysis or publication"
    elif first in ("system", "sky", "skyformat"):
        if not rest:
            return f"grid {first} needs a value"
        field = {"system": "system", "sky": "sky", "skyformat": "sky_format"}[first]
        setattr(config, field, value.lower())
    elif first in ("format1", "format2"):
        setattr(config, "x_format" if first == "format1" else "y_format", " ".join(rest))
    elif first in ELEMENTS:
        problem = _grid_element(config, first, [word.lower() for word in rest], rest, Placement)
        if problem:
            return problem
    else:
        return f"grid does not take {first}"
    analysis.apply_grid_settings(config)
    return None


def _grid_element(config, name: str, words: list[str], raw: list[str], placement) -> str | None:
    """One element's part of `grid`: `axes color red`, `numerics type ...`."""
    element = config.elements[name]
    if not words:
        element.show = True
        return None
    what = words[0]
    shown = as_bool(what)
    if shown is not None:
        element.show = shown
        return None
    value = words[1] if len(words) > 1 else ""
    if not value:
        return f"grid {name} {what} needs a value"
    if what == "color":
        element.color = value
    elif what in ("width", "fontsize"):
        try:
            number = int(float(value))
        except ValueError:
            return f"grid {name} {what} takes a number"
        setattr(element, "width" if what == "width" else "font_size", number)
    elif what == "dash":
        dashed = as_bool(value)
        if dashed is None:
            return f"grid {name} dash takes yes or no"
        element.style = "dashed" if dashed else "solid"
    elif what in ("font", "fontweight", "fontslant"):
        setattr(
            element, {"font": "font", "fontweight": "font_weight", "fontslant": "font_slant"}[what], value
        )
    elif what == "type" and name in ("axes", "numerics"):
        try:
            chosen = placement(value)
        except ValueError:
            return f"{value} is not interior or exterior"
        setattr(config, f"{name}_placement", chosen)
    elif what == "vertical" and name == "numerics":
        flag = as_bool(value)
        if flag is None:
            return "grid numerics vertical takes yes or no"
        config.vertical_text = flag
    elif what == "text" and name == "title":
        config.title = " ".join(raw[1:])
    elif what in ("text1", "text2") and name == "labels":
        setattr(config, "x_title" if what == "text1" else "y_title", " ".join(raw[1:]))
    else:
        # The gaps, the axes origin and the default-title switches: DS9's
        # AST grid has them, ours lays itself out without them.
        return f"grid {name} {what} is not implemented"
    return None


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
    if words[0] in ("open", "close"):
        return _pan_zoom_dialog(window, words[0])
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


def _crop_text(window, args: list[str] | None = None) -> str:
    """The crop as DS9 reports it: centre then size, in the system asked for.

    `xpaget ds9 crop`, `xpaget ds9 crop wcs galactic sexagesimal arcsec`,
    `xpaget ds9 crop lock`. The arguments used to be ignored, so a script
    asking for the crop in degrees got pixels back.
    """
    from ...coordinates import ds9_coords

    words = [str(word).lower() for word in (args or [])]
    if words and words[0] == "lock":
        return str(getattr(window, "_frame_lock_scope", {}).get("crop", "none"))
    if words and words[0] == "3d":
        frame = window.frame_manager.current_frame
        span = getattr(frame, "crop_z", None) if frame is not None else None
        return "" if span is None else f"{span[0]:g} {span[1]:g}"

    crop = window.crop.region()
    if crop is None:
        shape = window.crop.shape()
        if shape is None:
            return "0 0 0 0"
        # The whole image: its centre, in FITS coordinates, and its size.
        x, y, width, height = (shape[1] + 1) / 2, (shape[0] + 1) / 2, float(shape[1]), float(shape[0])
    else:
        (x, y), width, height = crop.center, crop.width, crop.height

    _values, system, sky, _format, unit = ds9_coords.split_system(words)
    centre = _position_text(window, x, y, words)
    frame = window.frame_manager.current_frame
    try:
        sizes = [ds9_coords.image_length_to(frame, value, system, unit) for value in (width, height)]
    except ds9_coords.CoordinateError:
        sizes = [width, height]
        system = "image"
    if ds9_coords.is_sky_system(system):
        digits = {"degrees": 7, "arcmin": 5, "arcsec": 3}[unit or "degrees"]
        size_text = " ".join(f"{value:.{digits}f}" for value in sizes)
    else:
        size_text = " ".join(f"{value:g}" for value in sizes)
    return f"{centre} {size_text}"


def _crop(window, args: list[str]) -> str | None:
    """DS9's `crop`: `<x> <y> <width> <height> [<coordsys>] [<skyframe>]
    [degrees|arcmin|arcsec]`, `match <coordsys>`, `lock <coordsys>|none`,
    `reset`, `3d <zmin> <zmax> [<coordsys>]`, `open` and `close`.

    The position and size are read in the system named; they used to be
    taken as image pixels whatever it was.
    """
    from ...coordinates import ds9_coords

    words = [str(word) for word in args]
    if not words:
        return "a centre and a size are needed"
    first = words[0].lower()
    rest = [word.lower() for word in words[1:]]

    if first == "reset":
        window.crop.reset()
        return None
    if first == "open":
        window.crop.show_dialog()
        return None
    if first == "close":
        dialog = getattr(window.crop, "_dialog", None)
        if dialog is not None:
            dialog.close()
        return None
    if first == "match":
        window.crop.match(rest[0] if rest else "wcs")
        return None
    if first == "lock":
        window.frame_controller.set_lock_scope("crop", rest[0] if rest else "wcs")
        return None
    if first == "3d":
        if len(rest) < 2:
            return "a lowest and a highest slice are needed"
        try:
            low, high = float(rest[0]), float(rest[1])
        except ValueError:
            return "the slice range has to be two numbers"
        window.crop.set_slice_range(low, high)
        return None

    values, system, sky, _format, unit = ds9_coords.split_system(words)
    if len(values) < 4:
        return "a centre and a size are needed"
    centre = _image_position(window, [*values[:2], system, sky])
    if isinstance(centre, str):
        return centre
    frame = window.frame_manager.current_frame
    try:
        width, height = (
            ds9_coords.length_to_image(frame, float(value), system, unit) for value in values[2:4]
        )
    except ValueError:
        return "the size has to be two numbers"
    from ...frames.crop import CropRegion

    if not window.crop.set_region(CropRegion.from_center(centre[0], centre[1], width, height)):
        return "that crop falls outside the image, or is too small"
    return None


def _mask_table(window) -> dict[str, str]:
    """DS9's mask settings, as `xpaget ds9 mask <what>` answers them."""
    settings = window.analysis.mask_settings
    return {
        "": on_off(getattr(window.analysis, "mask_layer", None) is not None),
        "color": settings.color,
        "mark": settings.mode.value,
        "range": f"{settings.low:g} {settings.high:g}",
        "transparency": f"{settings.transparency:g}",
        "blend": settings.blend.value,
        "system": "image",
    }


def _mask(window, args: list[str]) -> str | None:
    """DS9's `mask`: `load <file>`, `clear`, `color <c>`, `mark zero|nonzero|
    nan|nonnan|range`, `range <low> <high>`, `transparency <n>`, `blend
    source|screen|darken|lighten`, `system <coordsys>`, `open|close`, and a
    bare file name, which loads it.

    Every word but `clear` used to be taken for a file name -- `mask load
    foo.fits` tried to open a file called `load`.
    """
    from dataclasses import replace

    from ...analysis.mask import BlendMode, MaskMode

    words = [str(word) for word in args]
    if not words:
        return "a mask file or a mask setting is needed"
    analysis = window.analysis
    first, rest = words[0].lower(), words[1:]

    if first == "clear":
        analysis.clear_mask()
        return None
    if first == "open":
        analysis.show_mask_dialog()
        return None
    if first == "close":
        return None
    if first == "load":
        if not rest:
            return "a mask file is needed"
        return None if analysis.load_mask(rest[-1]) else f"{rest[-1]} could not be loaded as a mask"

    settings = analysis.mask_settings
    value = rest[0].lower() if rest else ""
    if first == "color":
        if not value:
            return "a colour is needed"
        settings = replace(settings, color=value)
    elif first == "mark":
        try:
            settings = replace(settings, mode=MaskMode(value))
        except ValueError:
            return "mark takes zero, nonzero, nan, nonnan or range"
    elif first == "range":
        try:
            settings = replace(settings, low=float(rest[0]), high=float(rest[1]))
        except (IndexError, ValueError):
            return "range takes a low and a high"
    elif first == "transparency":
        try:
            settings = replace(settings, transparency=max(0.0, min(100.0, float(value))))
        except ValueError:
            return "transparency takes a number from 0 to 100"
    elif first == "blend":
        try:
            settings = replace(settings, blend=BlendMode(value))
        except ValueError:
            return "blend takes source, screen, darken or lighten"
    elif first == "system":
        # Ours lines a mask up with the image pixel for pixel; DS9 can
        # align it through the WCS instead, which is not implemented.
        if value == "image":
            return None
        if value in ("wcs", "physical") or value.startswith("wcs"):
            return f"aligning a mask in {value} coordinates is not implemented; masks align by image pixel"
        return f"{rest[0] if rest else ''} is not a coordinate system"
    else:
        return None if analysis.load_mask(words[-1]) else f"{words[-1]} could not be loaded as a mask"

    analysis.mask_settings = settings
    if getattr(analysis, "mask_layer", None) is not None:
        window.display.display()
    return None


def _tile(window, args: list[str]) -> str | None:
    """DS9's `tile`: `[yes|no]`, `mode grid|column|row`, `grid`, `row`,
    `column`, and `grid mode|direction|layout|gap ...`.

    `tile column`, `tile row` and every `tile grid ...` used to answer ok
    and change nothing but the display mode.
    """
    from dataclasses import replace

    words = [str(word).lower() for word in args]
    controller = window.frame_controller
    arrangements = ("grid", "column", "row")

    if words and words[0] == "mode":
        if len(words) < 2 or words[1] not in arrangements:
            return "grid, column or row is needed"
        words = words[1:]
    if words and words[0] in arrangements and (words[0] != "grid" or len(words) == 1):
        controller.set_tile_arrangement(words[0])
        # DS9's `tile mode` says how to tile, which implies tiling.
        controller.set_display_mode("tile")
        return None

    if words and words[0] == "grid":
        what, rest = (words[1], words[2:]) if len(words) > 1 else ("", [])
        settings = controller.tile_settings
        if what == "mode":
            if not rest or rest[0] not in ("automatic", "manual"):
                return "grid mode takes automatic or manual"
            settings = replace(settings, manual=rest[0] == "manual")
        elif what == "direction":
            if not rest or rest[0] not in ("x", "y"):
                return "grid direction takes x or y"
            settings = replace(settings, direction=rest[0])
        elif what == "layout":
            try:
                columns, rows = int(float(rest[0])), int(float(rest[1]))
            except (IndexError, ValueError):
                return "grid layout takes a number of columns and of rows"
            if columns < 1 or rows < 1:
                return "grid layout needs at least one column and one row"
            # A layout is only used by a manual grid, which DS9 implies.
            settings = replace(settings, columns=columns, rows=rows, manual=True)
        elif what == "gap":
            try:
                settings = replace(settings, gap=max(0, int(float(rest[0]))))
            except (IndexError, ValueError):
                return "grid gap takes a number of pixels"
        else:
            return f"tile grid does not take {what}"
        controller.apply_tile_settings(settings)
        return None

    wanted = as_bool(words[0]) if words else True
    if wanted is None:
        return f"tile does not take {words[0]}"
    controller.set_display_mode("tile" if wanted else "single")
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
    if wanted is None:
        return f"{mode} does not take {words[0]}"
    window.frame_controller.set_display_mode(mode if wanted else "single")
    if wanted and window._frame_display_mode != mode:
        # The controller falls back to single with fewer than two frames
        # showing; saying ok to that would be a blink that never blinks.
        return f"{mode} needs at least two frames to show"
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


def _cube_table(window) -> dict[str, str]:
    """DS9's cube settings, as `xpaget ds9 cube <what>` answers them."""
    frame = window.frame_manager.current_frame
    panel = window.cube_dialog
    current = str(int(getattr(frame, "slice_index", 0) or 0) + 1)
    return {
        "": current,
        "image": current,
        "interval": f"{panel.interval_seconds:g}",
        "lock": str(getattr(window, "_frame_lock_scope", {}).get("slice", "none")),
        "order": str(getattr(frame, "axis_order", "123") or "123"),
        "axes lock": on_off(window.frame_controller.is_locked("axes_order")),
        "axis": "3",
    }


def _cube(window, args: list[str]) -> str | None:
    """DS9's `cube`: `[]`, `play|stop|next|prev|first|last`, `<slice>
    [<coordsys>]`, `interval <s>`, `match <coordsys>`, `lock <coordsys>|none`,
    `order <123..321>`, `axes lock [yes|no]`, `axis <n>`, `open|close`.

    Only a slice number used to be understood; every other word was
    refused as "not a slice number".
    """
    words = [str(word).lower() for word in args]
    controller = window.frame_controller
    panel = window.cube_dialog
    if not words or words[0] == "open":
        controller.show_cube_dialog()
        return None
    first, rest = words[0], words[1:]
    if first == "close":
        panel.close()
        return None

    handler = controller.cube_handler()
    frame = window.frame_manager.current_frame
    if first in ("play", "stop"):
        if handler is None:
            return "the current frame holds no data cube"
        panel.set_playing(first == "play")
        return None
    if first in ("next", "prev", "first", "last"):
        if handler is None or frame is None:
            return "the current frame holds no data cube"
        depth = handler.depth(frame.axis_order)
        current = int(frame.slice_index or 0)
        wanted = {
            "next": (current + 1) % depth,
            "prev": (current - 1) % depth,
            "first": 0,
            "last": depth - 1,
        }[first]
        controller.set_slice(wanted)
        return None
    if first == "interval":
        try:
            seconds = float(rest[0])
        except (IndexError, ValueError):
            return "interval takes a number of seconds"
        panel._interval.setValue(seconds)
        return None
    if first == "match":
        controller.match_slice(rest[0] if rest else "wcs")
        return None
    if first == "lock":
        return _lock(window, ["slice", *(rest or ["wcs"])])
    if first == "order":
        if not rest:
            return "order takes one of 123, 132, 213, 231, 312, 321"
        if handler is None:
            return "the current frame holds no data cube"
        try:
            from ...core.cube_handler import AxisOrder

            AxisOrder.parse(rest[0])
        except Exception:
            return f"{rest[0]} is not an axis order"
        controller.set_axis_order(rest[0])
        return None
    if first == "axes":
        if not rest or rest[0] != "lock":
            return "axes takes lock"
        return _lock(window, ["axes", *rest[1:]])
    if first == "axis":
        if rest and rest[0] == "3":
            return None
        return "only the third axis can be stepped through; a fourth is not implemented"

    if rest and rest[0] not in ("image",):
        return f"a slice in {rest[0]} coordinates is not implemented; give the slice number (image)"
    return _slice(window, [first])


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
    # DS9 says `scalelimits` and `axes`; the flags are `scale_limits` and
    # `axes_order`, and the DS9 spelling used to be refused.
    scope = _LOCK_NAMES.get(scope, scope)
    rest = [str(word).lower() for word in args[1:]]

    if scope in getattr(window, "_frame_lock_scope", {}):
        system = rest[0] if rest else "wcs"
        window.frame_controller.set_lock_scope(scope, system)
        return None
    if scope in getattr(window, "_frame_lock_flags", {}):
        wanted = as_bool(rest[0]) if rest else True
        if wanted is None:
            return f"lock {args[0]} takes yes or no"
        window.frame_controller.set_lock_flag(scope, wanted)
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
    if scope.startswith("slice"):
        # DS9's own example runs the system on: `match slicewcs`.
        controller.match_slice(system if len(args) > 1 else (scope[5:] or "wcs"))
        return None
    scope = _LOCK_NAMES.get(scope, scope)
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

    if words[0] in ("open", "close"):
        # Our Block Parameters is a modal question, which would hold the
        # XPA reply until somebody answered it; DS9's is a modeless window.
        return "the block dialog is modal here; set the factor with `block <n>`"
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
        factors = [int(float(word)) for word in words[:2]]
    except ValueError:
        return f"{' '.join(words[:2])} is not a block factor"
    if len(factors) == 2 and factors[0] != factors[1]:
        # DS9 can block the two axes differently; ours blocks both alike,
        # and taking the first while answering ok was a quiet half-truth.
        return "blocking the two axes by different factors is not implemented"
    analysis.set_block(factors[0])
    return None


def _pan_zoom_dialog(window, word: str) -> str | None:
    """`rotate|orient open|close`: DS9's Pan Zoom Rotate Parameters."""
    if word == "open":
        window.zoom.show_pan_zoom_rotate_dialog()
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
        get=lambda window: illustrate_file_text(window),
        query=_keyed(lambda window: _illustrate_table(window), bare=""),
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
        query=_keyed(_preserve_table),
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
        query=lambda window, args: _crosshair_text(window, args),
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
        query=_keyed(_pagesetup_table),
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
        set=lambda window, args: _header(window, args),
        summary="show, close or save a FITS header",
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


def _illustrate_table(window) -> dict[str, str]:
    """DS9's illustrate settings, as `xpaget ds9 illustrate <what>` answers."""
    layer = window.illustrate.layer
    return {
        "": illustrate_file_text(window),
        "shape": str(layer.shape),
        "color": str(layer.style.color),
        "fill": on_off(layer.style.fill),
        "width": str(layer.style.width),
        "dash": on_off(layer.style.dash),
        "show": on_off(layer.visible),
    }


def illustrate_file_text(window) -> str:
    """Every illustration, as an illustrate file holds them."""
    from ...illustrate import illustrate_file

    return illustrate_file.serialise(list(window.illustrate.layer.elements))


def _illustrate(window, args: list[str]) -> str | None:
    """DS9's `illustrate`: `open|close`, `shape`, `color`, `fill`, `width`,
    `dash`, `move front|back`, `select all|none|invert|front|back`, `save
    [select|all] <file>`, `list [select|all|close]`, `delete [all|select]`,
    `[load] <file>`, `show yes|no`, `command <line>`, `undo`, `cut`, `copy`,
    `paste`.
    """
    words = [str(word) for word in args]
    controller = window.illustrate
    if not words:
        return "a command or a file is needed"
    word = words[0].lower()
    rest = words[1:]
    lowered = [value.lower() for value in rest]
    layer = controller.layer

    if word == "open" and not rest:
        controller.show_dialog()
        return None
    if word == "close":
        return None
    if word == "open":
        # Not DS9's grammar, but this point took `open <file>` before it
        # took DS9's `load <file>`, and scripts may say it.
        word = "load"
    if word == "show":
        wanted = as_bool(lowered[0]) if lowered else True
        if wanted is None:
            return "show takes yes or no"
        controller.set_visible(wanted)
        return None
    if word == "shape":
        shapes = ("circle", "ellipse", "box", "polygon", "line", "text", "image")
        if not lowered or lowered[0] not in shapes:
            return f"shape takes one of {', '.join(shapes)}"
        controller.set_shape(lowered[0])
        return None
    if word == "color":
        if not rest:
            return "a colour is needed"
        controller.set_color(lowered[0])
        return None
    if word == "width":
        try:
            controller.set_width(int(float(rest[0])))
        except (IndexError, ValueError):
            return "width takes a number"
        return None
    if word in ("fill", "dash"):
        wanted = as_bool(lowered[0]) if lowered else None
        if wanted is None:
            return f"{word} takes yes or no"
        setattr(layer.style, word, wanted)
        for element in layer.selection():
            setattr(element.style, word, wanted)
        controller.refresh()
        return None
    if word == "move":
        if not lowered or lowered[0] not in ("front", "back"):
            return "move takes front or back"
        (controller.move_to_front if lowered[0] == "front" else controller.move_to_back)()
        return None
    if word == "select":
        actions = {
            "all": controller.select_all,
            "none": controller.select_none,
            "invert": controller.invert_selection,
            "front": controller.select_front,
            "back": controller.select_back,
        }
        if not lowered or lowered[0] not in actions:
            return f"select takes one of {', '.join(actions)}"
        actions[lowered[0]]()
        return None
    if word == "save":
        selected = bool(lowered) and lowered[0] == "select"
        paths = rest[1:] if lowered and lowered[0] in ("select", "all") else rest
        if not paths:
            return "a file is needed"
        chosen = layer.selection() if selected else layer.elements
        if not chosen:
            return "there are no illustrations to save"
        return (
            None
            if (controller.save_selection if selected else controller.save)(paths[0])
            else (f"could not write {paths[0]}")
        )
    if word == "list":
        if lowered and lowered[0] == "close":
            return None
        (controller.list_selection if lowered and lowered[0] == "select" else controller.list_all)()
        return None
    if word == "delete":
        if lowered and lowered[0] == "select":
            controller.delete_selection()
        else:
            controller.delete_all()
        return None
    if word in ("undo", "cut", "copy", "paste"):
        if word == "undo":
            return "illustrate undo is not implemented"
        {"cut": controller.cut_selection, "copy": controller.copy_selection, "paste": controller.paste}[
            word
        ]()
        return None
    if word == "command":
        from ...illustrate import illustrate_file

        elements = illustrate_file.parse(" ".join(rest).strip("{}"))
        if not elements:
            return f"nothing in {' '.join(rest)!r} was an illustration"
        for element in elements:
            layer.add(element)
        controller.refresh()
        return None
    path = rest[0] if word == "load" and rest else words[0]
    if word == "load" and not rest:
        return "a file is needed"
    from pathlib import Path

    if not Path(path).is_file():
        return f"there is no illustrate file at {path}"
    controller.load(path)
    return None


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
    words = [str(word) for word in args]
    if words and words[0].lower() == "color":
        words = words[1:]
    if not words:
        return "a colour is needed"
    window.nan_color = words[0]
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


def _crosshair_text(window, args: list[str]) -> str:
    """Where the crosshair is, in whichever system was asked for.

    `xpaget ds9 crosshair image`, `xpaget ds9 crosshair wcs fk5 degrees`,
    and `xpaget ds9 crosshair lock`, which answers the lock's system.
    """
    words = [str(word).lower() for word in args]
    if words and words[0] == "lock":
        return str(getattr(window, "_frame_lock_scope", {}).get("crosshair", "none"))
    placed = window.crosshair.position()
    if placed is None:
        return "0 0"
    return _position_text(window, placed[0], placed[1], words)


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


def _header(window, args: list[str]) -> str | None:
    """DS9's `header [<ext>]`, `header close [<ext>]`, `header save [<ext>]
    <file>`.

    The extension counts from one, as DS9's does. `header save` used to
    answer ok and write nothing, and `header 2` showed the frame's own.
    """
    words = [str(word) for word in args]
    handler = window.fits_handler
    if handler is None:
        return "no FITS file is loaded"
    first = words[0].lower() if words else ""

    def extension(word: str | None) -> int | None:
        if word is None:
            return None
        number = int(float(word))
        if number < 1:
            raise ValueError(word)
        return number - 1

    if first == "close":
        from PyQt6.QtWidgets import QApplication

        from ...ui.dialogs.header_dialog import HeaderDialog

        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, HeaderDialog):
                widget.close()
        return None
    if first == "save":
        rest = words[1:]
        if not rest:
            return "a file to write is needed"
        try:
            index = extension(rest[0]) if len(rest) > 1 else None
        except ValueError:
            return f"{rest[0]} is not an extension number"
        if index is None:
            index = getattr(window.frame_manager.current_frame, "hdu_index", None) or 0
        try:
            header = handler.get_header(index)
        except Exception as exc:
            return f"there is no header {index + 1}: {exc}"
        from pathlib import Path

        try:
            Path(rest[-1]).write_text(header.tostring(sep="\n", endcard=True, padding=False) + "\n")
        except OSError as exc:
            return f"cannot write {rest[-1]}: {exc}"
        return None
    try:
        index = extension(words[0]) if words else None
    except ValueError:
        return f"{words[0]} is not an extension number"
    if index is not None:
        try:
            handler.get_header(index)
        except Exception:
            return f"there is no header {index + 1}"
    window.file.show_header(index)
    return None


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
    """DS9's `saveimage`, in both its forms.

    `saveimage ds9.tiff` takes the format from the name; `saveimage jpeg
    ds9.jpeg 75` names the format first and the quality last. Reading the
    first word as the path breaks the second form, and the second form is
    the one anybody writes when they care about the quality.
    """
    if not args:
        return "a file is needed"
    from pathlib import Path

    from ...io import raster

    words = [str(word) for word in args]
    # The path is the argument with a suffix; a bare format name and a
    # bare number are the other two things DS9 allows.
    named = [word for word in words if Path(word).suffix]
    if not named:
        return "a file is needed"
    path = Path(named[-1])
    suffix = path.suffix.lower()

    # An explicit format wins over the suffix, as DS9's does.
    for word in words:
        if word is named[-1]:
            continue
        candidate = f".{word.lower().lstrip('.')}"
        if any(candidate in suffixes for suffixes in raster.FORMATS.values()):
            suffix = candidate
            break
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


def _magnifier(window, args: list[str]) -> str | None:
    """DS9's `magnifier`: `yes|no`, `zoom <n>`, `color`, `cursor`, `region`.

    The zoom used to be refused as "not yes, no, open or close"; the
    colour, cursor and region overlays are not drawn on our magnifier at
    all, so those say so.
    """
    words = [str(word).lower() for word in args]
    if words and words[0] == "zoom":
        try:
            zoom = int(float(words[1]))
        except (IndexError, ValueError):
            return "magnifier zoom takes a number"
        spin = window.magnifier_panel._zoom_spinbox
        if not spin.minimum() <= zoom <= spin.maximum():
            return f"magnifier zoom runs from {spin.minimum()} to {spin.maximum()}"
        spin.setValue(zoom)
        return None
    if words and words[0] in ("color", "cursor", "region"):
        return f"the magnifier has no {words[0]} overlay to set"
    return _panel(window, args, "magnifier")


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
    if wanted in ("open", "close"):
        return _pan_zoom_dialog(window, wanted)
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
        "catalog",
        get=lambda window: _catalog_text(window, []),
        query=lambda window, args: _catalog_text(window, args),
        set=lambda window, args: _catalog(window, args),
        aliases=("cat",),
        summary="the catalogue tool: load, query, filter, match, export",
    ),
    AccessPoint(
        "footprint",
        get=lambda window: _catalog_text(window, []),
        query=lambda window, args: _catalog_text(window, args),
        set=lambda window, args: _footprint(window, args),
        aliases=("fp",),
        summary="the footprint servers, which load as catalogues",
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
    AccessPoint(
        "prefs",
        query=lambda window, args: _prefs_text(window, args),
        set=lambda window, args: _prefs(window, args),
        summary="the preferences: bg and nan colour, precision, theme, threads",
    ),
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
    # DS9's trailing word: `big|little|native` for the array kinds, a
    # quality or a compression for the pictures, which are not settable.
    order = {"big": True, "little": False, "native": sys.byteorder == "big"}
    big_endian = order.get(words[2].lower()) if len(words) > 2 else None
    if big_endian is None and (kind in ("array", "nrrd", "envi") or kind.endswith("_array")):
        big_endian = order["native"]
    return None if window.file.export_file(kind, words[1], big_endian) else f"{words[1]} could not be written"


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
    # Through the system on the WCS menu, `wcs` or `wcsa`..`wcsz`, as DS9
    # reports a coordinate in whichever the user selected.
    handler = getattr(getattr(window, "wcs", None), "handler", None)
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
        get=lambda window: str(window.preferences.get("background_color", "#000000")),
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
        query=_keyed(
            lambda window: {
                "": _graph_text(window),
                "grid": on_off(window.horizontal_graph.settings.grid),
                "log": on_off(window.horizontal_graph.settings.log),
                "method": str(window.horizontal_graph.settings.method),
                "size": str(window.horizontal_graph.settings.size),
                "thickness": str(window.horizontal_graph.settings.thickness),
            },
            bare="",
        ),
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
        get=lambda window: str(window.preferences.get("theme", "System")).lower(),
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
        query=_keyed(_view_table),
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
        query=lambda window, args: _region_text(window, args),
        set=lambda window, args: _region(window, args),
        aliases=("regions",),
        summary="the regions: load, save, list, delete, colour, shape",
    ),
    AccessPoint(
        "rgb",
        get=lambda window: str(getattr(window.frame_manager.current_frame, "rgb_current_channel", "")),
        query=lambda window, args: _colour_frame_text(window, args),
        set=lambda window, args: _colour_frame(window, args, "rgb"),
        summary="the RGB frame and its channel",
    ),
    AccessPoint(
        "hsv",
        get=lambda window: str(getattr(window.frame_manager.current_frame, "rgb_current_channel", "")),
        query=lambda window, args: _colour_frame_text(window, args),
        set=lambda window, args: _colour_frame(window, args, "hsv"),
        summary="the HSV frame and its channel",
    ),
    AccessPoint(
        "hls",
        get=lambda window: str(getattr(window.frame_manager.current_frame, "rgb_current_channel", "")),
        query=lambda window, args: _colour_frame_text(window, args),
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
        query=_keyed(lambda window: _bin_table(window)),
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
        query=_keyed(_pagesetup_table),
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
    words = [str(word) for word in args]
    # DS9's `bg color red` as well as `bg red`.
    if words and words[0].lower() == "color":
        words = words[1:]
    if not words:
        return "a colour is needed"
    colour = words[0]
    window.preferences.set("background_color", colour)
    window._apply_background_color(colour)
    return None


def _data(window, args: list[str]) -> str:
    """DS9's `data`: a box of values, with or without their coordinates.

    `data <coordsys> [<skyframe>] <x> <y> <width> <height> [yes|no]`: the
    lower-left corner and the size in that system -- degrees for a WCS one
    -- and the trailing flag strips the coordinates, leaving the values.
    The system used to be ignored, so a box in `fk5` read degrees as
    pixels and came back empty.
    """
    import numpy as np

    from ...coordinates import ds9_coords

    frame = window.frame_manager.current_frame
    image = getattr(frame, "image_data", None) if frame is not None else None
    if image is None:
        return ""

    words = [str(word) for word in args]
    strip = True
    if words and as_bool(words[-1]) is not None and not _is_number(words[-1]):
        strip = bool(as_bool(words[-1]))
        words = words[:-1]
    values, system, sky, _format, _unit = ds9_coords.split_system(words)
    if not any(ds9_coords.is_system(word) or word.lower() in ds9_coords.SKY_FRAMES for word in words):
        system = "image"
    if len(values) < 4:
        raise ValueError("data needs a corner, a width and a height")

    corner = _image_position(window, [*values[:2], system, sky])
    if isinstance(corner, str):
        raise ValueError(corner)
    try:
        width, height = (
            ds9_coords.length_to_image(frame, float(value), system, "degrees") for value in values[2:4]
        )
    except ValueError as exc:
        raise ValueError("the width and height have to be numbers") from exc

    # DS9 counts the box in whole pixels from the corner pixel.
    left = int(round(corner[0])) - 1
    bottom = int(round(corner[1])) - 1
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
                continue
            x, y = left + column_index + 1, bottom + row_index + 1
            if system == "image":
                where = f"{x} {y}"
            else:
                where = _position_text(window, x, y, [system, sky])
            lines.append(f"{where} {value:g}")
    return "\n".join(lines)


def _is_number(word: str) -> bool:
    try:
        float(word)
    except ValueError:
        return False
    return True


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


#: DS9's nine precisions, in the order `precision` and `prefs precision`
#: take them, with DS9's defaults (`pds9(prec,*)` in `ds9/library/ds9.tcl`).
_PRECISIONS: tuple[tuple[str, int], ...] = (
    ("linear", 8),
    ("degrees", 7),
    ("hms", 4),
    ("dms", 3),
    ("len_linear", 8),
    ("len_degrees", 7),
    ("arcmin", 5),
    ("arcsec", 3),
    ("angle", 8),
)

#: The six-number form this point took before it took DS9's nine.
_LEGACY_PRECISIONS = ("linear", "degrees", "hms", "dms", "arcmin", "arcsec")


def _precision_text(window) -> str:
    """DS9's `precision`: the nine digit counts, in its own order."""
    store = window.preferences
    return " ".join(str(store.get(f"precision_{name}", default)) for name, default in _PRECISIONS)


def _precision(window, args: list[str]) -> str | None:
    """DS9's `precision`: how many digits a coordinate is written to.

    DS9 takes nine numbers positionally -- linear, degrees, hms, dms, then
    the length precisions linear, degrees, arcmin and arcsec, and the angle
    one. This took six, in a different order, so DS9's own example put
    its length precisions into the arcmin and arcsec slots. Six numbers are
    still read the old way, and a `<name> <value>` pair is accepted too.
    """
    names = [name for name, _default in _PRECISIONS]
    words = [str(word) for word in args]
    if not words:
        return "precision needs a number"

    if words[0].lower() in names:
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
    if len(values) == len(_LEGACY_PRECISIONS):
        order: tuple[str, ...] | list[str] = _LEGACY_PRECISIONS
    elif len(values) == len(names):
        order = names
    else:
        return f"precision takes {len(names)} numbers, not {len(values)}"
    for name, value in zip(order, values, strict=True):
        window.preferences.set(f"precision_{name}", value)
    return None


def _prefs_text(window, args: list[str]) -> str:
    """DS9's `xpaget ds9 prefs ...`: one preference, as DS9 answers it."""
    store = window.preferences
    words = [str(word).lower() for word in args if str(word).lower() != "color"]
    if not words:
        raise ValueError("prefs needs the name of a preference to read")
    first = words[0]
    if first == "has":
        # `prefs has bg color`: whether the background colour is in use.
        # Ours always is.
        return YES
    if first in ("bg", "background", "bgcolor"):
        return str(store.get("background_color", "#000000"))
    if first in ("nan", "nancolor"):
        return str(window.nan_color)
    if first == "precision":
        return _precision_text(window)
    if first == "auto":
        if words[-1] == "interval":
            return str(store.get("autosave_interval", 5))
        return on_off(store.get("autosave", True))
    if first == "theme":
        return str(store.get("theme", "System")).lower()
    if first == "threads":
        return str(store.get("worker_threads", 4))
    if first in ("irafalign", "iraf"):
        return NO
    raise ValueError(f"prefs has no {first} to read")


def _prefs(window, args: list[str]) -> str | None:
    """DS9's `prefs`: the dialog, and the handful of preferences it sets.

    `open`, `close`, `save`, `clear`, `bg color <colour>`, `nan color
    <colour>`, `precision <nine numbers>`, `auto recovery yes|no`, `auto
    recovery interval <n>`, `theme <theme>`, `threads <n>`, `irafalign
    yes|no`. Every one of these used to open the dialog and answer ok.
    """
    words = [str(word) for word in args]
    if not words or words[0].lower() == "open":
        window.edit.show_preferences()
        return None
    first = words[0].lower()
    rest = [word for word in words[1:] if word.lower() != "color"]

    if first == "close":
        return None
    if first == "save":
        window.preferences.save()
        return None
    if first == "clear":
        window.preferences.reset()
        window.edit.apply_preferences(window.edit.preferences_dict(), persist=False, show_message=False)
        return None
    if first in ("bg", "background", "bgcolor"):
        if not rest:
            return "a colour is needed"
        if as_bool(rest[0]) is not None:
            return "the background colour is always in use here; give a colour"
        return _background(window, rest)
    if first in ("nan", "nancolor"):
        if not rest:
            return "a colour is needed"
        window.preferences.set("nan_color", rest[0])
        return _nan(window, rest)
    if first == "precision":
        return _precision(window, rest)
    if first == "auto":
        rest = [word for word in rest if word.lower() != "recovery"]
        if rest and rest[0].lower() == "interval":
            try:
                window.preferences.set("autosave_interval", max(1, int(float(rest[1]))))
            except (IndexError, ValueError):
                return "auto recovery interval takes a number of minutes"
            return None
        wanted = as_bool(rest[0]) if rest else None
        if wanted is None:
            return "auto recovery takes yes or no"
        window.preferences.set("autosave", wanted)
        return None
    if first == "theme":
        return _theme(window, rest)
    if first == "threads":
        return _threads(window, rest)
    if first in ("irafalign", "iraf"):
        # DS9's IRAF alignment flips a frame to match IRAF's display; there
        # is nothing here for the flag to act on.
        return "IRAF alignment is not implemented"
    return f"prefs does not take {words[0]}"


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


def _channel_keys(window, frame) -> dict[str, str]:
    """Every name a channel answers to, mapped to its storage key.

    DS9's own name for the plane (`value` on an HSV frame) and the key it
    is stored under (`blue`) both work, so a script written for DS9 and
    one written against this application agree.
    """
    from ...ui.display import channel_labels

    keys = tuple(frame.rgb_channels)
    names = {key.lower(): key for key in keys}
    for label, key in zip(channel_labels(frame.frame_type), keys, strict=False):
        names[label.lower()] = key
    return names


def _channel_view(window, channel: str, shown: bool) -> str | None:
    """Show or hide one channel of an RGB, HSV or HLS frame."""
    frame = window.frame_manager.current_frame
    if frame is not None and getattr(frame, "rgb_channels", None):
        channel = _channel_keys(window, frame).get(channel.lower(), channel)
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


#: DS9's `-option value` words, on both a read and a write of `regions`.
_REGION_OPTIONS = ("-format", "-system", "-sky", "-skyformat", "-strip", "-prop", "-group", "-delim", "-wcs")

#: DS9's region property names and the attributes that hold them.
_REGION_FLAGS = {
    "fixed": "fixed",
    "edit": "can_edit",
    "move": "can_move",
    "rotate": "can_rotate",
    "delete": "can_delete",
    "dash": "dash",
    "fill": "fill",
}


def _region_options(words: list[str]) -> tuple[list[str], dict[str, str]]:
    """Split DS9's `-format ds9 -system wcs ...` off a `regions` command.

    Returns:
        The words that are left, and the options by name without the dash.
    """
    rest: list[str] = []
    options: dict[str, str] = {}
    index = 0
    while index < len(words):
        word = words[index]
        if word.lower() in _REGION_OPTIONS:
            name = word.lower().lstrip("-")
            if name == "prop" and index + 2 < len(words):
                options[f"prop {words[index + 1].lower()}"] = words[index + 2]
                index += 3
                continue
            options[name] = words[index + 1] if index + 1 < len(words) else ""
            index += 2
            continue
        rest.append(word)
        index += 1
    return rest, options


def _listing_options(options: dict[str, str]) -> dict[str, object]:
    """What `RegionController.render` takes, out of DS9's options."""
    found: dict[str, object] = {}
    if "format" in options:
        found["region_format"] = options["format"].lower()
    if "system" in options:
        found["system"] = options["system"].lower()
    if "sky" in options:
        found["sky"] = options["sky"].lower()
    if "skyformat" in options:
        found["skyformat"] = options["skyformat"].lower()
    if "strip" in options:
        found["strip"] = as_bool(options["strip"]) is True
    return found


def _region_subset(window, options: dict[str, str], extra: str | None = None) -> list:
    """The regions a read or a save names: all, or by property or group."""
    controller = window.region
    regions = list(controller._regions())
    wanted = dict(options)
    if extra:
        wanted[f"prop {extra}"] = "1"
    for key, value in wanted.items():
        if key.startswith("prop "):
            name = key[5:]
            on = as_bool(value) is not False
            regions = [region for region in regions if _region_property(region, name) == on]
    group = options.get("group")
    if group:
        regions = [region for region in regions if group in (region.tags or [])]
    return regions


def _region_property(region, name: str) -> bool:
    """One of DS9's region properties, as true or false."""
    if name in ("select", "selected"):
        return bool(getattr(region, "selected", False))
    if name == "include":
        return bool(region.include)
    if name == "exclude":
        return not region.include
    if name == "source":
        return bool(region.source)
    if name == "background":
        return not region.source
    attribute = _REGION_FLAGS.get(name, name)
    return bool(getattr(region, attribute, False))


def _region_text(window, args: list[str] | None = None) -> str:
    """What `xpaget ds9 regions [...]` answers.

    The regions, in the format and system asked for -- `-format ds9
    -system wcs -sky fk5 -skyformat sexagesimal`, defaulting to what
    `regions format|system|sky|skyformat` last set -- or one setting by
    name: `xpaget ds9 regions color`. Every argument used to be ignored,
    so each of those answered with the same listing.
    """
    words, options = _region_options([str(word) for word in (args or [])])
    controller = window.region
    first = words[0].lower() if words else ""
    settings = controller.output_settings()

    if first in ("source", "background", "include", "exclude", "selected", "select"):
        regions = _region_subset(window, options, first)
        return controller.render(regions, **_listing_options(options))
    if first and first != "list":
        return _region_setting(window, first, [word.lower() for word in words[1:]], settings)

    regions = _region_subset(window, options)
    return controller.render(regions, **_listing_options(options))


def _region_setting(window, what: str, rest: list[str], settings: dict) -> str:
    """One region setting, by DS9's name for it."""
    controller = window.region
    defaults = controller.defaults
    overlay = getattr(window.image_viewer, "region_overlay", None)
    font = str(defaults.get("font", "helvetica 10 normal roman")).split()
    if what == "format":
        return str(settings["region_format"])
    if what in ("system", "sky", "skyformat"):
        return str(settings[what])
    if what == "strip":
        return on_off(settings["strip"])
    if what == "color":
        return str(defaults.get("color", "green"))
    if what == "width":
        return str(defaults.get("width", 1))
    if what == "font":
        return str(defaults.get("font_family", font[0]))
    if what == "fontsize":
        return str(defaults.get("font_size", font[1] if len(font) > 1 else 10))
    if what == "fontweight":
        return font[2] if len(font) > 2 else "normal"
    if what == "fontslant":
        return font[3] if len(font) > 3 else "roman"
    if what in _REGION_FLAGS:
        attribute = _REGION_FLAGS[what]
        return on_off(defaults.get(attribute, attribute.startswith("can_")))
    if what == "shape":
        mode = getattr(overlay, "mode", None)
        return str(getattr(mode, "value", mode) or "none")
    if what == "show":
        return on_off(overlay is not None and not overlay.isHidden())
    if what == "showtext":
        renderer = getattr(overlay, "renderer", None)
        return on_off(getattr(renderer, "show_labels", True))
    if what == "epsilon":
        return str(window.preferences.get("region_epsilon", 3))
    if what == "centroid":
        if rest and rest[0] == "radius":
            return f"{controller.centroid_radius:g}"
        if rest and rest[0] == "iteration":
            return str(controller.centroid_iterations)
        return on_off(controller.auto_centroid)
    if what == "groups":
        from ...regions import group_manager

        return " ".join(group_manager.group_names(controller._regions()))
    raise ValueError(f"regions has no {what} to read")


def _region(window, args: list[str]) -> str | None:
    """DS9's `regions`, the grammar in `ds9/parsers/regionparser.tac`.

    `[<file>]`, `load [all] <file>`, `save [select] <file>`, `list [select|
    close]`, `delete [select]`, `delete load <file>`, `select all|none|
    invert|front|back`, `move front|back`, `show|showtext yes|no`, `format`,
    `system`, `sky`, `skyformat`, `strip`, `shape`, `color`, `width`,
    `dash`, `fill`, `font`, `fontsize`, `fontweight`, `fontslant`, the
    property flags, `include|exclude|source|background`, `centroid [auto
    yes|no] [radius|iteration <n>]`, `epsilon`, `command`, `composite`,
    `dissolve`, `template`, `group ...`, `copy`, `cut`, `paste`, `undo`,
    `open|close`, and the `-format|-system|-sky ...` options before a file.
    """
    from ...regions.region_formats import RegionFormat

    controller = window.region
    words, options = _region_options([str(word) for word in args])
    if not words:
        if options:
            # `regions -format ds9 -system wcs` with no file: DS9 takes the
            # options as the new defaults.
            return _region_defaults(window, _listing_options(options))
        return "region needs a file or a command"

    first = words[0].lower()
    rest = words[1:]
    lowered = [word.lower() for word in rest]

    if first == "load":
        every = bool(lowered) and lowered[0] == "all"
        paths = rest[1:] if every else rest
        if not paths:
            return "a region file is needed"
        return _region_load(window, paths, options, every)

    if first == "save":
        selected = bool(lowered) and lowered[0] == "select"
        paths = rest[1:] if selected else rest
        if not paths:
            return "a file to save to is needed"
        regions = _region_subset(window, options, "select" if selected else None)
        if not regions:
            return "No regions to save"
        try:
            text = controller.render(regions, **_listing_options(options))
            from pathlib import Path

            Path(paths[0]).write_text(text + "\n", encoding="utf-8")
        except (OSError, ValueError) as exc:
            return f"Error saving regions: {exc}"
        return None

    if first == "list":
        if lowered and lowered[0] == "close":
            return None
        selected = bool(lowered) and lowered[0] == "select"
        controller._show_listing(
            controller.selection() if selected else controller._regions(),
            "Selected Regions" if selected else "Regions",
            modal=False,
        )
        return None

    if first == "delete":
        if lowered and as_bool(lowered[0]) is not None:
            return _region_flag(window, "delete", lowered[0])
        if lowered and lowered[0] == "select":
            controller.delete_selection()
            return None
        if lowered and lowered[0] == "load":
            if len(rest) < 2:
                return "a region file is needed"
            controller.clear_regions()
            return _region_load(window, rest[1:], options, False)
        controller.clear_regions()
        return None

    if first == "select":
        which = lowered[0] if lowered else "all"
        if which in ("all", "none", "invert"):
            getattr(controller, f"select_{which}")()
            return None
        if which in ("front", "back"):
            getattr(controller, "bring_front" if which == "front" else "send_back")()
            return None
        return "select takes all, none, invert, front or back"

    if first == "move":
        if not lowered or lowered[0] not in ("front", "back"):
            return "move takes front or back"
        getattr(controller, f"move_{lowered[0]}")()
        return None

    if first in ("show", "showtext"):
        wanted = as_bool(lowered[0]) if lowered else None
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
        from ...ui.widgets.region_overlay import RegionMode

        shape = " ".join(lowered)
        if not shape.endswith("point") and shape not in {mode.value for mode in RegionMode}:
            return f"{' '.join(rest)} is not a region shape"
        controller.set_shape(shape)
        return None

    if first == "color":
        if not rest:
            return "a colour is needed"
        controller.set_color(lowered[0])
        return None

    if first in ("width", "fontsize"):
        try:
            value = int(float(rest[0]))
        except (IndexError, ValueError):
            return f"{first} takes a number"
        (controller.set_width if first == "width" else controller.set_font_size)(value)
        return None

    if first == "font":
        if not rest:
            return "a font is needed"
        controller.set_font_family(lowered[0])
        return None

    if first in ("fontweight", "fontslant"):
        allowed = ("normal", "bold") if first == "fontweight" else ("roman", "italic")
        if not lowered or lowered[0] not in allowed:
            return f"{first} takes {' or '.join(allowed)}"
        font = str(controller.defaults.get("font", "helvetica 10 normal roman")).split()
        font += ["helvetica", "10", "normal", "roman"][len(font) :]
        font[2 if first == "fontweight" else 3] = lowered[0]
        controller._apply("font", " ".join(font[:4]), f"Region font: {' '.join(font[:4])}")
        return None

    if first in _REGION_FLAGS:
        return _region_flag(window, first, lowered[0] if lowered else "yes")

    if first in ("include", "exclude", "source", "background"):
        attribute = "include" if first in ("include", "exclude") else "source"
        controller._apply(attribute, first in ("include", "source"), f"Region {first}")
        return None

    if first == "format":
        if not rest:
            return "a format is needed"
        try:
            window.preferences.set("region_format", RegionFormat(lowered[0]).value)
        except ValueError:
            return f"{rest[0]} is not a region format"
        return None

    if first in ("system", "sky", "skyformat", "strip"):
        if not rest:
            return f"region {first} needs a value"
        return _region_defaults(window, _listing_options({first: rest[0]}))

    if first == "centroid":
        if lowered and lowered[0] == "auto":
            wanted = as_bool(lowered[1]) if len(lowered) > 1 else True
            if wanted is None:
                return "centroid auto takes yes or no"
            controller.set_auto_centroid(wanted)
            return None
        if lowered and lowered[0] in ("radius", "iteration"):
            try:
                value = float(lowered[1])
            except (IndexError, ValueError):
                return f"centroid {lowered[0]} takes a number"
            if lowered[0] == "radius":
                controller.centroid_radius = value
            else:
                controller.centroid_iterations = max(1, int(value))
            return None
        controller.centroid()
        return None

    if first == "group":
        return _region_group(window, rest)

    if first == "template":
        if not rest:
            return "a template file is needed"
        if len(lowered) > 1 and lowered[1] == "at":
            return "placing a template at a position is not implemented; it goes at the image centre"
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

    if first in ("copy", "cut", "paste", "undo"):
        if first == "undo":
            window.undo.undo()
        else:
            getattr(window.edit, first)()
        return None

    if first in ("open", "close"):
        if first == "open":
            controller._show_listing(controller._regions(), "Regions", modal=False)
        return None

    if first == "analysis":
        return "region analysis from XPA is not implemented; use the region's Analysis menu"

    if first in ("groups", "selected"):
        return f"region {first} is something to read, not to set"

    # A bare word is a file to load, which is DS9's first form.
    return _region_load(window, words, options, False)


def _region_defaults(window, settings: dict[str, object]) -> str | None:
    """Set how regions are written: `regions system wcs`, `-format xy`."""
    from ...coordinates import ds9_coords
    from ...regions.region_formats import RegionFormat

    controller = window.region
    if "region_format" in settings:
        try:
            window.preferences.set("region_format", RegionFormat(str(settings["region_format"])).value)
        except ValueError:
            return f"{settings['region_format']} is not a region format"
    system = settings.get("system")
    if system is not None:
        if not ds9_coords.is_system(str(system)):
            return f"{system} is not a coordinate system"
        controller.output["system"] = system
    sky = settings.get("sky")
    if sky is not None:
        if sky not in ds9_coords.SKY_FRAMES:
            return f"{sky} is not a sky frame"
        controller.output["sky"] = sky
    sky_format = settings.get("skyformat")
    if sky_format is not None:
        if sky_format not in ("degrees", "sexagesimal"):
            return f"{sky_format} is not degrees or sexagesimal"
        controller.output["skyformat"] = sky_format
    if "strip" in settings:
        controller.output["strip"] = bool(settings["strip"])
    return None


def _region_flag(window, name: str, value: str) -> str | None:
    """One of DS9's yes/no region properties: `dash yes`, `edit no`."""
    wanted = as_bool(value)
    if wanted is None:
        return f"{name} takes yes or no"
    window.region.set_property(_REGION_FLAGS[name], wanted)
    return None


def _region_load(window, paths: list[str], options: dict[str, str], every: bool) -> str | None:
    """Load region files, adding to what is there, as DS9's `load` does.

    `load '*.reg'` is expanded here, DS9 doing its own globbing; `load
    all` loads into every frame; `-format`, `-system` and `-sky` say what
    a file that does not declare them is written in.
    """
    import glob
    from pathlib import Path

    from ...coordinates.ds9_coords import CoordinateError
    from ...regions import region_coords
    from ...regions.region_parser import RegionParser

    files: list[str] = []
    for path in paths:
        found = sorted(glob.glob(path)) if any(char in path for char in "*?[") else [path]
        if not found:
            return f"no region file matches {path}"
        files.extend(found)

    system = options.get("system", "").lower()
    sky = options.get("sky", "").lower()
    lead = ""
    if sky:
        lead = sky
    elif system:
        lead = system
    frames = list(window.frame_manager.frames) if every else [window.frame_manager.current_frame]
    frames = [frame for frame in frames if frame is not None]
    if not frames:
        return "No frame to load regions into"

    for path in files:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"Error loading regions: {exc}"
        if options.get("format", "").lower() == "xy":
            text = "\n".join(
                f"point({','.join(line.split()[:2])})" for line in text.splitlines() if line.split()
            )
        if lead:
            text = f"{lead}\n{text}"
        for frame in frames:
            try:
                regions = region_coords.place(RegionParser().parse_string(text), frame)
            except CoordinateError as exc:
                return f"Error loading regions from {path}: {exc}"
            except Exception as exc:
                return f"Error loading regions: {exc}"
            with window.undo.regions("Load Regions"):
                frame.regions = [*frame.regions, *regions]
    window.region.show_frame_regions(window.frame_manager.current_frame)
    return None


def _region_group(window, words: list[str]) -> str | None:
    """DS9's `regions group ...`: `new`, `<tag> new|select|delete|cut|copy|
    color <c>|font <f>|move <dx> <dy>|movefront|moveback|property <p>
    yes|no|update`."""
    from ...regions import group_manager

    controller = window.region
    frame = window.frame_manager.current_frame
    if frame is None:
        return "no frame"
    regions = frame.regions
    lowered = [word.lower() for word in words]
    if not words:
        return "group needs new or a group name"
    if lowered[0] == "new":
        # DS9 names a new group itself; ours asked in a dialog, which an
        # XPA caller can never answer.
        chosen = controller.selection_only()
        if not chosen:
            return "select the regions to group first"
        group_manager.create(chosen, group_manager.default_name(regions))
        controller.refresh_overlay()
        return None

    tag, action, rest = words[0], (lowered[1] if len(words) > 1 else ""), words[2:]
    members = group_manager.regions_in(regions, tag)
    if action == "new":
        chosen = controller.selection_only()
        if not chosen:
            return "select the regions to group first"
        group_manager.create(chosen, tag)
    elif not members:
        return f"there is no group {tag}"
    elif action == "select":
        group_manager.select(regions, tag)
    elif action in ("delete", "cut"):
        with window.undo.regions(f"Delete Group {tag}"):
            frame.regions = [region for region in regions if region not in members]
        controller.show_frame_regions(frame)
    elif action == "color" and rest:
        for region in members:
            region.color = rest[0]
    elif action == "move" and len(rest) >= 2:
        try:
            dx, dy = float(rest[0]), float(rest[1])
        except ValueError:
            return "group move takes two numbers"
        for region in members:
            region.move(dx, dy)
    elif action in ("movefront", "moveback"):
        others = [region for region in regions if region not in members]
        frame.regions = [*others, *members] if action == "movefront" else [*members, *others]
    elif action == "property" and len(rest) >= 2:
        wanted = as_bool(rest[1])
        attribute = _REGION_FLAGS.get(rest[0].lower())
        if wanted is None or attribute is None:
            return f"group property takes one of {', '.join(_REGION_FLAGS)} and yes or no"
        for region in members:
            setattr(region, attribute, wanted)
    elif action == "update":
        pass
    else:
        return f"group {action} is not implemented"
    controller.refresh_overlay()
    return None


def _region_command(window, text: str) -> str | None:
    """Add regions written in DS9's own syntax, `region command ...`."""
    from ...coordinates.ds9_coords import CoordinateError

    if not text.strip():
        return "a region to add is needed"
    try:
        regions = window.region.read(text=_as_region_file(text.strip().strip("{}")))
    except CoordinateError as exc:
        return f"could not place that region: {exc}"
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


def _colour_frame_text(window, args: list[str]) -> str:
    """`xpaget ds9 rgb channel|system|view <c>|lock <what>`."""
    frame = window.frame_manager.current_frame
    words = [str(word).lower() for word in args]
    current = str(getattr(frame, "rgb_current_channel", "") or "")
    if not words or words[0] == "channel":
        return current
    if words[0] == "system":
        return "image"
    if words[0] == "lock":
        return NO
    if words[0] == "view" and len(words) > 1 and frame is not None and getattr(frame, "rgb_channels", None):
        key = _channel_keys(window, frame).get(words[1], words[1])
        return on_off(frame.rgb_view.get(key, True))
    raise ValueError(f"there is no {' '.join(words)} to read")


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
    # DS9 names the three planes per colour space -- `hsv value`, `hls
    # lightness` -- while they are stored under one set of keys. Both
    # spellings are accepted, since a script written for DS9 uses its
    # names and one written against our storage uses ours.
    channels = _channel_keys(window, frame)

    if first == "channel":
        if not rest:
            return None
        key = channels.get(rest[0].lower())
        if key is None:
            return f"{rest[0]} is not a channel: {', '.join(sorted(channels))}"
        return controller.set_channel(key)

    if first == "view":
        if not rest:
            return "view needs a channel"
        wanted = as_bool(rest[1]) if len(rest) > 1 else True
        if wanted is None:
            return "view takes yes or no"
        return _channel_view(window, rest[0].lower(), wanted)

    if first == "system":
        # DS9 aligns the channels through this system. Ours are always
        # aligned pixel for pixel, so only `image` is honest to accept;
        # this used to set a frame lock called `wcs`, which does not exist.
        if not rest:
            return "system needs a coordinate system"
        if rest[0].lower() == "image":
            return None
        return (
            f"aligning {kind} channels in {rest[0]} coordinates is not implemented; they align by image pixel"
        )

    if first == "lock":
        # DS9's `rgb lock scale yes` ties the three channels' settings
        # together; the channels here carry no lock of their own.
        return f"locking {kind} channels together is not implemented"

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


def _bin_table(window) -> dict[str, str]:
    """DS9's binning settings, as `xpaget ds9 bin <what>` answers them."""
    settings = window.bin.settings
    return {
        "about": "center",
        "buffersize": str(settings.buffer_size),
        "cols": " ".join(window.bin.columns.columns),
        "factor": f"{settings.factor:g} {settings.factor:g}",
        "depth": str(settings.depth),
        "filter": settings.filter,
        "function": settings.function.value,
        "lock": on_off(window.frame_controller.is_locked("bin")),
    }


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
            factors = [float(word) for word in rest[:2]]
        except ValueError:
            return "factor takes a number"
        if not factors:
            return "factor takes a number"
        if len(factors) == 2 and factors[0] != factors[1]:
            return "binning the two axes by different factors is not implemented"
        controller.set_factor(factors[0])
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


def _catalog_text(window, args: list[str]) -> str:
    """What `xpaget ds9 catalog` answers.

    DS9 reads back the current catalogue's name, its filter, its row and
    column limits, and the rows themselves; a bare read lists what is
    loaded, which is the thing a script most often wants to know.
    """
    controller = window.catalog
    loaded = controller.catalogs.catalogs
    what = args[0].lower() if args else ""

    if not what:
        return "\n".join(f"{entry.name} {len(entry)}" for entry in loaded)
    if not loaded:
        return ""
    current = loaded[-1]

    if what == "current":
        return current.name
    if what == "filter":
        return current.filter_expression
    if what == "header":
        return " ".join(current.columns)
    if what in ("maxrows", "location", "psky", "psystem", "sky", "skyformat", "system"):
        return str(window.catalog.settings.get(what, ""))
    if what in ("ra", "dec"):
        from ...catalogs import catalog_query

        columns = catalog_query.coordinate_columns(current.table)
        if columns is None:
            return ""
        return columns[0] if what == "ra" else columns[1]
    if what == "export":
        from ...catalogs import catalog_file

        return catalog_file.to_text(current.filtered())
    return current.name


def _catalog(window, args: list[str]) -> str | None:
    """DS9's `catalog`, over the catalogue tool.

    `[<server>] [cds <name>] [new] [load <file>] [import <format> <file>]
    [export <format> <file>] [filter <expression>|clear] [clear] [close]
    [current <name>] [match ...] [maxrows <n>] [regions] [save <file>]
    [symbol ...] [update] [sky|system|skyformat ...]`.

    DS9's own search window and its per-column editing are its dialog's
    business; where a rule belongs to the window rather than to the
    catalogue, this says so.
    """
    from ...catalogs import catalog_file

    controller = window.catalog
    words = [str(word) for word in args]
    if not words:
        controller.show_tool()
        return None

    first = words[0].lower()
    rest = words[1:]
    loaded = controller.catalogs.catalogs
    current = loaded[-1] if loaded else None

    if first == "new":
        # DS9 opens an empty search window; ours opens the search dialog,
        # which is the same starting point.
        controller.search()
        return None
    if first == "close":
        for window_ in list(controller._windows.values()):
            window_.close()
        return None
    if first == "clear":
        controller.clear_all()
        return None
    if first == "cancel":
        return None
    if first == "update":
        controller.refresh_overlay()
        return None
    if first == "crosshair":
        return "catalog crosshair belongs to DS9's search window, which sets a position"

    if first == "load":
        if not rest:
            return "a catalogue file is needed"
        return None if controller.load_file(rest[0]) else f"{rest[0]} could not be loaded"
    if first == "import":
        # `import <format> <file>`; the loader detects the format anyway.
        if len(rest) < 2:
            return "a format and a file are needed"
        return None if controller.load_file(rest[1]) else f"{rest[1]} could not be loaded"
    if first in ("save", "export"):
        if current is None:
            return "no catalogue is loaded"
        path = rest[-1] if rest else ""
        if not path:
            return "a file to write is needed"
        try:
            catalog_file.save(path, current.filtered())
        except (catalog_file.CatalogFileError, OSError) as exc:
            return f"could not write {path}: {exc}"
        return None

    if first == "filter":
        if rest and rest[0].lower() == "clear":
            current and setattr(current, "filter_expression", "")
        elif rest and rest[0].lower() == "load":
            return "catalog filter load reads DS9's own filter file, which we do not write"
        elif current is not None:
            current.filter_expression = " ".join(rest)
        controller.refresh_overlay()
        return None

    if first == "current":
        if not rest:
            return "a catalogue name is needed"
        return None if controller.catalogs.by_name(rest[0]) else f"no catalogue called {rest[0]}"

    if first == "regions":
        if current is None:
            return "no catalogue is loaded"
        controller.to_regions(current)
        return None

    if first == "match":
        return _catalog_match(window, rest)

    if first in ("maxrows", "location", "sky", "skyformat", "system", "psky", "psystem"):
        controller.settings[first] = " ".join(rest) if rest else ""
        return None

    if first in ("allrows", "allcols", "header", "panto", "edit", "symbol", "plot", "print", "sort"):
        return f"catalog {first} belongs to the catalogue window, which has it on its own menus"

    if first in ("ra", "dec"):
        return f"catalog {first} names a column, which the loader finds from the table's own units"

    if first == "cds":
        if not rest:
            return "a CDS catalogue is needed"
        return None if controller.query_identifier(rest[0].strip("{}")) else f"{rest[0]} returned nothing"

    if first == "coordinate":
        return "catalog coordinate sets DS9's search position; ours searches about the frame"

    if first == "name":
        return "catalog name resolves an object for DS9's search window; use `nameserver`"

    # A bare word is one of DS9's catalogue names.
    return None if controller.query(first) else f"{first} returned nothing"


def _catalog_match(window, args: list[str]) -> str | None:
    """DS9's `catalog match`, which has settings of its own."""
    controller = window.catalog
    settings = controller.settings
    words = [str(word) for word in args]

    if words and words[0].lower() in ("error", "function", "unique", "return"):
        if len(words) < 2:
            return f"match {words[0]} needs a value"
        settings[f"match_{words[0].lower()}"] = " ".join(words[1:])
        return None

    names = [word for word in words if word.lower() not in ("error", "function", "unique", "return")]
    if len(names) < 2:
        loaded = controller.catalogs.catalogs
        if len(loaded) < 2:
            return "two loaded catalogues are needed to match"
        names = [loaded[-2].name, loaded[-1].name]

    radius = settings.get("match_error", "").split()
    try:
        arcsec = float(radius[0]) if radius else 2.0
    except ValueError:
        arcsec = 2.0
    if len(radius) > 1 and radius[1].lower().startswith("arcmin"):
        arcsec *= 60.0
    elif len(radius) > 1 and radius[1].lower().startswith("deg"):
        arcsec *= 3600.0

    matched = controller.match(
        names[0],
        names[1],
        arcsec,
        settings.get("match_function", "1and2"),
        settings.get("match_return", "1and2"),
        as_bool(settings.get("match_unique", "yes")) is not False,
    )
    return None if matched else "the two catalogues did not match"


def _footprint(window, args: list[str]) -> str | None:
    """DS9's `footprint`: what observations cover this field.

    They load as catalogues here, filterable and listable like any other,
    and their outlines are drawn as polygon regions -- which is what DS9's
    `fpreg.tcl` does with them -- so the rules a footprint shares with a
    catalogue go to the same place.
    """
    from ...catalogs import footprints

    words = [str(word) for word in args]
    if not words:
        return "a footprint server is needed: " + ", ".join(s.name for s in footprints.SERVERS)

    first = words[0].lower()
    if footprints.by_name(first) is not None:
        return None if window.catalog.query_footprints(first) else f"{first} returned nothing"
    if first == "clear":
        window.catalog.clear_footprints()
        return None
    return _catalog(window, words)


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
    """`crosshair <x> <y> [<coordsys> [<skyframe>]]`, `lock <coordsys>|none`
    or `match <coordsys>`.

    The position is read in the system named, as DS9 reads it: `crosshair
    345 58.8 wcs fk5` used to put the crosshair at *pixel* (345, 58.8),
    and a sexagesimal position was refused. DS9 also switches to crosshair
    mode when the crosshair is set, which this now does too.
    """
    words = [str(word) for word in args]
    if words and words[0].lower() == "lock":
        system = words[1].lower() if len(words) > 1 else "wcs"
        # Through the frame lock, so `xpaget ds9 lock crosshair` agrees.
        window.frame_controller.set_lock_scope("crosshair", system)
        return None
    if words and words[0].lower() == "match":
        window.crosshair.match(words[1].lower() if len(words) > 1 else "wcs")
        return None
    placed = _image_position(window, words)
    if isinstance(placed, str):
        return placed
    if window.edit_mode != "crosshair":
        window.edit.set_mode("crosshair")
    window.crosshair.move_to(*placed)
    return None


def _image_position(window, words: list[str]) -> tuple[float, float] | str:
    """`<x> <y> [<coordsys> [<skyframe>]]`, as FITS image coordinates.

    Returns:
        The position, or a message saying what was wrong with it.
    """
    from ...coordinates import ds9_coords

    values, system, sky, _format, _unit = ds9_coords.split_system(words)
    if len(values) < 2:
        return "an x and a y are needed"
    try:
        a, b = ds9_coords.parse_position(values[0], values[1], system, sky)
        return ds9_coords.to_image(window.frame_manager.current_frame, a, b, system, sky)
    except ds9_coords.CoordinateError as exc:
        return f"cannot place a {system} position: {exc}"
    except ValueError:
        return f"{values[0]} {values[1]} is not a position"


def _position_text(window, x: float, y: float, words: list[str]) -> str:
    """FITS image coordinates, in the system `words` names -- DS9's
    `[<coordsys> [<skyframe>] [<skyformat>]]`, physical by default."""
    from ...coordinates import ds9_coords

    _values, system, sky, sky_format, _unit = ds9_coords.split_system(words)
    frame = window.frame_manager.current_frame
    try:
        a, b = ds9_coords.from_image(frame, x, y, system, sky)
    except ds9_coords.CoordinateError:
        return f"{x:g} {y:g}"
    if not ds9_coords.is_sky_system(system):
        return f"{a:g} {b:g}"
    return ds9_coords.format_position(a, b, "wcs", sky, sky_format)


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
