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
Animated GIF writer for NCRADS9.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Any, Sequence, Union

import numpy as np
from numpy.typing import NDArray
from PIL import Image


class GIFWriter:
    """Writer for animated GIF files."""

    def __init__(self, filepath: Union[str, Path]) -> None:
        """
        Initialize GIF writer.

        Args:
            filepath: Path for the output GIF file.
        """
        self.filepath = Path(filepath)
        self._frames: list[Image.Image] = []

    def add_frame(
        self,
        data: NDArray[Any],
        normalize: bool = True,
    ) -> None:
        """
        Add a frame to the animation.

        Args:
            data: Image data as numpy array.
            normalize: Whether to normalize data to 0-255 range.
        """
        if normalize:
            data = self._normalize(data)

        if data.ndim == 2:
            mode = "L"
        elif data.ndim == 3 and data.shape[2] == 3:
            mode = "RGB"
        elif data.ndim == 3 and data.shape[2] == 4:
            mode = "RGBA"
        else:
            raise ValueError(f"Unsupported array shape: {data.shape}")

        frame = Image.fromarray(data.astype(np.uint8), mode=mode)
        self._frames.append(frame)

    def add_frames(
        self,
        frames: Sequence[NDArray[Any]],
        normalize: bool = True,
    ) -> None:
        """
        Add multiple frames at once.

        Args:
            frames: Sequence of image arrays.
            normalize: Whether to normalize data.
        """
        for frame in frames:
            self.add_frame(frame, normalize=normalize)

    def write(
        self,
        duration: int = 100,
        loop: int = 0,
        optimize: bool = True,
    ) -> None:
        """
        Write the animated GIF to disk.

        Args:
            duration: Frame duration in milliseconds.
            loop: Number of loops (0 = infinite).
            optimize: Whether to optimize the GIF.
        """
        if not self._frames:
            raise ValueError("No frames to write")

        self._frames[0].save(
            self.filepath,
            save_all=True,
            append_images=self._frames[1:],
            duration=duration,
            loop=loop,
            optimize=optimize,
        )

    def clear(self) -> None:
        """Clear all frames."""
        self._frames.clear()

    def _normalize(self, data: NDArray[Any]) -> NDArray[Any]:
        """Normalize data to 0-255 range."""
        data = np.asarray(data, dtype=np.float64)
        data_min = np.nanmin(data)
        data_max = np.nanmax(data)
        if data_max > data_min:
            data = (data - data_min) / (data_max - data_min) * 255
        return data
