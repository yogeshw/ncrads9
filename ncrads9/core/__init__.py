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
Core module for ncrads9.

This package provides core functionality for FITS file handling,
image data management, WCS transformations, and data caching.

Author: Yogesh Wadadekar
"""

from .fits_handler import FITSHandler
from .image_data import ImageData
from .wcs_handler import WCSHandler
from .cube_handler import CubeHandler
from .header_parser import parse_header, extract_keywords
from .data_cache import DataCache

__all__ = [
    "FITSHandler",
    "ImageData",
    "WCSHandler",
    "CubeHandler",
    "DataCache",
    "parse_header",
    "extract_keywords",
]
