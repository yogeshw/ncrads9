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
One controller per DS9 menu.

See `base.Controller` for the design and why controllers currently reach
shared state through the main window.

Author: Yogesh Wadadekar
"""

from .base import Controller
from .color import ColorController
from .edit import EditController
from .file import FileController
from .region import RegionController
from .scale import ScaleController
from .view import ViewController
from .wcs import WCSController
from .zoom import ZoomController

__all__ = [
    "ColorController",
    "Controller",
    "EditController",
    "FileController",
    "RegionController",
    "ScaleController",
    "ViewController",
    "WCSController",
    "ZoomController",
]
