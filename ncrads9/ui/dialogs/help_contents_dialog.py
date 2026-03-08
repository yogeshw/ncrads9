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
Help contents dialog.

Author: Yogesh Wadadekar
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QLabel,
    QWidget,
)
from PyQt6.QtCore import Qt


class HelpContentsDialog(QDialog):
    """Dialog showing help contents."""

    HELP_HTML = """
    <html>
    <head>
        <style>
            body { color: #2e3436; line-height: 1.4; }
            h1 { color: #2e3436; font-size: 24px; }
            h2 { color: #204a87; font-size: 18px; margin-top: 20px; }
            h3 { color: #4e9a06; font-size: 14px; margin-top: 15px; }
            code { background-color: #f0f0f0; padding: 2px 5px; font-family: monospace; }
        </style>
    </head>
    <body>
        <h1>NCRADS9 Help</h1>

        <h2>Overview</h2>
        <p>
            NCRADS9 is a Python/Qt6 FITS viewer inspired by SAOImageDS9. It supports
            single-frame viewing, tiled/multi-frame workflows, RGB composites, region
            overlays, WCS display, analysis tools, and DS9-style menu-driven navigation.
        </p>

        <h2>Opening Data</h2>
        <ul>
            <li><b>File → Open</b> (<code>Ctrl+O</code>) opens FITS images, including common FITS filename variants.</li>
            <li><b>Command line:</b> <code>ncrads9 image.fits</code> opens a file directly.</li>
            <li>You can also start in DS9-style modes such as tiled display or RGB startup from the command line.</li>
        </ul>

        <h2>Navigating the Image</h2>
        <ul>
            <li><b>Mouse wheel</b> zooms in and out.</li>
            <li><b>Middle-click + drag</b> pans the current view.</li>
            <li><b>Right-click + drag</b> adjusts contrast and brightness.</li>
            <li>The panner, magnifier, graphs, and status bar update with the active frame.</li>
        </ul>

        <h2>Zoom Menu</h2>
        <p>The top-level <b>Zoom</b> menu mirrors the current DS9-style implementation:</p>
        <ul>
            <li><b>Center Image</b>, <b>Align</b>, <b>Zoom In</b>, <b>Zoom Out</b>, and <b>Zoom Fit</b></li>
            <li>Preset zoom levels from <b>1/32</b> through <b>32</b></li>
            <li>Orientation controls: <b>None</b>, <b>Invert X</b>, <b>Invert Y</b>, and <b>Invert XY</b></li>
            <li>Rotation controls: <b>0</b>, <b>90</b>, <b>180</b>, and <b>270</b> degrees</li>
            <li><b>Crop Parameters</b> and <b>Pan Zoom Rotate Parameters</b> dialogs</li>
        </ul>
        <p>
            Direction arrows, overlays, and frame view state follow the active zoom/orientation settings.
        </p>

        <h2>Display Controls</h2>
        <ul>
            <li><b>Scale</b> menu: Linear, Log, Sqrt, Squared, Asinh, and Histogram Equalization</li>
            <li><b>Scale</b> limits: MinMax, ZScale, and parameter dialogs</li>
            <li><b>Color</b> menu: DS9-style default colormaps, extra scientific colormaps, inversion, reset, and user colormap load/save</li>
            <li><b>Colorbar</b> options: visibility, orientation, numeric spacing, and font</li>
            <li><b>Bin</b> menu: 1x1, 2x2, 4x4, and 8x8 display binning</li>
        </ul>

        <h2>Frames and RGB</h2>
        <ul>
            <li><b>Frame</b> menu supports new/delete/clear/reset/refresh operations.</li>
            <li>Display modes include <b>Single</b>, <b>Tile</b>, <b>Blink</b>, and <b>Fade</b>.</li>
            <li>Frame matching is available for frame, crosshair, crop, and slice coordinates.</li>
            <li><b>Frame → RGB</b> lets you build RGB composites from channel source frames.</li>
        </ul>

        <h2>Regions, WCS, and Analysis</h2>
        <ul>
            <li><b>Region</b> menu supports circle, ellipse, box, polygon, line, and point regions, plus DS9 region load/save.</li>
            <li><b>WCS</b> menu supports FK5, FK4, ICRS, Galactic, and Ecliptic systems, sexagesimal/degree formatting, and direction arrows.</li>
            <li><b>Analysis</b> tools include statistics, histogram, radial profile, FITS header, pixel table, contours, coordinate grid, block, and smooth controls.</li>
            <li><b>VO</b> and <b>SAMP</b> menus provide 2MASS/VizieR entry points and SAMP connectivity.</li>
        </ul>

        <h2>Large Images</h2>
        <p>
            NCRADS9 is optimized for large FITS images using memory-mapped loading, tiled GPU rendering
            when enabled, and lightweight preview panels. CPU mode also avoids unnecessary rerendering
            for repeated zoom/orientation changes.
        </p>

        <h2>Status Bar</h2>
        <p>The status bar reports the current cursor position and active frame state, including:</p>
        <ol>
            <li>Pixel coordinates</li>
            <li>WCS coordinates when available</li>
            <li>Pixel value under the cursor</li>
            <li>Image dimensions</li>
            <li>Current zoom level</li>
        </ol>

        <h2>Keyboard Shortcuts</h2>
        <p>See <b>Help → Keyboard Shortcuts</b> for the current shortcut list.</p>

        <h2>Current Notes</h2>
        <ul>
            <li>Region files can be saved, but FITS <b>Save</b>/<b>Save As</b> workflows are still limited.</li>
            <li>Some Virtual Observatory and advanced modules are present but still evolving.</li>
        </ul>

        <h2>More Information</h2>
        <p>
            Project page:
            <a href="https://github.com/ncra/ncrads9">https://github.com/ncra/ncrads9</a>
        </p>
    </body>
    </html>
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the help contents dialog.

        Args:
            parent: Optional parent widget.
        """
        # Pass None as parent to make dialog independent
        super().__init__(None)
        
        # Set window flags for independent draggable window
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        
        self.setWindowTitle("NCRADS9 Help")
        self.setMinimumSize(700, 600)
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout()
        
        # Help browser
        browser = QTextBrowser()
        browser.setHtml(self.HELP_HTML)
        browser.setOpenExternalLinks(True)
        layout.addWidget(browser)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
