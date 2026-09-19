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
Where the image sits on screen, as the coordinate grid needs to know it.

A coordinate grid is not drawn in the image's pixel frame; it is drawn in
the frame the reader is looking at. DS9 is explicit about this: `Grid2d::doit`
builds its AST plot on a frame set whose base domain is WIDGET, mapped to
IMAGE by `widgetToImage` -- so rotation, flips and zoom are all inside the
mapping, and the plot's box is an upright rectangle on the canvas
(`tksao/frame/grid2d.C`). The border, the numbers and the ticks therefore lie
along the screen's own edges however the image is turned, while the lines
themselves still follow the sky.

Computing the grid in image pixels instead gives a border that tilts with the
picture, numbers stacked along a diagonal, and ticks pointing off at the
rotation angle -- which is what this exists to stop.

The mapping here has to agree exactly with the one the overlays paint
through, `ui.view_transform.DisplayTransform`; `tests/unit/test_coordinate_grid.py`
holds the two together. It is repeated rather than imported because
`ncrads9.grid` is geometry and has no business importing a Qt widget module.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

#: cos and sin at the quarter turns, exactly. `math.cos(math.radians(90))` is
#: 6.1e-17, not zero, and a whole image width times that is still nothing --
#: but Qt's own `QTransform::rotate` special-cases the quarter turns, and the
#: two mappings are easier to hold together when both are exact.
_QUARTER_TURNS = {0.0: (1.0, 0.0), 90.0: (0.0, 1.0), 180.0: (-1.0, 0.0), 270.0: (0.0, -1.0)}


@dataclass(frozen=True)
class DisplayFrame:
    """The image's placement on screen: its size, rotation and flips.

    Display coordinates run from the top left of the *turned* image's
    bounding box, x right and y down, in units of image pixels before the
    zoom -- the same space `DisplayTransform` produces, which is what the
    overlays then scale by the zoom and shift by the pan.

    Image coordinates are the grid's own: FITS order, x right and y **up**.

    Attributes:
        width, height: The image's size in pixels, unturned.
        rotation: Degrees clockwise on screen, as DS9's Zoom menu sets it.
        flip_x, flip_y: DS9's Orient, applied after the rotation.
    """

    width: int
    height: int
    rotation: float = 0.0
    flip_x: bool = False
    flip_y: bool = False

    @property
    def upright(self) -> bool:
        """Whether the image is shown as it is stored, unturned."""
        return not self.flip_x and not self.flip_y and self.rotation % 360.0 == 0.0

    # -- the linear part ------------------------------------------------------

    def _linear(self) -> tuple[float, float, float, float]:
        """The 2x2 of the turn, as (m00, m01, m10, m11).

        Rotation first and then the flips, which is the order both
        `DisplayTransform._base_transform` and `ImageViewer._update_display`
        compose them in. Getting it the other way round is invisible at 0
        and 180 degrees and wrong at every other angle.
        """
        angle = float(self.rotation) % 360.0
        cosine, sine = _QUARTER_TURNS.get(
            angle, (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
        )
        scale_x = -1.0 if self.flip_x else 1.0
        scale_y = -1.0 if self.flip_y else 1.0
        # Qt's positive rotation is clockwise, because its y axis points down.
        return (scale_x * cosine, -scale_x * sine, scale_y * sine, scale_y * cosine)

    def _origin(self) -> tuple[float, float]:
        """The top left of the turned image's bounding box, before shifting.

        Taken from the corners of the *whole* source rectangle, 0 to width
        and 0 to height, which is the rectangle `DisplayTransform._bounds`
        uses. Anything else moves the grid off the picture by a fraction of
        a pixel at every angle.
        """
        m00, m01, m10, m11 = self._linear()
        centre_x, centre_y = self.width / 2.0, self.height / 2.0
        corners = (
            (0.0, 0.0),
            (float(self.width), 0.0),
            (0.0, float(self.height)),
            (float(self.width), float(self.height)),
        )
        mapped = [
            (
                m00 * (x - centre_x) + m01 * (y - centre_y) + centre_x,
                m10 * (x - centre_x) + m11 * (y - centre_y) + centre_y,
            )
            for x, y in corners
        ]
        return (min(point[0] for point in mapped), min(point[1] for point in mapped))

    # -- the mapping ----------------------------------------------------------

    def image_to_display(self, x, y) -> tuple[NDArray[np.floating], NDArray[np.floating]]:
        """Where image coordinates land in display space.

        Accepts scalars or arrays; returns arrays, 0-d for scalars, which
        `float()` takes.
        """
        m00, m01, m10, m11 = self._linear()
        origin_x, origin_y = self._origin()
        centre_x, centre_y = self.width / 2.0, self.height / 2.0

        column = np.asarray(x, dtype=float) - centre_x
        # Image y counts up from the bottom; display y counts down from the
        # top. That flip is the first thing, exactly as in the overlays.
        row = self._to_top_down(np.asarray(y, dtype=float)) - centre_y
        return (
            m00 * column + m01 * row + centre_x - origin_x,
            m10 * column + m11 * row + centre_y - origin_y,
        )

    def display_to_image(self, u, v) -> tuple[NDArray[np.floating], NDArray[np.floating]]:
        """The inverse: where a display coordinate is in the image."""
        m00, m01, m10, m11 = self._linear()
        origin_x, origin_y = self._origin()
        centre_x, centre_y = self.width / 2.0, self.height / 2.0

        # The turn is a rotation and at most two reflections, so its
        # determinant is +-1 and it is always invertible.
        determinant = m00 * m11 - m01 * m10
        column = np.asarray(u, dtype=float) + origin_x - centre_x
        row = np.asarray(v, dtype=float) + origin_y - centre_y
        return (
            (m11 * column - m01 * row) / determinant + centre_x,
            self._to_top_down((-m10 * column + m00 * row) / determinant + centre_y),
        )

    def _to_top_down(self, y):
        """Swap between the two senses of y. Its own inverse."""
        return (self.height - 1 - y) if self.height > 0 else y

    # -- the box the grid is drawn in ------------------------------------------

    def image_box(self) -> tuple[float, float, float, float]:
        """The upright display-space box the image fills.

        Returns:
            (left, top, right, bottom), the bounding box of the turned image
            rectangle. DS9 draws its grid in exactly this box for a
            publication grid, and in the whole canvas for an analysis one
            (`grid2d.C`); the image's own box is the one that means the same
            thing whatever size the window happens to be.
        """
        corners_x = np.array([0.5, self.width + 0.5, self.width + 0.5, 0.5])
        corners_y = np.array([0.5, 0.5, self.height + 0.5, self.height + 0.5])
        u, v = self.image_to_display(corners_x, corners_y)
        return (float(u.min()), float(v.min()), float(u.max()), float(v.max()))
