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
DS9's Notes: somewhere to write down what you are looking at.

An editable text window with DS9's File and Edit menus over it
(`notes.tcl`, and `EditTextDialog` which draws it). What makes it worth
having rather than a text editor beside the application is that the notes
go into the backup with everything else, so a session comes back with the
reasoning that went with it.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

#: How big the window opens, in characters as DS9 sizes it: 80 by 20.
WINDOW_SIZE = (680, 420)

#: The file filter for Open and Save.
FILE_FILTER = "Text files (*.txt *.notes);;All files (*)"


class NotesDialog(QDialog):
    """The notes window."""

    def __init__(self, controller, parent=None) -> None:
        """
        Args:
            controller: The `NotesController` holding the text.
            parent: The main window.
        """
        super().__init__(parent)
        self._controller = controller
        self._last_search = ""
        self.setWindowTitle("Notes")
        self.resize(*WINDOW_SIZE)

        layout = QVBoxLayout(self)
        layout.setMenuBar(self._menus())
        self.text = QPlainTextEdit()
        self.text.setPlainText(controller.text)
        self.text.textChanged.connect(self._on_changed)
        layout.addWidget(self.text)

    def _menus(self) -> QMenuBar:
        """DS9's File and Edit menus for an editable text window."""
        bar = QMenuBar(self)
        #: Action name -> the action, so a test can trigger one.
        self.actions_by_name: dict[str, QAction] = {}

        file_menu = bar.addMenu("&File")
        self._add(file_menu, "open", "&Open...", self.open_file, "Ctrl+O")
        self._add(file_menu, "save", "&Save...", self.save_file, "Ctrl+S")
        file_menu.addSeparator()
        self._add(file_menu, "close", "&Close", self.close, "Ctrl+W")

        edit_menu = bar.addMenu("&Edit")
        self._add(edit_menu, "cut", "Cu&t", lambda: self.text.cut(), "Ctrl+X")
        self._add(edit_menu, "copy", "&Copy", lambda: self.text.copy(), "Ctrl+C")
        self._add(edit_menu, "paste", "&Paste", lambda: self.text.paste(), "Ctrl+V")
        self._add(edit_menu, "clear", "C&lear", self.clear)
        edit_menu.addSeparator()
        self._add(edit_menu, "select_all", "Select &All", lambda: self.text.selectAll())
        self._add(edit_menu, "select_none", "Select &None", self.select_none)
        edit_menu.addSeparator()
        self._add(edit_menu, "find", "&Find...", self.find, "Ctrl+F")
        self._add(edit_menu, "find_next", "Find Ne&xt", self.find_next, "Ctrl+G")
        return bar

    def _add(self, menu, name: str, label: str, slot, shortcut: str | None = None) -> QAction:
        """One menu entry, remembered by name."""
        action = QAction(label, self)
        action.triggered.connect(lambda _checked=False: slot())
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        menu.addAction(action)
        self.actions_by_name[name] = action
        return action

    # -- the text ---------------------------------------------------------------

    def _on_changed(self) -> None:
        """Keep the controller's copy up to date as it is typed.

        The controller's copy is what the backup writes, so letting it lag
        behind the window would lose whatever was typed last.
        """
        self._controller.text = self.text.toPlainText()

    def reload(self) -> None:
        """Show what the controller holds, after a restore replaced it."""
        if self.text.toPlainText() != self._controller.text:
            self.text.setPlainText(self._controller.text)

    def clear(self) -> None:
        """Throw the notes away, DS9's Edit -> Clear."""
        self.text.clear()

    def select_none(self) -> None:
        """Select nothing."""
        cursor = self.text.textCursor()
        cursor.clearSelection()
        self.text.setTextCursor(cursor)

    # -- files ------------------------------------------------------------------

    def open_file(self, path: str | None = None) -> bool:
        """Read notes from a file, replacing what is there."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Open Notes", "", FILE_FILTER)
        if not path:
            return False
        try:
            self.text.setPlainText(Path(path).read_text(encoding="utf-8"))
        except OSError as exc:
            QMessageBox.warning(self, "Notes", f"Could not read {Path(path).name}:\n{exc}")
            return False
        return True

    def save_file(self, path: str | None = None) -> bool:
        """Write the notes to a file."""
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Save Notes", "", FILE_FILTER)
        if not path:
            return False
        try:
            Path(path).write_text(self.text.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Notes", f"Could not write {Path(path).name}:\n{exc}")
            return False
        return True

    # -- searching ---------------------------------------------------------------

    def find(self, text: str | None = None) -> bool:
        """Search the notes."""
        if text is None:
            text, ok = QInputDialog.getText(self, "Find", "Find:", text=self._last_search)
            if not ok or not text:
                return False
        self._last_search = text
        cursor = self.text.textCursor()
        cursor.setPosition(0)
        self.text.setTextCursor(cursor)
        return self.text.find(text)

    def find_next(self) -> bool:
        """Find the next occurrence of the last search."""
        if not self._last_search:
            return self.find()
        return self.text.find(self._last_search)
