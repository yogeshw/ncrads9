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

"""GridConfig class for grid configuration.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, Any


@dataclass
class GridConfig:
    """Configuration settings for WCS grid display."""

    # Grid visibility
    visible: bool = True
    show_labels: bool = True

    # Grid line appearance
    line_color: Tuple[int, int, int] = (128, 128, 128)
    line_width: float = 1.0
    line_style: str = "solid"  # solid, dashed, dotted

    # Label appearance
    label_color: Tuple[int, int, int] = (255, 255, 255)
    label_font_size: float = 10.0
    label_font_family: str = "sans-serif"

    # Grid spacing
    auto_spacing: bool = True
    ra_spacing: Optional[float] = None  # degrees
    dec_spacing: Optional[float] = None  # degrees

    # Grid density
    min_grid_lines: int = 3
    max_grid_lines: int = 20

    # Coordinate system
    coordinate_system: str = "fk5"  # fk5, galactic, ecliptic

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation of the configuration.
        """
        return {
            "visible": self.visible,
            "show_labels": self.show_labels,
            "line_color": self.line_color,
            "line_width": self.line_width,
            "line_style": self.line_style,
            "label_color": self.label_color,
            "label_font_size": self.label_font_size,
            "label_font_family": self.label_font_family,
            "auto_spacing": self.auto_spacing,
            "ra_spacing": self.ra_spacing,
            "dec_spacing": self.dec_spacing,
            "min_grid_lines": self.min_grid_lines,
            "max_grid_lines": self.max_grid_lines,
            "coordinate_system": self.coordinate_system,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GridConfig:
        """Create configuration from dictionary.

        Args:
            data: Dictionary with configuration values.

        Returns:
            GridConfig instance.
        """
        return cls(
            visible=data.get("visible", True),
            show_labels=data.get("show_labels", True),
            line_color=tuple(data.get("line_color", (128, 128, 128))),
            line_width=data.get("line_width", 1.0),
            line_style=data.get("line_style", "solid"),
            label_color=tuple(data.get("label_color", (255, 255, 255))),
            label_font_size=data.get("label_font_size", 10.0),
            label_font_family=data.get("label_font_family", "sans-serif"),
            auto_spacing=data.get("auto_spacing", True),
            ra_spacing=data.get("ra_spacing"),
            dec_spacing=data.get("dec_spacing"),
            min_grid_lines=data.get("min_grid_lines", 3),
            max_grid_lines=data.get("max_grid_lines", 20),
            coordinate_system=data.get("coordinate_system", "fk5"),
        )

    def copy(self) -> GridConfig:
        """Create a copy of this configuration.

        Returns:
            New GridConfig instance with same values.
        """
        return GridConfig.from_dict(self.to_dict())
