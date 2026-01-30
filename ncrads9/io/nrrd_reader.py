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
NRRD format reader for NCRADS9.

Author: Yogesh Wadadekar
"""

import gzip
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
from numpy.typing import NDArray


class NRRDReader:
    """Reader for NRRD (Nearly Raw Raster Data) files."""

    DTYPE_MAP: dict[str, np.dtype[Any]] = {
        "int8": np.dtype("int8"),
        "uint8": np.dtype("uint8"),
        "int16": np.dtype("int16"),
        "uint16": np.dtype("uint16"),
        "int32": np.dtype("int32"),
        "uint32": np.dtype("uint32"),
        "int64": np.dtype("int64"),
        "uint64": np.dtype("uint64"),
        "float": np.dtype("float32"),
        "double": np.dtype("float64"),
    }

    def __init__(self, filepath: Union[str, Path]) -> None:
        """
        Initialize NRRD reader.

        Args:
            filepath: Path to the NRRD file.
        """
        self.filepath = Path(filepath)
        self._header: dict[str, Any] = {}
        self._data_offset: int = 0

    def read_header(self) -> dict[str, Any]:
        """
        Parse NRRD header.

        Returns:
            Dictionary of header parameters.
        """
        self._header = {}
        with open(self.filepath, "rb") as f:
            magic = f.readline().decode("ascii").strip()
            if not magic.startswith("NRRD"):
                raise ValueError("Not a valid NRRD file")

            while True:
                line = f.readline().decode("ascii").strip()
                if not line:
                    break
                if ":" in line:
                    key, value = line.split(":", 1)
                    self._header[key.strip().lower()] = value.strip()

            self._data_offset = f.tell()

        return self._header

    def read_data(self) -> NDArray[Any]:
        """
        Read NRRD image data.

        Returns:
            Image data as numpy array.
        """
        if not self._header:
            self.read_header()

        dtype = self._get_dtype()
        sizes = self._get_sizes()
        encoding = self._header.get("encoding", "raw")

        with open(self.filepath, "rb") as f:
            f.seek(self._data_offset)
            raw_data = f.read()

        if encoding == "gzip":
            raw_data = gzip.decompress(raw_data)

        data = np.frombuffer(raw_data, dtype=dtype)
        data = data.reshape(sizes[::-1])

        return data

    def _get_dtype(self) -> np.dtype[Any]:
        """Get numpy dtype from header."""
        type_str = self._header.get("type", "float")
        return self.DTYPE_MAP.get(type_str, np.dtype("float32"))

    def _get_sizes(self) -> tuple[int, ...]:
        """Get array dimensions from header."""
        sizes_str = self._header.get("sizes", "")
        return tuple(int(s) for s in sizes_str.split())

    def get_spacing(self) -> Optional[tuple[float, ...]]:
        """
        Get voxel spacing if available.

        Returns:
            Tuple of spacing values or None.
        """
        if not self._header:
            self.read_header()

        spacings = self._header.get("spacings")
        if spacings:
            return tuple(float(s) for s in spacings.split())
        return None
