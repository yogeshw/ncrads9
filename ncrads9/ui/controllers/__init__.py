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
One controller per DS9 menu.

See `base.Controller` for the design and why controllers currently reach
shared state through the main window.

Author: Yogesh Wadadekar
"""

from .analysis import AnalysisController
from .analysis_tasks import AnalysisTaskController
from .base import Controller
from .bin import BinController
from .catalog import CatalogController
from .color import ColorController
from .crosshair import CrosshairController
from .edit import EditController
from .file import FileController
from .frame import FrameController
from .help import HelpController
from .image_servers import ImageServerController
from .pointer import PointerController
from .region import RegionController
from .scale import ScaleController
from .view import ViewController
from .vo import VOController
from .wcs import WCSController
from .zoom import ZoomController

__all__ = [
    "AnalysisController",
    "ColorController",
    "Controller",
    "EditController",
    "FileController",
    "FrameController",
    "HelpController",
    "RegionController",
    "ScaleController",
    "VOController",
    "ViewController",
    "WCSController",
    "ZoomController",
]


#: Every menu controller, by the attribute it is reached through. The
#: order is the order `sync()` is broadcast in, which nothing depends on.
CONTROLLERS: tuple[tuple[str, type], ...] = (
    ("analysis", AnalysisController),
    ("analysis_tasks", AnalysisTaskController),
    ("bin", BinController),
    ("catalog", CatalogController),
    ("color", ColorController),
    ("crosshair", CrosshairController),
    ("edit", EditController),
    ("file", FileController),
    ("frame_controller", FrameController),
    ("help", HelpController),
    ("image_servers", ImageServerController),
    ("pointer", PointerController),
    ("region", RegionController),
    ("scale", ScaleController),
    ("view", ViewController),
    ("vo", VOController),
    ("wcs", WCSController),
    ("zoom", ZoomController),
)
