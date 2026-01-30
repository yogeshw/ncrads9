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

"""PostScript generation utilities.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Optional, List, Tuple

if TYPE_CHECKING:
    from numpy.typing import NDArray
    from .page_setup import PageSetup


class PostScriptGenerator:
    """Generates PostScript output for astronomical images."""

    def __init__(
        self,
        page_setup: Optional[PageSetup] = None,
    ) -> None:
        """Initialize the PostScript generator.

        Args:
            page_setup: Page setup configuration.
        """
        self._page_setup: Optional[PageSetup] = page_setup
        self._buffer: StringIO = StringIO()
        self._title: str = "ncrads9 Output"
        self._creator: str = "ncrads9"
        self._color_mode: str = "rgb"  # rgb, grayscale, cmyk

    @property
    def page_setup(self) -> Optional[PageSetup]:
        """Get the current page setup."""
        return self._page_setup

    @page_setup.setter
    def page_setup(self, value: PageSetup) -> None:
        """Set the page setup."""
        self._page_setup = value

    @property
    def title(self) -> str:
        """Get the document title."""
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        """Set the document title."""
        self._title = value

    @property
    def color_mode(self) -> str:
        """Get the color mode."""
        return self._color_mode

    @color_mode.setter
    def color_mode(self, value: str) -> None:
        """Set the color mode (rgb, grayscale, cmyk)."""
        if value in ("rgb", "grayscale", "cmyk"):
            self._color_mode = value

    def begin_document(self) -> None:
        """Begin a new PostScript document."""
        self._buffer = StringIO()
        self._write_header()

    def end_document(self) -> None:
        """End the PostScript document."""
        self._buffer.write("%%Trailer\n")
        self._buffer.write("%%EOF\n")

    def _write_header(self) -> None:
        """Write the PostScript header."""
        self._buffer.write("%!PS-Adobe-3.0\n")
        self._buffer.write(f"%%Title: {self._title}\n")
        self._buffer.write(f"%%Creator: {self._creator}\n")
        self._buffer.write("%%Pages: 1\n")

        if self._page_setup:
            width = self._page_setup.paper_width_points
            height = self._page_setup.paper_height_points
            self._buffer.write(f"%%BoundingBox: 0 0 {width:.0f} {height:.0f}\n")

        self._buffer.write("%%EndComments\n")
        self._buffer.write("%%BeginProlog\n")
        self._buffer.write("%%EndProlog\n")
        self._buffer.write("%%Page: 1 1\n")

    def draw_image(
        self,
        image: NDArray,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        """Draw an image at the specified position.

        Args:
            image: Image data as numpy array.
            x: X position in points.
            y: Y position in points.
            width: Width in points.
            height: Height in points.
        """
        # TODO: Implement image drawing
        self._buffer.write(f"gsave\n")
        self._buffer.write(f"{x:.2f} {y:.2f} translate\n")
        self._buffer.write(f"{width:.2f} {height:.2f} scale\n")
        # Image data would go here
        self._buffer.write(f"grestore\n")

    def draw_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        line_width: float = 1.0,
    ) -> None:
        """Draw a line.

        Args:
            x1: Start X position.
            y1: Start Y position.
            x2: End X position.
            y2: End Y position.
            line_width: Line width in points.
        """
        self._buffer.write(f"{line_width:.2f} setlinewidth\n")
        self._buffer.write(f"newpath\n")
        self._buffer.write(f"{x1:.2f} {y1:.2f} moveto\n")
        self._buffer.write(f"{x2:.2f} {y2:.2f} lineto\n")
        self._buffer.write(f"stroke\n")

    def draw_text(
        self,
        text: str,
        x: float,
        y: float,
        font_name: str = "Helvetica",
        font_size: float = 12.0,
    ) -> None:
        """Draw text at the specified position.

        Args:
            text: Text to draw.
            x: X position in points.
            y: Y position in points.
            font_name: PostScript font name.
            font_size: Font size in points.
        """
        escaped_text = text.replace("(", "\\(").replace(")", "\\)")
        self._buffer.write(f"/{font_name} findfont\n")
        self._buffer.write(f"{font_size:.1f} scalefont setfont\n")
        self._buffer.write(f"{x:.2f} {y:.2f} moveto\n")
        self._buffer.write(f"({escaped_text}) show\n")

    def set_color(
        self,
        r: float,
        g: float,
        b: float,
    ) -> None:
        """Set the current color.

        Args:
            r: Red component (0-1).
            g: Green component (0-1).
            b: Blue component (0-1).
        """
        self._buffer.write(f"{r:.3f} {g:.3f} {b:.3f} setrgbcolor\n")

    def save(self, filename: str | Path) -> bool:
        """Save the PostScript to a file.

        Args:
            filename: Output file path.

        Returns:
            True if save was successful.
        """
        try:
            with open(filename, "w") as f:
                f.write(self._buffer.getvalue())
            return True
        except IOError:
            return False

    def get_content(self) -> str:
        """Get the PostScript content as a string.

        Returns:
            PostScript document content.
        """
        return self._buffer.getvalue()
