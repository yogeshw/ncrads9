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
Dialog modules for NCRADS9.

Author: Yogesh Wadadekar
"""

from .analysis_param_dialog import AnalysisParamDialog
from .analysis_text_dialog import AnalysisTextDialog
from .array_dialog import ArrayDialog
from .centroid_dialog import CentroidDialog
from .colormap_dialog import ColormapDialog
from .contour_dialog import ContourDialog
from .crop_parameters_dialog import CropParametersDialog
from .grid_dialog import GridDialog
from .group_dialog import GroupDialog
from .header_dialog import HeaderDialog
from .mask_dialog import MaskDialog
from .movie_dialog import MovieDialog
from .notes_dialog import NotesDialog
from .open_dialog import OpenDialog
from .pan_zoom_rotate_dialog import PanZoomRotateDialog
from .preferences_dialog import PreferencesDialog
from .region_analysis_dialog import RegionPlotDialog, RegionStatisticsDialog
from .region_dialog import RegionDialog
from .save_dialog import SaveDialog
from .scale_dialog import ScaleDialog
from .smooth_dialog import SmoothDialog

__all__ = [
    "OpenDialog",
    "SaveDialog",
    "HeaderDialog",
    "ContourDialog",
    "GridDialog",
    "SmoothDialog",
    "ScaleDialog",
    "ColormapDialog",
    "AnalysisParamDialog",
    "MaskDialog",
    "AnalysisTextDialog",
    "CentroidDialog",
    "GroupDialog",
    "RegionDialog",
    "RegionPlotDialog",
    "RegionStatisticsDialog",
    "PreferencesDialog",
    "ArrayDialog",
    "CropParametersDialog",
    "MovieDialog",
    "NotesDialog",
    "PanZoomRotateDialog",
]
