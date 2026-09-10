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
DS9's crosshair: a marker you place, not a cursor you chase.

The difference is the whole point of the mode. Out of it, the coordinate
readout and the two cut graphs follow the pointer and change the moment it
leaves the image. In crosshair mode they follow the crosshair, which stays
where it was put -- so a value can be read off, a cut can be looked at, and
the mouse can go and do something else.

What existed: a crosshair the overlay could draw, a colour and a size on the
window, and a Crosshair Parameters "dialog" made of two `QInputDialog`
prompts that asked whether to turn it on. It was never placed by a click and
never drove anything.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtGui import QColor

from .base import Controller

#: What a new crosshair looks like.
DEFAULT_COLOR = "red"
DEFAULT_SIZE = 24

#: The colours DS9's crosshair colour menu offers.
COLORS: tuple[str, ...] = (
    "black",
    "white",
    "red",
    "green",
    "blue",
    "cyan",
    "magenta",
    "yellow",
)


class CrosshairController(Controller):
    """Owns the crosshair: where it is, what it looks like, what it drives."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: Whether the crosshair is drawn.
        self.enabled = False
        #: Its colour and arm length.
        self.color = DEFAULT_COLOR
        self.size = DEFAULT_SIZE
        #: Whether moving it in one frame moves it in the others.
        self.locked = False
        #: The coordinate system the lock matches in.
        self.lock_system = "wcs"

    def connect(self) -> None:
        """Wire the Crosshair Parameters entry and the match commands."""
        self.menu.action_crosshair_params.triggered.connect(lambda _checked=False: self.show_dialog())

    # -- where it is ------------------------------------------------------------

    def position(self, frame=None) -> tuple[float, float] | None:
        """Where the crosshair is on a frame, or None if never placed."""
        target = frame if frame is not None else self.frame
        if target is None:
            return None
        placed = getattr(target, "crosshair", None)
        return (float(placed[0]), float(placed[1])) if placed else None

    def move_to(self, x: float, y: float, propagate: bool = True) -> None:
        """Put the crosshair somewhere and update everything watching it.

        Args:
            x: Image x, counting from one as FITS does.
            y: Image y.
            propagate: Whether to move the other frames' crosshairs too,
                if the lock is on. False when this call *is* the
                propagation, which is what stops it recursing.
        """
        frame = self.frame
        if frame is None:
            return

        frame.crosshair = (float(x), float(y))
        self.enabled = True
        self.refresh()
        self.update_readout(x, y)

        if propagate and self.locked:
            self.propagate(x, y, self.lock_system)

    def propagate(self, x: float, y: float, system: str = "wcs") -> int:
        """Move every other frame's crosshair to the same place.

        Through the sky rather than the pixels when asked for `wcs`: two
        frames of the same field at different scales have the same object at
        different pixels, and matching the pixels would put the crosshairs on
        different things. The other coordinate systems, and a frame with no
        usable WCS, fall back to the pixel position.

        Args:
            x: Image x of the crosshair on this frame.
            y: Image y.
            system: The coordinate system to match in, as DS9's Match ->
                Crosshair submenu offers. Only `wcs` differs today;
                physical, amplifier and detector share image's handling
                until M3-7 makes those systems real.

        Returns:
            How many frames were moved.
        """
        source = self.frame
        if source is None:
            return 0
        handler = getattr(source, "wcs_handler", None)
        sky = None
        if system == "wcs" and handler is not None and getattr(handler, "is_valid", False):
            try:
                sky = handler.pixel_to_world(x, y)
            except Exception:
                sky = None

        moved = 0
        for frame in self.frames.frames:
            if frame is source:
                continue
            target = (x, y)
            other = getattr(frame, "wcs_handler", None)
            if sky is not None and other is not None and getattr(other, "is_valid", False):
                try:
                    px, py = other.world_to_pixel(*sky)
                    target = (float(px), float(py))
                except Exception:
                    target = (x, y)
            frame.crosshair = target
            moved += 1
        return moved

    def match(self, system: str = "wcs") -> None:
        """Frame -> Match -> Crosshair: put every crosshair on this one.

        A one-off copy, unlike the lock, which keeps them together.
        """
        if self.position() is None:
            self.status("No crosshair to match; place one first", 2500)
            return
        x, y = self.position()  # type: ignore[misc]
        moved = self.propagate(x, y, system)
        self.refresh()
        self.status(f"Matched {moved} crosshair(s) ({system})", 2000)

    def centre(self) -> None:
        """Put the crosshair in the middle of the frame, where DS9 starts it."""
        frame = self.frame
        data = getattr(frame, "image_data", None) if frame else None
        if data is None:
            return
        self.move_to(data.shape[1] / 2.0, data.shape[0] / 2.0)

    # -- what it drives ----------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        """Show or hide the crosshair, placing it if it has never been placed."""
        self.enabled = bool(enabled)
        if self.enabled and self.position() is None:
            self.centre()
            return
        self.refresh()

    def refresh(self) -> None:
        """Redraw the crosshair on the current viewer."""
        viewer = self.viewer
        if not hasattr(viewer, "set_crosshair"):
            return
        viewer.set_crosshair(
            self.enabled,
            position=self.position(),
            color=QColor(self.color),
            size=self.size,
        )

    def update_readout(self, x: float, y: float) -> None:
        """Point the readout and the two cut graphs at the crosshair.

        Down the window's own pointer-readout path rather than a second one
        of this controller's: the info panel, the status bar, the WCS
        display, the magnifier and both graphs are all updated there, and
        two paths would drift apart the first time one of them changed.
        """
        updater = getattr(self.window, "_on_mouse_moved", None)
        if not callable(updater):
            return
        # That path takes zero-based image coordinates with y counting up;
        # the crosshair is stored the FITS way, from one.
        updater(int(round(x)) - 1, int(round(y)) - 1)

    def value_at(self, x: float, y: float) -> float | None:
        """The pixel value under the crosshair, or None if it is off the image."""
        frame = self.frame
        data = getattr(frame, "image_data", None) if frame else None
        if data is None:
            return None
        column = int(round(x)) - 1
        row = int(round(y)) - 1
        if 0 <= row < data.shape[0] and 0 <= column < data.shape[1]:
            value = float(data[row, column])
            return value if np.isfinite(value) else None
        return None

    # -- the dialog ---------------------------------------------------------------

    def show_dialog(self) -> None:
        """Show DS9's Crosshair Parameters dialog."""
        from ..dialogs.crosshair_dialog import CrosshairDialog

        existing = getattr(self, "_dialog", None)
        if existing is not None:
            existing.reload()
            existing.raise_()
            existing.activateWindow()
            return

        dialog = CrosshairDialog(self, self.window)
        dialog.finished.connect(lambda _result: setattr(self, "_dialog", None))
        self._dialog = dialog
        dialog.show()

    def sync(self) -> None:
        """Redraw after a frame change, since the crosshair is per frame."""
        self.refresh()

    def set_locked(self, locked: bool, system: str = "wcs") -> None:
        """Lock the crosshair across frames, DS9's Lock -> Crosshair.

        Args:
            locked: Whether to keep the frames' crosshairs together.
            system: Which coordinate system to keep them together in.
        """
        self.locked = bool(locked)
        if self.locked:
            self.lock_system = system
        placed = self.position()
        if self.locked and placed is not None:
            self.propagate(placed[0], placed[1], self.lock_system)
        self.status(f"Crosshair lock: {'on' if locked else 'off'}")
