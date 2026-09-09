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
The WCS menu: which coordinate system positions are reported in.

The settings themselves live in `coordinates.CoordinateContext`, which also
does the transforming and formatting; this controller only drives it from the
menu and keeps the readout in step.

DS9 offers rather more (PLAN.md §5.11): the alternate WCS solutions `wcsa`
through `wcsz`, image/physical/amplifier/detector as display systems, and a
WCS Parameters dialog for editing or replacing a frame's WCS. `CoordFrame`
already declares the systems; M3-7 surfaces them and M9 adds the dialog.

Direction arrows are a deliberate NCRADS9 addition, not a DS9 feature
(PLAN.md §7).

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import astropy.units as u
from astropy.coordinates import ICRS, SkyCoord

from ..view_transform import DisplayTransform
from .base import Controller

#: Menu action suffix -> the sky frame token it selects.
SKY_ACTIONS: tuple[str, ...] = ("fk5", "fk4", "icrs", "galactic", "ecliptic")

#: Menu action suffix -> the format token it selects.
FORMAT_ACTIONS: tuple[str, ...] = ("sexagesimal", "degrees")

#: Offset used to find north and east on the sky for the direction arrows.
ARROW_SEPARATION = 1.0 * u.arcmin


class WCSController(Controller):
    """Owns the WCS menu."""

    def connect(self) -> None:
        """Wire the WCS menu."""
        for name in SKY_ACTIONS:
            action = getattr(self.menu, f"action_wcs_{name}")
            action.triggered.connect(lambda _checked=False, s=name: self.set_sky_frame(s))

        for name in FORMAT_ACTIONS:
            action = getattr(self.menu, f"action_wcs_{name}")
            action.triggered.connect(lambda _checked=False, f=name: self.set_format(f))

        self.menu.action_show_direction_arrows.triggered.connect(self.set_direction_arrows_visible)

    def sync(self) -> None:
        """Tick the entries matching the current coordinate settings."""
        for name in SKY_ACTIONS:
            getattr(self.menu, f"action_wcs_{name}").setChecked(self.coords.sky.value == name)
        for name in FORMAT_ACTIONS:
            getattr(self.menu, f"action_wcs_{name}").setChecked(self.coords.sky_format.value == name)

    # -- coordinate settings -------------------------------------------------

    def set_sky_frame(self, system: str) -> None:
        """Report coordinates in the given sky frame.

        Args:
            system: One of fk4, fk5, icrs, galactic, ecliptic.
        """
        self.window.coord_context = self.coords.with_sky(system)
        self.sync()
        self.status(f"WCS system: {system.upper()}")
        self.refresh_readout()
        self.update_direction_arrows()

    def set_format(self, format_type: str) -> None:
        """Write coordinates as sexagesimal or as decimal degrees.

        Args:
            format_type: Either "sexagesimal" or "degrees".
        """
        self.window.coord_context = self.coords.with_format(format_type)
        self.sync()
        self.status(f"WCS format: {format_type}")
        self.refresh_readout()

    # -- readout -------------------------------------------------------------

    @property
    def _has_wcs(self) -> bool:
        """True when the current frame carries a usable WCS."""
        handler = self.window.wcs_handler
        return handler is not None and handler.is_valid

    def refresh_readout(self) -> None:
        """Re-render the coordinate readout at the last cursor position."""
        if self.window._last_mouse_pos is not None and self._has_wcs:
            self.update_readout(*self.window._last_mouse_pos)

    def update_readout(self, x: int, y: int) -> None:
        """Show the sky position of one image pixel in the status bar."""
        if not self._has_wcs:
            return
        ra, dec = self.window.wcs_handler.pixel_to_world(x, y)
        self.status_bar.update_wcs_coords(self.coords.describe_sky(ra, dec))

    # -- direction arrows ----------------------------------------------------

    def set_direction_arrows_visible(self, visible: bool) -> None:
        """Show or hide the north/east compass overlay."""
        self.window._show_direction_arrows = visible
        self.update_direction_arrows()

    def update_direction_arrows(self) -> None:
        """Recompute the north and east arrows from the frame's WCS.

        The arrows point along increasing declination and increasing right
        ascension at the image centre, then go through the same display
        transform as the image so they stay correct under rotation and flips.

        The result goes to the panner, which is where DS9 draws its compass,
        and -- only while `WCS -> Show Direction Arrows` is ticked -- over the
        image as well. NCRADS9 used to draw them over the image alone, on top
        of the data; that is now off by default (M3-9).
        """
        vectors = self._compass_vectors()
        if vectors is None:
            self._publish_compass(None, None, False)
            return
        self._publish_compass(*vectors, True)

    def _compass_vectors(self) -> tuple[tuple[float, float], tuple[float, float]] | None:
        """North and east as display-space vectors, or None if unavailable."""
        data = self.window.image_data
        if self.window._tile_mode_enabled or not self._has_wcs or data is None:
            return None

        handler = self.window.wcs_handler
        height, width = data.shape[:2]
        cx = (width - 1) / 2.0
        cy = (height - 1) / 2.0

        ra, dec = handler.pixel_to_world(cx, cy)
        center = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=ICRS())
        north = center.directional_offset_by(0.0 * u.deg, ARROW_SEPARATION)
        east = center.directional_offset_by(90.0 * u.deg, ARROW_SEPARATION)
        nx, ny = handler.world_to_pixel(north.ra.deg, north.dec.deg)
        ex, ey = handler.world_to_pixel(east.ra.deg, east.dec.deg)

        frame = self.frame
        transform = DisplayTransform(
            width=width,
            height=height,
            rotation=frame.rotation if frame is not None else 0.0,
            flip_x=frame.flip_x if frame is not None else False,
            flip_y=frame.flip_y if frame is not None else False,
        )
        return (
            transform.source_vector_to_display(float(nx - cx), float(ny - cy)),
            transform.source_vector_to_display(float(ex - cx), float(ey - cy)),
        )

    def _publish_compass(
        self,
        north: tuple[float, float] | None,
        east: tuple[float, float] | None,
        valid: bool,
    ) -> None:
        """Send the compass to the panner, and to the image if asked for."""
        panner = getattr(self.window, "panner_panel", None)
        if panner is not None:
            panner.set_compass(north, east, valid)
        if hasattr(self.viewer, "set_direction_arrows"):
            on_image = valid and self.window._show_direction_arrows
            self.viewer.set_direction_arrows(north, east, on_image)
