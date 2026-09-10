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
DS9's Plot Tool: the window an analysis task's `$plot` output lands in.

The state -- datasets, axes, legend -- is separate from the window that
draws it, so it can be built, saved, restored and tested without Qt. The
window is `ui/dialogs/plot_window.py`.

Author: Yogesh Wadadekar
"""

from .axis import Axis, AxisFormat
from .dataset import DataFormat, Dataset, PlotData, PlotDataError, parse_data, parse_stdin
from .plot_state import LegendPosition, PlotState, PlotStyle
from .zoom_stack import ZoomStack

__all__ = [
    "Axis",
    "AxisFormat",
    "DataFormat",
    "Dataset",
    "LegendPosition",
    "PlotData",
    "PlotDataError",
    "PlotState",
    "PlotStyle",
    "ZoomStack",
    "parse_data",
    "parse_stdin",
]
