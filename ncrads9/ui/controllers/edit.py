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
The Edit menu: pointer mode, clipboard, and preferences.

DS9's Edit menu is mostly a pointer-mode radio group -- none, region,
crosshair, colorbar, pan, zoom, rotate, crop, catalog, footprint, examine, 3d,
illustrate -- of which NCRADS9 implements none and region. Those arrive with
the features they drive: crosshair and examine in M9-1 and M9-4, colorbar mode
in M5-13, crop in M9-2.

Cut, copy and paste act on the selected region, which is what they do in DS9.
Undo and redo need the command stack in M9-24; until then they report that
they do nothing rather than pretending otherwise.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import copy
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from ...regions.base_region import BaseRegion
from ...rendering.scale_algorithms import ScaleAlgorithm
from ..dialogs.preferences_dialog import PreferencesDialog
from ..themes.dark import DarkTheme
from ..themes.default import DefaultTheme
from ..themes.native import NativeTheme
from .base import Controller

#: Preference key -> default, and the full set the dialog round-trips.
PREFERENCE_DEFAULTS: dict[str, object] = {
    "use_gpu": True,
    "tile_size": 512,
    "cache_size_mb": 1000,
    "background_color": "#000000",
    #: DS9's Blank/Inf/NaN colour (`pds9(nan)` in `ds9.tcl:157`), which is
    #: also what a cropped-out pixel is painted in.
    "nan_color": "#ffffff",
    "default_scale": "Linear",
    "default_colormap": "gray",
    "anti_aliasing": True,
    "theme": "System",
    #: Ask which HDU to load when a file has more than one displayable one.
    #: DS9 never asks; see ui/dialogs/open_dialog.py.
    "prompt_for_hdu": True,
}

#: Image pixels a pasted region is shifted by, so it does not hide the
#: original it was copied from.
PASTE_OFFSET = 10.0

#: Pointer modes that are recorded but do nothing yet, and the milestone
#: that gives each an effect. `none`, `region`, `crosshair` and `colorbar`
#: are live.
DEFERRED_MODES: dict[str, str] = {}

#: Where the applied theme's name is kept, so re-applying can be skipped.
THEME_PROPERTY = "ncrads9_theme"

#: Preferences-dialog theme name -> the theme class. The three theme modules
#: existed since before M0 and nothing ever called them; M3-8 wires them up.
THEMES: dict[str, type] = {
    "System": NativeTheme,
    "Light": DefaultTheme,
    "Dark": DarkTheme,
}

#: Preference name for a scale algorithm -> the algorithm.
DEFAULT_SCALES: dict[str, ScaleAlgorithm] = {
    "Linear": ScaleAlgorithm.LINEAR,
    "Log": ScaleAlgorithm.LOG,
    "Sqrt": ScaleAlgorithm.SQRT,
    "Power": ScaleAlgorithm.POWER,
    "Asinh": ScaleAlgorithm.ASINH,
}


class EditController(Controller):
    """Owns the Edit menu."""

    def __init__(self, window) -> None:
        super().__init__(window)
        #: The region held by Cut or Copy, ready for Paste. One deep, as DS9's
        #: is; a full clipboard history would need the M9-24 command stack.
        self._clipboard: BaseRegion | None = None

    def connect(self) -> None:
        """Wire the Edit menu."""
        self.menu.action_preferences.triggered.connect(self.show_preferences)
        self.menu.action_cut.triggered.connect(self.cut)
        self.menu.action_copy.triggered.connect(self.copy)
        self.menu.action_paste.triggered.connect(self.paste)

        for name, action in self.menu.edit_mode_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.set_mode(key))

    def sync(self) -> None:
        """Tick the pointer mode in force."""
        for name, action in self.menu.edit_mode_actions.items():
            action.setChecked(name == self.window.edit_mode)

    # -- pointer modes -------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        """Set what a drag on the image does.

        Args:
            mode: One of `MenuBar.edit_mode_actions`' keys.
        """
        if mode not in self.menu.edit_mode_actions:
            self.status(f"Unknown edit mode: {mode}", 3000)
            return

        self.window.edit_mode = mode
        self.sync()

        # Every mode but these three is carried out by the pointer
        # controller, which arms the handler the overlay dispatches to.
        self.window.pointer.set_mode(mode)
        if mode != "crosshair":
            self.window.crosshair.set_enabled(False)
        # The illustrate layer takes the mouse only in its own mode, so
        # clicking the image elsewhere is not caught by an invisible drawing.
        self.window.illustrate.set_editing(mode == "illustrate")

        if mode == "region":
            # Region mode is the drawing mode the Region menu already sets;
            # leaving the shape alone means switching to Region mode keeps
            # whatever shape was last chosen.
            self.status("Edit mode: region")
            return
        if mode == "crosshair":
            # Placed in the middle if it has never been placed, so the mode
            # does something the moment it is chosen.
            self.window.crosshair.set_enabled(True)
            self.status("Edit mode: crosshair -- click to place the crosshair")
            return
        if mode == "illustrate":
            self.status("Edit mode: illustrate -- drag to draw, click to select")
            return
        if mode == "3d":
            self.status("Edit mode: 3D -- drag to turn the cube")
            return

        milestone = DEFERRED_MODES.get(mode)
        if milestone is not None:
            self.status(f"{mode.title()} mode arrives in {milestone}", 3000)
            return
        self.status(f"Edit mode: {mode}")

    # -- clipboard -----------------------------------------------------------

    @property
    def clipboard(self) -> BaseRegion | None:
        """The region waiting to be pasted, if any."""
        return self._clipboard

    def _selected_region(self) -> BaseRegion | None:
        """The region the user has selected on the overlay, if any."""
        overlay = getattr(self.viewer, "region_overlay", None)
        return None if overlay is None else overlay.selected_region

    def copy(self) -> None:
        """Copy the selected region to the clipboard."""
        region = self._selected_region()
        if region is None:
            self.status("No region selected")
            return
        self._clipboard = copy.deepcopy(region)
        self._clipboard.selected = False
        self.status(f"Copied {type(region).__name__.lower()} region")

    def cut(self) -> None:
        """Copy the selected region to the clipboard, then delete it."""
        region = self._selected_region()
        if region is None:
            self.status("No region selected")
            return
        if not region.can_delete:
            self.status("Region cannot be deleted")
            return

        self.copy()
        frame = self.frame
        if frame is not None and region in frame.regions:
            frame.regions.remove(region)
        self.window.region.show_frame_regions(frame)
        self.status(f"Cut {type(region).__name__.lower()} region")

    def paste(self) -> None:
        """Add a copy of the clipboard region to the current frame.

        Offset slightly so a paste on top of the original is visible rather
        than hidden underneath it.
        """
        if self._clipboard is None:
            self.status("Nothing to paste")
            return
        frame = self.frame
        if frame is None:
            self.status("No frame to paste into")
            return

        region = copy.deepcopy(self._clipboard)
        region.move(PASTE_OFFSET, PASTE_OFFSET)
        frame.regions.append(region)
        self.window.region.show_frame_regions(frame)
        self.status(f"Pasted {type(region).__name__.lower()} region")

    # -- preferences ---------------------------------------------------------

    @staticmethod
    def preferences_path() -> Path:
        """Where preferences are stored."""
        return Path.home() / ".ncrads9" / "preferences.json"

    def apply_theme(self, name: str) -> None:
        """Restyle the application.

        A theme is application-wide, not per-window: it sets the
        `QApplication` stylesheet, and the System theme also swaps the
        `QStyle`. Both walk every existing widget, so the current theme is
        recorded on the application object and re-applying the same one is
        skipped -- otherwise every window construction would restyle the
        whole process, which is both wasteful and, with several windows
        already up, a way to crash Qt.

        Args:
            name: "System", "Light" or "Dark". An unknown name leaves the
                current styling alone rather than falling back, so a
                hand-edited preferences file cannot silently change the look.
        """
        theme = THEMES.get(name)
        if theme is None:
            self.status(f"Unknown theme: {name}", 3000)
            return

        app = QApplication.instance()
        if app is None:
            return
        if app.property(THEME_PROPERTY) == name:
            return
        theme.apply(app)
        app.setProperty(THEME_PROPERTY, name)

    def preferences_dict(self) -> dict:
        """The current preferences, with defaults filled in."""
        store = self.window.preferences
        return {key: store.get(key, default) for key, default in PREFERENCE_DEFAULTS.items()}

    def show_preferences(self) -> None:
        """Show the Preferences dialog."""
        dialog = PreferencesDialog(self.window)
        dialog.load_preferences(self.preferences_dict())
        dialog.preferences_changed.connect(self.apply_preferences)
        dialog.exec()

    def apply_preferences(
        self,
        prefs: dict,
        persist: bool = True,
        show_message: bool = True,
    ) -> None:
        """Apply preferences, and optionally write them to disk.

        Args:
            prefs: The settings to apply.
            persist: Write them to the preferences file. False during startup,
                where this is applying what was just read back.
            show_message: Report success in the status bar.
        """
        window = self.window

        if persist:
            for key, value in prefs.items():
                window.preferences.set(key, value, save=False)
            window.preferences.save()

        # Switching backend replaces the viewer widget, so this comes first.
        use_gpu = bool(prefs.get("use_gpu", window.use_gpu_rendering))
        if use_gpu != window.use_gpu_rendering:
            window._rebuild_image_viewer(use_gpu)

        if window.using_gpu_rendering:
            if hasattr(self.viewer, "set_tile_size"):
                self.viewer.set_tile_size(int(prefs.get("tile_size", 512)))
            if hasattr(self.viewer, "set_cache_size_mb"):
                self.viewer.set_cache_size_mb(int(prefs.get("cache_size_mb", 1000)))

        self.apply_theme(str(prefs.get("theme", "System")))

        window._apply_background_color(prefs.get("background_color", "#000000"))
        window.nan_color = str(prefs.get("nan_color", "#ffffff"))

        default_scale = prefs.get("default_scale", "Linear")
        if default_scale in DEFAULT_SCALES:
            window.scale.set_scale(DEFAULT_SCALES[default_scale])

        default_colormap = window.color.normalize_name(str(prefs.get("default_colormap", "gray")))
        if default_colormap in self.menu.colormap_actions:
            window.color.set_colormap(default_colormap)

        if window.image_data is not None:
            self.refresh()

        if show_message:
            self.status("Preferences updated")
