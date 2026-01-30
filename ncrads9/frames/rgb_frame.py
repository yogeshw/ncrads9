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

"""RGBFrame class for RGB compositing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray

from .frame import Frame


@dataclass
class ChannelSettings:
    """Settings for an individual RGB channel."""

    visible: bool = True
    scale_min: Optional[float] = None
    scale_max: Optional[float] = None
    bias: float = 0.5
    contrast: float = 1.0


class RGBFrame:
    """Frame for RGB compositing from multiple image frames."""

    def __init__(self, frame_id: int, name: str = "") -> None:
        """Initialize an RGBFrame.

        Args:
            frame_id: Unique identifier for the frame.
            name: Display name for the frame.
        """
        self._frame_id = frame_id
        self._name = name or f"RGB Frame {frame_id}"
        self._red_frame: Optional[Frame] = None
        self._green_frame: Optional[Frame] = None
        self._blue_frame: Optional[Frame] = None
        self._red_settings = ChannelSettings()
        self._green_settings = ChannelSettings()
        self._blue_settings = ChannelSettings()
        self._composite: Optional[NDArray[np.uint8]] = None

    @property
    def frame_id(self) -> int:
        """Return the frame ID."""
        return self._frame_id

    @property
    def name(self) -> str:
        """Return the frame name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set the frame name."""
        self._name = value

    @property
    def red_frame(self) -> Optional[Frame]:
        """Return the red channel frame."""
        return self._red_frame

    @red_frame.setter
    def red_frame(self, frame: Optional[Frame]) -> None:
        """Set the red channel frame."""
        self._red_frame = frame
        self._composite = None

    @property
    def green_frame(self) -> Optional[Frame]:
        """Return the green channel frame."""
        return self._green_frame

    @green_frame.setter
    def green_frame(self, frame: Optional[Frame]) -> None:
        """Set the green channel frame."""
        self._green_frame = frame
        self._composite = None

    @property
    def blue_frame(self) -> Optional[Frame]:
        """Return the blue channel frame."""
        return self._blue_frame

    @blue_frame.setter
    def blue_frame(self, frame: Optional[Frame]) -> None:
        """Set the blue channel frame."""
        self._blue_frame = frame
        self._composite = None

    @property
    def red_settings(self) -> ChannelSettings:
        """Return the red channel settings."""
        return self._red_settings

    @property
    def green_settings(self) -> ChannelSettings:
        """Return the green channel settings."""
        return self._green_settings

    @property
    def blue_settings(self) -> ChannelSettings:
        """Return the blue channel settings."""
        return self._blue_settings

    def set_channel(
        self, channel: str, frame: Optional[Frame]
    ) -> None:
        """Set a channel frame.

        Args:
            channel: Channel name ('red', 'green', or 'blue').
            frame: The frame to use for this channel.
        """
        channel_lower = channel.lower()
        if channel_lower == "red":
            self.red_frame = frame
        elif channel_lower == "green":
            self.green_frame = frame
        elif channel_lower == "blue":
            self.blue_frame = frame
        else:
            raise ValueError(f"Unknown channel: {channel}")

    def get_channel(self, channel: str) -> Optional[Frame]:
        """Get a channel frame.

        Args:
            channel: Channel name ('red', 'green', or 'blue').

        Returns:
            The frame for this channel, or None.
        """
        channel_lower = channel.lower()
        if channel_lower == "red":
            return self._red_frame
        elif channel_lower == "green":
            return self._green_frame
        elif channel_lower == "blue":
            return self._blue_frame
        else:
            raise ValueError(f"Unknown channel: {channel}")

    def get_channel_settings(self, channel: str) -> ChannelSettings:
        """Get settings for a channel.

        Args:
            channel: Channel name ('red', 'green', or 'blue').

        Returns:
            The settings for this channel.
        """
        channel_lower = channel.lower()
        if channel_lower == "red":
            return self._red_settings
        elif channel_lower == "green":
            return self._green_settings
        elif channel_lower == "blue":
            return self._blue_settings
        else:
            raise ValueError(f"Unknown channel: {channel}")

    def _normalize_channel(
        self,
        data: NDArray[np.floating[Any]],
        settings: ChannelSettings,
    ) -> NDArray[np.floating[Any]]:
        """Normalize channel data to 0-1 range.

        Args:
            data: The image data to normalize.
            settings: Channel settings for normalization.

        Returns:
            Normalized data array.
        """
        vmin = settings.scale_min if settings.scale_min is not None else np.nanmin(data)
        vmax = settings.scale_max if settings.scale_max is not None else np.nanmax(data)

        if vmax == vmin:
            return np.zeros_like(data)

        normalized = (data - vmin) / (vmax - vmin)
        normalized = np.clip(normalized, 0.0, 1.0)

        # Apply bias and contrast
        normalized = (normalized - settings.bias) * settings.contrast + 0.5
        normalized = np.clip(normalized, 0.0, 1.0)

        return normalized

    def compose(self) -> Optional[NDArray[np.uint8]]:
        """Compose the RGB image from the channel frames.

        Returns:
            RGB image as uint8 array with shape (height, width, 3), or None.
        """
        # Determine output shape from available frames
        shape: Optional[tuple[int, ...]] = None
        for frame in [self._red_frame, self._green_frame, self._blue_frame]:
            if frame is not None and frame.image_data is not None:
                shape = frame.image_data.shape[:2]
                break

        if shape is None:
            return None

        rgb = np.zeros((*shape, 3), dtype=np.float64)

        # Process each channel
        channels = [
            (self._red_frame, self._red_settings, 0),
            (self._green_frame, self._green_settings, 1),
            (self._blue_frame, self._blue_settings, 2),
        ]

        for frame, settings, index in channels:
            if frame is not None and frame.image_data is not None and settings.visible:
                data = frame.image_data.astype(np.float64)
                if data.shape[:2] == shape:
                    rgb[:, :, index] = self._normalize_channel(data, settings)

        self._composite = (rgb * 255).astype(np.uint8)
        return self._composite

    @property
    def composite(self) -> Optional[NDArray[np.uint8]]:
        """Return the cached composite image, composing if necessary."""
        if self._composite is None:
            return self.compose()
        return self._composite

    def invalidate(self) -> None:
        """Invalidate the cached composite image."""
        self._composite = None

    def clear(self) -> None:
        """Clear all channel frames."""
        self._red_frame = None
        self._green_frame = None
        self._blue_frame = None
        self._composite = None
