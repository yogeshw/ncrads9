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
Base class for the per-menu controllers.

PLAN.md §3.2: `main_window.py` was a 4,700-line, 238-method god object holding
file I/O, rendering, colormaps, scaling, blocking, smoothing, contours, grids,
masks, crosshairs, WCS formatting, frames, tiling, RGB composition, regions,
SAMP, VO queries, printing, preferences and external analysis commands. Nothing
in it could be tested without constructing the whole window, and it was where
essentially all the real logic lived.

M2 splits that behaviour into one controller per DS9 menu. Each controller owns
its menu's actions -- it connects them and keeps their checkmarks in step --
and holds the methods that implement them.

Controllers reach shared application state through `self.window`. That is a
deliberate intermediate step rather than the end state: passing each controller
only the collaborators it needs would be cleaner, but the 238 methods are
mutually entangled, and untangling them *and* relocating them in one move would
make the change unreviewable and unverifiable. Relocating first, with bodies
moved verbatim, keeps every step behaviour-preserving and testable; narrowing
the dependencies comes after, once each controller's real surface is visible.

The important property established here is that menu, XPA and the command line
all reach the same controller method, so they cannot drift apart -- which is
how they had already diverged before M2 (PLAN.md §4).

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...coordinates.coord_system import CoordinateContext
    from ...frames.frame import Frame
    from ...frames.frame_manager import FrameManager
    from ..main_window import MainWindow
    from ..menu_bar import MenuBar
    from ..status_bar import StatusBar

#: How long a transient status-bar message stays up, in milliseconds.
DEFAULT_MESSAGE_MS = 2000


class Controller:
    """Owns one DS9 menu: its actions, and the behaviour behind them."""

    def __init__(self, window: MainWindow) -> None:
        """
        Args:
            window: The main window, used to reach shared application state.
        """
        self.window = window

    # -- shared state, named once so controllers do not repeat the path ------

    @property
    def menu(self) -> MenuBar:
        """The menu bar holding this controller's actions."""
        return self.window.menu_bar

    @property
    def frames(self) -> FrameManager:
        """The frame collection."""
        return self.window.frame_manager

    @property
    def frame(self) -> Frame | None:
        """The current frame, or None when there is none."""
        return self.window.frame_manager.current_frame

    @property
    def viewer(self) -> Any:
        """The active image viewer, CPU or GPU backed."""
        return self.window.image_viewer

    @property
    def status_bar(self) -> StatusBar:
        """The status bar's coordinate and value fields."""
        return self.window.status_bar

    @property
    def coords(self) -> CoordinateContext:
        """The current coordinate display settings."""
        return self.window.coord_context

    # -- helpers every controller needs --------------------------------------

    def status(self, message: str, msecs: int = DEFAULT_MESSAGE_MS) -> None:
        """Show a transient message in the status bar."""
        self.window.statusBar().showMessage(message, msecs)

    def require_frame(self, message: str = "No image loaded") -> Frame | None:
        """Return the current frame if it holds data, else complain and fail.

        Almost every menu action needs this guard; before M2 it was repeated
        inline about forty times.
        """
        frame = self.frame
        if frame is None or not frame.has_data:
            self.status(message)
            return None
        return frame

    def refresh(self) -> None:
        """Redraw the current frame."""
        self.window._display_image()

    def connect(self) -> None:
        """Wire this controller's menu actions to its methods.

        Called once, during window construction. Subclasses override it.
        """

    def sync(self) -> None:
        """Bring this controller's menu state in step with the current frame.

        Called when the current frame changes, so checkmarks and radio groups
        show the new frame's settings. Subclasses override it as needed.
        """
