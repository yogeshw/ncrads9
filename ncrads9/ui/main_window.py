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
Main window for NCRADS9 application.

Author: Yogesh Wadadekar
"""

from typing import Optional, TYPE_CHECKING
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QDockWidget,
    QFileDialog,
    QLabel,
    QScrollArea,
)
import numpy as np

from .menu_bar import MenuBar
from .toolbar import MainToolbar
from .button_bar import ButtonBar
from .status_bar import StatusBar
from ..core.fits_handler import FITSHandler
from ..core.wcs_handler import WCSHandler
from ..rendering.scale_algorithms import apply_scale, ScaleAlgorithm, compute_zscale_limits
from ..colormaps.builtin_maps import get_colormap

if TYPE_CHECKING:
    from ncrads9.utils.config import Config


class MainWindow(QMainWindow):
    """Main application window for NCRADS9."""

    def __init__(self, config: Optional["Config"] = None, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the main window.

        Args:
            config: Application configuration.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("NCRADS9 - FITS Viewer")
        self.setMinimumSize(800, 600)
        
        # Initialize data storage
        self.current_file = None
        self.fits_handler = None
        self.wcs_handler = None
        self.image_data = None
        self.current_scale = ScaleAlgorithm.LINEAR
        self.current_colormap = "grey"

        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_dock_widgets()
        self._setup_status_bar()

    def _setup_menu_bar(self) -> None:
        """Set up the menu bar."""
        self.menu_bar = MenuBar(self)
        self.setMenuBar(self.menu_bar)
        
        # Connect menu actions to handlers
        self._connect_menu_actions()
    
    def _connect_menu_actions(self) -> None:
        """Connect menu actions to their handlers."""
        # File menu
        self.menu_bar.action_open.triggered.connect(self.open_file)
        self.menu_bar.action_save.triggered.connect(self.save_file)
        self.menu_bar.action_save_as.triggered.connect(self.save_file_as)
        self.menu_bar.action_exit.triggered.connect(self.close)
        
        # Scale menu
        self.menu_bar.action_scale_linear.triggered.connect(lambda: self._set_scale(ScaleAlgorithm.LINEAR))
        self.menu_bar.action_scale_log.triggered.connect(lambda: self._set_scale(ScaleAlgorithm.LOG))
        self.menu_bar.action_scale_sqrt.triggered.connect(lambda: self._set_scale(ScaleAlgorithm.SQRT))
        self.menu_bar.action_scale_asinh.triggered.connect(lambda: self._set_scale(ScaleAlgorithm.ASINH))
        self.menu_bar.action_scale_zscale.triggered.connect(self._display_image)
        
        # Color menu
        self.menu_bar.action_cmap_gray.triggered.connect(lambda: self._set_colormap("grey"))
        self.menu_bar.action_cmap_heat.triggered.connect(lambda: self._set_colormap("heat"))
        self.menu_bar.action_cmap_cool.triggered.connect(lambda: self._set_colormap("cool"))
        self.menu_bar.action_cmap_rainbow.triggered.connect(lambda: self._set_colormap("rainbow"))
        
        # Help menu
        self.menu_bar.action_about.triggered.connect(self.show_about)
        self.menu_bar.action_about_qt.triggered.connect(self.show_about_qt)

    def _setup_toolbar(self) -> None:
        """Set up the main toolbar."""
        self.main_toolbar = MainToolbar(self)
        self.addToolBar(self.main_toolbar)

    def _setup_central_widget(self) -> None:
        """Set up the central widget."""
        # Create scroll area for image display
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create image label
        self.image_label = QLabel()
        self.image_label.setScaledContents(False)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setText("No image loaded")
        
        self.scroll_area.setWidget(self.image_label)
        self.setCentralWidget(self.scroll_area)

    def _setup_dock_widgets(self) -> None:
        """Set up dock widgets."""
        # Left dock for button bar
        self.button_bar_dock = QDockWidget("Controls", self)
        self.button_bar = ButtonBar(self)
        self.button_bar_dock.setWidget(self.button_bar)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.button_bar_dock)

        # Right dock for info panel (placeholder)
        self.info_dock = QDockWidget("Info", self)
        self.info_widget = QWidget(self)
        self.info_dock.setWidget(self.info_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.info_dock)

    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

    def open_file(self, checked: bool = False, filepath: Optional[str] = None) -> None:
        """
        Open a FITS file.

        Args:
            checked: Ignored (from Qt signal).
            filepath: Optional path to the file. If None, shows a file dialog.
        """
        # Handle case where checked is actually a filepath string
        if isinstance(checked, str):
            filepath = checked
            
        if filepath is None or filepath is False:
            filepath, _ = QFileDialog.getOpenFileName(
                self,
                "Open FITS File",
                "",
                "FITS Files (*.fits *.fit *.fts *.fits.gz *.fit.gz);;All Files (*)",
            )

        if filepath:
            try:
                self._load_fits_file(filepath)
                self.statusBar().showMessage(f"Opened: {filepath}")
            except Exception as e:
                self.statusBar().showMessage(f"Error loading file: {e}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error Loading File", 
                                   f"Could not load FITS file:\n{filepath}\n\nError: {e}")
    
    def _load_fits_file(self, filepath: str) -> None:
        """
        Load a FITS file and display it.
        
        Args:
            filepath: Path to the FITS file.
        """
        # Load FITS file
        self.fits_handler = FITSHandler()
        self.fits_handler.load(filepath)
        self.image_data = self.fits_handler.get_data()
        self.current_file = filepath
        
        # Load WCS if available
        header = self.fits_handler.get_header()
        self.wcs_handler = WCSHandler(header)
        
        # Update window title
        filename = Path(filepath).name
        self.setWindowTitle(f"NCRADS9 - {filename}")
        
        # Display the image
        self._display_image()
        
        # Update status
        shape = self.image_data.shape
        dtype = self.image_data.dtype
        stats_msg = f"Image loaded: {shape[1]}x{shape[0]} pixels, {dtype}"
        if self.wcs_handler.is_valid:
            stats_msg += " (WCS available)"
        self.statusBar().showMessage(stats_msg)
    
    def _display_image(self) -> None:
        """Display the current image data."""
        if self.image_data is None:
            return
        
        # Compute scale limits using zscale
        z1, z2 = compute_zscale_limits(self.image_data)
        
        # Clip and scale the data
        clipped = np.clip(self.image_data, z1, z2)
        scaled = apply_scale(clipped, self.current_scale, vmin=z1, vmax=z2)
        
        # Apply colormap
        cmap = get_colormap(self.current_colormap)
        rgb = cmap.apply(scaled)
        
        # Convert to QImage
        height, width = rgb.shape[:2]
        bytes_per_line = 3 * width
        qimage = QImage(rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        
        # Create pixmap and display
        pixmap = QPixmap.fromImage(qimage)
        self.image_label.setPixmap(pixmap)
        self.image_label.resize(pixmap.size())
    
    def _set_scale(self, scale: ScaleAlgorithm) -> None:
        """
        Set the image scaling algorithm.
        
        Args:
            scale: The scaling algorithm to use.
        """
        self.current_scale = scale
        
        # Update menu checkboxes
        self.menu_bar.action_scale_linear.setChecked(scale == ScaleAlgorithm.LINEAR)
        self.menu_bar.action_scale_log.setChecked(scale == ScaleAlgorithm.LOG)
        self.menu_bar.action_scale_sqrt.setChecked(scale == ScaleAlgorithm.SQRT)
        self.menu_bar.action_scale_asinh.setChecked(scale == ScaleAlgorithm.ASINH)
        
        # Redisplay with new scale
        if self.image_data is not None:
            self._display_image()
            self.statusBar().showMessage(f"Scale: {scale.name}")
    
    def _set_colormap(self, colormap: str) -> None:
        """
        Set the colormap.
        
        Args:
            colormap: Name of the colormap to use.
        """
        self.current_colormap = colormap
        
        # Update menu checkboxes
        self.menu_bar.action_cmap_gray.setChecked(colormap == "grey")
        self.menu_bar.action_cmap_heat.setChecked(colormap == "heat")
        self.menu_bar.action_cmap_cool.setChecked(colormap == "cool")
        self.menu_bar.action_cmap_rainbow.setChecked(colormap == "rainbow")
        
        # Redisplay with new colormap
        if self.image_data is not None:
            self._display_image()
            self.statusBar().showMessage(f"Colormap: {colormap}")
    
    def save_file(self) -> None:
        """Save the current file."""
        self.statusBar().showMessage("Save not yet implemented")
    
    def save_file_as(self) -> None:
        """Save the current file with a new name."""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save FITS File",
            "",
            "FITS Files (*.fits *.fit *.fts);;All Files (*)",
        )
        if filepath:
            self.statusBar().showMessage(f"Save as: {filepath}")
    
    def show_about(self) -> None:
        """Show the About dialog."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "About NCRADS9",
            "<h2>NCRADS9</h2>"
            "<p>A Python/Qt6 clone of SAOImageDS9</p>"
            "<p>Version 0.1.0</p>"
            "<p>Copyright © 2026 Yogesh Wadadekar</p>"
            "<p>Licensed under GPL v3</p>"
        )
    
    def show_about_qt(self) -> None:
        """Show the About Qt dialog."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.aboutQt(self, "About Qt")
