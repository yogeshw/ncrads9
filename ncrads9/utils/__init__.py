# NCRA DS9 - Astronomical Image Viewer
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
Utility modules for NCRA DS9.

Author: Yogesh Wadadekar
"""

from .config import Config
from .preferences import Preferences
from .logger import setup_logging
from .resources import ResourceLoader
from .math_utils import normalize_image, compute_histogram, apply_scaling
from .threading import BackgroundTask, TaskRunner

__all__ = [
    "Config",
    "Preferences",
    "setup_logging",
    "ResourceLoader",
    "normalize_image",
    "compute_histogram",
    "apply_scaling",
    "BackgroundTask",
    "TaskRunner",
]
