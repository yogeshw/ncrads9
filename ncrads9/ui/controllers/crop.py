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
DS9's crop: choosing the section of the data a frame displays.

What existed was Crop Parameters, which zoomed and panned so a rectangle
filled the viewport. That is a useful thing, but it is not what DS9's crop
does and it is what the Zoom pointer mode's rubber band is for. DS9's crop
keeps the view exactly where it is and stops displaying what falls outside
the rectangle: coordinates, regions and the readout all stay put, and the
scale limits come from the cropped section alone.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from ...frames.crop import CropRegion
from .base import Controller


class CropController(Controller):
    """Owns each frame's crop: setting it, resetting it, matching it."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: Which coordinate system the lock matches crops in.
        self.lock_system = "wcs"
        #: Whether cropping one frame crops them all.
        self.locked = False
        self._dialog = None

    def connect(self) -> None:
        """Wire Zoom -> Crop Parameters."""
        self.menu.action_crop_parameters.triggered.connect(lambda _checked=False: self.show_dialog())

    # -- the crop itself -----------------------------------------------------------

    def region(self, frame=None) -> CropRegion | None:
        """The crop on a frame, or None when it displays everything."""
        target = frame if frame is not None else self.frame
        return getattr(target, "crop", None) if target is not None else None

    def shape(self, frame=None) -> tuple[int, int] | None:
        """The frame's data shape, or None when it has no data."""
        target = frame if frame is not None else self.frame
        data = getattr(target, "image_data", None) if target is not None else None
        return (int(data.shape[0]), int(data.shape[1])) if data is not None else None

    def set_region(self, crop: CropRegion | None, propagate: bool = True) -> bool:
        """Crop the current frame, or uncrop it with None.

        Args:
            crop: The section to display, clipped to the data first.
            propagate: Whether the lock may copy this to the other frames.
                False when this call *is* the propagation.

        Returns:
            Whether the frame was cropped.
        """
        frame = self.frame
        shape = self.shape(frame)
        if frame is None or shape is None:
            self.status("No image to crop", 2000)
            return False

        if crop is not None:
            crop = crop.clipped_to(shape)
            if not crop.is_usable():
                self.status("Crop region is too small", 2500)
                return False
            if crop.covers(shape):
                crop = None

        frame.crop = crop
        # The limits were measured over what used to be displayed, so they
        # have to be measured again -- that is DS9's CROPSEC.
        self.window.scale.invalidate()
        self.window.display.display()
        if self._dialog is not None:
            self._dialog.reload()

        if propagate and self.locked:
            self.propagate(crop, self.lock_system)
        return True

    def crop_to(self, x0: float, y0: float, x1: float, y1: float) -> bool:
        """Crop to a rectangle in image pixels, as the pointer's drag does."""
        return self.set_region(CropRegion(x0, y0, x1, y1))

    def reset(self) -> None:
        """Display the whole image again, DS9's Reset on the crop dialog."""
        frame = self.frame
        if frame is None:
            return
        if self.region(frame) is None:
            self.status("Frame is not cropped", 2000)
            return
        self.set_region(None)
        self.status("Crop reset")

    # -- across frames -------------------------------------------------------------

    def propagate(self, crop: CropRegion | None, system: str = "wcs") -> int:
        """Copy a crop to every other frame.

        Through the sky when asked for `wcs`, so the same patch of sky is
        displayed in each frame however its pixels are laid out; through the
        pixels otherwise, and whenever a frame has no usable WCS.

        Args:
            crop: The crop to copy, or None to uncrop the others too.
            system: The coordinate system to match in.

        Returns:
            How many frames were changed.
        """
        source = self.frame
        if source is None:
            return 0

        sky_corners = None
        handler = getattr(source, "wcs_handler", None)
        if crop is not None and system == "wcs" and getattr(handler, "is_valid", False):
            try:
                sky_corners = [handler.pixel_to_world(x, y) for x, y in crop.corners]
            except Exception:
                sky_corners = None

        changed = 0
        for frame in self.frames.frames:
            if frame is source:
                continue
            data = getattr(frame, "image_data", None)
            if data is None:
                continue
            target = crop
            other = getattr(frame, "wcs_handler", None)
            if sky_corners is not None and getattr(other, "is_valid", False):
                try:
                    (x0, y0), (x1, y1) = (other.world_to_pixel(*sky) for sky in sky_corners)
                    target = CropRegion(float(x0), float(y0), float(x1), float(y1))
                except Exception:
                    target = crop
            if target is not None:
                target = target.clipped_to(data.shape)
                if not target.is_usable():
                    continue
                if target.covers(data.shape):
                    target = None
            frame.crop = target
            changed += 1
        return changed

    def match(self, system: str = "wcs") -> None:
        """Frame -> Match -> Crop: crop every frame like this one."""
        crop = self.region()
        if self.frame is None:
            self.status("No frame to match", 2000)
            return
        changed = self.propagate(crop, system)
        self.window.scale.invalidate()
        self.window.display.display()
        what = "uncropped" if crop is None else "cropped"
        self.status(f"Matched {changed} frame(s) {what} ({system})", 2000)

    def set_locked(self, locked: bool, system: str = "wcs") -> None:
        """Frame -> Lock -> Crop: keep the frames' crops together."""
        self.locked = bool(locked)
        if self.locked:
            self.lock_system = system
            self.propagate(self.region(), system)
        self.status(f"Crop lock: {'on' if locked else 'off'}")

    # -- the dialog ------------------------------------------------------------------

    def show_dialog(self) -> None:
        """Show DS9's Crop Parameters dialog."""
        from ..dialogs.crop_parameters_dialog import CropParametersDialog

        if self._dialog is not None:
            self._dialog.reload()
            self._dialog.raise_()
            self._dialog.activateWindow()
            return

        dialog = CropParametersDialog(self, self.window)
        dialog.finished.connect(lambda _result: setattr(self, "_dialog", None))
        self._dialog = dialog
        dialog.show()

    def sync(self) -> None:
        """Follow a frame change, since the crop is per frame."""
        if self._dialog is not None:
            self._dialog.reload()

    # -- cubes -------------------------------------------------------------------------

    def set_slice_range(self, low: float | None, high: float | None) -> None:
        """DS9's `crop 3d`: the slices of a cube worth displaying.

        Recorded on the frame and shown in the dialog. The cube itself is
        3D work (M9-21), so nothing clips a slice out yet.
        """
        frame = self.frame
        if frame is None:
            return
        if low is None or high is None:
            frame.crop_z = None
            self.status("3D crop reset", 2000)
            return
        frame.crop_z = (min(float(low), float(high)), max(float(low), float(high)))
        self.status(f"3D crop: slices {frame.crop_z[0]:g} to {frame.crop_z[1]:g}", 2000)
