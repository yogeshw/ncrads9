"""
View transform helpers for rotated/flipped image display.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QTransform
from scipy import ndimage


def normalize_rotation(angle: float) -> float:
    """Normalize a rotation angle into the [0, 360) range."""
    value = float(angle) % 360.0
    return 0.0 if isclose(value, 360.0, abs_tol=1e-9) else value


def orientation_to_flags(orientation: str) -> tuple[bool, bool]:
    """Map DS9 orientation tokens to flip flags."""
    mapping = {
        "none": (False, False),
        "x": (True, False),
        "y": (False, True),
        "xy": (True, True),
    }
    return mapping.get(str(orientation).lower(), (False, False))


def flags_to_orientation(flip_x: bool, flip_y: bool) -> str:
    """Map flip flags to a DS9 orientation token."""
    if flip_x and flip_y:
        return "xy"
    if flip_x:
        return "x"
    if flip_y:
        return "y"
    return "none"


def transform_image_array(
    image: NDArray[np.generic],
    rotation: float,
    flip_x: bool,
    flip_y: bool,
) -> NDArray[np.generic]:
    """Apply the current display transform to a 2D or RGB image array."""
    transformed = image
    if flip_x:
        transformed = np.fliplr(transformed)
    if flip_y:
        transformed = np.flipud(transformed)

    angle = normalize_rotation(rotation)
    if isclose(angle, 0.0, abs_tol=1e-9):
        return np.ascontiguousarray(transformed)

    quarter_turn = angle / 90.0
    if isclose(quarter_turn, round(quarter_turn), abs_tol=1e-9):
        transformed = np.rot90(transformed, k=int(round(quarter_turn)) % 4)
        return np.ascontiguousarray(transformed)

    if transformed.ndim == 2:
        rotated = ndimage.rotate(
            transformed,
            angle,
            reshape=True,
            order=1,
            mode="nearest",
            prefilter=False,
        )
        return np.ascontiguousarray(rotated)

    channels = [
        ndimage.rotate(
            transformed[..., channel],
            angle,
            reshape=True,
            order=1,
            mode="nearest",
            prefilter=False,
        )
        for channel in range(transformed.shape[2])
    ]
    return np.ascontiguousarray(np.stack(channels, axis=-1))


@dataclass(frozen=True)
class DisplayTransform:
    """Coordinate transform between source and displayed image space."""

    width: int
    height: int
    rotation: float = 0.0
    flip_x: bool = False
    flip_y: bool = False

    def _base_transform(self) -> QTransform:
        cx = self.width / 2.0
        cy = self.height / 2.0
        transform = QTransform()
        transform.translate(cx, cy)
        transform.scale(-1.0 if self.flip_x else 1.0, -1.0 if self.flip_y else 1.0)
        transform.rotate(self.rotation)
        transform.translate(-cx, -cy)
        return transform

    def _bounds(self) -> tuple[float, float, float, float]:
        transform = self._base_transform()
        corners = (
            QPointF(0.0, 0.0),
            QPointF(float(self.width), 0.0),
            QPointF(0.0, float(self.height)),
            QPointF(float(self.width), float(self.height)),
        )
        mapped = [transform.map(point) for point in corners]
        min_x = min(point.x() for point in mapped)
        max_x = max(point.x() for point in mapped)
        min_y = min(point.y() for point in mapped)
        max_y = max(point.y() for point in mapped)
        return (min_x, min_y, max_x, max_y)

    @property
    def display_width(self) -> float:
        """Return the transformed display width in source-space pixels."""
        min_x, _, max_x, _ = self._bounds()
        return max(1.0, max_x - min_x)

    @property
    def display_height(self) -> float:
        """Return the transformed display height in source-space pixels."""
        _, min_y, _, max_y = self._bounds()
        return max(1.0, max_y - min_y)

    def source_to_display(self, x: float, y: float) -> tuple[float, float]:
        """Map source top-left coordinates to display top-left coordinates."""
        min_x, min_y, _, _ = self._bounds()
        mapped = self._base_transform().map(QPointF(float(x), float(y)))
        return (mapped.x() - min_x, mapped.y() - min_y)

    def display_to_source(self, x: float, y: float) -> tuple[float, float]:
        """Map display top-left coordinates back to source top-left coordinates."""
        min_x, min_y, _, _ = self._bounds()
        inverse, invertible = self._base_transform().inverted()
        if not invertible:
            return (float(x), float(y))
        mapped = inverse.map(QPointF(float(x) + min_x, float(y) + min_y))
        return (mapped.x(), mapped.y())

    def source_vector_to_display(self, dx: float, dy: float) -> tuple[float, float]:
        """Map a source-space y-up vector into display-space y-up coordinates."""
        if self.height <= 0:
            return (float(dx), float(dy))
        start_x = self.width / 2.0
        start_top_y = self.height / 2.0
        end_x = start_x + float(dx)
        end_top_y = start_top_y - float(dy)
        start_display = self.source_to_display(start_x, start_top_y)
        end_display = self.source_to_display(end_x, end_top_y)
        return (
            end_display[0] - start_display[0],
            -(end_display[1] - start_display[1]),
        )
