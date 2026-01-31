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

from typing import Optional, TYPE_CHECKING
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap, QColor
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QDockWidget,
    QFileDialog,
    QLabel,
    QScrollArea,
)
import numpy as np
from numpy.typing import NDArray
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
from .widgets.region_overlay import RegionMode
from .dialogs.statistics_dialog import StatisticsDialog
from .dialogs.histogram_dialog import HistogramDialog
from .dialogs.pixel_table_dialog import PixelTableDialog
from .dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from .dialogs.help_contents_dialog import HelpContentsDialog
from .dialogs.export_dialog import ExportDialog
from .dialogs.preferences_dialog import PreferencesDialog
from ..core.fits_handler import FITSHandler
from ..core.wcs_handler import WCSHandler
from ..rendering.scale_algorithms import apply_scale, ScaleAlgorithm, compute_zscale_limits
from ..colormaps.builtin_maps import get_colormap
from ..regions.region_parser import RegionParser
from ..frames.simple_frame_manager import FrameManager, Frame
from ..utils.preferences import Preferences

if TYPE_CHECKING:
    from ncrads9.utils.config import Config


class MainWindow(QMainWindow):
    """Main application window for NCRADS9."""

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

        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_dock_widgets()
        self._setup_status_bar()
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
        self.setMenuBar(self.menu_bar)
        
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
        
        # Color menu
        self.menu_bar.action_cmap_gray.triggered.connect(lambda: self._set_colormap("grey"))
        self.menu_bar.action_cmap_heat.triggered.connect(lambda: self._set_colormap("heat"))
        self.menu_bar.action_cmap_cool.triggered.connect(lambda: self._set_colormap("cool"))
        self.menu_bar.action_cmap_rainbow.triggered.connect(lambda: self._set_colormap("rainbow"))
        # Note: viridis not in DS9 builtin maps, skip connection
        self.menu_bar.action_invert_colormap.triggered.connect(self._toggle_invert_colormap)
        
        # Region menu (stubs)
        self.menu_bar.action_region_load.triggered.connect(self._load_regions)
        self.menu_bar.action_region_save.triggered.connect(lambda: self.statusBar().showMessage("Region saving not implemented", 2000))
        
        # WCS menu - connect all coordinate system options
        self.menu_bar.action_wcs_fk5.triggered.connect(lambda: self._set_wcs_system("fk5"))
        self.menu_bar.action_wcs_fk4.triggered.connect(lambda: self._set_wcs_system("fk4"))
        self.menu_bar.action_wcs_icrs.triggered.connect(lambda: self._set_wcs_system("icrs"))
        self.menu_bar.action_wcs_galactic.triggered.connect(lambda: self._set_wcs_system("galactic"))
        self.menu_bar.action_wcs_ecliptic.triggered.connect(lambda: self._set_wcs_system("ecliptic"))
        self.menu_bar.action_wcs_sexagesimal.triggered.connect(lambda: self._set_wcs_format("sexagesimal"))
        self.menu_bar.action_wcs_degrees.triggered.connect(lambda: self._set_wcs_format("degrees"))
        
        # Analysis menu - connect all tools
        self.menu_bar.action_statistics.triggered.connect(self._show_statistics)
        self.menu_bar.action_histogram.triggered.connect(self._show_histogram)
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

    def _setup_central_widget(self) -> None:
        """Set up the central widget."""
        # Create scroll area for image display
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)  # Allow widget to use full viewport
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
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
        viewer.contrast_changed.connect(self._on_contrast_changed)
        viewer.region_created.connect(self._on_region_created)
        viewer.region_selected.connect(self._on_region_selected)
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
        
        # Update window title
        filename = Path(filepath).name
        frame_info = f"Frame {self.frame_manager.current_index + 1}/{self.frame_manager.num_frames}"
        self.setWindowTitle(f"NCRADS9 - {filename} [{frame_info}]")
        
        # Display the image
        self._display_image()
        
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
                tile = image_data[y : y + h, x : x + w]
                clipped = np.clip(tile, adjusted_z1, adjusted_z2)
                scaled = apply_scale(clipped, self.current_scale, vmin=adjusted_z1, vmax=adjusted_z2)
                return cmap.apply(scaled)

            self.image_viewer.set_tile_provider(image_data.shape[1], image_data.shape[0], tile_provider)
            self.image_viewer.set_value_source(image_data)
        else:
            # Clip and scale the data
            clipped = np.clip(image_data, adjusted_z1, adjusted_z2)
            scaled = apply_scale(clipped, self.current_scale, vmin=adjusted_z1, vmax=adjusted_z2)
            rgb = cmap.apply(scaled)

            # Convert to QImage
            height, width = rgb.shape[:2]
            bytes_per_line = 3 * width
            qimage = QImage(rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            
            # Create pixmap and display
            pixmap = QPixmap.fromImage(qimage)
            self.image_viewer.set_image(pixmap)
        
        # Update zoom display
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self._update_bin_menu_checks(getattr(frame, "bin_factor", 1))
    
    def _set_scale(self, scale: ScaleAlgorithm) -> None:
        """
        Set the image scaling algorithm.
        
        Args:
            scale: The scaling algorithm to use.
        """
        self.current_scale = scale
        
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
        
        # Update menu checkboxes
        self.menu_bar.action_cmap_gray.setChecked(colormap == "grey")
        self.menu_bar.action_cmap_heat.setChecked(colormap == "heat")
        self.menu_bar.action_cmap_cool.setChecked(colormap == "cool")
        self.menu_bar.action_cmap_rainbow.setChecked(colormap == "rainbow")
        
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

        self._update_bin_menu_checks(factor)
        self._display_image()
        self.status_bar.update_image_info(frame.image_data.shape[1], frame.image_data.shape[0])
        self.statusBar().showMessage(f"Binning: {factor}x{factor}", 2000)
    
    def _zoom_in(self) -> None:
        """Zoom in."""
        self.image_viewer.zoom_in()
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self.statusBar().showMessage("Zoomed in", 1000)
    
    def _zoom_out(self) -> None:
        """Zoom out."""
        self.image_viewer.zoom_out()
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self.statusBar().showMessage("Zoomed out", 1000)
    
    def _zoom_fit(self) -> None:
        """Zoom to fit window."""
        self.image_viewer.zoom_fit(self.scroll_area.viewport().size())
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self.statusBar().showMessage("Zoom to fit", 1000)
    
    def _zoom_actual(self) -> None:
        """Zoom to 1:1."""
        self.image_viewer.zoom_actual()
        self.status_bar.update_zoom(self.image_viewer.get_zoom())
        self.statusBar().showMessage("Zoom 1:1", 1000)
    
    def _on_mouse_moved(self, x: int, y: int) -> None:
        """Handle mouse movement over image."""
        if self.image_data is None:
            return

        self._last_mouse_pos = (x, y)
        
        # Update pixel coordinates
        self.status_bar.update_pixel_coords(x, y)
        
        # Update pixel value
        if 0 <= y < self.image_data.shape[0] and 0 <= x < self.image_data.shape[1]:
            value = self.image_data[y, x]
            self.status_bar.update_pixel_value(value)
        
        # Update WCS coordinates if available
        if self.wcs_handler and self.wcs_handler.is_valid:
            self._update_wcs_display(x, y)
    
    def _on_contrast_changed(self, contrast: float, brightness: float) -> None:
        """Handle contrast/brightness change from mouse drag."""
        self._display_image()
        self.statusBar().showMessage(f"Contrast: {contrast:.2f}, Brightness: {brightness:.2f}", 1000)
    
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
                self.statusBar().showMessage(f"Zoom: {zoom_val}x", 1000)
            except ValueError:
                # Handle fractions like "1/2"
                if "/" in level:
                    parts = level.split("/")
                    zoom_val = float(parts[0]) / float(parts[1])
                    self.image_viewer.zoom_to(zoom_val)
                    self.status_bar.update_zoom(zoom_val)
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
        }
        region_mode = mode_map.get(mode, RegionMode.NONE)
        self.image_viewer.set_region_mode(region_mode)
        self.statusBar().showMessage(f"Region mode: {mode}", 2000)
    
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
            self.image_viewer.reset_contrast_brightness()
            self._display_image()
            self.statusBar().showMessage("Reset to ZScale limits", 2000)
    
    def _scale_minmax(self) -> None:
        """Set scale limits to data min/max."""
        if self.image_data is not None:
            self.z1 = float(np.nanmin(self.image_data))
            self.z2 = float(np.nanmax(self.image_data))
            self.image_viewer.reset_contrast_brightness()
            self._display_image()
            self.statusBar().showMessage(f"MinMax: {self.z1:.4g} to {self.z2:.4g}", 2000)
    
    def _toggle_invert_colormap(self, checked: bool) -> None:
        """Toggle colormap inversion."""
        self.invert_colormap = checked
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
                regions = parser.parse_file(filepath)
                self.statusBar().showMessage(f"Loaded {len(regions)} regions from {filepath}", 3000)
                # TODO: Display regions on image
            except Exception as e:
                self.statusBar().showMessage(f"Error loading regions: {e}", 3000)
    
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
    
    def _set_wcs_format(self, format_type: str) -> None:
        """Set WCS format (sexagesimal or degrees)."""
        self.current_wcs_format = format_type
        self.menu_bar.action_wcs_sexagesimal.setChecked(format_type == "sexagesimal")
        self.menu_bar.action_wcs_degrees.setChecked(format_type == "degrees")
        self.statusBar().showMessage(f"WCS format: {format_type}", 2000)
        if self._last_mouse_pos is not None and self.wcs_handler and self.wcs_handler.is_valid:
            self._update_wcs_display(*self._last_mouse_pos)

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
        frame_info = f"Frame {self.frame_manager.current_index + 1}/{self.frame_manager.num_frames}"
        self.setWindowTitle(f"NCRADS9 [{frame_info}]")
        self.statusBar().showMessage(f"Created {frame.filename}", 2000)
    
    def _delete_frame(self) -> None:
        """Delete current frame."""
        if self.frame_manager.delete_frame():
            self._display_image()
            frame = self.frame_manager.current_frame
            frame_info = f"Frame {self.frame_manager.current_index + 1}/{self.frame_manager.num_frames}"
            if frame and frame.filepath:
                self.setWindowTitle(f"NCRADS9 - {frame.filepath.name} [{frame_info}]")
            else:
                self.setWindowTitle(f"NCRADS9 [{frame_info}]")
            self.statusBar().showMessage(f"Deleted frame, now at {frame_info}", 2000)
        else:
            self.statusBar().showMessage("Cannot delete last frame", 2000)
    
    def _first_frame(self) -> None:
        """Go to first frame."""
        self.frame_manager.first_frame()
        self._display_image()
        self._update_frame_title()
    
    def _prev_frame(self) -> None:
        """Go to previous frame."""
        self.frame_manager.prev_frame()
        self._display_image()
        self._update_frame_title()
    
    def _next_frame(self) -> None:
        """Go to next frame."""
        self.frame_manager.next_frame()
        self._display_image()
        self._update_frame_title()
    
    def _last_frame(self) -> None:
        """Go to last frame."""
        self.frame_manager.last_frame()
        self._display_image()
        self._update_frame_title()
    
    def _update_frame_title(self) -> None:
        """Update window title with current frame info."""
        frame = self.frame_manager.current_frame
        frame_info = f"Frame {self.frame_manager.current_index + 1}/{self.frame_manager.num_frames}"
        if frame and frame.filepath:
            self.setWindowTitle(f"NCRADS9 - {frame.filepath.name} [{frame_info}]")
        else:
            self.setWindowTitle(f"NCRADS9 [{frame_info}]")
        self.statusBar().showMessage(frame_info, 2000)
    
    def _on_region_created(self, region) -> None:
        """Handle region creation."""
        frame = self.frame_manager.current_frame
        if frame:
            frame.regions.append(region)
        self.statusBar().showMessage(f"Created {region.mode.value} region", 2000)
    
    def _on_region_selected(self, region) -> None:
        """Handle region selection."""
        self.statusBar().showMessage(f"Selected {region.mode.value} region", 2000)
    
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
