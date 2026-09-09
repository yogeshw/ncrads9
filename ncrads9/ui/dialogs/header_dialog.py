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
FITS header viewer dialog.

Author: Yogesh Wadadekar
"""

from typing import Any

from astropy.io import fits
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ...core.header_parser import header_to_lines, summarize_header


class HeaderDialog(QDialog):
    """Dialog for viewing and searching FITS headers."""

    def __init__(
        self,
        header_data: "fits.Header | dict[str, Any] | None" = None,
        parent: QDialog | None = None,
    ) -> None:
        """Initialize the header dialog.

        Args:
            header_data: A FITS header, or any mapping of keyword to value.
                A real `fits.Header` also gets a summary block and keeps its
                card comments.
            parent: Parent widget.
        """
        # Pass None as parent to make dialog independent
        super().__init__(None)

        # Set window flags for independent draggable window
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)

        self.setWindowTitle("FITS Header")
        self.setMinimumSize(700, 500)
        self._header_data = header_data or {}
        self._setup_ui()
        self._populate_header()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Extension selector
        ext_layout = QHBoxLayout()
        ext_layout.addWidget(QLabel("Extension:"))
        self._ext_combo = QComboBox()
        self._ext_combo.addItem("Primary (0)")
        self._ext_combo.currentIndexChanged.connect(self._on_extension_changed)
        ext_layout.addWidget(self._ext_combo)
        ext_layout.addStretch()
        layout.addLayout(ext_layout)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search keyword...")
        self._search_edit.textChanged.connect(self._on_search)
        search_layout.addWidget(self._search_edit)
        layout.addLayout(search_layout)

        # Header text display
        self._header_text = QTextEdit()
        self._header_text.setReadOnly(True)
        self._header_text.setFont(QFont("Monospace", 10))
        layout.addWidget(self._header_text)

        # Button row
        button_layout = QHBoxLayout()

        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        button_layout.addWidget(copy_btn)

        save_btn = QPushButton("Save to File...")
        save_btn.clicked.connect(self._save_to_file)
        button_layout.addWidget(save_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _populate_header(self) -> None:
        """Populate the header text display.

        Rendering is delegated to `core.header_parser`, which reads
        `header.cards` and so keeps comments, COMMENT and HISTORY. This method
        used to iterate the header as a plain mapping, which silently dropped
        every comment -- the `isinstance(value, tuple)` branch it tested for
        never fires, because `fits.Header.items()` yields bare values.
        """
        if not self._header_data:
            self._header_text.setText("")
            return

        summary = summarize_header(self._header_data) if hasattr(self._header_data, "cards") else []
        lines = header_to_lines(self._header_data)
        if summary:
            lines = [*summary, "", "-" * 60, "", *lines]
        self._header_text.setText("\n".join(lines))

    def _on_extension_changed(self, index: int) -> None:
        """Handle extension selection change.

        Args:
            index: Selected extension index.
        """
        # Placeholder for extension switching

    def _on_search(self, text: str) -> None:
        """Handle search text change.

        Args:
            text: Search text.
        """
        if not text:
            self._populate_header()
            return

        # Filter the rendered card lines, so a search matches keyword, value
        # or comment -- the comment was previously unsearchable because it was
        # never rendered.
        text_lower = text.lower()
        matches = [line for line in header_to_lines(self._header_data) if text_lower in line.lower()]
        self._header_text.setText("\n".join(matches))

    def _copy_to_clipboard(self) -> None:
        """Copy header text to clipboard."""
        from PyQt6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self._header_text.toPlainText())

    def _save_to_file(self) -> None:
        """Save header to a text file."""
        from PyQt6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Header",
            "header.txt",
            "Text Files (*.txt);;All Files (*)",
        )
        if file_path:
            with open(file_path, "w") as f:
                f.write(self._header_text.toPlainText())

    def set_header_data(self, header_data: dict[str, Any]) -> None:
        """Set the header data to display.

        Args:
            header_data: FITS header data as dictionary.
        """
        self._header_data = header_data
        self._populate_header()
