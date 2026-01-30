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
Region overlay for drawing and displaying regions.

Author: Yogesh Wadadekar
"""

from typing import Optional, List, Tuple
from enum import Enum
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPolygonF
from PyQt6.QtWidgets import QWidget
from dataclasses import dataclass
import math


class RegionMode(Enum):
    """Region drawing modes."""
    NONE = "none"
    CIRCLE = "circle"
    BOX = "box"
    ELLIPSE = "ellipse"
    POLYGON = "polygon"
    POINT = "point"
    LINE = "line"


@dataclass
class Region:
    """Simple region representation."""
    mode: RegionMode
    points: List[QPointF]  # Image coordinates
    color: QColor = QColor(0, 255, 0)  # Green
    selected: bool = False
    
    def contains_point(self, point: QPointF, tolerance: float = 5.0) -> bool:
        """Check if point is inside or near region."""
        if self.mode == RegionMode.CIRCLE:
            if len(self.points) >= 2:
                center = self.points[0]
                radius_point = self.points[1]
                radius = math.sqrt((radius_point.x() - center.x())**2 + 
                                 (radius_point.y() - center.y())**2)
                dist = math.sqrt((point.x() - center.x())**2 + 
                               (point.y() - center.y())**2)
                return abs(dist - radius) < tolerance or dist < radius
        
        elif self.mode == RegionMode.BOX:
            if len(self.points) >= 2:
                rect = QRectF(self.points[0], self.points[1])
                return rect.contains(point)
        
        elif self.mode == RegionMode.ELLIPSE:
            if len(self.points) >= 2:
                center = QPointF((self.points[0].x() + self.points[1].x()) / 2,
                               (self.points[0].y() + self.points[1].y()) / 2)
                rx = abs(self.points[1].x() - self.points[0].x()) / 2
                ry = abs(self.points[1].y() - self.points[0].y()) / 2
                if rx > 0 and ry > 0:
                    dx = (point.x() - center.x()) / rx
                    dy = (point.y() - center.y()) / ry
                    return dx*dx + dy*dy <= 1.0
        
        elif self.mode == RegionMode.POLYGON:
            if len(self.points) >= 3:
                poly = QPolygonF(self.points)
                return poly.containsPoint(point, Qt.FillRule.OddEvenFill)
        
        return False


class RegionOverlay(QWidget):
    """Overlay widget for drawing and displaying regions."""
    
    region_created = pyqtSignal(object)  # Emits Region when complete
    region_selected = pyqtSignal(object)  # Emits Region when selected
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        
        self.mode: RegionMode = RegionMode.NONE
        self.regions: List[Region] = []
        self.current_points: List[QPointF] = []
        self.is_drawing: bool = False
        self.zoom: float = 1.0
        self.image_offset: Tuple[float, float] = (0, 0)
        
        # For moving/editing
        self.selected_region: Optional[Region] = None
        self.drag_start: Optional[QPointF] = None
    
    def set_mode(self, mode: RegionMode) -> None:
        """Set region drawing mode."""
        self.mode = mode
        self.current_points = []
        self.is_drawing = False
        self.update()
    
    def set_zoom(self, zoom: float, offset: Tuple[float, float]) -> None:
        """Update zoom and offset for coordinate transformation."""
        self.zoom = zoom
        self.image_offset = offset
        self.update()
    
    def add_region(self, region: Region) -> None:
        """Add a completed region."""
        self.regions.append(region)
        self.update()
    
    def clear_regions(self) -> None:
        """Clear all regions."""
        self.regions = []
        self.selected_region = None
        self.update()
    
    def _widget_to_image_coords(self, widget_point: QPointF) -> QPointF:
        """Convert widget coordinates to image coordinates."""
        img_x = (widget_point.x() - self.image_offset[0]) / self.zoom
        img_y = (widget_point.y() - self.image_offset[1]) / self.zoom
        return QPointF(img_x, img_y)
    
    def _image_to_widget_coords(self, image_point: QPointF) -> QPointF:
        """Convert image coordinates to widget coordinates."""
        widget_x = image_point.x() * self.zoom + self.image_offset[0]
        widget_y = image_point.y() * self.zoom + self.image_offset[1]
        return QPointF(widget_x, widget_y)
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse press for region drawing."""
        if self.mode == RegionMode.NONE:
            # Selection mode - check if clicking on existing region
            img_point = self._widget_to_image_coords(event.position())
            for region in reversed(self.regions):  # Check from top
                if region.contains_point(img_point):
                    if self.selected_region:
                        self.selected_region.selected = False
                    self.selected_region = region
                    region.selected = True
                    self.drag_start = img_point
                    self.region_selected.emit(region)
                    self.update()
                    event.accept()
                    return
            
            # Clicked on empty space - deselect
            if self.selected_region:
                self.selected_region.selected = False
                self.selected_region = None
                self.update()
            event.accept()
            return
        
        # Drawing mode
        if event.button() == Qt.MouseButton.LeftButton:
            img_point = self._widget_to_image_coords(event.position())
            
            if self.mode == RegionMode.POLYGON:
                # Polygon: accumulate points
                self.current_points.append(img_point)
                self.is_drawing = True
            else:
                # Circle, Box, Ellipse: start new region
                self.current_points = [img_point]
                self.is_drawing = True
            
            self.update()
            event.accept()
    
    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move for region preview or editing."""
        if not self.is_drawing and self.mode == RegionMode.NONE:
            # Moving selected region
            if self.selected_region and self.drag_start:
                img_point = self._widget_to_image_coords(event.position())
                dx = img_point.x() - self.drag_start.x()
                dy = img_point.y() - self.drag_start.y()
                
                # Move all points
                for point in self.selected_region.points:
                    point.setX(point.x() + dx)
                    point.setY(point.y() + dy)
                
                self.drag_start = img_point
                self.update()
            event.accept()
            return
        
        if self.is_drawing and len(self.current_points) > 0:
            # Update preview
            img_point = self._widget_to_image_coords(event.position())
            
            if self.mode in [RegionMode.CIRCLE, RegionMode.BOX, RegionMode.ELLIPSE]:
                # For these, we update the second point
                if len(self.current_points) == 1:
                    self.current_points.append(img_point)
                else:
                    self.current_points[1] = img_point
            
            self.update()
            event.accept()
    
    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release to finalize region."""
        if self.mode == RegionMode.NONE:
            self.drag_start = None
            event.accept()
            return
        
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            if self.mode == RegionMode.POLYGON:
                # Polygon continues until double-click or right-click
                pass
            else:
                # Finalize region for circle, box, ellipse
                if len(self.current_points) >= 2:
                    region = Region(
                        mode=self.mode,
                        points=self.current_points.copy(),
                        color=QColor(0, 255, 0)
                    )
                    self.regions.append(region)
                    self.region_created.emit(region)
                
                self.current_points = []
                self.is_drawing = False
                self.update()
            
            event.accept()
        
        elif event.button() == Qt.MouseButton.RightButton and self.mode == RegionMode.POLYGON:
            # Finalize polygon
            if len(self.current_points) >= 3:
                region = Region(
                    mode=RegionMode.POLYGON,
                    points=self.current_points.copy(),
                    color=QColor(0, 255, 0)
                )
                self.regions.append(region)
                self.region_created.emit(region)
            
            self.current_points = []
            self.is_drawing = False
            self.update()
            event.accept()
    
    def paintEvent(self, event) -> None:
        """Paint regions on overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw completed regions
        for region in self.regions:
            color = QColor(255, 255, 0) if region.selected else region.color
            pen = QPen(color, 2 if region.selected else 1)
            painter.setPen(pen)
            
            widget_points = [self._image_to_widget_coords(p) for p in region.points]
            
            if region.mode == RegionMode.CIRCLE and len(widget_points) >= 2:
                center = widget_points[0]
                radius_point = widget_points[1]
                radius = math.sqrt((radius_point.x() - center.x())**2 + 
                                 (radius_point.y() - center.y())**2)
                painter.drawEllipse(center, radius, radius)
            
            elif region.mode == RegionMode.BOX and len(widget_points) >= 2:
                rect = QRectF(widget_points[0], widget_points[1])
                painter.drawRect(rect)
            
            elif region.mode == RegionMode.ELLIPSE and len(widget_points) >= 2:
                rect = QRectF(widget_points[0], widget_points[1])
                painter.drawEllipse(rect)
            
            elif region.mode == RegionMode.POLYGON and len(widget_points) >= 3:
                poly = QPolygonF(widget_points)
                painter.drawPolygon(poly)
        
        # Draw current drawing preview
        if self.is_drawing and len(self.current_points) > 0:
            pen = QPen(QColor(255, 255, 0), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            
            widget_points = [self._image_to_widget_coords(p) for p in self.current_points]
            
            if self.mode == RegionMode.CIRCLE and len(widget_points) >= 2:
                center = widget_points[0]
                radius_point = widget_points[1]
                radius = math.sqrt((radius_point.x() - center.x())**2 + 
                                 (radius_point.y() - center.y())**2)
                painter.drawEllipse(center, radius, radius)
            
            elif self.mode == RegionMode.BOX and len(widget_points) >= 2:
                rect = QRectF(widget_points[0], widget_points[1])
                painter.drawRect(rect)
            
            elif self.mode == RegionMode.ELLIPSE and len(widget_points) >= 2:
                rect = QRectF(widget_points[0], widget_points[1])
                painter.drawEllipse(rect)
            
            elif self.mode == RegionMode.POLYGON and len(widget_points) >= 2:
                poly = QPolygonF(widget_points)
                painter.drawPolyline(poly)
