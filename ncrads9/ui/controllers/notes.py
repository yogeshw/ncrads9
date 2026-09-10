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
File -> Notes, and the `notes` XPA point.

The text lives here rather than in the window, so it survives the window
being closed and goes into the backup with everything else -- which is the
whole reason DS9 has notes of its own rather than leaving you to a text
editor (`notes.tcl`).

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

from .base import Controller


class NotesController(Controller):
    """Holds the session's notes."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: What has been written down.
        self.text = ""
        self._dialog = None

    def connect(self) -> None:
        """Wire File -> Notes."""
        self.menu.action_notes.triggered.connect(lambda _checked=False: self.show_dialog())

    def show_dialog(self):
        """Open the notes window, or raise the one already open."""
        from ..dialogs.notes_dialog import NotesDialog

        if self._dialog is not None:
            self._dialog.reload()
            self._dialog.raise_()
            self._dialog.activateWindow()
            return self._dialog

        dialog = NotesDialog(self, self.window)
        dialog.finished.connect(lambda _result: setattr(self, "_dialog", None))
        self._dialog = dialog
        dialog.show()
        return dialog

    def refresh(self) -> None:
        """Show what the controller holds, after a restore replaced it."""
        if self._dialog is not None:
            self._dialog.reload()

    # -- what XPA does to them ------------------------------------------------------

    def append(self, text: str) -> None:
        """Add a line at the end, DS9's `notes append`."""
        self.text = f"{self.text}{text}\n"
        self.refresh()

    def insert(self, text: str) -> None:
        """Add a line at the start, DS9's `notes insert`."""
        self.text = f"{text}\n{self.text}"
        self.refresh()

    def clear(self) -> None:
        """Throw the notes away."""
        self.text = ""
        self.refresh()

    def load(self, path: str | Path) -> bool:
        """Read the notes from a file, DS9's `notes load`."""
        try:
            self.text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            self.status(f"Could not read {Path(path).name}: {exc}", 4000)
            return False
        self.refresh()
        return True

    def save(self, path: str | Path) -> bool:
        """Write the notes to a file, DS9's `notes save`."""
        try:
            Path(path).write_text(self.text, encoding="utf-8")
        except OSError as exc:
            self.status(f"Could not write {Path(path).name}: {exc}", 4000)
            return False
        return True
