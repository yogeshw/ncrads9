# NCRADS9 - NCRA DS9 Viewer
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
Three-channel composition for RGB, HSV and HLS frames.

Every function here takes channels that are *already normalized* to [0, 1] --
scaling, clipping, contrast and bias belong to the display pipeline, which
applies them per channel before compositing. The job here is only to combine
three normalized planes into 8-bit RGB.

Everything is vectorized. The previous implementation of this module converted
HSV and HLS a pixel at a time in a Python double loop, which is around
16 million iterations for a 4k x 4k cube; it was never called, so nobody hit
it.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

#: Channel names, in composition order.
CHANNELS: tuple[str, str, str] = ("red", "green", "blue")


def _as_planes(
    channels: dict[str, NDArray[np.floating] | None],
    view: dict[str, bool] | None = None,
) -> tuple[NDArray[np.float32], ...] | None:
    """Return three [0, 1] planes of a common shape, or None if there are none.

    Channels that are absent, hidden, or shaped unlike the first present
    channel contribute zeros, which is what DS9 shows for an unassigned
    channel.
    """
    present = [data for data in channels.values() if data is not None]
    if not present:
        return None

    shape = present[0].shape[:2]
    planes = []
    for name in CHANNELS:
        data = channels.get(name)
        visible = True if view is None else view.get(name, True)
        if data is None or not visible or data.shape[:2] != shape:
            planes.append(np.zeros(shape, dtype=np.float32))
        else:
            planes.append(np.clip(np.asarray(data, dtype=np.float32), 0.0, 1.0))
    return tuple(planes)


def _to_uint8(rgb: NDArray[np.floating]) -> NDArray[np.uint8]:
    """Clip a float RGB cube to [0, 1] and scale to 8-bit."""
    return (np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8)


def compose_rgb(
    channels: dict[str, NDArray[np.floating] | None],
    view: dict[str, bool] | None = None,
) -> NDArray[np.uint8] | None:
    """Stack normalized red, green and blue planes into an 8-bit RGB image."""
    planes = _as_planes(channels, view)
    if planes is None:
        return None
    return _to_uint8(np.stack(planes, axis=-1))


def hsv_to_rgb(
    hue: NDArray[np.floating],
    saturation: NDArray[np.floating],
    value: NDArray[np.floating],
) -> NDArray[np.float32]:
    """Vectorized HSV -> RGB. All inputs and outputs in [0, 1]."""
    h = np.asarray(hue, dtype=np.float32) % 1.0
    s = np.clip(np.asarray(saturation, dtype=np.float32), 0.0, 1.0)
    v = np.clip(np.asarray(value, dtype=np.float32), 0.0, 1.0)

    sector = np.floor(h * 6.0)
    offset = h * 6.0 - sector
    p = v * (1.0 - s)
    q = v * (1.0 - s * offset)
    t = v * (1.0 - s * (1.0 - offset))

    index = sector.astype(np.int32) % 6
    # Each row is (r, g, b) for one of the six hue sectors.
    r = np.select([index == 0, index == 1, index == 2, index == 3, index == 4], [v, q, p, p, t], default=v)
    g = np.select([index == 0, index == 1, index == 2, index == 3, index == 4], [t, v, v, q, p], default=p)
    b = np.select([index == 0, index == 1, index == 2, index == 3, index == 4], [p, p, t, v, v], default=q)
    return np.stack([r, g, b], axis=-1)


def hls_to_rgb(
    hue: NDArray[np.floating],
    lightness: NDArray[np.floating],
    saturation: NDArray[np.floating],
) -> NDArray[np.float32]:
    """Vectorized HLS -> RGB. All inputs and outputs in [0, 1]."""
    h = np.asarray(hue, dtype=np.float32) % 1.0
    lightness_arr = np.clip(np.asarray(lightness, dtype=np.float32), 0.0, 1.0)
    s = np.clip(np.asarray(saturation, dtype=np.float32), 0.0, 1.0)

    chroma = (1.0 - np.abs(2.0 * lightness_arr - 1.0)) * s
    h6 = h * 6.0
    x = chroma * (1.0 - np.abs(h6 % 2.0 - 1.0))
    zero = np.zeros_like(chroma)

    index = np.floor(h6).astype(np.int32) % 6
    conds = [index == 0, index == 1, index == 2, index == 3, index == 4]
    r = np.select(conds, [chroma, x, zero, zero, x], default=chroma)
    g = np.select(conds, [x, chroma, chroma, x, zero], default=zero)
    b = np.select(conds, [zero, zero, x, chroma, chroma], default=x)

    m = lightness_arr - chroma / 2.0
    return np.stack([r + m, g + m, b + m], axis=-1)


def compose_hsv(
    channels: dict[str, NDArray[np.floating] | None],
    view: dict[str, bool] | None = None,
) -> NDArray[np.uint8] | None:
    """Treat the three channels as hue, saturation and value."""
    planes = _as_planes(channels, view)
    if planes is None:
        return None
    return _to_uint8(hsv_to_rgb(*planes))


def compose_hls(
    channels: dict[str, NDArray[np.floating] | None],
    view: dict[str, bool] | None = None,
) -> NDArray[np.uint8] | None:
    """Treat the three channels as hue, lightness and saturation."""
    planes = _as_planes(channels, view)
    if planes is None:
        return None
    return _to_uint8(hls_to_rgb(*planes))
