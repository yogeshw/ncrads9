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
What the pointer modes actually do to the application.

`ui/pointer_modes.py` decides what a drag *means*; this carries it out. The
split is what lets the meaning be tested without a display, and it is why
this class is mostly one short method per verb.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from ..pointer_modes import PointerHandler, handler_for
from .base import Controller

#: How much the view may be zoomed, either way.
MIN_ZOOM = 1.0 / 64.0
MAX_ZOOM = 64.0

#: The smallest crop, in image pixels. A one-pixel crop is not a view.
MIN_CROP = 2.0


class PointerController(Controller):
    """Carries out DS9's pointer modes."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: The active handler, or None in pointer, region and colorbar mode.
        self.handler: PointerHandler | None = None

    def set_mode(self, mode: str) -> PointerHandler | None:
        """Arm one pointer mode, and hand its handler to the overlay.

        Returns:
            The handler, or None for a mode with none.
        """
        self.handler = handler_for(mode, self)
        overlay = getattr(self.viewer, "region_overlay", None)
        if overlay is not None:
            overlay.pointer_handler = self.handler
            overlay.update()
        return self.handler

    # -- what the modes ask for -------------------------------------------------

    def pan_to(self, x: float, y: float) -> None:
        """Centre the view on an image position."""
        self.window.zoom.on_panner_pan(float(x), float(y))

    def pan_by(self, dx: float, dy: float) -> None:
        """Shift the view by an offset in image pixels."""
        centre = self._centre()
        if centre is None:
            return
        self.pan_to(centre[0] + dx, centre[1] + dy)

    def zoom_by(self, factor: float, x: float, y: float) -> None:
        """Zoom about an image position, then keep it centred."""
        viewer = self.viewer
        if not hasattr(viewer, "get_zoom"):
            return
        wanted = max(MIN_ZOOM, min(MAX_ZOOM, viewer.get_zoom() * float(factor)))
        self.window.zoom.set_zoom(wanted)
        # Zooming about a point means that point stays put, which is a pan
        # to it once the scale has changed.
        self.pan_to(x, y)

    def rotate_by(self, degrees: float) -> None:
        """Turn the view by an increment.

        The Zoom menu sets an absolute angle; a drag is relative, so the
        frame's current angle is read first.
        """
        frame = self.frame
        if frame is None:
            return
        self.window.zoom.set_rotation(float(getattr(frame, "rotation", 0.0)) + float(degrees))

    def crop_to(self, x0: float, y0: float, x1: float, y1: float) -> None:
        """Display only this rectangle, DS9's crop.

        The view does not move: a crop chooses what is displayed, not where
        the display is looking, which is what `zoom_to` is for.
        """
        if self.window.crop.crop_to(x0, y0, x1, y1):
            self.status(f"Cropped to {abs(x1 - x0):.0f} x {abs(y1 - y0):.0f} pixels")

    def zoom_to(self, x0: float, y0: float, x1: float, y1: float) -> None:
        """Centre a rectangle and zoom so it fills the viewport."""
        left, right = sorted((float(x0), float(x1)))
        bottom, top = sorted((float(y0), float(y1)))
        width = right - left
        height = top - bottom
        if width < MIN_CROP or height < MIN_CROP:
            self.status("That box is too small to zoom to", 3000)
            return

        viewport = self.window._effective_viewport_size()
        scale = min(viewport.width() / width, viewport.height() / height)
        self.window.zoom.set_zoom(max(MIN_ZOOM, min(MAX_ZOOM, scale)))
        self.pan_to((left + right) / 2.0, (bottom + top) / 2.0)
        self.status(f"Zoomed to {width:.0f} x {height:.0f} pixels")

    def examine_at(self, x: float, y: float, zoom: float) -> None:
        """Open a zoomed view of one position in a new frame.

        DS9 loads the same file into another frame, pans there and zooms in
        (`ExamineButtonBase`, `examine.tcl:29`), so the original view is
        left as it was -- which is the point of examining.
        """
        frame = self.frame
        path = getattr(frame, "filepath", None) if frame else None
        if path is None:
            self.status("Examine needs a frame with a file behind it", 3000)
            return

        self.window.frame_controller.new_frame()
        try:
            self.window.display.load_fits(str(path))
        except Exception as exc:
            self.status(f"Could not open a second view: {exc}", 4000)
            return

        self.window.zoom.set_zoom(max(MIN_ZOOM, min(MAX_ZOOM, float(zoom))))
        self.pan_to(x, y)
        self.status(f"Examining {x:.1f} {y:.1f} at {zoom:g}x")

    def move_crosshair(self, x: float, y: float) -> None:
        """Put the crosshair somewhere and update everything watching it."""
        self.window.crosshair.move_to(float(x), float(y))

    def turn_cube(self, dx: float, dy: float) -> None:
        """Turn a 3D frame's cube, as its pointer mode's drag asks."""
        self.window.frame_3d.rotate_by(float(dx), float(dy))

    def pick_at(self, x: float, y: float) -> bool:
        """Select the catalogue symbol at an image position, if any.

        Returns:
            Whether one was there.
        """
        overlay = getattr(self.viewer, "catalog_overlay", None)
        if overlay is None:
            return False
        return bool(overlay.pick(overlay._image_to_widget(x, y)))

    # -- helpers ------------------------------------------------------------------

    def _centre(self) -> tuple[float, float] | None:
        """Where the view is centred, in image pixels."""
        frame = self.frame
        data = getattr(frame, "image_data", None) if frame else None
        if data is None:
            return None
        pan = getattr(frame, "pan_center", None)
        if pan is not None:
            return (float(pan[0]), float(pan[1]))
        return (data.shape[1] / 2.0, data.shape[0] / 2.0)
