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

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal
from PyQt6.QtWidgets import QDialog
from PyQt6.QtGui import QImage, QPixmap, QColor
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QDockWidget,
    QFileDialog,
    QLabel,
    QScrollArea,
    QInputDialog,
    QColorDialog,
)
import numpy as np
from numpy.typing import NDArray
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
from .dialogs.statistics_dialog import StatisticsDialog
from .dialogs.scale_dialog import ScaleDialog
from .dialogs.histogram_dialog import HistogramDialog
from .dialogs.pixel_table_dialog import PixelTableDialog
from .dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from .dialogs.help_contents_dialog import HelpContentsDialog
from .dialogs.export_dialog import ExportDialog
from .dialogs.contour_dialog import ContourDialog
from .dialogs.preferences_dialog import PreferencesDialog
from ..core.fits_handler import FITSHandler
from ..core.wcs_handler import WCSHandler
from ..rendering.scale_algorithms import apply_scale, ScaleAlgorithm, compute_zscale_limits
from ..colormaps.builtin_maps import get_colormap
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
        self.invert_colormap = False
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
        self._show_direction_arrows = True
        self._tile_mode_enabled = False
        self._tile_layout: Optional[dict] = None
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
    
    @property
    def image_data(self):
        """Get current frame's image data."""
        frame = self.frame_manager.current_frame
        return frame.image_data if frame else None
    
    @property
    def wcs_handler(self):
        """Get current frame's WCS handler."""
        frame = self.frame_manager.current_frame
        return frame.wcs_handler if frame else None
    
    @property
    def fits_handler(self):
        """Get a temporary FITS handler for current frame."""
        # For compatibility - create on-demand
        frame = self.frame_manager.current_frame
        if frame and frame.filepath:
            handler = FITSHandler()
            handler.load(str(frame.filepath))
            return handler
        return None

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
        self.menu_bar.action_delete_frame.triggered.connect(self._delete_frame)
        self.menu_bar.action_first_frame.triggered.connect(self._first_frame)
        self.menu_bar.action_prev_frame.triggered.connect(self._prev_frame)
        self.menu_bar.action_next_frame.triggered.connect(self._next_frame)
        self.menu_bar.action_last_frame.triggered.connect(self._last_frame)
        self.menu_bar.action_match_image.triggered.connect(self._match_frames_image)
        self.menu_bar.action_match_wcs.triggered.connect(self._match_frames_wcs)
        self.menu_bar.action_tile_frames.triggered.connect(self._tile_frames)
        self.menu_bar.action_blink_frames.triggered.connect(self._toggle_blink)
        
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
        self.menu_bar.action_cmap_gray.triggered.connect(lambda: self._set_colormap("grey"))
        self.menu_bar.action_cmap_heat.triggered.connect(lambda: self._set_colormap("heat"))
        self.menu_bar.action_cmap_cool.triggered.connect(lambda: self._set_colormap("cool"))
        self.menu_bar.action_cmap_rainbow.triggered.connect(lambda: self._set_colormap("rainbow"))
        self.menu_bar.action_cmap_viridis.triggered.connect(lambda: self._set_colormap("viridis"))
        self.menu_bar.action_cmap_plasma.triggered.connect(lambda: self._set_colormap("plasma"))
        self.menu_bar.action_cmap_inferno.triggered.connect(lambda: self._set_colormap("inferno"))
        self.menu_bar.action_cmap_magma.triggered.connect(lambda: self._set_colormap("magma"))
        self.menu_bar.action_invert_colormap.triggered.connect(self._toggle_invert_colormap)
        
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
        self.menu_bar.action_statistics.triggered.connect(self._show_statistics)
        self.menu_bar.action_histogram.triggered.connect(self._show_histogram)
        self.menu_bar.action_contours.triggered.connect(self._show_contours)
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

        default_colormap = prefs.get("default_colormap", "gray")
        cmap_map = {
            "gray": "grey",
            "grey": "grey",
            "heat": "heat",
            "cool": "cool",
            "rainbow": "rainbow",
            "viridis": "viridis",
            "plasma": "plasma",
            "inferno": "inferno",
            "magma": "magma",
        }
        if default_colormap in cmap_map:
            self._set_colormap(cmap_map[default_colormap])

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
        
        # Load FITS file
        fits_handler = FITSHandler()
        fits_handler.load(filepath)
        image_data = fits_handler.get_data()
        
        # Load WCS if available
        header = fits_handler.get_header()
        wcs_handler = WCSHandler(header)
        
        # Update frame
        frame.filepath = Path(filepath)
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
    
    def _display_image(self) -> None:
        """Display the current frame's image data."""
        if self._tile_mode_enabled:
            self._display_tiled_frames()
            return

        frame = self.frame_manager.current_frame
        if not frame or not frame.has_data:
            return
        
        image_data = frame.image_data
        
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
        cmap = get_colormap(self.current_colormap)

        # Invert colormap if needed
        if self.invert_colormap:
            # Get colormap data and invert
            cmap_data = cmap.colors.copy()
            cmap_data = cmap_data[::-1]  # Reverse the colormap
            from ..colormaps.colormap import Colormap
            cmap = Colormap(f"{self.current_colormap}_inverted", cmap_data)
        
        # Update colorbar
        self.colorbar_widget.set_colormap(
            cmap.colors, adjusted_z1, adjusted_z2, 
            self.current_colormap, self.invert_colormap
        )
        
        if self.using_gpu_rendering:
            def tile_provider(x: int, y: int, w: int, h: int) -> NDArray[np.uint8]:
                y0 = image_data.shape[0] - (y + h)
                y1 = image_data.shape[0] - y
                tile = image_data[y0:y1, x : x + w]
                clipped = np.clip(tile, adjusted_z1, adjusted_z2)
                scaled = apply_scale(clipped, self.current_scale, vmin=adjusted_z1, vmax=adjusted_z2)
                rgb = cmap.apply(scaled)
                return rgb

            self.image_viewer.set_tile_provider(image_data.shape[1], image_data.shape[0], tile_provider)
            self.image_viewer.set_value_source(image_data)
            
            # For GPU mode, pre-render a small version for panner/magnifier
            clipped_full = np.clip(image_data, adjusted_z1, adjusted_z2)
            scaled_full = apply_scale(clipped_full, self.current_scale, vmin=adjusted_z1, vmax=adjusted_z2)
            rgb_full = cmap.apply(scaled_full)
            display_rgb = np.ascontiguousarray(np.flipud(rgb_full))
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
            self.panner_panel.set_image(display_rgb)
            self._update_panner_view_rect()
        
        # Update magnifier panel with RGB data (DS9 style)
        if hasattr(self, 'magnifier_panel'):
            self.magnifier_panel.set_image(display_rgb)
        
        # Update zoom display
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self._update_bin_menu_checks(getattr(frame, "bin_factor", 1))
        self._update_regions_for_frame(frame)
        self._sync_frame_view_state()
        if self._contour_settings is not None:
            self._update_contours()
        self._update_direction_arrows()

    def _render_frame_rgb(self, frame: Frame) -> Optional[NDArray[np.uint8]]:
        """Render a frame to RGB using its own display settings."""
        if not frame.has_data:
            return None

        image_data = frame.image_data
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

        cmap = get_colormap(frame.colormap)
        if frame.invert_colormap:
            cmap_data = cmap.colors.copy()[::-1]
            from ..colormaps.colormap import Colormap
            cmap = Colormap(f"{frame.colormap}_inverted", cmap_data)

        clipped = np.clip(image_data, adjusted_z1, adjusted_z2)
        scaled = apply_scale(clipped, frame.scale, vmin=adjusted_z1, vmax=adjusted_z2)
        return cmap.apply(scaled)

    def _display_tiled_frames(self) -> bool:
        """Render all loaded frames in a tiled grid."""
        rgb_frames: list[NDArray[np.uint8]] = []
        frame_indices: list[int] = []
        for frame_index, frame in enumerate(self.frame_manager.frames):
            rgb = self._render_frame_rgb(frame)
            if rgb is not None:
                rgb_frames.append(rgb)
                frame_indices.append(frame_index)

        if not rgb_frames:
            self._tile_layout = None
            self.statusBar().showMessage("No loaded frames to tile", 2000)
            return False

        count = len(rgb_frames)
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
                y0 = tiled_h - (y + h)
                y1 = tiled_h - y
                return tiled_rgb[y0:y1, x : x + w]

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
    
    def _set_colormap(self, colormap: str) -> None:
        """
        Set the colormap.
        
        Args:
            colormap: Name of the colormap to use.
        """
        self.current_colormap = colormap
        self._persist_frame_view_state()
        
        # Update menu checkboxes
        self.menu_bar.action_cmap_gray.setChecked(colormap == "grey")
        self.menu_bar.action_cmap_heat.setChecked(colormap == "heat")
        self.menu_bar.action_cmap_cool.setChecked(colormap == "cool")
        self.menu_bar.action_cmap_rainbow.setChecked(colormap == "rainbow")
        self.menu_bar.action_cmap_viridis.setChecked(colormap == "viridis")
        self.menu_bar.action_cmap_plasma.setChecked(colormap == "plasma")
        self.menu_bar.action_cmap_inferno.setChecked(colormap == "inferno")
        self.menu_bar.action_cmap_magma.setChecked(colormap == "magma")
        
        # Update button bar
        cmap_name_map = {
            "grey": "Gray",
            "heat": "Heat",
            "cool": "Cool",
            "rainbow": "Rainbow",
        }
        if colormap in cmap_name_map:
            self.button_bar.set_colormap(cmap_name_map[colormap])
        
        # Redisplay with new colormap
        if self.image_data is not None:
            self._display_image()
            self.statusBar().showMessage(f"Colormap: {colormap}", 2000)

    def _update_bin_menu_checks(self, factor: int) -> None:
        """Update Bin menu checkmarks based on current factor."""
        self.menu_bar.action_bin_1.setChecked(factor == 1)
        self.menu_bar.action_bin_2.setChecked(factor == 2)
        self.menu_bar.action_bin_4.setChecked(factor == 4)
        self.menu_bar.action_bin_8.setChecked(factor == 8)

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
        if self.image_data is None:
            self.statusBar().showMessage("No image loaded", 2000)
            return
        
        dialog = StatisticsDialog(self.image_data, self)
        dialog.exec()
    
    def _show_histogram(self) -> None:
        """Show histogram dialog."""
        if self.image_data is None:
            self.statusBar().showMessage("No image loaded", 2000)
            return
        
        dialog = HistogramDialog(self.image_data, self)
        dialog.exec()
    
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
        self.image_viewer.set_contrast_brightness(contrast, brightness)
        
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
        self._update_contours()

    def _update_contours(self) -> None:
        """Recompute contours for current image."""
        if self.image_data is None or self._contour_settings is None:
            if hasattr(self.image_viewer, "clear_contours"):
                self.image_viewer.clear_contours()
            return

        settings = self._contour_settings
        smooth_sigma = settings.get("smooth_sigma", 1.0) if settings.get("smooth") else None
        generator = ContourGenerator(self.image_data, smooth=smooth_sigma)

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
        if self.image_data is None:
            self.statusBar().showMessage("No image loaded", 2000)
            return
        
        # Use image center as default
        height, width = self.image_data.shape
        x, y = width // 2, height // 2
        
        dialog = PixelTableDialog(self.image_data, x, y, size=11, parent=self)
        dialog.exec()
    
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

        cmap = get_colormap(self.current_colormap)
        if self.invert_colormap:
            cmap_data = cmap.colors.copy()
            cmap_data = cmap_data[::-1]
            from ..colormaps.colormap import Colormap
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
    
    def _new_frame(self) -> None:
        """Create a new empty frame."""
        frame = self.frame_manager.new_frame()
        self.z1 = None
        self.z2 = None
        if hasattr(self.image_viewer, "reset_contrast_brightness"):
            self.image_viewer.reset_contrast_brightness()
        self._update_frame_display()
        self.statusBar().showMessage(f"Created {frame.filename}", 2000)
    
    def _delete_frame(self) -> None:
        """Delete current frame."""
        current_frame = self.frame_manager.current_frame
        current_frame_id = current_frame.frame_id if current_frame else None
        if self.frame_manager.delete_frame():
            if current_frame_id is not None:
                self._samp_catalog_sources.pop(current_frame_id, None)
            if self.frame_manager.num_frames <= 1 and self._blink_timer.isActive():
                self._blink_timer.stop()
                self.menu_bar.action_blink_frames.blockSignals(True)
                self.menu_bar.action_blink_frames.setChecked(False)
                self.menu_bar.action_blink_frames.blockSignals(False)
            self.z1 = None
            self.z2 = None
            if hasattr(self.image_viewer, "reset_contrast_brightness"):
                self.image_viewer.reset_contrast_brightness()
            self._update_frame_display()
            frame_info = f"Frame {self.frame_manager.current_index + 1}/{self.frame_manager.num_frames}"
            self.statusBar().showMessage(f"Deleted frame, now at {frame_info}", 2000)
        else:
            self.statusBar().showMessage("Cannot delete last frame", 2000)
    
    def _first_frame(self) -> None:
        """Go to first frame."""
        self.frame_manager.first_frame()
        self.z1 = None
        self.z2 = None
        if hasattr(self.image_viewer, "reset_contrast_brightness"):
            self.image_viewer.reset_contrast_brightness()
        self._update_frame_display()
    
    def _prev_frame(self) -> None:
        """Go to previous frame."""
        self.frame_manager.prev_frame()
        self.z1 = None
        self.z2 = None
        if hasattr(self.image_viewer, "reset_contrast_brightness"):
            self.image_viewer.reset_contrast_brightness()
        self._update_frame_display()
    
    def _next_frame(self) -> None:
        """Go to next frame."""
        self.frame_manager.next_frame()
        self.z1 = None
        self.z2 = None
        if hasattr(self.image_viewer, "reset_contrast_brightness"):
            self.image_viewer.reset_contrast_brightness()
        self._update_frame_display()
    
    def _last_frame(self) -> None:
        """Go to last frame."""
        self.frame_manager.last_frame()
        self.z1 = None
        self.z2 = None
        if hasattr(self.image_viewer, "reset_contrast_brightness"):
            self.image_viewer.reset_contrast_brightness()
        self._update_frame_display()
    
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
        if self._tile_mode_enabled:
            if not self._display_tiled_frames():
                self._tile_mode_enabled = False
                self.menu_bar.action_tile_frames.blockSignals(True)
                self.menu_bar.action_tile_frames.setChecked(False)
                self.menu_bar.action_tile_frames.blockSignals(False)
                return
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
        if self.frame_manager.num_frames <= 1:
            self._blink_timer.stop()
            self.menu_bar.action_blink_frames.blockSignals(True)
            self.menu_bar.action_blink_frames.setChecked(False)
            self.menu_bar.action_blink_frames.blockSignals(False)
            return
        self.frame_manager.next_frame()
        self._update_frame_display()

    def _toggle_blink(self, checked: bool) -> None:
        """Start/stop frame blinking."""
        if checked:
            if self._tile_mode_enabled:
                self._tile_mode_enabled = False
                self.menu_bar.action_tile_frames.blockSignals(True)
                self.menu_bar.action_tile_frames.setChecked(False)
                self.menu_bar.action_tile_frames.blockSignals(False)
                self._update_frame_display()
            if self.frame_manager.num_frames <= 1:
                self.menu_bar.action_blink_frames.blockSignals(True)
                self.menu_bar.action_blink_frames.setChecked(False)
                self.menu_bar.action_blink_frames.blockSignals(False)
                self.statusBar().showMessage("Need at least two frames to blink", 2000)
                return
            self._blink_timer.start(self._blink_timer.interval())
            self.statusBar().showMessage("Blinking started", 2000)
        else:
            self._blink_timer.stop()
            self.statusBar().showMessage("Blinking stopped", 2000)

    def _tile_frames(self, checked: bool) -> None:
        """Toggle tiled display of loaded frames."""
        if checked:
            if self._blink_timer.isActive():
                self._blink_timer.stop()
                self.menu_bar.action_blink_frames.blockSignals(True)
                self.menu_bar.action_blink_frames.setChecked(False)
                self.menu_bar.action_blink_frames.blockSignals(False)
            self._tile_mode_enabled = True
            if not self._display_tiled_frames():
                self._tile_mode_enabled = False
                self.menu_bar.action_tile_frames.blockSignals(True)
                self.menu_bar.action_tile_frames.setChecked(False)
                self.menu_bar.action_tile_frames.blockSignals(False)
                return
            self.statusBar().showMessage("Frame tiling enabled", 2000)
        else:
            self._tile_mode_enabled = False
            self._tile_layout = None
            self._update_frame_display()
            self.statusBar().showMessage("Frame tiling disabled", 2000)

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
        frame.colormap = self.current_colormap
        frame.scale = self.current_scale
        frame.invert_colormap = self.invert_colormap
        frame.z1 = self.z1
        frame.z2 = self.z2
        frame.zoom = self.image_viewer.get_zoom()
        frame.contrast, frame.brightness = self.image_viewer.get_contrast_brightness()
        if self.using_gpu_rendering and hasattr(self.image_viewer, "gl_canvas"):
            frame.pan_x, frame.pan_y = self.image_viewer.gl_canvas.pan_offset

    def _apply_frame_view_state(self, frame: Frame) -> None:
        """Apply stored display settings from the frame."""
        self.current_colormap = frame.colormap
        self.current_scale = frame.scale
        self.invert_colormap = frame.invert_colormap
        self.z1 = frame.z1
        self.z2 = frame.z2
        self.menu_bar.action_cmap_gray.setChecked(self.current_colormap == "grey")
        self.menu_bar.action_cmap_heat.setChecked(self.current_colormap == "heat")
        self.menu_bar.action_cmap_cool.setChecked(self.current_colormap == "cool")
        self.menu_bar.action_cmap_rainbow.setChecked(self.current_colormap == "rainbow")
        self.menu_bar.action_cmap_viridis.setChecked(self.current_colormap == "viridis")
        self.menu_bar.action_cmap_plasma.setChecked(self.current_colormap == "plasma")
        self.menu_bar.action_cmap_inferno.setChecked(self.current_colormap == "inferno")
        self.menu_bar.action_cmap_magma.setChecked(self.current_colormap == "magma")
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
        if hasattr(self.image_viewer, "set_contrast_brightness"):
            self.image_viewer.set_contrast_brightness(frame.contrast, frame.brightness)
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
