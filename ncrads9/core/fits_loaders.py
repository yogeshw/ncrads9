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
DS9's `File -> Open as` loaders, as functions over an open FITS file.

Each entry on that submenu is a different reading of the same file: one
extension, all of them as frames, all of them stacked as a cube, three of them
as colour channels, or several assembled as a mosaic. The functions here do
the reading and hand back `ImageData`; putting them on frames is the File
controller's job, so every loader can be tested without a window.

DS9's own list (`ds9/library/mfile.tcl`) is Slice, RGB/HSV/HLS Image, RGB/HSV/
HLS Cube, Multiple Extension Cube, Multiple Extension Frames, Mosaic WCS,
Mosaic WCS Segment, Mosaic IRAF, Mosaic IRAF Segment, Mosaic WFPC2, and URL.
URL is a download followed by an ordinary load, so it lives in the controller.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from astropy.io import fits

from .cube_handler import CUBE_AXES, AxisOrder, CubeHandler, is_cube
from .file_spec import FileSpec
from .fits_handler import FITSHandler, FITSLoadError, HDUInfo
from .image_data import ImageData
from .mosaic import MosaicKind, build_mosaic

#: The channels a colour frame has, in the order a cube's planes fill them.
RGB_CHANNELS: tuple[str, str, str] = ("red", "green", "blue")


def _path_of(handler: FITSHandler) -> Path:
    """An open handler's path.

    Raises:
        FITSLoadError: If the handler has no file open, which every loader
            here needs it to have.
    """
    if handler.filepath is None:
        raise FITSLoadError("no FITS file is open")
    return handler.filepath


def extension_images(
    handler: FITSHandler,
    spec: FileSpec | None = None,
) -> list[tuple[HDUInfo, ImageData]]:
    """Every displayable extension of an open file.

    Args:
        handler: An open `FITSHandler`.
        spec: A specification whose section, if any, is applied to each
            extension. Its extension field is ignored -- this loads all of
            them by definition.

    Returns:
        (info, image) for each displayable extension, in file order.

    Raises:
        FITSLoadError: If the file holds nothing displayable.
    """
    from .fits_handler import apply_section

    path = _path_of(handler)
    infos = handler.displayable_extensions()
    if not infos:
        raise FITSLoadError(f"{handler.filepath}: nothing displayable in any extension")

    images: list[tuple[HDUInfo, ImageData]] = []
    for info in infos:
        image = handler.load_spec(FileSpec(path=path, extension=info.index))
        if spec is not None and spec.section is not None:
            image = apply_section(image, spec.section)
        images.append((info, image))
    return images


def extension_cube(handler: FITSHandler, spec: FileSpec | None = None) -> ImageData:
    """Stack every displayable extension into one cube.

    DS9's Multiple Extension Cube. The extensions must share a shape, which
    is the case for the instrument files this is meant for -- a per-amplifier
    or per-exposure series.

    Args:
        handler: An open `FITSHandler`.
        spec: A specification whose section, if any, is applied first.

    Returns:
        The cube, carrying the first extension's header.

    Raises:
        FITSLoadError: If there are fewer than two extensions, or they differ
            in shape.
    """
    images = extension_images(handler, spec)
    if len(images) < 2:
        raise FITSLoadError(
            f"{handler.filepath}: a multiple-extension cube needs at least "
            f"two displayable extensions, found {len(images)}"
        )

    planes = [np.asarray(image.data, dtype=np.float32) for _info, image in images]
    shapes = {plane.shape[-2:] for plane in planes}
    if len(shapes) != 1:
        sizes = ", ".join(f"{s[1]}x{s[0]}" for s in sorted(shapes))
        raise FITSLoadError(
            f"{handler.filepath}: extensions differ in shape ({sizes}), so they "
            "cannot be stacked; try Multiple Extension Frames"
        )

    header = fits.Header() if images[0][1].header is None else images[0][1].header.copy()
    header["NAXIS3"] = len(planes)
    return ImageData(data=np.stack(planes, axis=0), header=header)


def mosaic_images(
    handler: FITSHandler,
    kind: MosaicKind = MosaicKind.WCS,
    existing: ImageData | None = None,
    spec: FileSpec | None = None,
) -> ImageData:
    """Assemble an open file's extensions into a mosaic.

    Args:
        handler: An open `FITSHandler`.
        kind: Which of DS9's three mosaic conventions to use.
        existing: The mosaic already on screen, for a segment load.
        spec: A specification whose section, if any, is applied first.

    Returns:
        The mosaic.

    Raises:
        FITSLoadError: If the file holds nothing displayable.
        MosaicError: If the extensions do not carry what the convention needs.
    """
    images = [image for _info, image in extension_images(handler, spec)]
    return build_mosaic(images, kind=kind, existing=existing)


def channel_images(
    handler: FITSHandler,
    spec: FileSpec | None = None,
    from_cube: bool = False,
) -> dict[str, ImageData]:
    """Three planes for a colour frame's channels.

    DS9's RGB, HSV and HLS loaders take their three channels either from a
    three-plane cube (`RGB Cube`) or from the file's first three extensions
    (`RGB Image`); the colour space differs but the loading does not, which
    is why one function serves all six menu entries.

    Args:
        handler: An open `FITSHandler`.
        spec: A specification whose extension and section are honoured when
            reading a cube.
        from_cube: Read the three planes from one cube's third axis rather
            than from three separate extensions.

    Returns:
        Channel name -> its plane, for as many of red, green and blue as the
        file provides.

    Raises:
        FITSLoadError: If the file cannot supply three planes the chosen way.
    """
    if from_cube:
        image = handler.load_spec(spec or FileSpec(path=_path_of(handler)))
        if not is_cube(image.data):
            raise FITSLoadError(
                f"{handler.filepath}: a colour cube needs {CUBE_AXES} axes, "
                f"this has {0 if image.data is None else image.data.ndim}"
            )
        cube = CubeHandler(image.data, image.header)
        depth = cube.depth()
        if depth < len(RGB_CHANNELS):
            raise FITSLoadError(
                f"{handler.filepath}: a colour cube needs {len(RGB_CHANNELS)} " f"planes, this has {depth}"
            )
        return {
            channel: ImageData(
                data=cube.get_slice(index, AxisOrder()),
                header=None if image.header is None else image.header.copy(),
            )
            for index, channel in enumerate(RGB_CHANNELS)
        }

    images = extension_images(handler, spec)
    if len(images) < len(RGB_CHANNELS):
        raise FITSLoadError(
            f"{handler.filepath}: a colour image needs {len(RGB_CHANNELS)} "
            f"displayable extensions, found {len(images)}"
        )
    return {channel: image for channel, (_info, image) in zip(RGB_CHANNELS, images, strict=False)}


def slice_image(handler: FITSHandler, spec: FileSpec, slice_index: int = 0) -> ImageData:
    """One slice of a cube, as DS9's `Open as -> Slice` loads it.

    The difference from an ordinary load is that the frame gets a plain 2D
    image with no cube behind it, so the Cube dialog does not open and the
    other slices are not held in memory.

    Args:
        handler: An open `FITSHandler`.
        spec: The specification naming the extension and any section.
        slice_index: Which slice, counting from zero.

    Returns:
        The slice.

    Raises:
        FITSLoadError: If the extension is not a cube, or the slice is
            outside it.
    """
    image = handler.load_spec(spec)
    if not is_cube(image.data):
        raise FITSLoadError(f"{handler.filepath}: not a data cube, so it has no slices to choose from")
    cube = CubeHandler(image.data, image.header)
    depth = cube.depth()
    if not 0 <= slice_index < depth:
        raise FITSLoadError(f"{handler.filepath}: slice {slice_index + 1} outside 1..{depth}")

    header = fits.Header() if image.header is None else image.header.copy()
    for key in ("NAXIS3", "CRVAL3", "CRPIX3", "CDELT3", "CTYPE3", "CUNIT3"):
        header.pop(key, None)
    header["NAXIS"] = 2
    return ImageData(data=cube.get_slice(slice_index), header=header)
