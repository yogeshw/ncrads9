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

"""PageSetup class for print configuration.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Dict, Any


class PaperSize(Enum):
    """Standard paper sizes."""

    LETTER = "letter"
    LEGAL = "legal"
    A4 = "a4"
    A3 = "a3"
    A5 = "a5"
    CUSTOM = "custom"


class Orientation(Enum):
    """Page orientation."""

    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


# Paper dimensions in inches (width, height)
PAPER_DIMENSIONS: Dict[PaperSize, Tuple[float, float]] = {
    PaperSize.LETTER: (8.5, 11.0),
    PaperSize.LEGAL: (8.5, 14.0),
    PaperSize.A4: (8.27, 11.69),
    PaperSize.A3: (11.69, 16.54),
    PaperSize.A5: (5.83, 8.27),
}


@dataclass
class PageSetup:
    """Configuration for print page layout."""

    paper_size: PaperSize = PaperSize.LETTER
    orientation: Orientation = Orientation.PORTRAIT
    margin_top: float = 0.5  # inches
    margin_bottom: float = 0.5
    margin_left: float = 0.5
    margin_right: float = 0.5
    custom_width: float = 8.5  # inches, for CUSTOM paper size
    custom_height: float = 11.0

    @property
    def paper_width(self) -> float:
        """Get the paper width in inches."""
        if self.paper_size == PaperSize.CUSTOM:
            width = self.custom_width
        else:
            width, _ = PAPER_DIMENSIONS[self.paper_size]

        if self.orientation == Orientation.LANDSCAPE:
            _, height = PAPER_DIMENSIONS.get(
                self.paper_size, (self.custom_width, self.custom_height)
            )
            return height

        return width

    @property
    def paper_height(self) -> float:
        """Get the paper height in inches."""
        if self.paper_size == PaperSize.CUSTOM:
            height = self.custom_height
        else:
            _, height = PAPER_DIMENSIONS[self.paper_size]

        if self.orientation == Orientation.LANDSCAPE:
            width, _ = PAPER_DIMENSIONS.get(
                self.paper_size, (self.custom_width, self.custom_height)
            )
            return width

        return height

    @property
    def printable_width(self) -> float:
        """Get the printable width in inches."""
        return self.paper_width - self.margin_left - self.margin_right

    @property
    def printable_height(self) -> float:
        """Get the printable height in inches."""
        return self.paper_height - self.margin_top - self.margin_bottom

    @property
    def paper_width_points(self) -> float:
        """Get the paper width in PostScript points."""
        return self.paper_width * 72.0

    @property
    def paper_height_points(self) -> float:
        """Get the paper height in PostScript points."""
        return self.paper_height * 72.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with configuration values.
        """
        return {
            "paper_size": self.paper_size.value,
            "orientation": self.orientation.value,
            "margin_top": self.margin_top,
            "margin_bottom": self.margin_bottom,
            "margin_left": self.margin_left,
            "margin_right": self.margin_right,
            "custom_width": self.custom_width,
            "custom_height": self.custom_height,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PageSetup:
        """Create from dictionary representation.

        Args:
            data: Dictionary with configuration values.

        Returns:
            PageSetup instance.
        """
        return cls(
            paper_size=PaperSize(data.get("paper_size", "letter")),
            orientation=Orientation(data.get("orientation", "portrait")),
            margin_top=data.get("margin_top", 0.5),
            margin_bottom=data.get("margin_bottom", 0.5),
            margin_left=data.get("margin_left", 0.5),
            margin_right=data.get("margin_right", 0.5),
            custom_width=data.get("custom_width", 8.5),
            custom_height=data.get("custom_height", 11.0),
        )

    def copy(self) -> PageSetup:
        """Create a copy of this configuration.

        Returns:
            New PageSetup instance.
        """
        return PageSetup.from_dict(self.to_dict())
