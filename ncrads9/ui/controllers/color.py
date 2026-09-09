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
The Color menu: colormap selection, inversion, and the colorbar.

M5 adds what DS9 has and this does not (PLAN.md §5.8): the 168 bundled
`.sao`/`.lut` colormaps and their category submenus, colour tags, multiple
colorbars, and the RGB/HSV/HLS colorbar variants.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtWidgets import QFileDialog, QInputDialog

from ...colormaps.builtin_maps import get_colormap
from ...colormaps.colormap import Colormap
from ...colormaps.lut_parser import parse_lut_file, save_lut_file
from ...colormaps.sao_parser import parse_sao_file
from .base import Controller

#: Colormap aliases the user may type, mapped to the internal name.
COLORMAP_ALIASES: dict[str, str] = {"gray": "grey"}

#: Internal colormap name -> the label the button bar uses.
BUTTON_LABELS: dict[str, str] = {
    "grey": "Gray",
    "heat": "Heat",
    "cool": "Cool",
    "rainbow": "Rainbow",
}

#: Font-size thresholds for the colorbar's Small/Medium/Large radio group.
SMALL_FONT_MAX = 7
LARGE_FONT_MIN = 10


class ColorController(Controller):
    """Owns the Color menu."""

    def connect(self) -> None:
        """Wire the Color menu."""
        for name, action in self.menu.colormap_actions.items():
            action.triggered.connect(lambda _checked=False, c=name: self.set_colormap(c))

        self.menu.action_invert_colormap.triggered.connect(self.set_inverted)
        self.menu.action_reset_colormap.triggered.connect(self.reset)
        self.menu.action_load_user_colormap.triggered.connect(self.load_user_colormap)
        self.menu.action_save_user_colormap.triggered.connect(self.save_current_colormap)
        self.menu.action_colormap_params.triggered.connect(self.show_dialog)

        self.menu.action_colorbar.triggered.connect(self.set_colorbar_visible)
        self.menu.action_colorbar_horizontal.triggered.connect(
            lambda: self.set_colorbar_orientation("horizontal")
        )
        self.menu.action_colorbar_vertical.triggered.connect(
            lambda: self.set_colorbar_orientation("vertical")
        )
        self.menu.action_colorbar_numerics_show.triggered.connect(self.set_colorbar_numerics)
        self.menu.action_colorbar_space_value.triggered.connect(lambda: self.set_colorbar_spacing("value"))
        self.menu.action_colorbar_space_distance.triggered.connect(
            lambda: self.set_colorbar_spacing("distance")
        )
        self.menu.action_colorbar_font_small.triggered.connect(lambda: self.set_colorbar_font_size(6))
        self.menu.action_colorbar_font_medium.triggered.connect(lambda: self.set_colorbar_font_size(8))
        self.menu.action_colorbar_font_large.triggered.connect(lambda: self.set_colorbar_font_size(11))
        self.menu.action_colorbar_size.triggered.connect(self.show_colorbar_size_dialog)
        self.menu.action_colorbar_ticks.triggered.connect(self.show_colorbar_ticks_dialog)

    def sync(self) -> None:
        """Tick the entry matching the current colormap."""
        for name, action in self.menu.colormap_actions.items():
            action.setChecked(name == self.window.current_colormap)

    # -- colormaps -----------------------------------------------------------

    @staticmethod
    def normalize_name(name: str) -> str:
        """Fold a colormap alias to its internal name."""
        lowered = name.strip().lower()
        return COLORMAP_ALIASES.get(lowered, lowered)

    def colormap(self, name: str) -> Colormap:
        """Return a built-in or user-loaded colormap by name.

        Raises:
            ValueError: If no such colormap is known.
        """
        cmap_name = self.normalize_name(name)
        if cmap_name in self.window.custom_colormaps:
            return self.window.custom_colormaps[cmap_name]
        cmap = get_colormap(cmap_name)
        if cmap is None:
            raise ValueError(f"Unknown colormap: {name}")
        return cmap

    def available_colormaps(self) -> list[str]:
        """Every colormap currently offered in the menu."""
        return sorted(self.menu.colormap_actions.keys())

    def set_colormap(self, colormap: str) -> None:
        """Apply a colormap by name.

        Args:
            colormap: Colormap name or alias.
        """
        cmap_name = self.normalize_name(colormap)
        if cmap_name not in self.menu.colormap_actions:
            self.status(f"Unsupported colormap: {colormap}")
            return

        self.window.current_colormap = cmap_name
        self.window._persist_frame_view_state()
        self.sync()

        if cmap_name in BUTTON_LABELS:
            self.window.button_bar.set_colormap(BUTTON_LABELS[cmap_name])

        if self.window.image_data is not None:
            self.refresh()
            self.status(f"Colormap: {cmap_name}")

    def reset(self) -> None:
        """Return to the default colormap, not inverted."""
        self.window.invert_colormap = False
        self.menu.action_invert_colormap.setChecked(False)
        self.set_colormap(self.window._default_colormap)
        self.status("Colormap reset")

    def set_inverted(self, inverted: bool) -> None:
        """Invert or un-invert the colormap."""
        self.window.invert_colormap = inverted
        self.window._persist_frame_view_state()
        if self.window.image_data is not None:
            self.refresh()
            self.status(f"Colormap {'inverted' if inverted else 'normal'}")

    # -- user colormaps ------------------------------------------------------

    def register_user_colormap(self, colormap: Colormap) -> None:
        """Add a loaded colormap to the menu under User."""
        name = self.normalize_name(colormap.name)
        self.window.custom_colormaps[name] = Colormap(name, colormap.colors)
        action = self.menu.add_user_colormap_action(name)
        if name not in self.window._user_colormap_actions:
            action.triggered.connect(lambda _checked=False, cmap=name: self.set_colormap(cmap))
            self.window._user_colormap_actions[name] = action

    def load_user_colormap(self) -> None:
        """Load a colormap from a DS9 `.lut` or `.sao` file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self.window,
            "Load Colormap",
            "",
            "Colormap Files (*.lut *.sao);;LUT Files (*.lut);;SAO Files (*.sao);;All Files (*)",
        )
        if not filepath:
            return
        try:
            parse = parse_sao_file if filepath.lower().endswith(".sao") else parse_lut_file
            cmap = parse(filepath)
            self.register_user_colormap(cmap)
            self.set_colormap(cmap.name)
            self.status(f"Loaded colormap: {cmap.name}", 3000)
        except Exception as exc:
            self.status(f"Error loading colormap: {exc}", 3000)

    def save_current_colormap(self) -> None:
        """Write the current colormap out as a `.lut` file."""
        try:
            cmap = self.colormap(self.window.current_colormap)
        except ValueError as exc:
            self.status(str(exc), 3000)
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self.window,
            "Save Colormap",
            f"{self.window.current_colormap}.lut",
            "LUT Files (*.lut);;All Files (*)",
        )
        if not filepath:
            return
        try:
            save_lut_file(cmap, filepath)
            self.status(f"Saved colormap: {filepath}", 3000)
        except Exception as exc:
            self.status(f"Error saving colormap: {exc}", 3000)

    # -- contrast and bias ---------------------------------------------------

    def set_contrast_brightness(self, contrast: float, brightness: float) -> None:
        """Push contrast and bias onto whichever viewer backend is active."""
        viewer = self.viewer
        if hasattr(viewer, "set_contrast_brightness"):
            viewer.set_contrast_brightness(contrast, brightness)
            return
        inner = getattr(viewer, "image_viewer", None)
        if inner is not None and hasattr(inner, "set_contrast_brightness"):
            inner.set_contrast_brightness(contrast, brightness)

    def on_contrast_changed(self, contrast: float, brightness: float) -> None:
        """Handle a contrast/bias change made by dragging on the image."""
        self.refresh()
        self.window._persist_frame_view_state()
        self.status(f"Contrast: {contrast:.2f}, Brightness: {brightness:.2f}", 1000)

    # -- colorbar ------------------------------------------------------------

    def set_colorbar_visible(self, visible: bool) -> None:
        """Show or hide the colorbar."""
        self.window.colorbar_dock.setVisible(visible)

    def set_colorbar_orientation(self, orientation: str) -> None:
        """Lay the colorbar out horizontally or vertically."""
        value = orientation.lower()
        self.window.colorbar_widget.set_orientation(value)
        self.menu.action_colorbar_horizontal.setChecked(value == "horizontal")
        self.menu.action_colorbar_vertical.setChecked(value == "vertical")
        self.status(f"Colorbar orientation: {orientation}")

    def set_colorbar_numerics(self, visible: bool) -> None:
        """Show or hide the colorbar's numeric labels."""
        self.window.colorbar_widget.set_show_numerics(visible)
        self.menu.action_colorbar_numerics_show.setChecked(visible)

    def set_colorbar_spacing(self, mode: str) -> None:
        """Space colorbar ticks by equal value or by equal distance."""
        value = mode.lower()
        self.window.colorbar_widget.set_spacing_mode(value)
        self.menu.action_colorbar_space_value.setChecked(value == "value")
        self.menu.action_colorbar_space_distance.setChecked(value == "distance")

    def set_colorbar_font_size(self, size: int) -> None:
        """Set the colorbar label font size, and tick the matching preset."""
        self.window.colorbar_widget.set_label_font_size(size)
        self.menu.action_colorbar_font_small.setChecked(size <= SMALL_FONT_MAX)
        self.menu.action_colorbar_font_large.setChecked(size >= LARGE_FONT_MIN)
        self.menu.action_colorbar_font_medium.setChecked(SMALL_FONT_MAX < size < LARGE_FONT_MIN)

    def show_colorbar_size_dialog(self) -> None:
        """Prompt for the colorbar's thickness."""
        size, ok = QInputDialog.getInt(
            self.window,
            "Colorbar Size",
            "Size:",
            value=self.window.colorbar_widget.bar_size,
            min=12,
            max=96,
        )
        if ok:
            self.window.colorbar_widget.set_bar_size(size)

    def show_colorbar_ticks_dialog(self) -> None:
        """Prompt for the number of colorbar ticks."""
        ticks, ok = QInputDialog.getInt(
            self.window,
            "Colorbar Ticks",
            "Number of ticks:",
            value=self.window.colorbar_widget.tick_count,
            min=2,
            max=30,
        )
        if ok:
            self.window.colorbar_widget.set_tick_count(ticks)

    # -- parameters dialog ---------------------------------------------------

    def show_dialog(self) -> None:
        """Show the Colormap Parameters dialog."""
        from ..dialogs.colormap_dialog import ColormapDialog

        dialog = ColormapDialog(self.window)
        dialog.colormap_changed.connect(self.apply_dialog_settings)
        dialog.exec()

    def apply_dialog_settings(self, settings: dict) -> None:
        """Apply settings from the Colormap Parameters dialog."""
        cmap_name = self.normalize_name(settings.get("colormap", self.window.current_colormap))
        if cmap_name in self.menu.colormap_actions:
            self.set_colormap(cmap_name)

        inverted = bool(settings.get("invert", self.window.invert_colormap))
        if inverted != self.window.invert_colormap:
            self.menu.action_invert_colormap.setChecked(inverted)
            self.set_inverted(inverted)
