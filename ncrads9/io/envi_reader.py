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
ENVI format reader for NCRADS9.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
from numpy.typing import NDArray


class ENVIReader:
    """Reader for ENVI format hyperspectral image files."""

    DTYPE_MAP: dict[int, np.dtype[Any]] = {
        1: np.dtype("uint8"),
        2: np.dtype("int16"),
        3: np.dtype("int32"),
        4: np.dtype("float32"),
        5: np.dtype("float64"),
        12: np.dtype("uint16"),
        13: np.dtype("uint32"),
        14: np.dtype("int64"),
        15: np.dtype("uint64"),
    }

    def __init__(self, filepath: Union[str, Path]) -> None:
        """
        Initialize ENVI reader.

        Args:
            filepath: Path to the ENVI header file (.hdr).
        """
        self.filepath = Path(filepath)
        self._header: dict[str, Any] = {}

    def read_header(self) -> dict[str, Any]:
        """
        Parse ENVI header file.

        Returns:
            Dictionary of header parameters.
        """
        header_path = self.filepath
        if not header_path.suffix == ".hdr":
            header_path = header_path.with_suffix(".hdr")

        self._header = {}
        with open(header_path, "r") as f:
            content = f.read()

        for line in content.split("\n"):
            line = line.strip()
            if "=" in line:
                key, value = line.split("=", 1)
                self._header[key.strip().lower()] = value.strip()

        return self._header

    def read_data(self) -> NDArray[Any]:
        """
        Read ENVI image data.

        Returns:
            Image data as numpy array.
        """
        if not self._header:
            self.read_header()

        lines = int(self._header.get("lines", 0))
        samples = int(self._header.get("samples", 0))
        bands = int(self._header.get("bands", 1))
        dtype_code = int(self._header.get("data type", 4))
        interleave = self._header.get("interleave", "bsq").lower()

        dtype = self.DTYPE_MAP.get(dtype_code, np.float32)

        data_path = self._get_data_path()
        data = np.fromfile(data_path, dtype=dtype)

        if interleave == "bsq":
            data = data.reshape((bands, lines, samples))
        elif interleave == "bil":
            data = data.reshape((lines, bands, samples))
        elif interleave == "bip":
            data = data.reshape((lines, samples, bands))

        return data

    def _get_data_path(self) -> Path:
        """Get path to the binary data file."""
        for ext in ["", ".raw", ".dat", ".img", ".bin"]:
            data_path = self.filepath.with_suffix(ext)
            if data_path.exists() and data_path.suffix != ".hdr":
                return data_path
        return self.filepath.with_suffix("")

    def get_wavelengths(self) -> Optional[list[float]]:
        """
        Get wavelength information if available.

        Returns:
            List of wavelengths or None.
        """
        if not self._header:
            self.read_header()

        wavelengths = self._header.get("wavelength")
        if wavelengths:
            wavelengths = wavelengths.strip("{}")
            return [float(w.strip()) for w in wavelengths.split(",")]
        return None
