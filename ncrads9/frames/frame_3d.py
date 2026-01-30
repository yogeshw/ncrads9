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

"""Frame3D class for 3D visualization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray

from .frame import Frame


class RenderMethod(Enum):
    """3D rendering methods."""

    MIP = auto()  # Maximum Intensity Projection
    AIP = auto()  # Average Intensity Projection
    VOLUME = auto()  # Volume rendering


class AxisOrientation(Enum):
    """Axis orientations for 3D viewing."""

    XY = auto()
    XZ = auto()
    YZ = auto()


@dataclass
class View3DSettings:
    """Settings for 3D visualization."""

    azimuth: float = 45.0
    elevation: float = 30.0
    distance: float = 1.0
    scale_z: float = 1.0
    render_method: RenderMethod = RenderMethod.MIP
    colormap: str = "viridis"
    opacity: float = 1.0
    show_axes: bool = True
    show_grid: bool = False
    show_colorbar: bool = True


class Frame3D:
    """Frame for 3D visualization of data cubes."""

    def __init__(self, frame_id: int, name: str = "") -> None:
        """Initialize a Frame3D.

        Args:
            frame_id: Unique identifier for the frame.
            name: Display name for the frame.
        """
        self._frame_id = frame_id
        self._name = name or f"3D Frame {frame_id}"
        self._source_frame: Optional[Frame] = None
        self._cube_data: Optional[NDArray[np.floating[Any]]] = None
        self._settings = View3DSettings()
        self._current_slice: int = 0
        self._axis_orientation = AxisOrientation.XY

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
    def source_frame(self) -> Optional[Frame]:
        """Return the source frame."""
        return self._source_frame

    @source_frame.setter
    def source_frame(self, frame: Optional[Frame]) -> None:
        """Set the source frame."""
        self._source_frame = frame
        if frame is not None and frame.image_data is not None:
            if frame.image_data.ndim >= 3:
                self._cube_data = frame.image_data.astype(np.float64)
            else:
                self._cube_data = None
        else:
            self._cube_data = None

    @property
    def cube_data(self) -> Optional[NDArray[np.floating[Any]]]:
        """Return the 3D data cube."""
        return self._cube_data

    @cube_data.setter
    def cube_data(self, data: Optional[NDArray[np.floating[Any]]]) -> None:
        """Set the 3D data cube directly."""
        if data is not None and data.ndim < 3:
            raise ValueError("Data must have at least 3 dimensions")
        self._cube_data = data

    @property
    def settings(self) -> View3DSettings:
        """Return the 3D view settings."""
        return self._settings

    @property
    def current_slice(self) -> int:
        """Return the current slice index."""
        return self._current_slice

    @current_slice.setter
    def current_slice(self, value: int) -> None:
        """Set the current slice index."""
        if self._cube_data is not None:
            max_slice = self._get_slice_count() - 1
            self._current_slice = max(0, min(value, max_slice))
        else:
            self._current_slice = 0

    @property
    def axis_orientation(self) -> AxisOrientation:
        """Return the axis orientation."""
        return self._axis_orientation

    @axis_orientation.setter
    def axis_orientation(self, value: AxisOrientation) -> None:
        """Set the axis orientation."""
        self._axis_orientation = value
        self._current_slice = 0

    @property
    def shape(self) -> Optional[tuple[int, ...]]:
        """Return the shape of the data cube."""
        if self._cube_data is not None:
            return self._cube_data.shape
        return None

    def _get_slice_count(self) -> int:
        """Get the number of slices along the current axis."""
        if self._cube_data is None:
            return 0

        if self._axis_orientation == AxisOrientation.XY:
            return self._cube_data.shape[0]
        elif self._axis_orientation == AxisOrientation.XZ:
            return self._cube_data.shape[1]
        else:  # YZ
            return self._cube_data.shape[2]

    def get_slice(self, index: Optional[int] = None) -> Optional[NDArray[np.floating[Any]]]:
        """Get a 2D slice from the data cube.

        Args:
            index: Slice index. If None, uses current_slice.

        Returns:
            2D array representing the slice, or None.
        """
        if self._cube_data is None:
            return None

        if index is None:
            index = self._current_slice

        if self._axis_orientation == AxisOrientation.XY:
            return self._cube_data[index, :, :]
        elif self._axis_orientation == AxisOrientation.XZ:
            return self._cube_data[:, index, :]
        else:  # YZ
            return self._cube_data[:, :, index]

    def get_projection(
        self, method: Optional[RenderMethod] = None
    ) -> Optional[NDArray[np.floating[Any]]]:
        """Get a 2D projection of the data cube.

        Args:
            method: Projection method. If None, uses settings.render_method.

        Returns:
            2D array representing the projection, or None.
        """
        if self._cube_data is None:
            return None

        if method is None:
            method = self._settings.render_method

        axis = 0
        if self._axis_orientation == AxisOrientation.XZ:
            axis = 1
        elif self._axis_orientation == AxisOrientation.YZ:
            axis = 2

        if method == RenderMethod.MIP:
            return np.nanmax(self._cube_data, axis=axis)
        elif method == RenderMethod.AIP:
            return np.nanmean(self._cube_data, axis=axis)
        else:
            # Volume rendering would require more complex implementation
            return np.nanmax(self._cube_data, axis=axis)

    def next_slice(self) -> int:
        """Move to the next slice.

        Returns:
            The new slice index.
        """
        max_slice = self._get_slice_count() - 1
        if max_slice > 0:
            self._current_slice = (self._current_slice + 1) % (max_slice + 1)
        return self._current_slice

    def previous_slice(self) -> int:
        """Move to the previous slice.

        Returns:
            The new slice index.
        """
        max_slice = self._get_slice_count() - 1
        if max_slice > 0:
            self._current_slice = (self._current_slice - 1) % (max_slice + 1)
        return self._current_slice

    def first_slice(self) -> int:
        """Move to the first slice.

        Returns:
            The new slice index (0).
        """
        self._current_slice = 0
        return self._current_slice

    def last_slice(self) -> int:
        """Move to the last slice.

        Returns:
            The new slice index.
        """
        self._current_slice = max(0, self._get_slice_count() - 1)
        return self._current_slice

    def set_view_angle(self, azimuth: float, elevation: float) -> None:
        """Set the 3D view angle.

        Args:
            azimuth: Azimuth angle in degrees.
            elevation: Elevation angle in degrees.
        """
        self._settings.azimuth = azimuth
        self._settings.elevation = elevation

    def rotate(self, delta_azimuth: float, delta_elevation: float) -> None:
        """Rotate the 3D view.

        Args:
            delta_azimuth: Change in azimuth angle.
            delta_elevation: Change in elevation angle.
        """
        self._settings.azimuth += delta_azimuth
        self._settings.elevation = max(-90, min(90, self._settings.elevation + delta_elevation))

    def zoom(self, factor: float) -> None:
        """Zoom the 3D view.

        Args:
            factor: Zoom factor (>1 to zoom in, <1 to zoom out).
        """
        self._settings.distance *= factor

    def clear(self) -> None:
        """Clear the 3D frame."""
        self._source_frame = None
        self._cube_data = None
        self._current_slice = 0
        self._settings = View3DSettings()
