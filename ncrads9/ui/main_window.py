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
Main window for NCRADS9 application.

Author: Yogesh Wadadekar
"""

from typing import Optional, TYPE_CHECKING, Dict, List, Tuple
from pathlib import Path
import tempfile
from urllib.parse import urlparse, unquote

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, QUrl, pyqtSignal
from PyQt6.QtWidgets import QDialog
from PyQt6.QtGui import QAction, QImage, QPixmap, QColor, QDesktopServices, QKeyEvent
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QButtonGroup,
    QRadioButton,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QLabel,
    QScrollArea,
    QInputDialog,
    QColorDialog,
)
import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from astropy.table import Table
from astropy.coordinates import (
    SkyCoord,
    FK5,
    FK4,
    ICRS,
    Galactic,
    BarycentricTrueEcliptic,
)
import astropy.units as u

from .menu_bar import MenuBar
from .toolbar import MainToolbar
from .button_bar import ButtonBar
from .status_bar import StatusBar
from .image_viewer import ImageViewer
from .widgets.colorbar_widget import ColorbarWidget
from .widgets.image_viewer_with_regions import ImageViewerWithRegions
from .widgets.gl_image_viewer_with_regions import GLImageViewerWithRegions
from .widgets.region_overlay import RegionMode, Region
from .panels.panner import PannerPanel
from .panels.magnifier import MagnifierPanel
from .panels.horizontal_graph import HorizontalGraph
from .panels.vertical_graph import VerticalGraph
from .dialogs.statistics_dialog import StatisticsDialog
from .dialogs.scale_dialog import ScaleDialog
from .dialogs.histogram_dialog import HistogramDialog
from .dialogs.pixel_table_dialog import PixelTableDialog
from .dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from .dialogs.help_contents_dialog import HelpContentsDialog
from .dialogs.export_dialog import ExportDialog
from .dialogs.contour_dialog import ContourDialog
from .dialogs.grid_dialog import GridDialog
from .dialogs.smooth_dialog import SmoothDialog
from .dialogs.preferences_dialog import PreferencesDialog
from ..core.fits_handler import FITSHandler
from ..core.wcs_handler import WCSHandler
from ..rendering.scale_algorithms import apply_scale, ScaleAlgorithm, compute_zscale_limits
from ..colormaps.builtin_maps import get_colormap
from ..colormaps.colormap import Colormap
from ..colormaps.lut_parser import parse_lut_file, save_lut_file
from ..colormaps.sao_parser import parse_sao_file
from ..regions.region_parser import RegionParser
from ..regions.region_writer import RegionWriter
from ..regions.shapes.circle import Circle
from ..regions.shapes.ellipse import Ellipse
from ..regions.shapes.box import Box
from ..regions.shapes.line import Line
from ..regions.shapes.point import Point
from ..regions.shapes.polygon import Polygon
from ..frames.simple_frame_manager import FrameManager, Frame
from ..analysis.contour import ContourGenerator
from ..analysis.smooth import gaussian_smooth, boxcar_smooth, tophat_smooth
from ..analysis.radial_profile import RadialProfile
from ..utils.preferences import Preferences
from ..image_servers.sia_client import SIAClient
from ..catalogs.vizier import VizierCatalog
from ..communication.samp import SAMPClient
from .dialogs.vo_query_dialog import VOQueryDialog

if TYPE_CHECKING:
    from ncrads9.utils.config import Config


class MainWindow(QMainWindow):
    """Main application window for NCRADS9."""
    samp_table_received = pyqtSignal(str, str, str)

    def __init__(self, config: Optional["Config"] = None, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the main window.

        Args:
            config: Application configuration.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("NCRADS9 - FITS Viewer")
        self.setMinimumSize(800, 600)
        
        # Initialize data storage
        self.frame_manager = FrameManager()
        self.current_scale = ScaleAlgorithm.LINEAR
        self.current_colormap = "grey"
        self._default_colormap = "grey"
        self.invert_colormap = False
        self.custom_colormaps: Dict[str, Colormap] = {}
        self._user_colormap_actions: Dict[str, object] = {}
        self.current_bin = 1
        self.current_wcs_system = "fk5"
        self.current_wcs_format = "sexagesimal"
        self._last_mouse_pos: Optional[tuple[int, int]] = None
        self.preferences = Preferences(self._preferences_path())
        self.use_gpu_rendering = bool(self.preferences.get("use_gpu", True))
        self.using_gpu_rendering = False
        self.z1 = None  # Scale limits
        self.z2 = None
        self._contour_settings: Optional[dict] = None
        self._contour_paths: Optional[list] = None
        self._contour_levels: Optional[list] = None
        self._smooth_settings: dict = {
            "kernel_type": "Gaussian",
            "sigma": 2.0,
            "kernel_size": 5,
            "elliptical": False,
            "axis_ratio": 1.0,
            "position_angle": 0.0,
            "preserve_nan": True,
            "normalize": True,
        }
        self._grid_settings: Optional[dict] = None
        self._analysis_command_log = False
        self._analysis_command_entries: List[str] = []
        self._loaded_analysis_actions: List[QAction] = []
        self._analysis_mask_mode = "disabled"
        self._analysis_mask_min: Optional[float] = None
        self._analysis_mask_max: Optional[float] = None
        self._crosshair_enabled = False
        self._crosshair_color = QColor(255, 0, 0)
        self._crosshair_size = 24
        self._show_direction_arrows = True
        self._frame_display_mode = "single"
        self._tile_mode_enabled = False
        self._tile_arrangement_mode = "grid"
        self._tile_layout: Optional[dict] = None
        current_frame = self.frame_manager.current_frame
        self._active_frame_ids: set[int] = {current_frame.frame_id} if current_frame else set()
        self._known_frame_ids: set[int] = set(self._active_frame_ids)
        self._frame_lock_scope: Dict[str, str] = {
            "frame": "none",
            "crosshair": "none",
            "crop": "none",
            "slice": "none",
        }
        self._frame_lock_flags: Dict[str, bool] = {
            "bin": False,
            "axes_order": False,
            "scale": False,
            "scale_limits": False,
            "colorbar": False,
            "block": False,
            "smooth": False,
            "3d": False,
        }
        self._fade_interval_ms = 1000
        self._samp_client: Optional[SAMPClient] = None
        self._samp_connected = False
        self._samp_marker_color = QColor(255, 255, 0)
        self._samp_marker_shape = "box"
        self._samp_marker_size = 6.0
        self._samp_catalog_sources: Dict[int, List[Tuple[float, float]]] = {}
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(500)
        self._blink_timer.timeout.connect(self._update_blink)
        self.samp_table_received.connect(self._handle_samp_table_message)

        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_dock_widgets()
        self._setup_status_bar()
        self._init_samp_client()
        self._update_samp_menu_state()
        self._apply_preferences(self._get_preferences_dict(), persist=False, show_message=False)
        self._refresh_frame_menu_items()
    
    @property
    def image_data(self):
        """Get current frame's image data."""
        frame = self.frame_manager.current_frame
        if not frame:
            return None
        if frame.frame_type == "rgb":
            return self._get_rgb_active_channel_data(frame)
        return frame.image_data
    
    @property
    def wcs_handler(self):
        """Get current frame's WCS handler."""
        frame = self.frame_manager.current_frame
        return frame.wcs_handler if frame else None
    
    @property
    def fits_handler(self):
        """Get a temporary FITS handler for current frame."""
        frame = self.frame_manager.current_frame
        if frame and frame.fits_handler is not None:
            return frame.fits_handler
        if frame and frame.filepath:
            handler = FITSHandler()
            handler.load(str(frame.filepath))
            frame.fits_handler = handler
            return handler
        return None

    @staticmethod
    def _rgb_channel_names() -> tuple[str, str, str]:
        return ("red", "green", "blue")

    def _set_viewer_contrast_brightness(self, contrast: float, brightness: float) -> None:
        """Set contrast/brightness on CPU or GPU viewer implementation."""
        if hasattr(self.image_viewer, "set_contrast_brightness"):
            self.image_viewer.set_contrast_brightness(contrast, brightness)
            return
        if hasattr(self.image_viewer, "image_viewer") and hasattr(self.image_viewer.image_viewer, "set_contrast_brightness"):
            self.image_viewer.image_viewer.set_contrast_brightness(contrast, brightness)

    def _get_rgb_active_channel_data(self, frame: Frame) -> Optional[NDArray[np.floating]]:
        """Return currently selected RGB channel data, or first available channel."""
        channel = frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
        data = frame.rgb_channels.get(channel)
        if data is not None:
            return data
        for name in self._rgb_channel_names():
            channel_data = frame.rgb_channels.get(name)
            if channel_data is not None:
                return channel_data
        return None

    def _sync_rgb_scalar_view(self, frame: Frame) -> None:
        """Keep scalar frame data in sync with selected RGB channel for analysis/status."""
        active = self._get_rgb_active_channel_data(frame)
        frame.image_data = active
        frame.original_image_data = active

    def _rgb_channel_view_settings(
        self,
        frame: Frame,
        channel: str,
    ) -> tuple[ScaleAlgorithm, Optional[float], Optional[float], float, float]:
        """Return per-channel RGB display settings."""
        scale = frame.rgb_channel_scale.get(channel, ScaleAlgorithm.LINEAR)
        z1 = frame.rgb_channel_z1.get(channel)
        z2 = frame.rgb_channel_z2.get(channel)
        contrast = max(float(frame.rgb_channel_contrast.get(channel, 1.0)), 0.1)
        brightness = max(-1.0, min(float(frame.rgb_channel_brightness.get(channel, 0.0)), 1.0))
        return scale, z1, z2, contrast, brightness

    def _compute_rgb_channel_scaled(
        self,
        frame: Frame,
        channel: str,
        data: NDArray[np.floating],
    ) -> NDArray[np.float32]:
        """Apply per-channel limits/contrast/brightness/scale and return [0,1] channel."""
        scale, z1, z2, contrast, brightness = self._rgb_channel_view_settings(frame, channel)
        if z1 is None or z2 is None:
            z1, z2 = compute_zscale_limits(data)
        range_val = max(float(z2 - z1), 1e-6)
        center = (z1 + z2) / 2.0
        new_range = range_val / contrast
        adjusted_z1 = center - new_range / 2.0 + brightness * range_val
        adjusted_z2 = center + new_range / 2.0 + brightness * range_val
        clipped = np.clip(data, adjusted_z1, adjusted_z2)
        scaled = apply_scale(clipped, scale, vmin=adjusted_z1, vmax=adjusted_z2)
        return np.clip(scaled.astype(np.float32), 0.0, 1.0)

    def _compose_rgb_frame_image(self, frame: Frame) -> Optional[NDArray[np.uint8]]:
        """Compose display RGB image for an RGB frame."""
        channels = {
            name: frame.rgb_channels.get(name)
            for name in self._rgb_channel_names()
            if frame.rgb_channels.get(name) is not None
        }
        if not channels:
            return None

        base_shape = next(iter(channels.values())).shape
        rgb = np.zeros((base_shape[0], base_shape[1], 3), dtype=np.float32)
        visible_assigned = False
        for name in self._rgb_channel_names():
            if not frame.rgb_view.get(name, True):
                continue
            data = frame.rgb_channels.get(name)
            if data is None or data.shape != base_shape:
                continue
            normalized = self._compute_rgb_channel_scaled(frame, name, data)
            if name == "red":
                rgb[:, :, 0] = normalized
            elif name == "green":
                rgb[:, :, 1] = normalized
            else:
                rgb[:, :, 2] = normalized
            visible_assigned = True
        if not visible_assigned:
            return np.zeros((base_shape[0], base_shape[1], 3), dtype=np.uint8)
        return (np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8)

    def _apply_rgb_frame_channels_from_sources(
        self,
        frame: Frame,
        channel_to_source_index: Dict[str, Optional[int]],
    ) -> None:
        """Assign RGB channels from existing mono frames."""
        for channel, source_index in channel_to_source_index.items():
            if channel not in frame.rgb_channels:
                continue
            if source_index is None:
                frame.rgb_channels[channel] = None
                frame.rgb_source_frame_ids[channel] = None
                continue
            if source_index < 0 or source_index >= len(self.frame_manager.frames):
                continue
            source_frame = self.frame_manager.frames[source_index]
            source_data = source_frame.image_data
            if source_data is None or source_data.ndim != 2:
                continue
            frame.rgb_channels[channel] = np.array(source_data, copy=True)
            frame.rgb_source_frame_ids[channel] = source_frame.frame_id
        self._sync_rgb_scalar_view(frame)

    def _sync_view_state_from_rgb_channel(self, frame: Frame) -> None:
        """Load current window scale/limits/contrast from active RGB channel."""
        channel = frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
        scale, z1, z2, contrast, brightness = self._rgb_channel_view_settings(frame, channel)
        self.current_scale = scale
        self.z1 = z1
        self.z2 = z2
        self._set_viewer_contrast_brightness(contrast, brightness)

    def _setup_menu_bar(self) -> None:
        """Set up the menu bar."""
        self.menu_bar = MenuBar(self)
        if hasattr(self.menu_bar, "setNativeMenuBar"):
            self.menu_bar.setNativeMenuBar(False)
        self.setMenuBar(self.menu_bar)
        self.menu_bar.update()
        
        # Connect menu actions to handlers
        self._connect_menu_actions()
    
    def _connect_menu_actions(self) -> None:
        """Connect menu actions to their handlers."""
        # File menu
        self.menu_bar.action_open.triggered.connect(self.open_file)
        self.menu_bar.action_save.triggered.connect(self.save_file)
        self.menu_bar.action_save_as.triggered.connect(self.save_file_as)
        self.menu_bar.action_export.triggered.connect(self._export_image)
        self.menu_bar.action_print.triggered.connect(self._print_image)
        self.menu_bar.action_exit.triggered.connect(self.close)
        
        # Edit menu
        self.menu_bar.action_undo.triggered.connect(lambda: self.statusBar().showMessage("Undo not implemented", 2000))
        self.menu_bar.action_redo.triggered.connect(lambda: self.statusBar().showMessage("Redo not implemented", 2000))
        self.menu_bar.action_preferences.triggered.connect(self._show_preferences)
        
        # View menu
        self.menu_bar.action_fullscreen.triggered.connect(self._toggle_fullscreen)
        self.menu_bar.action_show_toolbar.triggered.connect(self._toggle_toolbar)
        self.menu_bar.action_show_statusbar.triggered.connect(self._toggle_statusbar)
        
        # Frame menu
        self.menu_bar.action_new_frame.triggered.connect(self._new_frame)
        self.menu_bar.action_new_frame_rgb.triggered.connect(lambda: self._new_frame_with_type("rgb"))
        self.menu_bar.action_new_frame_hsv.triggered.connect(lambda: self._new_frame_with_type("hsv"))
        self.menu_bar.action_new_frame_hls.triggered.connect(lambda: self._new_frame_with_type("hls"))
        self.menu_bar.action_new_frame_3d.triggered.connect(lambda: self._new_frame_with_type("3d"))
        self.menu_bar.action_delete_frame.triggered.connect(self._delete_frame)
        self.menu_bar.action_delete_all_frames.triggered.connect(self._delete_all_frames)
        self.menu_bar.action_clear_frame.triggered.connect(self._clear_frame)
        self.menu_bar.action_reset_frame.triggered.connect(self._reset_frame)
        self.menu_bar.action_refresh_frame.triggered.connect(self._refresh_frame)
        self.menu_bar.action_single_frame.triggered.connect(self._show_single_frame)
        self.menu_bar.action_tile_frames.triggered.connect(self._tile_frames)
        self.menu_bar.action_blink_frames.triggered.connect(self._toggle_blink)
        self.menu_bar.action_fade_frames.triggered.connect(self._toggle_fade)
        self.menu_bar.action_show_all_frames.triggered.connect(self._show_all_frames)
        self.menu_bar.action_hide_all_frames.triggered.connect(self._hide_all_frames)
        self.menu_bar.action_move_frame_first.triggered.connect(self._move_frame_first)
        self.menu_bar.action_move_frame_back.triggered.connect(self._move_frame_back)
        self.menu_bar.action_move_frame_forward.triggered.connect(self._move_frame_forward)
        self.menu_bar.action_move_frame_last.triggered.connect(self._move_frame_last)
        self.menu_bar.action_first_frame.triggered.connect(self._first_frame)
        self.menu_bar.action_prev_frame.triggered.connect(self._prev_frame)
        self.menu_bar.action_next_frame.triggered.connect(self._next_frame)
        self.menu_bar.action_last_frame.triggered.connect(self._last_frame)
        self.menu_bar.action_match_image.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_wcs.triggered.connect(self._match_frames_wcs)
        self.menu_bar.action_match_frame_physical.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_frame_amplifier.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_frame_detector.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_crosshair_wcs.triggered.connect(self._match_frames_wcs)
        self.menu_bar.action_match_crosshair_image.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_crosshair_physical.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_crosshair_amplifier.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_crosshair_detector.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_crop_wcs.triggered.connect(self._match_frames_wcs)
        self.menu_bar.action_match_crop_image.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_crop_physical.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_crop_amplifier.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_crop_detector.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_slice_wcs.triggered.connect(self._match_frames_wcs)
        self.menu_bar.action_match_slice_image.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_bin.triggered.connect(self._match_frames_bin)
        self.menu_bar.action_match_axes_order.triggered.connect(self._match_frames_axes_order)
        self.menu_bar.action_match_scale.triggered.connect(self._match_frames_scale)
        self.menu_bar.action_match_scale_limits.triggered.connect(self._match_frames_scale_limits)
        self.menu_bar.action_match_colorbar.triggered.connect(self._match_frames_colorbar)
        self.menu_bar.action_match_block.triggered.connect(self._match_frames_block)
        self.menu_bar.action_match_smooth.triggered.connect(self._match_frames_smooth)
        self.menu_bar.action_match_3d.triggered.connect(self._match_frames_3d)
        self.menu_bar.action_lock_frame_none.triggered.connect(lambda: self._set_frame_lock_scope("frame", "none"))
        self.menu_bar.action_lock_frame_wcs.triggered.connect(lambda: self._set_frame_lock_scope("frame", "wcs"))
        self.menu_bar.action_lock_frame_image.triggered.connect(lambda: self._set_frame_lock_scope("frame", "image"))
        self.menu_bar.action_lock_frame_physical.triggered.connect(lambda: self._set_frame_lock_scope("frame", "physical"))
        self.menu_bar.action_lock_frame_amplifier.triggered.connect(lambda: self._set_frame_lock_scope("frame", "amplifier"))
        self.menu_bar.action_lock_frame_detector.triggered.connect(lambda: self._set_frame_lock_scope("frame", "detector"))
        self.menu_bar.action_lock_crosshair_none.triggered.connect(
            lambda: self._set_frame_lock_scope("crosshair", "none")
        )
        self.menu_bar.action_lock_crosshair_wcs.triggered.connect(
            lambda: self._set_frame_lock_scope("crosshair", "wcs")
        )
        self.menu_bar.action_lock_crosshair_image.triggered.connect(
            lambda: self._set_frame_lock_scope("crosshair", "image")
        )
        self.menu_bar.action_lock_crosshair_physical.triggered.connect(
            lambda: self._set_frame_lock_scope("crosshair", "physical")
        )
        self.menu_bar.action_lock_crosshair_amplifier.triggered.connect(
            lambda: self._set_frame_lock_scope("crosshair", "amplifier")
        )
        self.menu_bar.action_lock_crosshair_detector.triggered.connect(
            lambda: self._set_frame_lock_scope("crosshair", "detector")
        )
        self.menu_bar.action_lock_crop_none.triggered.connect(lambda: self._set_frame_lock_scope("crop", "none"))
        self.menu_bar.action_lock_crop_wcs.triggered.connect(lambda: self._set_frame_lock_scope("crop", "wcs"))
        self.menu_bar.action_lock_crop_image.triggered.connect(lambda: self._set_frame_lock_scope("crop", "image"))
        self.menu_bar.action_lock_crop_physical.triggered.connect(
            lambda: self._set_frame_lock_scope("crop", "physical")
        )
        self.menu_bar.action_lock_crop_amplifier.triggered.connect(
            lambda: self._set_frame_lock_scope("crop", "amplifier")
        )
        self.menu_bar.action_lock_crop_detector.triggered.connect(
            lambda: self._set_frame_lock_scope("crop", "detector")
        )
        self.menu_bar.action_lock_slice_none.triggered.connect(lambda: self._set_frame_lock_scope("slice", "none"))
        self.menu_bar.action_lock_slice_wcs.triggered.connect(lambda: self._set_frame_lock_scope("slice", "wcs"))
        self.menu_bar.action_lock_slice_image.triggered.connect(
            lambda: self._set_frame_lock_scope("slice", "image")
        )
        self.menu_bar.action_lock_bin.triggered.connect(
            lambda checked=False: self._set_frame_lock_flag("bin", self.menu_bar.action_lock_bin.isChecked())
        )
        self.menu_bar.action_lock_axes_order.triggered.connect(
            lambda checked=False: self._set_frame_lock_flag(
                "axes_order",
                self.menu_bar.action_lock_axes_order.isChecked(),
            )
        )
        self.menu_bar.action_lock_scale.triggered.connect(
            lambda checked=False: self._set_frame_lock_flag("scale", self.menu_bar.action_lock_scale.isChecked())
        )
        self.menu_bar.action_lock_scale_limits.triggered.connect(
            lambda checked=False: self._set_frame_lock_flag(
                "scale_limits",
                self.menu_bar.action_lock_scale_limits.isChecked(),
            )
        )
        self.menu_bar.action_lock_colorbar.triggered.connect(
            lambda checked=False: self._set_frame_lock_flag(
                "colorbar",
                self.menu_bar.action_lock_colorbar.isChecked(),
            )
        )
        self.menu_bar.action_lock_block.triggered.connect(
            lambda checked=False: self._set_frame_lock_flag("block", self.menu_bar.action_lock_block.isChecked())
        )
        self.menu_bar.action_lock_smooth.triggered.connect(
            lambda checked=False: self._set_frame_lock_flag("smooth", self.menu_bar.action_lock_smooth.isChecked())
        )
        self.menu_bar.action_lock_3d.triggered.connect(
            lambda checked=False: self._set_frame_lock_flag("3d", self.menu_bar.action_lock_3d.isChecked())
        )
        self.menu_bar.action_tile_mode_grid.triggered.connect(lambda: self._set_tile_arrangement_mode("grid"))
        self.menu_bar.action_tile_mode_columns.triggered.connect(
            lambda: self._set_tile_arrangement_mode("column")
        )
        self.menu_bar.action_tile_mode_rows.triggered.connect(lambda: self._set_tile_arrangement_mode("row"))
        for interval, action in self.menu_bar.blink_interval_actions.items():
            action.triggered.connect(
                lambda checked=False, ms=interval: self._set_blink_interval(ms)
            )
        for interval, action in self.menu_bar.fade_interval_actions.items():
            action.triggered.connect(
                lambda checked=False, ms=interval: self._set_fade_interval(ms)
            )
        self.menu_bar.action_frame_cube_dialog.triggered.connect(lambda: self._show_frame_dialog("cube"))
        self.menu_bar.action_frame_rgb_dialog.triggered.connect(lambda: self._show_frame_dialog("rgb"))
        self.menu_bar.action_frame_hsv_dialog.triggered.connect(lambda: self._show_frame_dialog("hsv"))
        self.menu_bar.action_frame_hls_dialog.triggered.connect(lambda: self._show_frame_dialog("hls"))
        self.menu_bar.action_frame_3d_dialog.triggered.connect(lambda: self._show_frame_dialog("3d"))
        
        # Bin menu
        self.menu_bar.action_bin_1.triggered.connect(lambda: self._set_bin(1))
        self.menu_bar.action_bin_2.triggered.connect(lambda: self._set_bin(2))
        self.menu_bar.action_bin_4.triggered.connect(lambda: self._set_bin(4))
        self.menu_bar.action_bin_8.triggered.connect(lambda: self._set_bin(8))
        
        # Scale menu
        self.menu_bar.action_scale_linear.triggered.connect(lambda: self._set_scale(ScaleAlgorithm.LINEAR))
        self.menu_bar.action_scale_log.triggered.connect(lambda: self._set_scale(ScaleAlgorithm.LOG))
        self.menu_bar.action_scale_sqrt.triggered.connect(lambda: self._set_scale(ScaleAlgorithm.SQRT))
        self.menu_bar.action_scale_squared.triggered.connect(lambda: self._set_scale(ScaleAlgorithm.POWER))
        self.menu_bar.action_scale_asinh.triggered.connect(lambda: self._set_scale(ScaleAlgorithm.ASINH))
        self.menu_bar.action_scale_histeq.triggered.connect(lambda: self._set_scale(ScaleAlgorithm.HISTOGRAM_EQUALIZATION))
        self.menu_bar.action_scale_zscale.triggered.connect(self._reset_scale_limits)
        self.menu_bar.action_scale_minmax.triggered.connect(self._scale_minmax)
        self.menu_bar.action_scale_params.triggered.connect(self._show_scale_dialog)
        
        # Color menu
        for cmap_name, action in self.menu_bar.colormap_actions.items():
            action.triggered.connect(lambda checked=False, name=cmap_name: self._set_colormap(name))
        self.menu_bar.action_invert_colormap.triggered.connect(self._toggle_invert_colormap)
        self.menu_bar.action_reset_colormap.triggered.connect(self._reset_colormap)
        self.menu_bar.action_colorbar.triggered.connect(self._toggle_colorbar_visibility)
        self.menu_bar.action_colorbar_horizontal.triggered.connect(
            lambda checked=False: self._set_colorbar_orientation("horizontal")
        )
        self.menu_bar.action_colorbar_vertical.triggered.connect(
            lambda checked=False: self._set_colorbar_orientation("vertical")
        )
        self.menu_bar.action_colorbar_numerics_show.triggered.connect(self._set_colorbar_numerics)
        self.menu_bar.action_colorbar_space_value.triggered.connect(
            lambda checked=False: self._set_colorbar_spacing_mode("value")
        )
        self.menu_bar.action_colorbar_space_distance.triggered.connect(
            lambda checked=False: self._set_colorbar_spacing_mode("distance")
        )
        self.menu_bar.action_colorbar_font_small.triggered.connect(
            lambda checked=False: self._set_colorbar_font_size(7)
        )
        self.menu_bar.action_colorbar_font_medium.triggered.connect(
            lambda checked=False: self._set_colorbar_font_size(8)
        )
        self.menu_bar.action_colorbar_font_large.triggered.connect(
            lambda checked=False: self._set_colorbar_font_size(10)
        )
        self.menu_bar.action_colorbar_size.triggered.connect(self._show_colorbar_size_dialog)
        self.menu_bar.action_colorbar_ticks.triggered.connect(self._show_colorbar_ticks_dialog)
        self.menu_bar.action_colormap_params.triggered.connect(self._show_colormap_dialog)
        self.menu_bar.action_load_user_colormap.triggered.connect(self._load_user_colormap)
        self.menu_bar.action_save_user_colormap.triggered.connect(self._save_current_colormap)
        
        # Region menu
        self.menu_bar.action_region_none.triggered.connect(lambda: self._set_region_mode(RegionMode.NONE))
        self.menu_bar.action_region_circle.triggered.connect(lambda: self._set_region_mode(RegionMode.CIRCLE))
        self.menu_bar.action_region_ellipse.triggered.connect(lambda: self._set_region_mode(RegionMode.ELLIPSE))
        self.menu_bar.action_region_box.triggered.connect(lambda: self._set_region_mode(RegionMode.BOX))
        self.menu_bar.action_region_polygon.triggered.connect(lambda: self._set_region_mode(RegionMode.POLYGON))
        self.menu_bar.action_region_line.triggered.connect(lambda: self._set_region_mode(RegionMode.LINE))
        self.menu_bar.action_region_point.triggered.connect(lambda: self._set_region_mode(RegionMode.POINT))
        self.menu_bar.action_region_load.triggered.connect(self._load_regions)
        self.menu_bar.action_region_save.triggered.connect(self._save_regions)
        self.menu_bar.action_region_delete_all.triggered.connect(self._clear_regions)

        # VO menu
        self.menu_bar.action_siap_2mass.triggered.connect(self._vo_siap_2mass)
        self.menu_bar.action_catalog_vizier.triggered.connect(self._vo_catalog_vizier)
        self.menu_bar.action_samp_connect.triggered.connect(self._samp_connect)
        self.menu_bar.action_samp_disconnect.triggered.connect(self._samp_disconnect)
        self.menu_bar.action_samp_marker_color.triggered.connect(self._samp_choose_marker_color)
        self.menu_bar.action_samp_marker_shape.triggered.connect(self._samp_choose_marker_shape)
        self.menu_bar.action_samp_marker_size.triggered.connect(self._samp_choose_marker_size)
        
        # WCS menu - connect all coordinate system options
        self.menu_bar.action_wcs_fk5.triggered.connect(lambda: self._set_wcs_system("fk5"))
        self.menu_bar.action_wcs_fk4.triggered.connect(lambda: self._set_wcs_system("fk4"))
        self.menu_bar.action_wcs_icrs.triggered.connect(lambda: self._set_wcs_system("icrs"))
        self.menu_bar.action_wcs_galactic.triggered.connect(lambda: self._set_wcs_system("galactic"))
        self.menu_bar.action_wcs_ecliptic.triggered.connect(lambda: self._set_wcs_system("ecliptic"))
        self.menu_bar.action_wcs_sexagesimal.triggered.connect(lambda: self._set_wcs_format("sexagesimal"))
        self.menu_bar.action_wcs_degrees.triggered.connect(lambda: self._set_wcs_format("degrees"))
        self.menu_bar.action_show_direction_arrows.triggered.connect(self._toggle_direction_arrows)
        
        # Analysis menu - connect all tools
        self.menu_bar.action_name_resolution.triggered.connect(self._resolve_object_name)
        self.menu_bar.action_statistics.triggered.connect(self._show_statistics)
        self.menu_bar.action_histogram.triggered.connect(self._show_histogram)
        self.menu_bar.action_radial_profile.triggered.connect(self._show_radial_profile)
        self.menu_bar.action_mask_params.triggered.connect(self._show_mask_parameters)
        self.menu_bar.action_crosshair_params.triggered.connect(self._show_crosshair_parameters)
        self.menu_bar.action_graph_params.triggered.connect(self._show_graph_parameters)
        self.menu_bar.action_contours.triggered.connect(self._toggle_contours)
        self.menu_bar.action_contour_params.triggered.connect(self._show_contours)
        self.menu_bar.action_coordinate_grid.triggered.connect(self._toggle_coordinate_grid)
        self.menu_bar.action_coordinate_grid_params.triggered.connect(self._show_grid_dialog)
        self.menu_bar.action_block_in.triggered.connect(self._block_in)
        self.menu_bar.action_block_out.triggered.connect(self._block_out)
        self.menu_bar.action_block_fit.triggered.connect(self._block_fit)
        self.menu_bar.action_block_1.triggered.connect(lambda: self._set_block_factor(1))
        self.menu_bar.action_block_2.triggered.connect(lambda: self._set_block_factor(2))
        self.menu_bar.action_block_4.triggered.connect(lambda: self._set_block_factor(4))
        self.menu_bar.action_block_8.triggered.connect(lambda: self._set_block_factor(8))
        self.menu_bar.action_block_16.triggered.connect(lambda: self._set_block_factor(16))
        self.menu_bar.action_block_32.triggered.connect(lambda: self._set_block_factor(32))
        self.menu_bar.action_block_params.triggered.connect(self._show_block_parameters)
        self.menu_bar.action_smooth.triggered.connect(self._toggle_smooth)
        self.menu_bar.action_smooth_params.triggered.connect(self._show_smooth_dialog)
        self.menu_bar.action_analysis_2mass.triggered.connect(self._vo_siap_2mass)
        self.menu_bar.action_analysis_vizier.triggered.connect(self._vo_catalog_vizier)
        self.menu_bar.action_catalog_tool.triggered.connect(self._vo_catalog_vizier)
        self.menu_bar.action_plot_tool_line.triggered.connect(lambda: self._set_graph_visibility("Both"))
        self.menu_bar.action_plot_tool_bar.triggered.connect(lambda: self._set_graph_visibility("Vertical"))
        self.menu_bar.action_virtual_observatory.triggered.connect(self._vo_catalog_vizier)
        self.menu_bar.action_web_browser.triggered.connect(self._open_analysis_web_browser)
        self.menu_bar.action_analysis_command_log.triggered.connect(self._set_analysis_command_log)
        self.menu_bar.action_load_analysis_commands.triggered.connect(self._load_analysis_commands)
        self.menu_bar.action_clear_analysis_commands.triggered.connect(self._clear_analysis_commands)
        self.menu_bar.action_pixel_table.triggered.connect(self._show_pixel_table)
        self.menu_bar.action_fits_header.triggered.connect(self._show_fits_header)
        
        # Zoom menu
        self.menu_bar.action_zoom_in.triggered.connect(self._zoom_in)
        self.menu_bar.action_zoom_out.triggered.connect(self._zoom_out)
        self.menu_bar.action_zoom_fit.triggered.connect(self._zoom_fit)
        self.menu_bar.action_zoom_1.triggered.connect(self._zoom_actual)
        self.menu_bar.action_zoom_center.triggered.connect(lambda: self.statusBar().showMessage("Center not implemented", 2000))
        
        # Help menu
        self.menu_bar.action_help_contents.triggered.connect(self._show_help_contents)
        self.menu_bar.action_keyboard_shortcuts.triggered.connect(self._show_keyboard_shortcuts)
        self.menu_bar.action_about.triggered.connect(self.show_about)
        self.menu_bar.action_about_qt.triggered.connect(self.show_about_qt)

    def _setup_toolbar(self) -> None:
        """Set up the main toolbar."""
        self.main_toolbar = MainToolbar(self)
        self.addToolBar(self.main_toolbar)
        
        # Connect toolbar actions
        self.main_toolbar.action_open.triggered.connect(self.open_file)
        self.main_toolbar.action_save.triggered.connect(self.save_file)
        self.main_toolbar.action_zoom_in.triggered.connect(self._zoom_in)
        self.main_toolbar.action_zoom_out.triggered.connect(self._zoom_out)
        self.main_toolbar.action_zoom_fit.triggered.connect(self._zoom_fit)
        self.main_toolbar.action_zoom_1.triggered.connect(self._zoom_actual)
        self.main_toolbar.action_statistics.triggered.connect(self._show_statistics)
        self.main_toolbar.action_histogram.triggered.connect(self._show_histogram)
        self.main_toolbar.action_prev_frame.triggered.connect(self._prev_frame)
        self.main_toolbar.action_next_frame.triggered.connect(self._next_frame)
        self.main_toolbar.action_region_circle.triggered.connect(lambda: self._set_region_mode(RegionMode.CIRCLE))
        self.main_toolbar.action_region_box.triggered.connect(lambda: self._set_region_mode(RegionMode.BOX))
        self.main_toolbar.action_region_polygon.triggered.connect(lambda: self._set_region_mode(RegionMode.POLYGON))

    def _setup_central_widget(self) -> None:
        """Set up the central widget."""
        # Create scroll area for image display
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)  # Allow widget to use full viewport
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.horizontalScrollBar().valueChanged.connect(
            lambda _: self._update_panner_view_rect()
        )
        self.scroll_area.verticalScrollBar().valueChanged.connect(
            lambda _: self._update_panner_view_rect()
        )
        
        # Create interactive image viewer with regions
        self.image_viewer = self._create_image_viewer(self.use_gpu_rendering)

        self.scroll_area.setWidget(self.image_viewer)
        self.setCentralWidget(self.scroll_area)

    def _create_image_viewer(self, use_gpu: bool):
        """Create an image viewer and connect signals."""
        if use_gpu:
            try:
                viewer = GLImageViewerWithRegions()
                self.using_gpu_rendering = True
            except Exception:
                viewer = ImageViewerWithRegions()
                self.using_gpu_rendering = False
        else:
            viewer = ImageViewerWithRegions()
            self.using_gpu_rendering = False

        viewer.setText("No image loaded")
        viewer.mouse_moved.connect(self._on_mouse_moved)
        viewer.mouse_clicked.connect(self._on_image_clicked)
        viewer.contrast_changed.connect(self._on_contrast_changed)
        viewer.region_created.connect(self._on_region_created)
        viewer.region_selected.connect(self._on_region_selected)
        if hasattr(viewer, "gl_canvas"):
            viewer.gl_canvas.pan_changed.connect(lambda *_: self._update_panner_view_rect())
            viewer.gl_canvas.zoom_changed.connect(lambda *_: self._update_panner_view_rect())
        return viewer

    def _setup_dock_widgets(self) -> None:
        """Set up dock widgets."""
        # Left dock for button bar
        self.button_bar_dock = QDockWidget("Controls", self)
        self.button_bar = ButtonBar(self)
        
        # Connect button bar signals
        self.button_bar.zoom_changed.connect(self._on_button_bar_zoom)
        self.button_bar.scale_changed.connect(self._on_button_bar_scale)
        self.button_bar.colormap_changed.connect(self._on_button_bar_colormap)
        self.button_bar.region_mode_changed.connect(self._on_button_bar_region)
        
        self.button_bar_dock.setWidget(self.button_bar)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.button_bar_dock)

        # Right dock for colorbar
        self.colorbar_dock = QDockWidget("Colorbar", self)
        self.colorbar_widget = ColorbarWidget(self)
        self.colorbar_dock.setWidget(self.colorbar_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.colorbar_dock)
        self.colorbar_dock.visibilityChanged.connect(self.menu_bar.action_colorbar.setChecked)
        
        # Top-right dock for panner (DS9 style)
        self.panner_dock = QDockWidget("Panner", self)
        self.panner_panel = PannerPanel(self)
        self.panner_panel.pan_to.connect(self._on_panner_pan)
        self.panner_dock.setWidget(self.panner_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.panner_dock)
        
        # Top-right dock for magnifier (DS9 style)
        self.magnifier_dock = QDockWidget("Magnifier", self)
        self.magnifier_panel = MagnifierPanel(self)
        self.magnifier_dock.setWidget(self.magnifier_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.magnifier_dock)

        self.horizontal_graph_dock = HorizontalGraph(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.horizontal_graph_dock)
        self.horizontal_graph_dock.hide()

        self.vertical_graph_dock = VerticalGraph(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.vertical_graph_dock)
        self.vertical_graph_dock.hide()

    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

    def _preferences_path(self) -> Path:
        """Return the default preferences file path."""
        return Path.home() / ".ncrads9" / "preferences.json"

    def _get_preferences_dict(self) -> dict:
        """Get current preferences as a dict with defaults."""
        return {
            "use_gpu": self.preferences.get("use_gpu", True),
            "tile_size": self.preferences.get("tile_size", 512),
            "cache_size_mb": self.preferences.get("cache_size_mb", 1000),
            "background_color": self.preferences.get("background_color", "#000000"),
            "default_scale": self.preferences.get("default_scale", "Linear"),
            "default_colormap": self.preferences.get("default_colormap", "gray"),
            "anti_aliasing": self.preferences.get("anti_aliasing", True),
        }

    def _show_preferences(self) -> None:
        """Show preferences dialog."""
        dialog = PreferencesDialog(self)
        dialog.load_preferences(self._get_preferences_dict())
        dialog.preferences_changed.connect(self._apply_preferences)
        dialog.exec()

    def _apply_preferences(
        self,
        prefs: dict,
        persist: bool = True,
        show_message: bool = True,
    ) -> None:
        """Apply preferences and optionally persist them."""
        if persist:
            for key, value in prefs.items():
                self.preferences.set(key, value, save=False)
            self.preferences.save()

        use_gpu = bool(prefs.get("use_gpu", self.use_gpu_rendering))
        if use_gpu != self.use_gpu_rendering:
            self._rebuild_image_viewer(use_gpu)

        tile_size = int(prefs.get("tile_size", 512))
        cache_size_mb = int(prefs.get("cache_size_mb", 1000))
        if self.using_gpu_rendering:
            if hasattr(self.image_viewer, "set_tile_size"):
                self.image_viewer.set_tile_size(tile_size)
            if hasattr(self.image_viewer, "set_cache_size_mb"):
                self.image_viewer.set_cache_size_mb(cache_size_mb)

        background_color = prefs.get("background_color", "#000000")
        self._apply_background_color(background_color)

        default_scale = prefs.get("default_scale", "Linear")
        scale_map = {
            "Linear": ScaleAlgorithm.LINEAR,
            "Log": ScaleAlgorithm.LOG,
            "Sqrt": ScaleAlgorithm.SQRT,
            "Power": ScaleAlgorithm.POWER,
            "Asinh": ScaleAlgorithm.ASINH,
        }
        if default_scale in scale_map:
            self._set_scale(scale_map[default_scale])

        default_colormap = self._normalize_colormap_name(str(prefs.get("default_colormap", "gray")))
        if default_colormap in self.menu_bar.colormap_actions:
            self._set_colormap(default_colormap)

        if self.image_data is not None:
            self._display_image()

        if show_message:
            self.statusBar().showMessage("Preferences updated", 2000)

    def _rebuild_image_viewer(self, use_gpu: bool) -> None:
        """Recreate the image viewer based on GPU setting."""
        self.use_gpu_rendering = use_gpu
        new_viewer = self._create_image_viewer(use_gpu)
        old_viewer = self.image_viewer
        self.image_viewer = new_viewer
        self.scroll_area.setWidget(self.image_viewer)
        old_viewer.deleteLater()
        if self.image_data is not None:
            self._display_image()

    def _apply_background_color(self, color_hex: str) -> None:
        """Apply background color to the viewer."""
        if self.using_gpu_rendering and hasattr(self.image_viewer, "set_background_color"):
            self.image_viewer.set_background_color(color_hex)
        elif hasattr(self.image_viewer, "set_background_color"):
            self.image_viewer.set_background_color(color_hex)

    def _apply_frame_pan(self, frame: Frame) -> None:
        """Apply stored pan to the GPU canvas."""
        if not (self.using_gpu_rendering and hasattr(self.image_viewer, "gl_canvas")):
            return
        if frame.pan_x == 0.0 and frame.pan_y == 0.0:
            return
        canvas = self.image_viewer.gl_canvas
        canvas.pan_offset = (frame.pan_x, frame.pan_y)
        canvas.pan_changed.emit(frame.pan_x, frame.pan_y)
        canvas.update()

    def open_file(self, checked: bool = False, filepath: Optional[str] = None) -> None:
        """
        Open a FITS file.

        Args:
            checked: Ignored (from Qt signal).
            filepath: Optional path to the file. If None, shows a file dialog.
        """
        # Handle case where checked is actually a filepath string
        if isinstance(checked, str):
            filepath = checked
            
        if filepath is None or filepath is False:
            filepath, _ = QFileDialog.getOpenFileName(
                self,
                "Open FITS File",
                "",
                "FITS Files (*.fits *.fit *.fts *.fits.gz *.fit.gz);;All Files (*)",
            )

        if filepath:
            try:
                self._load_fits_file(filepath)
                self.statusBar().showMessage(f"Opened: {filepath}", 3000)
            except Exception as e:
                self.statusBar().showMessage(f"Error loading file: {e}", 5000)
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error Loading File", 
                                   f"Could not load FITS file:\n{filepath}\n\nError: {e}")
    
    def _load_fits_file(self, filepath: str) -> None:
        """
        Load a FITS file into current frame.
        
        Args:
            filepath: Path to the FITS file.
        """
        # Get current frame
        frame = self.frame_manager.current_frame
        if not frame:
            frame = self.frame_manager.new_frame()
            self._active_frame_ids.add(frame.frame_id)

        old_handler = frame.fits_handler
        if old_handler is not None:
            try:
                old_handler.close()
            except Exception:
                pass
        
        # Load FITS file
        fits_handler = FITSHandler()
        fits_handler.load(filepath)
        image_data = fits_handler.get_data()
        
        # Load WCS if available
        header = fits_handler.get_header()
        wcs_handler = WCSHandler(header)
        
        # Update frame
        frame.filepath = Path(filepath)
        frame.fits_handler = fits_handler
        if frame.frame_type == "rgb":
            channel = frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
            frame.rgb_channels[channel] = np.array(image_data, copy=True)
            frame.rgb_source_frame_ids[channel] = None
            self._sync_rgb_scalar_view(frame)
        else:
            frame.image_data = image_data
            frame.original_image_data = image_data
        frame.bin_factor = 1
        frame.header = header
        frame.wcs_handler = wcs_handler
        frame.colormap = self.current_colormap
        frame.scale = self.current_scale
        frame.invert_colormap = self.invert_colormap
        frame.z1 = None
        frame.z2 = None

        # Reset display state for new data
        self.z1 = None
        self.z2 = None
        if hasattr(self.image_viewer, "reset_contrast_brightness"):
            self.image_viewer.reset_contrast_brightness()
        
        # Update window title
        filename = Path(filepath).name
        frame_info = f"Frame {self.frame_manager.current_index + 1}/{self.frame_manager.num_frames}"
        self.setWindowTitle(f"NCRADS9 - {filename} [{frame_info}]")
        
        # Display the image
        self._display_image()
        
        # Fit image to window on initial load
        self._zoom_fit()
        
        # Update status bar image info
        shape = image_data.shape
        dtype = image_data.dtype
        self.status_bar.update_image_info(shape[1], shape[0])
        
        # Update temporary message
        stats_msg = f"Loaded: {shape[1]}x{shape[0]} pixels, {dtype}"
        if wcs_handler.is_valid:
            stats_msg += " (WCS available)"
        self.statusBar().showMessage(stats_msg, 3000)

    @staticmethod
    def _downsample_for_preview(
        image_data: NDArray[np.float32],
        max_pixels: int = 4_000_000,
    ) -> NDArray[np.float32]:
        """Return a strided preview view for large images."""
        height, width = image_data.shape[:2]
        total_pixels = int(height * width)
        if total_pixels <= max_pixels:
            return image_data
        stride = max(1, int(np.ceil(np.sqrt(total_pixels / max_pixels))))
        return image_data[::stride, ::stride]

    def _render_preview_rgb(
        self,
        image_data: NDArray[np.float32],
        z1: float,
        z2: float,
        cmap: Colormap,
    ) -> NDArray[np.uint8]:
        """Render a lightweight RGB preview for panner/magnifier panels."""
        preview_data = self._downsample_for_preview(image_data)
        clipped_preview = np.clip(preview_data, z1, z2)
        scaled_preview = apply_scale(
            clipped_preview,
            self.current_scale,
            vmin=z1,
            vmax=z2,
        )
        rgb_preview = cmap.apply(scaled_preview)
        return np.ascontiguousarray(np.flipud(rgb_preview))

    @staticmethod
    def _extract_gpu_tile_data(
        data: NDArray[np.floating],
        x: int,
        y: int,
        w: int,
        h: int,
    ) -> NDArray[np.floating]:
        """Extract tile data for GPU upload."""
        return np.ascontiguousarray(data[y : y + h, x : x + w])
    
    def _display_image(self) -> None:
        """Display the current frame's image data."""
        if self._tile_mode_enabled:
            self._display_tiled_frames()
            return

        frame = self.frame_manager.current_frame
        if not frame:
            return
        if frame.frame_type == "rgb":
            self._display_rgb_frame(frame)
            return
        if not frame.has_data:
            return
        
        image_data = self._get_display_image_data(frame)
        
        # Compute scale limits using zscale (once, or when reset)
        if self.z1 is None or self.z2 is None:
            self.z1, self.z2 = compute_zscale_limits(image_data)
        
        # Get contrast/brightness adjustments from viewer
        contrast, brightness = self.image_viewer.get_contrast_brightness()
        
        # Apply adjustments to scale limits
        range_val = self.z2 - self.z1
        center = (self.z1 + self.z2) / 2
        new_range = range_val / contrast
        adjusted_z1 = center - new_range / 2 + brightness * range_val
        adjusted_z2 = center + new_range / 2 + brightness * range_val
        
        # Apply colormap
        try:
            cmap = self._get_colormap_instance(self.current_colormap)
        except ValueError:
            self.current_colormap = "grey"
            cmap = self._get_colormap_instance(self.current_colormap)

        # Invert colormap if needed
        if self.invert_colormap:
            # Get colormap data and invert
            cmap_data = cmap.colors.copy()
            cmap_data = cmap_data[::-1]  # Reverse the colormap
            cmap = Colormap(f"{self.current_colormap}_inverted", cmap_data)
        
        # Update colorbar
        self.colorbar_widget.set_colormap(
            cmap.colors, adjusted_z1, adjusted_z2, 
            self.current_colormap, self.invert_colormap
        )
        
        if self.using_gpu_rendering:
            def tile_provider(x: int, y: int, w: int, h: int) -> NDArray[np.uint8]:
                tile = self._extract_gpu_tile_data(image_data, x, y, w, h)
                clipped = np.clip(tile, adjusted_z1, adjusted_z2)
                scaled = apply_scale(clipped, self.current_scale, vmin=adjusted_z1, vmax=adjusted_z2)
                rgb = cmap.apply(scaled)
                return rgb

            self.image_viewer.set_tile_provider(image_data.shape[1], image_data.shape[0], tile_provider)
            self.image_viewer.set_value_source(image_data)
            display_rgb = self._render_preview_rgb(
                image_data,
                adjusted_z1,
                adjusted_z2,
                cmap,
            )
        else:
            # Clip and scale the data
            clipped = np.clip(image_data, adjusted_z1, adjusted_z2)
            scaled = apply_scale(clipped, self.current_scale, vmin=adjusted_z1, vmax=adjusted_z2)
            rgb_full = cmap.apply(scaled)
            display_rgb = np.ascontiguousarray(np.flipud(rgb_full))

            # Convert to QImage
            height, width = display_rgb.shape[:2]
            bytes_per_line = 3 * width
            qimage = QImage(display_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            
            # Create pixmap and display
            pixmap = QPixmap.fromImage(qimage)
            self.image_viewer.set_image(pixmap)
        
        # Update panner panel with RGB data (DS9 style)
        if hasattr(self, 'panner_panel'):
            self.panner_panel.set_image(
                display_rgb,
                source_size=(image_data.shape[1], image_data.shape[0]),
            )
            self._update_panner_view_rect()
        
        # Update magnifier panel with RGB data (DS9 style)
        if hasattr(self, 'magnifier_panel'):
            self.magnifier_panel.set_image(
                display_rgb,
                source_size=(image_data.shape[1], image_data.shape[0]),
            )
        if hasattr(self, "horizontal_graph_dock"):
            self.horizontal_graph_dock.set_image(image_data)
        if hasattr(self, "vertical_graph_dock"):
            self.vertical_graph_dock.set_image(image_data)
        
        # Update zoom display
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self._update_bin_menu_checks(getattr(frame, "bin_factor", 1))
        self._update_regions_for_frame(frame)
        self._sync_frame_view_state()
        if self._contour_settings is not None:
            self._update_contours()
        self._update_direction_arrows()
        self._refresh_analysis_overlays()

    def _display_rgb_frame(self, frame: Frame) -> bool:
        """Display a composite RGB frame."""
        active_channel = frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
        contrast, brightness = self.image_viewer.get_contrast_brightness()
        frame.rgb_channel_scale[active_channel] = self.current_scale
        frame.rgb_channel_z1[active_channel] = self.z1
        frame.rgb_channel_z2[active_channel] = self.z2
        frame.rgb_channel_contrast[active_channel] = contrast
        frame.rgb_channel_brightness[active_channel] = brightness
        composite = self._compose_rgb_frame_image(frame)
        if composite is None:
            self.statusBar().showMessage("RGB frame has no channel data", 2000)
            return False

        active_data = self._get_rgb_active_channel_data(frame)
        if active_data is None:
            active_data = np.mean(composite.astype(np.float32), axis=2)

        self._sync_rgb_scalar_view(frame)
        self.colorbar_widget.set_colormap(
            self._get_colormap_instance("grey").colors,
            0.0,
            255.0,
            "RGB Composite",
            False,
        )
        display_rgb = np.ascontiguousarray(np.flipud(composite))

        if self.using_gpu_rendering:
            def tile_provider(x: int, y: int, w: int, h: int) -> NDArray[np.uint8]:
                return self._extract_gpu_tile_data(composite, x, y, w, h)

            self.image_viewer.set_tile_provider(composite.shape[1], composite.shape[0], tile_provider)
            self.image_viewer.set_value_source(active_data.astype(np.float32))
        else:
            height, width = display_rgb.shape[:2]
            bytes_per_line = 3 * width
            qimage = QImage(display_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            self.image_viewer.set_image(QPixmap.fromImage(qimage))

        if hasattr(self, "panner_panel"):
            self.panner_panel.set_image(
                display_rgb,
                source_size=(composite.shape[1], composite.shape[0]),
            )
            self._update_panner_view_rect()
        if hasattr(self, "magnifier_panel"):
            self.magnifier_panel.set_image(
                display_rgb,
                source_size=(composite.shape[1], composite.shape[0]),
            )
        if hasattr(self, "horizontal_graph_dock"):
            self.horizontal_graph_dock.set_image(active_data)
        if hasattr(self, "vertical_graph_dock"):
            self.vertical_graph_dock.set_image(active_data)

        self.status_bar.update_image_info(composite.shape[1], composite.shape[0])
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self._update_bin_menu_checks(getattr(frame, "bin_factor", 1))
        self._update_regions_for_frame(frame)
        self._sync_frame_view_state()
        if self._contour_settings is not None:
            self._update_contours()
        self._update_direction_arrows()
        self._refresh_analysis_overlays()
        return True

    def _render_frame_rgb(self, frame: Frame) -> Optional[NDArray[np.uint8]]:
        """Render a frame to RGB using its own display settings."""
        if frame.frame_type == "rgb":
            return self._compose_rgb_frame_image(frame)
        if not frame.has_data:
            return None

        image_data = self._get_display_image_data(frame)
        if image_data is None:
            return None

        z1 = frame.z1
        z2 = frame.z2
        if z1 is None or z2 is None:
            z1, z2 = compute_zscale_limits(image_data)

        contrast = max(frame.contrast, 0.1)
        brightness = max(-1.0, min(frame.brightness, 1.0))
        range_val = max(float(z2 - z1), 1e-6)
        center = (z1 + z2) / 2.0
        new_range = range_val / contrast
        adjusted_z1 = center - new_range / 2.0 + brightness * range_val
        adjusted_z2 = center + new_range / 2.0 + brightness * range_val

        try:
            cmap = self._get_colormap_instance(frame.colormap)
        except ValueError:
            frame.colormap = "grey"
            cmap = self._get_colormap_instance("grey")
        if frame.invert_colormap:
            cmap_data = cmap.colors.copy()[::-1]
            cmap = Colormap(f"{frame.colormap}_inverted", cmap_data)

        clipped = np.clip(image_data, adjusted_z1, adjusted_z2)
        scaled = apply_scale(clipped, frame.scale, vmin=adjusted_z1, vmax=adjusted_z2)
        return cmap.apply(scaled)

    def _display_tiled_frames(self) -> bool:
        """Render all loaded frames in a tiled grid."""
        rgb_frames: list[NDArray[np.uint8]] = []
        frame_indices: list[int] = []
        active_indices = self._get_active_frame_indices()
        for frame_index in active_indices:
            frame = self.frame_manager.frames[frame_index]
            rgb = self._render_frame_rgb(frame)
            if rgb is not None:
                rgb_frames.append(rgb)
                frame_indices.append(frame_index)

        if not rgb_frames:
            self._tile_layout = None
            self.statusBar().showMessage("No loaded frames to tile", 2000)
            return False

        count = len(rgb_frames)
        if self._tile_arrangement_mode == "column":
            cols = 1
            rows = count
        elif self._tile_arrangement_mode == "row":
            cols = count
            rows = 1
        else:
            cols = max(1, int(np.ceil(np.sqrt(count))))
            rows = int(np.ceil(count / cols))
        cell_h = max(rgb.shape[0] for rgb in rgb_frames)
        cell_w = max(rgb.shape[1] for rgb in rgb_frames)
        gap = 8

        tiled_h = rows * cell_h + (rows + 1) * gap
        tiled_w = cols * cell_w + (cols + 1) * gap
        tiled_rgb = np.zeros((tiled_h, tiled_w, 3), dtype=np.uint8)
        self._tile_layout = {
            "cols": cols,
            "rows": rows,
            "cell_w": cell_w,
            "cell_h": cell_h,
            "gap": gap,
            "tiled_w": tiled_w,
            "tiled_h": tiled_h,
            "frame_indices": frame_indices,
        }

        for index, rgb in enumerate(rgb_frames):
            row, col = divmod(index, cols)
            y0 = gap + row * (cell_h + gap)
            x0 = gap + col * (cell_w + gap)
            if rgb.shape[0] != cell_h or rgb.shape[1] != cell_w:
                y_idx = np.linspace(0, rgb.shape[0] - 1, cell_h).astype(np.int32)
                x_idx = np.linspace(0, rgb.shape[1] - 1, cell_w).astype(np.int32)
                rgb = rgb[y_idx][:, x_idx]
            tiled_rgb[y0 : y0 + cell_h, x0 : x0 + cell_w] = rgb
        display_rgb = np.flipud(tiled_rgb)
        display_rgb = np.ascontiguousarray(display_rgb)

        if self.using_gpu_rendering:
            def tile_provider(x: int, y: int, w: int, h: int) -> NDArray[np.uint8]:
                return self._extract_gpu_tile_data(tiled_rgb, x, y, w, h)

            self.image_viewer.set_tile_provider(tiled_w, tiled_h, tile_provider)
            self.image_viewer.set_value_source(np.mean(tiled_rgb, axis=2).astype(np.float32))
        else:
            bytes_per_line = 3 * tiled_w
            qimage = QImage(display_rgb.data, tiled_w, tiled_h, bytes_per_line, QImage.Format.Format_RGB888)
            self.image_viewer.set_image(QPixmap.fromImage(qimage))

        if hasattr(self.image_viewer, "clear_regions"):
            self.image_viewer.clear_regions()
        if hasattr(self.image_viewer, "clear_contours"):
            self.image_viewer.clear_contours()
        if hasattr(self.image_viewer, "set_direction_arrows"):
            self.image_viewer.set_direction_arrows(None, None, False)
        if hasattr(self, "panner_panel"):
            self.panner_panel.set_image(display_rgb)
            self.panner_panel.set_view_rect(None)
        if hasattr(self, "magnifier_panel"):
            self.magnifier_panel.set_image(display_rgb)
        self.status_bar.update_image_info(tiled_w, tiled_h)
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        return True
    
    def _set_scale(self, scale: ScaleAlgorithm) -> None:
        """
        Set the image scaling algorithm.
        
        Args:
            scale: The scaling algorithm to use.
        """
        self.current_scale = scale
        self._persist_frame_view_state()
        
        # Update menu checkboxes
        self.menu_bar.action_scale_linear.setChecked(scale == ScaleAlgorithm.LINEAR)
        self.menu_bar.action_scale_log.setChecked(scale == ScaleAlgorithm.LOG)
        self.menu_bar.action_scale_sqrt.setChecked(scale == ScaleAlgorithm.SQRT)
        self.menu_bar.action_scale_squared.setChecked(scale == ScaleAlgorithm.POWER)
        self.menu_bar.action_scale_asinh.setChecked(scale == ScaleAlgorithm.ASINH)
        self.menu_bar.action_scale_histeq.setChecked(scale == ScaleAlgorithm.HISTOGRAM_EQUALIZATION)
        
        # Update button bar
        scale_name_map = {
            ScaleAlgorithm.LINEAR: "Linear",
            ScaleAlgorithm.LOG: "Log",
            ScaleAlgorithm.SQRT: "Sqrt",
            ScaleAlgorithm.POWER: "Squared",
            ScaleAlgorithm.ASINH: "Asinh",
            ScaleAlgorithm.HISTOGRAM_EQUALIZATION: "HistEq",
        }
        if scale in scale_name_map:
            self.button_bar.set_scale(scale_name_map[scale])
        
        # Redisplay with new scale
        if self.image_data is not None:
            self._display_image()
            self.statusBar().showMessage(f"Scale: {scale.name}", 2000)

    @staticmethod
    def _normalize_colormap_name(name: str) -> str:
        """Normalize colormap aliases to internal names."""
        lower = name.strip().lower()
        if lower == "gray":
            return "grey"
        return lower

    def _get_colormap_instance(self, name: str) -> Colormap:
        """Return built-in or runtime-loaded colormap instance."""
        cmap_name = self._normalize_colormap_name(name)
        if cmap_name in self.custom_colormaps:
            return self.custom_colormaps[cmap_name]
        cmap = get_colormap(cmap_name)
        if cmap is None:
            raise ValueError(f"Unknown colormap: {name}")
        return cmap

    def get_available_colormaps(self) -> List[str]:
        """Return currently available colormap names."""
        return sorted(self.menu_bar.colormap_actions.keys())

    def _update_colormap_menu_checks(self) -> None:
        """Sync menu check marks with current colormap selection."""
        for cmap_name, action in self.menu_bar.colormap_actions.items():
            action.setChecked(cmap_name == self.current_colormap)
    
    def _set_colormap(self, colormap: str) -> None:
        """
        Set the colormap.
        
        Args:
            colormap: Name of the colormap to use.
        """
        cmap_name = self._normalize_colormap_name(colormap)
        if cmap_name not in self.menu_bar.colormap_actions:
            self.statusBar().showMessage(f"Unsupported colormap: {colormap}", 2000)
            return
        self.current_colormap = cmap_name
        self._persist_frame_view_state()
        
        # Update menu checkboxes
        self._update_colormap_menu_checks()
        
        # Update button bar
        cmap_name_map = {
            "grey": "Gray",
            "heat": "Heat",
            "cool": "Cool",
            "rainbow": "Rainbow",
        }
        if cmap_name in cmap_name_map:
            self.button_bar.set_colormap(cmap_name_map[cmap_name])
        
        # Redisplay with new colormap
        if self.image_data is not None:
            self._display_image()
            self.statusBar().showMessage(f"Colormap: {cmap_name}", 2000)

    def _reset_colormap(self) -> None:
        """Reset colormap and inversion to defaults."""
        self.invert_colormap = False
        self.menu_bar.action_invert_colormap.setChecked(False)
        self._set_colormap(self._default_colormap)
        self.statusBar().showMessage("Colormap reset", 2000)

    def _toggle_colorbar_visibility(self, checked: bool) -> None:
        """Show or hide colorbar dock."""
        self.colorbar_dock.setVisible(checked)

    def _set_colorbar_orientation(self, orientation: str) -> None:
        """Set colorbar orientation."""
        orientation_l = orientation.lower()
        self.colorbar_widget.set_orientation(orientation_l)
        self.menu_bar.action_colorbar_horizontal.setChecked(orientation_l == "horizontal")
        self.menu_bar.action_colorbar_vertical.setChecked(orientation_l == "vertical")
        self.statusBar().showMessage(f"Colorbar orientation: {orientation}", 2000)

    def _set_colorbar_numerics(self, checked: bool) -> None:
        """Set colorbar numerics visibility."""
        self.colorbar_widget.set_show_numerics(checked)
        self.menu_bar.action_colorbar_numerics_show.setChecked(checked)

    def _set_colorbar_spacing_mode(self, mode: str) -> None:
        """Set colorbar tick spacing mode."""
        mode_l = mode.lower()
        self.colorbar_widget.set_spacing_mode(mode_l)
        self.menu_bar.action_colorbar_space_value.setChecked(mode_l == "value")
        self.menu_bar.action_colorbar_space_distance.setChecked(mode_l == "distance")

    def _set_colorbar_font_size(self, size: int) -> None:
        """Set colorbar numeric label font size."""
        self.colorbar_widget.set_label_font_size(size)
        if size <= 7:
            self.menu_bar.action_colorbar_font_small.setChecked(True)
        elif size >= 10:
            self.menu_bar.action_colorbar_font_large.setChecked(True)
        else:
            self.menu_bar.action_colorbar_font_medium.setChecked(True)

    def _show_colorbar_size_dialog(self) -> None:
        """Prompt for colorbar size and apply it."""
        size, ok = QInputDialog.getInt(
            self,
            "Colorbar Size",
            "Size:",
            value=self.colorbar_widget.bar_size,
            min=12,
            max=96,
        )
        if ok:
            self.colorbar_widget.set_bar_size(size)

    def _show_colorbar_ticks_dialog(self) -> None:
        """Prompt for number of colorbar ticks and apply it."""
        ticks, ok = QInputDialog.getInt(
            self,
            "Colorbar Ticks",
            "Number of ticks:",
            value=self.colorbar_widget.tick_count,
            min=2,
            max=30,
        )
        if ok:
            self.colorbar_widget.set_tick_count(ticks)

    def _show_colormap_dialog(self) -> None:
        """Open colormap parameter dialog."""
        from .dialogs.colormap_dialog import ColormapDialog

        dialog = ColormapDialog(self)
        dialog.colormap_changed.connect(self._apply_colormap_dialog_settings)
        dialog.exec()

    def _apply_colormap_dialog_settings(self, settings: dict) -> None:
        """Apply settings emitted by ColormapDialog."""
        cmap_name = self._normalize_colormap_name(settings.get("colormap", self.current_colormap))
        if cmap_name in self.menu_bar.colormap_actions:
            self._set_colormap(cmap_name)
        invert = bool(settings.get("invert", self.invert_colormap))
        if invert != self.invert_colormap:
            self.menu_bar.action_invert_colormap.setChecked(invert)
            self._toggle_invert_colormap(invert)

    def _register_user_colormap(self, colormap: Colormap) -> None:
        """Register a user-loaded colormap and attach a menu action."""
        name = self._normalize_colormap_name(colormap.name)
        self.custom_colormaps[name] = Colormap(name, colormap.colors)
        action = self.menu_bar.add_user_colormap_action(name)
        if name not in self._user_colormap_actions:
            action.triggered.connect(lambda checked=False, cmap=name: self._set_colormap(cmap))
            self._user_colormap_actions[name] = action

    def _load_user_colormap(self) -> None:
        """Load a user colormap from .lut or .sao file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Colormap",
            "",
            "Colormap Files (*.lut *.sao);;LUT Files (*.lut);;SAO Files (*.sao);;All Files (*)",
        )
        if not filepath:
            return
        try:
            if filepath.lower().endswith(".sao"):
                cmap = parse_sao_file(filepath)
            else:
                cmap = parse_lut_file(filepath)
            self._register_user_colormap(cmap)
            self._set_colormap(cmap.name)
            self.statusBar().showMessage(f"Loaded colormap: {cmap.name}", 3000)
        except Exception as exc:
            self.statusBar().showMessage(f"Error loading colormap: {exc}", 3000)

    def _save_current_colormap(self) -> None:
        """Save current colormap to a LUT file."""
        try:
            cmap = self._get_colormap_instance(self.current_colormap)
        except ValueError as exc:
            self.statusBar().showMessage(str(exc), 3000)
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Colormap",
            f"{self.current_colormap}.lut",
            "LUT Files (*.lut);;All Files (*)",
        )
        if not filepath:
            return
        try:
            save_lut_file(cmap, filepath)
            self.statusBar().showMessage(f"Saved colormap: {filepath}", 3000)
        except Exception as exc:
            self.statusBar().showMessage(f"Error saving colormap: {exc}", 3000)

    def _update_block_menu_checks(self, factor: int) -> None:
        """Update Analysis->Block checkmarks based on current factor."""
        self.menu_bar.action_block_1.setChecked(factor == 1)
        self.menu_bar.action_block_2.setChecked(factor == 2)
        self.menu_bar.action_block_4.setChecked(factor == 4)
        self.menu_bar.action_block_8.setChecked(factor == 8)
        self.menu_bar.action_block_16.setChecked(factor == 16)
        self.menu_bar.action_block_32.setChecked(factor == 32)

    def _set_block_factor(self, factor: int) -> None:
        """Set block/bin factor from Analysis->Block menu."""
        allowed = [1, 2, 4, 8, 16, 32]
        nearest = min(allowed, key=lambda item: abs(item - factor))
        self._set_bin(nearest)
        self._log_analysis_command(f"block {nearest}")

    def _block_in(self) -> None:
        """Decrease block factor to next lower preset."""
        frame = self.frame_manager.current_frame
        current = getattr(frame, "bin_factor", 1) if frame else 1
        allowed = [1, 2, 4, 8, 16, 32]
        idx = max(0, allowed.index(current) - 1) if current in allowed else 0
        self._set_block_factor(allowed[idx])

    def _block_out(self) -> None:
        """Increase block factor to next higher preset."""
        frame = self.frame_manager.current_frame
        current = getattr(frame, "bin_factor", 1) if frame else 1
        allowed = [1, 2, 4, 8, 16, 32]
        idx = min(len(allowed) - 1, allowed.index(current) + 1) if current in allowed else 1
        self._set_block_factor(allowed[idx])

    def _block_fit(self) -> None:
        """Choose a block factor that roughly fits image into viewport."""
        frame = self.frame_manager.current_frame
        if not frame or frame.original_image_data is None:
            if frame and frame.image_data is not None:
                frame.original_image_data = frame.image_data
            else:
                self.statusBar().showMessage("No image loaded", 2000)
                return
        if frame.original_image_data is None:
            self.statusBar().showMessage("No image loaded", 2000)
            return

        height, width = frame.original_image_data.shape[:2]
        viewport = self.scroll_area.viewport().size()
        vw = max(1, viewport.width())
        vh = max(1, viewport.height())
        needed = max(width / vw, height / vh)
        allowed = [1, 2, 4, 8, 16, 32]
        factor = next((value for value in allowed if value >= needed), 32)
        self._set_block_factor(factor)

    def _show_block_parameters(self) -> None:
        """Show block-factor parameter dialog."""
        frame = self.frame_manager.current_frame
        current = getattr(frame, "bin_factor", 1) if frame else 1
        value, ok = QInputDialog.getInt(self, "Block Parameters", "Block factor:", int(current), 1, 32, 1)
        if not ok:
            return
        self._set_block_factor(value)

    def _show_smooth_dialog(self) -> None:
        """Show smoothing parameters dialog."""
        if self.image_data is None:
            self.statusBar().showMessage("No image loaded", 2000)
            return
        dialog = SmoothDialog(self)
        dialog.smoothing_changed.connect(self._apply_smooth_settings)
        dialog.exec()

    def _apply_smooth_settings(self, settings: dict) -> None:
        """Apply smoothing settings from dialog."""
        self._smooth_settings = settings
        self.menu_bar.action_smooth.blockSignals(True)
        self.menu_bar.action_smooth.setChecked(True)
        self.menu_bar.action_smooth.blockSignals(False)
        self._toggle_smooth(True)

    def _toggle_smooth(self, checked: bool) -> None:
        """Toggle display smoothing."""
        self.z1 = None
        self.z2 = None
        self._display_image()
        self._log_analysis_command(f"smooth {'on' if checked else 'off'}")
        self.statusBar().showMessage(f"Smooth {'enabled' if checked else 'disabled'}", 2000)

    def _get_display_image_data(self, frame: Frame) -> NDArray[np.floating]:
        """Return frame data after display-level analysis transforms."""
        image_data = self._get_rgb_active_channel_data(frame) if frame.frame_type == "rgb" else frame.image_data
        if image_data is None:
            return np.array([], dtype=np.float32)
        if self.menu_bar.action_smooth.isChecked():
            return self._apply_smoothing(image_data)
        return image_data

    def _get_analysis_image_data(self, frame: Frame) -> NDArray[np.floating]:
        """Return analysis-ready data with current smoothing and mask settings."""
        display_data = self._get_display_image_data(frame)
        return self._apply_analysis_mask(display_data)

    def _apply_analysis_mask(self, data: NDArray[np.floating]) -> NDArray[np.floating]:
        """Apply analysis mask settings to image data."""
        if self._analysis_mask_mode == "disabled":
            return data
        masked = np.array(data, copy=True, dtype=np.float32)
        finite_mask = np.isfinite(masked)
        keep_mask = finite_mask
        if self._analysis_mask_mode == "range":
            low = self._analysis_mask_min if self._analysis_mask_min is not None else -np.inf
            high = self._analysis_mask_max if self._analysis_mask_max is not None else np.inf
            keep_mask = finite_mask & (masked >= low) & (masked <= high)
        masked[~keep_mask] = np.nan
        return masked

    def _apply_smoothing(self, data: NDArray[np.floating]) -> NDArray[np.floating]:
        """Apply configured smoothing to an image array."""
        settings = self._smooth_settings
        kernel = str(settings.get("kernel_type", "Gaussian")).lower()
        preserve_nan = bool(settings.get("preserve_nan", True))
        nan_mask = np.isnan(data)

        working = data.astype(np.float32, copy=True)
        if preserve_nan and np.any(nan_mask):
            fill = float(np.nanmedian(working)) if np.isfinite(np.nanmedian(working)) else 0.0
            working[nan_mask] = fill

        if kernel == "gaussian":
            sigma = float(settings.get("sigma", 2.0))
            if settings.get("elliptical"):
                axis_ratio = max(float(settings.get("axis_ratio", 1.0)), 0.1)
                smoothed = gaussian_smooth(working, (sigma * axis_ratio, sigma))
            else:
                smoothed = gaussian_smooth(working, sigma)
        elif kernel == "boxcar":
            smoothed = boxcar_smooth(working, int(settings.get("kernel_size", 5)))
        elif kernel == "tophat":
            radius = max(1.0, float(settings.get("kernel_size", 5)) / 2.0)
            smoothed = tophat_smooth(working, radius)
        else:
            smoothed = ndimage.median_filter(working, size=int(settings.get("kernel_size", 5)))

        if preserve_nan and np.any(nan_mask):
            smoothed = smoothed.astype(np.float32, copy=True)
            smoothed[nan_mask] = np.nan
        return smoothed

    def _toggle_coordinate_grid(self, checked: bool) -> None:
        """Toggle coordinate grid overlay."""
        self._refresh_analysis_overlays()
        self.statusBar().showMessage(
            "Coordinate grid enabled" if checked else "Coordinate grid disabled",
            2000,
        )
        self._log_analysis_command(f"grid {'on' if checked else 'off'}")

    def _show_grid_dialog(self) -> None:
        """Show coordinate grid parameters dialog."""
        dialog = GridDialog(self)
        if self._grid_settings:
            dialog._coord_combo.setCurrentText(self._grid_settings.get("coord_system", "WCS"))
            dialog._format_combo.setCurrentText(self._grid_settings.get("label_format", "Sexagesimal"))
            dialog._auto_spacing_check.setChecked(self._grid_settings.get("auto_spacing", True))
            dialog._ra_spacing_spin.setValue(float(self._grid_settings.get("ra_spacing", 1.0)))
            dialog._dec_spacing_spin.setValue(float(self._grid_settings.get("dec_spacing", 1.0)))
        dialog.grid_changed.connect(self._apply_grid_settings)
        dialog.exec()

    def _apply_grid_settings(self, settings: dict) -> None:
        """Store coordinate grid settings."""
        self._grid_settings = settings
        self.menu_bar.action_coordinate_grid.blockSignals(True)
        self.menu_bar.action_coordinate_grid.setChecked(True)
        self.menu_bar.action_coordinate_grid.blockSignals(False)
        self._refresh_analysis_overlays()
        self._log_analysis_command("grid params")
        self.statusBar().showMessage("Updated coordinate grid parameters", 2000)

    def _show_mask_parameters(self) -> None:
        """Show mask parameter controls for analysis tools."""
        mode_labels = ["Disabled", "Finite Pixels Only", "Value Range"]
        mode_map = {
            "Disabled": "disabled",
            "Finite Pixels Only": "finite",
            "Value Range": "range",
        }
        current_label = next(
            (label for label, mode in mode_map.items() if mode == self._analysis_mask_mode),
            "Disabled",
        )
        choice, ok = QInputDialog.getItem(
            self,
            "Mask Parameters",
            "Mask mode:",
            mode_labels,
            mode_labels.index(current_label),
            False,
        )
        if not ok:
            return
        mode = mode_map[choice]
        self._analysis_mask_mode = mode
        if mode == "range":
            min_default = self._analysis_mask_min if self._analysis_mask_min is not None else 0.0
            max_default = self._analysis_mask_max if self._analysis_mask_max is not None else 1.0
            min_val, ok_min = QInputDialog.getDouble(
                self,
                "Mask Parameters",
                "Minimum value:",
                float(min_default),
                decimals=6,
            )
            if not ok_min:
                return
            max_val, ok_max = QInputDialog.getDouble(
                self,
                "Mask Parameters",
                "Maximum value:",
                float(max_default),
                decimals=6,
            )
            if not ok_max:
                return
            if max_val < min_val:
                min_val, max_val = max_val, min_val
            self._analysis_mask_min = float(min_val)
            self._analysis_mask_max = float(max_val)
            self.statusBar().showMessage(
                f"Mask range set to [{self._analysis_mask_min:.4g}, {self._analysis_mask_max:.4g}]",
                3000,
            )
        else:
            self._analysis_mask_min = None
            self._analysis_mask_max = None
            self.statusBar().showMessage(f"Mask mode: {choice}", 2500)
        self._log_analysis_command(f"mask {mode}")

    def _show_crosshair_parameters(self) -> None:
        """Show crosshair parameter controls."""
        enabled, ok = QInputDialog.getItem(
            self,
            "Crosshair Parameters",
            "Crosshair:",
            ["Off", "On"],
            1 if self._crosshair_enabled else 0,
            False,
        )
        if not ok:
            return
        self._crosshair_enabled = enabled == "On"
        if self._crosshair_enabled:
            color = QColorDialog.getColor(self._crosshair_color, self, "Crosshair Color")
            if color.isValid():
                self._crosshair_color = color
            size, ok_size = QInputDialog.getInt(
                self,
                "Crosshair Parameters",
                "Crosshair size (pixels):",
                self._crosshair_size,
                4,
                256,
            )
            if ok_size:
                self._crosshair_size = int(size)
        self._refresh_analysis_overlays()
        self._log_analysis_command(f"crosshair {'on' if self._crosshair_enabled else 'off'}")
        self.statusBar().showMessage(
            f"Crosshair {'enabled' if self._crosshair_enabled else 'disabled'}",
            2000,
        )

    def _show_graph_parameters(self) -> None:
        """Show graph panel visibility controls."""
        current = "None"
        if self.horizontal_graph_dock.isVisible() and self.vertical_graph_dock.isVisible():
            current = "Both"
        elif self.horizontal_graph_dock.isVisible():
            current = "Horizontal"
        elif self.vertical_graph_dock.isVisible():
            current = "Vertical"
        mode, ok = QInputDialog.getItem(
            self,
            "Graph Parameters",
            "Visible graph panels:",
            ["None", "Horizontal", "Vertical", "Both"],
            ["None", "Horizontal", "Vertical", "Both"].index(current),
            False,
        )
        if not ok:
            return
        self._set_graph_visibility(mode)
        self.statusBar().showMessage(f"Graph panels: {mode}", 2000)

    def _set_graph_visibility(self, mode: str) -> None:
        """Set visibility for horizontal/vertical graph docks."""
        show_horizontal = mode in ("Horizontal", "Both")
        show_vertical = mode in ("Vertical", "Both")
        self.horizontal_graph_dock.setVisible(show_horizontal)
        self.vertical_graph_dock.setVisible(show_vertical)
        self._log_analysis_command(f"graph {mode.lower()}")
        frame = self.frame_manager.current_frame
        if frame and frame.image_data is not None:
            analysis_data = self._get_analysis_image_data(frame)
            self.horizontal_graph_dock.set_image(analysis_data)
            self.vertical_graph_dock.set_image(analysis_data)

    def _refresh_analysis_overlays(self) -> None:
        """Apply grid/crosshair overlay states to the active viewer."""
        if hasattr(self.image_viewer, "set_grid"):
            self.image_viewer.set_grid(
                self.menu_bar.action_coordinate_grid.isChecked(),
                self._grid_settings,
            )
        if hasattr(self.image_viewer, "set_crosshair"):
            position = (
                (float(self._last_mouse_pos[0]), float(self._last_mouse_pos[1]))
                if self._last_mouse_pos is not None
                else None
            )
            self.image_viewer.set_crosshair(
                self._crosshair_enabled,
                position=position,
                color=self._crosshair_color,
                size=self._crosshair_size,
            )

    def _resolve_object_name(self) -> None:
        """Resolve an object name and pan to it if WCS is available."""
        name, ok = QInputDialog.getText(self, "Name Resolution", "Object name:")
        if not ok or not name.strip():
            return
        query = name.strip()
        try:
            coord = SkyCoord.from_name(query)
        except Exception as exc:
            self.statusBar().showMessage(f"Name resolution failed: {exc}", 3500)
            return

        if self.wcs_handler and self.wcs_handler.is_valid:
            try:
                x, y = self.wcs_handler.world_to_pixel(coord.ra.deg, coord.dec.deg)
                if self.using_gpu_rendering and hasattr(self.image_viewer, "set_pan"):
                    self.image_viewer.set_pan(float(x), float(y))
                    self._persist_frame_view_state()
                    self._update_panner_view_rect()
                else:
                    self._on_panner_pan(float(x), float(y))
                self.statusBar().showMessage(
                    f"{query}: RA {coord.ra.deg:.6f} deg, Dec {coord.dec.deg:.6f} deg",
                    4000,
                )
                self._log_analysis_command(f"name {query}")
                return
            except Exception:
                pass

        self.statusBar().showMessage(
            f"{query}: RA {coord.ra.deg:.6f} deg, Dec {coord.dec.deg:.6f} deg",
            4000,
        )
        self._log_analysis_command(f"name {query}")

    def _set_analysis_command_log(self, checked: bool) -> None:
        """Toggle analysis command logging preference."""
        self._analysis_command_log = checked
        self.statusBar().showMessage(
            f"Analysis command log {'enabled' if checked else 'disabled'}",
            2000,
        )

    def _log_analysis_command(self, command: str) -> None:
        """Append an analysis command to in-memory log when enabled."""
        if not self._analysis_command_log:
            return
        self._analysis_command_entries.append(command)
        if len(self._analysis_command_entries) > 200:
            self._analysis_command_entries = self._analysis_command_entries[-200:]

    def _load_analysis_commands(self) -> None:
        """Load simple external analysis commands into the Analysis menu."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Analysis Commands",
            "",
            "Analysis Command Files (*.ans *.analysis *.txt *.ds9);;All Files (*)",
        )
        if not filepath:
            return

        self._clear_analysis_commands(show_message=False)
        loaded = 0
        try:
            with open(filepath, "r", encoding="utf-8") as handle:
                lines = handle.readlines()
        except Exception as exc:
            self.statusBar().showMessage(f"Failed to load analysis commands: {exc}", 3500)
            return

        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                label, command = [part.strip() for part in line.split("|", 1)]
            else:
                label, command = line, line
            if not label or not command:
                continue
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked=False, cmd=command, title=label: self._execute_loaded_analysis_command(title, cmd)
            )
            self.menu_bar.analysis_menu.insertAction(self.menu_bar.action_load_analysis_commands, action)
            self._loaded_analysis_actions.append(action)
            loaded += 1

        self._log_analysis_command(f"load_analysis_commands {loaded}")
        self.statusBar().showMessage(f"Loaded {loaded} analysis commands", 3000)

    def _execute_loaded_analysis_command(self, title: str, command: str) -> None:
        """Execute a simple loaded analysis command."""
        cmd = command.strip()
        self._log_analysis_command(f"run {title}: {cmd}")
        if cmd.lower().startswith(("http://", "https://", "url:")):
            target = cmd.split(":", 1)[1].strip() if cmd.lower().startswith("url:") else cmd
            QDesktopServices.openUrl(QUrl(target))
            self.statusBar().showMessage(f"Opened {title}", 2000)
            return
        if cmd.lower().startswith("open:"):
            target = cmd.split(":", 1)[1].strip()
            if target:
                self.open_file(target)
                return
        if cmd.lower().startswith("message:"):
            self.statusBar().showMessage(cmd.split(":", 1)[1].strip(), 3000)
            return
        self.statusBar().showMessage(f"{title}: {cmd}", 3000)

    def _clear_analysis_commands(self, show_message: bool = True) -> None:
        """Clear previously loaded external analysis commands."""
        if not self._loaded_analysis_actions:
            if show_message:
                self.statusBar().showMessage("No external analysis commands are currently loaded", 2500)
            return
        for action in self._loaded_analysis_actions:
            self.menu_bar.analysis_menu.removeAction(action)
        cleared = len(self._loaded_analysis_actions)
        self._loaded_analysis_actions = []
        self._log_analysis_command(f"clear_analysis_commands {cleared}")
        if show_message:
            self.statusBar().showMessage(f"Cleared {cleared} analysis commands", 2500)

    def _open_analysis_web_browser(self) -> None:
        """Open a browser URL from the Analysis menu."""
        QDesktopServices.openUrl(QUrl("https://sites.google.com/cfa.harvard.edu/saoimageds9"))
        self._log_analysis_command("web")
        self.statusBar().showMessage("Opened web browser", 2000)

    def _update_bin_menu_checks(self, factor: int) -> None:
        """Update Bin menu checkmarks based on current factor."""
        self.menu_bar.action_bin_1.setChecked(factor == 1)
        self.menu_bar.action_bin_2.setChecked(factor == 2)
        self.menu_bar.action_bin_4.setChecked(factor == 4)
        self.menu_bar.action_bin_8.setChecked(factor == 8)
        self._update_block_menu_checks(factor)

    def _rebin_image(self, data: np.ndarray, factor: int) -> np.ndarray:
        """Rebin image by an integer factor using block mean."""
        if factor <= 1:
            return data

        height, width = data.shape[:2]
        new_height = (height // factor) * factor
        new_width = (width // factor) * factor
        if new_height == 0 or new_width == 0:
            return data

        trimmed = data[:new_height, :new_width]
        reshaped = trimmed.reshape(new_height // factor, factor, new_width // factor, factor)
        return np.nanmean(reshaped, axis=(1, 3)).astype(np.float32)

    def _set_bin(self, factor: int) -> None:
        """Set binning factor for the current frame."""
        frame = self.frame_manager.current_frame
        if not frame or not frame.has_data:
            self.statusBar().showMessage("No image loaded", 2000)
            return

        if frame.original_image_data is None:
            frame.original_image_data = frame.image_data

        if factor == 1:
            frame.image_data = frame.original_image_data
        else:
            frame.image_data = self._rebin_image(frame.original_image_data, factor)

        frame.bin_factor = factor
        self.current_bin = factor
        self.z1 = None
        self.z2 = None
        frame.z1 = None
        frame.z2 = None

        self._update_bin_menu_checks(factor)
        self._display_image()
        self.status_bar.update_image_info(frame.image_data.shape[1], frame.image_data.shape[0])
        self.statusBar().showMessage(f"Binning: {factor}x{factor}", 2000)
    
    def _zoom_in(self) -> None:
        """Zoom in."""
        self.image_viewer.zoom_in()
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self._persist_frame_view_state()
        self._update_panner_view_rect()
        self.statusBar().showMessage("Zoomed in", 1000)
    
    def _zoom_out(self) -> None:
        """Zoom out."""
        self.image_viewer.zoom_out()
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self._persist_frame_view_state()
        self._update_panner_view_rect()
        self.statusBar().showMessage("Zoomed out", 1000)
    
    def _zoom_fit(self) -> None:
        """Zoom to fit window."""
        self.image_viewer.zoom_fit(self.scroll_area.viewport().size())
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self._persist_frame_view_state()
        self._update_panner_view_rect()
        self.statusBar().showMessage("Zoom to fit", 1000)
    
    def _zoom_actual(self) -> None:
        """Zoom to 1:1."""
        self.image_viewer.zoom_actual()
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self._persist_frame_view_state()
        self._update_panner_view_rect()
        self.statusBar().showMessage("Zoom 1:1", 1000)
    
    def _on_mouse_moved(self, x: int, y: int) -> None:
        """Handle mouse movement over image."""
        if self.image_data is None:
            return

        image_height = self.image_data.shape[0]
        row = image_height - 1 - y
        self._last_mouse_pos = (x, y)
        
        # Update pixel coordinates
        self.status_bar.update_pixel_coords(x, y)
        
        # Update pixel value
        if 0 <= row < image_height and 0 <= x < self.image_data.shape[1]:
            value = self.image_data[row, x]
            self.status_bar.update_pixel_value(value)
        
        # Update WCS coordinates if available
        if self.wcs_handler and self.wcs_handler.is_valid:
            self._update_wcs_display(x, y)
        
        # Update magnifier panel (DS9 style)
        if hasattr(self, 'magnifier_panel'):
            self.magnifier_panel.update_cursor_position(x, row)
        if hasattr(self, "horizontal_graph_dock") and self.horizontal_graph_dock.isVisible():
            self.horizontal_graph_dock.update_cursor_position(x, row)
        if hasattr(self, "vertical_graph_dock") and self.vertical_graph_dock.isVisible():
            self.vertical_graph_dock.update_cursor_position(x, row)
        self._refresh_analysis_overlays()

    def _on_image_clicked(self, x: int, y: int, button: int) -> None:
        """Handle image clicks (used for tiled frame selection)."""
        if not self._tile_mode_enabled or button != int(Qt.MouseButton.LeftButton.value):
            return
        if self._select_tiled_frame(x, y):
            self._display_tiled_frames()
            self._update_frame_title()
            self.statusBar().showMessage(
                f"Selected frame {self.frame_manager.current_index + 1}",
                1500,
            )
    
    def _on_contrast_changed(self, contrast: float, brightness: float) -> None:
        """Handle contrast/brightness change from mouse drag."""
        self._display_image()
        self._persist_frame_view_state()
        self.statusBar().showMessage(f"Contrast: {contrast:.2f}, Brightness: {brightness:.2f}", 1000)
    
    def _on_panner_pan(self, x: float, y: float) -> None:
        """Handle pan request from panner panel."""
        if self.image_data is None:
            return
        image_height = self.image_data.shape[0]
        y_bottom = image_height - 1 - y
        
        # x, y are image coordinates where user clicked in panner
        # Center the main view on this position
        
        if self.using_gpu_rendering:
            # For GPU mode: set pan to the clicked position
            # The pan coordinates represent the image point at viewport center
            self.image_viewer.set_pan(x, y_bottom)
            self.statusBar().showMessage(f"Panned to ({x:.0f}, {y_bottom:.0f})", 1000)
        else:
            # For CPU mode: calculate scroll bar positions
            # Get current zoom
            zoom = self.image_viewer.get_zoom()
            
            # Calculate where this image point should be in widget coordinates
            # We want it centered in the viewport
            viewport = self.scroll_area.viewport()
            viewport_center_x = viewport.width() / 2
            viewport_center_y = viewport.height() / 2
            
            # Image point at (x, y) in zoomed coordinates
            zoomed_x = x * zoom
            zoomed_y = y * zoom
            
            # Scroll position to center this point
            scroll_x = int(zoomed_x - viewport_center_x)
            scroll_y = int(zoomed_y - viewport_center_y)
            
            self.scroll_area.horizontalScrollBar().setValue(scroll_x)
            self.scroll_area.verticalScrollBar().setValue(scroll_y)
            self.statusBar().showMessage(f"Panned to ({x:.0f}, {y_bottom:.0f})", 1000)
        
        # Persist the new pan state
        self._persist_frame_view_state()
        self._update_panner_view_rect()

    def _pan_by_pixels(self, dx: int, dy: int) -> None:
        """Pan display by integer image pixels."""
        if self.image_data is None:
            return
        if self.using_gpu_rendering and hasattr(self.image_viewer, "gl_canvas"):
            pan_x, pan_y = self.image_viewer.gl_canvas.pan_offset
            self.image_viewer.set_pan(pan_x + dx, pan_y + dy)
        else:
            zoom = max(self.image_viewer.get_zoom(), 1e-6)
            step = max(1, int(round(zoom)))
            self.scroll_area.horizontalScrollBar().setValue(
                self.scroll_area.horizontalScrollBar().value() + dx * step
            )
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - dy * step
            )
        self._persist_frame_view_state()
        self._update_panner_view_rect()

    def _update_panner_view_rect(self) -> None:
        """Update panner viewport rectangle to match main display viewport."""
        if not hasattr(self, "panner_panel"):
            return
        if self._tile_mode_enabled or self.image_data is None:
            self.panner_panel.set_view_rect(None)
            return

        image_h, image_w = self.image_data.shape[:2]
        if image_w <= 0 or image_h <= 0:
            self.panner_panel.set_view_rect(None)
            return

        zoom = max(self.image_viewer.get_zoom(), 1e-6)
        if self.using_gpu_rendering and hasattr(self.image_viewer, "gl_canvas"):
            canvas = self.image_viewer.gl_canvas
            view_w = canvas.width() / zoom
            view_h = canvas.height() / zoom
            pan_x, pan_y = canvas.pan_offset
            x = pan_x - view_w / 2.0
            y_bottom = pan_y - view_h / 2.0
            y = image_h - (y_bottom + view_h)
        else:
            viewport = self.scroll_area.viewport()
            view_w = viewport.width() / zoom
            view_h = viewport.height() / zoom
            x = self.scroll_area.horizontalScrollBar().value() / zoom
            y = self.scroll_area.verticalScrollBar().value() / zoom

        rect_w = min(float(image_w), max(1.0, float(view_w)))
        rect_h = min(float(image_h), max(1.0, float(view_h)))
        x = max(0.0, min(float(image_w) - rect_w, float(x)))
        y = max(0.0, min(float(image_h) - rect_h, float(y)))
        self.panner_panel.set_view_rect(QRectF(x, y, rect_w, rect_h))
    
    def _on_button_bar_zoom(self, level: str) -> None:
        """Handle zoom change from button bar."""
        if level == "Fit":
            self._zoom_fit()
        elif level == "1":
            self._zoom_actual()
        else:
            try:
                zoom_val = float(level)
                self.image_viewer.zoom_to(zoom_val)
                self.status_bar.update_zoom(zoom_val)
                self._persist_frame_view_state()
                self._update_panner_view_rect()
                self.statusBar().showMessage(f"Zoom: {zoom_val}x", 1000)
            except ValueError:
                # Handle fractions like "1/2"
                if "/" in level:
                    parts = level.split("/")
                    zoom_val = float(parts[0]) / float(parts[1])
                    self.image_viewer.zoom_to(zoom_val)
                    self.status_bar.update_zoom(zoom_val)
                    self._persist_frame_view_state()
                    self._update_panner_view_rect()
                    self.statusBar().showMessage(f"Zoom: {level}", 1000)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard panning with arrow keys."""
        key = event.key()
        if key == Qt.Key.Key_Left:
            self._pan_by_pixels(-1, 0)
            event.accept()
            return
        if key == Qt.Key.Key_Right:
            self._pan_by_pixels(1, 0)
            event.accept()
            return
        if key == Qt.Key.Key_Up:
            self._pan_by_pixels(0, 1)
            event.accept()
            return
        if key == Qt.Key.Key_Down:
            self._pan_by_pixels(0, -1)
            event.accept()
            return
        super().keyPressEvent(event)
    
    def _on_button_bar_scale(self, scale_name: str) -> None:
        """Handle scale change from button bar."""
        scale_map = {
            "Linear": ScaleAlgorithm.LINEAR,
            "Log": ScaleAlgorithm.LOG,
            "Sqrt": ScaleAlgorithm.SQRT,
            "Squared": ScaleAlgorithm.POWER,
            "Asinh": ScaleAlgorithm.ASINH,
            "HistEq": ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
        }
        if scale_name in scale_map:
            self._set_scale(scale_map[scale_name])
    
    def _on_button_bar_colormap(self, cmap_name: str) -> None:
        """Handle colormap change from button bar."""
        cmap_map = {
            "Gray": "grey",
            "Heat": "heat",
            "Cool": "cool",
            "Rainbow": "rainbow",
        }
        if cmap_name in cmap_map:
            self._set_colormap(cmap_map[cmap_name])
    
    def _on_button_bar_region(self, mode: str) -> None:
        """Handle region mode change from button bar."""
        mode_map = {
            "None": RegionMode.NONE,
            "Circle": RegionMode.CIRCLE,
            "Ellipse": RegionMode.ELLIPSE,
            "Box": RegionMode.BOX,
            "Polygon": RegionMode.POLYGON,
            "Line": RegionMode.LINE,
        }
        region_mode = mode_map.get(mode, RegionMode.NONE)
        self._set_region_mode(region_mode)
    
    def _toggle_fullscreen(self, checked: bool) -> None:
        """Toggle fullscreen mode."""
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()
    
    def _toggle_toolbar(self, checked: bool) -> None:
        """Toggle toolbar visibility."""
        self.main_toolbar.setVisible(checked)
    
    def _toggle_statusbar(self, checked: bool) -> None:
        """Toggle status bar visibility."""
        self.statusBar().setVisible(checked)
    
    def _reset_scale_limits(self) -> None:
        """Reset scale limits to ZScale auto-computed values."""
        if self.image_data is not None:
            self.z1 = None
            self.z2 = None
            frame = self.frame_manager.current_frame
            if frame:
                if frame.frame_type == "rgb":
                    channel = frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
                    frame.rgb_channel_z1[channel] = None
                    frame.rgb_channel_z2[channel] = None
                else:
                    frame.z1 = None
                    frame.z2 = None
            self.image_viewer.reset_contrast_brightness()
            self._display_image()
            self.statusBar().showMessage("Reset to ZScale limits", 2000)
    
    def _scale_minmax(self) -> None:
        """Set scale limits to data min/max."""
        if self.image_data is not None:
            self.z1 = float(np.nanmin(self.image_data))
            self.z2 = float(np.nanmax(self.image_data))
            frame = self.frame_manager.current_frame
            if frame:
                if frame.frame_type == "rgb":
                    channel = frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
                    frame.rgb_channel_z1[channel] = self.z1
                    frame.rgb_channel_z2[channel] = self.z2
                else:
                    frame.z1 = self.z1
                    frame.z2 = self.z2
            self.image_viewer.reset_contrast_brightness()
            self._display_image()
            self.statusBar().showMessage(f"MinMax: {self.z1:.4g} to {self.z2:.4g}", 2000)
    
    def _toggle_invert_colormap(self, checked: bool) -> None:
        """Toggle colormap inversion."""
        self.invert_colormap = checked
        self._persist_frame_view_state()
        if self.image_data is not None:
            self._display_image()
            inv_str = "inverted" if checked else "normal"
            self.statusBar().showMessage(f"Colormap {inv_str}", 2000)
    
    def _load_regions(self) -> None:
        """Load region file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Region File",
            "",
            "Region Files (*.reg);;All Files (*)",
        )
        if filepath:
            try:
                parser = RegionParser()
                base_regions = parser.parse_file(filepath)
                overlay_regions = []
                for base_region in base_regions:
                    overlay = self._base_region_to_overlay(base_region)
                    if overlay is not None:
                        overlay_regions.append(overlay)
                frame = self.frame_manager.current_frame
                if frame:
                    frame.regions = overlay_regions
                    self._update_regions_for_frame(frame)
                self.statusBar().showMessage(f"Loaded {len(overlay_regions)} regions from {filepath}", 3000)
            except Exception as e:
                self.statusBar().showMessage(f"Error loading regions: {e}", 3000)

    def _vo_siap_2mass(self) -> None:
        """Query 2MASS via SIAP and load image into new frame."""
        ra, dec = self._get_query_coordinates()
        dialog = VOQueryDialog(self, ra, dec, radius_deg=0.1, title="2MASS SIAP Query")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        ra, dec, radius = dialog.values()

        client = SIAClient(SIAClient.get_known_services()["2MASS"])
        table = client.query(ra, dec, size=radius, format="image/fits")
        if table is None or len(table) == 0:
            self.statusBar().showMessage("No SIAP images found", 3000)
            return

        access_url = self._pick_siap_access_url(table)
        if not access_url:
            self.statusBar().showMessage("No SIAP access URL found", 3000)
            return

        try:
            data = client.get_image(access_url)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".fits") as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            self._new_frame()
            self._load_fits_file(tmp_path)
            self.statusBar().showMessage("Loaded SIAP image into new frame", 3000)
        except Exception as e:
            self.statusBar().showMessage(f"SIAP load error: {e}", 3000)

    def _vo_catalog_vizier(self) -> None:
        """Query VizieR and overlay catalog sources."""
        ra, dec = self._get_query_coordinates()
        dialog = VOQueryDialog(self, ra, dec, radius_deg=0.05, title="VizieR Catalog Query")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        ra, dec, radius = dialog.values()

        catalog = VizierCatalog(catalog="II/246/out")
        coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
        table = catalog.query_region(coord, radius=radius * u.deg)
        if table is None or len(table) == 0:
            self.statusBar().showMessage("No VizieR sources found", 3000)
            return
        coords = catalog.get_coordinates(table)
        if not coords:
            self.statusBar().showMessage("Catalog has no usable coordinates", 3000)
            return
        if not self.wcs_handler or not self.wcs_handler.is_valid:
            self.statusBar().showMessage("Current frame has no WCS for overlay", 3000)
            return

        for coord in coords:
            pixel = self._world_to_overlay_pixel(coord.ra.deg, coord.dec.deg)
            if pixel is None:
                continue
            x, y = pixel
            region = Region(mode=RegionMode.POINT, points=[QPointF(x, y)])
            self._on_region_created(region)
            self.image_viewer.add_region(region)

        self.statusBar().showMessage(f"Overlayed {len(coords)} catalog sources", 3000)

    def _init_samp_client(self) -> None:
        """Initialize SAMP client and callbacks."""
        self._samp_client = SAMPClient()
        self._samp_client.register_callback("table.load.votable", self._on_samp_votable)
        self._samp_client.register_callback("table.load.fits", self._on_samp_fits)

    def _update_samp_menu_state(self) -> None:
        """Update SAMP menu action enabled states."""
        self.menu_bar.action_samp_connect.setEnabled(not self._samp_connected)
        self.menu_bar.action_samp_disconnect.setEnabled(self._samp_connected)

    def _samp_connect(self) -> None:
        """Connect to a SAMP hub."""
        if self._samp_client is None:
            self._init_samp_client()
        if self._samp_client is None:
            self.statusBar().showMessage("SAMP client unavailable", 3000)
            return
        if self._samp_client.connect():
            self._samp_connected = True
            self.statusBar().showMessage("Connected to SAMP hub", 3000)
        else:
            self._samp_connected = False
            self.statusBar().showMessage("Failed to connect to SAMP hub", 3000)
        self._update_samp_menu_state()

    def _samp_disconnect(self) -> None:
        """Disconnect from SAMP hub."""
        if self._samp_client is not None:
            self._samp_client.disconnect()
        self._samp_connected = False
        self._update_samp_menu_state()
        self.statusBar().showMessage("Disconnected from SAMP hub", 3000)

    def _on_samp_votable(self, sender_id: str, params: dict) -> None:
        """Queue incoming table.load.votable message on UI thread."""
        self._queue_samp_table(params, "votable")

    def _on_samp_fits(self, sender_id: str, params: dict) -> None:
        """Queue incoming table.load.fits message on UI thread."""
        self._queue_samp_table(params, "fits")

    def _queue_samp_table(self, params: dict, table_format: str) -> None:
        """Queue incoming SAMP table message for UI-thread handling."""
        url = str(params.get("url", "")).strip()
        if not url:
            return
        table_id = str(params.get("table-id") or params.get("name") or "samp-catalog")
        self.samp_table_received.emit(url, table_id, table_format)

    def _handle_samp_table_message(self, url: str, table_id: str, table_format: str) -> None:
        """Handle incoming SAMP catalog message."""
        frame = self.frame_manager.current_frame
        if not frame or frame.image_data is None:
            self.statusBar().showMessage("No image loaded for SAMP catalog overlay", 3000)
            return
        if not self.wcs_handler or not self.wcs_handler.is_valid:
            self.statusBar().showMessage("Current frame has no WCS for SAMP catalog overlay", 3000)
            return

        table = self._read_samp_table(url, table_format)
        if table is None or len(table) == 0:
            self.statusBar().showMessage(f"Failed to load SAMP catalog: {table_id}", 3000)
            return

        coords = self._extract_catalog_coordinates(table)
        if not coords:
            self.statusBar().showMessage("SAMP catalog has no usable RA/Dec columns", 3000)
            return

        sources: List[Tuple[float, float]] = []
        for coord in coords:
            pixel = self._world_to_overlay_pixel(coord.ra.deg, coord.dec.deg)
            if pixel is not None:
                sources.append(pixel)

        if not sources:
            self.statusBar().showMessage("No plottable sources in SAMP catalog", 3000)
            return

        self._samp_catalog_sources[frame.frame_id] = sources
        self._rebuild_samp_regions_for_frame(frame)
        self._update_regions_for_frame(frame)
        self.statusBar().showMessage(f"Loaded SAMP catalog {table_id}: {len(sources)} sources", 4000)

    def _read_samp_table(self, url: str, table_format: str) -> Optional[Table]:
        """Read SAMP table from URL/path."""
        target = url
        parsed = urlparse(url)
        if parsed.scheme == "file":
            target = unquote(parsed.path)

        try:
            return Table.read(target, format=table_format)
        except Exception:
            try:
                return Table.read(target)
            except Exception:
                return None

    def _extract_catalog_coordinates(self, table: Table) -> Optional[List[SkyCoord]]:
        """Extract ICRS coordinates from a table."""
        ra_col: Optional[str] = None
        dec_col: Optional[str] = None
        for col in table.colnames:
            col_lower = col.lower()
            if col_lower in ("ra", "_ra", "raj2000", "ra_icrs", "ra_j2000"):
                ra_col = col
            elif col_lower in ("dec", "_dec", "dej2000", "de", "dec_icrs", "dec_j2000"):
                dec_col = col
        if ra_col is None or dec_col is None:
            return None

        coords: List[SkyCoord] = []
        for row in table:
            try:
                coord = SkyCoord(
                    ra=float(row[ra_col]),
                    dec=float(row[dec_col]),
                    unit=(u.deg, u.deg),
                    frame="icrs",
                )
                coords.append(coord)
            except Exception:
                continue
        return coords if coords else None

    def _build_samp_marker_region(self, x: float, y: float) -> Region:
        """Create a region for a SAMP catalog source."""
        size = max(1.0, float(self._samp_marker_size))
        color = QColor(self._samp_marker_color)

        if self._samp_marker_shape == "circle":
            return Region(
                mode=RegionMode.CIRCLE,
                points=[QPointF(x, y), QPointF(x + size, y)],
                color=color,
                marker_size=size,
                source="samp_catalog",
            )
        if self._samp_marker_shape == "box":
            return Region(
                mode=RegionMode.BOX,
                points=[QPointF(x - size, y - size), QPointF(x + size, y + size)],
                color=color,
                marker_size=size,
                source="samp_catalog",
            )
        if self._samp_marker_shape == "ellipse":
            return Region(
                mode=RegionMode.ELLIPSE,
                points=[QPointF(x - size, y - size), QPointF(x + size, y + size)],
                color=color,
                marker_size=size,
                source="samp_catalog",
            )
        return Region(
            mode=RegionMode.POINT,
            points=[QPointF(x, y)],
            color=color,
            marker_size=size,
            source="samp_catalog",
        )

    def _rebuild_samp_regions_for_frame(self, frame: Frame) -> None:
        """Rebuild SAMP regions for a frame from stored source positions."""
        frame.regions = [
            region
            for region in frame.regions
            if getattr(region, "source", "user") != "samp_catalog"
        ]
        for x, y in self._samp_catalog_sources.get(frame.frame_id, []):
            frame.regions.append(self._build_samp_marker_region(x, y))

    def _refresh_samp_regions(self) -> None:
        """Refresh SAMP catalog marker rendering with current style."""
        for frame in self.frame_manager.frames:
            if frame.frame_id in self._samp_catalog_sources:
                self._rebuild_samp_regions_for_frame(frame)
        self._update_regions_for_frame(self.frame_manager.current_frame)

    def _samp_choose_marker_color(self) -> None:
        """Change SAMP catalog marker color."""
        color = QColorDialog.getColor(self._samp_marker_color, self, "SAMP Marker Color")
        if not color.isValid():
            return
        self._samp_marker_color = color
        self._refresh_samp_regions()
        self.statusBar().showMessage("Updated SAMP marker color", 2000)

    def _samp_choose_marker_shape(self) -> None:
        """Change SAMP catalog marker shape."""
        shape_map = {
            "Point": "point",
            "Circle": "circle",
            "Box": "box",
            "Ellipse": "ellipse",
        }
        labels = list(shape_map.keys())
        current_label = next((label for label, value in shape_map.items() if value == self._samp_marker_shape), "Point")
        current_index = labels.index(current_label)
        selected, ok = QInputDialog.getItem(
            self,
            "SAMP Marker Shape",
            "Shape:",
            labels,
            current_index,
            False,
        )
        if not ok:
            return
        self._samp_marker_shape = shape_map[selected]
        self._refresh_samp_regions()
        self.statusBar().showMessage(f"SAMP marker shape: {selected}", 2000)

    def _samp_choose_marker_size(self) -> None:
        """Change SAMP catalog marker size."""
        size, ok = QInputDialog.getDouble(
            self,
            "SAMP Marker Size",
            "Size (pixels):",
            float(self._samp_marker_size),
            1.0,
            100.0,
            1,
        )
        if not ok:
            return
        self._samp_marker_size = float(size)
        self._refresh_samp_regions()
        self.statusBar().showMessage(f"SAMP marker size: {self._samp_marker_size:.1f}", 2000)

    def _get_query_coordinates(self) -> tuple[float, float]:
        """Get query coordinates from cursor WCS or image center."""
        if self._last_mouse_pos is not None and self.wcs_handler and self.wcs_handler.is_valid:
            x, y = self._last_mouse_pos
            ra, dec = self.wcs_handler.pixel_to_world(x, y)
            return ra, dec
        if self.image_data is not None and self.wcs_handler and self.wcs_handler.is_valid:
            cx = self.image_data.shape[1] / 2
            cy = self.image_data.shape[0] / 2
            ra, dec = self.wcs_handler.pixel_to_world(cx, cy)
            return ra, dec
        return (0.0, 0.0)

    def _pick_siap_access_url(self, table: Table) -> str:
        """Pick access URL from SIAP table."""
        for col in ("access_url", "download", "url", "accessURL", "AccessURL"):
            if col in table.colnames:
                return str(table[col][0])
        return ""

    def _world_to_overlay_pixel(self, ra_deg: float, dec_deg: float) -> Optional[Tuple[float, float]]:
        """Convert WCS world coordinates to overlay pixel coordinates."""
        if (
            self.wcs_handler is None
            or not self.wcs_handler.is_valid
            or self.image_data is None
        ):
            return None
        try:
            x, y = self.wcs_handler.world_to_pixel(ra_deg, dec_deg)
            if not np.isfinite(x) or not np.isfinite(y):
                return None
            return float(x), float(y)
        except Exception:
            return None
    
    def _set_wcs_system(self, system: str) -> None:
        """Set WCS coordinate system."""
        self.current_wcs_system = system
        # Update menu checkmarks
        self.menu_bar.action_wcs_fk5.setChecked(system == "fk5")
        self.menu_bar.action_wcs_fk4.setChecked(system == "fk4")
        self.menu_bar.action_wcs_icrs.setChecked(system == "icrs")
        self.menu_bar.action_wcs_galactic.setChecked(system == "galactic")
        self.menu_bar.action_wcs_ecliptic.setChecked(system == "ecliptic")
        self.statusBar().showMessage(f"WCS system: {system.upper()}", 2000)
        if self._last_mouse_pos is not None and self.wcs_handler and self.wcs_handler.is_valid:
            self._update_wcs_display(*self._last_mouse_pos)
        self._update_direction_arrows()
    
    def _set_wcs_format(self, format_type: str) -> None:
        """Set WCS format (sexagesimal or degrees)."""
        self.current_wcs_format = format_type
        self.menu_bar.action_wcs_sexagesimal.setChecked(format_type == "sexagesimal")
        self.menu_bar.action_wcs_degrees.setChecked(format_type == "degrees")
        self.statusBar().showMessage(f"WCS format: {format_type}", 2000)
        if self._last_mouse_pos is not None and self.wcs_handler and self.wcs_handler.is_valid:
            self._update_wcs_display(*self._last_mouse_pos)

    def _toggle_direction_arrows(self, checked: bool) -> None:
        """Toggle WCS direction arrows overlay."""
        self._show_direction_arrows = checked
        self._update_direction_arrows()

    def _update_direction_arrows(self) -> None:
        """Update WCS direction arrows from current frame WCS."""
        if not hasattr(self.image_viewer, "set_direction_arrows"):
            return
        if (
            self._tile_mode_enabled
            or not self._show_direction_arrows
            or self.wcs_handler is None
            or not self.wcs_handler.is_valid
            or self.image_data is None
        ):
            self.image_viewer.set_direction_arrows(None, None, False)
            return

        h, w = self.image_data.shape[:2]
        cx = (w - 1) / 2.0
        cy = (h - 1) / 2.0

        ra, dec = self.wcs_handler.pixel_to_world(cx, cy)
        center = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=ICRS())
        separation = 1.0 * u.arcmin
        north = center.directional_offset_by(0.0 * u.deg, separation)
        east = center.directional_offset_by(90.0 * u.deg, separation)
        nx, ny = self.wcs_handler.world_to_pixel(north.ra.deg, north.dec.deg)
        ex, ey = self.wcs_handler.world_to_pixel(east.ra.deg, east.dec.deg)

        north_vector = (float(nx - cx), float(ny - cy))
        east_vector = (float(ex - cx), float(ey - cy))
        self.image_viewer.set_direction_arrows(north_vector, east_vector, True)

    def _update_wcs_display(self, x: int, y: int) -> None:
        """Update the status bar WCS display for the given pixel position."""
        if not self.wcs_handler or not self.wcs_handler.is_valid:
            return

        ra, dec = self.wcs_handler.pixel_to_world(x, y)
        base_coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=ICRS())

        system = self.current_wcs_system
        if system == "fk5":
            coord = base_coord.transform_to(FK5())
            lon = coord.ra.deg
            lat = coord.dec.deg
            labels = ("RA", "Dec")
        elif system == "fk4":
            coord = base_coord.transform_to(FK4())
            lon = coord.ra.deg
            lat = coord.dec.deg
            labels = ("RA", "Dec")
        elif system == "icrs":
            coord = base_coord.transform_to(ICRS())
            lon = coord.ra.deg
            lat = coord.dec.deg
            labels = ("RA", "Dec")
        elif system == "galactic":
            coord = base_coord.transform_to(Galactic())
            lon = coord.l.deg
            lat = coord.b.deg
            labels = ("l", "b")
        elif system == "ecliptic":
            coord = base_coord.transform_to(BarycentricTrueEcliptic())
            lon = coord.lon.deg
            lat = coord.lat.deg
            labels = ("Lon", "Lat")
        else:
            lon = ra
            lat = dec
            labels = ("RA", "Dec")

        self.status_bar.update_wcs_coords(
            lon,
            lat,
            format_type=self.current_wcs_format,
            labels=labels,
        )
    
    def _show_statistics(self) -> None:
        """Show statistics dialog."""
        frame = self.frame_manager.current_frame
        if frame is None or frame.image_data is None:
            self.statusBar().showMessage("No image loaded", 2000)
            return

        dialog = StatisticsDialog(self._get_analysis_image_data(frame), self)
        dialog.exec()
        self._log_analysis_command("statistics")
    
    def _show_histogram(self) -> None:
        """Show histogram dialog."""
        frame = self.frame_manager.current_frame
        if frame is None or frame.image_data is None:
            self.statusBar().showMessage("No image loaded", 2000)
            return

        dialog = HistogramDialog(self._get_analysis_image_data(frame), self)
        dialog.exec()
        self._log_analysis_command("histogram")

    def _show_radial_profile(self) -> None:
        """Show radial profile plot from the current frame."""
        frame = self.frame_manager.current_frame
        if frame is None or frame.image_data is None:
            self.statusBar().showMessage("No image loaded", 2000)
            return

        data = self._get_analysis_image_data(frame)
        if not np.any(np.isfinite(data)):
            self.statusBar().showMessage("No valid pixels for radial profile", 2500)
            return
        profile = RadialProfile(data)
        radii, values = profile.extract()

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("Radial Profile")
        dialog.setMinimumSize(640, 420)
        layout = QVBoxLayout(dialog)
        figure = Figure(figsize=(7, 4))
        canvas = FigureCanvasQTAgg(figure)
        ax = figure.add_subplot(111)
        ax.plot(radii, values, color="tab:blue", linewidth=1.5)
        ax.set_xlabel("Radius (pixels)")
        ax.set_ylabel("Mean value")
        ax.set_title("Radial Profile")
        ax.grid(True, alpha=0.3)
        figure.tight_layout()
        layout.addWidget(canvas)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        dialog.exec()
        self._log_analysis_command("radial_profile")
    
    def _show_scale_dialog(self) -> None:
        """Show scale parameters dialog (DS9 style)."""
        if self.image_data is None:
            self.statusBar().showMessage("No image loaded", 2000)
            return
        
        dialog = ScaleDialog(self)
        # Connect the signal BEFORE showing the dialog so Apply button works
        dialog.scale_changed.connect(self._apply_scale_params)
        dialog.exec()
    
    def _apply_scale_params(self, params: dict) -> None:
        """Apply scale parameters from the scale dialog."""
        # Map dialog scale names to ScaleAlgorithm enum
        scale_map = {
            "Linear": ScaleAlgorithm.LINEAR,
            "Log": ScaleAlgorithm.LOG,
            "Power": ScaleAlgorithm.POWER,
            "Sqrt": ScaleAlgorithm.SQRT,
            "Squared": ScaleAlgorithm.POWER,
            "Asinh": ScaleAlgorithm.ASINH,
            "Sinh": ScaleAlgorithm.ASINH,  # Map to asinh for now
            "Histogram Equalization": ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
        }
        
        scale_name = params.get("scale_function", "Linear")
        if scale_name in scale_map:
            self.current_scale = scale_map[scale_name]
        
        # Apply min/max limits if not auto
        if not params.get("auto_limits", True):
            self.z1 = params.get("min_value", self.z1)
            self.z2 = params.get("max_value", self.z2)
        
        # Apply contrast/bias adjustments
        # Contrast slider: 0-100 → 0-2.0 (50 = 1.0 neutral)
        contrast = params.get("contrast", 1.0)
        # Bias slider: 0-100 → -1.0 to +1.0 (50 = 0.0 neutral)
        bias_value = params.get("bias", 1.0)  # This is 0-2 range from slider/50
        brightness = bias_value - 1.0  # Convert to -1 to +1 range
        self._set_viewer_contrast_brightness(contrast, brightness)
        
        # Redisplay image with new settings
        self._display_image()
        self._persist_frame_view_state()
        self.statusBar().showMessage(f"Scale: {scale_name}, Contrast: {contrast:.2f}, Brightness: {brightness:.2f}", 2000)

    def _show_contours(self) -> None:
        """Show contour dialog and apply contours."""
        if self.image_data is None:
            self.statusBar().showMessage("No image loaded", 2000)
            return

        dialog = ContourDialog(self)
        if self._contour_settings is not None:
            dialog.load_settings(self._contour_settings)
        dialog.contours_changed.connect(self._apply_contours)
        dialog.contours_export_requested.connect(self._export_contours)
        dialog.exec()

    def _apply_contours(self, settings: dict) -> None:
        """Compute and display contours based on settings."""
        self._contour_settings = settings
        self.menu_bar.action_contours.blockSignals(True)
        self.menu_bar.action_contours.setChecked(True)
        self.menu_bar.action_contours.blockSignals(False)
        self._update_contours()
        self._log_analysis_command("contour params")

    def _toggle_contours(self, checked: bool) -> None:
        """Toggle contour overlay visibility."""
        if checked:
            if self._contour_settings is None:
                self._contour_settings = {
                    "method": "Linear",
                    "num_levels": 10,
                    "smooth": False,
                    "smooth_sigma": 1.0,
                    "line_width": 1.0,
                    "line_style": "Solid",
                    "color": "#00ff00",
                    "show_labels": False,
                }
            self._update_contours()
            self._log_analysis_command("contour on")
            self.statusBar().showMessage("Contours enabled", 2000)
        else:
            if hasattr(self.image_viewer, "clear_contours"):
                self.image_viewer.clear_contours()
            self._log_analysis_command("contour off")
            self.statusBar().showMessage("Contours disabled", 2000)

    def _update_contours(self) -> None:
        """Recompute contours for current image."""
        if not self.menu_bar.action_contours.isChecked():
            if hasattr(self.image_viewer, "clear_contours"):
                self.image_viewer.clear_contours()
            return
        frame = self.frame_manager.current_frame
        if frame is None or frame.image_data is None or self._contour_settings is None:
            if hasattr(self.image_viewer, "clear_contours"):
                self.image_viewer.clear_contours()
            return

        contour_data = self._get_analysis_image_data(frame)
        settings = self._contour_settings
        smooth_sigma = settings.get("smooth_sigma", 1.0) if settings.get("smooth") else None
        generator = ContourGenerator(contour_data, smooth=smooth_sigma)

        levels = self._compute_contour_levels(generator, settings)

        try:
            contours = generator.find_contours(levels)
            contour_paths = self._convert_skimage_contours(contours)
        except Exception:
            contours = generator.find_contours_scipy(levels)
            contour_paths = self._convert_scipy_contours(contours)

        self._contour_paths = contour_paths
        self._contour_levels = levels

        style = self._contour_style_from_settings(settings)
        if hasattr(self.image_viewer, "set_contours"):
            self.image_viewer.set_contours(contour_paths, levels, style)

    def _compute_contour_levels(self, generator: ContourGenerator, settings: dict) -> list:
        """Compute contour levels based on settings."""
        if settings.get("use_sigma"):
            sigmas = settings.get("sigma_levels") or [3.0, 5.0, 10.0]
            base = settings.get("sigma_base", "Median")
            if base == "Mean":
                base_level = float(np.nanmean(generator.data))
            else:
                base_level = float(np.nanmedian(generator.data))
            return generator.generate_sigma_levels(sigmas, base_level=base_level)

        method = settings.get("method", "Linear")
        num_levels = settings.get("num_levels", 10)
        vmin = settings.get("min_level")
        vmax = settings.get("max_level")

        if vmin is not None and vmax is not None and vmin >= vmax:
            vmin = None
            vmax = None

        if method == "Custom":
            custom = settings.get("custom_levels") or []
            return list(custom)

        if method == "Logarithmic":
            return generator.generate_levels(num_levels, vmin=vmin, vmax=vmax, log_scale=True)

        if method == "Square Root":
            valid = generator.data[~np.isnan(generator.data)]
            if vmin is None:
                vmin = float(np.min(valid))
            if vmax is None:
                vmax = float(np.max(valid))
            vmin = max(0.0, vmin)
            vmax = max(vmin + 1e-12, vmax)
            levels = np.linspace(np.sqrt(vmin), np.sqrt(vmax), num_levels) ** 2
            return list(levels)

        return generator.generate_levels(num_levels, vmin=vmin, vmax=vmax, log_scale=False)

    def _convert_skimage_contours(self, contours: list) -> list:
        """Convert skimage contours to x/y arrays."""
        contour_paths: list = []
        for level_paths in contours:
            converted = []
            for path in level_paths:
                if path.ndim == 2 and path.shape[1] == 2:
                    coords = np.column_stack([path[:, 1], path[:, 0]]).astype(np.float64)
                    converted.append(coords)
            contour_paths.append(converted)
        return contour_paths

    def _convert_scipy_contours(self, contours: list) -> list:
        """Convert scipy contours to x/y arrays."""
        contour_paths: list = []
        for level_paths in contours:
            converted = []
            for x_coords, y_coords in level_paths:
                coords = np.column_stack([x_coords, y_coords]).astype(np.float64)
                converted.append(coords)
            contour_paths.append(converted)
        return contour_paths

    def _contour_style_from_settings(self, settings: dict):
        """Build contour style tuple for overlay."""
        color = QColor(settings.get("color", "#00ff00"))
        line_width = float(settings.get("line_width", 1.0))
        line_style = settings.get("line_style", "Solid")
        style_map = {
            "Solid": Qt.PenStyle.SolidLine,
            "Dashed": Qt.PenStyle.DashLine,
            "Dotted": Qt.PenStyle.DotLine,
            "Dash-Dot": Qt.PenStyle.DashDotLine,
        }
        pen_style = style_map.get(line_style, Qt.PenStyle.SolidLine)
        show_labels = bool(settings.get("show_labels", False))
        return (color, line_width, pen_style, show_labels)

    def _export_contours(self, settings: dict) -> None:
        """Export current contours to a file."""
        if self._contour_paths is None or self._contour_levels is None:
            self._apply_contours(settings)
            if self._contour_paths is None or self._contour_levels is None:
                self.statusBar().showMessage("No contours to export", 2000)
                return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Contours",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not filepath:
            return

        export_data = {
            "levels": self._contour_levels,
            "contours": [
                [path.tolist() for path in level_paths]
                for level_paths in self._contour_paths
            ],
            "settings": settings,
        }

        import json

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)
        self.statusBar().showMessage(f"Exported contours to {filepath}", 3000)
    
    def _show_pixel_table(self) -> None:
        """Show pixel table dialog."""
        frame = self.frame_manager.current_frame
        if frame is None or frame.image_data is None:
            self.statusBar().showMessage("No image loaded", 2000)
            return
        
        # Use image center as default
        analysis_data = self._get_analysis_image_data(frame)
        height, width = analysis_data.shape
        x, y = width // 2, height // 2
        
        dialog = PixelTableDialog(analysis_data, x, y, size=11, parent=self)
        dialog.exec()
        self._log_analysis_command("pixel_table")
    
    def _show_fits_header(self) -> None:
        """Show FITS header dialog."""
        if self.fits_handler is None:
            self.statusBar().showMessage("No FITS file loaded", 2000)
            return
        
        from .dialogs.header_dialog import HeaderDialog
        header = self.fits_handler.get_header()
        dialog = HeaderDialog(header, self)
        dialog.exec()
    
    def _show_help_contents(self) -> None:
        """Show help contents dialog."""
        dialog = HelpContentsDialog(self)
        dialog.exec()
    
    def _show_keyboard_shortcuts(self) -> None:
        """Show keyboard shortcuts dialog."""
        dialog = KeyboardShortcutsDialog(self)
        dialog.exec()
    
    def _export_image(self) -> None:
        """Export current image view."""
        pixmap = self._get_current_pixmap()
        if pixmap is None:
            self.statusBar().showMessage("No image to export", 2000)
            return

        dialog = ExportDialog(pixmap, self)
        if dialog.exec():
            self.statusBar().showMessage(f"Exported to {dialog.export_path}", 3000)
    
    def _print_image(self) -> None:
        """Print current image view."""
        pixmap = self._get_current_pixmap()
        if pixmap is None:
            self.statusBar().showMessage("No image to print", 2000)
            return
        
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt6.QtGui import QPainter
        
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            painter = QPainter(printer)
            rect = painter.viewport()
            size = pixmap.size()
            size.scale(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
            painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
            painter.setWindow(pixmap.rect())
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            self.statusBar().showMessage("Print completed", 2000)

    def _get_current_pixmap(self) -> Optional[QPixmap]:
        """Get a pixmap of the current image for export/print."""
        if self.image_data is None:
            return None

        image_data = self.image_data

        if self.z1 is None or self.z2 is None:
            self.z1, self.z2 = compute_zscale_limits(image_data)

        contrast, brightness = self.image_viewer.get_contrast_brightness()
        range_val = self.z2 - self.z1
        center = (self.z1 + self.z2) / 2
        new_range = range_val / contrast
        adjusted_z1 = center - new_range / 2 + brightness * range_val
        adjusted_z2 = center + new_range / 2 + brightness * range_val

        clipped = np.clip(image_data, adjusted_z1, adjusted_z2)
        scaled = apply_scale(clipped, self.current_scale, vmin=adjusted_z1, vmax=adjusted_z2)

        try:
            cmap = self._get_colormap_instance(self.current_colormap)
        except ValueError:
            cmap = self._get_colormap_instance("grey")
        if self.invert_colormap:
            cmap_data = cmap.colors.copy()
            cmap_data = cmap_data[::-1]
            cmap = Colormap(f"{self.current_colormap}_inverted", cmap_data)

        rgb = cmap.apply(scaled)
        height, width = rgb.shape[:2]
        bytes_per_line = 3 * width
        qimage = QImage(rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimage)
    
    def save_file(self) -> None:
        """Save the current file."""
        self.statusBar().showMessage("Save not yet implemented", 3000)
    
    def save_file_as(self) -> None:
        """Save the current file with a new name."""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save FITS File",
            "",
            "FITS Files (*.fits *.fit *.fts);;All Files (*)",
        )
        if filepath:
            self.statusBar().showMessage(f"Save as: {filepath}", 3000)
    
    def _reset_frame_view_defaults(self, frame: Frame) -> None:
        """Reset a frame's display state to defaults."""
        frame.bin_factor = 1
        frame.colormap = self._default_colormap
        frame.scale = ScaleAlgorithm.LINEAR
        frame.invert_colormap = False
        frame.z1 = None
        frame.z2 = None
        frame.zoom = 1.0
        frame.pan_x = 0.0
        frame.pan_y = 0.0
        frame.contrast = 1.0
        frame.brightness = 0.0
        frame.rgb_channel_scale = {
            "red": ScaleAlgorithm.LINEAR,
            "green": ScaleAlgorithm.LINEAR,
            "blue": ScaleAlgorithm.LINEAR,
        }
        frame.rgb_channel_z1 = {"red": None, "green": None, "blue": None}
        frame.rgb_channel_z2 = {"red": None, "green": None, "blue": None}
        frame.rgb_channel_contrast = {"red": 1.0, "green": 1.0, "blue": 1.0}
        frame.rgb_channel_brightness = {"red": 0.0, "green": 0.0, "blue": 0.0}

    def _ensure_active_frames_valid(self) -> None:
        """Ensure active frame IDs map to existing frames."""
        valid_ids = {frame.frame_id for frame in self.frame_manager.frames}
        self._active_frame_ids.update(valid_ids - self._known_frame_ids)
        self._active_frame_ids.intersection_update(valid_ids)
        self._known_frame_ids = set(valid_ids)
        if not self._active_frame_ids and self.frame_manager.frames:
            frame = self.frame_manager.current_frame or self.frame_manager.frames[0]
            self._active_frame_ids.add(frame.frame_id)

    def _get_active_frame_indices(self) -> list[int]:
        """Return frame indices currently marked active."""
        self._ensure_active_frames_valid()
        return [
            idx
            for idx, frame in enumerate(self.frame_manager.frames)
            if frame.frame_id in self._active_frame_ids
        ]

    def _refresh_frame_menu_items(self) -> None:
        """Refresh dynamic frame menu items."""
        self._ensure_active_frames_valid()
        current_index = self.frame_manager.current_index

        self.menu_bar.goto_frame_menu.clear()
        for idx, _frame in enumerate(self.frame_manager.frames):
            action = QAction(f"Frame {idx + 1}", self)
            action.setCheckable(True)
            action.setChecked(idx == current_index)
            action.triggered.connect(lambda checked=False, i=idx: self._goto_frame_index(i))
            self.menu_bar.goto_frame_menu.addAction(action)

        self.menu_bar.show_hide_frames_menu.clear()
        self.menu_bar.show_hide_frames_menu.addAction(self.menu_bar.action_show_all_frames)
        self.menu_bar.show_hide_frames_menu.addAction(self.menu_bar.action_hide_all_frames)
        self.menu_bar.show_hide_frames_menu.addSeparator()
        for idx, frame in enumerate(self.frame_manager.frames):
            action = QAction(f"Frame {idx + 1}", self)
            action.setCheckable(True)
            action.setChecked(frame.frame_id in self._active_frame_ids)
            action.triggered.connect(
                lambda checked, fid=frame.frame_id: self._set_frame_active(fid, checked)
            )
            self.menu_bar.show_hide_frames_menu.addAction(action)

    def _goto_frame_index(self, index: int) -> None:
        """Switch to a specific frame index."""
        if self.frame_manager.goto_frame(index):
            self.z1 = None
            self.z2 = None
            if hasattr(self.image_viewer, "reset_contrast_brightness"):
                self.image_viewer.reset_contrast_brightness()
            self._update_frame_display()

    def _new_frame_with_type(self, frame_type: str) -> None:
        """Create a new frame of the requested DS9-style type."""
        frame = self.frame_manager.new_frame(frame_type=frame_type)
        self._known_frame_ids.add(frame.frame_id)
        self._active_frame_ids.add(frame.frame_id)
        self.z1 = None
        self.z2 = None
        if hasattr(self.image_viewer, "reset_contrast_brightness"):
            self.image_viewer.reset_contrast_brightness()
        self._update_frame_display()
        self.statusBar().showMessage(f"Created Frame {self.frame_manager.current_index + 1} ({frame_type})", 2000)

    def _new_frame(self) -> None:
        """Create a new empty frame."""
        self._new_frame_with_type("base")

    def _delete_all_frames(self) -> None:
        """Delete all frames and create one new empty frame."""
        for existing in self.frame_manager.frames:
            if existing.fits_handler is not None:
                try:
                    existing.fits_handler.close()
                except Exception:
                    pass
        frame = self.frame_manager.reset_to_single_frame()
        self._samp_catalog_sources.clear()
        self._known_frame_ids = {frame.frame_id}
        self._active_frame_ids = {frame.frame_id}
        self._set_frame_display_mode("single")
        self.statusBar().showMessage("Deleted all frames", 2000)

    def _delete_frame(self) -> None:
        """Delete current frame."""
        current_frame = self.frame_manager.current_frame
        current_frame_id = current_frame.frame_id if current_frame else None
        if self.frame_manager.delete_frame():
            if current_frame and current_frame.fits_handler is not None:
                try:
                    current_frame.fits_handler.close()
                except Exception:
                    pass
            if current_frame_id is not None:
                self._active_frame_ids.discard(current_frame_id)
                self._samp_catalog_sources.pop(current_frame_id, None)
            self._ensure_active_frames_valid()
            if len(self._get_active_frame_indices()) <= 1 and self._frame_display_mode in {"blink", "fade"}:
                self._set_frame_display_mode("single")
            else:
                self.z1 = None
                self.z2 = None
                if hasattr(self.image_viewer, "reset_contrast_brightness"):
                    self.image_viewer.reset_contrast_brightness()
                self._update_frame_display()
            frame_info = f"Frame {self.frame_manager.current_index + 1}/{self.frame_manager.num_frames}"
            self.statusBar().showMessage(f"Deleted frame, now at {frame_info}", 2000)
        else:
            self.statusBar().showMessage("Cannot delete last frame", 2000)

    def _clear_frame(self) -> None:
        """Clear data from current frame."""
        frame = self.frame_manager.current_frame
        if frame is None:
            return
        frame.filepath = None
        if frame.fits_handler is not None:
            try:
                frame.fits_handler.close()
            except Exception:
                pass
        frame.fits_handler = None
        frame.image_data = None
        frame.original_image_data = None
        frame.rgb_channels = {"red": None, "green": None, "blue": None}
        frame.rgb_source_frame_ids = {"red": None, "green": None, "blue": None}
        frame.rgb_view = {"red": True, "green": True, "blue": True}
        frame.rgb_current_channel = "red"
        frame.header = None
        frame.wcs_handler = None
        frame.regions.clear()
        self._samp_catalog_sources.pop(frame.frame_id, None)
        self._reset_frame_view_defaults(frame)
        self.z1 = None
        self.z2 = None
        if hasattr(self.image_viewer, "reset_contrast_brightness"):
            self.image_viewer.reset_contrast_brightness()
        self._update_frame_display()
        self.statusBar().showMessage("Cleared current frame", 2000)

    def _reset_frame(self) -> None:
        """Reset display parameters for current frame."""
        frame = self.frame_manager.current_frame
        if frame is None:
            return
        self._reset_frame_view_defaults(frame)
        self.z1 = None
        self.z2 = None
        if hasattr(self.image_viewer, "reset_contrast_brightness"):
            self.image_viewer.reset_contrast_brightness()
        self._update_frame_display()
        self.statusBar().showMessage("Reset current frame", 2000)

    def _refresh_frame(self) -> None:
        """Refresh current frame display."""
        self._update_frame_display()
        self.statusBar().showMessage("Refreshed current frame", 2000)

    def _move_frame_first(self) -> None:
        """Move current frame to first position."""
        current = self.frame_manager.current_index
        if self.frame_manager.move_frame(current, 0):
            self._update_frame_display()

    def _move_frame_back(self) -> None:
        """Move current frame one position backward."""
        count = self.frame_manager.num_frames
        current = self.frame_manager.current_index
        target = count - 1 if current <= 0 else current - 1
        if self.frame_manager.move_frame(current, target):
            self._update_frame_display()

    def _move_frame_forward(self) -> None:
        """Move current frame one position forward."""
        count = self.frame_manager.num_frames
        current = self.frame_manager.current_index
        target = 0 if current >= count - 1 else current + 1
        if self.frame_manager.move_frame(current, target):
            self._update_frame_display()

    def _move_frame_last(self) -> None:
        """Move current frame to last position."""
        current = self.frame_manager.current_index
        if self.frame_manager.move_frame(current, self.frame_manager.num_frames - 1):
            self._update_frame_display()

    def _set_frame_active(self, frame_id: int, active: bool) -> None:
        """Set active visibility state for a frame."""
        if active:
            self._active_frame_ids.add(frame_id)
        else:
            if frame_id not in self._active_frame_ids:
                return
            if len(self._active_frame_ids) <= 1:
                self.statusBar().showMessage("At least one frame must remain visible", 2000)
                self._refresh_frame_menu_items()
                return
            self._active_frame_ids.remove(frame_id)
        self._ensure_active_frames_valid()
        current_frame = self.frame_manager.current_frame
        if current_frame and current_frame.frame_id not in self._active_frame_ids:
            active_indices = self._get_active_frame_indices()
            if active_indices:
                self.frame_manager.goto_frame(active_indices[0])
        if len(self._get_active_frame_indices()) <= 1 and self._frame_display_mode in {"blink", "fade"}:
            self._set_frame_display_mode("single")
        else:
            self._update_frame_display()

    def _show_all_frames(self) -> None:
        """Mark all frames active."""
        self._active_frame_ids = {frame.frame_id for frame in self.frame_manager.frames}
        self._update_frame_display()

    def _hide_all_frames(self) -> None:
        """Hide all but the current frame."""
        current = self.frame_manager.current_frame
        if current is None:
            return
        self._active_frame_ids = {current.frame_id}
        if self._frame_display_mode in {"blink", "fade"}:
            self._set_frame_display_mode("single")
        else:
            self._update_frame_display()

    def _first_frame(self) -> None:
        """Go to first active frame."""
        active_indices = self._get_active_frame_indices()
        if active_indices:
            self._goto_frame_index(active_indices[0])

    def _prev_frame(self) -> None:
        """Go to previous active frame."""
        active_indices = self._get_active_frame_indices()
        if not active_indices:
            return
        current = self.frame_manager.current_index
        if current not in active_indices:
            self._goto_frame_index(active_indices[0])
            return
        pos = active_indices.index(current)
        self._goto_frame_index(active_indices[(pos - 1) % len(active_indices)])

    def _next_frame(self) -> None:
        """Go to next active frame."""
        active_indices = self._get_active_frame_indices()
        if not active_indices:
            return
        current = self.frame_manager.current_index
        if current not in active_indices:
            self._goto_frame_index(active_indices[0])
            return
        pos = active_indices.index(current)
        self._goto_frame_index(active_indices[(pos + 1) % len(active_indices)])

    def _last_frame(self) -> None:
        """Go to last active frame."""
        active_indices = self._get_active_frame_indices()
        if active_indices:
            self._goto_frame_index(active_indices[-1])
    
    def _update_frame_title(self) -> None:
        """Update window title with current frame info."""
        frame = self.frame_manager.current_frame
        frame_info = f"Frame {self.frame_manager.current_index + 1}/{self.frame_manager.num_frames}"
        if frame and frame.filepath:
            self.setWindowTitle(f"NCRADS9 - {frame.filepath.name} [{frame_info}]")
        else:
            self.setWindowTitle(f"NCRADS9 [{frame_info}]")
        self.statusBar().showMessage(frame_info, 2000)

    def _update_frame_display(self) -> None:
        """Update UI to reflect the current frame."""
        self._ensure_active_frames_valid()
        self._tile_mode_enabled = self._frame_display_mode == "tile"
        if self._tile_mode_enabled:
            if not self._display_tiled_frames():
                self._set_frame_display_mode("single")
                return
            self._refresh_frame_menu_items()
            self._update_frame_title()
            return

        frame = self.frame_manager.current_frame
        self._update_regions_for_frame(frame)
        if frame and frame.has_data:
            self._apply_frame_view_state(frame)
            self._display_image()
            self.status_bar.update_image_info(frame.image_data.shape[1], frame.image_data.shape[0])
            if self.using_gpu_rendering and hasattr(self.image_viewer, "gl_canvas"):
                self.image_viewer.gl_canvas.reset_view()
                if frame.zoom:
                    self.image_viewer.zoom_to(frame.zoom)
        else:
            self.status_bar.update_image_info(None, None)
            if hasattr(self.image_viewer, "set_direction_arrows"):
                self.image_viewer.set_direction_arrows(None, None, False)
            if hasattr(self, "panner_panel"):
                self.panner_panel.set_view_rect(None)
        self._refresh_frame_menu_items()
        self._update_frame_title()

    def _update_regions_for_frame(self, frame: Optional[Frame]) -> None:
        """Sync region overlay with current frame."""
        if not hasattr(self.image_viewer, "clear_regions"):
            return
        self.image_viewer.clear_regions()
        if frame:
            for region in frame.regions:
                self.image_viewer.add_region(region)

    def _update_blink(self) -> None:
        """Advance blink animation and refresh display."""
        if self._frame_display_mode not in {"blink", "fade"}:
            return
        active_indices = self._get_active_frame_indices()
        if len(active_indices) <= 1:
            self._set_frame_display_mode("single")
            return
        current = self.frame_manager.current_index
        if current not in active_indices:
            next_index = active_indices[0]
        else:
            position = active_indices.index(current)
            next_index = active_indices[(position + 1) % len(active_indices)]
        self.frame_manager.goto_frame(next_index)
        self._update_frame_display()

    def _show_single_frame(self, checked: bool = False) -> None:
        """Set display mode to single-frame."""
        _ = checked
        self._set_frame_display_mode("single")

    def _set_frame_display_mode(self, mode: str) -> None:
        """Set frame display mode and synchronize UI/timers."""
        if mode not in {"single", "tile", "blink", "fade"}:
            return
        if mode in {"blink", "fade"} and len(self._get_active_frame_indices()) <= 1:
            mode = "single"
            self.statusBar().showMessage("Need at least two visible frames", 2000)

        self._frame_display_mode = mode
        self._tile_mode_enabled = mode == "tile"

        self.menu_bar.action_single_frame.blockSignals(True)
        self.menu_bar.action_tile_frames.blockSignals(True)
        self.menu_bar.action_blink_frames.blockSignals(True)
        self.menu_bar.action_fade_frames.blockSignals(True)
        self.menu_bar.action_single_frame.setChecked(mode == "single")
        self.menu_bar.action_tile_frames.setChecked(mode == "tile")
        self.menu_bar.action_blink_frames.setChecked(mode == "blink")
        self.menu_bar.action_fade_frames.setChecked(mode == "fade")
        self.menu_bar.action_single_frame.blockSignals(False)
        self.menu_bar.action_tile_frames.blockSignals(False)
        self.menu_bar.action_blink_frames.blockSignals(False)
        self.menu_bar.action_fade_frames.blockSignals(False)

        if mode == "blink":
            self._blink_timer.start(self._blink_timer.interval())
            self.statusBar().showMessage("Blinking started", 2000)
        elif mode == "fade":
            self._blink_timer.start(self._fade_interval_ms)
            self.statusBar().showMessage("Fade mode enabled", 2000)
        else:
            self._blink_timer.stop()
            if mode == "tile":
                self.statusBar().showMessage("Frame tiling enabled", 2000)
            else:
                self.statusBar().showMessage("Single frame mode", 2000)

        if mode != "tile":
            self._tile_layout = None
        self._update_frame_display()

    def _toggle_blink(self, checked: bool) -> None:
        """Start/stop frame blinking."""
        if checked:
            self._set_frame_display_mode("blink")
        elif self._frame_display_mode == "blink":
            self._set_frame_display_mode("single")

    def _toggle_fade(self, checked: bool) -> None:
        """Start/stop frame fading."""
        if checked:
            self._set_frame_display_mode("fade")
        elif self._frame_display_mode == "fade":
            self._set_frame_display_mode("single")

    def _tile_frames(self, checked: bool) -> None:
        """Toggle tiled display of loaded frames."""
        if checked:
            self._set_frame_display_mode("tile")
        elif self._frame_display_mode == "tile":
            self._set_frame_display_mode("single")

    def _set_tile_arrangement_mode(self, mode: str) -> None:
        """Set tile arrangement mode."""
        self._tile_arrangement_mode = mode
        if self._frame_display_mode == "tile":
            self._update_frame_display()

    def _set_blink_interval(self, interval_ms: int) -> None:
        """Set blink interval."""
        self._blink_timer.setInterval(int(interval_ms))
        if self._frame_display_mode == "blink":
            self._blink_timer.start(self._blink_timer.interval())
        self.statusBar().showMessage(f"Blink interval set to {interval_ms} ms", 1500)

    def _set_fade_interval(self, interval_ms: int) -> None:
        """Set fade interval."""
        self._fade_interval_ms = int(interval_ms)
        if self._frame_display_mode == "fade":
            self._blink_timer.start(self._fade_interval_ms)
        self.statusBar().showMessage(f"Fade interval set to {interval_ms} ms", 1500)

    def _show_frame_dialog(self, frame_mode: str) -> None:
        """Open frame mode dialog."""
        if frame_mode == "rgb":
            self._show_rgb_dialog()
            return
        self.statusBar().showMessage(f"{frame_mode.upper()} parameters dialog not yet implemented", 2000)

    def _show_rgb_dialog(self) -> None:
        """Show DS9-style RGB channel dialog."""
        self._persist_frame_view_state()
        frame = self.frame_manager.current_frame
        if frame is None or frame.frame_type != "rgb":
            self._new_frame_with_type("rgb")
            frame = self.frame_manager.current_frame
        if frame is None:
            return

        dialog = QDialog(None)
        dialog.setWindowFlag(Qt.WindowType.Window, True)
        dialog.setWindowTitle("RGB")
        layout = QVBoxLayout(dialog)

        channel_group = QGroupBox("Current Channel", dialog)
        channel_layout = QHBoxLayout(channel_group)
        button_group = QButtonGroup(channel_group)
        radio_buttons: Dict[str, QRadioButton] = {}
        for channel in self._rgb_channel_names():
            radio = QRadioButton(channel.capitalize(), channel_group)
            radio.setChecked(frame.rgb_current_channel == channel)
            button_group.addButton(radio)
            channel_layout.addWidget(radio)
            radio_buttons[channel] = radio
        layout.addWidget(channel_group)

        view_group = QGroupBox("View", dialog)
        view_layout = QHBoxLayout(view_group)
        view_checks: Dict[str, QCheckBox] = {}
        for channel in self._rgb_channel_names():
            checkbox = QCheckBox(channel.capitalize(), view_group)
            checkbox.setChecked(frame.rgb_view.get(channel, True))
            view_layout.addWidget(checkbox)
            view_checks[channel] = checkbox
        layout.addWidget(view_group)

        settings_group = QGroupBox("Per-Channel Display Settings", dialog)
        settings_layout = QGridLayout(settings_group)
        settings_layout.addWidget(QLabel("Channel"), 0, 0)
        settings_layout.addWidget(QLabel("Scale"), 0, 1)
        settings_layout.addWidget(QLabel("Auto"), 0, 2)
        settings_layout.addWidget(QLabel("Min"), 0, 3)
        settings_layout.addWidget(QLabel("Max"), 0, 4)
        settings_layout.addWidget(QLabel("Contrast"), 0, 5)
        settings_layout.addWidget(QLabel("Brightness"), 0, 6)

        scale_choices: list[tuple[str, ScaleAlgorithm]] = [
            ("Linear", ScaleAlgorithm.LINEAR),
            ("Log", ScaleAlgorithm.LOG),
            ("Sqrt", ScaleAlgorithm.SQRT),
            ("Squared", ScaleAlgorithm.POWER),
            ("Asinh", ScaleAlgorithm.ASINH),
            ("HistEq", ScaleAlgorithm.HISTOGRAM_EQUALIZATION),
        ]
        channel_settings: Dict[str, Dict[str, object]] = {}
        for row, channel in enumerate(self._rgb_channel_names(), start=1):
            settings_layout.addWidget(QLabel(channel.capitalize()), row, 0)

            scale_combo = QComboBox(settings_group)
            for label, _scale in scale_choices:
                scale_combo.addItem(label)
            channel_scale = frame.rgb_channel_scale.get(channel, ScaleAlgorithm.LINEAR)
            scale_index = next(
                (idx for idx, (_, scale) in enumerate(scale_choices) if scale == channel_scale),
                0,
            )
            scale_combo.setCurrentIndex(scale_index)
            settings_layout.addWidget(scale_combo, row, 1)

            auto_limits = QCheckBox(settings_group)
            channel_z1 = frame.rgb_channel_z1.get(channel)
            channel_z2 = frame.rgb_channel_z2.get(channel)
            auto_limits.setChecked(channel_z1 is None or channel_z2 is None)
            settings_layout.addWidget(auto_limits, row, 2)

            min_spin = QDoubleSpinBox(settings_group)
            min_spin.setDecimals(6)
            min_spin.setRange(-1e30, 1e30)
            min_spin.setValue(float(channel_z1) if channel_z1 is not None else 0.0)
            settings_layout.addWidget(min_spin, row, 3)

            max_spin = QDoubleSpinBox(settings_group)
            max_spin.setDecimals(6)
            max_spin.setRange(-1e30, 1e30)
            max_spin.setValue(float(channel_z2) if channel_z2 is not None else 1.0)
            settings_layout.addWidget(max_spin, row, 4)

            contrast_spin = QDoubleSpinBox(settings_group)
            contrast_spin.setDecimals(3)
            contrast_spin.setRange(0.1, 10.0)
            contrast_spin.setValue(float(frame.rgb_channel_contrast.get(channel, 1.0)))
            settings_layout.addWidget(contrast_spin, row, 5)

            brightness_spin = QDoubleSpinBox(settings_group)
            brightness_spin.setDecimals(3)
            brightness_spin.setRange(-1.0, 1.0)
            brightness_spin.setSingleStep(0.05)
            brightness_spin.setValue(float(frame.rgb_channel_brightness.get(channel, 0.0)))
            settings_layout.addWidget(brightness_spin, row, 6)

            min_spin.setEnabled(not auto_limits.isChecked())
            max_spin.setEnabled(not auto_limits.isChecked())
            auto_limits.toggled.connect(
                lambda checked, lo=min_spin, hi=max_spin: (
                    lo.setEnabled(not checked),
                    hi.setEnabled(not checked),
                )
            )

            channel_settings[channel] = {
                "scale_combo": scale_combo,
                "auto_limits": auto_limits,
                "min_spin": min_spin,
                "max_spin": max_spin,
                "contrast_spin": contrast_spin,
                "brightness_spin": brightness_spin,
            }
        layout.addWidget(settings_group)

        source_group = QGroupBox("Assign Channels from Existing Frames", dialog)
        source_layout = QFormLayout(source_group)
        source_combos: Dict[str, QComboBox] = {}
        source_frames = [
            (index, candidate)
            for index, candidate in enumerate(self.frame_manager.frames)
            if candidate.frame_id != frame.frame_id
            and candidate.image_data is not None
            and candidate.image_data.ndim == 2
        ]
        for channel in self._rgb_channel_names():
            combo = QComboBox(source_group)
            combo.addItem("Keep current data", "KEEP")
            combo.addItem("None (clear)", "CLEAR")
            for index, source_frame in source_frames:
                label = f"Frame {index + 1}"
                if source_frame.filepath:
                    label += f" - {source_frame.filepath.name}"
                combo.addItem(label, index)
            source_id = frame.rgb_source_frame_ids.get(channel)
            if source_id is not None:
                for item_index in range(combo.count()):
                    source_index = combo.itemData(item_index)
                    if (
                        isinstance(source_index, int)
                        and source_index < len(self.frame_manager.frames)
                        and self.frame_manager.frames[source_index].frame_id == source_id
                    ):
                        combo.setCurrentIndex(item_index)
                        break
            source_layout.addRow(channel.capitalize(), combo)
            source_combos[channel] = combo
        layout.addWidget(source_group)

        def apply_changes() -> None:
            for channel, radio in radio_buttons.items():
                if radio.isChecked():
                    frame.rgb_current_channel = channel
                    break
            for channel, checkbox in view_checks.items():
                frame.rgb_view[channel] = checkbox.isChecked()

            for channel, controls in channel_settings.items():
                scale_combo = controls["scale_combo"]
                auto_limits = controls["auto_limits"]
                min_spin = controls["min_spin"]
                max_spin = controls["max_spin"]
                contrast_spin = controls["contrast_spin"]
                brightness_spin = controls["brightness_spin"]

                if isinstance(scale_combo, QComboBox):
                    _, selected_scale = scale_choices[scale_combo.currentIndex()]
                    frame.rgb_channel_scale[channel] = selected_scale
                if isinstance(auto_limits, QCheckBox) and auto_limits.isChecked():
                    frame.rgb_channel_z1[channel] = None
                    frame.rgb_channel_z2[channel] = None
                else:
                    low = float(min_spin.value()) if isinstance(min_spin, QDoubleSpinBox) else 0.0
                    high = float(max_spin.value()) if isinstance(max_spin, QDoubleSpinBox) else 1.0
                    frame.rgb_channel_z1[channel] = min(low, high)
                    frame.rgb_channel_z2[channel] = max(low, high)
                frame.rgb_channel_contrast[channel] = (
                    float(contrast_spin.value()) if isinstance(contrast_spin, QDoubleSpinBox) else 1.0
                )
                frame.rgb_channel_brightness[channel] = (
                    float(brightness_spin.value()) if isinstance(brightness_spin, QDoubleSpinBox) else 0.0
                )

            updates: Dict[str, Optional[int]] = {}
            for channel, combo in source_combos.items():
                value = combo.currentData()
                if value == "KEEP":
                    continue
                if value == "CLEAR":
                    updates[channel] = None
                elif isinstance(value, int):
                    updates[channel] = value
            if updates:
                self._apply_rgb_frame_channels_from_sources(frame, updates)
            else:
                self._sync_rgb_scalar_view(frame)

            self._sync_view_state_from_rgb_channel(frame)
            self._apply_frame_view_state(frame)
            self._display_image()
            active = frame.rgb_current_channel.capitalize()
            self.statusBar().showMessage(f"RGB updated (active channel: {active})", 2000)

        def apply_and_close() -> None:
            apply_changes()
            dialog.accept()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            dialog,
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.clicked.connect(apply_and_close)
        if apply_button is not None:
            apply_button.clicked.connect(apply_changes)
        if cancel_button is not None:
            cancel_button.clicked.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _set_frame_lock_scope(self, scope: str, value: str) -> None:
        """Set lock scope value."""
        self._frame_lock_scope[scope] = value
        self.statusBar().showMessage(f"Frame lock {scope}: {value}", 2000)

    def _set_frame_lock_flag(self, flag: str, enabled: bool) -> None:
        """Set lock checkbox value."""
        self._frame_lock_flags[flag] = bool(enabled)
        state = "on" if enabled else "off"
        self.statusBar().showMessage(f"Frame lock {flag}: {state}", 2000)

    def _select_tiled_frame(self, x: int, y: int) -> bool:
        """Select frame corresponding to a click on the tiled composite."""
        if self._tile_layout is None:
            return False
        gap = int(self._tile_layout["gap"])
        cell_w = int(self._tile_layout["cell_w"])
        cell_h = int(self._tile_layout["cell_h"])
        cols = int(self._tile_layout["cols"])
        tiled_h = int(self._tile_layout["tiled_h"])
        frame_indices = self._tile_layout["frame_indices"]

        if x < gap or y < 0:
            return False
        top_y = tiled_h - 1 - y
        if top_y < gap:
            return False

        col = (x - gap) // (cell_w + gap)
        row = (top_y - gap) // (cell_h + gap)
        if col < 0 or row < 0 or col >= cols:
            return False
        if (x - gap) % (cell_w + gap) >= cell_w:
            return False
        if (top_y - gap) % (cell_h + gap) >= cell_h:
            return False

        tile_index = int(row * cols + col)
        if tile_index < 0 or tile_index >= len(frame_indices):
            return False
        frame_index = int(frame_indices[tile_index])
        if frame_index == self.frame_manager.current_index:
            return False
        self.frame_manager.goto_frame(frame_index)
        self._apply_frame_view_state(self.frame_manager.current_frame)
        return True

    def _persist_frame_view_state(self) -> None:
        """Persist display settings to the current frame."""
        frame = self.frame_manager.current_frame
        if not frame:
            return
        contrast, brightness = self.image_viewer.get_contrast_brightness()
        if frame.frame_type == "rgb":
            channel = frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
            frame.rgb_channel_scale[channel] = self.current_scale
            frame.rgb_channel_z1[channel] = self.z1
            frame.rgb_channel_z2[channel] = self.z2
            frame.rgb_channel_contrast[channel] = contrast
            frame.rgb_channel_brightness[channel] = brightness
        frame.colormap = self.current_colormap
        frame.scale = self.current_scale
        frame.invert_colormap = self.invert_colormap
        frame.z1 = self.z1
        frame.z2 = self.z2
        frame.zoom = self.image_viewer.get_zoom()
        frame.contrast = contrast
        frame.brightness = brightness
        if self.using_gpu_rendering and hasattr(self.image_viewer, "gl_canvas"):
            frame.pan_x, frame.pan_y = self.image_viewer.gl_canvas.pan_offset

    def _apply_frame_view_state(self, frame: Frame) -> None:
        """Apply stored display settings from the frame."""
        self.current_colormap = self._normalize_colormap_name(frame.colormap)
        self.invert_colormap = frame.invert_colormap
        if frame.frame_type == "rgb":
            self._sync_view_state_from_rgb_channel(frame)
        else:
            self.current_scale = frame.scale
            self.z1 = frame.z1
            self.z2 = frame.z2
        self._update_colormap_menu_checks()
        self.menu_bar.action_invert_colormap.setChecked(self.invert_colormap)
        self.menu_bar.action_scale_linear.setChecked(self.current_scale == ScaleAlgorithm.LINEAR)
        self.menu_bar.action_scale_log.setChecked(self.current_scale == ScaleAlgorithm.LOG)
        self.menu_bar.action_scale_sqrt.setChecked(self.current_scale == ScaleAlgorithm.SQRT)
        self.menu_bar.action_scale_squared.setChecked(self.current_scale == ScaleAlgorithm.POWER)
        self.menu_bar.action_scale_asinh.setChecked(self.current_scale == ScaleAlgorithm.ASINH)
        self.menu_bar.action_scale_histeq.setChecked(
            self.current_scale == ScaleAlgorithm.HISTOGRAM_EQUALIZATION
        )
        cmap_name_map = {
            "grey": "Gray",
            "heat": "Heat",
            "cool": "Cool",
            "rainbow": "Rainbow",
        }
        if self.current_colormap in cmap_name_map:
            self.button_bar.set_colormap(cmap_name_map[self.current_colormap])
        scale_name_map = {
            ScaleAlgorithm.LINEAR: "Linear",
            ScaleAlgorithm.LOG: "Log",
            ScaleAlgorithm.SQRT: "Sqrt",
            ScaleAlgorithm.POWER: "Squared",
            ScaleAlgorithm.ASINH: "Asinh",
            ScaleAlgorithm.HISTOGRAM_EQUALIZATION: "HistEq",
        }
        if self.current_scale in scale_name_map:
            self.button_bar.set_scale(scale_name_map[self.current_scale])
        if frame.frame_type != "rgb":
            self._set_viewer_contrast_brightness(frame.contrast, frame.brightness)
        if self.using_gpu_rendering and hasattr(self.image_viewer, "set_pan"):
            self.image_viewer.set_pan(frame.pan_x, frame.pan_y)

    def _sync_frame_view_state(self) -> None:
        """Persist current view state after rendering."""
        self._persist_frame_view_state()

    def _match_frames_image(self) -> None:
        """Match all frames to current image view settings."""
        source = self.frame_manager.current_frame
        if not source:
            self.statusBar().showMessage("No frame to match", 2000)
            return
        for frame in self.frame_manager.frames:
            if frame is source:
                continue
            frame.colormap = source.colormap
            frame.scale = source.scale
            frame.invert_colormap = source.invert_colormap
            frame.z1 = source.z1
            frame.z2 = source.z2
            frame.zoom = source.zoom
            frame.pan_x = source.pan_x
            frame.pan_y = source.pan_y
            frame.contrast = source.contrast
            frame.brightness = source.brightness
        self.statusBar().showMessage("Matched frames (image)", 2000)

    def _match_frames_wcs(self) -> None:
        """Match all frames to current frame using WCS."""
        source = self.frame_manager.current_frame
        if not source or not source.wcs_handler or not source.wcs_handler.is_valid:
            self.statusBar().showMessage("Current frame has no valid WCS", 2000)
            return
        if source.image_data is None:
            self.statusBar().showMessage("Current frame has no image data", 2000)
            return
        cx = source.image_data.shape[1] / 2
        cy = source.image_data.shape[0] / 2
        ra, dec = source.wcs_handler.pixel_to_world(cx, cy)
        for frame in self.frame_manager.frames:
            if frame is source:
                continue
            if frame.wcs_handler and frame.wcs_handler.is_valid:
                fx, fy = frame.wcs_handler.world_to_pixel(ra, dec)
                frame.pan_x = float(fx)
                frame.pan_y = float(fy)
                frame.zoom = source.zoom
                frame.colormap = source.colormap
                frame.scale = source.scale
                frame.invert_colormap = source.invert_colormap
                frame.z1 = source.z1
                frame.z2 = source.z2
                frame.contrast = source.contrast
                frame.brightness = source.brightness
        self.statusBar().showMessage("Matched frames (WCS)", 2000)

    def _match_frames_bin(self) -> None:
        """Match bin factors across frames."""
        source = self.frame_manager.current_frame
        if not source:
            self.statusBar().showMessage("No frame to match", 2000)
            return
        for frame in self.frame_manager.frames:
            if frame is not source:
                frame.bin_factor = source.bin_factor
        self.statusBar().showMessage("Matched frames (bin)", 2000)

    def _match_frames_axes_order(self) -> None:
        """Match cube axes order across frames."""
        self.statusBar().showMessage("Axes order matching is not yet implemented", 2000)

    def _match_frames_scale(self) -> None:
        """Match scale functions across frames."""
        source = self.frame_manager.current_frame
        if not source:
            self.statusBar().showMessage("No frame to match", 2000)
            return
        for frame in self.frame_manager.frames:
            if frame is not source:
                frame.scale = source.scale
        self.statusBar().showMessage("Matched frames (scale)", 2000)

    def _match_frames_scale_limits(self) -> None:
        """Match scale functions and limits across frames."""
        source = self.frame_manager.current_frame
        if not source:
            self.statusBar().showMessage("No frame to match", 2000)
            return
        for frame in self.frame_manager.frames:
            if frame is not source:
                frame.scale = source.scale
                frame.z1 = source.z1
                frame.z2 = source.z2
        self.statusBar().showMessage("Matched frames (scale and limits)", 2000)

    def _match_frames_colorbar(self) -> None:
        """Match colormap/colorbar choices across frames."""
        source = self.frame_manager.current_frame
        if not source:
            self.statusBar().showMessage("No frame to match", 2000)
            return
        for frame in self.frame_manager.frames:
            if frame is not source:
                frame.colormap = source.colormap
                frame.invert_colormap = source.invert_colormap
        self.statusBar().showMessage("Matched frames (colorbar)", 2000)

    def _match_frames_block(self) -> None:
        """Match block/bin factors across frames."""
        self._match_frames_bin()

    def _match_frames_smooth(self) -> None:
        """Match smoothing parameters across frames."""
        self.statusBar().showMessage("Smoothing parameters are global in this build", 2000)

    def _match_frames_3d(self) -> None:
        """Match 3D parameters across frames."""
        self.statusBar().showMessage("3D matching is not yet implemented", 2000)
    
    def _on_region_created(self, region) -> None:
        """Handle region creation."""
        frame = self.frame_manager.current_frame
        if frame:
            frame.regions.append(region)
        self.statusBar().showMessage(f"Created {region.mode.value} region", 2000)
    
    def _on_region_selected(self, region) -> None:
        """Handle region selection."""
        self.statusBar().showMessage(f"Selected {region.mode.value} region", 2000)

    def _set_region_mode(self, mode: RegionMode) -> None:
        """Set current region mode and sync UI."""
        self.image_viewer.set_region_mode(mode)
        mode_name_map = {
            RegionMode.NONE: "None",
            RegionMode.CIRCLE: "Circle",
            RegionMode.ELLIPSE: "Ellipse",
            RegionMode.BOX: "Box",
            RegionMode.POLYGON: "Polygon",
            RegionMode.LINE: "Line",
            RegionMode.POINT: "Point",
        }
        mode_name = mode_name_map.get(mode, "None")
        self.button_bar.set_region_mode(mode_name)
        self.statusBar().showMessage(f"Region mode: {mode_name}", 2000)

    def _clear_regions(self) -> None:
        """Clear all regions from the current frame."""
        frame = self.frame_manager.current_frame
        if frame:
            frame.regions.clear()
            self._samp_catalog_sources.pop(frame.frame_id, None)
        if hasattr(self.image_viewer, "clear_regions"):
            self.image_viewer.clear_regions()
        self._set_region_mode(RegionMode.NONE)
        self.statusBar().showMessage("Cleared all regions", 2000)

    def _save_regions(self) -> None:
        """Save regions to a DS9 region file."""
        frame = self.frame_manager.current_frame
        if not frame or not frame.regions:
            self.statusBar().showMessage("No regions to save", 2000)
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Region File",
            "",
            "Region Files (*.reg);;All Files (*)",
        )
        if not filepath:
            return
        base_regions = self._overlay_regions_to_base(frame.regions)
        if not base_regions:
            self.statusBar().showMessage("No supported regions to save", 2000)
            return
        writer = RegionWriter()
        writer.write_file(base_regions, filepath)
        self.statusBar().showMessage(f"Saved regions to {filepath}", 3000)

    def _overlay_regions_to_base(self, regions: list[Region]) -> list:
        """Convert overlay regions to DS9 BaseRegion instances."""
        converted = []
        for region in regions:
            if region.mode == RegionMode.CIRCLE and len(region.points) >= 2:
                center = region.points[0]
                edge = region.points[1]
                radius = ((edge.x() - center.x()) ** 2 + (edge.y() - center.y()) ** 2) ** 0.5
                converted.append(Circle(center=(center.x(), center.y()), radius=radius))
            elif region.mode == RegionMode.ELLIPSE and len(region.points) >= 2:
                p1, p2 = region.points[0], region.points[1]
                center = ((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
                semi_major = abs(p2.x() - p1.x()) / 2
                semi_minor = abs(p2.y() - p1.y()) / 2
                converted.append(Ellipse(center=center, semi_major=semi_major, semi_minor=semi_minor))
            elif region.mode == RegionMode.BOX and len(region.points) >= 2:
                p1, p2 = region.points[0], region.points[1]
                center = ((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
                width_box = abs(p2.x() - p1.x())
                height_box = abs(p2.y() - p1.y())
                converted.append(Box(center=center, width_box=width_box, height_box=height_box))
            elif region.mode == RegionMode.LINE and len(region.points) >= 2:
                p1, p2 = region.points[0], region.points[1]
                converted.append(Line(start=(p1.x(), p1.y()), end=(p2.x(), p2.y())))
            elif region.mode == RegionMode.POINT and len(region.points) >= 1:
                p1 = region.points[0]
                converted.append(Point(center=(p1.x(), p1.y())))
            elif region.mode == RegionMode.POLYGON and len(region.points) >= 3:
                vertices = [(p.x(), p.y()) for p in region.points]
                converted.append(Polygon(vertices=vertices))
        return converted

    def _base_region_to_overlay(self, region) -> Optional[Region]:
        """Convert a BaseRegion to an overlay Region."""
        if isinstance(region, Circle):
            cx, cy = region.center
            r = region.radius
            return Region(
                mode=RegionMode.CIRCLE,
                points=[QPointF(cx, cy), QPointF(cx + r, cy)],
                color=QColor(region.color)
            )
        if isinstance(region, Ellipse):
            cx, cy = region.center
            a = region.semi_major
            b = region.semi_minor
            return Region(
                mode=RegionMode.ELLIPSE,
                points=[QPointF(cx - a, cy - b), QPointF(cx + a, cy + b)],
                color=QColor(region.color)
            )
        if isinstance(region, Box):
            cx, cy = region.center
            half_w = region.width_box / 2
            half_h = region.height_box / 2
            return Region(
                mode=RegionMode.BOX,
                points=[QPointF(cx - half_w, cy - half_h), QPointF(cx + half_w, cy + half_h)],
                color=QColor(region.color)
            )
        if isinstance(region, Line):
            x1, y1 = region.start
            x2, y2 = region.end
            return Region(
                mode=RegionMode.LINE,
                points=[QPointF(x1, y1), QPointF(x2, y2)],
                color=QColor(region.color)
            )
        if isinstance(region, Point):
            cx, cy = region.center
            return Region(
                mode=RegionMode.POINT,
                points=[QPointF(cx, cy)],
                color=QColor(region.color)
            )
        if isinstance(region, Polygon):
            points = [QPointF(x, y) for x, y in region.vertices]
            return Region(
                mode=RegionMode.POLYGON,
                points=points,
                color=QColor(region.color)
            )
        return None

    def closeEvent(self, event) -> None:
        """Disconnect SAMP client on close."""
        if self._samp_client is not None:
            self._samp_client.disconnect()
            self._samp_connected = False
        super().closeEvent(event)
    
    def show_about(self) -> None:
        """Show the About dialog."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "About NCRADS9",
            "<h2>NCRADS9</h2>"
            "<p>A Python/Qt6 clone of SAOImageDS9</p>"
            "<p>Version 0.1.0</p>"
            "<p>Copyright © 2026 Yogesh Wadadekar</p>"
            "<p>Licensed under GPL v3</p>"
        )
    
    def show_about_qt(self) -> None:
        """Show the About Qt dialog."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.aboutQt(self, "About Qt")
