# ncrads9 - NCRA DS9 Analysis Package
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
Pixel table for examining pixel values in astronomical images.

Author: Yogesh Wadadekar
"""

from typing import Optional, Tuple, List, Dict, Any
import numpy as np
from numpy.typing import NDArray


class PixelTable:
    """
    Class for examining and displaying pixel values.

    Parameters
    ----------
    data : NDArray
        Input 2D image data.
    wcs : object, optional
        WCS object for coordinate transformation.

    Attributes
    ----------
    data : NDArray
        The image data.
    shape : tuple
        Shape of the image (ny, nx).
    """

    def __init__(
        self,
        data: NDArray[np.floating],
        wcs: Optional[Any] = None,
    ) -> None:
        self.data = data
        self.wcs = wcs
        self.shape: Tuple[int, int] = data.shape

    def get_pixel(
        self,
        x: int,
        y: int,
    ) -> float:
        """
        Get the value at a single pixel.

        Parameters
        ----------
        x : int
            X coordinate (column).
        y : int
            Y coordinate (row).

        Returns
        -------
        float
            Pixel value.

        Raises
        ------
        IndexError
            If coordinates are out of bounds.
        """
        if not (0 <= x < self.shape[1] and 0 <= y < self.shape[0]):
            raise IndexError(f"Coordinates ({x}, {y}) out of bounds for shape {self.shape}")
        return float(self.data[y, x])

    def get_region(
        self,
        x_center: int,
        y_center: int,
        size: int = 5,
    ) -> NDArray[np.floating]:
        """
        Get pixel values in a square region.

        Parameters
        ----------
        x_center : int
            X coordinate of center.
        y_center : int
            Y coordinate of center.
        size : int, default 5
            Size of the region (must be odd).

        Returns
        -------
        NDArray
            2D array of pixel values.
        """
        half = size // 2
        y_min = max(0, y_center - half)
        y_max = min(self.shape[0], y_center + half + 1)
        x_min = max(0, x_center - half)
        x_max = min(self.shape[1], x_center + half + 1)

        return self.data[y_min:y_max, x_min:x_max].copy()

    def get_row(
        self,
        y: int,
        x_start: Optional[int] = None,
        x_end: Optional[int] = None,
    ) -> NDArray[np.floating]:
        """
        Get pixel values along a row.

        Parameters
        ----------
        y : int
            Row index.
        x_start : int, optional
            Starting column.
        x_end : int, optional
            Ending column.

        Returns
        -------
        NDArray
            1D array of pixel values.
        """
        if x_start is None:
            x_start = 0
        if x_end is None:
            x_end = self.shape[1]
        return self.data[y, x_start:x_end].copy()

    def get_column(
        self,
        x: int,
        y_start: Optional[int] = None,
        y_end: Optional[int] = None,
    ) -> NDArray[np.floating]:
        """
        Get pixel values along a column.

        Parameters
        ----------
        x : int
            Column index.
        y_start : int, optional
            Starting row.
        y_end : int, optional
            Ending row.

        Returns
        -------
        NDArray
            1D array of pixel values.
        """
        if y_start is None:
            y_start = 0
        if y_end is None:
            y_end = self.shape[0]
        return self.data[y_start:y_end, x].copy()

    def format_table(
        self,
        x_center: int,
        y_center: int,
        size: int = 5,
        precision: int = 4,
    ) -> str:
        """
        Format pixel values as a text table.

        Parameters
        ----------
        x_center : int
            X coordinate of center.
        y_center : int
            Y coordinate of center.
        size : int, default 5
            Size of the region.
        precision : int, default 4
            Decimal precision for values.

        Returns
        -------
        str
            Formatted text table.
        """
        region = self.get_region(x_center, y_center, size)
        half = size // 2

        y_min = max(0, y_center - half)
        x_min = max(0, x_center - half)

        lines = []
        header = "     " + " ".join(
            f"{x_min + i:>{precision + 6}}" for i in range(region.shape[1])
        )
        lines.append(header)
        lines.append("-" * len(header))

        for j in range(region.shape[0]):
            y_coord = y_min + j
            row_values = " ".join(
                f"{val:>{precision + 6}.{precision}g}" for val in region[j]
            )
            lines.append(f"{y_coord:4d} {row_values}")

        return "\n".join(lines)

    def to_dict(
        self,
        x_center: int,
        y_center: int,
        size: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Convert pixel region to list of dictionaries.

        Parameters
        ----------
        x_center : int
            X coordinate of center.
        y_center : int
            Y coordinate of center.
        size : int, default 5
            Size of the region.

        Returns
        -------
        list of dict
            List of dicts with 'x', 'y', 'value' keys.
        """
        region = self.get_region(x_center, y_center, size)
        half = size // 2

        y_min = max(0, y_center - half)
        x_min = max(0, x_center - half)

        result = []
        for j in range(region.shape[0]):
            for i in range(region.shape[1]):
                result.append({
                    "x": x_min + i,
                    "y": y_min + j,
                    "value": float(region[j, i]),
                })
        return result

    def find_extrema(
        self,
        x_center: int,
        y_center: int,
        size: int = 5,
    ) -> Dict[str, Any]:
        """
        Find min and max values in a region.

        Parameters
        ----------
        x_center : int
            X coordinate of center.
        y_center : int
            Y coordinate of center.
        size : int, default 5
            Size of the region.

        Returns
        -------
        dict
            Dictionary with min/max values and coordinates.
        """
        region = self.get_region(x_center, y_center, size)
        half = size // 2

        y_min = max(0, y_center - half)
        x_min = max(0, x_center - half)

        min_idx = np.unravel_index(np.nanargmin(region), region.shape)
        max_idx = np.unravel_index(np.nanargmax(region), region.shape)

        return {
            "min_value": float(region[min_idx]),
            "min_x": x_min + min_idx[1],
            "min_y": y_min + min_idx[0],
            "max_value": float(region[max_idx]),
            "max_x": x_min + max_idx[1],
            "max_y": y_min + max_idx[0],
        }

    def pixel_to_world(
        self,
        x: int,
        y: int,
    ) -> Optional[Tuple[float, float]]:
        """
        Convert pixel coordinates to world coordinates.

        Parameters
        ----------
        x : int
            X pixel coordinate.
        y : int
            Y pixel coordinate.

        Returns
        -------
        tuple or None
            (ra, dec) in degrees if WCS is available, else None.
        """
        if self.wcs is None:
            return None
        try:
            coords = self.wcs.pixel_to_world(x, y)
            return (float(coords.ra.deg), float(coords.dec.deg))
        except Exception:
            return None

    def sample_line(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        num_points: Optional[int] = None,
    ) -> Tuple[NDArray[np.floating], NDArray[np.floating]]:
        """
        Sample pixel values along a line.

        Parameters
        ----------
        x1, y1 : int
            Start point coordinates.
        x2, y2 : int
            End point coordinates.
        num_points : int, optional
            Number of sample points. If None, uses line length.

        Returns
        -------
        tuple
            (distances, values) arrays.
        """
        length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if num_points is None:
            num_points = int(np.ceil(length))

        x_coords = np.linspace(x1, x2, num_points)
        y_coords = np.linspace(y1, y2, num_points)

        distances = np.sqrt((x_coords - x1) ** 2 + (y_coords - y1) ** 2)

        from scipy import ndimage
        values = ndimage.map_coordinates(
            self.data, [y_coords, x_coords], order=1, mode="constant", cval=np.nan
        )

        return distances, values
