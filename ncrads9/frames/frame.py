# NCRA DS9 - Astronomical Image Viewer
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
#
# Author: Yogesh Wadadekar

"""Frame class representing a single image frame."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray


@dataclass
class FrameSettings:
    """Settings for a frame."""

    colormap: str = "gray"
    scale: str = "linear"
    scale_min: Optional[float] = None
    scale_max: Optional[float] = None
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    rotation: float = 0.0
    flip_x: bool = False
    flip_y: bool = False


@dataclass
class Region:
    """A region annotation on a frame."""

    shape: str
    coordinates: list[float]
    color: str = "green"
    width: int = 1
    text: str = ""
    properties: dict[str, Any] = field(default_factory=dict)


class Frame:
    """Represents a single image frame with image data, regions, and settings."""

    def __init__(
        self,
        frame_id: int,
        name: str = "",
        image_data: Optional[NDArray[np.floating[Any]]] = None,
    ) -> None:
        """Initialize a Frame.

        Args:
            frame_id: Unique identifier for the frame.
            name: Display name for the frame.
            image_data: Optional numpy array containing image data.
        """
        self._frame_id = frame_id
        self._name = name or f"Frame {frame_id}"
        self._image_data = image_data
        self._settings = FrameSettings()
        self._regions: list[Region] = []
        self._header: dict[str, Any] = {}
        self._wcs: Optional[Any] = None
        self._modified: bool = False

    @property
    def frame_id(self) -> int:
        """Return the frame ID."""
        return self._frame_id

    @property
    def name(self) -> str:
        """Return the frame name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set the frame name."""
        self._name = value

    @property
    def image_data(self) -> Optional[NDArray[np.floating[Any]]]:
        """Return the image data."""
        return self._image_data

    @image_data.setter
    def image_data(self, value: Optional[NDArray[np.floating[Any]]]) -> None:
        """Set the image data."""
        self._image_data = value
        self._modified = True

    @property
    def settings(self) -> FrameSettings:
        """Return the frame settings."""
        return self._settings

    @property
    def regions(self) -> list[Region]:
        """Return the list of regions."""
        return self._regions

    @property
    def header(self) -> dict[str, Any]:
        """Return the FITS header."""
        return self._header

    @header.setter
    def header(self, value: dict[str, Any]) -> None:
        """Set the FITS header."""
        self._header = value

    @property
    def wcs(self) -> Optional[Any]:
        """Return the WCS object."""
        return self._wcs

    @wcs.setter
    def wcs(self, value: Any) -> None:
        """Set the WCS object."""
        self._wcs = value

    @property
    def shape(self) -> Optional[tuple[int, ...]]:
        """Return the shape of the image data."""
        if self._image_data is not None:
            return self._image_data.shape
        return None

    @property
    def is_modified(self) -> bool:
        """Return whether the frame has been modified."""
        return self._modified

    def add_region(self, region: Region) -> None:
        """Add a region to the frame.

        Args:
            region: The region to add.
        """
        self._regions.append(region)
        self._modified = True

    def remove_region(self, index: int) -> None:
        """Remove a region by index.

        Args:
            index: Index of the region to remove.
        """
        if 0 <= index < len(self._regions):
            del self._regions[index]
            self._modified = True

    def clear_regions(self) -> None:
        """Remove all regions from the frame."""
        self._regions.clear()
        self._modified = True

    def clear(self) -> None:
        """Clear the frame data and reset settings."""
        self._image_data = None
        self._header = {}
        self._wcs = None
        self._regions.clear()
        self._settings = FrameSettings()
        self._modified = False

    def copy_settings_from(self, other: Frame) -> None:
        """Copy settings from another frame.

        Args:
            other: The frame to copy settings from.
        """
        self._settings = FrameSettings(
            colormap=other.settings.colormap,
            scale=other.settings.scale,
            scale_min=other.settings.scale_min,
            scale_max=other.settings.scale_max,
            zoom=other.settings.zoom,
            pan_x=other.settings.pan_x,
            pan_y=other.settings.pan_y,
            rotation=other.settings.rotation,
            flip_x=other.settings.flip_x,
            flip_y=other.settings.flip_y,
        )

    def mark_saved(self) -> None:
        """Mark the frame as saved (not modified)."""
        self._modified = False
