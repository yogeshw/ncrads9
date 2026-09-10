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
ENVI out: two files, a text header and the pixels beside it.

DS9's Export -> ENVI asks for both names (`export.tcl:24`), because ENVI
keeps them apart -- which is the one thing about the format a user has to
be told.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

#: numpy type -> ENVI's `data type` code. The reader's map, inverted.
ENVI_TYPES: dict[str, int] = {
    "uint8": 1,
    "int16": 2,
    "int32": 3,
    "float32": 4,
    "float64": 5,
    "uint16": 12,
    "uint32": 13,
    "int64": 14,
    "uint64": 15,
}


def header_path(path: str | Path) -> Path:
    """Where the header goes for a given data file."""
    target = Path(path)
    return target if target.suffix == ".hdr" else target.with_suffix(".hdr")


def write(
    path: str | Path,
    data: NDArray[Any],
    big_endian: bool = True,
    header: str | Path | None = None,
) -> tuple[Path, Path]:
    """Write an array as an ENVI pair.

    Args:
        path: The data file.
        data: The pixels.
        big_endian: Whether to write big-endian; ENVI records which.
        header: Where to put the header, or None for the data file's name
            with `.hdr`.

    Returns:
        (data file, header file).

    Raises:
        OSError: If either file cannot be written.
    """
    array = np.asarray(data)
    name = array.dtype.newbyteorder("=").name
    if name not in ENVI_TYPES:
        array = array.astype(np.float32)
        name = "float32"

    order = ">" if big_endian else "<"
    array.astype(np.dtype(order + array.dtype.str[1:])).tofile(str(path))

    bands = array.shape[0] if array.ndim > 2 else 1
    lines = array.shape[-2] if array.ndim > 1 else 1
    samples = array.shape[-1]
    text = "\n".join(
        [
            "ENVI",
            "description = {Written by NCRADS9}",
            f"samples = {samples}",
            f"lines = {lines}",
            f"bands = {bands}",
            "header offset = 0",
            "file type = ENVI Standard",
            f"data type = {ENVI_TYPES[name]}",
            "interleave = bsq",
            f"byte order = {1 if big_endian else 0}",
            "",
        ]
    )

    target_header = Path(header) if header is not None else header_path(path)
    target_header.write_text(text, encoding="ascii")
    return (Path(path), target_header)
