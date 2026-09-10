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
Raw arrays: DS9's `[xdim=...,bitpix=...]` specification, and reading one.

A raw array is a file of pixels and nothing else, so its shape and its
number format have to be given rather than read. DS9 takes them in the
filename, in either of two syntaxes, or from `$DS9_ARRAY`
(`ds9/doc/ref/file.html`, the Array section):

    bar.arr[xdim=512,ydim=512,bitpix=16]
    bar.arr[dim=256,bitpix=-32,skip=4]
    bar.arr[array(r256:4l)]

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import DTypeLike, NDArray

#: DS9's BITPIX values and the numpy types they mean. Negative is floating
#: point, as in FITS.
BITPIX_TYPES: dict[int, str] = {
    8: "u1",
    16: "i2",
    -16: "u2",
    32: "i4",
    64: "i8",
    -32: "f4",
    -64: "f8",
}

#: The one-letter types DS9's `array(...)` syntax uses.
LETTER_TYPES: dict[str, int] = {
    "b": 8,
    "s": 16,
    "u": -16,
    "i": 32,
    "l": 64,
    "r": -32,
    "f": -32,
    "d": -64,
}

#: The environment variable DS9 reads default array parameters from.
ENVIRONMENT_VARIABLE = "DS9_ARRAY"

#: `key=value` inside an array specification.
_KEYWORD = re.compile(r"(\w+)\s*=\s*([^,\]]+)")

#: DS9's compact form: `array(<type><dim>[:<skip>][<endian>])`.
_COMPACT = re.compile(
    r"array\(\s*([a-z])(\d+(?:\.\d+)*)(?::(\d+))?([lb])?\s*\)",
    re.IGNORECASE,
)


class ArraySpecError(ValueError):
    """An array specification that cannot be used, for the reason given."""


@dataclass(frozen=True)
class ArraySpec:
    """How to read a raw array: its shape, its numbers, its header.

    Attributes:
        xdim, ydim, zdim: The dimensions. `zdim` is 1 for an image.
        bitpix: The number format, in FITS's terms.
        skip: How many bytes of header to step over.
        big_endian: Whether the numbers are big-endian, as FITS is.
    """

    xdim: int
    ydim: int
    zdim: int = 1
    bitpix: int = -32
    skip: int = 0
    big_endian: bool = True

    @property
    def dtype(self) -> np.dtype:
        """The numpy type the pixels are in, byte order included."""
        if self.bitpix not in BITPIX_TYPES:
            raise ArraySpecError(f"bitpix {self.bitpix} is not one DS9 supports")
        return np.dtype((">" if self.big_endian else "<") + BITPIX_TYPES[self.bitpix])

    @property
    def shape(self) -> tuple[int, ...]:
        """The array's shape in numpy order, slowest axis first."""
        return (self.zdim, self.ydim, self.xdim) if self.zdim > 1 else (self.ydim, self.xdim)

    @property
    def expected_bytes(self) -> int:
        """How large the file has to be, header included."""
        return self.skip + self.xdim * self.ydim * self.zdim * self.dtype.itemsize


def parse_spec(text: str, defaults: ArraySpec | None = None) -> ArraySpec:
    """Read one of DS9's two array specifications.

    Args:
        text: The specification, with or without its brackets --
            `[xdim=512,ydim=512,bitpix=16]` or `[array(s512)]`.
        defaults: What to fall back on for anything the text leaves out.

    Returns:
        The specification.

    Raises:
        ArraySpecError: If it says nothing about the dimensions, or if what
            it says cannot be read.
    """
    body = text.strip()
    if body.startswith("["):
        body = body[1:]
    if body.endswith("]"):
        body = body[:-1]

    compact = _COMPACT.search(body)
    if compact is not None:
        return _compact_spec(compact, defaults)

    values: dict[str, Any] = {}
    for key, value in _KEYWORD.findall(body):
        key = key.lower()
        raw = value.strip()
        if key in ("dim", "dims"):
            values["xdim"] = values["ydim"] = _integer(raw, key)
        elif key in ("xdim", "ydim", "zdim", "bitpix", "skip"):
            values[key] = _integer(raw, key)
        elif key in ("arch", "endian"):
            values["big_endian"] = not raw.lower().startswith("little")

    return _spec_from(values, defaults)


def _compact_spec(match: re.Match[str], defaults: ArraySpec | None) -> ArraySpec:
    """DS9's `array(r256:4l)` form."""
    letter, dimensions, skip, endian = match.groups()
    if letter.lower() not in LETTER_TYPES:
        raise ArraySpecError(f"array type '{letter}' is not one DS9 supports")

    parts = [int(part) for part in dimensions.split(".")]
    if len(parts) == 1:
        xdim = ydim = parts[0]
        zdim = 1
    elif len(parts) == 2:
        xdim, ydim = parts
        zdim = 1
    else:
        xdim, ydim, zdim = parts[:3]

    return _spec_from(
        {
            "xdim": xdim,
            "ydim": ydim,
            "zdim": zdim,
            "bitpix": LETTER_TYPES[letter.lower()],
            "skip": int(skip) if skip else 0,
            "big_endian": endian.lower() != "l" if endian else True,
        },
        defaults,
    )


def _spec_from(values: dict[str, Any], defaults: ArraySpec | None) -> ArraySpec:
    """One specification out of what was given and what came before."""
    base = defaults or ArraySpec(xdim=0, ydim=0)
    merged = {
        "xdim": values.get("xdim", base.xdim),
        "ydim": values.get("ydim", base.ydim),
        "zdim": values.get("zdim", base.zdim),
        "bitpix": values.get("bitpix", base.bitpix),
        "skip": values.get("skip", base.skip),
        "big_endian": values.get("big_endian", base.big_endian),
    }
    if merged["xdim"] <= 0 or merged["ydim"] <= 0:
        raise ArraySpecError("an array specification needs xdim and ydim")
    if merged["bitpix"] not in BITPIX_TYPES:
        raise ArraySpecError(f"bitpix {merged['bitpix']} is not one DS9 supports")
    return ArraySpec(**merged)


def _integer(text: str, key: str) -> int:
    """One integer out of a specification, with a readable complaint."""
    try:
        return int(float(text))
    except ValueError as exc:
        raise ArraySpecError(f"{key} is not a number: {text}") from exc


def environment_spec() -> ArraySpec | None:
    """What `$DS9_ARRAY` says, or None if it says nothing usable."""
    text = os.environ.get(ENVIRONMENT_VARIABLE)
    if not text:
        return None
    try:
        return parse_spec(text)
    except ArraySpecError:
        return None


def split_spec(path: str) -> tuple[Path, str]:
    """A filename and its array specification, if it carries one."""
    text = str(path)
    bracket = text.find("[")
    if bracket < 0:
        return (Path(text), "")
    return (Path(text[:bracket]), text[bracket:])


def read(path: str | Path, spec: ArraySpec | str | None = None) -> NDArray[Any]:
    """Read a raw array.

    Args:
        path: The file, which may carry its own specification in brackets.
        spec: The specification, or the text of one. None takes it from the
            filename, and failing that from `$DS9_ARRAY`.

    Returns:
        The array, in native byte order.

    Raises:
        ArraySpecError: If there is no usable specification.
        OSError: If the file cannot be read.
    """
    target, embedded = split_spec(str(path))
    default = environment_spec()

    if isinstance(spec, ArraySpec):
        chosen = spec
    elif isinstance(spec, str) and spec.strip():
        chosen = parse_spec(spec, default)
    elif embedded:
        chosen = parse_spec(embedded, default)
    elif default is not None:
        chosen = default
    else:
        raise ArraySpecError(
            "a raw array needs its dimensions: give them in the filename, "
            f"in the dialog, or in ${ENVIRONMENT_VARIABLE}"
        )

    size = target.stat().st_size
    if size < chosen.expected_bytes:
        raise ArraySpecError(
            f"{target.name} holds {size} bytes; "
            f"{chosen.xdim}x{chosen.ydim}x{chosen.zdim} at bitpix {chosen.bitpix} "
            f"needs {chosen.expected_bytes}"
        )

    data = np.fromfile(target, dtype=chosen.dtype, offset=chosen.skip)
    wanted = int(np.prod(chosen.shape))
    # A file longer than the array is DS9's `skip` case seen from the other
    # end: read the pixels asked for and leave the rest.
    data = data[:wanted].reshape(chosen.shape)
    return np.ascontiguousarray(data.astype(data.dtype.newbyteorder("=")))


def write(
    path: str | Path,
    data: NDArray[Any],
    big_endian: bool = True,
) -> ArraySpec:
    """Write a raw array, as DS9's Export -> Array does.

    Args:
        path: The file to write.
        data: The pixels.
        big_endian: Whether to write big-endian, DS9's default and FITS's.

    Returns:
        The specification the file would have to be read back with, which
        is what the caller shows the user -- a raw array carries none.
    """
    array = np.asarray(data)
    bitpix = _bitpix_for(array.dtype)
    order = ">" if big_endian else "<"
    array.astype(np.dtype(order + BITPIX_TYPES[bitpix])).tofile(str(path))

    shape = array.shape
    return ArraySpec(
        xdim=shape[-1],
        ydim=shape[-2] if array.ndim > 1 else 1,
        zdim=shape[0] if array.ndim > 2 else 1,
        bitpix=bitpix,
        big_endian=big_endian,
    )


def _bitpix_for(dtype: np.dtype) -> int:
    """The BITPIX that holds a numpy type without losing anything."""
    for bitpix, code in BITPIX_TYPES.items():
        if np.dtype(code) == dtype.newbyteorder("="):
            return bitpix
    # Anything else -- float16, int8, a bool mask -- goes out as the float
    # DS9 defaults to rather than being refused.
    return -32


class ArrayReader:
    """Reader for raw binary array files."""

    def __init__(self, filepath: str | Path) -> None:
        """
        Initialize array reader.

        Args:
            filepath: Path to the raw array file.
        """
        self.filepath = Path(filepath)

    def read(
        self,
        dtype: DTypeLike = np.float32,
        shape: tuple[int, ...] | None = None,
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
        shape: tuple[int, ...] | None = None,
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
