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
#
# Author: Yogesh Wadadekar

"""Tests for builtin colormaps."""

from ncrads9.colormaps.builtin_maps import get_builtin_colormap


def test_common_ds9_colormaps_available():
    for name in ("viridis", "plasma", "inferno", "magma"):
        cmap = get_builtin_colormap(name)
        assert cmap is not None
        assert cmap.name == name
        assert cmap.colors.shape == (256, 3)
        assert cmap.colors.min() >= 0.0
        assert cmap.colors.max() <= 1.0
