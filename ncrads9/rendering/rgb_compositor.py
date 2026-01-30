# NCRADS9 - RGB Compositor
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
RGB compositor for multi-channel astronomical image compositing.

Provides tools for combining multiple image frames into RGB, HLS, or HSV
composite images, commonly used in astronomical visualization.
"""

from enum import Enum, auto
from typing import Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from .scale_algorithms import ScaleAlgorithm, apply_scale


class ColorSpace(Enum):
    """Enumeration of supported color spaces."""

    RGB = auto()
    HLS = auto()
    HSV = auto()


class RGBCompositor:
    """
    Compositor for creating RGB images from multiple frames.

    Combines separate image frames (e.g., from different filters)
    into composite color images using RGB, HLS, or HSV color spaces.

    Attributes:
        color_space: Current color space mode.
    """

    def __init__(self, color_space: ColorSpace = ColorSpace.RGB) -> None:
        """
        Initialize the RGB compositor.

        Args:
            color_space: Color space for compositing (default RGB).
        """
        self._color_space: ColorSpace = color_space
        self._red_frame: Optional[NDArray[np.float32]] = None
        self._green_frame: Optional[NDArray[np.float32]] = None
        self._blue_frame: Optional[NDArray[np.float32]] = None
        self._red_scale: ScaleAlgorithm = ScaleAlgorithm.LINEAR
        self._green_scale: ScaleAlgorithm = ScaleAlgorithm.LINEAR
        self._blue_scale: ScaleAlgorithm = ScaleAlgorithm.LINEAR
        self._red_limits: Tuple[float, float] = (0.0, 1.0)
        self._green_limits: Tuple[float, float] = (0.0, 1.0)
        self._blue_limits: Tuple[float, float] = (0.0, 1.0)

    @property
    def color_space(self) -> ColorSpace:
        """Get current color space."""
        return self._color_space

    @color_space.setter
    def color_space(self, value: ColorSpace) -> None:
        """Set color space."""
        self._color_space = value

    def set_red_frame(
        self,
        data: NDArray[np.float32],
        scale: ScaleAlgorithm = ScaleAlgorithm.LINEAR,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
    ) -> None:
        """
        Set the red channel frame.

        Args:
            data: Image data for red channel.
            scale: Scaling algorithm to apply.
            vmin: Minimum value for scaling.
            vmax: Maximum value for scaling.
        """
        self._red_frame = data.astype(np.float32)
        self._red_scale = scale
        vmin = vmin if vmin is not None else float(np.nanmin(data))
        vmax = vmax if vmax is not None else float(np.nanmax(data))
        self._red_limits = (vmin, vmax)

    def set_green_frame(
        self,
        data: NDArray[np.float32],
        scale: ScaleAlgorithm = ScaleAlgorithm.LINEAR,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
    ) -> None:
        """
        Set the green channel frame.

        Args:
            data: Image data for green channel.
            scale: Scaling algorithm to apply.
            vmin: Minimum value for scaling.
            vmax: Maximum value for scaling.
        """
        self._green_frame = data.astype(np.float32)
        self._green_scale = scale
        vmin = vmin if vmin is not None else float(np.nanmin(data))
        vmax = vmax if vmax is not None else float(np.nanmax(data))
        self._green_limits = (vmin, vmax)

    def set_blue_frame(
        self,
        data: NDArray[np.float32],
        scale: ScaleAlgorithm = ScaleAlgorithm.LINEAR,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
    ) -> None:
        """
        Set the blue channel frame.

        Args:
            data: Image data for blue channel.
            scale: Scaling algorithm to apply.
            vmin: Minimum value for scaling.
            vmax: Maximum value for scaling.
        """
        self._blue_frame = data.astype(np.float32)
        self._blue_scale = scale
        vmin = vmin if vmin is not None else float(np.nanmin(data))
        vmax = vmax if vmax is not None else float(np.nanmax(data))
        self._blue_limits = (vmin, vmax)

    def clear_frames(self) -> None:
        """Clear all frame data."""
        self._red_frame = None
        self._green_frame = None
        self._blue_frame = None

    def compose(self) -> NDArray[np.uint8]:
        """
        Compose the RGB image from set frames.

        Returns:
            RGBA image array with shape (H, W, 4).

        Raises:
            ValueError: If no frames are set or frame dimensions don't match.
        """
        frames = [self._red_frame, self._green_frame, self._blue_frame]
        valid_frames = [f for f in frames if f is not None]

        if not valid_frames:
            raise ValueError("At least one frame must be set")

        # Get shape from first valid frame
        shape = valid_frames[0].shape
        for f in valid_frames[1:]:
            if f.shape != shape:
                raise ValueError("All frames must have the same dimensions")

        # Scale each channel
        red = self._scale_channel(
            self._red_frame, self._red_scale, self._red_limits, shape
        )
        green = self._scale_channel(
            self._green_frame, self._green_scale, self._green_limits, shape
        )
        blue = self._scale_channel(
            self._blue_frame, self._blue_scale, self._blue_limits, shape
        )

        # Compose based on color space
        if self._color_space == ColorSpace.RGB:
            return self._compose_rgb(red, green, blue)
        elif self._color_space == ColorSpace.HLS:
            return self._compose_hls(red, green, blue)
        elif self._color_space == ColorSpace.HSV:
            return self._compose_hsv(red, green, blue)
        else:
            return self._compose_rgb(red, green, blue)

    def _scale_channel(
        self,
        data: Optional[NDArray[np.float32]],
        scale: ScaleAlgorithm,
        limits: Tuple[float, float],
        shape: Tuple[int, ...],
    ) -> NDArray[np.float32]:
        """Scale a single channel or return zeros if None."""
        if data is None:
            return np.zeros(shape, dtype=np.float32)
        return apply_scale(data, scale, limits[0], limits[1])

    def _compose_rgb(
        self,
        red: NDArray[np.float32],
        green: NDArray[np.float32],
        blue: NDArray[np.float32],
    ) -> NDArray[np.uint8]:
        """Compose RGB image."""
        result = np.zeros((*red.shape, 4), dtype=np.uint8)
        result[:, :, 0] = (np.clip(red, 0, 1) * 255).astype(np.uint8)
        result[:, :, 1] = (np.clip(green, 0, 1) * 255).astype(np.uint8)
        result[:, :, 2] = (np.clip(blue, 0, 1) * 255).astype(np.uint8)
        result[:, :, 3] = 255
        return result

    def _compose_hls(
        self,
        h_data: NDArray[np.float32],
        l_data: NDArray[np.float32],
        s_data: NDArray[np.float32],
    ) -> NDArray[np.uint8]:
        """
        Compose image from HLS color space.

        Args:
            h_data: Hue channel [0, 1].
            l_data: Lightness channel [0, 1].
            s_data: Saturation channel [0, 1].

        Returns:
            RGBA image.
        """
        result = np.zeros((*h_data.shape, 4), dtype=np.uint8)

        for i in range(h_data.shape[0]):
            for j in range(h_data.shape[1]):
                r, g, b = self._hls_to_rgb(h_data[i, j], l_data[i, j], s_data[i, j])
                result[i, j, 0] = int(r * 255)
                result[i, j, 1] = int(g * 255)
                result[i, j, 2] = int(b * 255)
                result[i, j, 3] = 255

        return result

    def _compose_hsv(
        self,
        h_data: NDArray[np.float32],
        s_data: NDArray[np.float32],
        v_data: NDArray[np.float32],
    ) -> NDArray[np.uint8]:
        """
        Compose image from HSV color space.

        Args:
            h_data: Hue channel [0, 1].
            s_data: Saturation channel [0, 1].
            v_data: Value channel [0, 1].

        Returns:
            RGBA image.
        """
        result = np.zeros((*h_data.shape, 4), dtype=np.uint8)

        for i in range(h_data.shape[0]):
            for j in range(h_data.shape[1]):
                r, g, b = self._hsv_to_rgb(h_data[i, j], s_data[i, j], v_data[i, j])
                result[i, j, 0] = int(r * 255)
                result[i, j, 1] = int(g * 255)
                result[i, j, 2] = int(b * 255)
                result[i, j, 3] = 255

        return result

    @staticmethod
    def _hls_to_rgb(h: float, l: float, s: float) -> Tuple[float, float, float]:
        """
        Convert HLS to RGB.

        Args:
            h: Hue [0, 1].
            l: Lightness [0, 1].
            s: Saturation [0, 1].

        Returns:
            Tuple of (r, g, b) in [0, 1].
        """
        if s == 0.0:
            return (l, l, l)

        def hue_to_rgb(p: float, q: float, t: float) -> float:
            if t < 0:
                t += 1
            if t > 1:
                t -= 1
            if t < 1 / 6:
                return p + (q - p) * 6 * t
            if t < 1 / 2:
                return q
            if t < 2 / 3:
                return p + (q - p) * (2 / 3 - t) * 6
            return p

        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q

        r = hue_to_rgb(p, q, h + 1 / 3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1 / 3)

        return (r, g, b)

    @staticmethod
    def _hsv_to_rgb(h: float, s: float, v: float) -> Tuple[float, float, float]:
        """
        Convert HSV to RGB.

        Args:
            h: Hue [0, 1].
            s: Saturation [0, 1].
            v: Value [0, 1].

        Returns:
            Tuple of (r, g, b) in [0, 1].
        """
        if s == 0.0:
            return (v, v, v)

        i = int(h * 6.0)
        f = (h * 6.0) - i
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        i = i % 6

        if i == 0:
            return (v, t, p)
        elif i == 1:
            return (q, v, p)
        elif i == 2:
            return (p, v, t)
        elif i == 3:
            return (p, q, v)
        elif i == 4:
            return (t, p, v)
        else:
            return (v, p, q)

    def compose_lupton(
        self,
        softening: float = 1.0,
        stretch: float = 5.0,
    ) -> NDArray[np.uint8]:
        """
        Create RGB composite using Lupton et al. (2004) algorithm.

        This algorithm is specifically designed for astronomical images
        and preserves color while mapping a large intensity range.

        Args:
            softening: Softening parameter Q (default 1.0).
            stretch: Linear stretch parameter (default 5.0).

        Returns:
            RGBA image array.
        """
        if self._red_frame is None or self._green_frame is None or self._blue_frame is None:
            raise ValueError("All three frames must be set for Lupton compositing")

        r = self._red_frame
        g = self._green_frame
        b = self._blue_frame

        # Calculate intensity
        intensity = (r + g + b) / 3.0

        # Apply asinh stretch
        stretched = np.arcsinh(softening * stretch * intensity) / (
            softening * np.arcsinh(softening * stretch)
        )

        # Scale RGB by stretched intensity
        with np.errstate(divide="ignore", invalid="ignore"):
            scale = np.where(intensity > 0, stretched / intensity, 0)

        r_out = np.clip(r * scale, 0, 1)
        g_out = np.clip(g * scale, 0, 1)
        b_out = np.clip(b * scale, 0, 1)

        return self._compose_rgb(r_out, g_out, b_out)
