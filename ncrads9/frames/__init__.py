# NCRA DS9 - Astronomical Image Viewer
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

"""Frames module for NCRA DS9."""

from .frame import Frame
from .frame_manager import FrameManager
from .rgb_frame import RGBFrame
from .hls_frame import HLSFrame
from .hsv_frame import HSVFrame
from .frame_3d import Frame3D
from .tile_layout import TileLayout
from .blink_controller import BlinkController

__all__ = [
    "Frame",
    "FrameManager",
    "RGBFrame",
    "HLSFrame",
    "HSVFrame",
    "Frame3D",
    "TileLayout",
    "BlinkController",
]
