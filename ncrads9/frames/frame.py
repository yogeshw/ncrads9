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
The frame model: one loaded image plus everything the display remembers
about it.

A frame carries its own view state (zoom, pan, rotation, flips, scale limits,
colormap, block factor, crop, per-channel RGB settings) so that switching
frames restores exactly what the user last saw, which is how DS9 behaves.

Before M1 there were two Frame classes: this one -- reached through
`simple_frame_manager` -- and an unused `frames/frame.py` with a different,
smaller field set. This is the one the application actually used; the other
was deleted along with its FrameManager.

Author: Yogesh Wadadekar
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..rendering.scale_algorithms import ScaleAlgorithm


@dataclass
class Frame:
    """Container for a single frame (image + metadata)."""

    frame_id: int
    filepath: Path | None = None
    image_data: np.ndarray | None = None
    header: dict | None = None
    wcs_handler: object | None = None
    fits_handler: object | None = None
    regions: list = None
    original_image_data: np.ndarray | None = None
    bin_factor: int = 1
    colormap: str = "grey"
    scale: ScaleAlgorithm = ScaleAlgorithm.LINEAR
    invert_colormap: bool = False
    z1: float | None = None
    z2: float | None = None
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    rotation: float = 0.0
    flip_x: bool = False
    flip_y: bool = False
    align_wcs: bool = False
    contrast: float = 1.0
    brightness: float = 0.0
    crop_center_x: float | None = None
    crop_center_y: float | None = None
    crop_width: float | None = None
    crop_height: float | None = None
    frame_type: str = "base"
    rgb_channels: dict[str, np.ndarray | None] = None
    rgb_view: dict[str, bool] = None
    rgb_source_frame_ids: dict[str, int | None] = None
    rgb_current_channel: str = "red"
    rgb_channel_scale: dict[str, ScaleAlgorithm] = None
    rgb_channel_z1: dict[str, float | None] = None
    rgb_channel_z2: dict[str, float | None] = None
    rgb_channel_contrast: dict[str, float] = None
    rgb_channel_brightness: dict[str, float] = None

    def __post_init__(self):
        if self.regions is None:
            self.regions = []
        if self.rgb_channels is None:
            self.rgb_channels = {"red": None, "green": None, "blue": None}
        if self.rgb_view is None:
            self.rgb_view = {"red": True, "green": True, "blue": True}
        if self.rgb_source_frame_ids is None:
            self.rgb_source_frame_ids = {"red": None, "green": None, "blue": None}
        if self.rgb_channel_scale is None:
            self.rgb_channel_scale = {
                "red": ScaleAlgorithm.LINEAR,
                "green": ScaleAlgorithm.LINEAR,
                "blue": ScaleAlgorithm.LINEAR,
            }
        if self.rgb_channel_z1 is None:
            self.rgb_channel_z1 = {"red": None, "green": None, "blue": None}
        if self.rgb_channel_z2 is None:
            self.rgb_channel_z2 = {"red": None, "green": None, "blue": None}
        if self.rgb_channel_contrast is None:
            self.rgb_channel_contrast = {"red": 1.0, "green": 1.0, "blue": 1.0}
        if self.rgb_channel_brightness is None:
            self.rgb_channel_brightness = {"red": 0.0, "green": 0.0, "blue": 0.0}

    @property
    def has_data(self) -> bool:
        """Check if frame has image data."""
        return self.image_data is not None

    @property
    def filename(self) -> str:
        """Get filename or 'Empty'."""
        if self.filepath:
            return self.filepath.name
        return f"Frame {self.frame_id}"
