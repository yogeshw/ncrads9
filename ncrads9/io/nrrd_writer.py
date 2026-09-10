# NCRADS9 - NCRA DS9-like FITS Viewer
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
NRRD out: a short text header, then the pixels.

DS9's Export -> NRRD (`export.tcl:23`). Detached headers and the other
encodings NRRD allows are not written -- one file with raw pixels is what
DS9 writes and what `nrrd_reader.py` reads back.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import gzip
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

#: numpy type -> what NRRD calls it. The reader's map, inverted.
NRRD_TYPES: dict[str, str] = {
    "int8": "int8",
    "uint8": "uint8",
    "int16": "int16",
    "uint16": "uint16",
    "int32": "int32",
    "uint32": "uint32",
    "int64": "int64",
    "uint64": "uint64",
    "float32": "float",
    "float64": "double",
}


def write(
    path: str | Path,
    data: NDArray[Any],
    big_endian: bool = True,
    compress: bool = False,
) -> Path:
    """Write an array as a NRRD file.

    Args:
        path: The file to write.
        data: The pixels.
        big_endian: Whether to write big-endian, as DS9's export dialog
            asks; NRRD records which in its header either way.
        compress: Whether to gzip the pixels, which NRRD calls that
            encoding.

    Returns:
        The path written.

    Raises:
        ValueError: If the array's type has no NRRD equivalent.
        OSError: If the file cannot be written.
    """
    array = np.asarray(data)
    name = array.dtype.newbyteorder("=").name
    if name not in NRRD_TYPES:
        # float16 and the like: written as the float NRRD does have rather
        # than refused.
        array = array.astype(np.float32)
        name = "float32"

    order = ">" if big_endian else "<"
    payload = array.astype(np.dtype(order + array.dtype.str[1:])).tobytes()
    if compress:
        payload = gzip.compress(payload)

    # NRRD quotes sizes fastest-axis-first, which is numpy's reversed.
    sizes = " ".join(str(length) for length in reversed(array.shape))
    header = "\n".join(
        [
            "NRRD0004",
            "# Written by NCRADS9",
            f"type: {NRRD_TYPES[name]}",
            f"dimension: {array.ndim}",
            f"sizes: {sizes}",
            f"endian: {'big' if big_endian else 'little'}",
            f"encoding: {'gzip' if compress else 'raw'}",
            "",
            "",
        ]
    )

    target = Path(path)
    with open(target, "wb") as handle:
        handle.write(header.encode("ascii"))
        handle.write(payload)
    return target
