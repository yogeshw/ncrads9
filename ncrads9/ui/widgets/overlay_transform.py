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
The image-to-widget mapping every overlay needs.

Three overlays sit on the image viewer -- regions, contours-and-grid, and
catalogue symbols -- and all three have to turn an image coordinate into a
place on the widget through the same zoom, pan, rotation and flips. Held
here once so a fourth cannot get it subtly different, which is how an
overlay ends up half a pixel or a whole flip away from the picture.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF

from ..view_transform import DisplayTransform


class OverlayTransformMixin:
    """Gives a widget the viewer's coordinate mapping.

    The host must call `set_zoom` whenever the view changes, which is what
    `ImageViewerWithRegions._update_overlay_transform` does for all of them.
    """

    def init_transform(self) -> None:
        """Set the mapping to the identity. Call from `__init__`."""
        self._zoom: float = 1.0
        self._offset: tuple[float, float] = (0.0, 0.0)
        self._image_width: int = 0
        self._image_height: int = 0
        self._rotation: float = 0.0
        self._flip_x: bool = False
        self._flip_y: bool = False

    def set_zoom(
        self,
        zoom: float,
        offset: tuple[float, float],
        image_width: int | None = None,
        image_height: int | None = None,
        rotation: float = 0.0,
        flip_x: bool = False,
        flip_y: bool = False,
    ) -> None:
        """Set the zoom, pan, rotation and flips the viewer is showing."""
        self._zoom = zoom
        self._offset = offset
        if image_width is not None:
            self._image_width = max(0, int(image_width))
        if image_height is not None:
            self._image_height = max(0, int(image_height))
        self._rotation = rotation
        self._flip_x = flip_x
        self._flip_y = flip_y
        self.update()

    def _display_transform(self) -> DisplayTransform:
        """The rotation and flips, as the view transform expresses them."""
        return DisplayTransform(
            width=self._image_width,
            height=self._image_height,
            rotation=self._rotation,
            flip_x=self._flip_x,
            flip_y=self._flip_y,
        )

    def _image_to_widget(self, x: float, y: float) -> QPointF:
        """Where an image coordinate lands on the widget.

        Image coordinates count from the bottom left, as FITS and DS9 do;
        widget coordinates from the top left, as Qt does. That flip is the
        first thing here and the easiest to forget.
        """
        source_top_y = (self._image_height - 1 - y) if self._image_height > 0 else y
        display_x, display_y = self._display_transform().source_to_display(x, source_top_y)
        return QPointF(
            display_x * self._zoom + self._offset[0],
            display_y * self._zoom + self._offset[1],
        )

    def _widget_to_image(self, point: QPointF) -> QPointF:
        """The inverse: where a click on the widget is in the image.

        Needed by any overlay that can be clicked -- picking a catalogue
        symbol, for one.
        """
        display_x = (point.x() - self._offset[0]) / (self._zoom or 1.0)
        display_y = (point.y() - self._offset[1]) / (self._zoom or 1.0)
        source_x, source_y = self._display_transform().display_to_source(display_x, display_y)
        image_y = (self._image_height - 1 - source_y) if self._image_height > 0 else source_y
        return QPointF(source_x, image_y)
