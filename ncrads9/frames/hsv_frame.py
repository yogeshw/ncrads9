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

"""HSVFrame class for HSV compositing."""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray

from .frame import Frame


@dataclass
class HSVChannelSettings:
    """Settings for an individual HSV channel."""

    visible: bool = True
    scale_min: Optional[float] = None
    scale_max: Optional[float] = None


class HSVFrame:
    """Frame for HSV (Hue, Saturation, Value) compositing."""

    def __init__(self, frame_id: int, name: str = "") -> None:
        """Initialize an HSVFrame.

        Args:
            frame_id: Unique identifier for the frame.
            name: Display name for the frame.
        """
        self._frame_id = frame_id
        self._name = name or f"HSV Frame {frame_id}"
        self._hue_frame: Optional[Frame] = None
        self._saturation_frame: Optional[Frame] = None
        self._value_frame: Optional[Frame] = None
        self._hue_settings = HSVChannelSettings()
        self._saturation_settings = HSVChannelSettings()
        self._value_settings = HSVChannelSettings()
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
    def hue_frame(self) -> Optional[Frame]:
        """Return the hue channel frame."""
        return self._hue_frame

    @hue_frame.setter
    def hue_frame(self, frame: Optional[Frame]) -> None:
        """Set the hue channel frame."""
        self._hue_frame = frame
        self._composite = None

    @property
    def saturation_frame(self) -> Optional[Frame]:
        """Return the saturation channel frame."""
        return self._saturation_frame

    @saturation_frame.setter
    def saturation_frame(self, frame: Optional[Frame]) -> None:
        """Set the saturation channel frame."""
        self._saturation_frame = frame
        self._composite = None

    @property
    def value_frame(self) -> Optional[Frame]:
        """Return the value channel frame."""
        return self._value_frame

    @value_frame.setter
    def value_frame(self, frame: Optional[Frame]) -> None:
        """Set the value channel frame."""
        self._value_frame = frame
        self._composite = None

    @property
    def hue_settings(self) -> HSVChannelSettings:
        """Return the hue channel settings."""
        return self._hue_settings

    @property
    def saturation_settings(self) -> HSVChannelSettings:
        """Return the saturation channel settings."""
        return self._saturation_settings

    @property
    def value_settings(self) -> HSVChannelSettings:
        """Return the value channel settings."""
        return self._value_settings

    def set_channel(self, channel: str, frame: Optional[Frame]) -> None:
        """Set a channel frame.

        Args:
            channel: Channel name ('hue', 'saturation', or 'value').
            frame: The frame to use for this channel.
        """
        channel_lower = channel.lower()
        if channel_lower in ("hue", "h"):
            self.hue_frame = frame
        elif channel_lower in ("saturation", "s"):
            self.saturation_frame = frame
        elif channel_lower in ("value", "v"):
            self.value_frame = frame
        else:
            raise ValueError(f"Unknown channel: {channel}")

    def get_channel(self, channel: str) -> Optional[Frame]:
        """Get a channel frame.

        Args:
            channel: Channel name ('hue', 'saturation', or 'value').

        Returns:
            The frame for this channel, or None.
        """
        channel_lower = channel.lower()
        if channel_lower in ("hue", "h"):
            return self._hue_frame
        elif channel_lower in ("saturation", "s"):
            return self._saturation_frame
        elif channel_lower in ("value", "v"):
            return self._value_frame
        else:
            raise ValueError(f"Unknown channel: {channel}")

    def _normalize_channel(
        self,
        data: NDArray[np.floating[Any]],
        settings: HSVChannelSettings,
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
        return np.clip(normalized, 0.0, 1.0)

    def compose(self) -> Optional[NDArray[np.uint8]]:
        """Compose the RGB image from the HSV channel frames.

        Returns:
            RGB image as uint8 array with shape (height, width, 3), or None.
        """
        # Determine output shape from available frames
        shape: Optional[tuple[int, ...]] = None
        for frame in [self._hue_frame, self._saturation_frame, self._value_frame]:
            if frame is not None and frame.image_data is not None:
                shape = frame.image_data.shape[:2]
                break

        if shape is None:
            return None

        # Default values for HSV
        h_data = np.zeros(shape, dtype=np.float64)
        s_data = np.ones(shape, dtype=np.float64)
        v_data = np.ones(shape, dtype=np.float64)

        # Process each channel
        if (
            self._hue_frame is not None
            and self._hue_frame.image_data is not None
            and self._hue_settings.visible
        ):
            data = self._hue_frame.image_data.astype(np.float64)
            if data.shape[:2] == shape:
                h_data = self._normalize_channel(data, self._hue_settings)

        if (
            self._saturation_frame is not None
            and self._saturation_frame.image_data is not None
            and self._saturation_settings.visible
        ):
            data = self._saturation_frame.image_data.astype(np.float64)
            if data.shape[:2] == shape:
                s_data = self._normalize_channel(data, self._saturation_settings)

        if (
            self._value_frame is not None
            and self._value_frame.image_data is not None
            and self._value_settings.visible
        ):
            data = self._value_frame.image_data.astype(np.float64)
            if data.shape[:2] == shape:
                v_data = self._normalize_channel(data, self._value_settings)

        # Convert HSV to RGB
        rgb = np.zeros((*shape, 3), dtype=np.float64)
        for i in range(shape[0]):
            for j in range(shape[1]):
                r, g, b = colorsys.hsv_to_rgb(h_data[i, j], s_data[i, j], v_data[i, j])
                rgb[i, j] = [r, g, b]

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
        self._hue_frame = None
        self._saturation_frame = None
        self._value_frame = None
        self._composite = None
