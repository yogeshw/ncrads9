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
The page a print goes on: its size, which way round, and how much of it.

DS9's Page Setup (`pagesetup.tcl`) offers five named sizes, its own in
inches or millimetres, portrait or landscape, and a percentage scale. The
sizes are DS9's own list, poster included -- it is there because people
print mosaics on plotters.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

#: How many points to an inch, and to a millimetre. PostScript works in
#: points, and every size below is quoted the way DS9 quotes it.
POINTS_PER_INCH = 72.0
POINTS_PER_MM = POINTS_PER_INCH / 25.4


class PaperSize(Enum):
    """The page sizes DS9's Page Setup offers."""

    LETTER = "letter"
    LEGAL = "legal"
    TABLOID = "tabloid"
    POSTER = "poster"
    A4 = "a4"
    #: DS9's `other`: a size typed in inches.
    OTHER = "other"
    #: DS9's `othermm`: a size typed in millimetres.
    OTHER_MM = "othermm"


class Orientation(Enum):
    """Which way round the page is."""

    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


#: Each named size in inches, as DS9 labels it on the dialog.
PAPER_INCHES: dict[PaperSize, tuple[float, float]] = {
    PaperSize.LETTER: (8.5, 11.0),
    PaperSize.LEGAL: (8.5, 14.0),
    PaperSize.TABLOID: (11.0, 17.0),
    PaperSize.POSTER: (36.0, 48.0),
    # 210 x 297 mm, which is what the dialog says.
    PaperSize.A4: (210.0 / 25.4, 297.0 / 25.4),
}

#: The margin left around the image, in points. DS9 prints to the page's
#: edges and lets the printer's own unprintable margin take care of it;
#: half an inch is kinder and still leaves the image the same shape.
DEFAULT_MARGIN = 0.5 * POINTS_PER_INCH


@dataclass
class PageSetup:
    """One page's geometry.

    Attributes:
        paper_size: One of DS9's sizes.
        orientation: Portrait or landscape.
        scale: A percentage, as DS9's dialog asks. 100 fits the page.
        width, height: The typed size, in inches for `OTHER` and in
            millimetres for `OTHER_MM`. Ignored for a named size.
        margin: How much to leave around the image, in points.
    """

    paper_size: PaperSize = PaperSize.LETTER
    orientation: Orientation = Orientation.PORTRAIT
    scale: float = 100.0
    width: float = 8.5
    height: float = 11.0
    margin: float = DEFAULT_MARGIN

    # -- the paper ------------------------------------------------------------

    @property
    def size_points(self) -> tuple[float, float]:
        """The paper's width and height in points, orientation applied."""
        if self.paper_size is PaperSize.OTHER:
            width, height = self.width * POINTS_PER_INCH, self.height * POINTS_PER_INCH
        elif self.paper_size is PaperSize.OTHER_MM:
            width, height = self.width * POINTS_PER_MM, self.height * POINTS_PER_MM
        else:
            inches = PAPER_INCHES[self.paper_size]
            width, height = inches[0] * POINTS_PER_INCH, inches[1] * POINTS_PER_INCH

        if self.orientation is Orientation.LANDSCAPE:
            return (height, width)
        return (width, height)

    @property
    def width_points(self) -> float:
        """The paper's width in points."""
        return self.size_points[0]

    @property
    def height_points(self) -> float:
        """The paper's height in points."""
        return self.size_points[1]

    # -- what can be printed on it ---------------------------------------------

    @property
    def printable(self) -> tuple[float, float, float, float]:
        """The area inside the margins, as (x, y, width, height) in points."""
        width, height = self.size_points
        inset = max(0.0, min(self.margin, min(width, height) / 4.0))
        return (inset, inset, width - 2 * inset, height - 2 * inset)

    def place(self, image_width: int, image_height: int) -> tuple[float, float, float, float]:
        """Where an image of a given pixel size goes on the page.

        Fitted to the printable area with its shape kept, then multiplied by
        the scale percentage and centred -- so 200% prints an image twice
        the size it would otherwise be, off the edges if it must, which is
        what a percentage scale is for.

        Args:
            image_width: The image's width in pixels.
            image_height: Its height.

        Returns:
            (x, y, width, height) in points, with y from the bottom as
            PostScript counts it.
        """
        if image_width <= 0 or image_height <= 0:
            return (0.0, 0.0, 0.0, 0.0)

        left, bottom, area_width, area_height = self.printable
        fit = min(area_width / image_width, area_height / image_height)
        factor = fit * max(1.0, self.scale) / 100.0
        width = image_width * factor
        height = image_height * factor
        return (
            left + (area_width - width) / 2.0,
            bottom + (area_height - height) / 2.0,
            width,
            height,
        )
