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
The WCS menu: which coordinate system positions are reported in.

The settings themselves live in `coordinates.CoordinateContext`, which also
does the transforming and formatting; this controller only drives it from the
menu and keeps the readout in step.

DS9's menu has three independent choices (`CoordMenu` in `menu.tcl`): the
system -- `wcs`, or one of the alternate descriptions `wcsa`..`wcsz` a FITS
header may carry -- the sky frame and the sky format. The system decides
which WCS the readouts, the grid and the compass report through; the frame's
primary WCS stays what matching, catalogues and alignment compute with.

This controller also owns the frame's WCS itself, as DS9's `wcs` command
does: replacing it (`WCS Parameters -> Apply`, `wcs replace foo.wcs`),
appending to it, saving it and resetting it to the file's own. And it is
where DS9's `wcs` grammar is read, once, for both XPA and the command line
(`command`, `report`).

Image, physical, amplifier and detector as display systems are still to
come (PLAN.md §5.11); DS9's main WCS menu does not offer them either.

Direction arrows are a deliberate NCRADS9 addition, not a DS9 feature
(PLAN.md §7).

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import astropy.units as u
from astropy.coordinates import ICRS, SkyCoord

from ...core import wcs_keywords
from ...core.wcs_handler import WCSHandler, available_alternates
from ..view_transform import DisplayTransform
from .base import Controller

#: Menu action suffix -> the sky frame token it selects.
SKY_ACTIONS: tuple[str, ...] = ("fk5", "fk4", "icrs", "galactic", "ecliptic")

#: Menu action suffix -> the format token it selects.
FORMAT_ACTIONS: tuple[str, ...] = ("sexagesimal", "degrees")

#: DS9's system tokens: the primary WCS and its twenty-six alternates.
SYSTEMS: tuple[str, ...] = ("wcs", *(f"wcs{letter}" for letter in wcs_keywords.ALTERNATE_LETTERS))

#: DS9's sky frame tokens, with the two aliases its parser accepts
#: (`skyframe.trl`).
SKY_TOKENS: dict[str, str] = {
    "fk4": "fk4",
    "b1950": "fk4",
    "fk5": "fk5",
    "j2000": "fk5",
    "icrs": "icrs",
    "galactic": "galactic",
    "ecliptic": "ecliptic",
}

#: Offset used to find north and east on the sky for the direction arrows.
ARROW_SEPARATION = 1.0 * u.arcmin

_YES = frozenset({"yes", "on", "true", "1"})
_NO = frozenset({"no", "off", "false", "0"})


def command_length(words: list[str]) -> int:
    """How many of `words` DS9's `wcs` grammar would take.

    The command line has no delimiter between `-wcs`'s arguments and the
    file names after them -- `ncrads9 -wcs galactic m51.fits` -- so the
    parser needs to know where the command stops, without running it. This
    reads the same grammar as `WCSController.command` and stops at the
    first word that does not belong.
    """
    index = 0
    while index < len(words):
        word = str(words[index]).lower()
        following = str(words[index + 1]).lower() if index + 1 < len(words) else None
        if word in ("open", "close") or word in SYSTEMS or word in SKY_TOKENS or word in FORMAT_ACTIONS:
            index += 1
        elif (
            (word == "system" and following in SYSTEMS)
            or (word == "sky" and following in SKY_TOKENS)
            or (word == "skyformat" and following in FORMAT_ACTIONS)
            or (word == "align" and following in _YES | _NO)
            or (word == "load" and following is not None)
        ):
            index += 2
        elif word == "reset":
            index += 2 if following is not None and following.isdigit() else 1
        elif word in ("replace", "append", "save"):
            index += 1
            if following is not None and following.isdigit() and index + 1 < len(words):
                index += 1
            if index < len(words):
                index += 1
        else:
            break
    return index


class WCSController(Controller):
    """Owns the WCS menu and the current frame's WCS."""

    def __init__(self, window) -> None:
        super().__init__(window)
        #: The WCS Parameters window, while one is open.
        self.dialog = None
        #: Which frame and WCS the dialog last showed, so a `sync` that
        #: changes neither leaves the user's half-typed edits alone.
        self._dialog_source: tuple[int, int] | None = None

    def connect(self) -> None:
        """Wire the WCS menu."""
        for system, action in self.menu.wcs_system_actions.items():
            action.triggered.connect(lambda _checked=False, s=system: self.set_system(s))

        for name in SKY_ACTIONS:
            action = getattr(self.menu, f"action_wcs_{name}")
            action.triggered.connect(lambda _checked=False, s=name: self.set_sky_frame(s))

        for name in FORMAT_ACTIONS:
            action = getattr(self.menu, f"action_wcs_{name}")
            action.triggered.connect(lambda _checked=False, f=name: self.set_format(f))

        self.menu.action_wcs_parameters.triggered.connect(self.show_dialog)
        self.menu.action_show_direction_arrows.triggered.connect(self.set_direction_arrows_visible)

    def sync(self) -> None:
        """Tick the entries matching the current coordinate settings.

        The letters the current frame's header does not carry are greyed
        out. DS9 leaves all twenty-six live, which offers choices that can
        only blank the readout; the one ticked stays enabled so the menu
        still says what is selected.
        """
        system = self.coords.system
        present = set(available_alternates(self._header()))
        for name, action in self.menu.wcs_system_actions.items():
            action.setChecked(name == system)
            if name != "wcs":
                action.setEnabled(name[3:] in present or name == system)
        for name in SKY_ACTIONS:
            getattr(self.menu, f"action_wcs_{name}").setChecked(self.coords.sky.value == name)
        for name in FORMAT_ACTIONS:
            getattr(self.menu, f"action_wcs_{name}").setChecked(self.coords.sky_format.value == name)
        self._sync_dialog()

    # -- coordinate settings -------------------------------------------------

    def set_system(self, system: str) -> None:
        """Report coordinates through one of the header's WCS descriptions.

        Args:
            system: `wcs` for the primary, `wcsa`..`wcsz` for an alternate.

        Raises:
            ValueError: For any other token.
        """
        self.window.coord_context = self.coords.with_system(system)
        self.sync()
        frame = self.frame
        if frame is not None and frame.has_data and not self._has_wcs:
            self.status(f"WCS system: {system} (this image has none)")
        else:
            self.status(f"WCS system: {system}")
        self.refresh_dependents()

    def set_sky_frame(self, system: str) -> None:
        """Report coordinates in the given sky frame.

        Args:
            system: One of fk4, fk5, icrs, galactic, ecliptic.
        """
        self.window.coord_context = self.coords.with_sky(system)
        self.sync()
        self.status(f"WCS system: {system.upper()}")
        self.refresh_readout()
        self.update_direction_arrows()
        self._refresh_grid()

    def set_format(self, format_type: str) -> None:
        """Write coordinates as sexagesimal or as decimal degrees.

        Args:
            format_type: Either "sexagesimal" or "degrees".
        """
        self.window.coord_context = self.coords.with_format(format_type)
        self.sync()
        self.status(f"WCS format: {format_type}")
        self.refresh_readout()
        self._refresh_grid()

    # -- readout -------------------------------------------------------------

    @property
    def handler(self) -> WCSHandler | None:
        """The current frame's WCS for the system on the WCS menu.

        `MainWindow.wcs_handler` is always the primary description, which is
        what matching, catalogues and the rest compute with. This is the one
        the user asked to *see* -- `wcs`, or `wcsa`..`wcsz` from `WCS ->
        Multiple WCS` -- and what the readouts, the grid, the compass and the
        XPA reports go through.
        """
        frame = self.frame
        if frame is None:
            return None
        return frame.wcs_for(self.coords.wcs_key)

    @property
    def _has_wcs(self) -> bool:
        """True when the current frame carries the WCS the menu selects."""
        handler = self.handler
        return handler is not None and handler.is_valid

    def refresh_readout(self) -> None:
        """Re-render the coordinate readout at the last cursor position."""
        if self.window._last_mouse_pos is not None:
            self.update_readout(*self.window._last_mouse_pos)

    def update_readout(self, x: int, y: int) -> None:
        """Show the sky position of one image pixel in the status bar.

        Through the WCS the menu selects, and blank when the frame has none
        rather than leaving the previous position on show.
        """
        if not self._has_wcs:
            self.status_bar.update_wcs_coords(None)
            return
        ra, dec = self.handler.pixel_to_icrs(x, y)
        self.status_bar.update_wcs_coords(self.coords.describe_sky(float(ra), float(dec)))

    def refresh_dependents(self) -> None:
        """Bring everything drawn or reported through the WCS up to date.

        DS9's `UpdateWCS`: the readout, the information panel, the grid, the
        compass, WCS alignment and the regions all follow a change of system
        or of the WCS itself.
        """
        self.refresh_readout()
        position = getattr(self.window, "_last_mouse_pos", None)
        view = getattr(self.window, "view", None)
        if position is not None and view is not None and hasattr(view, "update_cursor"):
            view.update_cursor(*position)
        self.update_direction_arrows()
        self._refresh_grid()
        frame = self.frame
        if frame is not None and frame.align_wcs:
            self.window.frame_controller.apply_locks()
        region = getattr(self.window, "region", None)
        if frame is not None and region is not None and hasattr(region, "refresh_overlay"):
            region.refresh_overlay()

    def _refresh_grid(self) -> None:
        """Redraw the coordinate grid, which is drawn through the system's WCS."""
        analysis = getattr(self.window, "analysis", None)
        if analysis is not None and hasattr(analysis, "refresh_grid"):
            analysis.refresh_grid()

    # -- the frame's WCS: DS9's `wcs replace|append|reset|save` ----------------

    def _header(self):
        """The current frame's header, or None."""
        frame = self.frame
        if frame is None:
            return None
        if frame.header is not None:
            return frame.header
        return getattr(frame.fits_handler, "header", None)

    def current_wcs_values(self) -> dict[str, str]:
        """The current frame's WCS keywords, as keyword -> text."""
        return wcs_keywords.header_values(self._header())

    def current_wcs_text(self) -> str:
        """The current frame's WCS keywords, as a `.wcs` file holds them."""
        return wcs_keywords.format_wcs_text(self._header())

    def replace_wcs(self, values: str | Mapping, append: bool = False) -> str | None:
        """Give the current frame a new WCS, or add to the one it has.

        The first change keeps the file's own WCS on the frame, which is what
        `reset_wcs` puts back.

        Args:
            values: The keywords -- `.wcs` text, a keyword -> value mapping
                or a header.
            append: Add the keywords rather than replacing the whole WCS,
                DS9's `wcs append`.

        Returns:
            None on success, otherwise why not.
        """
        frame = self.require_frame()
        if frame is None:
            return "no image is loaded"
        if isinstance(values, str):
            values = wcs_keywords.parse_wcs_text(values)
        if not values:
            return "no WCS keywords found"
        header = self._header()
        if frame.wcs_original is None:
            frame.wcs_original = wcs_keywords.extract_wcs(header)
        if append:
            updated = wcs_keywords.append_wcs(header, values)
        else:
            updated = wcs_keywords.replace_wcs(header, values)
        self._install(frame, updated)
        self.status("WCS appended" if append else "WCS replaced")
        return None

    def reset_wcs(self) -> str | None:
        """Put back the WCS the frame was loaded with, DS9's `wcs reset`."""
        frame = self.require_frame()
        if frame is None:
            return "no image is loaded"
        if frame.wcs_original is not None:
            updated = wcs_keywords.replace_wcs(self._header(), frame.wcs_original, dates=True)
            frame.wcs_original = None
            self._install(frame, updated)
        self.status("WCS reset")
        return None

    def load_wcs_file(self, path: str | Path, append: bool = False) -> str | None:
        """Replace, or append to, the frame's WCS from a `.wcs` file."""
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"unable to open {path}: {exc.strerror or exc}"
        return self.replace_wcs(text, append=append)

    def save_wcs_file(self, path: str | Path) -> str | None:
        """Write the frame's current WCS keywords to a `.wcs` file.

        DS9's `WCSSaveDialog` writes the frame's WCS, not what is typed on
        the dialog; Apply first to save an edit.
        """
        frame = self.require_frame()
        if frame is None:
            return "no image is loaded"
        try:
            Path(path).write_text(self.current_wcs_text(), encoding="utf-8")
        except OSError as exc:
            return f"unable to write {path}: {exc.strerror or exc}"
        self.status(f"Saved WCS to {Path(path).name}")
        return None

    def _install(self, frame, header) -> None:
        """Make `header` the frame's, rebuild its WCS and redraw.

        The new primary handler also retires the cached alternates
        (`Frame.wcs_for`), so every letter is read afresh.
        """
        frame.header = header
        image = getattr(frame, "image", None)
        if image is not None and hasattr(image, "header"):
            image.header = header
            if hasattr(image, "wcs"):
                try:
                    from astropy.wcs import WCS

                    image.wcs = WCS(header)
                except Exception:
                    image.wcs = None
        try:
            frame.wcs_handler = WCSHandler(header)
        except Exception:
            frame.wcs_handler = WCSHandler(None)
        self.sync()
        self.refresh_dependents()
        self._sync_dialog(force=True)

    # -- the WCS Parameters window -------------------------------------------

    def show_dialog(self):
        """Open DS9's WCS Parameters window, or raise the one already up."""
        from ..dialogs.wcs_dialog import WCSDialog

        if self._dialog_open():
            self.dialog.raise_()
            self.dialog.activateWindow()
            return self.dialog
        dialog = WCSDialog(self, self.window)
        dialog.set_system(self.coords.system)
        self.dialog = self.show_window(dialog)
        self._sync_dialog(force=True)
        return self.dialog

    def close_dialog(self) -> None:
        """Close the WCS Parameters window, if it is open."""
        if self._dialog_open():
            self.dialog.close()
        self.dialog = None
        self._dialog_source = None

    def _dialog_open(self) -> bool:
        """Whether the WCS Parameters window is on screen."""
        if self.dialog is None:
            return False
        try:
            return bool(self.dialog.isVisible())
        except RuntimeError:
            # Qt has already deleted it.
            self.dialog = None
            return False

    def _sync_dialog(self, force: bool = False) -> None:
        """Show the current frame's WCS in the dialog, once it has changed."""
        if not self._dialog_open():
            return
        frame = self.frame
        source = (getattr(frame, "frame_id", -1), id(getattr(frame, "wcs_handler", None)))
        if force or source != self._dialog_source:
            self._dialog_source = source
            self.dialog.load_values(self.current_wcs_values())

    # -- DS9's `wcs` command ---------------------------------------------------

    def report(self, words: list[str]) -> str:
        """Answer DS9's `xpaget ds9 wcs [system|sky|skyformat|align]`.

        Raises:
            ValueError: For anything else.
        """
        what = words[0].lower() if words else "system"
        if what == "system":
            return self.coords.system
        if what == "sky":
            return self.coords.sky.value
        if what == "skyformat":
            return self.coords.sky_format.value
        if what == "align":
            frame = self.frame
            return "yes" if frame is not None and frame.align_wcs else "no"
        raise ValueError(f"wcs: unknown query '{words[0]}'")

    def command(self, words: list[str], data: str | None = None) -> str | None:
        """Run DS9's `wcs` command (`wcsparser.tac`), for XPA and `-wcs`.

        `wcs [[system] wcs|wcsa..wcsz] [[sky] fk4|fk5|icrs|galactic|ecliptic]
        [[skyformat] degrees|sexagesimal] [align yes|no] [reset] [load <file>]
        [replace [<int>] [<file>]] [append [<int>] [<file>]]
        [save [<int>] <file>] [open|close]`

        DS9's parser takes one of these per command; this takes them in
        sequence, so `wcs galactic degrees` does both, as the bracketed
        synopsis in DS9's reference reads. The extension number DS9 allows
        on `replace`, `append`, `save` and `reset` picks a mosaic segment;
        a frame here holds one, so it is accepted and has no effect.

        Args:
            words: The arguments after `wcs`.
            data: What `xpaset` sent on its standard input, which `replace`
                and `append` read when they are not given a file.

        Returns:
            None on success, otherwise a message saying what was wrong.
        """
        index = 0
        while index < len(words):
            word = str(words[index]).lower()
            index += 1
            following = str(words[index]).lower() if index < len(words) else None
            problem: str | None = None

            if word == "open":
                self.show_dialog()
            elif word == "close":
                self.close_dialog()
            elif word == "system" or word in SYSTEMS:
                if word == "system":
                    if following not in SYSTEMS:
                        return f"wcs system: expected wcs or wcsa..wcsz, not {following!r}"
                    word, index = following, index + 1
                self.set_system(word)
            elif word == "sky" or word in SKY_TOKENS:
                if word == "sky":
                    if following not in SKY_TOKENS:
                        return f"wcs sky: expected fk4, fk5, icrs, galactic or ecliptic, not {following!r}"
                    word, index = following, index + 1
                self.set_sky_frame(SKY_TOKENS[word])
            elif word == "skyformat" or word in FORMAT_ACTIONS:
                if word == "skyformat":
                    if following not in FORMAT_ACTIONS:
                        return f"wcs skyformat: expected degrees or sexagesimal, not {following!r}"
                    word, index = following, index + 1
                self.set_format(word)
            elif word == "align":
                if following not in _YES | _NO:
                    return f"wcs align: expected yes or no, not {following!r}"
                index += 1
                self.window.zoom.set_align_wcs(following in _YES)
                self.refresh_dependents()
            elif word == "reset":
                if following is not None and following.isdigit():
                    index += 1
                problem = self.reset_wcs()
            elif word == "load":
                if following is None:
                    return "wcs load: a file name is required"
                problem = self.load_wcs_file(words[index])
                index += 1
            elif word in ("replace", "append"):
                if following is not None and following.isdigit():
                    index += 1
                if index < len(words):
                    problem = self.load_wcs_file(words[index], append=word == "append")
                    index += 1
                elif data:
                    problem = self.replace_wcs(data, append=word == "append")
                else:
                    return f"wcs {word}: a file name or WCS keywords are required"
            elif word == "save":
                if following is not None and following.isdigit() and index + 1 < len(words):
                    index += 1
                if index >= len(words):
                    return "wcs save: a file name is required"
                problem = self.save_wcs_file(words[index])
                index += 1
            else:
                return f"wcs: unknown argument '{words[index - 1]}'"
            if problem:
                return problem
        return None

    # -- direction arrows ----------------------------------------------------

    def set_direction_arrows_visible(self, visible: bool) -> None:
        """Show or hide the north/east compass overlay."""
        self.window._show_direction_arrows = visible
        self.update_direction_arrows()

    def update_direction_arrows(self) -> None:
        """Recompute the north and east arrows from the frame's WCS.

        The arrows point along increasing declination and increasing right
        ascension at the image centre, then go through the same display
        transform as the image so they stay correct under rotation and flips.

        The result goes to the panner, which is where DS9 draws its compass,
        and -- only while `WCS -> Show Direction Arrows` is ticked -- over the
        image as well. NCRADS9 used to draw them over the image alone, on top
        of the data; that is now off by default (M3-9).
        """
        vectors = self._compass_vectors()
        if vectors is None:
            self._publish_compass(None, None, False)
            return
        self._publish_compass(*vectors, True)

    def _compass_vectors(self) -> tuple[tuple[float, float], tuple[float, float]] | None:
        """North and east as display-space vectors, or None if unavailable.

        Through the WCS the menu selects, and in ICRS whatever frame that
        WCS is written in, so a galactic alternate still points at
        equatorial north as the primary does.
        """
        data = self.window.image_data
        if self.window._tile_mode_enabled or not self._has_wcs or data is None:
            return None

        handler = self.handler
        height, width = data.shape[:2]
        cx = (width - 1) / 2.0
        cy = (height - 1) / 2.0

        ra, dec = handler.pixel_to_icrs(cx, cy)
        center = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=ICRS())
        north = center.directional_offset_by(0.0 * u.deg, ARROW_SEPARATION)
        east = center.directional_offset_by(90.0 * u.deg, ARROW_SEPARATION)
        nx, ny = handler.icrs_to_pixel(north.ra.deg, north.dec.deg)
        ex, ey = handler.icrs_to_pixel(east.ra.deg, east.dec.deg)

        frame = self.frame
        transform = DisplayTransform(
            width=width,
            height=height,
            rotation=frame.rotation if frame is not None else 0.0,
            flip_x=frame.flip_x if frame is not None else False,
            flip_y=frame.flip_y if frame is not None else False,
        )
        return (
            transform.source_vector_to_display(float(nx - cx), float(ny - cy)),
            transform.source_vector_to_display(float(ex - cx), float(ey - cy)),
        )

    def _publish_compass(
        self,
        north: tuple[float, float] | None,
        east: tuple[float, float] | None,
        valid: bool,
    ) -> None:
        """Send the compass to the panner, and to the image if asked for."""
        panner = getattr(self.window, "panner_panel", None)
        if panner is not None:
            panner.set_compass(north, east, valid)
        if hasattr(self.viewer, "set_direction_arrows"):
            on_image = valid and self.window._show_direction_arrows
            self.viewer.set_direction_arrows(north, east, on_image)
