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

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QDockWidget,
    QFileDialog,
)

from .menu_bar import MenuBar
from .toolbar import MainToolbar
from .button_bar import ButtonBar
from .status_bar import StatusBar

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
        
        # Help menu
        self.menu_bar.action_about.triggered.connect(self.show_about)
        self.menu_bar.action_about_qt.triggered.connect(self.show_about_qt)

    def _setup_toolbar(self) -> None:
        """Set up the main toolbar."""
        self.main_toolbar = MainToolbar(self)
        self.addToolBar(self.main_toolbar)

    def _setup_central_widget(self) -> None:
        """Set up the central widget."""
        self.central_widget = QWidget(self)
        self.central_layout = QVBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(self.central_widget)

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
            # TODO: Implement file loading logic
            self.statusBar().showMessage(f"Opened: {filepath}")
    
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
