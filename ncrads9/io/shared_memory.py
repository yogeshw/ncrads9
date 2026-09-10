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
Reading an image out of shared memory, so a pipeline need not use a disk.

DS9's `shm` access point takes a **System V** segment, by key or by shmid
(`ds9/doc/ref/xpa.html`). Python has no System V shared memory in its
standard library; it has POSIX shared memory, which is the same idea with
a name instead of a key and is what a program written this decade would
reach for.

So this reads both:

  * a POSIX segment by name, always -- `multiprocessing.shared_memory`;
  * a System V segment by key or shmid, when `sysv_ipc` is installed,
    which it is not by default.

That is a deliberate deviation, recorded in TODO. Refusing to read
anything at all without a C extension would be worse, and a POSIX name is
what most producers can offer.

The bytes in the segment are either a FITS file or a raw array, which is
DS9's distinction too -- its `shm fits` and `shm array`.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import io
from typing import Any

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray

from .array_reader import ArraySpec, parse_spec

#: How a segment can be named, in the order DS9's syntax lists them.
KINDS: tuple[str, ...] = ("key", "shmid", "name")


class SharedMemoryError(Exception):
    """A segment that cannot be read, for the reason given."""


def available() -> dict[str, bool]:
    """Which kinds of shared memory this installation can read."""
    return {"posix": True, "sysv": _sysv() is not None}


def _sysv():
    """The `sysv_ipc` module, or None if it is not installed."""
    try:
        import sysv_ipc
    except ImportError:
        return None
    return sysv_ipc


def read_bytes(identifier: str | int, kind: str = "name") -> bytes:
    """Everything in one shared-memory segment.

    Args:
        identifier: The segment's name, for POSIX; its key or shmid, for
            System V.
        kind: `name`, `key` or `shmid`.

    Returns:
        The segment's contents.

    Raises:
        SharedMemoryError: If the segment cannot be opened, or the kind
            asked for is not supported here.
    """
    if kind not in KINDS:
        raise SharedMemoryError(f"{kind} is not a way of naming a segment")

    if kind == "name":
        from multiprocessing import shared_memory

        try:
            segment = shared_memory.SharedMemory(name=str(identifier))
        except FileNotFoundError as exc:
            raise SharedMemoryError(f"no shared-memory segment named {identifier}") from exc
        except OSError as exc:
            raise SharedMemoryError(f"cannot open {identifier}: {exc}") from exc
        try:
            return bytes(segment.buf)
        finally:
            segment.close()

    module = _sysv()
    if module is None:
        raise SharedMemoryError(
            f"reading a System V segment by {kind} needs the sysv_ipc package; "
            "a POSIX segment can be read by name without it"
        )
    try:
        number = int(identifier)
    except (TypeError, ValueError) as exc:
        raise SharedMemoryError(f"{identifier} is not a {kind}") from exc

    try:
        if kind == "shmid":
            segment = module.SharedMemory(None, flags=0, mode=0, size=0, init_character=b" ")
            segment.id = number  # type: ignore[misc]
        else:
            segment = module.SharedMemory(number)
        return segment.read()
    except Exception as exc:  # sysv_ipc raises its own exception types
        raise SharedMemoryError(f"cannot read segment {identifier}: {exc}") from exc


def read_fits(identifier: str | int, kind: str = "name") -> NDArray[Any]:
    """A FITS file held in shared memory.

    Args:
        identifier: The segment.
        kind: How it is named.

    Returns:
        The first image in it.

    Raises:
        SharedMemoryError: If the segment cannot be read, or holds no
            image.
    """
    payload = read_bytes(identifier, kind)
    try:
        with fits.open(io.BytesIO(payload), memmap=False) as hdus:
            for hdu in hdus:
                if getattr(hdu, "data", None) is not None and hdu.data.ndim >= 2:
                    return np.asarray(hdu.data)
    except OSError as exc:
        raise SharedMemoryError(f"the segment does not hold a FITS file: {exc}") from exc
    raise SharedMemoryError("the segment's FITS file holds no image")


def read_array(
    identifier: str | int,
    spec: ArraySpec | str,
    kind: str = "name",
) -> NDArray[Any]:
    """A raw array held in shared memory.

    Args:
        identifier: The segment.
        spec: Its shape and number format, as DS9's array specification --
            `xdim=512,ydim=512,bitpix=-32` -- or an `ArraySpec`.
        kind: How the segment is named.

    Returns:
        The array, in native byte order.

    Raises:
        SharedMemoryError: If the segment cannot be read or is too small
            for the specification.
    """
    chosen = spec if isinstance(spec, ArraySpec) else parse_spec(str(spec))
    payload = read_bytes(identifier, kind)
    if len(payload) < chosen.expected_bytes:
        raise SharedMemoryError(
            f"the segment holds {len(payload)} bytes; "
            f"{chosen.xdim}x{chosen.ydim}x{chosen.zdim} at bitpix {chosen.bitpix} "
            f"needs {chosen.expected_bytes}"
        )

    wanted = int(np.prod(chosen.shape))
    data = np.frombuffer(payload, dtype=chosen.dtype, count=wanted, offset=chosen.skip)
    return np.ascontiguousarray(data.reshape(chosen.shape).astype(chosen.dtype.newbyteorder("=")))
