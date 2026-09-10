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
Epanda region shape: a panda with elliptical annuli.

DS9's `epanda x y startangle stopangle nangle innerMajor innerMinor
outerMajor outerMinor nradius [angle]` -- a pie sliced into `nangle` wedges
crossed with `nradius` elliptical annuli. Its plain cousin `panda` uses circles;
this uses ellipsees, so each ring has two radii and the whole shape may be
rotated.

DS9 requires the inner and outer ellipsees to have the same axis ratio, and
says so in `ds9/doc/ref/region.html`: "the ratio of innerMajor/innerMinor and
outerMajor/outerMinor must be the same". That is not enforced here -- DS9
itself accepts a file that breaks it and simply draws what it is given, and
refusing a file DS9 would open is worse than drawing an odd shape.

Author: Yogesh Wadadekar
"""

import math
from typing import Any

from ..base_region import BaseRegion


def _within_span(angle: float, start: float, stop: float) -> bool:
    """Whether an angle falls in a span, which may wrap past 360 degrees."""
    if abs(stop - start) >= 360.0:
        return True
    angle %= 360.0
    start %= 360.0
    stop %= 360.0
    if start <= stop:
        return start <= angle <= stop
    return angle >= start or angle <= stop


class Epanda(BaseRegion):
    """A panda whose annuli are ellipticales."""

    def __init__(
        self,
        center: tuple[float, float],
        start_angle: float,
        stop_angle: float,
        num_angles: int,
        inner_major: float,
        inner_minor: float,
        outer_major: float,
        outer_minor: float,
        num_radii: int,
        angle: float = 0.0,
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize a epanda region.

        Args:
            center: The (x, y) center coordinates.
            start_angle: The first wedge's starting angle, in degrees.
            stop_angle: The last wedge's stopping angle, in degrees.
            num_angles: How many wedges the pie is cut into.
            inner_major: The inner ellipse's semi-major axis.
            inner_minor: The inner ellipse's semi-minor axis.
            outer_major: The outer ellipse's semi-major axis.
            outer_minor: The outer ellipse's semi-minor axis.
            num_radii: How many annuli lie between inner and outer.
            angle: The whole shape's rotation, in degrees.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
        """
        super().__init__(center, color, width, font, text, tags, **kwargs)
        self._start_angle = float(start_angle)
        self._stop_angle = float(stop_angle)
        self._num_angles = int(num_angles)
        self._inner_major = float(inner_major)
        self._inner_minor = float(inner_minor)
        self._outer_major = float(outer_major)
        self._outer_minor = float(outer_minor)
        self._num_radii = int(num_radii)
        self._angle = float(angle)

    @property
    def start_angle(self) -> float:
        """The first wedge's starting angle, in degrees."""
        return self._start_angle

    @start_angle.setter
    def start_angle(self, value: float) -> None:
        self._start_angle = float(value)

    @property
    def stop_angle(self) -> float:
        """The last wedge's stopping angle, in degrees."""
        return self._stop_angle

    @stop_angle.setter
    def stop_angle(self, value: float) -> None:
        self._stop_angle = float(value)

    @property
    def num_angles(self) -> int:
        """How many wedges the pie is cut into."""
        return self._num_angles

    @num_angles.setter
    def num_angles(self, value: int) -> None:
        self._num_angles = int(value)

    @property
    def inner_major(self) -> float:
        """The inner ellipse's semi-major axis."""
        return self._inner_major

    @inner_major.setter
    def inner_major(self, value: float) -> None:
        self._inner_major = float(value)

    @property
    def inner_minor(self) -> float:
        """The inner ellipse's semi-minor axis."""
        return self._inner_minor

    @inner_minor.setter
    def inner_minor(self, value: float) -> None:
        self._inner_minor = float(value)

    @property
    def outer_major(self) -> float:
        """The outer ellipse's semi-major axis."""
        return self._outer_major

    @outer_major.setter
    def outer_major(self, value: float) -> None:
        self._outer_major = float(value)

    @property
    def outer_minor(self) -> float:
        """The outer ellipse's semi-minor axis."""
        return self._outer_minor

    @outer_minor.setter
    def outer_minor(self, value: float) -> None:
        self._outer_minor = float(value)

    @property
    def num_radii(self) -> int:
        """How many annuli lie between inner and outer."""
        return self._num_radii

    @num_radii.setter
    def num_radii(self, value: int) -> None:
        self._num_radii = int(value)

    @property
    def angle(self) -> float:
        """The whole shape's rotation, in degrees."""
        return self._angle

    @angle.setter
    def angle(self, value: float) -> None:
        self._angle = float(value)

    def draw(self, context: Any) -> None:
        """
        Draw the epanda on the given context.

        Args:
            context: The drawing context.
        """

    def contains(self, x: float, y: float) -> bool:
        """
        Whether a point lies in one of the epanda's wedges.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is between the inner and outer ellipsees and
            within the angular span.
        """
        cx, cy = self.center
        radians = math.radians(-self._angle)
        dx, dy = x - cx, y - cy
        local_x = dx * math.cos(radians) - dy * math.sin(radians)
        local_y = dx * math.sin(radians) + dy * math.cos(radians)

        # Inside the outer ellipse and outside the inner one, in the
        # shape's own rotated frame.
        outer = (local_x / self._outer_major) ** 2 + (local_y / self._outer_minor) ** 2
        inner = (
            (local_x / self._inner_major) ** 2 + (local_y / self._inner_minor) ** 2
            if self._inner_major > 0 and self._inner_minor > 0
            else float("inf")
        )
        if outer > 1.0 or inner < 1.0:
            return False

        return _within_span(
            math.degrees(math.atan2(local_y, local_x)),
            self._start_angle,
            self._stop_angle,
        )

    def move(self, dx: float, dy: float) -> None:
        """
        Move the epanda by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the epanda by the given scale factors.

        Args:
            scale_x: The scale factor along the major axis.
            scale_y: The scale factor along the minor axis.
        """
        self._inner_major *= scale_x
        self._outer_major *= scale_x
        self._inner_minor *= scale_y
        self._outer_minor *= scale_y

    def to_ds9_string(self) -> str:
        """
        Convert the epanda to a DS9 format string.

        Returns:
            The epanda as a DS9 format string.
        """
        cx, cy = self.center
        return (
            f"epanda({cx:g},{cy:g},{self._start_angle:g},{self._stop_angle:g},"
            f"{self._num_angles:d},{self._inner_major:g},{self._inner_minor:g},"
            f"{self._outer_major:g},{self._outer_minor:g},{self._num_radii:d},"
            f"{self._angle:g})"
        )

    def __repr__(self) -> str:
        """Return a string representation of the epanda."""
        return (
            f"Epanda(center={self.center}, angles=({self._start_angle},"
            f"{self._stop_angle}), major=({self._inner_major},{self._outer_major}))"
        )
