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
Base coordinate system classes and types.

Author: Yogesh Wadadekar
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from enum import Enum, auto

from .sexagesimal import degrees_to_dms, degrees_to_hms


class CoordSystemType(Enum):
    """Enumeration of coordinate system types."""

    IMAGE = auto()
    PHYSICAL = auto()
    WCS = auto()


class CoordSystem(ABC):
    """Abstract base class for coordinate systems."""

    def __init__(self, coord_type: CoordSystemType) -> None:
        """
        Initialize the coordinate system.

        Args:
            coord_type: The type of coordinate system.
        """
        self._coord_type = coord_type

    @property
    def coord_type(self) -> CoordSystemType:
        """Return the coordinate system type."""
        return self._coord_type

    @abstractmethod
    def get_coordinates(self) -> tuple[float, float]:
        """
        Get the coordinates as a tuple.

        Returns:
            A tuple of (x, y) or (ra, dec) coordinates.
        """

    @abstractmethod
    def set_coordinates(self, x: float, y: float) -> None:
        """
        Set the coordinates.

        Args:
            x: The x or RA coordinate.
            y: The y or Dec coordinate.
        """

    @abstractmethod
    def to_string(self, precision: int | None = None) -> str:
        """
        Convert coordinates to a string representation.

        Args:
            precision: Optional decimal precision for formatting.

        Returns:
            String representation of the coordinates.
        """

    def __repr__(self) -> str:
        """Return string representation of the coordinate system."""
        return f"{self.__class__.__name__}({self.to_string()})"


class CoordFrame(Enum):
    """DS9's coordinate *system*: WCS, or one of the pixel systems.

    DS9's WCS menu offers `wcs` plus `wcsa`..`wcsz` for files carrying
    alternate WCS solutions, and the four pixel systems. Only `WCS` and `IMAGE`
    are wired up so far; the rest are declared here so the menu, the XPA
    `wcs system` command and the info panel can all name the same values as
    they land (M3, M9-25).
    """

    WCS = "wcs"
    IMAGE = "image"
    PHYSICAL = "physical"
    AMPLIFIER = "amplifier"
    DETECTOR = "detector"


class SkyFrame(Enum):
    """The celestial reference frame WCS coordinates are expressed in."""

    FK4 = "fk4"
    FK5 = "fk5"
    ICRS = "icrs"
    GALACTIC = "galactic"
    ECLIPTIC = "ecliptic"


class SkyFormat(Enum):
    """How a sky coordinate pair is written out."""

    DEGREES = "degrees"
    SEXAGESIMAL = "sexagesimal"


#: Axis labels per sky frame, matching what DS9 shows in its info panel.
_SKY_LABELS: dict[SkyFrame, tuple[str, str]] = {
    SkyFrame.FK4: ("RA", "Dec"),
    SkyFrame.FK5: ("RA", "Dec"),
    SkyFrame.ICRS: ("RA", "Dec"),
    SkyFrame.GALACTIC: ("l", "b"),
    SkyFrame.ECLIPTIC: ("Lon", "Lat"),
}

#: Frames whose longitude is conventionally written in hours, not degrees.
_HOUR_ANGLE_FRAMES = frozenset({SkyFrame.FK4, SkyFrame.FK5, SkyFrame.ICRS})


@dataclass
class CoordinateContext:
    """The user's current coordinate display settings, and how to apply them.

    Every coordinate string the application shows goes through `format_pair`,
    so the info panel, the status bar, region dialogs and XPA replies cannot
    drift apart. Before M1 the frame transform lived in
    `MainWindow._update_wcs_display` and the sexagesimal formatting lived
    separately in `StatusBar.update_wcs_coords`, each with its own rules.

    Attributes:
        frame: Which coordinate system to report positions in.
        sky: The celestial frame used when `frame` is WCS.
        sky_format: Degrees or sexagesimal.
        precision: Fractional digits on the seconds field (sexagesimal) or on
            the degree value (degrees).
    """

    frame: CoordFrame = CoordFrame.WCS
    sky: SkyFrame = SkyFrame.FK5
    sky_format: SkyFormat = SkyFormat.SEXAGESIMAL
    precision: int = 2

    # -- construction from the plain strings the UI and XPA use --------------

    @classmethod
    def from_names(
        cls,
        frame: str = "wcs",
        sky: str = "fk5",
        sky_format: str = "sexagesimal",
        precision: int = 2,
    ) -> "CoordinateContext":
        """Build a context from DS9's lowercase token names."""
        return cls(
            frame=CoordFrame(frame),
            sky=SkyFrame(sky),
            sky_format=SkyFormat(sky_format),
            precision=precision,
        )

    def with_sky(self, sky: str | SkyFrame) -> "CoordinateContext":
        """Return a copy using a different sky frame."""
        return replace(self, sky=SkyFrame(sky) if isinstance(sky, str) else sky)

    def with_format(self, sky_format: str | SkyFormat) -> "CoordinateContext":
        """Return a copy using a different sky format."""
        return replace(
            self,
            sky_format=SkyFormat(sky_format) if isinstance(sky_format, str) else sky_format,
        )

    # -- labels --------------------------------------------------------------

    @property
    def labels(self) -> tuple[str, str]:
        """The two axis labels for the current settings."""
        if self.frame is CoordFrame.WCS:
            return _SKY_LABELS[self.sky]
        return ("X", "Y")

    @property
    def uses_hour_angle(self) -> bool:
        """True when the longitude axis is written in hours."""
        return self.frame is CoordFrame.WCS and self.sky in _HOUR_ANGLE_FRAMES

    # -- transformation ------------------------------------------------------

    def transform(self, ra_deg: float, dec_deg: float) -> tuple[float, float]:
        """Convert ICRS degrees into the current sky frame.

        Args:
            ra_deg: Right ascension in degrees, ICRS.
            dec_deg: Declination in degrees, ICRS.

        Returns:
            (longitude, latitude) in degrees in the configured sky frame.
        """
        # Imported lazily: astropy's coordinate machinery is slow to import,
        # and callers that only format pixel coordinates never need it.
        import astropy.units as u
        from astropy.coordinates import (
            FK4,
            FK5,
            ICRS,
            BarycentricTrueEcliptic,
            Galactic,
            SkyCoord,
        )

        base = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame=ICRS())

        if self.sky is SkyFrame.ICRS:
            return base.ra.deg, base.dec.deg
        if self.sky is SkyFrame.FK5:
            coord = base.transform_to(FK5())
            return coord.ra.deg, coord.dec.deg
        if self.sky is SkyFrame.FK4:
            coord = base.transform_to(FK4())
            return coord.ra.deg, coord.dec.deg
        if self.sky is SkyFrame.GALACTIC:
            coord = base.transform_to(Galactic())
            return coord.l.deg, coord.b.deg
        coord = base.transform_to(BarycentricTrueEcliptic())
        return coord.lon.deg, coord.lat.deg

    # -- formatting ----------------------------------------------------------

    def format_pair(self, lon_deg: float, lat_deg: float) -> tuple[str, str]:
        """Format a coordinate pair, already in the target frame.

        Returns:
            The two formatted values, without their labels.
        """
        if self.sky_format is SkyFormat.DEGREES or self.frame is not CoordFrame.WCS:
            return (
                f"{lon_deg:.{self.precision + 3}f}",
                f"{lat_deg:.{self.precision + 3}f}",
            )

        if self.uses_hour_angle:
            return (
                degrees_to_hms(lon_deg, precision=self.precision),
                degrees_to_dms(lat_deg, precision=max(0, self.precision - 1)),
            )
        return (
            degrees_to_dms(lon_deg, precision=self.precision),
            degrees_to_dms(lat_deg, precision=max(0, self.precision - 1)),
        )

    def format_sky(self, ra_deg: float, dec_deg: float) -> tuple[str, str]:
        """Transform ICRS degrees into the current frame, then format them."""
        return self.format_pair(*self.transform(ra_deg, dec_deg))

    def describe(self, lon_deg: float, lat_deg: float) -> str:
        """Format a pair with its labels, as the info panel shows it."""
        label_x, label_y = self.labels
        value_x, value_y = self.format_pair(lon_deg, lat_deg)
        unit = " deg" if self.sky_format is SkyFormat.DEGREES and self.frame is CoordFrame.WCS else ""
        return f"{label_x}: {value_x}{unit} {label_y}: {value_y}{unit}"

    def describe_sky(self, ra_deg: float, dec_deg: float) -> str:
        """Transform ICRS degrees into the current frame, then describe them."""
        return self.describe(*self.transform(ra_deg, dec_deg))
