# NCRADS9 - Rendering Module
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

"""
Rendering module for NCRADS9.

This module provides OpenGL-based rendering components for astronomical
image display, including scaling algorithms, colormaps, and tile-based
rendering for large images.
"""

from .gl_canvas import GLCanvas
from .scale_algorithms import ScaleAlgorithm, apply_scale
from .colormap_engine import ColormapEngine
from .texture_manager import TextureManager
from .tile_renderer import TileRenderer
from .rgb_compositor import RGBCompositor

__all__ = [
    "GLCanvas",
    "ScaleAlgorithm",
    "apply_scale",
    "ColormapEngine",
    "TextureManager",
    "TileRenderer",
    "RGBCompositor",
]
