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

"""Parser for .lut colormap files."""

from pathlib import Path
from typing import Union, List, Tuple
import numpy as np
from numpy.typing import NDArray

from .colormap import Colormap


def parse_lut_file(
    filepath: Union[str, Path],
    name: str = None,
) -> Colormap:
    """Parse a .lut colormap file.

    LUT files contain lookup table data with RGB values.
    Supported formats:
    - 3 columns: R G B values (0-255 or 0.0-1.0)
    - Single column: grayscale values

    Args:
        filepath: Path to the .lut file.
        name: Optional name for the colormap. Defaults to filename stem.

    Returns:
        Colormap object.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is invalid.
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"LUT file not found: {filepath}")

    if name is None:
        name = filepath.stem

    colors: List[Tuple[float, float, float]] = []

    with open(filepath, "r") as f:
        for line_num, line in enumerate(f, 1):
            # Skip comments and empty lines
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue

            # Parse values
            try:
                values = [float(v) for v in line.split()]
            except ValueError as e:
                raise ValueError(
                    f"Invalid value on line {line_num}: {line}"
                ) from e

            if len(values) == 3:
                r, g, b = values
            elif len(values) == 1:
                r = g = b = values[0]
            elif len(values) == 4:
                # RGBA format - ignore alpha
                r, g, b = values[:3]
            else:
                raise ValueError(
                    f"Invalid number of values on line {line_num}: "
                    f"expected 1, 3, or 4, got {len(values)}"
                )

            colors.append((r, g, b))

    if not colors:
        raise ValueError(f"No color data found in LUT file: {filepath}")

    # Convert to numpy array
    color_array: NDArray[np.floating] = np.array(colors, dtype=np.float64)

    # Normalize if values are in 0-255 range
    if np.max(color_array) > 1.0:
        color_array = color_array / 255.0

    # Clip to valid range
    color_array = np.clip(color_array, 0.0, 1.0)

    return Colormap(name, color_array)


def save_lut_file(
    colormap: Colormap,
    filepath: Union[str, Path],
    format: str = "float",
) -> None:
    """Save a colormap to a .lut file.

    Args:
        colormap: Colormap to save.
        filepath: Path to the output .lut file.
        format: Output format - "float" (0.0-1.0) or "int" (0-255).

    Raises:
        ValueError: If format is invalid.
    """
    filepath = Path(filepath)

    if format not in ("float", "int"):
        raise ValueError(f"Invalid format: {format}. Use 'float' or 'int'.")

    with open(filepath, "w") as f:
        f.write(f"# LUT colormap: {colormap.name}\n")
        f.write(f"# {len(colormap.colors)} colors\n")

        for r, g, b in colormap.colors:
            if format == "int":
                f.write(f"{int(r * 255)} {int(g * 255)} {int(b * 255)}\n")
            else:
                f.write(f"{r:.6f} {g:.6f} {b:.6f}\n")
