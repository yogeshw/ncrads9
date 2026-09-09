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
Multi-channel frame types: RGB, HSV and HLS.

Each subclass differs from `Frame` in exactly one respect -- how its three
normalized channels combine into a displayed image -- so each is a thin
subclass overriding `compose`.

Channels arrive already normalized to [0, 1]: the display pipeline applies
each channel's own scale algorithm, clip limits, contrast and bias before
compositing. The actual colour-space maths lives in
`ncrads9.rendering.rgb_compositor`.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..rendering.rgb_compositor import compose_hls, compose_hsv, compose_rgb
from .frame import Frame


@dataclass
class RGBFrame(Frame):
    """A frame whose three channels are red, green and blue."""

    frame_type: str = "rgb"

    #: Channel labels as shown in the UI, in composition order.
    CHANNEL_LABELS: tuple[str, str, str] = ("Red", "Green", "Blue")

    def compose(
        self,
        normalized: dict[str, NDArray[np.floating] | None],
        view: dict[str, bool] | None = None,
    ) -> NDArray[np.uint8] | None:
        """Combine normalized channels into an 8-bit RGB image.

        Args:
            normalized: Channel name -> plane in [0, 1], or None if unassigned.
            view: Channel name -> visible. Defaults to all visible.

        Returns:
            An (h, w, 3) uint8 array, or None if no channel is assigned.
        """
        return compose_rgb(normalized, view if view is not None else self.rgb_view)


@dataclass
class HSVFrame(RGBFrame):
    """A frame whose three channels are hue, saturation and value."""

    frame_type: str = "hsv"

    CHANNEL_LABELS: tuple[str, str, str] = ("Hue", "Saturation", "Value")

    def compose(
        self,
        normalized: dict[str, NDArray[np.floating] | None],
        view: dict[str, bool] | None = None,
    ) -> NDArray[np.uint8] | None:
        """Combine normalized channels as HSV."""
        return compose_hsv(normalized, view if view is not None else self.rgb_view)


@dataclass
class HLSFrame(RGBFrame):
    """A frame whose three channels are hue, lightness and saturation."""

    frame_type: str = "hls"

    CHANNEL_LABELS: tuple[str, str, str] = ("Hue", "Lightness", "Saturation")

    def compose(
        self,
        normalized: dict[str, NDArray[np.floating] | None],
        view: dict[str, bool] | None = None,
    ) -> NDArray[np.uint8] | None:
        """Combine normalized channels as HLS."""
        return compose_hls(normalized, view if view is not None else self.rgb_view)
