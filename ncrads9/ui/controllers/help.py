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
SAOImageDS9, an acknowledgment and About (PLAN.md §5.12). NCRADS9 has an
in-app contents dialog, a keyboard-shortcut list, and the two About boxes.
M9-31's documentation work fills in the rest.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox

from ... import __version__
from ..dialogs.help_contents_dialog import HelpContentsDialog
from ..dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from .base import Controller


class HelpController(Controller):
    """Owns the Help menu."""

    def connect(self) -> None:
        """Wire the Help menu."""
        self.menu.action_help_contents.triggered.connect(self.show_contents)
        self.menu.action_keyboard_shortcuts.triggered.connect(self.show_shortcuts)
        self.menu.action_about.triggered.connect(self.show_about)
        self.menu.action_about_qt.triggered.connect(self.show_about_qt)

    def show_contents(self) -> None:
        """Show the in-app help contents."""
        HelpContentsDialog(self.window).exec()

    def show_shortcuts(self) -> None:
        """Show the keyboard shortcut reference."""
        KeyboardShortcutsDialog(self.window).exec()

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
