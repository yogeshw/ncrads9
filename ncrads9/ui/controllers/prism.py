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
File -> Prism, and the `prism` XPA point.

DS9 opens Prism on the current frame's file when there is one and empty
otherwise (`PrismDialogLoad`), which is what makes the entry useful next to
Open rather than a second file dialog.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

from .base import Controller


class PrismController(Controller):
    """Opens and keeps DS9's Prism windows."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: Every open Prism window, newest last, as DS9's `iprism(prisms)`.
        self.windows: list = []
        #: How many have been opened, for naming the next one.
        self._opened = 0

    def connect(self) -> None:
        """Wire File -> Prism."""
        self.menu.action_prism.triggered.connect(lambda _checked=False: self.show())

    def show(self, path: str | Path | None = None):
        """Open a Prism window.

        Args:
            path: The file to browse. None means the current frame's file
                if it has one, as DS9 does, and nothing otherwise.

        Returns:
            The window.
        """
        from ..dialogs.prism_dialog import PrismDialog

        dialog = PrismDialog(self.window, self.window)
        self._opened += 1
        # DS9 names them prism, prism2, prism3 ... and XPA addresses them by
        # that name (`prism current prism2`).
        dialog.ref = "prism" if self._opened == 1 else f"prism{self._opened}"
        self.windows.append(dialog)
        dialog.finished.connect(lambda _result, made=dialog: self._forget(made))

        target = path if path is not None else self.current_path()
        if target is not None:
            dialog.open_file(str(target))
        dialog.show()
        return dialog

    def current_path(self) -> Path | None:
        """The current frame's file, without any extension specifier.

        DS9 strips the `[...]` before handing the name to Prism, which
        browses the whole file rather than the one extension on screen.
        """
        frame = self.frame
        path = getattr(frame, "filepath", None) if frame is not None else None
        if path is None:
            return None
        text = str(path)
        bracket = text.find("[")
        if bracket > 0:
            text = text[:bracket]
        candidate = Path(text)
        return candidate if candidate.exists() else None

    def _forget(self, dialog) -> None:
        """Drop a closed window."""
        if dialog in self.windows:
            self.windows.remove(dialog)

    @property
    def latest(self):
        """The most recently opened window, which is what XPA addresses."""
        return self.windows[-1] if self.windows else None

    # -- what XPA addresses ----------------------------------------------------------

    def refs(self) -> list[str]:
        """Every open window's name, newest last -- what `xpaget prism` says."""
        return [getattr(dialog, "ref", "prism") for dialog in self.windows]

    def by_ref(self, ref: str):
        """One window by name, or None if there is none."""
        for dialog in self.windows:
            if getattr(dialog, "ref", "") == ref:
                return dialog
        return None

    def set_current(self, ref: str) -> bool:
        """Make one window the one XPA talks to, DS9's `prism current`.

        Returns:
            Whether there was such a window.
        """
        dialog = self.by_ref(ref)
        if dialog is None:
            return False
        self.windows.remove(dialog)
        self.windows.append(dialog)
        return True

    def ensure(self):
        """The window XPA is talking to, opening one if none is open."""
        return self.latest if self.windows else self.show()
