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

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from urllib.parse import unquote, urlparse

import astropy.units as u
import numpy as np
from astropy.coordinates import (
    SkyCoord,
)
from astropy.table import Table
from numpy.typing import NDArray
from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QImage, QKeyEvent, QPixmap
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDockWidget,
    QInputDialog,
    QMainWindow,
    QScrollArea,
    QWidget,
)

from ..catalogs.vizier import VizierCatalog
from ..colormaps.colormap import Colormap
from ..communication.samp import SAMPClient
from ..coordinates.coord_system import CoordinateContext
from ..core.fits_handler import FITSHandler
from ..core.wcs_handler import WCSHandler
from ..frames.blink_controller import (
    DEFAULT_BLINK_INTERVAL_MS,
    DEFAULT_FADE_INTERVAL_MS,
    BlinkController,
)
from ..frames.frame import Frame
from ..frames.frame_manager import FrameManager
from ..frames.tile_layout import TileLayout
from ..image_servers.sia_client import SIAClient
from ..regions.base_region import BaseRegion
from ..regions.shapes.box import Box
from ..regions.shapes.circle import Circle
from ..regions.shapes.ellipse import Ellipse
from ..regions.shapes.point import Point
from ..rendering.rgb_compositor import compose_rgb
from ..rendering.scale_algorithms import ScaleAlgorithm, apply_scale, compute_zscale_limits
from ..utils.preferences import Preferences
from .button_bar import ButtonBar
from .controllers.analysis import AnalysisController
from .controllers.base import Controller
from .controllers.color import ColorController
from .controllers.edit import EditController
from .controllers.file import FileController
from .controllers.frame import FrameController
from .controllers.region import RegionController
from .controllers.scale import ScaleController
from .controllers.view import ViewController
from .controllers.wcs import WCSController
from .controllers.zoom import ZoomController
from .dialogs.help_contents_dialog import HelpContentsDialog
from .dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from .dialogs.vo_query_dialog import VOQueryDialog
from .menu_bar import MenuBar
from .panels.horizontal_graph import HorizontalGraph
from .panels.magnifier import MagnifierPanel
from .panels.panner import PannerPanel
from .panels.vertical_graph import VerticalGraph
from .status_bar import StatusBar
from .toolbar import MainToolbar
from .view_transform import (
    transform_image_array,
)
from .widgets.colorbar_widget import ColorbarWidget
from .widgets.gl_image_viewer_with_regions import GLImageViewerWithRegions
from .widgets.image_viewer_with_regions import ImageViewerWithRegions
from .widgets.region_overlay import RegionMode

if TYPE_CHECKING:
    from ncrads9.utils.config import Config


class MainWindow(QMainWindow):
    """Main application window for NCRADS9."""

    #: Smallest viewport dimension, in pixels, that is treated as laid out.
    MIN_USABLE_VIEWPORT: int = 64
    #: DS9's default canvas size, used when no laid-out viewport is available.
    DEFAULT_CANVAS_WIDTH: int = 738
    DEFAULT_CANVAS_HEIGHT: int = 528

    samp_table_received = pyqtSignal(str, str, str)

    def __init__(self, config: Optional["Config"] = None, parent: QWidget | None = None) -> None:
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

        # Controllers only capture a reference to this window, so they can be
        # built before the state they will later reach through it. Signals
        # connected below need them to exist.
        self._setup_controllers()

        # Initialize data storage
        self.frame_manager = FrameManager()
        self.current_scale = ScaleAlgorithm.LINEAR
        self.current_colormap = "grey"
        self._default_colormap = "grey"
        self.invert_colormap = False
        self.custom_colormaps: dict[str, Colormap] = {}
        self._user_colormap_actions: dict[str, object] = {}
        self.current_bin = 1
        # Single source of truth for how coordinates are transformed and
        # written. Every coordinate string in the UI goes through it.
        self.coord_context = CoordinateContext()
        self._last_mouse_pos: tuple[int, int] | None = None
        self._preview_rgb_cache: NDArray[np.uint8] | None = None
        self._preview_rgb_cache_frame_id: int | None = None
        # A staticmethod, so it is callable before the controllers exist.
        self.preferences = Preferences(EditController.preferences_path())
        self.use_gpu_rendering = bool(self.preferences.get("use_gpu", True))
        self.using_gpu_rendering = False
        self.z1 = None  # Scale limits
        self.z2 = None
        self._contour_settings: dict | None = None
        self._contour_paths: list | None = None
        self._contour_levels: list | None = None
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
        self._grid_settings: dict | None = None
        self._analysis_command_log = False
        self._analysis_command_entries: list[str] = []
        self._loaded_analysis_actions: list[QAction] = []
        self._analysis_mask_mode = "disabled"
        self._analysis_mask_min: float | None = None
        self._analysis_mask_max: float | None = None
        self._crosshair_enabled = False
        self._crosshair_color = QColor(255, 0, 0)
        self._crosshair_size = 24
        self._show_direction_arrows = True
        self._frame_display_mode = "single"
        self._tile_mode_enabled = False
        self._tile_arrangement_mode = "grid"
        self._tile_layout: TileLayout | None = None
        self._tile_frame_indices: list[int] = []
        current_frame = self.frame_manager.current_frame
        self._active_frame_ids: set[int] = {current_frame.frame_id} if current_frame else set()
        self._known_frame_ids: set[int] = set(self._active_frame_ids)
        self._frame_lock_scope: dict[str, str] = {
            "frame": "none",
            "crosshair": "none",
            "crop": "none",
            "slice": "none",
        }
        self._frame_lock_flags: dict[str, bool] = {
            "bin": False,
            "axes_order": False,
            "scale": False,
            "scale_limits": False,
            "colorbar": False,
            "block": False,
            "smooth": False,
            "3d": False,
        }
        self._fade_interval_ms = DEFAULT_FADE_INTERVAL_MS
        self._samp_client: SAMPClient | None = None
        self._samp_connected = False
        self._samp_marker_color = QColor(255, 255, 0)
        self._samp_marker_shape = "box"
        self._samp_marker_size = 6.0
        self._samp_catalog_sources: dict[int, list[tuple[float, float]]] = {}
        self._blink_controller = BlinkController(interval_ms=DEFAULT_BLINK_INTERVAL_MS)
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(DEFAULT_BLINK_INTERVAL_MS)
        self._blink_timer.timeout.connect(self.frame_controller.advance_blink)
        self.samp_table_received.connect(self._handle_samp_table_message)

        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_dock_widgets()
        self._setup_status_bar()
        self._init_samp_client()
        self._update_samp_menu_state()
        self.edit.apply_preferences(self.edit.preferences_dict(), persist=False, show_message=False)
        self.frame_controller.refresh_menu_items()

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

    def _get_rgb_active_channel_data(self, frame: Frame) -> NDArray[np.floating] | None:
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
    ) -> tuple[ScaleAlgorithm, float | None, float | None, float, float]:
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
        scaled = apply_scale(data, scale, vmin=adjusted_z1, vmax=adjusted_z2)
        return np.clip(scaled.astype(np.float32), 0.0, 1.0)

    def _compose_rgb_frame_image(self, frame: Frame) -> NDArray[np.uint8] | None:
        """Compose display RGB image for an RGB frame."""
        channels = {
            name: frame.rgb_channels.get(name)
            for name in self._rgb_channel_names()
            if frame.rgb_channels.get(name) is not None
        }
        if not channels:
            return None

        base_shape = next(iter(channels.values())).shape

        # Scale each channel with its own algorithm and limits, then let the
        # frame combine them: RGBFrame stacks, HSVFrame and HLSFrame convert
        # from their colour space. Frames created before the typed subclasses
        # existed, and plain Frames carrying frame_type="rgb", fall back to a
        # plain stack.
        normalized = {
            name: self._compute_rgb_channel_scaled(frame, name, data)
            for name, data in ((name, frame.rgb_channels.get(name)) for name in self._rgb_channel_names())
            if data is not None and data.shape == base_shape
        }
        compose = getattr(frame, "compose", None)
        composed = (
            compose(normalized, frame.rgb_view)
            if compose is not None
            else compose_rgb(normalized, frame.rgb_view)
        )
        if composed is None:
            return np.zeros((base_shape[0], base_shape[1], 3), dtype=np.uint8)
        return composed

    def _apply_rgb_frame_channels_from_sources(
        self,
        frame: Frame,
        channel_to_source_index: dict[str, int | None],
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
        self.color.set_contrast_brightness(contrast, brightness)

    def _setup_controllers(self) -> None:
        """Create the per-menu controllers.

        Runs before `_setup_menu_bar`, because that calls each controller's
        `connect()` to wire its own actions. See `ui/controllers/base.py` for
        why controllers hold a reference to the window.
        """
        self.analysis = AnalysisController(self)
        self.color = ColorController(self)
        # Named `frame_controller`: `self.frame` would shadow nothing on the
        # window, but reads as a Frame everywhere else in the codebase.
        self.frame_controller = FrameController(self)
        self.edit = EditController(self)
        self.file = FileController(self)
        self.region = RegionController(self)
        self.view = ViewController(self)
        self.zoom = ZoomController(self)
        self.scale = ScaleController(self)
        self.wcs = WCSController(self)

        #: Every controller, for broadcasting `sync()` on a frame change.
        self.controllers: tuple[Controller, ...] = (
            self.analysis,
            self.color,
            self.edit,
            self.frame_controller,
            self.file,
            self.region,
            self.scale,
            self.view,
            self.wcs,
            self.zoom,
        )

    def _sync_controllers(self) -> None:
        """Bring every controller's menu state in step with the current frame."""
        for controller in self.controllers:
            controller.sync()

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
        self.file.connect()
        self.edit.connect()
        self.view.connect()

        # Frame menu
        self.frame_controller.connect()

        # Scale, Color and Region menus
        self.scale.connect()
        self.color.connect()
        self.region.connect()

        # VO menu. Not a DS9 menu -- DS9 reaches these from Analysis
        # (PLAN.md section 7). M8 folds them into the Analysis menu proper.
        self.menu_bar.action_siap_2mass.triggered.connect(self._vo_siap_2mass)
        self.menu_bar.action_catalog_vizier.triggered.connect(self._vo_catalog_vizier)
        self.menu_bar.action_samp_connect.triggered.connect(self._samp_connect)
        self.menu_bar.action_samp_disconnect.triggered.connect(self._samp_disconnect)
        self.menu_bar.action_samp_marker_color.triggered.connect(self._samp_choose_marker_color)
        self.menu_bar.action_samp_marker_shape.triggered.connect(self._samp_choose_marker_shape)
        self.menu_bar.action_samp_marker_size.triggered.connect(self._samp_choose_marker_size)

        # WCS menu
        self.wcs.connect()

        # Analysis and Bin menus
        self.analysis.connect()

        # Analysis entries still served by the window: the VO and catalog
        # tools, and the FITS header viewer.
        self.menu_bar.action_analysis_2mass.triggered.connect(self._vo_siap_2mass)
        self.menu_bar.action_analysis_vizier.triggered.connect(self._vo_catalog_vizier)
        self.menu_bar.action_catalog_tool.triggered.connect(self._vo_catalog_vizier)
        self.menu_bar.action_virtual_observatory.triggered.connect(self._vo_catalog_vizier)
        self.menu_bar.action_fits_header.triggered.connect(self.file.show_header)
        self.menu_bar.action_plot_tool_line.triggered.connect(
            lambda: self.statusBar().showMessage("Plot Tool arrives in M7-15", 2000)
        )
        self.menu_bar.action_plot_tool_bar.triggered.connect(
            lambda: self.statusBar().showMessage("Plot Tool arrives in M7-15", 2000)
        )

        # Zoom menu
        self.zoom.connect()

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
        self.main_toolbar.action_open.triggered.connect(self.file.open_file)
        self.main_toolbar.action_save.triggered.connect(self.file.save_file)
        self.main_toolbar.action_zoom_in.triggered.connect(self.zoom.zoom_in)
        self.main_toolbar.action_zoom_out.triggered.connect(self.zoom.zoom_out)
        self.main_toolbar.action_zoom_fit.triggered.connect(self.zoom.zoom_fit)
        self.main_toolbar.action_zoom_1.triggered.connect(self.zoom.zoom_actual)
        self.main_toolbar.action_statistics.triggered.connect(self.analysis.show_statistics)
        self.main_toolbar.action_histogram.triggered.connect(self.analysis.show_histogram)
        self.main_toolbar.action_prev_frame.triggered.connect(self.frame_controller.previous)
        self.main_toolbar.action_next_frame.triggered.connect(self.frame_controller.next)
        self.main_toolbar.action_region_circle.triggered.connect(
            lambda: self.region.set_mode(RegionMode.CIRCLE)
        )
        self.main_toolbar.action_region_box.triggered.connect(lambda: self.region.set_mode(RegionMode.BOX))
        self.main_toolbar.action_region_polygon.triggered.connect(
            lambda: self.region.set_mode(RegionMode.POLYGON)
        )

    def _setup_central_widget(self) -> None:
        """Set up the central widget."""
        # Create scroll area for image display
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)  # Allow widget to use full viewport
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.horizontalScrollBar().valueChanged.connect(lambda _: self.zoom.update_panner_rect())
        self.scroll_area.verticalScrollBar().valueChanged.connect(lambda _: self.zoom.update_panner_rect())

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
        viewer.contrast_changed.connect(self.color.on_contrast_changed)
        viewer.region_created.connect(self.region.on_created)
        viewer.region_selected.connect(self.region.on_selected)
        if hasattr(viewer, "gl_canvas"):
            viewer.gl_canvas.pan_changed.connect(lambda *_: self.zoom.update_panner_rect())
            viewer.gl_canvas.zoom_changed.connect(lambda *_: self.zoom.update_panner_rect())
        return viewer

    def _setup_dock_widgets(self) -> None:
        """Set up dock widgets."""
        # Left dock for button bar
        self.button_bar_dock = QDockWidget("Controls", self)
        self.button_bar = ButtonBar(self)

        # Connect button bar signals
        self.button_bar.zoom_changed.connect(self.zoom.on_button_bar_zoom)
        self.button_bar.scale_changed.connect(self._on_button_bar_scale)
        self.button_bar.colormap_changed.connect(self._on_button_bar_colormap)
        self.button_bar.region_mode_changed.connect(self.region.on_button_bar_mode)

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
        self.panner_panel.pan_to.connect(self.zoom.on_panner_pan)
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

    def _rebuild_image_viewer(self, use_gpu: bool) -> None:
        """Recreate the image viewer based on GPU setting."""
        self.use_gpu_rendering = use_gpu
        new_viewer = self._create_image_viewer(use_gpu)
        self.image_viewer = new_viewer
        self.scroll_area.setWidget(self.image_viewer)
        if self.image_data is not None:
            self._display_image()

    def _apply_background_color(self, color_hex: str) -> None:
        """Apply background color to the viewer."""
        # Both viewer backends expose set_background_color, so this does not
        # depend on which one is active. (This was previously an if/elif whose
        # two branches were identical, making the GPU test dead.)
        if hasattr(self.image_viewer, "set_background_color"):
            self.image_viewer.set_background_color(color_hex)

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

        # Load FITS file. ImageData gathers the array, header, WCS and derived
        # metadata (BITPIX, cached min/max) in one place; M4 extends this to
        # extensions, cubes and mosaics.
        fits_handler = FITSHandler()
        fits_handler.load(filepath)
        image = fits_handler.load_image_data()
        image_data = image.data
        header = image.header
        wcs_handler = WCSHandler(header)

        # Update frame
        frame.filepath = Path(filepath)
        frame.fits_handler = fits_handler
        frame.image = image
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
        self.zoom.zoom_fit()

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
        scaled_preview = apply_scale(
            preview_data,
            self.current_scale,
            vmin=z1,
            vmax=z2,
        )
        rgb_preview = cmap.apply_normalized(scaled_preview)
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

    def _apply_view_transform_to_viewer(self, frame: Frame) -> None:
        """Apply per-frame orientation/rotation to the active viewer."""
        if self.using_gpu_rendering and (not np.isclose(frame.rotation, 0.0) or frame.flip_x or frame.flip_y):
            self._rebuild_image_viewer(False)
            self.statusBar().showMessage(
                "Switched to CPU rendering for rotated/flipped display",
                2500,
            )
        if hasattr(self.image_viewer, "set_view_transform"):
            self.image_viewer.set_view_transform(frame.rotation, frame.flip_x, frame.flip_y)

    def _get_cpu_pan_center(self) -> tuple[float, float] | None:
        """Return the current CPU-view center in source image coordinates."""
        viewer = getattr(self.image_viewer, "image_viewer", None)
        if viewer is None or self.image_data is None:
            return None
        zoom = max(self.image_viewer.get_zoom(), 1e-6)
        display_x = (
            self.scroll_area.horizontalScrollBar().value() + self.scroll_area.viewport().width() / 2
        ) / zoom
        display_y = (
            self.scroll_area.verticalScrollBar().value() + self.scroll_area.viewport().height() / 2
        ) / zoom
        source_x, source_top_y = viewer.get_view_transform().display_to_source(display_x, display_y)
        source_y = viewer.get_image_size()[1] - 1 - source_top_y
        return (float(source_x), float(source_y))

    def _transform_preview_image(
        self,
        image: NDArray[np.generic],
        frame: Frame,
    ) -> NDArray[np.generic]:
        """Apply frame orientation/rotation to panner and magnifier previews."""
        return transform_image_array(image, frame.rotation, frame.flip_x, frame.flip_y)

    def _cache_preview_rgb(self, frame: Frame, image: NDArray[np.uint8]) -> None:
        """Remember the latest untransformed preview RGB for fast view updates."""
        self._preview_rgb_cache = np.ascontiguousarray(image)
        self._preview_rgb_cache_frame_id = frame.frame_id

    def _update_preview_panels(self, frame: Frame) -> None:
        """Refresh panner/magnifier panels from the cached preview image."""
        if self._preview_rgb_cache is None or self._preview_rgb_cache_frame_id != frame.frame_id:
            return
        transformed_preview = self._transform_preview_image(self._preview_rgb_cache, frame)
        if hasattr(self, "panner_panel"):
            self.panner_panel.set_image(
                transformed_preview,
                source_size=(transformed_preview.shape[1], transformed_preview.shape[0]),
            )
        if hasattr(self, "magnifier_panel"):
            self.magnifier_panel.set_image(
                transformed_preview,
                source_size=(transformed_preview.shape[1], transformed_preview.shape[0]),
            )

    def _refresh_transformed_view(self, frame: Frame) -> None:
        """Apply a pure view transform change without re-rendering image data."""
        self._apply_view_transform_to_viewer(frame)
        self._update_preview_panels(frame)
        self.zoom.update_panner_rect()
        self.wcs.update_direction_arrows()
        if self._last_mouse_pos is not None:
            self._on_mouse_moved(*self._last_mouse_pos)

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
        self._apply_view_transform_to_viewer(frame)

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
            cmap = self.color.colormap(self.current_colormap)
        except ValueError:
            self.current_colormap = "grey"
            cmap = self.color.colormap(self.current_colormap)

        # Invert colormap if needed
        if self.invert_colormap:
            # Get colormap data and invert
            cmap_data = cmap.colors.copy()
            cmap_data = cmap_data[::-1]  # Reverse the colormap
            cmap = Colormap(f"{self.current_colormap}_inverted", cmap_data)

        # Update colorbar
        self.colorbar_widget.set_colormap(
            cmap.colors, adjusted_z1, adjusted_z2, self.current_colormap, self.invert_colormap
        )

        if self.using_gpu_rendering:

            def tile_provider(x: int, y: int, w: int, h: int) -> NDArray[np.uint8]:
                tile = self._extract_gpu_tile_data(image_data, x, y, w, h)
                scaled = apply_scale(tile, self.current_scale, vmin=adjusted_z1, vmax=adjusted_z2)
                rgb = cmap.apply_normalized(scaled)
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
            scaled = apply_scale(image_data, self.current_scale, vmin=adjusted_z1, vmax=adjusted_z2)
            rgb_full = cmap.apply_normalized(scaled)
            display_rgb = np.ascontiguousarray(np.flipud(rgb_full))

            # Convert to QImage
            height, width = display_rgb.shape[:2]
            bytes_per_line = 3 * width
            qimage = QImage(display_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)

            # Create pixmap and display
            pixmap = QPixmap.fromImage(qimage)
            self.image_viewer.set_image(pixmap)

        preview_rgb = self._render_preview_rgb(
            image_data,
            adjusted_z1,
            adjusted_z2,
            cmap,
        )
        self._cache_preview_rgb(frame, preview_rgb)
        transformed_preview = self._transform_preview_image(preview_rgb, frame)

        # Update panner panel with RGB data (DS9 style)
        if hasattr(self, "panner_panel"):
            self.panner_panel.set_image(
                transformed_preview,
                source_size=(transformed_preview.shape[1], transformed_preview.shape[0]),
            )
            self.zoom.update_panner_rect()

        # Update magnifier panel with RGB data (DS9 style)
        if hasattr(self, "magnifier_panel"):
            self.magnifier_panel.set_image(
                transformed_preview,
                source_size=(transformed_preview.shape[1], transformed_preview.shape[0]),
            )
        if hasattr(self, "horizontal_graph_dock"):
            self.horizontal_graph_dock.set_image(image_data)
        if hasattr(self, "vertical_graph_dock"):
            self.vertical_graph_dock.set_image(image_data)

        # Update zoom display
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self.analysis.sync_bin_menu(getattr(frame, "bin_factor", 1))
        self.region.show_frame_regions(frame)
        self.frame_controller.sync_view_state()
        if self._contour_settings is not None:
            self.analysis.update_contours()
        self.wcs.update_direction_arrows()
        self.analysis.refresh_overlays()

    def _display_rgb_frame(self, frame: Frame) -> bool:
        """Display a composite RGB frame."""
        active_channel = (
            frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
        )
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
            self.color.colormap("grey").colors,
            0.0,
            255.0,
            "RGB Composite",
            False,
        )
        display_rgb = np.ascontiguousarray(np.flipud(composite))
        self._apply_view_transform_to_viewer(frame)

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

        self._cache_preview_rgb(frame, display_rgb)
        transformed_preview = self._transform_preview_image(display_rgb, frame)

        if hasattr(self, "panner_panel"):
            self.panner_panel.set_image(
                transformed_preview,
                source_size=(transformed_preview.shape[1], transformed_preview.shape[0]),
            )
            self.zoom.update_panner_rect()
        if hasattr(self, "magnifier_panel"):
            self.magnifier_panel.set_image(
                transformed_preview,
                source_size=(transformed_preview.shape[1], transformed_preview.shape[0]),
            )
        if hasattr(self, "horizontal_graph_dock"):
            self.horizontal_graph_dock.set_image(active_data)
        if hasattr(self, "vertical_graph_dock"):
            self.vertical_graph_dock.set_image(active_data)

        self.status_bar.update_image_info(composite.shape[1], composite.shape[0])
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self.analysis.sync_bin_menu(getattr(frame, "bin_factor", 1))
        self.region.show_frame_regions(frame)
        self.frame_controller.sync_view_state()
        if self._contour_settings is not None:
            self.analysis.update_contours()
        self.wcs.update_direction_arrows()
        self.analysis.refresh_overlays()
        return True

    def _render_frame_rgb(self, frame: Frame) -> NDArray[np.uint8] | None:
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
            cmap = self.color.colormap(frame.colormap)
        except ValueError:
            frame.colormap = "grey"
            cmap = self.color.colormap("grey")
        if frame.invert_colormap:
            cmap_data = cmap.colors.copy()[::-1]
            cmap = Colormap(f"{frame.colormap}_inverted", cmap_data)

        scaled = apply_scale(image_data, frame.scale, vmin=adjusted_z1, vmax=adjusted_z2)
        return cmap.apply_normalized(scaled)

    def _display_tiled_frames(self) -> bool:
        """Render all loaded frames in a tiled grid."""
        rgb_frames: list[NDArray[np.uint8]] = []
        frame_indices: list[int] = []
        active_indices = self.frame_controller.active_indices()
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

        layout = TileLayout.compute(
            count=len(rgb_frames),
            cell_width=max(rgb.shape[1] for rgb in rgb_frames),
            cell_height=max(rgb.shape[0] for rgb in rgb_frames),
            mode=self._tile_arrangement_mode,
        )
        self._tile_layout = layout
        self._tile_frame_indices = frame_indices

        cell_w, cell_h = layout.cell_width, layout.cell_height
        tiled_w, tiled_h = layout.width, layout.height
        tiled_rgb = np.zeros((tiled_h, tiled_w, 3), dtype=np.uint8)

        for placement, rgb in zip(layout.placements(), rgb_frames, strict=True):
            if rgb.shape[0] != cell_h or rgb.shape[1] != cell_w:
                y_idx = np.linspace(0, rgb.shape[0] - 1, cell_h).astype(np.int32)
                x_idx = np.linspace(0, rgb.shape[1] - 1, cell_w).astype(np.int32)
                rgb = rgb[y_idx][:, x_idx]
            # `placement` is bottom-up; `tiled_rgb` rows are top-down.
            top = tiled_h - placement.y - cell_h
            tiled_rgb[top : top + cell_h, placement.x : placement.x + cell_w] = rgb
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

    def _get_display_image_data(self, frame: Frame) -> NDArray[np.floating]:
        """Return frame data after display-level analysis transforms."""
        image_data = (
            self._get_rgb_active_channel_data(frame) if frame.frame_type == "rgb" else frame.image_data
        )
        if image_data is None:
            return np.array([], dtype=np.float32)
        if self.menu_bar.action_smooth.isChecked():
            return self.analysis.apply_smoothing(image_data)
        return image_data

    def _effective_viewport_size(self) -> QSize:
        """Return a usable viewport size for zoom/block-factor arithmetic.

        ``QScrollArea.viewport().size()`` is only meaningful once the widget has
        been laid out. Before the window is shown -- at startup, and in headless
        tests -- it reports a degenerate size (a few tens of pixels), which makes
        any zoom or block factor derived from it wildly wrong. Fall back to the
        scroll area, then the window, then DS9's default canvas size.
        """
        candidates = (
            self.scroll_area.viewport().size(),
            self.scroll_area.size(),
            self.size(),
        )
        for size in candidates:
            if size.width() >= self.MIN_USABLE_VIEWPORT and size.height() >= self.MIN_USABLE_VIEWPORT:
                return size
        return QSize(self.DEFAULT_CANVAS_WIDTH, self.DEFAULT_CANVAS_HEIGHT)

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
            self.wcs.update_readout(x, y)

        # Update magnifier panel (DS9 style)
        if hasattr(self, "magnifier_panel"):
            frame = self.frame_manager.current_frame
            viewer = getattr(self.image_viewer, "image_viewer", None)
            if frame is not None and viewer is not None:
                display_coords = viewer.map_image_to_display_coords(x, y)
                if display_coords is not None:
                    self.magnifier_panel.update_cursor_position(*display_coords)
        if hasattr(self, "horizontal_graph_dock") and self.horizontal_graph_dock.isVisible():
            self.horizontal_graph_dock.update_cursor_position(x, row)
        if hasattr(self, "vertical_graph_dock") and self.vertical_graph_dock.isVisible():
            self.vertical_graph_dock.update_cursor_position(x, row)
        self.analysis.refresh_overlays()

    def _on_image_clicked(self, x: int, y: int, button: int) -> None:
        """Handle image clicks (used for tiled frame selection)."""
        if not self._tile_mode_enabled or button != int(Qt.MouseButton.LeftButton.value):
            return
        if self.frame_controller.select_tile_at(x, y):
            self._display_tiled_frames()
            self.frame_controller.update_title()
            self.statusBar().showMessage(
                f"Selected frame {self.frame_manager.current_index + 1}",
                1500,
            )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard panning with arrow keys."""
        key = event.key()
        if key == Qt.Key.Key_Left:
            self.zoom.pan_by_pixels(-1, 0)
            event.accept()
            return
        if key == Qt.Key.Key_Right:
            self.zoom.pan_by_pixels(1, 0)
            event.accept()
            return
        if key == Qt.Key.Key_Up:
            self.zoom.pan_by_pixels(0, 1)
            event.accept()
            return
        if key == Qt.Key.Key_Down:
            self.zoom.pan_by_pixels(0, -1)
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
            self.scale.set_scale(scale_map[scale_name])

    def _on_button_bar_colormap(self, cmap_name: str) -> None:
        """Handle colormap change from button bar."""
        cmap_map = {
            "Gray": "grey",
            "Heat": "heat",
            "Cool": "cool",
            "Rainbow": "rainbow",
        }
        if cmap_name in cmap_map:
            self.color.set_colormap(cmap_map[cmap_name])

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
            self.frame_controller.new_frame()
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
            pixel = self.region.world_to_pixel(coord.ra.deg, coord.dec.deg)
            if pixel is None:
                continue
            x, y = pixel
            region = Point(center=(x, y), origin="vizier_catalog")
            self.region.on_created(region)
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

        sources: list[tuple[float, float]] = []
        for coord in coords:
            pixel = self.region.world_to_pixel(coord.ra.deg, coord.dec.deg)
            if pixel is not None:
                sources.append(pixel)

        if not sources:
            self.statusBar().showMessage("No plottable sources in SAMP catalog", 3000)
            return

        self._samp_catalog_sources[frame.frame_id] = sources
        self._rebuild_samp_regions_for_frame(frame)
        self.region.show_frame_regions(frame)
        self.statusBar().showMessage(f"Loaded SAMP catalog {table_id}: {len(sources)} sources", 4000)

    def _read_samp_table(self, url: str, table_format: str) -> Table | None:
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

    def _extract_catalog_coordinates(self, table: Table) -> list[SkyCoord] | None:
        """Extract ICRS coordinates from a table."""
        ra_col: str | None = None
        dec_col: str | None = None
        for col in table.colnames:
            col_lower = col.lower()
            if col_lower in ("ra", "_ra", "raj2000", "ra_icrs", "ra_j2000"):
                ra_col = col
            elif col_lower in ("dec", "_dec", "dej2000", "de", "dec_icrs", "dec_j2000"):
                dec_col = col
        if ra_col is None or dec_col is None:
            return None

        coords: list[SkyCoord] = []
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

    def _build_samp_marker_region(self, x: float, y: float) -> BaseRegion:
        """Create a region marking a SAMP catalog source.

        Tagged with origin="samp_catalog" so `_rebuild_samp_regions_for_frame`
        can replace exactly these regions when the marker style changes,
        without disturbing anything the user drew.
        """
        size = max(1.0, float(self._samp_marker_size))
        shape = self._samp_marker_shape
        common = {"color": self._samp_marker_color, "origin": "samp_catalog"}

        if shape == "circle":
            return Circle(center=(x, y), radius=size, **common)
        if shape == "box":
            return Box(center=(x, y), width_box=size * 2, height_box=size * 2, **common)
        if shape == "ellipse":
            return Ellipse(center=(x, y), semi_major=size, semi_minor=size, **common)
        return Point(center=(x, y), size=int(round(size * 2)), **common)

    def _rebuild_samp_regions_for_frame(self, frame: Frame) -> None:
        """Rebuild SAMP regions for a frame from stored source positions."""
        frame.regions = [
            region for region in frame.regions if getattr(region, "origin", "user") != "samp_catalog"
        ]
        for x, y in self._samp_catalog_sources.get(frame.frame_id, []):
            frame.regions.append(self._build_samp_marker_region(x, y))

    def _refresh_samp_regions(self) -> None:
        """Refresh SAMP catalog marker rendering with current style."""
        for frame in self.frame_manager.frames:
            if frame.frame_id in self._samp_catalog_sources:
                self._rebuild_samp_regions_for_frame(frame)
        self.region.show_frame_regions(self.frame_manager.current_frame)

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
        current_label = next(
            (label for label, value in shape_map.items() if value == self._samp_marker_shape), "Point"
        )
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

    def _show_help_contents(self) -> None:
        """Show help contents dialog."""
        dialog = HelpContentsDialog(self)
        dialog.exec()

    def _show_keyboard_shortcuts(self) -> None:
        """Show keyboard shortcuts dialog."""
        dialog = KeyboardShortcutsDialog(self)
        dialog.exec()

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
            "<p>Licensed under GPL v3</p>",
        )

    def show_about_qt(self) -> None:
        """Show the About Qt dialog."""
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.aboutQt(self, "About Qt")
