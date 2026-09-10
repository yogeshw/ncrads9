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
GIF, TIFF, JPEG and PNG, read as data and written as pictures.

The two directions are not symmetrical, and DS9's menu says which is which.
Import reads a picture *as data*: the pixels become the frame's array, so
they can be scaled, measured and have regions drawn on them. Export writes
the frame *as a picture*: the colormap and the scale are already applied,
because a GIF has no room for a stretch.

Rows are flipped on the way in and out. A picture counts them from the top
and FITS counts them from the bottom, so a photograph imported without the
flip is displayed upside down -- and re-exported right way up, which is how
the mistake hides.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

#: The formats DS9's Import and Export offer, and what they are called on
#: disk. GIF is 8-bit and paletted; the rest take 8 bits a channel.
FORMATS: dict[str, tuple[str, ...]] = {
    "gif": (".gif",),
    "tiff": (".tif", ".tiff"),
    "jpeg": (".jpg", ".jpeg"),
    "png": (".png",),
}

#: What PIL calls each of them.
PIL_FORMATS: dict[str, str] = {
    "gif": "GIF",
    "tiff": "TIFF",
    "jpeg": "JPEG",
    "png": "PNG",
}


def file_filter(name: str) -> str:
    """The Open/Save filter for one raster format."""
    patterns = " ".join(f"*{suffix}" for suffix in FORMATS.get(name, ()))
    return f"{name.upper()} files ({patterns});;All files (*)"


def read(path: str | Path, colour: bool = False) -> NDArray[Any]:
    """Read a picture as data.

    Args:
        path: The file.
        colour: Whether to keep its three channels. False averages them
            into one plane, which is what a greyscale frame wants; DS9's
            plain Import does the same and its RGB Array import does not.

    Returns:
        A 2D array of luminance, or a (3, height, width) cube of channels
        when `colour` is asked for -- FITS's plane order, not a picture's.

    Raises:
        OSError: If the file cannot be read or is not a picture.
    """
    with Image.open(path) as picture:
        if colour:
            rgb = np.asarray(picture.convert("RGB"), dtype=np.float32)
            # Rows from the bottom, and channels first, as a FITS cube has
            # them.
            return np.ascontiguousarray(rgb[::-1].transpose(2, 0, 1))
        grey = np.asarray(picture.convert("F"), dtype=np.float32)
        return np.ascontiguousarray(grey[::-1])


def write(
    path: str | Path,
    rgb: NDArray[np.uint8],
    name: str,
    quality: int = 95,
    compress: str | None = "lzw",
) -> Path:
    """Write a rendered image out as a picture.

    Args:
        path: The file to write.
        rgb: The rendered image, (height, width, 3) of bytes, rows from the
            bottom as the renderer leaves them.
        name: One of `FORMATS`.
        quality: JPEG quality, DS9's `export(jpeg,quality)`.
        compress: TIFF compression, DS9's `export(tiff,compress)`. None
            writes it uncompressed.

    Returns:
        The path written.

    Raises:
        ValueError: If the format is not one of DS9's four.
        OSError: If the file cannot be written.
    """
    if name not in PIL_FORMATS:
        raise ValueError(f"{name} is not a raster format DS9 exports")

    array = np.asarray(rgb, dtype=np.uint8)
    if array.ndim == 2:
        array = np.repeat(array[:, :, None], 3, axis=2)
    # Back to a picture's row order.
    picture = Image.fromarray(np.ascontiguousarray(array[::-1]), mode="RGB")

    options: dict[str, Any] = {}
    if name == "jpeg":
        options["quality"] = int(quality)
    elif name == "tiff" and compress:
        options["compression"] = compress
    elif name == "gif":
        # GIF holds 256 colours; PIL needs telling which 256.
        picture = picture.convert("P", palette=Image.Palette.ADAPTIVE)

    picture.save(str(path), PIL_FORMATS[name], **options)
    return Path(path)
