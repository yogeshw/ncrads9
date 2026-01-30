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
Raw array file reader for NCRADS9.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
from numpy.typing import DTypeLike, NDArray


class ArrayReader:
    """Reader for raw binary array files."""

    def __init__(self, filepath: Union[str, Path]) -> None:
        """
        Initialize array reader.

        Args:
            filepath: Path to the raw array file.
        """
        self.filepath = Path(filepath)

    def read(
        self,
        dtype: DTypeLike = np.float32,
        shape: Optional[tuple[int, ...]] = None,
        offset: int = 0,
        order: str = "C",
    ) -> NDArray[Any]:
        """
        Read raw binary array data.

        Args:
            dtype: Data type of the array elements.
            shape: Shape of the array. If None, returns 1D array.
            offset: Byte offset from start of file.
            order: Array memory order ('C' or 'F').

        Returns:
            Numpy array with the data.
        """
        data = np.fromfile(self.filepath, dtype=dtype, offset=offset)

        if shape is not None:
            data = data.reshape(shape, order=order)

        return data

    def read_memmap(
        self,
        dtype: DTypeLike = np.float32,
        shape: Optional[tuple[int, ...]] = None,
        offset: int = 0,
        mode: str = "r",
    ) -> NDArray[Any]:
        """
        Read array as memory-mapped file.

        Args:
            dtype: Data type of the array elements.
            shape: Shape of the array.
            offset: Byte offset from start of file.
            mode: Memory map mode ('r', 'r+', 'w+', 'c').

        Returns:
            Memory-mapped numpy array.
        """
        return np.memmap(
            self.filepath,
            dtype=dtype,
            mode=mode,
            offset=offset,
            shape=shape,
        )
