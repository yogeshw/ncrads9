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
The Zoom menu: zoom, pan, orientation, rotation and crop.

Both viewer backends are driven from here. The GPU canvas pans by moving the
image point that sits at the viewport centre; the CPU path pans by moving
scrollbars. Every method that pans has to handle both, which is why the
`using_gpu_rendering` branches appear as often as they do.

M9-2 adds the interactive crop mode DS9 has; this only offers the parameters
dialog. Arbitrary rotation angles are M5/M9 as well -- the menu presets are
0/90/180/270.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QRectF

from ..dialogs.pan_zoom_rotate_dialog import PanZoomRotateDialog
from ..view_transform import (
    flags_to_orientation,
    normalize_rotation,
    orientation_to_flags,
)
from .base import Controller

#: Ratio applied by one Zoom In or Zoom Out step.
ZOOM_STEP = 1.2

#: Smallest zoom the pan/zoom/rotate dialog will accept.
MIN_DIALOG_ZOOM = 0.01

#: Guard against dividing by a zero zoom.
MIN_ZOOM = 1e-6


class ZoomController(Controller):
    """Owns the Zoom menu."""

    def connect(self) -> None:
        """Wire the Zoom menu."""
        self.menu.action_zoom_center.triggered.connect(self.center_image)
        self.menu.action_zoom_align.triggered.connect(self.set_align_wcs)
        self.menu.action_zoom_in.triggered.connect(self.zoom_in)
        self.menu.action_zoom_out.triggered.connect(self.zoom_out)
        self.menu.action_zoom_fit.triggered.connect(self.zoom_fit)

        for value, action in self.menu.zoom_preset_actions.items():
            action.triggered.connect(lambda _checked=False, z=value: self.set_zoom(z))
        for token, action in self.menu.zoom_orientation_actions.items():
            action.triggered.connect(lambda _checked=False, o=token: self.set_orientation(o))
        for degrees, action in self.menu.zoom_rotation_actions.items():
            action.triggered.connect(lambda _checked=False, d=degrees: self.set_rotation(d))

        self.menu.action_pan_zoom_rotate_parameters.triggered.connect(self.show_pan_zoom_rotate_dialog)

    def sync(self) -> None:
        """Tick the Zoom menu entries matching the active frame.

        A zoom, orientation or rotation that is not one of the presets leaves
        the whole radio group unchecked, rather than rounding to the nearest
        preset and claiming a value the frame does not have. Qt needs the group
        made non-exclusive to clear every button.
        """
        frame = self.frame
        if frame is None:
            return

        preset = min(self.menu.zoom_preset_actions.keys(), key=lambda value: abs(value - frame.zoom))
        if np.isclose(frame.zoom, preset, atol=1e-6, rtol=1e-6):
            self.menu.zoom_preset_actions[preset].setChecked(True)
        else:
            self._clear_group(self.menu.zoom_preset_group, self.menu.zoom_preset_actions)

        self.menu.action_zoom_align.setChecked(bool(frame.align_wcs))
        self.menu.zoom_orientation_actions[self.orientation()].setChecked(True)

        rotation = normalize_rotation(frame.rotation)
        snapped = int(round(rotation / 90.0) * 90) % 360
        if np.isclose(rotation, snapped, atol=1e-6):
            self.menu.zoom_rotation_actions[snapped].setChecked(True)
        else:
            self._clear_group(self.menu.zoom_rotation_group, self.menu.zoom_rotation_actions)

    @staticmethod
    def _clear_group(group: object, actions: dict) -> None:
        """Uncheck every action in an exclusive group."""
        group.setExclusive(False)
        for action in actions.values():
            action.setChecked(False)
        group.setExclusive(True)

    # -- zoom ----------------------------------------------------------------

    def set_zoom(self, zoom: float) -> None:
        """Set an explicit zoom level."""
        self.viewer.zoom_to(zoom)
        self.status_bar.update_zoom(self.viewer.get_zoom())
        self.window.frame_controller.persist_view_state()
        self.sync()
        self.window.frame_controller.apply_locks()
        self.update_panner_rect()
        self.status(f"Zoom {self.viewer.get_zoom():.5g}", 1000)

    def zoom_in(self) -> None:
        """Zoom in one step."""
        self.set_zoom(self.viewer.get_zoom() * ZOOM_STEP)

    def zoom_out(self) -> None:
        """Zoom out one step."""
        self.set_zoom(self.viewer.get_zoom() / ZOOM_STEP)

    def zoom_actual(self) -> None:
        """Zoom to 1:1."""
        self.set_zoom(1.0)

    def zoom_fit(self) -> None:
        """Zoom so the whole image fits the viewport."""
        self.viewer.zoom_fit(self.window._effective_viewport_size())
        self.status_bar.update_zoom(self.viewer.get_zoom())
        self.window.frame_controller.persist_view_state()
        self.sync()
        self.window.frame_controller.apply_locks()
        self.update_panner_rect()
        self.status("Zoom to fit", 1000)

    def on_button_bar_zoom(self, level: str) -> None:
        """Handle a zoom chosen on the button bar.

        Labels are "Fit", "1", plain multipliers, or fractions like "1/2".
        """
        if level == "Fit":
            self.zoom_fit()
            return
        if level == "1":
            self.zoom_actual()
            return

        try:
            value = float(level)
        except ValueError:
            if "/" not in level:
                return
            numerator, denominator = level.split("/", 1)
            value = float(numerator) / float(denominator)

        self.viewer.zoom_to(value)
        self.status_bar.update_zoom(value)
        self.window.frame_controller.persist_view_state()
        self.update_panner_rect()
        self.status(f"Zoom: {level}", 1000)

    # -- orientation and rotation --------------------------------------------

    def orientation(self) -> str:
        """The current frame's orientation token: none, x, y or xy."""
        frame = self.frame
        if frame is None:
            return "none"
        return flags_to_orientation(frame.flip_x, frame.flip_y)

    def _reapply_transform(self, frame) -> None:
        """Redraw after a flip or rotation.

        The GPU path has to re-render, because the transform is baked into the
        tiles it uploads; the CPU path can transform the existing pixmap.
        """
        if self.window.using_gpu_rendering and (
            frame.flip_x or frame.flip_y or not np.isclose(frame.rotation, 0.0)
        ):
            self.refresh()
        else:
            self.window.display.refresh_transformed_view(frame)

    def set_orientation(self, orientation: str) -> None:
        """Flip the frame: none, x, y or xy."""
        frame = self.require_frame()
        if frame is None:
            return
        frame.flip_x, frame.flip_y = orientation_to_flags(orientation)
        self._reapply_transform(frame)
        self.window.frame_controller.persist_view_state()
        self.sync()
        self.window.frame_controller.apply_locks()
        self.status(f"Orientation: {orientation}", 1500)

    def set_rotation(self, degrees: float) -> None:
        """Rotate the frame to the given angle."""
        frame = self.require_frame()
        if frame is None:
            return
        frame.rotation = normalize_rotation(degrees)
        self._reapply_transform(frame)
        self.window.frame_controller.persist_view_state()
        self.sync()
        self.window.frame_controller.apply_locks()
        self.status(f"Rotation: {frame.rotation:.2f} degrees", 1500)

    def set_align_wcs(self, enabled: bool) -> None:
        """Align the frame to north-up, east-left."""
        frame = self.require_frame()
        if frame is None:
            return
        frame.align_wcs = bool(enabled)
        self.menu.action_zoom_align.setChecked(frame.align_wcs)
        self.window.frame_controller.apply_locks()
        self.status(f"WCS alignment: {'on' if frame.align_wcs else 'off'}", 1500)

    # -- pan -----------------------------------------------------------------

    def _scroll_to_image_point(self, x: float, y: float, viewport_size=None) -> None:
        """Centre the CPU viewport on one image point."""
        inner = getattr(self.viewer, "image_viewer", None)
        if inner is None:
            return
        display = inner.map_image_to_display_coords(x, y)
        if display is None:
            return
        size = viewport_size if viewport_size is not None else self.window.scroll_area.viewport().size()
        zoom = self.viewer.get_zoom()
        display_x, display_y = display
        self.window.scroll_area.horizontalScrollBar().setValue(int(display_x * zoom - size.width() / 2))
        self.window.scroll_area.verticalScrollBar().setValue(int(display_y * zoom - size.height() / 2))

    def center_image(self) -> None:
        """Centre the image in the viewport."""
        frame = self.require_frame()
        if frame is None:
            return

        if self.window.using_gpu_rendering and hasattr(self.viewer, "set_pan"):
            self.viewer.set_pan(
                float(frame.image_data.shape[1]) / 2.0,
                float(frame.image_data.shape[0]) / 2.0,
            )
        else:
            horizontal = self.window.scroll_area.horizontalScrollBar()
            vertical = self.window.scroll_area.verticalScrollBar()
            horizontal.setValue(horizontal.maximum() // 2)
            vertical.setValue(vertical.maximum() // 2)

        self.window.frame_controller.persist_view_state()
        self.window.frame_controller.apply_locks()
        self.update_panner_rect()
        self.status("Centered image", 1500)

    def on_panner_pan(self, x: float, y: float) -> None:
        """Handle a pan requested by clicking in the panner."""
        data = self.window.image_data
        if data is None:
            return

        if self.window.using_gpu_rendering:
            # The panner works top-down; the GL canvas pans in bottom-up
            # image coordinates.
            y_bottom = data.shape[0] - 1 - y
            self.viewer.set_pan(x, y_bottom)
            self.status(f"Panned to ({x:.0f}, {y_bottom:.0f})", 1000)
        else:
            zoom = self.viewer.get_zoom()
            viewport = self.window.scroll_area.viewport()
            self.window.scroll_area.horizontalScrollBar().setValue(int(x * zoom - viewport.width() / 2))
            self.window.scroll_area.verticalScrollBar().setValue(int(y * zoom - viewport.height() / 2))
            self.status(f"Panned to ({x:.0f}, {y:.0f})", 1000)

        self.window.frame_controller.persist_view_state()
        self.update_panner_rect()

    def pan_by_pixels(self, dx: int, dy: int) -> None:
        """Pan by a whole number of image pixels, as the arrow keys do."""
        if self.window.image_data is None:
            return

        if self.window.using_gpu_rendering and hasattr(self.viewer, "gl_canvas"):
            pan_x, pan_y = self.viewer.gl_canvas.pan_offset
            self.viewer.set_pan(pan_x + dx, pan_y + dy)
        else:
            step = max(1, int(round(max(self.viewer.get_zoom(), MIN_ZOOM))))
            horizontal = self.window.scroll_area.horizontalScrollBar()
            vertical = self.window.scroll_area.verticalScrollBar()
            horizontal.setValue(horizontal.value() + dx * step)
            # Scrollbars grow downward, image y grows upward.
            vertical.setValue(vertical.value() - dy * step)

        self.window.frame_controller.persist_view_state()
        self.update_panner_rect()

    def apply_frame_pan(self, frame) -> None:
        """Restore a frame's stored pan on the GPU canvas."""
        if not (self.window.using_gpu_rendering and hasattr(self.viewer, "gl_canvas")):
            return
        if frame.pan_x == 0.0 and frame.pan_y == 0.0:
            return
        canvas = self.viewer.gl_canvas
        canvas.pan_offset = (frame.pan_x, frame.pan_y)
        canvas.pan_changed.emit(frame.pan_x, frame.pan_y)
        canvas.update()

    def update_panner_rect(self) -> None:
        """Show the visible region as a rectangle in the panner."""
        if not hasattr(self.window, "panner_panel"):
            return
        if self.window._tile_mode_enabled or self.window.image_data is None:
            self.window.panner_panel.set_view_rect(None)
            return

        image_w, image_h = self.viewer.get_display_image_size()
        if image_w <= 0 or image_h <= 0:
            self.window.panner_panel.set_view_rect(None)
            return

        zoom = max(self.viewer.get_zoom(), MIN_ZOOM)
        if self.window.using_gpu_rendering and hasattr(self.viewer, "gl_canvas"):
            canvas = self.viewer.gl_canvas
            view_w = canvas.width() / zoom
            view_h = canvas.height() / zoom
            pan_x, pan_y = canvas.pan_offset
            x = pan_x - view_w / 2.0
            # The panner draws top-down; the canvas pans bottom-up.
            y = image_h - (pan_y - view_h / 2.0 + view_h)
        else:
            viewport = self.window.scroll_area.viewport()
            view_w = viewport.width() / zoom
            view_h = viewport.height() / zoom
            x = self.window.scroll_area.horizontalScrollBar().value() / zoom
            y = self.window.scroll_area.verticalScrollBar().value() / zoom

        rect_w = min(float(image_w), max(1.0, float(view_w)))
        rect_h = min(float(image_h), max(1.0, float(view_h)))
        x = max(0.0, min(float(image_w) - rect_w, float(x)))
        y = max(0.0, min(float(image_h) - rect_h, float(y)))
        self.window.panner_panel.set_view_rect(QRectF(x, y, rect_w, rect_h))

    # -- crop ----------------------------------------------------------------

    # -- pan/zoom/rotate dialog ----------------------------------------------

    def apply_pan_zoom_rotate_parameters(self, params: dict) -> None:
        """Apply the Pan Zoom Rotate dialog's settings."""
        frame = self.require_frame()
        if frame is None:
            return

        zoom = max(MIN_DIALOG_ZOOM, float(params["zoom"]))
        pan_x = float(params["pan_x"])
        pan_y = float(params["pan_y"])

        frame.align_wcs = bool(params.get("align", frame.align_wcs))
        self.menu.action_zoom_align.setChecked(frame.align_wcs)
        self.viewer.zoom_to(zoom)
        frame.rotation = normalize_rotation(float(params["rotation"]))
        self.window.display.apply_view_transform(frame)

        if self.window.using_gpu_rendering and hasattr(self.viewer, "set_pan"):
            self.viewer.set_pan(pan_x, pan_y)
        else:
            self._scroll_to_image_point(pan_x, pan_y)

        self.refresh()
        self.window.frame_controller.persist_view_state()
        self.sync()
        self.window.frame_controller.apply_locks()
        self.update_panner_rect()
        self.status("Pan/zoom/rotate updated", 1500)

    def show_pan_zoom_rotate_dialog(self) -> None:
        """Show the Pan Zoom Rotate dialog, seeded from the frame."""
        frame = self.require_frame()
        if frame is None:
            return

        dialog = PanZoomRotateDialog(self.window)
        dialog.set_values(
            zoom=frame.zoom,
            pan_x=frame.pan_x,
            pan_y=frame.pan_y,
            rotation=frame.rotation,
            align=frame.align_wcs,
        )
        dialog.parameters_changed.connect(self.apply_pan_zoom_rotate_parameters)
        dialog.exec()
