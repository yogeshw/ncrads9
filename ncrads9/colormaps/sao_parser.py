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

"""Parser for SAO DS9 .sao colormap files."""

from pathlib import Path
from typing import Union, List, Tuple, Optional
import numpy as np
from numpy.typing import NDArray

from .colormap import Colormap


def _interpolate_channel(
    control_points: List[Tuple[float, float]],
    n_colors: int,
) -> NDArray[np.floating]:
    """Interpolate a color channel from control points.

    Args:
        control_points: List of (position, value) tuples.
        n_colors: Number of output colors.

    Returns:
        Array of interpolated values.
    """
    if not control_points:
        return np.zeros(n_colors)

    # Sort by position
    control_points = sorted(control_points, key=lambda p: p[0])

    positions = np.array([p[0] for p in control_points])
    values = np.array([p[1] for p in control_points])

    # Output positions
    x = np.linspace(0, 1, n_colors)

    # Interpolate
    return np.interp(x, positions, values)


def parse_sao_file(
    filepath: Union[str, Path],
    name: Optional[str] = None,
    n_colors: int = 256,
) -> Colormap:
    """Parse a SAO DS9 .sao colormap file.

    SAO colormap files define color channels using control points
    with position and value pairs.

    Format:
        # Comment lines start with #
        COLOR_MODEL [RGB|HSV]
        RED:
        (position, value)
        ...
        GREEN:
        (position, value)
        ...
        BLUE:
        (position, value)
        ...

    Args:
        filepath: Path to the .sao file.
        name: Optional name for the colormap. Defaults to filename stem.
        n_colors: Number of colors in the output colormap.

    Returns:
        Colormap object.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is invalid.
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"SAO file not found: {filepath}")

    if name is None:
        name = filepath.stem

    # Parse control points for each channel
    red_points: List[Tuple[float, float]] = []
    green_points: List[Tuple[float, float]] = []
    blue_points: List[Tuple[float, float]] = []

    current_channel: Optional[str] = None
    color_model: str = "RGB"

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Check for color model
            if line.upper().startswith("COLOR_MODEL"):
                parts = line.split()
                if len(parts) >= 2:
                    color_model = parts[1].upper()
                continue

            # Check for channel headers
            line_upper = line.upper()
            if line_upper.startswith("RED") or line_upper == "R:":
                current_channel = "red"
                continue
            elif line_upper.startswith("GREEN") or line_upper == "G:":
                current_channel = "green"
                continue
            elif line_upper.startswith("BLUE") or line_upper == "B:":
                current_channel = "blue"
                continue
            elif line_upper.startswith("HUE") or line_upper == "H:":
                current_channel = "red"  # Map hue to red channel
                continue
            elif line_upper.startswith("SATURATION") or line_upper == "S:":
                current_channel = "green"  # Map saturation to green
                continue
            elif line_upper.startswith("VALUE") or line_upper == "V:":
                current_channel = "blue"  # Map value to blue
                continue

            # Parse control point
            if current_channel:
                # Handle format: (x, y) or x y or x,y
                line = line.replace("(", "").replace(")", "")
                line = line.replace(",", " ")
                parts = line.split()

                if len(parts) >= 2:
                    try:
                        pos = float(parts[0])
                        val = float(parts[1])
                        point = (pos, val)

                        if current_channel == "red":
                            red_points.append(point)
                        elif current_channel == "green":
                            green_points.append(point)
                        elif current_channel == "blue":
                            blue_points.append(point)
                    except ValueError:
                        continue

    # Ensure we have at least some control points
    if not red_points:
        red_points = [(0.0, 0.0), (1.0, 1.0)]
    if not green_points:
        green_points = [(0.0, 0.0), (1.0, 1.0)]
    if not blue_points:
        blue_points = [(0.0, 0.0), (1.0, 1.0)]

    # Interpolate channels
    red = _interpolate_channel(red_points, n_colors)
    green = _interpolate_channel(green_points, n_colors)
    blue = _interpolate_channel(blue_points, n_colors)

    # Handle HSV color model
    if color_model == "HSV":
        # Convert HSV to RGB
        colors = np.column_stack([red, green, blue])
        colors = _hsv_to_rgb(colors)
    else:
        colors = np.column_stack([red, green, blue])

    # Clip to valid range
    colors = np.clip(colors, 0.0, 1.0)

    return Colormap(name, colors)


def _hsv_to_rgb(hsv: NDArray[np.floating]) -> NDArray[np.floating]:
    """Convert HSV colors to RGB.

    Args:
        hsv: Array with shape (N, 3) containing H, S, V values in [0, 1].

    Returns:
        Array with shape (N, 3) containing R, G, B values in [0, 1].
    """
    h = hsv[:, 0]
    s = hsv[:, 1]
    v = hsv[:, 2]

    i = (h * 6).astype(int) % 6
    f = (h * 6) - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)

    rgb = np.zeros_like(hsv)

    mask = i == 0
    rgb[mask] = np.column_stack([v[mask], t[mask], p[mask]])
    mask = i == 1
    rgb[mask] = np.column_stack([q[mask], v[mask], p[mask]])
    mask = i == 2
    rgb[mask] = np.column_stack([p[mask], v[mask], t[mask]])
    mask = i == 3
    rgb[mask] = np.column_stack([p[mask], q[mask], v[mask]])
    mask = i == 4
    rgb[mask] = np.column_stack([t[mask], p[mask], v[mask]])
    mask = i == 5
    rgb[mask] = np.column_stack([v[mask], p[mask], q[mask]])

    return rgb


def save_sao_file(
    colormap: Colormap,
    filepath: Union[str, Path],
    n_control_points: int = 16,
) -> None:
    """Save a colormap to a SAO DS9 .sao file.

    Args:
        colormap: Colormap to save.
        filepath: Path to the output .sao file.
        n_control_points: Number of control points per channel.
    """
    filepath = Path(filepath)

    # Sample control points from colormap
    indices = np.linspace(0, len(colormap.colors) - 1, n_control_points).astype(int)
    positions = np.linspace(0, 1, n_control_points)

    with open(filepath, "w") as f:
        f.write(f"# SAO colormap: {colormap.name}\n")
        f.write("COLOR_MODEL RGB\n\n")

        f.write("RED:\n")
        for pos, idx in zip(positions, indices):
            f.write(f"({pos:.4f}, {colormap.colors[idx, 0]:.4f})\n")

        f.write("\nGREEN:\n")
        for pos, idx in zip(positions, indices):
            f.write(f"({pos:.4f}, {colormap.colors[idx, 1]:.4f})\n")

        f.write("\nBLUE:\n")
        for pos, idx in zip(positions, indices):
            f.write(f"({pos:.4f}, {colormap.colors[idx, 2]:.4f})\n")
