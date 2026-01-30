# NCRADS9 - NCRA DS9 Viewer
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
Regions package for NCRADS9.

This package provides classes for handling DS9 regions including parsing,
rendering, and management.

Author: Yogesh Wadadekar
"""

from .base_region import BaseRegion
from .region_parser import RegionParser
from .region_writer import RegionWriter
from .region_manager import RegionManager
from .region_renderer import RegionRenderer
from .group_manager import GroupManager

__all__ = [
    "BaseRegion",
    "RegionParser",
    "RegionWriter",
    "RegionManager",
    "RegionRenderer",
    "GroupManager",
]
