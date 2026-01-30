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
Open file dialog with preview functionality.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QGroupBox,
    QTextEdit,
)


class OpenDialog(QDialog):
    """Dialog for opening FITS files with preview."""

    file_selected = pyqtSignal(str)

    def __init__(self, parent: Optional[QDialog] = None) -> None:
        """Initialize the open dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Open FITS File")
        self.setMinimumSize(800, 600)
        self._selected_file: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # File browser section
        browser_group = QGroupBox("Files")
        browser_layout = QVBoxLayout(browser_group)

        self._file_list = QListWidget()
        self._file_list.itemClicked.connect(self._on_file_clicked)
        self._file_list.itemDoubleClicked.connect(self._on_file_double_clicked)
        browser_layout.addWidget(self._file_list)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_files)
        browser_layout.addWidget(browse_btn)

        splitter.addWidget(browser_group)

        # Preview section
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self._preview_label = QLabel("No file selected")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumSize(300, 300)
        preview_layout.addWidget(self._preview_label)

        self._info_text = QTextEdit()
        self._info_text.setReadOnly(True)
        self._info_text.setMaximumHeight(150)
        preview_layout.addWidget(self._info_text)

        splitter.addWidget(preview_group)

        layout.addWidget(splitter)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self._accept)
        button_layout.addWidget(open_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _browse_files(self) -> None:
        """Open file browser dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FITS File",
            "",
            "FITS Files (*.fits *.fit *.fts *.fits.gz *.fit.gz);;All Files (*)",
        )
        if file_path:
            self._add_file_to_list(file_path)

    def _add_file_to_list(self, file_path: str) -> None:
        """Add a file to the list widget.

        Args:
            file_path: Path to the file.
        """
        item = QListWidgetItem(Path(file_path).name)
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        self._file_list.addItem(item)
        self._file_list.setCurrentItem(item)
        self._on_file_clicked(item)

    def _on_file_clicked(self, item: QListWidgetItem) -> None:
        """Handle file selection.

        Args:
            item: Selected list item.
        """
        file_path = item.data(Qt.ItemDataRole.UserRole)
        self._selected_file = file_path
        self._update_preview(file_path)

    def _on_file_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle file double-click.

        Args:
            item: Double-clicked list item.
        """
        self._on_file_clicked(item)
        self._accept()

    def _update_preview(self, file_path: str) -> None:
        """Update the preview for the selected file.

        Args:
            file_path: Path to the file.
        """
        self._preview_label.setText(f"Preview: {Path(file_path).name}")
        self._info_text.setText(f"File: {file_path}\n\nHeader info will be displayed here.")

    def _accept(self) -> None:
        """Accept the dialog and emit the selected file."""
        if self._selected_file:
            self.file_selected.emit(self._selected_file)
            self.accept()

    def get_selected_file(self) -> Optional[str]:
        """Get the selected file path.

        Returns:
            Selected file path or None.
        """
        return self._selected_file
