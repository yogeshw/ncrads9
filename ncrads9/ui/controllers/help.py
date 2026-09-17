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
The Help menu.

DS9 offers eight entries, all pointing at its bundled documentation: the
Reference Manual, User Manual, FAQ, Release Notes, Help Desk, the story of
SAOImageDS9, an acknowledgment and About (PLAN.md section 5.12). NCRADS9
answers all eight with its own material -- see
`ncrads9/ui/help_documents.py` -- and keeps its own contents page, shortcut
list and About boxes alongside them.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QMessageBox

from ... import __version__
from ..dialogs.help_contents_dialog import HelpContentsDialog
from ..dialogs.help_document_dialog import HelpDocumentDialog
from ..dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from ..help_documents import BY_NAME
from .base import Controller

if TYPE_CHECKING:
    from ..main_window import MainWindow


class HelpController(Controller):
    """Owns the Help menu."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        #: Document name -> its open window, so a second Open raises the
        #: first rather than stacking another copy on top of it.
        self._open: dict[str, HelpDocumentDialog] = {}

    def connect(self) -> None:
        """Wire the Help menu."""
        for name, action in self.menu.help_document_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.show_document(key))
        self.menu.action_help_contents.triggered.connect(self.show_contents)
        self.menu.action_keyboard_shortcuts.triggered.connect(self.show_shortcuts)
        self.menu.action_about.triggered.connect(self.show_about)
        self.menu.action_about_qt.triggered.connect(self.show_about_qt)

    def show_document(self, name: str) -> None:
        """Open one of DS9's eight Help entries.

        One window per document, raised rather than duplicated: a reference
        page opened twice from a menu is a second window to close.

        Args:
            name: A key of `help_documents.BY_NAME`.
        """
        document = BY_NAME.get(name)
        if document is None:
            self.status(f"Unknown help document: {name}", 3000)
            return
        existing = self._open.get(name)
        if existing is not None:
            existing.refresh()
            existing.raise_()
            existing.activateWindow()
            return
        window = HelpDocumentDialog(document, self.window)
        window.finished.connect(lambda _result, key=name: self._open.pop(key, None))
        self._open[name] = window
        self.show_window(window)

    def show_contents(self) -> None:
        """Show the in-app help contents."""
        self.show_window(HelpContentsDialog(self.window))

    def show_shortcuts(self) -> None:
        """Show the keyboard shortcut reference."""
        self.show_window(KeyboardShortcutsDialog(self.window))

    def show_about(self) -> None:
        """Show the About box.

        The version comes from the package rather than a literal, so it cannot
        fall behind `pyproject.toml`.
        """
        QMessageBox.about(
            self.window,
            "About NCRADS9",
            "<h2>NCRADS9</h2>"
            "<p>A Python/Qt6 clone of SAOImageDS9</p>"
            f"<p>Version {__version__}</p>"
            "<p>Copyright &copy; 2026 Yogesh Wadadekar</p>"
            "<p>Licensed under GPL v3</p>",
        )

    def show_about_qt(self) -> None:
        """Show Qt's own About box."""
        QMessageBox.aboutQt(self.window, "About Qt")
