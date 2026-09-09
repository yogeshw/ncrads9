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
The Frame menu: frame lifecycle, navigation, display mode, match and lock.

The largest controller, because DS9's Frame menu is its largest menu and it is
also the one NCRADS9 covers best -- 66 of DS9's 69 entries (PLAN.md §5.4).

Three ideas run through it:

*Active frames.* DS9's Show/Hide Frames takes a frame out of the tile grid and
the blink cycle without deleting it. That set is tracked by frame id rather
than index, so it survives reordering, and `ensure_active_valid` reconciles it
whenever frames are added or removed.

*Per-frame view state.* Every frame remembers its own zoom, pan, rotation,
scale, limits and colormap, so switching frames restores exactly what the user
last saw. `persist_view_state` and `apply_view_state` are the two halves.

*Match and lock.* Match is a one-shot copy of one frame's setting to all the
others; lock keeps them tied as the user works. Both walk the same scopes.

*Cubes.* A frame whose extension has three or more axes shows one slice at a
time. The slice index and axis order live on the frame, so each frame steps
independently, and the Cube dialog reports what the user asked for rather than
reaching into the frame itself.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from ...core.cube_handler import AxisOrder, CubeHandler, is_cube
from ...frames.frame import Frame
from ...rendering.scale_algorithms import ScaleAlgorithm
from ..view_transform import normalize_rotation
from .base import Controller


class FrameController(Controller):
    """Owns the Frame menu."""

    def connect(self) -> None:
        """Wire the Frame menu."""
        menu = self.menu

        menu.action_new_frame.triggered.connect(self.new_frame)
        menu.action_new_frame_rgb.triggered.connect(lambda: self.new_frame_of_type("rgb"))
        menu.action_new_frame_hsv.triggered.connect(lambda: self.new_frame_of_type("hsv"))
        menu.action_new_frame_hls.triggered.connect(lambda: self.new_frame_of_type("hls"))
        menu.action_new_frame_3d.triggered.connect(lambda: self.new_frame_of_type("3d"))
        menu.action_delete_frame.triggered.connect(self.delete_current)
        menu.action_delete_all_frames.triggered.connect(self.delete_all)
        menu.action_clear_frame.triggered.connect(self.clear_current)
        menu.action_reset_frame.triggered.connect(self.reset_current)
        menu.action_refresh_frame.triggered.connect(self.refresh_current)

        menu.action_single_frame.triggered.connect(self.show_single)
        menu.action_tile_frames.triggered.connect(self.set_tile)
        menu.action_blink_frames.triggered.connect(self.set_blink)
        menu.action_fade_frames.triggered.connect(self.set_fade)

        menu.action_first_frame.triggered.connect(self.first)
        menu.action_prev_frame.triggered.connect(self.previous)
        menu.action_next_frame.triggered.connect(self.next)
        menu.action_last_frame.triggered.connect(self.last)

        menu.action_move_frame_first.triggered.connect(self.move_first)
        menu.action_move_frame_back.triggered.connect(self.move_back)
        menu.action_move_frame_forward.triggered.connect(self.move_forward)
        menu.action_move_frame_last.triggered.connect(self.move_last)
        menu.action_show_all_frames.triggered.connect(self.show_all)
        menu.action_hide_all_frames.triggered.connect(self.hide_all)

        menu.action_frame_cube_dialog.triggered.connect(lambda: self.show_frame_dialog("cube"))
        menu.action_frame_rgb_dialog.triggered.connect(self.show_rgb_dialog)
        menu.action_frame_hsv_dialog.triggered.connect(lambda: self.show_frame_dialog("hsv"))
        menu.action_frame_hls_dialog.triggered.connect(lambda: self.show_frame_dialog("hls"))
        menu.action_frame_3d_dialog.triggered.connect(lambda: self.show_frame_dialog("3d"))

        menu.action_tile_mode_grid.triggered.connect(lambda: self.set_tile_arrangement("grid"))
        menu.action_tile_mode_columns.triggered.connect(lambda: self.set_tile_arrangement("column"))
        menu.action_tile_mode_rows.triggered.connect(lambda: self.set_tile_arrangement("row"))
        for interval, action in menu.blink_interval_actions.items():
            action.triggered.connect(lambda _checked=False, ms=interval: self.set_blink_interval(ms))
        for interval, action in menu.fade_interval_actions.items():
            action.triggered.connect(lambda _checked=False, ms=interval: self.set_fade_interval(ms))

        self._connect_match_actions(menu)
        self._connect_lock_actions(menu)

    def _connect_match_actions(self, menu) -> None:
        """Wire Frame -> Match.

        DS9 offers each match scope per coordinate system. Only WCS and image
        differ in practice today: physical, amplifier and detector all fall
        back to image until M3-7 makes those coordinate systems real, so they
        deliberately share a handler rather than pretending to differ.
        """
        menu.action_match_wcs.triggered.connect(self.match_wcs)
        menu.action_match_frame_physical.triggered.connect(self.match_image)
        menu.action_match_frame_amplifier.triggered.connect(self.match_image)
        menu.action_match_frame_detector.triggered.connect(self.match_image)
        menu.action_match_image.triggered.connect(self.match_image)

        menu.action_match_crosshair_wcs.triggered.connect(self.match_wcs)
        menu.action_match_crosshair_image.triggered.connect(self.match_image)
        menu.action_match_crosshair_physical.triggered.connect(self.match_image)
        menu.action_match_crosshair_amplifier.triggered.connect(self.match_image)
        menu.action_match_crosshair_detector.triggered.connect(self.match_image)

        menu.action_match_crop_wcs.triggered.connect(self.match_wcs)
        menu.action_match_crop_image.triggered.connect(self.match_image)
        menu.action_match_crop_physical.triggered.connect(self.match_image)
        menu.action_match_crop_amplifier.triggered.connect(self.match_image)
        menu.action_match_crop_detector.triggered.connect(self.match_image)

        menu.action_match_slice_wcs.triggered.connect(self.match_wcs)
        menu.action_match_slice_image.triggered.connect(self.match_image)

        menu.action_match_bin.triggered.connect(self.match_bin)
        menu.action_match_axes_order.triggered.connect(self.match_axes_order)
        menu.action_match_scale.triggered.connect(self.match_scale)
        menu.action_match_scale_limits.triggered.connect(self.match_scale_limits)
        menu.action_match_colorbar.triggered.connect(self.match_colorbar)
        menu.action_match_block.triggered.connect(self.match_block)
        menu.action_match_smooth.triggered.connect(self.match_smooth)
        menu.action_match_3d.triggered.connect(self.match_3d)

    def _connect_lock_actions(self, menu) -> None:
        """Wire Frame -> Lock."""
        for scope in ("frame", "crosshair", "crop", "slice"):
            for system in ("none", "wcs", "image", "physical", "amplifier", "detector"):
                action = getattr(menu, f"action_lock_{scope}_{system}", None)
                if action is not None:
                    action.triggered.connect(
                        lambda _checked=False, s=scope, v=system: self.set_lock_scope(s, v)
                    )

        for flag in ("bin", "axes_order", "scale", "scale_limits", "colorbar", "block", "smooth", "3d"):
            action = getattr(menu, f"action_lock_{flag}", None)
            if action is not None:
                action.triggered.connect(
                    lambda _checked=False, f=flag: self.set_lock_flag(
                        f, getattr(self.menu, f"action_lock_{f}").isChecked()
                    )
                )

    def reset_view_defaults(self, frame: Frame) -> None:
        """Reset a frame's display state to defaults."""
        frame.block_factor = 1
        frame.colormap = self.window._default_colormap
        frame.scale = ScaleAlgorithm.LINEAR
        frame.invert_colormap = False
        frame.z1 = None
        frame.z2 = None
        frame.zoom = 1.0
        frame.pan_x = 0.0
        frame.pan_y = 0.0
        frame.rotation = 0.0
        frame.flip_x = False
        frame.flip_y = False
        frame.align_wcs = False
        frame.contrast = 1.0
        frame.brightness = 0.0
        frame.crop_center_x = None
        frame.crop_center_y = None
        frame.crop_width = None
        frame.crop_height = None
        frame.rgb_channel_scale = {
            "red": ScaleAlgorithm.LINEAR,
            "green": ScaleAlgorithm.LINEAR,
            "blue": ScaleAlgorithm.LINEAR,
        }
        frame.rgb_channel_z1 = {"red": None, "green": None, "blue": None}
        frame.rgb_channel_z2 = {"red": None, "green": None, "blue": None}
        frame.rgb_channel_contrast = {"red": 1.0, "green": 1.0, "blue": 1.0}
        frame.rgb_channel_brightness = {"red": 0.0, "green": 0.0, "blue": 0.0}

    def ensure_active_valid(self) -> None:
        """Ensure active frame IDs map to existing frames."""
        valid_ids = {frame.frame_id for frame in self.frames.frames}
        self.window._active_frame_ids.update(valid_ids - self.window._known_frame_ids)
        self.window._active_frame_ids.intersection_update(valid_ids)
        self.window._known_frame_ids = set(valid_ids)
        if not self.window._active_frame_ids and self.frames.frames:
            frame = self.frames.current_frame or self.frames.frames[0]
            self.window._active_frame_ids.add(frame.frame_id)

    def active_indices(self) -> list[int]:
        """Return frame indices currently marked active."""
        self.ensure_active_valid()
        return [
            idx
            for idx, frame in enumerate(self.frames.frames)
            if frame.frame_id in self.window._active_frame_ids
        ]

    def refresh_menu_items(self) -> None:
        """Refresh dynamic frame menu items."""
        self.ensure_active_valid()
        current_index = self.frames.current_index

        self.menu.goto_frame_menu.clear()
        for idx, _frame in enumerate(self.frames.frames):
            action = QAction(f"Frame {idx + 1}", self.window)
            action.setCheckable(True)
            action.setChecked(idx == current_index)
            action.triggered.connect(lambda checked=False, i=idx: self.goto_index(i))
            self.menu.goto_frame_menu.addAction(action)

        self.menu.show_hide_frames_menu.clear()
        self.menu.show_hide_frames_menu.addAction(self.menu.action_show_all_frames)
        self.menu.show_hide_frames_menu.addAction(self.menu.action_hide_all_frames)
        self.menu.show_hide_frames_menu.addSeparator()
        for idx, frame in enumerate(self.frames.frames):
            action = QAction(f"Frame {idx + 1}", self.window)
            action.setCheckable(True)
            action.setChecked(frame.frame_id in self.window._active_frame_ids)
            action.triggered.connect(lambda checked, fid=frame.frame_id: self.set_active(fid, checked))
            self.menu.show_hide_frames_menu.addAction(action)

    def goto_index(self, index: int) -> None:
        """Switch to a specific frame index."""
        if self.frames.goto_frame(index):
            self.window.z1 = None
            self.window.z2 = None
            if hasattr(self.viewer, "reset_contrast_brightness"):
                self.viewer.reset_contrast_brightness()
            self.update_display()

    def new_frame_of_type(self, frame_type: str) -> None:
        """Create a new frame of the requested DS9-style type."""
        frame = self.frames.new_frame(frame_type=frame_type)
        self.window._known_frame_ids.add(frame.frame_id)
        self.window._active_frame_ids.add(frame.frame_id)
        self.window.z1 = None
        self.window.z2 = None
        if hasattr(self.viewer, "reset_contrast_brightness"):
            self.viewer.reset_contrast_brightness()
        self.update_display()
        self.status(f"Created Frame {self.frames.current_index + 1} ({frame_type})", 2000)

    def new_frame(self) -> None:
        """Create a new empty frame."""
        self.new_frame_of_type("base")

    def delete_all(self) -> None:
        """Delete all frames and create one new empty frame."""
        for existing in self.frames.frames:
            if existing.fits_handler is not None:
                try:
                    existing.fits_handler.close()
                except Exception:
                    pass
        frame = self.frames.reset_to_single_frame()
        self.window._samp_catalog_sources.clear()
        self.window._known_frame_ids = {frame.frame_id}
        self.window._active_frame_ids = {frame.frame_id}
        self.set_display_mode("single")
        self.status("Deleted all frames", 2000)

    def delete_current(self) -> None:
        """Delete current frame."""
        current_frame = self.frames.current_frame
        current_frame_id = current_frame.frame_id if current_frame else None
        if self.frames.delete_frame():
            if current_frame and current_frame.fits_handler is not None:
                try:
                    current_frame.fits_handler.close()
                except Exception:
                    pass
            if current_frame_id is not None:
                self.window._active_frame_ids.discard(current_frame_id)
                self.window._samp_catalog_sources.pop(current_frame_id, None)
            self.ensure_active_valid()
            if len(self.active_indices()) <= 1 and self.window._frame_display_mode in {"blink", "fade"}:
                self.set_display_mode("single")
            else:
                self.window.z1 = None
                self.window.z2 = None
                if hasattr(self.viewer, "reset_contrast_brightness"):
                    self.viewer.reset_contrast_brightness()
                self.update_display()
            frame_info = f"Frame {self.frames.current_index + 1}/{self.frames.num_frames}"
            self.status(f"Deleted frame, now at {frame_info}", 2000)
        else:
            self.status("Cannot delete last frame", 2000)

    def clear_current(self) -> None:
        """Clear data from current frame."""
        frame = self.frames.current_frame
        if frame is None:
            return
        frame.filepath = None
        if frame.fits_handler is not None:
            try:
                frame.fits_handler.close()
            except Exception:
                pass
        frame.fits_handler = None
        frame.image_data = None
        frame.original_image_data = None
        frame.rgb_channels = {"red": None, "green": None, "blue": None}
        frame.rgb_source_frame_ids = {"red": None, "green": None, "blue": None}
        frame.rgb_view = {"red": True, "green": True, "blue": True}
        frame.rgb_current_channel = "red"
        frame.header = None
        frame.wcs_handler = None
        frame.regions.clear()
        self.window._samp_catalog_sources.pop(frame.frame_id, None)
        self.reset_view_defaults(frame)
        self.window.z1 = None
        self.window.z2 = None
        if hasattr(self.viewer, "reset_contrast_brightness"):
            self.viewer.reset_contrast_brightness()
        self.update_display()
        self.status("Cleared current frame", 2000)

    def reset_current(self) -> None:
        """Reset display parameters for current frame."""
        frame = self.frames.current_frame
        if frame is None:
            return
        self.reset_view_defaults(frame)
        self.window.z1 = None
        self.window.z2 = None
        if hasattr(self.viewer, "reset_contrast_brightness"):
            self.viewer.reset_contrast_brightness()
        self.update_display()
        self.status("Reset current frame", 2000)

    def refresh_current(self) -> None:
        """Refresh current frame display."""
        self.update_display()
        self.status("Refreshed current frame", 2000)

    def move_first(self) -> None:
        """Move current frame to first position."""
        current = self.frames.current_index
        if self.frames.move_frame(current, 0):
            self.update_display()

    def move_back(self) -> None:
        """Move current frame one position backward."""
        count = self.frames.num_frames
        current = self.frames.current_index
        target = count - 1 if current <= 0 else current - 1
        if self.frames.move_frame(current, target):
            self.update_display()

    def move_forward(self) -> None:
        """Move current frame one position forward."""
        count = self.frames.num_frames
        current = self.frames.current_index
        target = 0 if current >= count - 1 else current + 1
        if self.frames.move_frame(current, target):
            self.update_display()

    def move_last(self) -> None:
        """Move current frame to last position."""
        current = self.frames.current_index
        if self.frames.move_frame(current, self.frames.num_frames - 1):
            self.update_display()

    def set_active(self, frame_id: int, active: bool) -> None:
        """Set active visibility state for a frame."""
        if active:
            self.window._active_frame_ids.add(frame_id)
        else:
            if frame_id not in self.window._active_frame_ids:
                return
            if len(self.window._active_frame_ids) <= 1:
                self.status("At least one frame must remain visible", 2000)
                self.refresh_menu_items()
                return
            self.window._active_frame_ids.remove(frame_id)
        self.ensure_active_valid()
        current_frame = self.frames.current_frame
        if current_frame and current_frame.frame_id not in self.window._active_frame_ids:
            active_indices = self.active_indices()
            if active_indices:
                self.frames.goto_frame(active_indices[0])
        if len(self.active_indices()) <= 1 and self.window._frame_display_mode in {"blink", "fade"}:
            self.set_display_mode("single")
        else:
            self.update_display()

    def show_all(self) -> None:
        """Mark all frames active."""
        self.window._active_frame_ids = {frame.frame_id for frame in self.frames.frames}
        self.update_display()

    def hide_all(self) -> None:
        """Hide all but the current frame."""
        current = self.frames.current_frame
        if current is None:
            return
        self.window._active_frame_ids = {current.frame_id}
        if self.window._frame_display_mode in {"blink", "fade"}:
            self.set_display_mode("single")
        else:
            self.update_display()

    def first(self) -> None:
        """Go to first active frame."""
        active_indices = self.active_indices()
        if active_indices:
            self.goto_index(active_indices[0])

    def previous(self) -> None:
        """Go to previous active frame."""
        active_indices = self.active_indices()
        if not active_indices:
            return
        current = self.frames.current_index
        if current not in active_indices:
            self.goto_index(active_indices[0])
            return
        pos = active_indices.index(current)
        self.goto_index(active_indices[(pos - 1) % len(active_indices)])

    def next(self) -> None:
        """Go to next active frame."""
        active_indices = self.active_indices()
        if not active_indices:
            return
        current = self.frames.current_index
        if current not in active_indices:
            self.goto_index(active_indices[0])
            return
        pos = active_indices.index(current)
        self.goto_index(active_indices[(pos + 1) % len(active_indices)])

    def last(self) -> None:
        """Go to last active frame."""
        active_indices = self.active_indices()
        if active_indices:
            self.goto_index(active_indices[-1])

    def update_title(self) -> None:
        """Update window title with current frame info."""
        frame = self.frames.current_frame
        frame_info = f"Frame {self.frames.current_index + 1}/{self.frames.num_frames}"
        if frame and frame.filepath:
            self.window.setWindowTitle(f"NCRADS9 - {frame.filepath.name} [{frame_info}]")
        else:
            self.window.setWindowTitle(f"NCRADS9 [{frame_info}]")
        self.status(frame_info, 2000)

    def update_display(self) -> None:
        """Update UI to reflect the current frame."""
        self.ensure_active_valid()
        self.window._tile_mode_enabled = self.window._frame_display_mode == "tile"
        if self.window._tile_mode_enabled:
            if not self.window.display.display_tiled():
                self.set_display_mode("single")
                return
            self.refresh_menu_items()
            self.update_title()
            return

        frame = self.frames.current_frame
        self.window.region.show_frame_regions(frame)
        if frame and frame.has_data:
            self.apply_view_state(frame)
            self.window.display.display()
            self.apply_view_state(frame)
            self.status_bar.update_image_info(frame.image_data.shape[1], frame.image_data.shape[0])
            if self.window.using_gpu_rendering and hasattr(self.viewer, "gl_canvas"):
                self.viewer.gl_canvas.reset_view()
                if frame.zoom:
                    self.viewer.zoom_to(frame.zoom)
        else:
            self.status_bar.update_image_info(None, None)
            if hasattr(self.viewer, "set_direction_arrows"):
                self.viewer.set_direction_arrows(None, None, False)
            if hasattr(self.window, "panner_panel"):
                self.window.panner_panel.set_view_rect(None)
        self.refresh_menu_items()
        self.update_title()

    def advance_blink(self) -> None:
        """Advance blink animation and refresh display."""
        if self.window._frame_display_mode not in {"blink", "fade"}:
            return
        next_index = self.window._blink_controller.next_index(
            self.active_indices(),
            self.frames.current_index,
        )
        if next_index is None:
            # Fewer than two frames left visible; nothing to blink between.
            self.set_display_mode("single")
            return
        self.frames.goto_frame(next_index)
        self.update_display()

    def show_single(self, checked: bool = False) -> None:
        """Set display mode to single-frame."""
        _ = checked
        self.set_display_mode("single")

    def set_display_mode(self, mode: str) -> None:
        """Set frame display mode and synchronize UI/timers."""
        if mode not in {"single", "tile", "blink", "fade"}:
            return
        if mode in {"blink", "fade"} and len(self.active_indices()) <= 1:
            mode = "single"
            self.status("Need at least two visible frames", 2000)

        self.window._frame_display_mode = mode
        self.window._tile_mode_enabled = mode == "tile"

        self.menu.action_single_frame.blockSignals(True)
        self.menu.action_tile_frames.blockSignals(True)
        self.menu.action_blink_frames.blockSignals(True)
        self.menu.action_fade_frames.blockSignals(True)
        self.menu.action_single_frame.setChecked(mode == "single")
        self.menu.action_tile_frames.setChecked(mode == "tile")
        self.menu.action_blink_frames.setChecked(mode == "blink")
        self.menu.action_fade_frames.setChecked(mode == "fade")
        self.menu.action_single_frame.blockSignals(False)
        self.menu.action_tile_frames.blockSignals(False)
        self.menu.action_blink_frames.blockSignals(False)
        self.menu.action_fade_frames.blockSignals(False)

        if mode == "blink":
            self.window._blink_timer.start(self.window._blink_timer.interval())
            self.status("Blinking started", 2000)
        elif mode == "fade":
            self.window._blink_timer.start(self.window._fade_interval_ms)
            self.status("Fade mode enabled", 2000)
        else:
            self.window._blink_timer.stop()
            if mode == "tile":
                self.status("Frame tiling enabled", 2000)
            else:
                self.status("Single frame mode", 2000)

        if mode != "tile":
            self.window._tile_layout = None
        self.update_display()

    def set_blink(self, checked: bool) -> None:
        """Start/stop frame blinking."""
        if checked:
            self.set_display_mode("blink")
        elif self.window._frame_display_mode == "blink":
            self.set_display_mode("single")

    def set_fade(self, checked: bool) -> None:
        """Start/stop frame fading."""
        if checked:
            self.set_display_mode("fade")
        elif self.window._frame_display_mode == "fade":
            self.set_display_mode("single")

    def set_tile(self, checked: bool) -> None:
        """Toggle tiled display of loaded frames."""
        if checked:
            self.set_display_mode("tile")
        elif self.window._frame_display_mode == "tile":
            self.set_display_mode("single")

    def set_tile_arrangement(self, mode: str) -> None:
        """Set tile arrangement mode."""
        self.window._tile_arrangement_mode = mode
        if self.window._frame_display_mode == "tile":
            self.update_display()

    def set_blink_interval(self, interval_ms: int) -> None:
        """Set the blink step interval and restart the timer if blinking."""
        self.window._blink_timer.setInterval(self.window._blink_controller.set_interval(interval_ms))
        if self.window._frame_display_mode == "blink":
            self.window._blink_timer.start(self.window._blink_timer.interval())

    def set_fade_interval(self, interval_ms: int) -> None:
        """Set the fade step interval and restart the timer if fading."""
        self.window._fade_interval_ms = max(1, int(interval_ms))
        if self.window._frame_display_mode == "fade":
            self.window._blink_timer.start(self.window._fade_interval_ms)

    def show_frame_dialog(self, frame_mode: str) -> None:
        """Open frame mode dialog."""
        if frame_mode == "rgb":
            self.show_rgb_dialog()
            return
        if frame_mode == "cube":
            self.show_cube_dialog()
            return
        self.status(f"{frame_mode.upper()} parameters dialog not yet implemented", 2000)

    # -- data cubes ----------------------------------------------------------

    def cube_handler(self, frame: Frame | None = None) -> CubeHandler | None:
        """A `CubeHandler` over a frame's extension, if it is a cube.

        Reads `frame.image`, the array as it came off disk, not
        `frame.image_data`, which by then holds the displayed slice.

        Args:
            frame: The frame to look at. Defaults to the current one.

        Returns:
            The handler, or None when the frame holds no cube.
        """
        frame = frame or self.frames.current_frame
        if frame is None or frame.image is None or not is_cube(frame.image.data):
            return None
        return CubeHandler(frame.image.data, frame.image.header)

    def show_cube_dialog(self) -> None:
        """Show DS9's Cube dialog for the current frame."""
        handler = self.cube_handler()
        if handler is None:
            self.status("The current frame holds no data cube", 3000)
            return
        frame = self.frames.current_frame
        if frame is None:
            return

        dialog = self.window.cube_dialog
        dialog.set_axis_order(frame.axis_order, notify=False)
        dialog.set_depth(handler.depth(frame.axis_order), frame.slice_index)
        self.update_cube_coordinate()
        dialog.show()
        dialog.raise_()

    def set_slice(self, slice_index: int) -> None:
        """Show one slice of the current frame's cube.

        Args:
            slice_index: The slice, counting from zero. Clamped to the cube.
        """
        handler = self.cube_handler()
        frame = self.frames.current_frame
        if handler is None or frame is None:
            return

        depth = handler.depth(frame.axis_order)
        wanted = max(0, min(int(slice_index), depth - 1))
        plane = handler.get_slice(wanted, frame.axis_order)
        if plane is None:
            return

        frame.slice_index = wanted
        frame.image_data = plane
        frame.original_image_data = plane
        # Rescale to the new slice. DS9's default scale scope is local, so the
        # limits follow the displayed data; keeping the previous slice's
        # limits makes a cube whose brightness varies with channel saturate
        # to flat white or flat black as you step through it. M5-4 adds the
        # global scope for anyone who wants the limits held still.
        frame.z1 = None
        frame.z2 = None
        self.window.z1 = None
        self.window.z2 = None
        self.window.display.display()
        self.update_cube_coordinate()

    def set_axis_order(self, order: str | AxisOrder) -> None:
        """Re-slice the current frame along a different axis.

        Args:
            order: A three-digit order, as DS9's Axis Order menu gives it.
        """
        handler = self.cube_handler()
        frame = self.frames.current_frame
        if handler is None or frame is None:
            return

        try:
            axes = AxisOrder.parse(order)
        except ValueError as exc:
            self.status(str(exc), 3000)
            return

        frame.axis_order = str(axes)
        depth = handler.depth(axes)
        # The new slice axis is a different length, so the old index may be
        # past its end.
        frame.slice_index = min(frame.slice_index, depth - 1)
        self.window.cube_dialog.set_depth(depth, frame.slice_index)
        self.set_slice(frame.slice_index)
        self.status(f"Axis order: {axes}")

    def update_cube_coordinate(self) -> None:
        """Show the current slice's world coordinate on the Cube dialog."""
        handler = self.cube_handler()
        frame = self.frames.current_frame
        dialog = self.window.cube_dialog
        if handler is None or frame is None:
            dialog.set_coordinate("")
            return
        coordinate = handler.slice_coordinate(frame.slice_index, frame.axis_order)
        if coordinate is None:
            dialog.set_coordinate("")
            return
        value, unit = coordinate
        dialog.set_coordinate(f"{value:.6g} {unit}".strip())

    def sync_cube_dialog(self) -> None:
        """Bring the Cube dialog in step with the current frame."""
        dialog = getattr(self.window, "cube_dialog", None)
        if dialog is None or not dialog.isVisible():
            return
        handler = self.cube_handler()
        frame = self.frames.current_frame
        if handler is None or frame is None:
            dialog.set_depth(1, 0)
            dialog.set_coordinate("")
            return
        dialog.set_axis_order(frame.axis_order, notify=False)
        dialog.set_depth(handler.depth(frame.axis_order), frame.slice_index)
        self.update_cube_coordinate()

    def show_rgb_dialog(self) -> None:
        """Show DS9-style RGB channel dialog."""
        self.persist_view_state()
        frame = self.frames.current_frame
        if frame is None or frame.frame_type != "rgb":
            self.new_frame_of_type("rgb")
            frame = self.frames.current_frame
        if frame is None:
            return

        dialog = QDialog(None)
        dialog.setWindowFlag(Qt.WindowType.Window, True)
        dialog.setWindowTitle("RGB")
        layout = QVBoxLayout(dialog)

        channel_group = QGroupBox("Current Channel", dialog)
        channel_layout = QHBoxLayout(channel_group)
        button_group = QButtonGroup(channel_group)
        radio_buttons: dict[str, QRadioButton] = {}
        for channel in self.window.display.channel_names():
            radio = QRadioButton(channel.capitalize(), channel_group)
            radio.setChecked(frame.rgb_current_channel == channel)
            button_group.addButton(radio)
            channel_layout.addWidget(radio)
            radio_buttons[channel] = radio
        layout.addWidget(channel_group)

        view_group = QGroupBox("View", dialog)
        view_layout = QHBoxLayout(view_group)
        view_checks: dict[str, QCheckBox] = {}
        for channel in self.window.display.channel_names():
            checkbox = QCheckBox(channel.capitalize(), view_group)
            checkbox.setChecked(frame.rgb_view.get(channel, True))
            view_layout.addWidget(checkbox)
            view_checks[channel] = checkbox
        layout.addWidget(view_group)

        settings_group = QGroupBox("Per-Channel Display Settings", dialog)
        settings_layout = QGridLayout(settings_group)
        settings_layout.addWidget(QLabel("Channel"), 0, 0)
        settings_layout.addWidget(QLabel("Scale"), 0, 1)
        settings_layout.addWidget(QLabel("Auto"), 0, 2)
        settings_layout.addWidget(QLabel("Min"), 0, 3)
        settings_layout.addWidget(QLabel("Max"), 0, 4)
        settings_layout.addWidget(QLabel("Contrast"), 0, 5)
        settings_layout.addWidget(QLabel("Brightness"), 0, 6)

        scale_choices: list[tuple[str, ScaleAlgorithm]] = [
            ("Linear", ScaleAlgorithm.LINEAR),
            ("Log", ScaleAlgorithm.LOG),
            ("Sqrt", ScaleAlgorithm.SQRT),
            ("Squared", ScaleAlgorithm.POWER),
            ("Asinh", ScaleAlgorithm.ASINH),
            ("HistEq", ScaleAlgorithm.HISTOGRAM_EQUALIZATION),
        ]
        channel_settings: dict[str, dict[str, object]] = {}
        for row, channel in enumerate(self.window.display.channel_names(), start=1):
            settings_layout.addWidget(QLabel(channel.capitalize()), row, 0)

            scale_combo = QComboBox(settings_group)
            for label, _scale in scale_choices:
                scale_combo.addItem(label)
            channel_scale = frame.rgb_channel_scale.get(channel, ScaleAlgorithm.LINEAR)
            scale_index = next(
                (idx for idx, (_, scale) in enumerate(scale_choices) if scale == channel_scale),
                0,
            )
            scale_combo.setCurrentIndex(scale_index)
            settings_layout.addWidget(scale_combo, row, 1)

            auto_limits = QCheckBox(settings_group)
            channel_z1 = frame.rgb_channel_z1.get(channel)
            channel_z2 = frame.rgb_channel_z2.get(channel)
            auto_limits.setChecked(channel_z1 is None or channel_z2 is None)
            settings_layout.addWidget(auto_limits, row, 2)

            min_spin = QDoubleSpinBox(settings_group)
            min_spin.setDecimals(6)
            min_spin.setRange(-1e30, 1e30)
            min_spin.setValue(float(channel_z1) if channel_z1 is not None else 0.0)
            settings_layout.addWidget(min_spin, row, 3)

            max_spin = QDoubleSpinBox(settings_group)
            max_spin.setDecimals(6)
            max_spin.setRange(-1e30, 1e30)
            max_spin.setValue(float(channel_z2) if channel_z2 is not None else 1.0)
            settings_layout.addWidget(max_spin, row, 4)

            contrast_spin = QDoubleSpinBox(settings_group)
            contrast_spin.setDecimals(3)
            contrast_spin.setRange(0.1, 10.0)
            contrast_spin.setValue(float(frame.rgb_channel_contrast.get(channel, 1.0)))
            settings_layout.addWidget(contrast_spin, row, 5)

            brightness_spin = QDoubleSpinBox(settings_group)
            brightness_spin.setDecimals(3)
            brightness_spin.setRange(-1.0, 1.0)
            brightness_spin.setSingleStep(0.05)
            brightness_spin.setValue(float(frame.rgb_channel_brightness.get(channel, 0.0)))
            settings_layout.addWidget(brightness_spin, row, 6)

            min_spin.setEnabled(not auto_limits.isChecked())
            max_spin.setEnabled(not auto_limits.isChecked())
            auto_limits.toggled.connect(
                lambda checked, lo=min_spin, hi=max_spin: (
                    lo.setEnabled(not checked),
                    hi.setEnabled(not checked),
                )
            )

            channel_settings[channel] = {
                "scale_combo": scale_combo,
                "auto_limits": auto_limits,
                "min_spin": min_spin,
                "max_spin": max_spin,
                "contrast_spin": contrast_spin,
                "brightness_spin": brightness_spin,
            }
        layout.addWidget(settings_group)

        source_group = QGroupBox("Assign Channels from Existing Frames", dialog)
        source_layout = QFormLayout(source_group)
        source_combos: dict[str, QComboBox] = {}
        source_frames = [
            (index, candidate)
            for index, candidate in enumerate(self.frames.frames)
            if candidate.frame_id != frame.frame_id
            and candidate.image_data is not None
            and candidate.image_data.ndim == 2
        ]
        for channel in self.window.display.channel_names():
            combo = QComboBox(source_group)
            combo.addItem("Keep current data", "KEEP")
            combo.addItem("None (clear)", "CLEAR")
            for index, source_frame in source_frames:
                label = f"Frame {index + 1}"
                if source_frame.filepath:
                    label += f" - {source_frame.filepath.name}"
                combo.addItem(label, index)
            source_id = frame.rgb_source_frame_ids.get(channel)
            if source_id is not None:
                for item_index in range(combo.count()):
                    source_index = combo.itemData(item_index)
                    if (
                        isinstance(source_index, int)
                        and source_index < len(self.frames.frames)
                        and self.frames.frames[source_index].frame_id == source_id
                    ):
                        combo.setCurrentIndex(item_index)
                        break
            source_layout.addRow(channel.capitalize(), combo)
            source_combos[channel] = combo
        layout.addWidget(source_group)

        def apply_changes() -> None:
            for channel, radio in radio_buttons.items():
                if radio.isChecked():
                    frame.rgb_current_channel = channel
                    break
            for channel, checkbox in view_checks.items():
                frame.rgb_view[channel] = checkbox.isChecked()

            for channel, controls in channel_settings.items():
                scale_combo = controls["scale_combo"]
                auto_limits = controls["auto_limits"]
                min_spin = controls["min_spin"]
                max_spin = controls["max_spin"]
                contrast_spin = controls["contrast_spin"]
                brightness_spin = controls["brightness_spin"]

                if isinstance(scale_combo, QComboBox):
                    _, selected_scale = scale_choices[scale_combo.currentIndex()]
                    frame.rgb_channel_scale[channel] = selected_scale
                if isinstance(auto_limits, QCheckBox) and auto_limits.isChecked():
                    frame.rgb_channel_z1[channel] = None
                    frame.rgb_channel_z2[channel] = None
                else:
                    low = float(min_spin.value()) if isinstance(min_spin, QDoubleSpinBox) else 0.0
                    high = float(max_spin.value()) if isinstance(max_spin, QDoubleSpinBox) else 1.0
                    frame.rgb_channel_z1[channel] = min(low, high)
                    frame.rgb_channel_z2[channel] = max(low, high)
                frame.rgb_channel_contrast[channel] = (
                    float(contrast_spin.value()) if isinstance(contrast_spin, QDoubleSpinBox) else 1.0
                )
                frame.rgb_channel_brightness[channel] = (
                    float(brightness_spin.value()) if isinstance(brightness_spin, QDoubleSpinBox) else 0.0
                )

            updates: dict[str, int | None] = {}
            for channel, combo in source_combos.items():
                value = combo.currentData()
                if value == "KEEP":
                    continue
                if value == "CLEAR":
                    updates[channel] = None
                elif isinstance(value, int):
                    updates[channel] = value
            if updates:
                self.window.display.apply_rgb_channels_from_sources(frame, updates)
            else:
                self.window.display.sync_rgb_scalar_view(frame)

            self.window.display.sync_view_state_from_channel(frame)
            self.apply_view_state(frame)
            self.window.display.display()
            active = frame.rgb_current_channel.capitalize()
            self.status(f"RGB updated (active channel: {active})", 2000)

        def apply_and_close() -> None:
            apply_changes()
            dialog.accept()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            dialog,
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.clicked.connect(apply_and_close)
        if apply_button is not None:
            apply_button.clicked.connect(apply_changes)
        if cancel_button is not None:
            cancel_button.clicked.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def set_lock_scope(self, scope: str, value: str) -> None:
        """Set lock scope value."""
        self.window._frame_lock_scope[scope] = value
        self.status(f"Frame lock {scope}: {value}", 2000)

    def set_lock_flag(self, flag: str, enabled: bool) -> None:
        """Turn one Frame -> Lock flag on or off.

        Most of these flags are recorded and not yet acted on; making every
        one of them live is M9's remaining lock work. `block` is live as of
        M5-20 -- changing the block factor with it on changes every frame's.
        """
        self.window._frame_lock_flags[flag] = bool(enabled)
        state = "on" if enabled else "off"
        self.status(f"Frame lock {flag}: {state}", 2000)

        if flag == "bin" and enabled:
            self.status("Bin-table binning arrives in M5-16; see Lock Block", 3000)
        elif flag == "block" and enabled:
            self.match_block()

    def block_is_locked(self) -> bool:
        """Whether a block change should be copied to every frame."""
        return bool(self.window._frame_lock_flags.get("block"))

    def select_tile_at(self, x: int, y: int) -> bool:
        """Select frame corresponding to a click on the tiled composite."""
        if self.window._tile_layout is None:
            return False

        tile_index = self.window._tile_layout.tile_at(x, y)
        if tile_index is None or tile_index >= len(self.window._tile_frame_indices):
            return False
        frame_index = int(self.window._tile_frame_indices[tile_index])
        if frame_index == self.frames.current_index:
            return False
        self.frames.goto_frame(frame_index)
        self.apply_view_state(self.frames.current_frame)
        return True

    def persist_view_state(self) -> None:
        """Persist display settings to the current frame."""
        frame = self.frames.current_frame
        if not frame:
            return
        contrast, brightness = self.viewer.get_contrast_brightness()
        if frame.frame_type == "rgb":
            channel = frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
            frame.rgb_channel_scale[channel] = self.window.current_scale
            frame.rgb_channel_z1[channel] = self.window.z1
            frame.rgb_channel_z2[channel] = self.window.z2
            frame.rgb_channel_contrast[channel] = contrast
            frame.rgb_channel_brightness[channel] = brightness
        frame.colormap = self.window.current_colormap
        frame.scale = self.window.current_scale
        frame.invert_colormap = self.window.invert_colormap
        frame.z1 = self.window.z1
        frame.z2 = self.window.z2
        frame.zoom = self.viewer.get_zoom()
        frame.contrast = contrast
        frame.brightness = brightness
        frame.rotation = normalize_rotation(frame.rotation)
        if self.window.using_gpu_rendering and hasattr(self.viewer, "gl_canvas"):
            frame.pan_x, frame.pan_y = self.viewer.gl_canvas.pan_offset
        else:
            pan_center = self.window.display.cpu_pan_center()
            if pan_center is not None:
                frame.pan_x, frame.pan_y = pan_center

    def apply_view_state(self, frame: Frame) -> None:
        """Apply stored display settings from the frame."""
        self.window.display.apply_view_transform(frame)
        self.window.current_colormap = self.window.color.normalize_name(frame.colormap)
        self.window.invert_colormap = frame.invert_colormap
        if frame.frame_type == "rgb":
            self.window.display.sync_view_state_from_channel(frame)
        else:
            self.window.current_scale = frame.scale
            self.window.z1 = frame.z1
            self.window.z2 = frame.z2
        self.window.color.sync()
        self.menu.action_invert_colormap.setChecked(self.window.invert_colormap)
        self.menu.action_scale_linear.setChecked(self.window.current_scale == ScaleAlgorithm.LINEAR)
        self.menu.action_scale_log.setChecked(self.window.current_scale == ScaleAlgorithm.LOG)
        self.menu.action_scale_sqrt.setChecked(self.window.current_scale == ScaleAlgorithm.SQRT)
        self.menu.action_scale_squared.setChecked(self.window.current_scale == ScaleAlgorithm.POWER)
        self.menu.action_scale_asinh.setChecked(self.window.current_scale == ScaleAlgorithm.ASINH)
        self.menu.action_scale_histeq.setChecked(
            self.window.current_scale == ScaleAlgorithm.HISTOGRAM_EQUALIZATION
        )
        cmap_name_map = {
            "grey": "Gray",
            "heat": "Heat",
            "cool": "Cool",
            "rainbow": "Rainbow",
        }
        if self.window.current_colormap in cmap_name_map:
            self.window.button_bar.set_colormap(cmap_name_map[self.window.current_colormap])
        scale_name_map = {
            ScaleAlgorithm.LINEAR: "Linear",
            ScaleAlgorithm.LOG: "Log",
            ScaleAlgorithm.SQRT: "Sqrt",
            ScaleAlgorithm.POWER: "Squared",
            ScaleAlgorithm.ASINH: "Asinh",
            ScaleAlgorithm.HISTOGRAM_EQUALIZATION: "HistEq",
        }
        if self.window.current_scale in scale_name_map:
            self.window.button_bar.set_scale(scale_name_map[self.window.current_scale])
        if frame.frame_type != "rgb":
            self.window.color.set_contrast_brightness(frame.contrast, frame.brightness)
        if frame.zoom:
            self.viewer.zoom_to(frame.zoom)
        if self.window.using_gpu_rendering and hasattr(self.viewer, "set_pan"):
            self.viewer.set_pan(frame.pan_x, frame.pan_y)
        elif hasattr(self.viewer, "image_viewer"):
            display_coords = self.viewer.image_viewer.map_image_to_display_coords(
                frame.pan_x,
                frame.pan_y,
            )
            if display_coords is not None:
                viewport = self.window.scroll_area.viewport().size()
                zoom = max(self.viewer.get_zoom(), 1e-6)
                display_x, display_y = display_coords
                self.window.scroll_area.horizontalScrollBar().setValue(
                    int(display_x * zoom - viewport.width() / 2)
                )
                self.window.scroll_area.verticalScrollBar().setValue(
                    int(display_y * zoom - viewport.height() / 2)
                )
        self.window.zoom.sync()

    def sync_view_state(self) -> None:
        """Persist current view state after rendering."""
        self.persist_view_state()

    def apply_locks(self) -> None:
        """Propagate zoom/orientation/rotation according to frame lock scope."""
        scope = self.window._frame_lock_scope.get("frame", "none")
        if scope == "wcs":
            self.match_wcs()
        elif scope != "none":
            self.match_image()

    def match_image(self) -> None:
        """Match all frames to current image view settings."""
        source = self.frames.current_frame
        if not source:
            self.status("No frame to match", 2000)
            return
        for frame in self.frames.frames:
            if frame is source:
                continue
            frame.colormap = source.colormap
            frame.scale = source.scale
            frame.invert_colormap = source.invert_colormap
            frame.z1 = source.z1
            frame.z2 = source.z2
            frame.zoom = source.zoom
            frame.pan_x = source.pan_x
            frame.pan_y = source.pan_y
            frame.rotation = source.rotation
            frame.flip_x = source.flip_x
            frame.flip_y = source.flip_y
            frame.align_wcs = source.align_wcs
            frame.contrast = source.contrast
            frame.brightness = source.brightness
        self.status("Matched frames (image)", 2000)

    def match_wcs(self) -> None:
        """Match all frames to current frame using WCS."""
        source = self.frames.current_frame
        if not source or not source.wcs_handler or not source.wcs_handler.is_valid:
            self.status("Current frame has no valid WCS", 2000)
            return
        if source.image_data is None:
            self.status("Current frame has no image data", 2000)
            return
        cx = source.image_data.shape[1] / 2
        cy = source.image_data.shape[0] / 2
        ra, dec = source.wcs_handler.pixel_to_world(cx, cy)
        for frame in self.frames.frames:
            if frame is source:
                continue
            if frame.wcs_handler and frame.wcs_handler.is_valid:
                fx, fy = frame.wcs_handler.world_to_pixel(ra, dec)
                frame.pan_x = float(fx)
                frame.pan_y = float(fy)
                frame.zoom = source.zoom
                frame.rotation = source.rotation
                frame.flip_x = source.flip_x
                frame.flip_y = source.flip_y
                frame.align_wcs = True
                frame.colormap = source.colormap
                frame.scale = source.scale
                frame.invert_colormap = source.invert_colormap
                frame.z1 = source.z1
                frame.z2 = source.z2
                frame.contrast = source.contrast
                frame.brightness = source.brightness
        self.status("Matched frames (WCS)", 2000)

    def match_bin(self) -> None:
        """Copy the bin-table binning of this frame to the others.

        DS9's Bin is the table-to-image conversion; nothing here does that
        yet (M5-16), so this reports rather than copying the block factor,
        which is what it used to do and which is what `match_block` is for.
        """
        if not self.frames.current_frame:
            self.status("No frame to match", 2000)
            return
        self.status("Bin-table binning arrives in M5-16; see Match Block", 3000)

    def match_axes_order(self) -> None:
        """Match cube axes order across frames."""
        self.status("Axes order matching is not yet implemented", 2000)

    def match_scale(self) -> None:
        """Match scale functions across frames."""
        source = self.frames.current_frame
        if not source:
            self.status("No frame to match", 2000)
            return
        for frame in self.frames.frames:
            if frame is not source:
                frame.scale = source.scale
        self.status("Matched frames (scale)", 2000)

    def match_scale_limits(self) -> None:
        """Match scale functions and limits across frames."""
        source = self.frames.current_frame
        if not source:
            self.status("No frame to match", 2000)
            return
        for frame in self.frames.frames:
            if frame is not source:
                frame.scale = source.scale
                frame.z1 = source.z1
                frame.z2 = source.z2
        self.status("Matched frames (scale and limits)", 2000)

    def match_colorbar(self) -> None:
        """Match colormap/colorbar choices across frames."""
        source = self.frames.current_frame
        if not source:
            self.status("No frame to match", 2000)
            return
        for frame in self.frames.frames:
            if frame is not source:
                frame.colormap = source.colormap
                frame.invert_colormap = source.invert_colormap
        self.status("Matched frames (colorbar)", 2000)

    def match_block(self) -> None:
        """Copy this frame's display block factor to the others."""
        source = self.frames.current_frame
        if not source:
            self.status("No frame to match", 2000)
            return
        for frame in self.frames.frames:
            if frame is not source:
                frame.block_factor = source.block_factor
        self.window.display.display()
        self.status(f"Matched frames (block {source.block_factor})", 2000)

    def match_smooth(self) -> None:
        """Match smoothing parameters across frames."""
        self.status("Smoothing parameters are global in this build", 2000)

    def match_3d(self) -> None:
        """Match 3D parameters across frames."""
        self.status("3D matching is not yet implemented", 2000)
