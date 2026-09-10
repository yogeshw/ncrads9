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
An undo stack: what was done, how to take it back, how to do it again.

DS9's Edit menu has one Undo and no Redo, and its undo takes back the last
region edit alone (`UpdateEditMenu` disables it outside region and
illustrate modes). This is the deeper stack PLAN asks for -- a named
command with an undo and a redo, remembered to a depth -- because "I have
just undone three things and want them back" is a reasonable thing to
want, and Redo is already on our Edit menu.

Nothing here knows what a region or a colormap is: a command is a label
and two callables, and the controllers say what those do.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

#: How many commands are kept. Region snapshots are small; a hundred of
#: them is nothing, and a hundred steps is more than anyone walks back.
DEFAULT_DEPTH = 100


@dataclass(frozen=True)
class Command:
    """One thing that was done, and how to take it back.

    Attributes:
        label: What to call it on the menu -- "Delete Region", so the entry
            reads "Undo Delete Region" as every other application's does.
        undo: Called to take it back.
        redo: Called to do it again.
    """

    label: str
    undo: Callable[[], None]
    redo: Callable[[], None]


class UndoStack:
    """What has been done and what has been undone."""

    def __init__(self, depth: int = DEFAULT_DEPTH) -> None:
        """
        Args:
            depth: How many commands to keep. The oldest is dropped first.
        """
        self.depth = max(1, int(depth))
        #: Done, oldest first.
        self._done: list[Command] = []
        #: Undone, most recently undone last.
        self._undone: list[Command] = []
        #: True while undoing or redoing, so a command that changes the
        #: same state does not record itself as a new command.
        self.applying = False

    def __len__(self) -> int:
        """How many commands can be undone."""
        return len(self._done)

    # -- recording ---------------------------------------------------------------

    def push(self, command: Command) -> Command | None:
        """Remember one command.

        Anything undone is forgotten, as it is in every editor: once you do
        something new, the branch you had undone is not coming back.

        Args:
            command: What was done.

        Returns:
            The command, or None if it was ignored because an undo or a
            redo was in progress.
        """
        if self.applying:
            return None
        self._done.append(command)
        del self._done[: max(0, len(self._done) - self.depth)]
        self._undone.clear()
        return command

    def record(self, label: str, undo: Callable[[], None], redo: Callable[[], None]) -> Command | None:
        """Remember a command described by its two callables."""
        return self.push(Command(label=label, undo=undo, redo=redo))

    # -- walking it back and forth --------------------------------------------------

    @property
    def can_undo(self) -> bool:
        """Whether there is anything to undo."""
        return bool(self._done)

    @property
    def can_redo(self) -> bool:
        """Whether there is anything to redo."""
        return bool(self._undone)

    @property
    def undo_label(self) -> str:
        """What the next undo would take back, or "" if there is nothing."""
        return self._done[-1].label if self._done else ""

    @property
    def redo_label(self) -> str:
        """What the next redo would do again, or "" if there is nothing."""
        return self._undone[-1].label if self._undone else ""

    def undo(self) -> str | None:
        """Take back the last command.

        Returns:
            Its label, or None if there was nothing to undo.
        """
        if not self._done:
            return None
        command = self._done.pop()
        self.applying = True
        try:
            command.undo()
        finally:
            self.applying = False
        self._undone.append(command)
        return command.label

    def redo(self) -> str | None:
        """Do the last undone command again.

        Returns:
            Its label, or None if there was nothing to redo.
        """
        if not self._undone:
            return None
        command = self._undone.pop()
        self.applying = True
        try:
            command.redo()
        finally:
            self.applying = False
        self._done.append(command)
        return command.label

    def clear(self) -> None:
        """Forget everything, as loading a new file does."""
        self._done.clear()
        self._undone.clear()

    def labels(self) -> list[str]:
        """What can be undone, oldest first. For tests and for a history."""
        return [command.label for command in self._done]
