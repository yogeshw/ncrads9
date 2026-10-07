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
Moved to `ncrads9.coordinates.positions`; re-exported so old imports work.

The dialogs read and write the same positions as XPA does, and a dialog
should not have to import the XPA package to do it.

Author: Yogesh Wadadekar
"""

from ...coordinates.positions import (  # noqa: F401
    SKY_FORMATS,
    SKY_FRAMES,
    SYSTEMS,
    _physical,
    _sky_coord,
    distance_from_image,
    distance_to_image,
    from_image,
    has_system,
    is_system,
    split_spec,
    to_image,
    wcs_handler,
)
