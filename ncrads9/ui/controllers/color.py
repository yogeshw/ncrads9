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

M5 bundled DS9's colour tables (`colormaps/bundled.py`) and put them on
DS9's ten cascades, so a name resolves in one of three ways: a built-in from
`colormaps/builtin_maps.py`, a bundled `.sao`/`.lut` table parsed on first
use, or a table the user loaded at runtime. `colormap()` is the one place
that resolution happens.

Colour tags are held per frame (`colormaps/color_tags.py`) and painted onto
whatever table is in force, after inversion and before anything is drawn, so
they follow a colormap change and a clip-limit change without moving.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtWidgets import QFileDialog, QInputDialog

from ...colormaps.builtin_maps import get_colormap
from ...colormaps.bundled import load as load_bundled
from ...colormaps.color_tags import (
    DEFAULT_TAG_COLOR,
    ColorTag,
    ColorTagError,
    ColorTagSet,
)
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

#: Filter for the colour tag file dialogs.
TAG_FILTER = "Color Tag Files (*.tag);;All Files (*)"

#: How wide a new tag is, as a fraction of the colorbar, when the user
#: clicks somewhere untagged.
NEW_TAG_WIDTH = 0.05

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
        self.menu.action_reset_colorbar.triggered.connect(self.reset_contrast_bias)

        self.menu.action_load_color_tags.triggered.connect(self.load_tags)
        self.menu.action_save_color_tags.triggered.connect(self.save_tags)
        self.menu.action_delete_color_tags.triggered.connect(self.delete_tags)

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
        """Return a colormap by name, from wherever it comes from.

        Looked up in the order a name should win: a table the user loaded at
        runtime, then one of NCRADS9's built-ins, then one of DS9's bundled
        files.

        Args:
            name: A colormap name or alias.

        Returns:
            The colormap.

        Raises:
            ValueError: If no such colormap is known.
        """
        cmap_name = self.normalize_name(name)
        if cmap_name in self.window.custom_colormaps:
            return self.window.custom_colormaps[cmap_name]
        cmap = get_colormap(cmap_name)
        if cmap is not None:
            return cmap
        bundled = load_bundled(cmap_name)
        if bundled is not None:
            return bundled
        raise ValueError(f"Unknown colormap: {name}")

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
        self.window.frame_controller.persist_view_state()
        self.sync()

        if cmap_name in BUTTON_LABELS:
            self.window.button_bar.set_colormap(BUTTON_LABELS[cmap_name])

        if self.window.image_data is not None:
            self.refresh()
            self.status(f"Colormap: {cmap_name}")

    def on_button_bar_colormap(self, label: str) -> None:
        """Select a colormap from a button-bar label."""
        for name, text in BUTTON_LABELS.items():
            if text == label:
                self.set_colormap(name)
                return

    def reset(self) -> None:
        """Return to the default colormap, not inverted."""
        self.window.invert_colormap = False
        self.menu.action_invert_colormap.setChecked(False)
        self.set_colormap(self.window._default_colormap)
        self.status("Colormap reset")

    def set_inverted(self, inverted: bool) -> None:
        """Invert or un-invert the colormap."""
        self.window.invert_colormap = inverted
        self.window.frame_controller.persist_view_state()
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

    # -- colour tags ---------------------------------------------------------

    def tags(self, frame=None) -> ColorTagSet:
        """The current frame's colour tags, creating the set on first use.

        Args:
            frame: The frame to read. Defaults to the current one.

        Returns:
            Its tag set. An empty set with no frame, so every caller can
            treat the result as a set rather than checking for None.
        """
        frame = frame if frame is not None else self.frame
        if frame is None:
            return ColorTagSet()
        if not isinstance(getattr(frame, "color_tags", None), ColorTagSet):
            frame.color_tags = ColorTagSet()
        return frame.color_tags

    def apply_tags(self, colormap: Colormap, frame=None) -> Colormap:
        """Paint a frame's tags onto a colour table.

        Args:
            colormap: The table as the colormap and inversion left it.
            frame: The frame whose tags to use. Defaults to the current one.

        Returns:
            A tagged copy, or `colormap` itself when the frame has no tags.
        """
        tags = self.tags(frame)
        if not tags:
            return colormap
        return Colormap(f"{colormap.name}+tags", tags.apply(colormap.colors))

    def add_tag(self, start: float, stop: float, color: str = DEFAULT_TAG_COLOR) -> None:
        """Tag a stretch of the colorbar.

        Args:
            start: Where the tag begins, 0 at the bottom of the colorbar.
            stop: Where it ends.
            color: A colour name or `#rrggbb`.
        """
        if self.require_frame("No image to tag") is None:
            return
        try:
            tag = ColorTag(start, stop, color)
        except ColorTagError as exc:
            self.status(str(exc), 3000)
            return
        self.tags().add(tag)
        self.refresh_tags()
        self.status(f"Tagged {tag.start:.3g}..{tag.stop:.3g} {tag.color}")

    def edit_tag(self, index: int, start: float, stop: float, color: str) -> None:
        """Change one tag."""
        try:
            self.tags().replace(index, ColorTag(start, stop, color))
        except (IndexError, ColorTagError) as exc:
            self.status(str(exc), 3000)
            return
        self.refresh_tags()

    def delete_tag(self, index: int) -> None:
        """Delete one tag."""
        try:
            self.tags().remove(index)
        except IndexError:
            self.status(f"No colour tag {index}", 3000)
            return
        self.refresh_tags()
        self.status("Deleted colour tag")

    def delete_tags(self) -> None:
        """Delete every tag on the current frame (DS9's Delete Color Tag)."""
        tags = self.tags()
        if not tags:
            self.status("No colour tags to delete")
            return
        count = len(tags)
        tags.clear()
        self.refresh_tags()
        self.status(f"Deleted {count} colour tag{'s' if count != 1 else ''}")

    def load_tags(self) -> None:
        """Load a DS9 colour tag file onto the current frame."""
        if self.require_frame("No image to tag") is None:
            return
        filepath, _ = QFileDialog.getOpenFileName(self.window, "Load Color Tags", "", TAG_FILTER)
        if not filepath:
            return
        try:
            loaded = ColorTagSet.load(filepath)
        except (ColorTagError, OSError) as exc:
            self.status(f"Error loading colour tags: {exc}", 5000)
            return
        frame = self.frame
        if frame is not None:
            frame.color_tags = loaded
        self.refresh_tags()
        self.status(f"Loaded {len(loaded)} colour tags from {filepath}", 3000)

    def save_tags(self) -> None:
        """Write the current frame's colour tags to a file."""
        tags = self.tags()
        if not tags:
            self.status("No colour tags to save")
            return
        filepath, _ = QFileDialog.getSaveFileName(self.window, "Save Color Tags", "", TAG_FILTER)
        if not filepath:
            return
        try:
            tags.save(filepath)
        except OSError as exc:
            self.status(f"Error saving colour tags: {exc}", 5000)
            return
        self.status(f"Saved {len(tags)} colour tags to {filepath}", 3000)

    def refresh_tags(self) -> None:
        """Redraw after a tag change.

        The colorbar is painted from the same table the image is, tags and
        all, so redisplaying updates both and there is nothing to tell the
        colorbar separately.
        """
        if self.window.image_data is not None:
            self.refresh()

    def on_colorbar_clicked(self, position: float) -> None:
        """Handle a click on the colorbar in DS9's Colorbar edit mode.

        Clicking an existing tag edits it; clicking anywhere else starts a
        new one, a twentieth of the bar wide, which the dialog then adjusts.

        Args:
            position: 0 at the bottom of the colorbar, 1 at the top.
        """
        if self.window.edit_mode != "colorbar":
            return
        if self.require_frame("No image to tag") is None:
            return

        tags = self.tags()
        index = tags.index_at(position)
        if index is None:
            half = NEW_TAG_WIDTH / 2.0
            self.add_tag(position - half, position + half)
            index = len(tags) - 1
        self.show_tag_dialog(index)

    def show_tag_dialog(self, index: int) -> None:
        """Edit or delete one tag (DS9's ColorTagDialog)."""
        tags = self.tags()
        if not 0 <= index < len(tags):
            return
        from ..dialogs.color_tag_dialog import ColorTagDialog

        dialog = ColorTagDialog(tags.tags[index], self.window)
        outcome = dialog.exec()
        if outcome == ColorTagDialog.DELETED:
            self.delete_tag(index)
        elif outcome:
            edited = dialog.tag()
            self.edit_tag(index, edited.start, edited.stop, edited.color)

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

    def reset_contrast_bias(self) -> None:
        """Put contrast and bias back to neutral.

        Dragging on the image adjusts them, with nothing to say what they are
        or how to undo it. M5-13 gives that its own entry.
        """
        viewer = self.viewer
        if hasattr(viewer, "reset_contrast_brightness"):
            viewer.reset_contrast_brightness()
        else:
            self.set_contrast_brightness(1.0, 0.0)
        self.window.frame_controller.persist_view_state()
        if self.window.image_data is not None:
            self.refresh()
        self.status("Contrast and bias reset")

    def on_contrast_changed(self, contrast: float, brightness: float) -> None:
        """Handle a contrast/bias change made by dragging on the image."""
        self.refresh()
        self.window.frame_controller.persist_view_state()
        self.status(f"Contrast: {contrast:.2f}, Brightness: {brightness:.2f}", 1000)

    # -- colorbar ------------------------------------------------------------

    def set_colorbar_visible(self, visible: bool) -> None:
        """Show or hide the colorbar.

        Colorbar visibility is one of DS9's View flags, so the View
        controller owns it; the Color menu's entry is the same `QAction`.
        """
        self.window.view.set_colorbar_visible(visible)

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
