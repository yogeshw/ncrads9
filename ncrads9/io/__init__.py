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
IO module for NCRADS9.

Provides readers and writers for various file formats.

Author: Yogesh Wadadekar
"""

from .fits_reader import FITSReader
from .fits_writer import FITSWriter
from .array_reader import ArrayReader
from .envi_reader import ENVIReader
from .nrrd_reader import NRRDReader
from .gif_writer import GIFWriter
from .mpeg_writer import MPEGWriter
from .png_writer import PNGWriter
from .jpeg_writer import JPEGWriter
from .tiff_writer import TIFFWriter
from .eps_writer import EPSWriter
from .pdf_writer import PDFWriter

__all__ = [
    "FITSReader",
    "FITSWriter",
    "ArrayReader",
    "ENVIReader",
    "NRRDReader",
    "GIFWriter",
    "MPEGWriter",
    "PNGWriter",
    "JPEGWriter",
    "TIFFWriter",
    "EPSWriter",
    "PDFWriter",
]
