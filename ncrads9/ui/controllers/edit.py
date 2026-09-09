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

Undo/redo and cut/copy/paste need the command stack in M9-24; until then the
undo entries report that they do nothing rather than pretending otherwise, and
cut/copy/paste are the three actions the dead-action guard tracks.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

from ...rendering.scale_algorithms import ScaleAlgorithm
from ..dialogs.preferences_dialog import PreferencesDialog
from .base import Controller

#: Preference key -> default, and the full set the dialog round-trips.
PREFERENCE_DEFAULTS: dict[str, object] = {
    "use_gpu": True,
    "tile_size": 512,
    "cache_size_mb": 1000,
    "background_color": "#000000",
    "default_scale": "Linear",
    "default_colormap": "gray",
    "anti_aliasing": True,
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

    def connect(self) -> None:
        """Wire the Edit menu."""
        self.menu.action_preferences.triggered.connect(self.show_preferences)
        self.menu.action_undo.triggered.connect(lambda: self.status("Undo not implemented"))
        self.menu.action_redo.triggered.connect(lambda: self.status("Redo not implemented"))

    # -- preferences ---------------------------------------------------------

    @staticmethod
    def preferences_path() -> Path:
        """Where preferences are stored."""
        return Path.home() / ".ncrads9" / "preferences.json"

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

        window._apply_background_color(prefs.get("background_color", "#000000"))

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
