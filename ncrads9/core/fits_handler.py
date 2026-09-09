# This file is part of ncrads9.
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
FITS file handler module.

Provides functionality for loading and managing FITS files using astropy.

The extension model below follows the algorithm DS9 documents in
`ds9/doc/ref/file.html`: examine the primary HDU and load it if it is an
image; otherwise walk the extensions, loading the first image, or the first
binary table that can be turned into one -- a tile-compressed image
(`ZIMAGE = T`), an events table (`EXTNAME` of EVENTS, STDEVT or RAYEVENT with
X and Y columns), or a HEALPIX table (`PIXTYPE = HEALPIX`). If nothing
qualifies, DS9 raises an error, and so does this.

Author: Yogesh Wadadekar
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray

from .file_spec import BinSpec, FileSpec, Section
from .image_data import ImageData

if TYPE_CHECKING:
    from .bin_table import BinSettings

#: `EXTNAME` values DS9 recognises as an events table.
EVENTS_EXTNAMES: frozenset[str] = frozenset({"EVENTS", "STDEVT", "RAYEVENT"})

#: The two columns an events table must have for DS9 to bin it.
EVENTS_COLUMNS: tuple[str, str] = ("X", "Y")

#: Smallest number of axes a displayable image needs.
MIN_IMAGE_AXES = 2


class FITSLoadError(OSError):
    """A FITS file that cannot be displayed, for the reason given."""


class HDUKind(Enum):
    """What one HDU holds, in the terms DS9's loader cares about."""

    #: A plain image, primary or extension.
    IMAGE = "image"
    #: A tile-compressed image, which astropy presents as an image too.
    COMPRESSED = "compressed"
    #: A binary table with X and Y columns, to be binned into an image.
    EVENTS = "events"
    #: A HEALPIX table, to be reprojected into an image.
    HEALPIX = "healpix"
    #: Any other table.
    TABLE = "table"
    #: A header-only HDU -- almost always the primary of an MEF file.
    EMPTY = "empty"


@dataclass(frozen=True)
class HDUInfo:
    """One HDU, described well enough to choose between them.

    Attributes:
        index: Position in the HDU list.
        name: `EXTNAME`, or "PRIMARY" for the first HDU.
        kind: What the HDU holds.
        shape: The data shape in numpy order, or () for a table.
        bitpix: The header's BITPIX, or None if it has none.
        rows: Table rows, or None for an image.
        columns: Table column names, or () for an image.
        displayable: Whether the loader can turn this into an image.
    """

    index: int
    name: str
    kind: HDUKind
    shape: tuple[int, ...] = ()
    bitpix: int | None = None
    rows: int | None = None
    columns: tuple[str, ...] = field(default_factory=tuple)
    displayable: bool = False

    @property
    def is_cube(self) -> bool:
        """True when the data has three or more non-degenerate axes."""
        return len([length for length in self.shape if length > 1]) > MIN_IMAGE_AXES

    @property
    def dimensions(self) -> str:
        """The shape as DS9 writes it in the HDU chooser, e.g. "512x512"."""
        if self.shape:
            # FITS and DS9 quote axes in NAXIS order, which is numpy's
            # reversed.
            return "x".join(str(length) for length in reversed(self.shape))
        if self.rows is not None:
            return f"{self.rows} rows x {len(self.columns)} cols"
        return ""

    def describe(self) -> str:
        """A one-line summary for a chooser row or a status message."""
        parts = [f"[{self.index}]", self.name or "-", self.kind.value]
        if self.dimensions:
            parts.append(self.dimensions)
        if not self.displayable:
            parts.append("(not displayable)")
        return "  ".join(parts)


def _column_names(hdu: fits.hdu.base.ExtensionHDU) -> tuple[str, ...]:
    """A table HDU's column names, uppercased, or () if it has none."""
    columns = getattr(hdu, "columns", None)
    if columns is None:
        return ()
    try:
        return tuple(str(name).upper() for name in columns.names)
    except Exception:
        return ()


def classify(hdu: fits.hdu.base.ExtensionHDU, index: int) -> HDUInfo:
    """Describe one HDU, following DS9's loader rules.

    Args:
        hdu: The HDU to look at.
        index: Its position in the HDU list.

    Returns:
        Its `HDUInfo`. Reads the header only -- never the data -- so this
        stays cheap on a lazily-opened file.
    """
    header = hdu.header
    name = str(getattr(hdu, "name", "") or ("PRIMARY" if index == 0 else ""))
    bitpix = header.get("BITPIX")
    bitpix = int(bitpix) if isinstance(bitpix, (int, float)) else None

    if isinstance(hdu, fits.CompImageHDU):
        # astropy presents a tile-compressed HDU as the image it decompresses
        # to, so its header already carries NAXIS rather than ZNAXIS. Read
        # ZNAXIS as a fallback for a header taken straight off the wire.
        shape = tuple(int(n) for n in (_header_shape(header, "NAXIS") or _header_shape(header, "ZNAXIS")))
        return HDUInfo(
            index=index,
            name=name,
            kind=HDUKind.COMPRESSED,
            shape=shape,
            bitpix=header.get("ZBITPIX", bitpix),
            displayable=len(shape) >= MIN_IMAGE_AXES,
        )

    if isinstance(hdu, (fits.PrimaryHDU, fits.ImageHDU)):
        shape = tuple(int(n) for n in _header_shape(header, "NAXIS"))
        if not shape:
            return HDUInfo(index=index, name=name, kind=HDUKind.EMPTY, bitpix=bitpix)
        return HDUInfo(
            index=index,
            name=name,
            kind=HDUKind.IMAGE,
            shape=shape,
            bitpix=bitpix,
            displayable=len(shape) >= MIN_IMAGE_AXES,
        )

    columns = _column_names(hdu)
    rows = header.get("NAXIS2")
    rows = int(rows) if isinstance(rows, (int, float)) else None

    kind = HDUKind.TABLE
    displayable = False
    if str(header.get("PIXTYPE", "")).upper() == "HEALPIX":
        kind = HDUKind.HEALPIX
        # Reprojecting HEALPIX is M9 work; the HDU is recognised but the
        # loader cannot yet turn it into an image.
    elif name.upper() in EVENTS_EXTNAMES and all(c in columns for c in EVENTS_COLUMNS):
        kind = HDUKind.EVENTS
        displayable = True
    elif all(c in columns for c in EVENTS_COLUMNS):
        # DS9 keys on EXTNAME, but a table with X and Y is bin-able whatever
        # it calls itself, and `[bin=...]` may name other columns entirely.
        kind = HDUKind.EVENTS
        displayable = True

    return HDUInfo(
        index=index,
        name=name,
        kind=kind,
        bitpix=bitpix,
        rows=rows,
        columns=columns,
        displayable=displayable,
    )


def _header_shape(header: fits.Header, prefix: str) -> list[int]:
    """The data shape from `NAXIS`/`ZNAXIS` cards, in numpy order."""
    count = header.get(prefix, 0)
    if not isinstance(count, (int, float)) or count < 1:
        return []
    lengths = [int(header.get(f"{prefix}{axis}", 0)) for axis in range(1, int(count) + 1)]
    if any(length < 1 for length in lengths):
        return []
    return list(reversed(lengths))


class FITSHandler:
    """Handler class for FITS file operations.

    This class provides methods for loading FITS files, accessing
    extensions, and extracting data arrays.

    Attributes:
        filepath: Path to the FITS file.
        hdu_list: The HDU list from the opened FITS file.
    """

    def __init__(self, filepath: str | Path | None = None) -> None:
        """Initialize FITSHandler.

        Args:
            filepath: Optional path to a FITS file to load.
        """
        self.filepath: Path | None = Path(filepath) if filepath else None
        self.hdu_list: fits.HDUList | None = None

        if self.filepath is not None:
            self.load(self.filepath)

    def load(self, filepath: str | Path, memmap: bool = True) -> fits.HDUList:
        """Load a FITS file.

        Args:
            filepath: Path to the FITS file.
            memmap: Whether to memory-map FITS data access.

        Returns:
            The HDU list from the FITS file.

        Raises:
            FileNotFoundError: If the file does not exist.
            IOError: If the file cannot be read.
        """
        self.filepath = Path(filepath)
        self.hdu_list = fits.open(
            self.filepath,
            memmap=memmap,
            lazy_load_hdus=True,
            mode="readonly",
        )
        return self.hdu_list

    def get_extension(self, ext: int | str = 0) -> fits.hdu.base.ExtensionHDU:
        """Get a specific extension from the FITS file.

        Args:
            ext: Extension index or name.

        Returns:
            The requested HDU extension.

        Raises:
            ValueError: If no file is loaded.
        """
        if self.hdu_list is None:
            raise ValueError("No FITS file loaded")
        return self.hdu_list[ext]

    def get_data(self, ext: int | str = 0) -> NDArray[np.floating]:
        """Get data array from a specific extension.

        Args:
            ext: Extension index or name.

        Returns:
            The data array from the extension.
        """
        if self.hdu_list is None:
            raise ValueError("No FITS file loaded")
        return self.hdu_list[ext].data

    def get_header(self, ext: int | str = 0) -> fits.Header:
        """Get header from a specific extension.

        Args:
            ext: Extension index or name.

        Returns:
            The header from the extension.
        """
        if self.hdu_list is None:
            raise ValueError("No FITS file loaded")
        return self.hdu_list[ext].header

    def list_extensions(self) -> list[tuple[int, str, str]]:
        """List all extensions in the FITS file.

        Returns:
            List of tuples containing (index, name, type) for each extension.
        """
        if self.hdu_list is None:
            raise ValueError("No FITS file loaded")
        extensions = []
        for i, hdu in enumerate(self.hdu_list):
            extensions.append((i, hdu.name, type(hdu).__name__))
        return extensions

    # -- the extension model -------------------------------------------------

    def extensions(self) -> list[HDUInfo]:
        """Describe every HDU in the file.

        Returns:
            One `HDUInfo` per HDU, in file order.

        Raises:
            ValueError: If no file is open.
        """
        if self.hdu_list is None:
            raise ValueError("No FITS file loaded")
        return [classify(hdu, index) for index, hdu in enumerate(self.hdu_list)]

    def displayable_extensions(self) -> list[HDUInfo]:
        """Only the HDUs the loader can turn into an image."""
        return [info for info in self.extensions() if info.displayable]

    def default_extension(self) -> HDUInfo:
        """The HDU DS9 would load when none is named.

        DS9's rule, from `ds9/doc/ref/file.html`: take the primary HDU if it
        is an image, else the first extension that is one, or that can be
        made into one.

        Returns:
            The chosen HDU's info.

        Raises:
            ValueError: If no file is open.
            FITSLoadError: If nothing in the file is displayable, which is
                the error DS9 raises in the same case.
        """
        displayable = self.displayable_extensions()
        if not displayable:
            raise FITSLoadError(
                f"{self.filepath}: no displayable image, events table or " "compressed image in any HDU"
            )
        return displayable[0]

    def resolve_extension(self, ext: int | str | None) -> HDUInfo:
        """Find the HDU a specification names.

        Args:
            ext: An index, an `EXTNAME` (matched case-insensitively, as DS9
                does), or None for DS9's default search.

        Returns:
            The chosen HDU's info.

        Raises:
            FITSLoadError: If the name or index does not exist, or names an
                HDU that cannot be displayed.
        """
        if ext is None:
            return self.default_extension()

        infos = self.extensions()
        if isinstance(ext, int):
            if not -len(infos) <= ext < len(infos):
                raise FITSLoadError(f"{self.filepath}: no extension {ext}")
            return infos[ext]

        wanted = ext.strip().upper()
        for info in infos:
            if info.name.upper() == wanted:
                return info
        raise FITSLoadError(f"{self.filepath}: no extension named {ext!r}")

    def load_image_data(self, ext: int | str = 0) -> "ImageData":
        """Return one extension wrapped in an ImageData container.

        Gathers the array, the header, the WCS and the derived metadata
        (BITPIX, cached min/max) in one step, so the caller does not assemble
        them itself.

        Args:
            ext: Extension index or EXTNAME.

        Returns:
            The extension's ImageData.

        Raises:
            ValueError: If no file is open.
        """
        if self.hdu_list is None:
            raise ValueError("No FITS file loaded")
        return ImageData.from_hdu(self.hdu_list[ext])

    # -- loading a specification ---------------------------------------------

    def load_spec_with_bin(
        self,
        spec: FileSpec,
        settings: "BinSettings | None" = None,
    ) -> "ImageData":
        """Load a specification, binning a table with the given settings.

        Args:
            spec: A `FileSpec`.
            settings: DS9's Bin menu, or None for its defaults.

        Returns:
            The extension's `ImageData`.
        """
        return self.load_spec(spec, settings)

    def load_spec(self, spec: FileSpec, bin_settings: "BinSettings | None" = None) -> "ImageData":
        """Load whatever a parsed file specification names.

        Applies, in DS9's order: choose the HDU, turn an events table into an
        image if that is what it is, then cut the subsection.

        Args:
            spec: A `FileSpec`, usually from `core.file_spec.parse`.

        Returns:
            The extension's `ImageData`, sectioned if the spec asked for it.

        Raises:
            ValueError: If no file is open.
            FITSLoadError: If the named extension is missing or unusable.
        """
        if self.hdu_list is None:
            raise ValueError("No FITS file loaded")

        info = self.resolve_extension(spec.extension)
        if not info.displayable:
            raise FITSLoadError(
                f"{self.filepath}: extension {info.index} ({info.name}) is a "
                f"{info.kind.value} and cannot be displayed"
            )

        hdu = self.hdu_list[info.index]
        if info.kind is HDUKind.EVENTS:
            # A filter may arrive in its own bracket group -- DS9's
            # `foo.fits[bin=x,y][pha>500]` -- rather than inside the bin
            # group, so the specification's whole filter expression is what
            # the binning has to see.
            image = bin_events(hdu, spec.bin, _with_filter(bin_settings, spec))
        else:
            image = ImageData.from_hdu(hdu)

        if spec.section is not None:
            image = apply_section(image, spec.section)
        return image

    def close(self) -> None:
        """Close the FITS file."""
        if self.hdu_list is not None:
            self.hdu_list.close()
            self.hdu_list = None

    def __enter__(self) -> "FITSHandler":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit."""
        self.close()


def apply_section(image: "ImageData", section: Section) -> "ImageData":
    """Cut a subsection out of an image, carrying the WCS with it.

    DS9 counts section bounds from one and includes both ends, and reads them
    as image coordinates unless the section ends in `p`, in which case they
    are physical and go through the header's `LTV`/`LTM` mapping first.

    The block factor is *not* applied here: blocking is a display transform
    that the frame owns (PLAN.md §3.4), so it is left on the section for the
    caller to hand to the frame.

    Args:
        image: The full extension.
        section: The subsection to cut.

    Returns:
        A new `ImageData` holding the cut, with `CRPIX` shifted to match.
        The original is left alone.
    """
    from .file_spec import AxisSpec

    data = image.data
    if data is None or data.ndim < MIN_IMAGE_AXES:
        return image

    bounds = section
    if section.physical:
        bounds = _to_image_coordinates(section, image.header)

    height, width = data.shape[-2], data.shape[-1]
    x0, x1 = bounds.x.resolve(width)
    y0, y1 = bounds.y.resolve(height)
    slices: list[slice] = [slice(y0 - 1, y1), slice(x0 - 1, x1)]

    z_axis: AxisSpec | None = bounds.z
    if z_axis is not None and data.ndim >= 3:
        z0, z1 = z_axis.resolve(data.shape[-3])
        slices.insert(0, slice(z0 - 1, z1))
    # Any axes above the ones being cut are taken whole.
    leading = [slice(None)] * (data.ndim - len(slices))

    cut = data[tuple([*leading, *slices])]

    header = None if image.header is None else image.header.copy()
    if header is not None:
        _shift_reference_pixel(header, x0 - 1, y0 - 1)
    return ImageData(data=cut, header=header)


def _to_image_coordinates(section: Section, header: fits.Header | None) -> Section:
    """Convert a physical section to image coordinates."""
    from ..coordinates.physical_coords import PhysicalTransform
    from .file_spec import AxisSpec

    transform = PhysicalTransform() if header is None else PhysicalTransform.from_header(header)
    if transform.is_identity:
        return section

    def convert(axis: AxisSpec, index: int) -> AxisSpec:
        if axis.is_wildcard:
            return axis
        pair = [
            transform.physical_to_image(axis.lo or 1, axis.lo or 1),
            transform.physical_to_image(axis.hi or 1, axis.hi or 1),
        ]
        return AxisSpec.between(int(round(pair[0][index])), int(round(pair[1][index])))

    return Section(
        x=convert(section.x, 0),
        y=convert(section.y, 1),
        # LTV/LTM describe the two image axes only, so a z range is already
        # in image coordinates.
        z=section.z,
        block=section.block,
        physical=False,
    )


def _shift_reference_pixel(header: fits.Header, dx: int, dy: int) -> None:
    """Move `CRPIX` so the WCS still points at the same sky after a cut."""
    for key, shift in (("CRPIX1", dx), ("CRPIX2", dy)):
        if key in header and shift:
            header[key] = header[key] - shift
    # The physical mapping is anchored to the original array, so it moves too.
    for key, shift in (("LTV1", dx), ("LTV2", dy)):
        if key in header and shift:
            header[key] = header[key] - shift


def _with_filter(
    settings: "BinSettings | None",
    spec: FileSpec,
) -> "BinSettings | None":
    """Fold a specification's filter into the bin settings.

    A filter set on the Bin menu wins, since the user asked for it more
    recently than the file name did.
    """
    expression = spec.filter_expression
    if not expression:
        return settings

    from dataclasses import replace

    from .bin_table import BinSettings

    base = settings if settings is not None else BinSettings()
    return base if base.filter else replace(base, filter=expression)


def bin_events(
    hdu: fits.hdu.base.ExtensionHDU,
    spec: BinSpec | None,
    settings: "BinSettings | None" = None,
) -> "ImageData":
    """Turn a FITS binary table into an image.

    DS9 does this for any events table, which is why such a table counts as
    displayable. The work is in `core/bin_table.py`, which holds DS9's Bin
    menu -- the function, the bin factor, the buffer size, the depth column
    and the row filter -- and the four-card search for each axis's extent.

    Args:
        hdu: The table HDU.
        spec: The parsed `bin=` group, or None for DS9's default X and Y.
        settings: The Bin menu's settings, or None for DS9's defaults.

    Returns:
        The image, with a WCS from the columns' own `TC*` cards where present.

    Raises:
        FITSLoadError: If the table cannot be binned as asked.
    """
    from .bin_table import BinTableError, bin_table

    try:
        return bin_table(hdu, spec, settings)
    except BinTableError as exc:
        raise FITSLoadError(str(exc)) from exc
