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
File -> XPA: what the server is, and turning it off and on.

DS9's submenu is Information, Connect and Disconnect (`mfile.tcl`), and
Information is where you find the name another program has to address --
which is the only thing anyone opens it for.

Author: Yogesh Wadadekar

"""

from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox

from .base import Controller


class XPAController(Controller):
    """Owns File -> XPA."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: The running server, set by the application at startup. None when
        #: XPA is switched off in the configuration.
        self.server = None
        #: The command table, so Information can say how many points there
        #: are and a test can reach them without a server.
        self.commands = None

    def connect(self) -> None:
        """Wire File -> XPA."""
        menu = self.menu
        menu.action_xpa_information.triggered.connect(lambda _checked=False: self.show_information())
        menu.action_xpa_connect.triggered.connect(lambda _checked=False: self.start())
        menu.action_xpa_disconnect.triggered.connect(lambda _checked=False: self.stop())

    def attach(self, server, commands=None) -> None:
        """Take the server the application started."""
        self.server = server
        if commands is not None:
            self.commands = commands
        self.sync()

    def sync(self) -> None:
        """Grey out whichever of Connect and Disconnect makes no sense."""
        running = self.is_running()
        self.menu.action_xpa_connect.setEnabled(not running)
        self.menu.action_xpa_disconnect.setEnabled(running)

    def is_running(self) -> bool:
        """Whether the server is listening."""
        server = self.server
        return bool(server is not None and getattr(server, "running", False))

    # -- the three entries ----------------------------------------------------------

    def information(self) -> str:
        """What Information shows: the address, and what can be sent to it."""
        server = self.server
        if server is None:
            return "XPA is switched off in the configuration."

        points = len(self.commands.get_available_commands()) if self.commands is not None else 0
        lines = [
            f"Name:    {getattr(server, 'name', 'ncrads9')}",
            f"Address: {getattr(server, 'address', '')}",
            f"State:   {'connected' if self.is_running() else 'disconnected'}",
            f"Access points: {points}",
            "",
            "Example:",
            f"  xpaget {getattr(server, 'name', 'ncrads9')} frame",
            f"  xpaset -p {getattr(server, 'name', 'ncrads9')} zoom 2",
        ]
        return "\n".join(lines)

    def show_information(self) -> None:
        """Show it, with the access points behind the details button."""
        box = QMessageBox(self.window)
        box.setWindowTitle("XPA Information")
        box.setText(self.information())
        if self.commands is not None:
            box.setDetailedText(self.commands.describe_points())
        box.exec()

    def start(self) -> bool:
        """Connect: start listening.

        Returns:
            Whether the server is listening afterwards.
        """
        server = self.server
        if server is None:
            self.status("XPA is switched off in the configuration", 3000)
            return False
        if self.is_running():
            self.status("XPA is already connected", 2000)
            return True
        started = bool(server.start())
        self.sync()
        self.status(
            f"XPA connected on {server.address}" if started else "XPA could not connect",
            3000,
        )
        return started

    def stop(self) -> bool:
        """Disconnect: stop listening.

        Returns:
            Whether the server is stopped afterwards.
        """
        server = self.server
        if server is None or not self.is_running():
            self.status("XPA is not connected", 2000)
            return True
        server.stop()
        self.sync()
        self.status("XPA disconnected", 3000)
        return True
