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
File -> SAMP and File -> SAMP Hub: talking to the other applications.

DS9 has two submenus and they do different things. SAMP connects *this*
application to a hub and broadcasts the current image or table to whatever
else is registered -- Topcat, Aladin, another DS9. SAMP Hub runs a hub
here, for when nothing else is running one.

The VO menu's own SAMP entries are left where they are: those are the
marker colour, shape and size for a table that arrives *over* SAMP, which
is a different job from broadcasting one.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QMessageBox

from ...communication.samp.samp_hub import SAMPHub
from .base import Controller

#: What a broadcast of each kind needs from the frame.
BROADCASTS: tuple[str, ...] = ("image", "table")


class SAMPController(Controller):
    """Owns File -> SAMP and File -> SAMP Hub."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: The hub this application is running, if it started one.
        self.hub: SAMPHub | None = None
        #: Whether the hub serves the web profile, so a browser-based tool
        #: can join (M9-28). DS9's hub does; ours does unless told not to.
        self.web_profile = True

    def connect(self) -> None:
        """Wire both submenus."""
        menu = self.menu
        menu.action_samp_file_connect.triggered.connect(lambda _checked=False: self.connect_hub())
        menu.action_samp_file_disconnect.triggered.connect(lambda _checked=False: self.disconnect_hub())
        for name, action in menu.samp_broadcast_actions.items():
            action.triggered.connect(lambda _checked=False, kind=name: self.broadcast(kind))

        menu.action_samp_hub_information.triggered.connect(lambda _checked=False: self.show_information())
        menu.action_samp_hub_start.triggered.connect(lambda _checked=False: self.start_hub())
        menu.action_samp_hub_stop.triggered.connect(lambda _checked=False: self.stop_hub())
        self.sync()

    def sync(self) -> None:
        """Grey out what makes no sense, and refresh the client lists."""
        menu = self.menu
        connected = bool(self.window._samp_connected)
        menu.action_samp_file_connect.setEnabled(not connected)
        menu.action_samp_file_disconnect.setEnabled(connected)
        for action in menu.samp_broadcast_actions.values():
            action.setEnabled(connected)

        running = self.hub_running()
        menu.action_samp_hub_start.setEnabled(not running)
        menu.action_samp_hub_stop.setEnabled(running)
        self.refresh_clients()

    # -- connecting -----------------------------------------------------------------

    def connect_hub(self) -> bool:
        """Connect to a hub, as the VO menu's Connect does.

        Returns:
            Whether it connected.
        """
        self.window.vo.samp_connect()
        self.sync()
        return bool(self.window._samp_connected)

    def disconnect_hub(self) -> bool:
        """Disconnect from the hub."""
        self.window.vo.samp_disconnect()
        self.sync()
        return True

    def clients(self) -> list[dict[str, str]]:
        """Everything else registered with the hub, if we are connected."""
        client = self.window._samp_client
        if client is None or not self.window._samp_connected:
            return []
        try:
            return list(client.get_registered_clients())
        except Exception:
            return []

    def refresh_clients(self) -> None:
        """Put the registered clients under Image and Table, as DS9 does.

        A broadcast goes to everything; the entries under it send to one
        client, which is how you get an image into Topcat without also
        sending it to Aladin.
        """
        for kind, submenu in self.menu.samp_broadcast_menus.items():
            broadcast = self.menu.samp_broadcast_actions[kind]
            for action in list(submenu.actions()):
                if action is not broadcast and not action.isSeparator():
                    submenu.removeAction(action)
            for client in self.clients():
                name = client.get("name") or client.get("id") or "?"
                identifier = client.get("id")
                action = submenu.addAction(name)
                action.triggered.connect(
                    lambda _checked=False, k=kind, who=identifier: self.broadcast(k, who)
                )

    # -- broadcasting ----------------------------------------------------------------

    def broadcast(self, kind: str, recipient: str | None = None) -> bool:
        """Send the current image or table to the other applications.

        SAMP passes a *URL*, not the bytes, so what is broadcast has to be
        a file on disk that the other application can open. A frame with no
        file behind it -- an array over XPA, a mosaic assembled in memory
        -- has nothing to send, and saying so is better than sending a
        broken URL.

        Args:
            kind: `image` or `table`.
            recipient: One client's id, or None for everything.

        Returns:
            Whether the message went.
        """
        if kind not in BROADCASTS:
            self.status(f"{kind} is not something SAMP broadcasts", 3000)
            return False

        client = self.window._samp_client
        if client is None or not self.window._samp_connected:
            self.status("Connect to a SAMP hub first", 3000)
            return False

        path = self.current_path(kind)
        if path is None:
            self.status(
                "SAMP sends a URL, and this frame has no file behind it -- save it first",
                5000,
            )
            return False

        url = path.as_uri()
        sender = client.send_image if kind == "image" else client.send_table
        if not sender(url, recipient):
            self.status(f"The {kind} could not be broadcast", 4000)
            return False

        where = "one client" if recipient else "every client"
        self.status(f"Broadcast {path.name} to {where}", 3000)
        return True

    def current_path(self, kind: str) -> Path | None:
        """The file a broadcast would send, or None if there is not one."""
        frame = self.frame
        if frame is None:
            return None
        if kind == "table":
            # A catalogue is broadcast from the file it came from. One
            # queried from a server and never saved has no URL to send,
            # and `source` is where that is recorded.
            catalogs = getattr(self.window.catalog, "catalogs", None)
            loaded = list(getattr(catalogs, "catalogs", []) or [])
            for catalog in reversed(loaded):
                candidate = Path(str(catalog.source))
                if catalog.source and candidate.exists():
                    return candidate
            return None
        path = getattr(frame, "filepath", None)
        if path is None:
            return None
        candidate = Path(str(path).split("[")[0])
        return candidate if candidate.exists() else None

    # -- the hub ----------------------------------------------------------------------

    def hub_running(self) -> bool:
        """Whether the hub we started is running."""
        return bool(self.hub is not None and self.hub.is_running())

    def start_hub(self) -> bool:
        """Start a hub here, DS9's SAMP Hub -> Start.

        Returns:
            Whether it is running afterwards.
        """
        if self.hub_running():
            self.status("The SAMP hub is already running", 2000)
            return True
        if self.hub is None:
            self.hub = SAMPHub()
        started = bool(self.hub.start(web_profile=self.web_profile))
        self.sync()
        if started:
            web = " with the web profile" if self.web_profile else ""
            self.status(f"SAMP hub started{web}", 3000)
        else:
            self.status("The SAMP hub could not be started", 4000)
        return started

    def stop_hub(self) -> bool:
        """Stop the hub."""
        if not self.hub_running():
            self.status("No SAMP hub is running here", 2000)
            return True
        self.hub.stop()
        self.sync()
        self.status("SAMP hub stopped", 3000)
        return True

    def information(self) -> str:
        """What SAMP Hub -> Information shows."""
        lines = []
        if self.hub_running():
            lines.append("Hub: running here")
            lines.append(f"Web profile: {'yes' if self.web_profile else 'no'}")
        elif SAMPHub.is_hub_running():
            lines.append("Hub: running elsewhere")
            found = SAMPHub.find_hub()
            if found:
                lines.append(f"Address: {found}")
        else:
            lines.append("Hub: none running")

        lines.append(f"Connected: {'yes' if self.window._samp_connected else 'no'}")
        clients = self.clients()
        lines.append(f"Registered clients: {len(clients)}")
        lines.extend(f"  {client.get('name') or client.get('id')}" for client in clients)
        return "\n".join(lines)

    def show_information(self) -> None:
        """Show it."""
        box = QMessageBox(self.window)
        box.setWindowTitle("SAMP Hub Information")
        box.setText(self.information())
        box.exec()

    def clean_exit(self) -> None:
        """Stop the hub, so it does not outlive the application."""
        if self.hub_running():
            self.hub.stop()
