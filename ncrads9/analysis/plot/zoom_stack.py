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
A plot's zoom history, so zooming in can be undone one step at a time.

DS9 inherits this from BLT (`ds9/library/plotzoomstack.tcl`, which redefines
`blt::ZoomStack`): each drag pushes the view you were looking at, and
zooming out pops back to it. The bottom of the stack is the automatic view
that fits the data, which is why `reset` empties the stack rather than
pushing another entry.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

#: A view: (x0, x1, y0, y1), with None for an axis left automatic.
View = tuple[float | None, float | None, float | None, float | None]

#: How deep the history goes. DS9's is unbounded; a cap keeps a window that
#: has been zoomed a thousand times from holding a thousand views.
MAX_DEPTH = 100


class ZoomStack:
    """The views a plot has been zoomed out of, most recent last."""

    def __init__(self) -> None:
        self._views: list[View] = []

    def __len__(self) -> int:
        return len(self._views)

    def __bool__(self) -> bool:
        return bool(self._views)

    @property
    def views(self) -> tuple[View, ...]:
        """The history, oldest first."""
        return tuple(self._views)

    @property
    def depth(self) -> int:
        """How many times zooming out will do something."""
        return len(self._views)

    def push(self, view: View) -> None:
        """Remember the view being left behind.

        A view identical to the top is not pushed twice: a click that
        happened not to change anything should not cost a zoom-out.
        """
        if self._views and self._views[-1] == view:
            return
        self._views.append(view)
        if len(self._views) > MAX_DEPTH:
            del self._views[0]

    def pop(self) -> View | None:
        """The view to go back to, or None at the bottom of the stack."""
        return self._views.pop() if self._views else None

    def peek(self) -> View | None:
        """The view zooming out would return to, without leaving here."""
        return self._views[-1] if self._views else None

    def reset(self) -> None:
        """Forget the history, which is what going back to automatic means."""
        self._views.clear()
