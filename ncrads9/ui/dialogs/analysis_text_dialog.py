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
The window `$text` output lands in, and DS9's help windows with it.

DS9's `SimpleTextDialog`: eighty columns of fixed-pitch text, modeless, and
appendable -- a task run twice adds to the window rather than replacing it,
which is how a series of runs can be compared. Save and Clear are here for
the same reason.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

#: How big the window opens. DS9's is 80 columns by 20 rows.
WINDOW_SIZE = (720, 460)

#: The filter its Save offers.
TEXT_FILTER = "Text Files (*.txt);;All Files (*)"


class AnalysisTextDialog(QDialog):
    """A modeless text window an analysis task can keep adding to.

    Args:
        title: The window's title, usually the task's label.
        body: The text to start with.
        parent: Optional parent widget.
    """

    def __init__(self, title: str, body: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title or "Analysis")
        self.resize(*WINDOW_SIZE)

        layout = QVBoxLayout(self)
        self._view = QPlainTextEdit()
        self._view.setReadOnly(True)
        # Analysis output is columns of numbers; it only lines up in a fixed
        # pitch, and wrapping a wide table makes it unreadable.
        self._view.setFont(QFont("monospace"))
        self._view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._view)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        save = QPushButton("Save...")
        save.clicked.connect(self.save)
        buttons.addButton(save, QDialogButtonBox.ButtonRole.ActionRole)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear)
        buttons.addButton(clear, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.set_text(body)

    def text(self) -> str:
        """Everything the window is showing."""
        return self._view.toPlainText()

    def set_text(self, body: str) -> None:
        """Replace the contents."""
        self._view.setPlainText(body)

    def append(self, body: str) -> None:
        """Add to the contents, with a rule between runs.

        A task run twice adds rather than replaces, so two runs can be
        compared; a rule is what makes the join visible.
        """
        if not body:
            return
        if self.text():
            self._view.appendPlainText("\n" + "-" * 72)
        self._view.appendPlainText(body)

    def clear(self) -> None:
        """Empty the window."""
        self._view.clear()

    def save(self) -> None:
        """Write the contents to a file."""
        path, _filter = QFileDialog.getSaveFileName(self, "Save Text", "", TEXT_FILTER)
        if not path:
            return
        try:
            Path(path).write_text(self.text())
        except OSError as exc:
            QMessageBox.warning(self, "Save Text", str(exc))
