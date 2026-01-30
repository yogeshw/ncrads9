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
Main toolbar for NCRADS9 application.

Author: Yogesh Wadadekar
"""

from typing import Optional

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QToolBar, QWidget


class MainToolbar(QToolBar):
    """Main toolbar with common actions."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the main toolbar.

        Args:
            parent: Optional parent widget.
        """
        super().__init__("Main Toolbar", parent)
        self.setObjectName("MainToolbar")

        self._setup_actions()

    def _setup_actions(self) -> None:
        """Set up toolbar actions."""
        # File actions
        self.action_open: QAction = QAction(QIcon.fromTheme("document-open"), "Open", self)
        self.action_open.setToolTip("Open FITS file")
        self.addAction(self.action_open)

        self.action_save: QAction = QAction(QIcon.fromTheme("document-save"), "Save", self)
        self.action_save.setToolTip("Save current view")
        self.addAction(self.action_save)

        self.addSeparator()

        # Zoom actions
        self.action_zoom_in: QAction = QAction(QIcon.fromTheme("zoom-in"), "Zoom In", self)
        self.action_zoom_in.setToolTip("Zoom in")
        self.addAction(self.action_zoom_in)

        self.action_zoom_out: QAction = QAction(QIcon.fromTheme("zoom-out"), "Zoom Out", self)
        self.action_zoom_out.setToolTip("Zoom out")
        self.addAction(self.action_zoom_out)

        self.action_zoom_fit: QAction = QAction(
            QIcon.fromTheme("zoom-fit-best"), "Zoom Fit", self
        )
        self.action_zoom_fit.setToolTip("Zoom to fit window")
        self.addAction(self.action_zoom_fit)

        self.action_zoom_1: QAction = QAction(
            QIcon.fromTheme("zoom-original"), "Zoom 1:1", self
        )
        self.action_zoom_1.setToolTip("Zoom to 1:1")
        self.addAction(self.action_zoom_1)

        self.addSeparator()

        # Frame actions
        self.action_prev_frame: QAction = QAction(
            QIcon.fromTheme("go-previous"), "Previous", self
        )
        self.action_prev_frame.setToolTip("Previous frame")
        self.addAction(self.action_prev_frame)

        self.action_next_frame: QAction = QAction(QIcon.fromTheme("go-next"), "Next", self)
        self.action_next_frame.setToolTip("Next frame")
        self.addAction(self.action_next_frame)

        self.addSeparator()

        # Region actions
        self.action_region_circle: QAction = QAction("Circle", self)
        self.action_region_circle.setToolTip("Draw circle region")
        self.action_region_circle.setCheckable(True)
        self.addAction(self.action_region_circle)

        self.action_region_box: QAction = QAction("Box", self)
        self.action_region_box.setToolTip("Draw box region")
        self.action_region_box.setCheckable(True)
        self.addAction(self.action_region_box)

        self.action_region_polygon: QAction = QAction("Polygon", self)
        self.action_region_polygon.setToolTip("Draw polygon region")
        self.action_region_polygon.setCheckable(True)
        self.addAction(self.action_region_polygon)

        self.addSeparator()

        # Analysis actions
        self.action_statistics: QAction = QAction("Stats", self)
        self.action_statistics.setToolTip("Show statistics")
        self.addAction(self.action_statistics)

        self.action_histogram: QAction = QAction("Histogram", self)
        self.action_histogram.setToolTip("Show histogram")
        self.addAction(self.action_histogram)
