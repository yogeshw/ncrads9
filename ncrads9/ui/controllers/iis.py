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
IRAF: the IIS server, and the interactive examine it drives.

Two halves. The IIS server is the socket IRAF's `display` writes pixels
to and `imexam` reads the cursor from -- an old protocol, still the way
IRAF talks to a display. Interactive examine is DS9's `iexam`: a script
asks a question, the user clicks, and the answer goes back.

The examine has to block: `xpaget ds9 iexam coordinate image` does not
answer until there has been a click. It blocks on its own event loop
rather than on the GUI thread doing nothing, so the window still redraws
and the click can actually happen.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QEventLoop, Qt, QTimer

from ...communication.iis.iis_server import IISServer
from .base import Controller

#: How long an interactive examine waits for a click before giving up, in
#: milliseconds. A script that asked and walked away should not leave the
#: application waiting for ever.
EXAMINE_TIMEOUT = 120_000

#: What `iexam` can be asked for.
EXAMINE_KINDS: tuple[str, ...] = ("coordinate", "data")


class IISController(Controller):
    """Owns the IIS server and DS9's interactive examine."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: The server, once started.
        self.server: IISServer | None = None
        #: Which file each IIS frame is showing, for `xpaget iis filename`.
        self.filenames: dict[int, str] = {}
        self._loop: QEventLoop | None = None
        self._clicked: tuple[float, float] | None = None

    def connect(self) -> None:
        """Nothing on the menus: DS9 has no IIS entries either."""

    # -- the server ---------------------------------------------------------------

    def running(self) -> bool:
        """Whether the IIS server is listening."""
        return bool(self.server is not None and self.server.running)

    def start(self, port: int = 5137) -> bool:
        """Start the IIS server, so IRAF can display into this window.

        Args:
            port: The port to listen on. IRAF's default is 5137.

        Returns:
            Whether it is listening afterwards.
        """
        if self.running():
            self.status("The IIS server is already running", 2000)
            return True

        server = self.server or IISServer(socket_port=port)
        server.set_image_callback(self.on_image)
        server.set_cursor_callback(self.on_cursor_read)
        server.set_cursor_write_callback(self.on_cursor_write)
        self.server = server

        if not server.start():
            self.status("The IIS server could not be started", 4000)
            return False
        self.status(f"IIS server listening on port {port}", 3000)
        return True

    def stop(self) -> None:
        """Stop the server."""
        if self.server is not None and self.server.running:
            self.server.stop()
            self.status("IIS server stopped", 2000)

    # -- what the server asks for ---------------------------------------------------

    def on_image(self, frame: int, data) -> None:
        """Display what IRAF wrote into one of its frames.

        IRAF writes a line at a time, so this is called often with the same
        frame; the array it is given is the whole buffer.
        """
        array = np.asarray(data, dtype=np.float32)
        name = self.filenames.get(frame, f"IIS frame {frame}")
        self.window.display.load_array(array, name=name)

    def on_cursor_read(self, x: float, y: float, frame: int):
        """Where the cursor is, for IRAF's `imexam`."""
        placed = self.window.crosshair.position()
        if placed is not None:
            return (placed[0], placed[1], frame)
        last = self.window._last_mouse_pos
        if last is not None:
            # The readout counts from zero and IIS from one.
            return (float(last[0]) + 1.0, float(last[1]) + 1.0, frame)
        return (x, y, frame)

    def on_cursor_write(self, x: float, y: float, frame: int) -> None:
        """Move the crosshair, which is what IRAF asked for."""
        self.window.crosshair.move_to(float(x), float(y))

    def filename(self, frame: int | None = None) -> str:
        """What `xpaget iis filename` answers."""
        if frame is None:
            frame = self.server._current_frame if self.server is not None else 1
        return self.filenames.get(int(frame), "")

    def set_filename(self, name: str, frame: int | None = None) -> None:
        """What `xpaset iis filename` sets."""
        if frame is None:
            frame = self.server._current_frame if self.server is not None else 1
        self.filenames[int(frame)] = str(name)

    # -- interactive examine ----------------------------------------------------------

    def examine(
        self,
        what: str = "coordinate",
        system: str = "image",
        sky: str = "fk5",
        sky_format: str = "degrees",
        width: int = 1,
        height: int = 1,
        macro: str = "",
        timeout: int = EXAMINE_TIMEOUT,
    ) -> str:
        """Wait for a click and answer with what was asked for.

        Args:
            what: `coordinate` or `data`.
            system: Which coordinate system a coordinate comes back in.
            sky: The sky frame, when the system is `wcs`.
            sky_format: `degrees` or `sexagesimal`.
            width: For `data`, how wide a box of values to return.
            height: How tall.
            macro: A macro string to expand instead, as DS9's last form
                takes -- `'Click at $x,$y in file $filename'`.
            timeout: How long to wait, in milliseconds.

        Returns:
            The answer, or "" if nothing was clicked in time.
        """
        position = self.wait_for_click(timeout)
        if position is None:
            self.status("Examine: nothing was clicked", 3000)
            return ""

        x, y = position
        if macro:
            return self.expand(macro, x, y)
        if what == "data":
            return self.values(x, y, width, height)
        return self.coordinate(x, y, system, sky, sky_format)

    def wait_for_click(self, timeout: int = EXAMINE_TIMEOUT) -> tuple[float, float] | None:
        """Block until the image is clicked, or the wait runs out.

        Its own event loop, so the window keeps redrawing and the click
        can actually be made -- a plain `while` would freeze the
        application it is waiting for.
        """
        overlay = getattr(self.viewer, "region_overlay", None)
        if overlay is None:
            return None

        self._clicked = None
        self._loop = QEventLoop()
        previous = overlay.examine_handler
        overlay.examine_handler = self._on_click
        self.viewer.setCursor(Qt.CursorShape.CrossCursor)
        self.status("Examine: click on the image", 0)

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(self._loop.quit)
        timer.start(max(1, int(timeout)))
        try:
            self._loop.exec()
        finally:
            timer.stop()
            overlay.examine_handler = previous
            self.viewer.unsetCursor()
            self._loop = None
        return self._clicked

    def _on_click(self, x: float, y: float) -> bool:
        """Take the click the examine was waiting for."""
        self._clicked = (float(x), float(y))
        if self._loop is not None:
            self._loop.quit()
        return True

    # -- what an examine answers with ---------------------------------------------------

    def coordinate(
        self,
        x: float,
        y: float,
        system: str = "image",
        sky: str = "fk5",
        sky_format: str = "degrees",
    ) -> str:
        """One position, in whichever system was asked for."""
        if system in ("image", "physical", "amplifier", "detector"):
            return f"{x:g} {y:g}"

        handler = getattr(self.frame, "wcs_handler", None)
        if handler is None or not getattr(handler, "is_valid", False):
            return f"{x:g} {y:g}"
        longitude, latitude = handler.pixel_to_world(x, y)

        if sky_format.startswith("sex"):
            from astropy.coordinates import SkyCoord

            coordinate = SkyCoord(longitude, latitude, unit="deg", frame=sky.lower())
            return coordinate.to_string("hmsdms", sep=":", precision=3)
        return f"{longitude:.6f} {latitude:.6f}"

    def values(self, x: float, y: float, width: int = 1, height: int = 1) -> str:
        """The pixel values in a box about a position, as DS9's `data` does."""
        frame = self.frame
        data = getattr(frame, "image_data", None) if frame is not None else None
        if data is None:
            return ""

        from ...analysis.pixel_table import PixelTable

        # DS9 takes a width and a height; the reader takes one size, so a
        # box that is not square comes back as the larger of the two
        # rather than being refused.
        size = max(1, int(width), int(height))
        table = PixelTable(data)
        # The reader indexes from zero; a clicked position is FITS's, from
        # one, which is the difference between reading the pixel that was
        # clicked and its neighbour.
        rows = np.atleast_2d(
            np.asarray(table.get_region(int(round(x)) - 1, int(round(y)) - 1, size), dtype=float)
        )
        return "\n".join(" ".join(f"{value:g}" for value in row) for row in rows)

    def expand(self, macro: str, x: float, y: float) -> str:
        """Expand DS9's analysis macros against the clicked position."""
        from ...analysis.macros import MacroContext, expand

        frame = self.frame
        data = getattr(frame, "image_data", None) if frame is not None else None
        value = ""
        if data is not None:
            column, row = int(round(x)) - 1, int(round(y)) - 1
            if 0 <= row < data.shape[0] and 0 <= column < data.shape[1]:
                value = f"{float(data[row, column]):g}"

        context = MacroContext(
            filename=str(getattr(frame, "filepath", "") or ""),
            width=int(data.shape[1]) if data is not None else 0,
            height=int(data.shape[0]) if data is not None else 0,
            # `$x`, `$y` and `$value` are callables in a MacroContext,
            # since a macro can ask for them in any coordinate system.
            coordinate=lambda axis, system, sky, sky_format: self.coordinate(
                x, y, system, sky, sky_format
            ).split()[0 if axis == "x" else -1],
            value=lambda: value,
        )
        return expand(macro, context).command
