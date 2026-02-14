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

"""DS9 builtin colormaps for ncrads9."""

from typing import Dict, List, Optional, Tuple
import numpy as np
from numpy.typing import NDArray

from .colormap import Colormap


def _generate_from_stops(stops: NDArray[np.floating], n: int = 256) -> NDArray[np.floating]:
    """Generate a colormap by interpolating RGB control stops."""
    x = np.linspace(0.0, 1.0, n)
    stop_x = np.linspace(0.0, 1.0, len(stops))
    return np.column_stack(
        [
            np.interp(x, stop_x, stops[:, 0]),
            np.interp(x, stop_x, stops[:, 1]),
            np.interp(x, stop_x, stops[:, 2]),
        ]
    )


def _generate_grey(n: int = 256) -> NDArray[np.floating]:
    """Generate grey/grayscale colormap."""
    v = np.linspace(0, 1, n)
    return np.column_stack([v, v, v])


def _generate_heat(n: int = 256) -> NDArray[np.floating]:
    """Generate heat colormap (black-red-yellow-white)."""
    colors = np.zeros((n, 3))
    for i in range(n):
        t = i / (n - 1)
        if t < 0.33:
            colors[i] = [t * 3, 0, 0]
        elif t < 0.67:
            colors[i] = [1, (t - 0.33) * 3, 0]
        else:
            colors[i] = [1, 1, (t - 0.67) * 3]
    return np.clip(colors, 0, 1)


def _generate_cool(n: int = 256) -> NDArray[np.floating]:
    """Generate cool colormap (cyan to magenta)."""
    t = np.linspace(0, 1, n)
    r = t
    g = 1 - t
    b = np.ones(n)
    return np.column_stack([r, g, b])


def _generate_rainbow(n: int = 256) -> NDArray[np.floating]:
    """Generate rainbow colormap."""
    colors = np.zeros((n, 3))
    for i in range(n):
        t = i / (n - 1)
        if t < 0.2:
            colors[i] = [1, t * 5, 0]
        elif t < 0.4:
            colors[i] = [1 - (t - 0.2) * 5, 1, 0]
        elif t < 0.6:
            colors[i] = [0, 1, (t - 0.4) * 5]
        elif t < 0.8:
            colors[i] = [0, 1 - (t - 0.6) * 5, 1]
        else:
            colors[i] = [(t - 0.8) * 5, 0, 1]
    return np.clip(colors, 0, 1)


def _generate_bb(n: int = 256) -> NDArray[np.floating]:
    """Generate bb (blackbody) colormap."""
    colors = np.zeros((n, 3))
    for i in range(n):
        t = i / (n - 1)
        # Black -> Red -> Orange -> Yellow -> White
        if t < 0.25:
            colors[i] = [t * 4, 0, 0]
        elif t < 0.5:
            colors[i] = [1, (t - 0.25) * 4, 0]
        elif t < 0.75:
            colors[i] = [1, 1, (t - 0.5) * 4]
        else:
            colors[i] = [1, 1, 1]
    return np.clip(colors, 0, 1)


def _generate_he(n: int = 256) -> NDArray[np.floating]:
    """Generate he (histogram equalization style) colormap."""
    colors = np.zeros((n, 3))
    for i in range(n):
        t = i / (n - 1)
        colors[i] = [
            0.5 * (1 + np.sin(2 * np.pi * t)),
            0.5 * (1 + np.sin(2 * np.pi * t + 2 * np.pi / 3)),
            0.5 * (1 + np.sin(2 * np.pi * t + 4 * np.pi / 3)),
        ]
    return colors


def _generate_aips0(n: int = 256) -> NDArray[np.floating]:
    """Generate AIPS0 colormap."""
    colors = np.zeros((n, 3))
    for i in range(n):
        t = i / (n - 1)
        # AIPS standard colormap
        if t < 0.125:
            colors[i] = [0, 0, t * 8]
        elif t < 0.25:
            colors[i] = [0, (t - 0.125) * 8, 1]
        elif t < 0.375:
            colors[i] = [0, 1, 1 - (t - 0.25) * 8]
        elif t < 0.5:
            colors[i] = [(t - 0.375) * 8, 1, 0]
        elif t < 0.625:
            colors[i] = [1, 1 - (t - 0.5) * 8, 0]
        elif t < 0.75:
            colors[i] = [1, 0, (t - 0.625) * 8]
        elif t < 0.875:
            colors[i] = [1, (t - 0.75) * 8, 1]
        else:
            colors[i] = [1, 1, 1]
    return np.clip(colors, 0, 1)


def _generate_staircase(n: int = 256) -> NDArray[np.floating]:
    """Generate staircase colormap with discrete steps."""
    num_steps = 16
    colors = np.zeros((n, 3))
    for i in range(n):
        step = int((i / n) * num_steps)
        t = step / (num_steps - 1)
        # Create distinct color steps
        colors[i] = [
            (step % 4) / 3,
            ((step // 4) % 4) / 3,
            (step // 8) / 2,
        ]
    return np.clip(colors, 0, 1)


def _generate_color(n: int = 256) -> NDArray[np.floating]:
    """Generate color colormap."""
    colors = np.zeros((n, 3))
    for i in range(n):
        t = i / (n - 1)
        colors[i] = [
            np.abs(np.sin(t * np.pi)),
            np.abs(np.sin(t * np.pi + np.pi / 3)),
            np.abs(np.sin(t * np.pi + 2 * np.pi / 3)),
        ]
    return colors


def _generate_a(n: int = 256) -> NDArray[np.floating]:
    """Generate 'a' colormap (blue-white)."""
    t = np.linspace(0, 1, n)
    r = t
    g = t
    b = np.ones(n)
    return np.column_stack([r, g, b])


def _generate_b(n: int = 256) -> NDArray[np.floating]:
    """Generate 'b' colormap (red-white)."""
    t = np.linspace(0, 1, n)
    r = np.ones(n)
    g = t
    b = t
    return np.column_stack([r, g, b])


def _generate_sls(n: int = 256) -> NDArray[np.floating]:
    """Generate SLS (Smooth Linear Segmented) colormap."""
    colors = np.zeros((n, 3))
    for i in range(n):
        t = i / (n - 1)
        # Blue -> Cyan -> Green -> Yellow -> Red
        if t < 0.25:
            colors[i] = [0, t * 4, 1]
        elif t < 0.5:
            colors[i] = [0, 1, 1 - (t - 0.25) * 4]
        elif t < 0.75:
            colors[i] = [(t - 0.5) * 4, 1, 0]
        else:
            colors[i] = [1, 1 - (t - 0.75) * 4, 0]
    return np.clip(colors, 0, 1)


def _generate_hsv(n: int = 256) -> NDArray[np.floating]:
    """Generate HSV colormap."""
    colors = np.zeros((n, 3))
    for i in range(n):
        h = i / n
        # HSV to RGB conversion with S=1, V=1
        c = 1.0
        x = c * (1 - abs((h * 6) % 2 - 1))
        if h < 1 / 6:
            colors[i] = [c, x, 0]
        elif h < 2 / 6:
            colors[i] = [x, c, 0]
        elif h < 3 / 6:
            colors[i] = [0, c, x]
        elif h < 4 / 6:
            colors[i] = [0, x, c]
        elif h < 5 / 6:
            colors[i] = [x, 0, c]
        else:
            colors[i] = [c, 0, x]
    return colors


def _generate_standard(n: int = 256) -> NDArray[np.floating]:
    """Generate standard colormap."""
    return _generate_grey(n)


def _generate_red(n: int = 256) -> NDArray[np.floating]:
    """Generate red colormap."""
    t = np.linspace(0, 1, n)
    return np.column_stack([t, np.zeros(n), np.zeros(n)])


def _generate_green(n: int = 256) -> NDArray[np.floating]:
    """Generate green colormap."""
    t = np.linspace(0, 1, n)
    return np.column_stack([np.zeros(n), t, np.zeros(n)])


def _generate_blue(n: int = 256) -> NDArray[np.floating]:
    """Generate blue colormap."""
    t = np.linspace(0, 1, n)
    return np.column_stack([np.zeros(n), np.zeros(n), t])


def _generate_i8(n: int = 256) -> NDArray[np.floating]:
    """Generate I8 colormap."""
    colors = np.zeros((n, 3))
    for i in range(n):
        t = i / (n - 1)
        segment = int(t * 8)
        colors[i] = [
            (segment & 1) * 0.5 + t * 0.5,
            ((segment >> 1) & 1) * 0.5 + t * 0.5,
            ((segment >> 2) & 1) * 0.5 + t * 0.5,
        ]
    return np.clip(colors, 0, 1)


def _generate_viridis(n: int = 256) -> NDArray[np.floating]:
    """Generate viridis colormap (from DS9 cmap set)."""
    stops = np.array(
        [
            [0.267004, 0.004874, 0.329415],
            [0.253935, 0.265254, 0.529983],
            [0.163625, 0.471133, 0.558148],
            [0.134692, 0.658636, 0.517649],
            [0.477504, 0.821444, 0.318195],
            [0.993248, 0.906157, 0.143936],
        ],
        dtype=np.float64,
    )
    return _generate_from_stops(stops, n)


def _generate_plasma(n: int = 256) -> NDArray[np.floating]:
    """Generate plasma colormap (from DS9 cmap set)."""
    stops = np.array(
        [
            [0.050383, 0.029803, 0.527975],
            [0.417642, 0.000564, 0.658390],
            [0.692840, 0.165141, 0.564522],
            [0.881443, 0.392529, 0.383229],
            [0.988260, 0.652325, 0.211364],
            [0.940015, 0.975158, 0.131326],
        ],
        dtype=np.float64,
    )
    return _generate_from_stops(stops, n)


def _generate_inferno(n: int = 256) -> NDArray[np.floating]:
    """Generate inferno colormap (from DS9 cmap set)."""
    stops = np.array(
        [
            [0.001462, 0.000466, 0.013866],
            [0.141935, 0.040119, 0.324538],
            [0.364543, 0.071579, 0.431994],
            [0.609330, 0.178249, 0.450586],
            [0.851384, 0.346636, 0.280346],
            [0.987622, 0.645320, 0.039886],
            [0.988362, 0.998364, 0.644924],
        ],
        dtype=np.float64,
    )
    return _generate_from_stops(stops, n)


def _generate_magma(n: int = 256) -> NDArray[np.floating]:
    """Generate magma colormap (from DS9 cmap set)."""
    stops = np.array(
        [
            [0.001462, 0.000466, 0.013866],
            [0.171713, 0.067305, 0.370771],
            [0.445163, 0.122724, 0.506901],
            [0.716387, 0.214982, 0.475290],
            [0.944006, 0.377643, 0.365136],
            [0.997351, 0.676795, 0.429406],
            [0.987053, 0.991438, 0.749504],
        ],
        dtype=np.float64,
    )
    return _generate_from_stops(stops, n)


# Dictionary of colormap generator functions
_COLORMAP_GENERATORS: Dict[str, callable] = {
    "grey": _generate_grey,
    "gray": _generate_grey,
    "heat": _generate_heat,
    "cool": _generate_cool,
    "rainbow": _generate_rainbow,
    "bb": _generate_bb,
    "he": _generate_he,
    "aips0": _generate_aips0,
    "staircase": _generate_staircase,
    "color": _generate_color,
    "a": _generate_a,
    "b": _generate_b,
    "sls": _generate_sls,
    "hsv": _generate_hsv,
    "standard": _generate_standard,
    "red": _generate_red,
    "green": _generate_green,
    "blue": _generate_blue,
    "i8": _generate_i8,
    "viridis": _generate_viridis,
    "plasma": _generate_plasma,
    "inferno": _generate_inferno,
    "magma": _generate_magma,
}

# List of all builtin colormap names
BUILTIN_COLORMAPS: List[str] = list(_COLORMAP_GENERATORS.keys())


def get_builtin_colormap(name: str, n_colors: int = 256) -> Optional[Colormap]:
    """Get a builtin colormap by name.

    Args:
        name: Name of the colormap.
        n_colors: Number of colors in the colormap.

    Returns:
        Colormap object or None if name is not found.
    """
    name_lower = name.lower()
    if name_lower in _COLORMAP_GENERATORS:
        n_colors = max(2, int(n_colors))
        colors = _COLORMAP_GENERATORS[name_lower](n_colors)
        return Colormap(name_lower, colors)
    return None


def list_builtin_colormaps() -> List[str]:
    """Return list of available builtin colormap names.

    Returns:
        List of colormap names.
    """
    return BUILTIN_COLORMAPS.copy()


# Convenience aliases
get_colormap = get_builtin_colormap
list_colormaps = list_builtin_colormaps
