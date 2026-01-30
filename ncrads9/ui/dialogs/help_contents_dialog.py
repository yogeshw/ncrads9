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
            h1 { color: #2e3436; font-size: 24px; }
            h2 { color: #204a87; font-size: 18px; margin-top: 20px; }
            h3 { color: #4e9a06; font-size: 14px; margin-top: 15px; }
            code { background-color: #f0f0f0; padding: 2px 5px; font-family: monospace; }
        </style>
    </head>
    <body>
        <h1>NCRADS9 Help</h1>
        
        <h2>Getting Started</h2>
        <p>NCRADS9 is a Python/Qt6 clone of SAOImageDS9 for viewing FITS astronomical images.</p>
        
        <h3>Opening Files</h3>
        <ul>
            <li><b>File → Open</b> (Ctrl+O): Open a FITS file</li>
            <li><b>Command line:</b> <code>ncrads9 image.fits</code></li>
        </ul>
        
        <h3>Viewing Images</h3>
        <ul>
            <li><b>Mouse wheel:</b> Zoom in/out</li>
            <li><b>Right-click + drag:</b> Adjust contrast/brightness</li>
            <li><b>Middle-click + drag:</b> Pan the image</li>
        </ul>
        
        <h3>Zoom Controls</h3>
        <ul>
            <li><b>Ctrl++:</b> Zoom in</li>
            <li><b>Ctrl+-:</b> Zoom out</li>
            <li><b>Zoom → Fit:</b> Fit image to window</li>
            <li><b>Zoom → 1:1:</b> View at actual pixel size</li>
        </ul>
        
        <h3>Scale Algorithms</h3>
        <p>Change the data scaling via <b>Scale</b> menu:</p>
        <ul>
            <li><b>Linear:</b> Linear scaling (default)</li>
            <li><b>Log:</b> Logarithmic scaling</li>
            <li><b>Sqrt:</b> Square root scaling</li>
            <li><b>Squared:</b> Power-law scaling</li>
            <li><b>Asinh:</b> Inverse hyperbolic sine</li>
            <li><b>HistEq:</b> Histogram equalization</li>
        </ul>
        
        <h3>Colormaps</h3>
        <p>Select colormaps via <b>Color</b> menu (19 DS9 colormaps available):</p>
        <ul>
            <li><b>Grey:</b> Grayscale (default)</li>
            <li><b>Heat, Cool, Rainbow:</b> Color maps</li>
            <li><b>Invert Colormap:</b> Reverse any colormap</li>
        </ul>
        
        <h3>Analysis Tools</h3>
        <ul>
            <li><b>Analysis → Statistics:</b> Image statistics (min/max/mean/median)</li>
            <li><b>Analysis → Histogram:</b> Pixel value distribution</li>
            <li><b>Analysis → Pixel Table:</b> Examine individual pixel values</li>
            <li><b>Analysis → FITS Header:</b> View FITS header keywords</li>
        </ul>
        
        <h3>Regions</h3>
        <ul>
            <li><b>Region → Load Region File:</b> Load DS9 .reg files</li>
            <li>Region drawing and editing (in development)</li>
        </ul>
        
        <h3>Keyboard Shortcuts</h3>
        <p>See <b>Help → Keyboard Shortcuts</b> for complete list.</p>
        
        <h2>Status Bar</h2>
        <p>The status bar shows (from left to right):</p>
        <ol>
            <li>Pixel coordinates (x, y)</li>
            <li>WCS coordinates (RA, Dec) if available</li>
            <li>Pixel value at cursor</li>
            <li>Image dimensions</li>
            <li>Current zoom level</li>
        </ol>
        
        <h2>More Information</h2>
        <p>For more information, visit: <a href="https://github.com/yogeshw/ncrads9">
        https://github.com/yogeshw/ncrads9</a></p>
    </body>
    </html>
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the help contents dialog.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
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
