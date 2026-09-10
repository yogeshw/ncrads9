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
The Image Servers menu: fetching a cutout and loading it into a frame.

Nine servers, one dialog, and one transport -- which is injectable, so the
whole path from menu click to loaded frame can be tested without asking
anyone for an image.

A retrieved cutout goes into a *new* frame, which is what DS9 does: the
point of fetching a survey image is usually to compare it with what is
already loaded, and replacing that would defeat it.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

from ...image_servers import fetch as fetch_module
from ...image_servers.servers import SERVERS, ImageServer, by_name
from ..dialogs.image_server_dialog import ImageServerDialog
from .base import Controller


class ImageServerController(Controller):
    """Owns the Image Servers menu."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: How cutouts are fetched. Replaced in tests; `None` is the real
        #: network client.
        self.transport = None
        #: The dialogs open, by server name, so they are not collected.
        self._dialogs: dict[str, ImageServerDialog] = {}

    def connect(self) -> None:
        """Wire every image server on the menu."""
        for name, action in self.menu.image_server_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.show_dialog(key))

    def frame_center(self) -> tuple[float, float] | None:
        """The current frame's centre in degrees, or None with no WCS."""
        frame = self.frame
        handler = getattr(frame, "wcs_handler", None) if frame else None
        data = getattr(frame, "image_data", None) if frame else None
        if handler is None or not getattr(handler, "is_valid", False) or data is None:
            return None
        try:
            longitude, latitude = handler.pixel_to_world(data.shape[1] / 2.0, data.shape[0] / 2.0)
        except Exception:
            return None
        return (float(longitude), float(latitude))

    def show_dialog(self, name: str) -> ImageServerDialog | None:
        """Open one server's dialog, or raise the open one."""
        server = by_name(name)
        if server is None:
            self.status(f"No such image server: {name}", 3000)
            return None

        existing = self._dialogs.get(name)
        if existing is not None:
            existing.raise_()
            existing.activateWindow()
            return existing

        dialog = ImageServerDialog(server, self.frame_center(), self.window)
        dialog.retrieve_requested.connect(
            lambda longitude, latitude, width, height, survey, s=server, d=dialog: self.retrieve(
                s, longitude, latitude, width, height, survey, d
            )
        )
        dialog.name_requested.connect(lambda text, d=dialog: self.resolve(text, d))
        dialog.finished.connect(lambda _result, key=name: self._dialogs.pop(key, None))
        self._dialogs[name] = dialog
        dialog.show()
        return dialog

    def resolve(self, name: str, dialog: ImageServerDialog) -> None:
        """Resolve an object name to coordinates and fill the dialog in."""
        from astropy.coordinates import SkyCoord

        try:
            coordinate = SkyCoord.from_name(name)
        except Exception as exc:
            dialog.set_message(f"Could not resolve {name}: {exc}")
            return
        dialog.set_center(coordinate.ra.deg, coordinate.dec.deg)
        dialog.set_message(f"{name}: {coordinate.ra.deg:.6f} {coordinate.dec.deg:.6f}")

    def retrieve(
        self,
        server: ImageServer,
        longitude: float,
        latitude: float,
        width: float,
        height: float,
        survey: str = "",
        dialog: ImageServerDialog | None = None,
    ) -> Path | None:
        """Fetch a cutout and load it into a new frame.

        Returns:
            The file loaded, or None if the fetch failed.
        """
        request = fetch_module.ImageRequest(
            server=server,
            longitude=longitude,
            latitude=latitude,
            width=width,
            height=height,
            survey=survey,
        )
        self.status(f"Retrieving from {server.label}...")

        try:
            path = fetch_module.retrieve(request, transport=self.transport)
        except fetch_module.ImageServerError as exc:
            self.status(str(exc), 6000)
            if dialog is not None:
                dialog.set_message(str(exc))
            return None

        try:
            self.window.frame_controller.new_frame()
            self.window.display.load_fits(str(path))
        except Exception as exc:
            self.status(f"{server.label} returned an image that will not load: {exc}", 6000)
            if dialog is not None:
                dialog.set_message(str(exc))
            return None

        message = f"Loaded {server.label}"
        if survey:
            message += f" ({survey})"
        self.status(message)
        if dialog is not None:
            dialog.set_message(message)
        return path

    def server_names(self) -> tuple[str, ...]:
        """Every server's internal name, for XPA."""
        return tuple(server.name for server in SERVERS)
