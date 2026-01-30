# This file is part of ncrads9.
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

"""GridLabels class for coordinate labels on grid.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional, List, Tuple

if TYPE_CHECKING:
    from astropy.wcs import WCS
    from .grid_config import GridConfig


class LabelPosition(Enum):
    """Position of labels relative to the grid."""

    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"


class CoordinateFormat(Enum):
    """Format for coordinate display."""

    DEGREES = "degrees"
    HMS_DMS = "hms_dms"
    SEXAGESIMAL = "sexagesimal"


@dataclass
class Label:
    """Represents a single coordinate label."""

    text: str
    x: float
    y: float
    angle: float = 0.0
    position: LabelPosition = LabelPosition.BOTTOM


class GridLabels:
    """Manages coordinate labels for WCS grid display."""

    def __init__(
        self,
        wcs: Optional[WCS] = None,
        config: Optional[GridConfig] = None,
    ) -> None:
        """Initialize the grid labels manager.

        Args:
            wcs: World Coordinate System object for coordinate transformations.
            config: Grid configuration settings.
        """
        self._wcs: Optional[WCS] = wcs
        self._config: Optional[GridConfig] = config
        self._labels: List[Label] = []
        self._format: CoordinateFormat = CoordinateFormat.HMS_DMS

    @property
    def wcs(self) -> Optional[WCS]:
        """Get the current WCS object."""
        return self._wcs

    @wcs.setter
    def wcs(self, value: WCS) -> None:
        """Set the WCS object."""
        self._wcs = value

    @property
    def format(self) -> CoordinateFormat:
        """Get the current coordinate format."""
        return self._format

    @format.setter
    def format(self, value: CoordinateFormat) -> None:
        """Set the coordinate format."""
        self._format = value

    def compute_labels(
        self,
        image_width: int,
        image_height: int,
    ) -> List[Label]:
        """Compute labels for grid lines.

        Args:
            image_width: Width of the image in pixels.
            image_height: Height of the image in pixels.

        Returns:
            List of Label objects with positions and text.
        """
        self._labels = []
        if self._wcs is None:
            return self._labels

        # TODO: Implement label computation using WCS
        return self._labels

    def format_coordinate(
        self,
        ra: float,
        dec: float,
    ) -> Tuple[str, str]:
        """Format RA/Dec coordinates according to current format.

        Args:
            ra: Right Ascension in degrees.
            dec: Declination in degrees.

        Returns:
            Tuple of formatted (RA, Dec) strings.
        """
        if self._format == CoordinateFormat.DEGREES:
            return f"{ra:.6f}°", f"{dec:.6f}°"
        elif self._format == CoordinateFormat.HMS_DMS:
            # TODO: Implement HMS/DMS conversion
            return f"{ra:.6f}", f"{dec:.6f}"
        else:
            return f"{ra:.6f}", f"{dec:.6f}"

    def render(
        self,
        canvas: object,
        font_size: float = 10.0,
    ) -> None:
        """Render labels on the given canvas.

        Args:
            canvas: Canvas object to render on.
            font_size: Font size for labels.
        """
        # TODO: Implement rendering logic
        pass

    def clear(self) -> None:
        """Clear all computed labels."""
        self._labels = []
