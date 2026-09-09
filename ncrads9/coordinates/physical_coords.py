# NCRADS9 - NCRA DS9 Visualization Tool
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
Physical coordinate system.

Author: Yogesh Wadadekar
"""

from dataclasses import dataclass
from typing import Any

from .coord_system import CoordSystem, CoordSystemType


class PhysicalCoords(CoordSystem):
    """Coordinate system for physical coordinates (detector coordinates)."""

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        """
        Initialize physical coordinates.

        Args:
            x: The x physical coordinate.
            y: The y physical coordinate.
        """
        super().__init__(CoordSystemType.PHYSICAL)
        self._x = x
        self._y = y

    @property
    def x(self) -> float:
        """Return the x physical coordinate."""
        return self._x

    @x.setter
    def x(self, value: float) -> None:
        """Set the x physical coordinate."""
        self._x = value

    @property
    def y(self) -> float:
        """Return the y physical coordinate."""
        return self._y

    @y.setter
    def y(self, value: float) -> None:
        """Set the y physical coordinate."""
        self._y = value

    def get_coordinates(self) -> tuple[float, float]:
        """
        Get the physical coordinates as a tuple.

        Returns:
            A tuple of (x, y) physical coordinates.
        """
        return (self._x, self._y)

    def set_coordinates(self, x: float, y: float) -> None:
        """
        Set the physical coordinates.

        Args:
            x: The x physical coordinate.
            y: The y physical coordinate.
        """
        self._x = x
        self._y = y

    def to_string(self, precision: int | None = None) -> str:
        """
        Convert physical coordinates to a string representation.

        Args:
            precision: Optional decimal precision for formatting.

        Returns:
            String representation of the physical coordinates.
        """
        if precision is not None:
            return f"{self._x:.{precision}f}, {self._y:.{precision}f}"
        return f"{self._x}, {self._y}"


@dataclass(frozen=True)
class PhysicalTransform:
    """The image <-> physical mapping carried in a FITS header.

    IRAF records the relationship between a trimmed/binned image and the
    original detector readout in the ``LTV1``, ``LTV2``, ``LTM1_1`` and
    ``LTM2_2`` keywords, which DS9 reads to offer its Physical coordinate
    system. The mapping is

        image = LTM * physical + LTV

    so going the other way is

        physical = (image - LTV) / LTM

    Only the diagonal terms are used: the off-diagonal ``LTM1_2``/``LTM2_1``
    are zero for every instrument that writes these keywords, and DS9 ignores
    them too.

    An image with no LTV/LTM keywords gets the identity, which makes physical
    coordinates equal image coordinates -- again matching DS9.
    """

    ltv1: float = 0.0
    ltv2: float = 0.0
    ltm1: float = 1.0
    ltm2: float = 1.0

    @classmethod
    def from_header(cls, header: Any) -> "PhysicalTransform":
        """Read the transform from a FITS header, or any mapping.

        Args:
            header: An ``astropy.io.fits.Header`` or plain dict.

        Returns:
            The transform. A zero or missing LTM scale falls back to 1.0,
            since a zero scale would make the inverse undefined.
        """

        def value(key: str, default: float) -> float:
            try:
                raw = header.get(key, default) if header is not None else default
            except AttributeError:
                return default
            try:
                number = float(raw)
            except (TypeError, ValueError):
                return default
            return number

        ltm1 = value("LTM1_1", 1.0) or 1.0
        ltm2 = value("LTM2_2", 1.0) or 1.0
        return cls(ltv1=value("LTV1", 0.0), ltv2=value("LTV2", 0.0), ltm1=ltm1, ltm2=ltm2)

    @property
    def is_identity(self) -> bool:
        """True when physical coordinates are the same as image coordinates."""
        return (self.ltv1, self.ltv2, self.ltm1, self.ltm2) == (0.0, 0.0, 1.0, 1.0)

    def image_to_physical(self, x: float, y: float) -> tuple[float, float]:
        """Convert image coordinates to physical (detector) coordinates."""
        return ((x - self.ltv1) / self.ltm1, (y - self.ltv2) / self.ltm2)

    def physical_to_image(self, x: float, y: float) -> tuple[float, float]:
        """Convert physical (detector) coordinates to image coordinates."""
        return (x * self.ltm1 + self.ltv1, y * self.ltm2 + self.ltv2)
