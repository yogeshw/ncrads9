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
#
# Author: Yogesh Wadadekar

"""Colormaps package for ncrads9."""

from .colormap import Colormap
from .builtin_maps import BUILTIN_COLORMAPS, get_builtin_colormap
from .lut_parser import parse_lut_file
from .sao_parser import parse_sao_file
from .colorbar_widget import ColorbarWidget

__all__ = [
    "Colormap",
    "BUILTIN_COLORMAPS",
    "get_builtin_colormap",
    "parse_lut_file",
    "parse_sao_file",
    "ColorbarWidget",
]
