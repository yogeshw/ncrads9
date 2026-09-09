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
The View menu: what parts of the window are visible.

DS9 has more than twenty visibility toggles here (PLAN.md §5.3) -- the
information panel, panner, magnifier, buttons, icons, colorbar, the two cut
graphs, the horizontal/vertical layout switch, basic/advanced modes, and a
toggle per info-panel field. NCRADS9 has three. M3 builds the DS9 window
layout and hangs the rest of them here.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from .base import Controller


class ViewController(Controller):
    """Owns the View menu."""

    def connect(self) -> None:
        """Wire the View menu."""
        self.menu.action_fullscreen.triggered.connect(self.set_fullscreen)
        self.menu.action_show_toolbar.triggered.connect(self.set_toolbar_visible)
        self.menu.action_show_statusbar.triggered.connect(self.set_statusbar_visible)

    def set_fullscreen(self, fullscreen: bool) -> None:
        """Show the window full screen, or return it to normal."""
        if fullscreen:
            self.window.showFullScreen()
        else:
            self.window.showNormal()

    def set_toolbar_visible(self, visible: bool) -> None:
        """Show or hide the toolbar."""
        self.window.main_toolbar.setVisible(visible)

    def set_statusbar_visible(self, visible: bool) -> None:
        """Show or hide the status bar."""
        self.window.statusBar().setVisible(visible)
