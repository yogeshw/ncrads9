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

`math_utils`, `resources` and `threading` are deliberately not imported
here: nothing reaches them yet, and importing them from the package would
hide that from the no-orphan-modules guard. Import them directly if they
gain a caller.

Author: Yogesh Wadadekar
"""

from .config import Config
from .logger import setup_logging
from .preferences import Preferences
from .undo import Command, UndoStack

__all__ = [
    "Command",
    "Config",
    "Preferences",
    "UndoStack",
    "setup_logging",
]
