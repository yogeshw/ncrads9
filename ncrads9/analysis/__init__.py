# ncrads9 - NCRA DS9 Analysis Package
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
NCRA DS9 Analysis Package

This package provides analysis tools for astronomical image processing.

Author: Yogesh Wadadekar
"""

from .statistics import (
    image_mean,
    image_median,
    image_std,
    image_min,
    image_max,
    image_stats,
)
from .histogram import Histogram
from .radial_profile import RadialProfile
from .contour import ContourGenerator
from .smooth import gaussian_smooth, boxcar_smooth, tophat_smooth
from .centroid import calculate_centroid, calculate_centroid_iterative
from .pixel_table import PixelTable

__all__ = [
    "image_mean",
    "image_median",
    "image_std",
    "image_min",
    "image_max",
    "image_stats",
    "Histogram",
    "RadialProfile",
    "ContourGenerator",
    "gaussian_smooth",
    "boxcar_smooth",
    "tophat_smooth",
    "calculate_centroid",
    "calculate_centroid_iterative",
    "PixelTable",
]
