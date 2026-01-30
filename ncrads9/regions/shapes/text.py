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
Text region shape.

Author: Yogesh Wadadekar
"""

from typing import Any, Optional

from ..base_region import BaseRegion


class Text(BaseRegion):
    """A text annotation region."""

    def __init__(
        self,
        center: tuple[float, float],
        label: str,
        angle: float = 0.0,
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize a text region.

        Args:
            center: The (x, y) coordinates for the text position.
            label: The text string to display.
            angle: The rotation angle in degrees.
            color: The color of the text.
            width: The line width (not typically used for text).
            font: The font specification for the text.
            tags: Optional list of tags for grouping regions.
        """
        super().__init__(center, color, width, font, label, tags)
        self._label = label
        self._angle = angle

    @property
    def label(self) -> str:
        """Get the text label."""
        return self._label

    @label.setter
    def label(self, value: str) -> None:
        """Set the text label."""
        self._label = value
        self._text = value

    @property
    def angle(self) -> float:
        """Get the rotation angle in degrees."""
        return self._angle

    @angle.setter
    def angle(self, value: float) -> None:
        """Set the rotation angle in degrees."""
        self._angle = value

    def draw(self, context: Any) -> None:
        """
        Draw the text on the given context.

        Args:
            context: The drawing context.
        """
        pass

    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is near the text.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is within the text bounding box.
        """
        cx, cy = self.center
        text_width = len(self._label) * 8
        text_height = 12
        return (
            abs(x - cx) <= text_width / 2 and abs(y - cy) <= text_height / 2
        )

    def move(self, dx: float, dy: float) -> None:
        """
        Move the text by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the text (no-op for text regions).

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        pass

    def to_ds9_string(self) -> str:
        """
        Convert the text to a DS9 format string.

        Returns:
            The text as a DS9 format string.
        """
        cx, cy = self.center
        return f'text({cx},{cy}) # text={{{self._label}}}'

    def __repr__(self) -> str:
        """Return a string representation of the text."""
        return f"Text(center={self.center}, label={self._label!r})"
