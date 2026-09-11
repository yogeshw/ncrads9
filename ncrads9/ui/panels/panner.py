# This file is part of ncrads9.
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
Panner panel showing overview with pan rectangle.

Author: Yogesh Wadadekar
"""


import math

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

#: DS9's `ipanner(size)` -- the panner is a fixed 128x128 square.
PANNER_SIZE = 128
#: How long the compass arrows are drawn, in panner pixels.
COMPASS_LENGTH = 22
#: Where the compass sits, inset from the panner's bottom-left corner.
COMPASS_INSET = 6
#: How far past the arrow head its N/E letter is drawn.
COMPASS_LABEL_GAP = 6
#: How long each barb of an arrow head is, and how far it spreads.
COMPASS_HEAD = 5.0
COMPASS_SPREAD = 3.0


class PannerLabel(QLabel):
    """Label widget that handles mouse clicks for panning."""

    pan_requested = pyqtSignal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the panner label."""
        super().__init__(parent)
        self._image_size: tuple[int, int] = (1, 1)
        self._scale_factor: float = 1.0

    def set_image_size(self, width: int, height: int) -> None:
        """Set the original image size for coordinate conversion."""
        self._image_size = (width, height)

    def set_scale_factor(self, factor: float) -> None:
        """Set the scale factor for coordinate conversion."""
        self._scale_factor = factor

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Handle mouse press for panning."""
        if event is None:
            return
        if event.button() != Qt.MouseButton.LeftButton or self._scale_factor <= 0:
            return

        pixmap = self.pixmap()
        if pixmap is None:
            return

        x_offset = max(0.0, (self.width() - pixmap.width()) / 2.0)
        y_offset = max(0.0, (self.height() - pixmap.height()) / 2.0)
        local_x = event.position().x() - x_offset
        local_y = event.position().y() - y_offset
        if local_x < 0 or local_y < 0 or local_x >= pixmap.width() or local_y >= pixmap.height():
            return

        max_x = max(0.0, self._image_size[0] - 1)
        max_y = max(0.0, self._image_size[1] - 1)
        x = min(max(local_x / self._scale_factor, 0.0), max_x)
        y = min(max(local_y / self._scale_factor, 0.0), max_y)
        self.pan_requested.emit(x, y)


class PannerPanel(QWidget):
    """Panel showing an image overview with the current view rectangle.

    A plain widget, not a dock: DS9 packs the panner into the fixed header row
    (`LayoutViewHorz` in `ds9/library/layout.tcl`), and the shell does the
    same. It used to be a `QDockWidget` placed *inside* another dock, which
    gave it two title bars and let the user tear it out of the window.
    """

    pan_to = pyqtSignal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Initialize the panner panel.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setObjectName("PannerPanel")

        self._current_image: NDArray[np.float64] | None = None
        self._view_rect: QRectF | None = None
        self._thumbnail_size: int = PANNER_SIZE
        self._source_image_size: tuple[int, int] | None = None
        self._north: tuple[float, float] | None = None
        self._east: tuple[float, float] | None = None
        self._show_compass: bool = True

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._panner_label = PannerLabel()
        self._panner_label.setFixedSize(self._thumbnail_size, self._thumbnail_size)
        self._panner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._panner_label.setStyleSheet("background-color: black;")
        self._panner_label.pan_requested.connect(self._on_pan_requested)
        layout.addWidget(self._panner_label)

    def _on_pan_requested(self, x: float, y: float) -> None:
        """Handle pan request from label click."""
        self.pan_to.emit(x, y)

    def set_image(
        self,
        image: NDArray[np.float64],
        source_size: tuple[int, int] | None = None,
    ) -> None:
        """
        Set the image data for the overview.

        Args:
            image: 2D numpy array of image data.
            source_size: Optional (width, height) of the full-resolution source.
        """
        self._current_image = image
        if source_size is None:
            h, w = image.shape[:2]
            self._source_image_size = (w, h)
        else:
            self._source_image_size = source_size
        self._update_thumbnail()

    def set_compass(
        self,
        north: tuple[float, float] | None,
        east: tuple[float, float] | None,
        visible: bool = True,
    ) -> None:
        """Set the WCS compass drawn over the thumbnail.

        DS9 draws this compass in the panner, not on the image -- the panner
        widget in `tksao` carries both a WCS compass and an image-orientation
        one. NCRADS9 drew the N/E arrows over the image itself, where they sat
        on top of the data; this is where a DS9 user looks for them.

        Args:
            north: Screen-space (dx, dy) along increasing declination, or None
                when the frame has no usable WCS.
            east: Screen-space (dx, dy) along increasing right ascension.
            visible: Whether to draw the compass at all.
        """
        self._north = north
        self._east = east
        self._show_compass = visible
        self._update_thumbnail()

    def compass_arrows(self, size: tuple[int, int]) -> dict[str, tuple[QPointF, QPointF]]:
        """The compass as the painter draws it: label -> (origin, tip).

        Screen space, y running *down*. Separate from `_draw_compass` so a
        test can assert on the geometry rather than on pixels -- which is
        how the bug this had got through: the vectors were right and only
        the drawing was mirrored.
        """
        if not self._show_compass or self._north is None or self._east is None:
            return {}

        width, height = size
        origin = QPointF(COMPASS_INSET + COMPASS_LENGTH, height - COMPASS_INSET - COMPASS_LENGTH)
        if origin.x() > width or origin.y() < 0:
            return {}

        arrows: dict[str, tuple[QPointF, QPointF]] = {}
        for vector, label in ((self._north, "N"), (self._east, "E")):
            dx, dy = vector
            # The vectors arrive y-*up*, as `source_vector_to_display`
            # returns them, and a painter's y runs *down*. Without this
            # negation north was drawn pointing south: the compass was
            # mirrored, and on a normally-oriented image it read N-down,
            # E-left. The image overlay in `contour_overlay.py` has always
            # done this conversion; the panner did not.
            dy = -dy
            norm = math.hypot(dx, dy)
            if norm <= 0:
                continue
            ux, uy = dx / norm, dy / norm
            arrows[label] = (
                origin,
                QPointF(origin.x() + ux * COMPASS_LENGTH, origin.y() + uy * COMPASS_LENGTH),
            )
        return arrows

    def _draw_compass(self, painter: QPainter, size: tuple[int, int]) -> None:
        """Draw the N and E arrows in the panner's bottom-left corner."""
        arrows = self.compass_arrows(size)
        if not arrows:
            return

        painter.setPen(QPen(QColor(0, 255, 0), 1))
        for label, (origin, tip) in arrows.items():
            norm = math.hypot(tip.x() - origin.x(), tip.y() - origin.y())
            if norm <= 0:
                continue
            ux, uy = (tip.x() - origin.x()) / norm, (tip.y() - origin.y()) / norm
            painter.drawLine(origin, tip)

            # An arrow head, so the pair reads as arrows rather than as a
            # corner. Perpendicular to the shaft, barbs swept back.
            px, py = -uy, ux
            for side in (1.0, -1.0):
                painter.drawLine(
                    tip,
                    QPointF(
                        tip.x() - ux * COMPASS_HEAD + px * COMPASS_SPREAD * side,
                        tip.y() - uy * COMPASS_HEAD + py * COMPASS_SPREAD * side,
                    ),
                )

            # Nudge the letter clear of the arrow head.
            painter.drawText(
                QPointF(
                    tip.x() + ux * COMPASS_LABEL_GAP - COMPASS_LABEL_GAP / 2,
                    tip.y() + uy * COMPASS_LABEL_GAP + COMPASS_LABEL_GAP / 2,
                ),
                label,
            )

    def set_view_rect(self, rect: QRectF | None) -> None:
        """
        Set the current view rectangle.

        Args:
            rect: Rectangle representing the current view in image coordinates.
        """
        self._view_rect = rect
        self._update_thumbnail()

    def _update_thumbnail(self) -> None:
        """Update the thumbnail with view rectangle overlay."""
        if self._current_image is None:
            return

        preview_h, preview_w = self._current_image.shape[:2]
        if self._source_image_size is None:
            source_w, source_h = preview_w, preview_h
        else:
            source_w, source_h = self._source_image_size
        is_rgb = len(self._current_image.shape) == 3 and self._current_image.shape[2] == 3
        if is_rgb:
            if self._current_image.dtype == np.uint8:
                normalized = self._current_image
            else:
                vmin, vmax = np.nanmin(self._current_image), np.nanmax(self._current_image)
                if vmax > vmin:
                    normalized = ((self._current_image - vmin) / (vmax - vmin) * 255).astype(np.uint8)
                else:
                    normalized = np.zeros((preview_h, preview_w, 3), dtype=np.uint8)
            if not normalized.flags["C_CONTIGUOUS"]:
                normalized = np.ascontiguousarray(normalized)
            qimage = QImage(
                normalized.data,
                preview_w,
                preview_h,
                3 * preview_w,
                QImage.Format.Format_RGB888,
            )
        else:
            vmin, vmax = np.nanmin(self._current_image), np.nanmax(self._current_image)
            if vmax > vmin:
                normalized = ((self._current_image - vmin) / (vmax - vmin) * 255).astype(np.uint8)
            else:
                normalized = np.zeros((preview_h, preview_w), dtype=np.uint8)
            if not normalized.flags["C_CONTIGUOUS"]:
                normalized = np.ascontiguousarray(normalized)
            qimage = QImage(
                normalized.data,
                preview_w,
                preview_h,
                normalized.strides[0],
                QImage.Format.Format_Grayscale8,
            )

        # Scale to thumbnail size
        scale = min(self._thumbnail_size / source_w, self._thumbnail_size / source_h)
        new_w = int(source_w * scale)
        new_h = int(source_h * scale)

        pixmap = QPixmap.fromImage(qimage).scaled(
            new_w,
            new_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self._panner_label.set_image_size(source_w, source_h)
        self._panner_label.set_scale_factor(scale)

        # Draw view rectangle
        if self._view_rect is not None and self._view_rect.width() > 0 and self._view_rect.height() > 0:
            view_cover_x = self._view_rect.width() / max(source_w, 1)
            view_cover_y = self._view_rect.height() / max(source_h, 1)
            if view_cover_x >= 0.98 and view_cover_y >= 0.98:
                self._paint_overlay(pixmap)
                return

            if is_rgb:
                gray = (
                    normalized[..., 0].astype(np.float32) * 0.2126
                    + normalized[..., 1].astype(np.float32) * 0.7152
                    + normalized[..., 2].astype(np.float32) * 0.0722
                )
            else:
                gray = normalized.astype(np.float32)

            x_scale = preview_w / max(source_w, 1)
            y_scale = preview_h / max(source_h, 1)
            x0 = max(0, min(preview_w - 1, int(self._view_rect.x() * x_scale)))
            y0 = max(0, min(preview_h - 1, int(self._view_rect.y() * y_scale)))
            x1 = max(
                x0 + 1,
                min(preview_w, int((self._view_rect.x() + self._view_rect.width()) * x_scale)),
            )
            y1 = max(
                y0 + 1,
                min(preview_h, int((self._view_rect.y() + self._view_rect.height()) * y_scale)),
            )
            local_mean = float(np.nanmean(gray[y0:y1, x0:x1]))
            rect_color = QColor(255, 255, 255) if local_mean < 128.0 else QColor(0, 0, 0)

            painter = QPainter(pixmap)
            painter.setPen(QPen(rect_color, 2))
            scaled_rect = QRectF(
                self._view_rect.x() * scale,
                self._view_rect.y() * scale,
                self._view_rect.width() * scale,
                self._view_rect.height() * scale,
            )
            painter.drawRect(scaled_rect)
            self._draw_compass(painter, (pixmap.width(), pixmap.height()))
            painter.end()
            self._panner_label.setPixmap(pixmap)
            return

        self._paint_overlay(pixmap)

    def _paint_overlay(self, pixmap: QPixmap) -> None:
        """Draw the compass onto a thumbnail that has no view rectangle."""
        if self._show_compass and self._north is not None and self._east is not None:
            painter = QPainter(pixmap)
            self._draw_compass(painter, (pixmap.width(), pixmap.height()))
            painter.end()
        self._panner_label.setPixmap(pixmap)
