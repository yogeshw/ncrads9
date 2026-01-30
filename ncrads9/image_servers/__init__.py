# This file is part of ncrads9.
#
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
Image servers package for accessing astronomical image archives.

Author: Yogesh Wadadekar
"""

from .dss import DSSServer
from .twomass_image import TwoMassImage
from .eso import ESOArchive
from .sdss_image import SDSSImage
from .skyview import SkyViewServer
from .sia_client import SIAClient

__all__ = [
    "DSSServer",
    "TwoMassImage",
    "ESOArchive",
    "SDSSImage",
    "SkyViewServer",
    "SIAClient",
]
