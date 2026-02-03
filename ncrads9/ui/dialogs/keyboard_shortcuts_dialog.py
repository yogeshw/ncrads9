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
Keyboard shortcuts help dialog.

Author: Yogesh Wadadekar
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QLabel,
    QWidget,
)
from PyQt6.QtCore import Qt


class KeyboardShortcutsDialog(QDialog):
    """Dialog showing keyboard shortcuts."""

    SHORTCUTS = {
        "File Operations": [
            ("Ctrl+O", "Open FITS file"),
            ("Ctrl+Q", "Quit application"),
        ],
        "Zoom": [
            ("Ctrl++", "Zoom in"),
            ("Ctrl+-", "Zoom out"),
            ("Scroll Wheel", "Zoom in/out"),
        ],
        "View": [
            ("F11", "Toggle fullscreen"),
        ],
        "Mouse Operations": [
            ("Scroll Wheel", "Zoom in/out"),
            ("Right-click + Drag Horizontal", "Adjust contrast"),
            ("Right-click + Drag Vertical", "Adjust brightness"),
            ("Middle-click + Drag", "Pan image"),
        ],
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the keyboard shortcuts dialog.

        Args:
            parent: Optional parent widget.
        """
        # Pass None as parent to make dialog independent
        super().__init__(None)
        
        # Set window flags for independent draggable window
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(500, 400)
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("NCRADS9 Keyboard Shortcuts")
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Shortcuts display
        text = QTextEdit()
        text.setReadOnly(True)
        
        # Build shortcuts text
        shortcuts_text = ""
        for category, shortcuts in self.SHORTCUTS.items():
            shortcuts_text += f"\n<b>{category}</b>\n"
            shortcuts_text += "-" * 50 + "\n"
            for key, description in shortcuts:
                shortcuts_text += f"  <b>{key:25s}</b>  {description}\n"
            shortcuts_text += "\n"
        
        text.setHtml(f"<pre>{shortcuts_text}</pre>")
        layout.addWidget(text)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
