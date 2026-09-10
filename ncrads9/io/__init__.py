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
Reading and writing everything that is not a FITS image.

`eps_writer` and `pdf_writer` are deliberately not imported here: nothing
reaches them until M9-18 and M9-20 give them a Print dialog, and importing
them would hide that from the no-orphan-modules guard.
"""

from .array_reader import ArraySpec, ArraySpecError
from .envi_reader import ENVIReader
from .fits_writer import FITSWriter
from .gif_writer import GIFWriter
from .jpeg_writer import JPEGWriter
from .mpeg_writer import MPEGWriter
from .nrrd_reader import NRRDReader
from .png_writer import PNGWriter
from .tiff_writer import TIFFWriter

__all__ = [
    "ArraySpec",
    "ArraySpecError",
    "ENVIReader",
    "FITSWriter",
    "GIFWriter",
    "JPEGWriter",
    "MPEGWriter",
    "NRRDReader",
    "PNGWriter",
    "TIFFWriter",
]
