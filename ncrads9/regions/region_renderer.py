# NCRADS9 - NCRA DS9 Viewer
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
Region renderer for Qt-based drawing.

Author: Yogesh Wadadekar
"""

from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen

from .base_region import BaseRegion
from .region_manager import RegionManager


class RegionRenderer:
    """Renderer for drawing regions using Qt."""

    # Color name to QColor mapping
    COLOR_MAP: dict[str, QColor] = {
        "green": QColor(0, 255, 0),
        "red": QColor(255, 0, 0),
        "blue": QColor(0, 0, 255),
        "cyan": QColor(0, 255, 255),
        "magenta": QColor(255, 0, 255),
        "yellow": QColor(255, 255, 0),
        "white": QColor(255, 255, 255),
        "black": QColor(0, 0, 0),
        "orange": QColor(255, 165, 0),
        "pink": QColor(255, 192, 203),
    }

    # Selection highlight color
    SELECTION_COLOR = QColor(255, 255, 0, 128)

    def __init__(
        self,
        region_manager: Optional[RegionManager] = None,
        scale: float = 1.0,
        offset: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        """
        Initialize the region renderer.

        Args:
            region_manager: Optional region manager to use.
            scale: The zoom scale factor.
            offset: The (x, y) offset for panning.
        """
        self._region_manager = region_manager
        self._scale = scale
        self._offset = offset
        self._show_labels = True
        self._antialiasing = True

    @property
    def scale(self) -> float:
        """Get the zoom scale."""
        return self._scale

    @scale.setter
    def scale(self, value: float) -> None:
        """Set the zoom scale."""
        self._scale = max(0.01, value)

    @property
    def offset(self) -> tuple[float, float]:
        """Get the pan offset."""
        return self._offset

    @offset.setter
    def offset(self, value: tuple[float, float]) -> None:
        """Set the pan offset."""
        self._offset = value

    @property
    def show_labels(self) -> bool:
        """Get whether labels are shown."""
        return self._show_labels

    @show_labels.setter
    def show_labels(self, value: bool) -> None:
        """Set whether labels are shown."""
        self._show_labels = value

    @property
    def antialiasing(self) -> bool:
        """Get whether antialiasing is enabled."""
        return self._antialiasing

    @antialiasing.setter
    def antialiasing(self, value: bool) -> None:
        """Set whether antialiasing is enabled."""
        self._antialiasing = value

    def set_region_manager(self, manager: RegionManager) -> None:
        """
        Set the region manager.

        Args:
            manager: The region manager to use.
        """
        self._region_manager = manager

    def render(self, painter: QPainter) -> None:
        """
        Render all regions.

        Args:
            painter: The QPainter to draw with.
        """
        if self._region_manager is None:
            return

        # Enable antialiasing if requested
        if self._antialiasing:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw all regions
        for i, region in enumerate(self._region_manager):
            is_selected = self._region_manager.is_selected(i)
            self.render_region(painter, region, is_selected)

    def render_region(
        self,
        painter: QPainter,
        region: BaseRegion,
        selected: bool = False,
    ) -> None:
        """
        Render a single region.

        Args:
            painter: The QPainter to draw with.
            region: The region to render.
            selected: Whether the region is selected.
        """
        # Set up the pen
        pen = self._create_pen(region, selected)
        painter.setPen(pen)

        # Transform coordinates
        center = self._transform_point(region.center)

        # Draw the region (delegates to region's draw method)
        region.draw(painter)

        # Draw selection handles if selected
        if selected:
            self._draw_selection_handles(painter, region)

        # Draw label if enabled
        if self._show_labels and region.text:
            self._draw_label(painter, region, center)

    def render_regions(
        self,
        painter: QPainter,
        regions: list[BaseRegion],
        selected_indices: Optional[set[int]] = None,
    ) -> None:
        """
        Render a list of regions.

        Args:
            painter: The QPainter to draw with.
            regions: The list of regions to render.
            selected_indices: Optional set of selected region indices.
        """
        if self._antialiasing:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        selected_indices = selected_indices or set()

        for i, region in enumerate(regions):
            is_selected = i in selected_indices
            self.render_region(painter, region, is_selected)

    def _create_pen(self, region: BaseRegion, selected: bool) -> QPen:
        """
        Create a pen for drawing a region.

        Args:
            region: The region to create a pen for.
            selected: Whether the region is selected.

        Returns:
            A QPen configured for the region.
        """
        color = self._get_color(region.color)
        if selected:
            # Make selected regions slightly brighter
            color = color.lighter(120)

        pen = QPen(color)
        pen.setWidth(region.width)
        pen.setStyle(Qt.PenStyle.SolidLine)

        return pen

    def _get_color(self, color_name: str) -> QColor:
        """
        Get a QColor from a color name.

        Args:
            color_name: The color name.

        Returns:
            The corresponding QColor.
        """
        color_name = color_name.lower()
        if color_name in self.COLOR_MAP:
            return self.COLOR_MAP[color_name]

        # Try to parse as hex color
        if color_name.startswith("#"):
            return QColor(color_name)

        # Default to green
        return self.COLOR_MAP["green"]

    def _transform_point(
        self, point: tuple[float, float]
    ) -> tuple[float, float]:
        """
        Transform a point from image to screen coordinates.

        Args:
            point: The (x, y) point in image coordinates.

        Returns:
            The (x, y) point in screen coordinates.
        """
        x = (point[0] + self._offset[0]) * self._scale
        y = (point[1] + self._offset[1]) * self._scale
        return (x, y)

    def _inverse_transform_point(
        self, point: tuple[float, float]
    ) -> tuple[float, float]:
        """
        Transform a point from screen to image coordinates.

        Args:
            point: The (x, y) point in screen coordinates.

        Returns:
            The (x, y) point in image coordinates.
        """
        x = point[0] / self._scale - self._offset[0]
        y = point[1] / self._scale - self._offset[1]
        return (x, y)

    def _draw_selection_handles(
        self, painter: QPainter, region: BaseRegion
    ) -> None:
        """
        Draw selection handles around a region.

        Args:
            painter: The QPainter to draw with.
            region: The region to draw handles for.
        """
        # Draw a small square at the center
        center = self._transform_point(region.center)
        handle_size = 6

        pen = QPen(self.SELECTION_COLOR)
        pen.setWidth(2)
        painter.setPen(pen)

        rect = QRectF(
            center[0] - handle_size / 2,
            center[1] - handle_size / 2,
            handle_size,
            handle_size,
        )
        painter.drawRect(rect)

    def _draw_label(
        self,
        painter: QPainter,
        region: BaseRegion,
        center: tuple[float, float],
    ) -> None:
        """
        Draw a text label for a region.

        Args:
            painter: The QPainter to draw with.
            region: The region to label.
            center: The center point in screen coordinates.
        """
        font = self._parse_font(region.font)
        painter.setFont(font)

        color = self._get_color(region.color)
        painter.setPen(color)

        # Draw text slightly above the center
        point = QPointF(center[0], center[1] - 10)
        painter.drawText(point, region.text)

    def _parse_font(self, font_spec: str) -> QFont:
        """
        Parse a DS9 font specification.

        Args:
            font_spec: The font specification string.

        Returns:
            A QFont object.
        """
        parts = font_spec.split()
        font = QFont()

        if len(parts) >= 1:
            font.setFamily(parts[0])
        if len(parts) >= 2:
            try:
                font.setPointSize(int(parts[1]))
            except ValueError:
                pass
        if len(parts) >= 3:
            if parts[2] == "bold":
                font.setBold(True)
            elif parts[2] == "italic":
                font.setItalic(True)

        return font

    def screen_to_image(
        self, screen_x: float, screen_y: float
    ) -> tuple[float, float]:
        """
        Convert screen coordinates to image coordinates.

        Args:
            screen_x: The x coordinate in screen space.
            screen_y: The y coordinate in screen space.

        Returns:
            The (x, y) coordinates in image space.
        """
        return self._inverse_transform_point((screen_x, screen_y))

    def image_to_screen(
        self, image_x: float, image_y: float
    ) -> tuple[float, float]:
        """
        Convert image coordinates to screen coordinates.

        Args:
            image_x: The x coordinate in image space.
            image_y: The y coordinate in image space.

        Returns:
            The (x, y) coordinates in screen space.
        """
        return self._transform_point((image_x, image_y))
