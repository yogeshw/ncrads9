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

from typing import TYPE_CHECKING, Optional

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QKeyEvent
from PyQt6.QtWidgets import (
    QMainWindow,
    QScrollArea,
    QWidget,
)

from ..colormaps.colormap import Colormap
from ..communication.samp import SAMPClient
from ..coordinates.coord_system import CoordinateContext
from ..core.fits_handler import FITSHandler
from ..frames.blink_controller import (
    DEFAULT_BLINK_INTERVAL_MS,
    DEFAULT_FADE_INTERVAL_MS,
    BlinkController,
)
from ..frames.frame_manager import FrameManager
from ..frames.tile_layout import TileLayout
from ..rendering.scale_algorithms import ScaleAlgorithm
from ..utils.preferences import Preferences
from .button_bar import ButtonBar
from .controllers.analysis import AnalysisController
from .controllers.base import Controller
from .controllers.color import ColorController
from .controllers.edit import EditController
from .controllers.file import FileController
from .controllers.frame import FrameController
from .controllers.help import HelpController
from .controllers.region import RegionController
from .controllers.scale import ScaleController
from .controllers.view import ViewController
from .controllers.vo import VOController
from .controllers.wcs import WCSController
from .controllers.zoom import ZoomController
from .display import DisplayPipeline
from .layout.shell import WindowShell
from .layout.view_state import ViewState
from .menu_bar import MenuBar
from .panels.horizontal_graph import HorizontalGraph
from .panels.info_panel import InfoPanel
from .panels.magnifier import MagnifierPanel
from .panels.panner import PannerPanel
from .panels.vertical_graph import VerticalGraph
from .status_bar import StatusBar
from .toolbar import MainToolbar
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
        # Which panels are shown and how they are arranged, at DS9's defaults.
        self.view_state = ViewState()
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
        # DS9 draws its N/E compass in the panner, not over the data, so the
        # image overlay is opt-in via WCS -> Show Direction Arrows.
        self._show_direction_arrows = False
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
        self.samp_table_received.connect(self.vo.handle_samp_table)

        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_status_bar()
        self.view.apply()
        self.vo.init_samp()
        self.vo.sync_samp_menu()
        self.edit.apply_preferences(self.edit.preferences_dict(), persist=False, show_message=False)
        self.frame_controller.refresh_menu_items()

    @property
    def image_data(self):
        """Get current frame's image data."""
        frame = self.frame_manager.current_frame
        if not frame:
            return None
        if frame.frame_type == "rgb":
            return self.display.active_channel_data(frame)
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

    def _setup_controllers(self) -> None:
        """Create the per-menu controllers.

        Runs before `_setup_menu_bar`, because that calls each controller's
        `connect()` to wire its own actions. See `ui/controllers/base.py` for
        why controllers hold a reference to the window.
        """
        # Not a menu controller, but extracted for the same reason: the
        # render pipeline is 600 lines of behaviour that nothing could test
        # without building the whole window.
        self.display = DisplayPipeline(self)

        self.analysis = AnalysisController(self)
        self.color = ColorController(self)
        # Named `frame_controller`: `self.frame` would shadow nothing on the
        # window, but reads as a Frame everywhere else in the codebase.
        self.frame_controller = FrameController(self)
        self.help = HelpController(self)
        self.edit = EditController(self)
        self.file = FileController(self)
        self.region = RegionController(self)
        self.view = ViewController(self)
        self.vo = VOController(self)
        self.zoom = ZoomController(self)
        self.scale = ScaleController(self)
        self.wcs = WCSController(self)

        #: Every controller, for broadcasting `sync()` on a frame change.
        self.controllers: tuple[Controller, ...] = (
            self.analysis,
            self.color,
            self.edit,
            self.frame_controller,
            self.help,
            self.file,
            self.region,
            self.scale,
            self.view,
            self.vo,
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

        # VO menu
        self.vo.connect()

        # WCS menu
        self.wcs.connect()

        # Analysis and Bin menus
        self.analysis.connect()

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
        self.help.connect()

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

        self._setup_panels()
        self.shell = WindowShell(
            info_panel=self.info_panel,
            panner=self.panner_panel,
            magnifier=self.magnifier_panel,
            button_bar=self.button_bar,
            image_area=self.scroll_area,
            colorbar=self.colorbar_widget,
            graph_horizontal=self.horizontal_graph,
            graph_vertical=self.vertical_graph,
            parent=self,
        )
        self.setCentralWidget(self.shell)

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

    def _setup_panels(self) -> None:
        """Create the panels the shell arranges.

        These were `QDockWidget`s until M3: draggable, tearable, and in the
        panner's and magnifier's case a dock nested inside another dock, so
        each carried two title bars. DS9 has no floating panels -- see
        `ui/layout/shell.py`.
        """
        self.info_panel = InfoPanel(self)

        self.button_bar = ButtonBar(self.menu_bar, self)
        self.button_bar.command.connect(self._on_button_bar_command)

        self.colorbar_widget = ColorbarWidget(self)

        self.panner_panel = PannerPanel(self)
        self.panner_panel.pan_to.connect(self.zoom.on_panner_pan)

        self.magnifier_panel = MagnifierPanel(self)

        self.horizontal_graph = HorizontalGraph(self)
        self.vertical_graph = VerticalGraph(self)

    #: Button-bar command family -> the controller method that services it.
    #: Buttons whose menu entry is a single `QAction` trigger that action
    #: directly and never reach here; these are the ones with no such entry.
    BUTTON_COMMANDS: dict[str, str] = {
        "zoom": "on_button_bar_zoom",
        "region": "on_button_bar_mode",
    }

    def _on_button_bar_command(self, command: str) -> None:
        """Dispatch a button-bar command id of the form "family:label"."""
        family, _, label = command.partition(":")
        controller = {"zoom": self.zoom, "region": self.region}.get(family)
        handler = self.BUTTON_COMMANDS.get(family)
        if controller is None or handler is None:
            self.statusBar().showMessage(f"Unhandled button: {command}", 2000)
            return
        getattr(controller, handler)(label)

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
            self.display.display()

    def _apply_background_color(self, color_hex: str) -> None:
        """Apply background color to the viewer."""
        # Both viewer backends expose set_background_color, so this does not
        # depend on which one is active. (This was previously an if/elif whose
        # two branches were identical, making the GPU test dead.)
        if hasattr(self.image_viewer, "set_background_color"):
            self.image_viewer.set_background_color(color_hex)

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
        self.view.update_cursor(x, y)
        if hasattr(self, "horizontal_graph") and self.horizontal_graph.isVisible():
            self.horizontal_graph.update_cursor_position(x, row)
        if hasattr(self, "vertical_graph") and self.vertical_graph.isVisible():
            self.vertical_graph.update_cursor_position(x, row)
        self.analysis.refresh_overlays()

    def _on_image_clicked(self, x: int, y: int, button: int) -> None:
        """Handle image clicks (used for tiled frame selection)."""
        if not self._tile_mode_enabled or button != int(Qt.MouseButton.LeftButton.value):
            return
        if self.frame_controller.select_tile_at(x, y):
            self.display.display_tiled()
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

    def closeEvent(self, event) -> None:
        """Disconnect SAMP client on close."""
        if self._samp_client is not None:
            self._samp_client.disconnect()
            self._samp_connected = False
        super().closeEvent(event)
