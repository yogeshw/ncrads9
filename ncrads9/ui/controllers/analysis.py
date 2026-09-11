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
The Analysis menu: block, smooth, contours, grid, mask and the analysis tools.

DS9's Analysis menu is where most of the remaining functional gap lives
(PLAN.md §5.12). Present and working here: contours, smoothing, blocking,
statistics, histogram, radial profile, pixel table and name resolution.

Absent, with the milestone that adds each:

* A real WCS graticule. What `set_grid` toggles today is a *pixel* grid drawn
  in image coordinates by `contour_overlay`, not DS9's coordinate graticule
  with curved lines, tick marks and sexagesimal labels (PLAN.md §3.5, M7-10).
* Mask *files*, with blend mode, colour and value range; only thresholding
  exists (M7-24).
* The catalog tool, image servers, archives and footprint servers (M8).

`set_bin` is knowingly misnamed. DS9's Bin builds an image from a FITS bin
table by binning two columns; this block-averages an image, which is DS9's
Block. The two menus therefore run the same code today. M5-14 to M5-19
separate them.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from numpy.typing import NDArray
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QPushButton,
    QVBoxLayout,
)
from scipy import ndimage

from ...analysis import contour_file
from ...analysis import mask as mask_module
from ...analysis.contour import ContourGenerator
from ...analysis.mask import MaskSettings
from ...analysis.pixel_table import PixelTable
from ...analysis.plot import PlotState, PlotStyle
from ...analysis.radial_profile import RadialProfile
from ...analysis.smooth import (
    boxcar_smooth,
    elliptical_gaussian_smooth,
    gaussian_smooth,
    tophat_smooth,
)
from ...frames.frame import Frame
from ...grid import GridConfig, GridRenderer
from ..dialogs.contour_dialog import ContourDialog
from ..dialogs.grid_dialog import GridDialog
from ..dialogs.histogram_dialog import HistogramDialog
from ..dialogs.mask_dialog import MaskDialog
from ..dialogs.pixel_table_dialog import PixelTableDialog
from ..dialogs.plot_window import PlotWindow
from ..dialogs.smooth_dialog import SmoothDialog
from ..dialogs.statistics_dialog import StatisticsDialog
from ..menu_bar import BLOCK_FACTORS
from .base import Controller

#: The filter DS9's contour Open and Save offer.
CONTOUR_FILTER = "Contour Files (*.ctr *.con);;All Files (*)"

#: The block factors the menu offers, imported so the two cannot diverge.


class AnalysisController(Controller):
    """Owns the Analysis and Bin menus."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: Open plot windows. A modeless window nothing holds a reference to
        #: is collected the moment it is shown. Per instance, not per class:
        #: a shared set would outlive the window that opened them.
        # A list, not a set: DS9's `plot` access point acts on "the last
        # plot created", which needs an order.
        self._plots: list[PlotWindow] = []
        #: Which plot `xpaset ds9 plot ...` acts on, DS9's `plot current`.
        self._current_plot: PlotWindow | None = None

        #: DS9's mask layer: a second FITS image painted over the first.
        #: `None` until one is opened, which is what "no mask" means. On
        #: the controller rather than the window, which the M2 guard caps
        #: at 600 lines.
        self.mask_layer = None
        self.mask_path: str | None = None
        self.mask_settings = MaskSettings()

        #: What the coordinate grid looks like, and the renderer that works
        #: out where its lines go.
        #: The pixel table, while it is open. DS9's follows the cursor.
        self.pixel_table = None
        self.grid_config = GridConfig()
        self._grid_renderer = GridRenderer(config=self.grid_config)

    def connect(self) -> None:
        """Wire the Analysis and Bin menus."""
        menu = self.menu

        menu.action_pixel_table.triggered.connect(self.show_pixel_table)
        menu.action_name_resolution.triggered.connect(self.resolve_object_name)
        menu.action_statistics.triggered.connect(self.show_statistics)
        menu.action_histogram.triggered.connect(self.show_histogram)
        menu.action_radial_profile.triggered.connect(self.show_radial_profile)

        menu.action_mask_params.triggered.connect(self.show_mask_dialog)
        menu.action_graph_params.triggered.connect(self.show_graph_dialog)

        menu.action_contours.triggered.connect(self.set_contours)
        menu.action_contour_params.triggered.connect(self.show_contour_dialog)
        menu.action_coordinate_grid.triggered.connect(self.set_grid)
        menu.action_coordinate_grid_params.triggered.connect(self.show_grid_dialog)

        menu.action_block_in.triggered.connect(self.block_in)
        menu.action_block_out.triggered.connect(self.block_out)
        menu.action_block_fit.triggered.connect(self.block_fit)
        menu.action_block_params.triggered.connect(self.show_block_dialog)
        for factor in BLOCK_FACTORS:
            getattr(menu, f"action_block_{factor}").triggered.connect(
                lambda _checked=False, f=factor: self.set_block_factor(f)
            )

        menu.action_smooth.triggered.connect(self.set_smooth)
        menu.action_smooth_params.triggered.connect(self.show_smooth_dialog)

        menu.action_analysis_command_log.triggered.connect(self.set_command_log)
        menu.action_plot_tool_line.triggered.connect(
            lambda _checked=False: self.open_plot_tool(PlotStyle.LINE)
        )
        menu.action_plot_tool_bar.triggered.connect(lambda _checked=False: self.open_plot_tool(PlotStyle.BAR))

        menu.action_web_browser.triggered.connect(self.open_web_browser)

    def sync_block_menu(self, factor: int) -> None:
        """Tick the Block entry matching the current factor."""
        for value in BLOCK_FACTORS:
            getattr(self.menu, f"action_block_{value}").setChecked(value == factor)

    def set_block_factor(self, factor: int) -> None:
        """Set the display block factor from the Block menu.

        Args:
            factor: The wanted factor. Snapped to the nearest of
                `BLOCK_FACTORS`, as DS9's menu offers only those.
        """
        nearest = min(BLOCK_FACTORS, key=lambda item: abs(item - factor))
        self.set_block(nearest)
        self.log_command(f"block {nearest}")

    def block_in(self) -> None:
        """Halve the block factor, stopping at one."""
        self.set_block_factor(self._step_block(-1))

    def block_out(self) -> None:
        """Double the block factor, stopping at the largest preset."""
        self.set_block_factor(self._step_block(1))

    def _step_block(self, direction: int) -> int:
        """The preset one step from the current factor."""
        frame = self.frames.current_frame
        current = getattr(frame, "block_factor", 1) if frame else 1
        if current not in BLOCK_FACTORS:
            current = min(BLOCK_FACTORS, key=lambda item: abs(item - current))
        index = BLOCK_FACTORS.index(current) + direction
        return BLOCK_FACTORS[max(0, min(len(BLOCK_FACTORS) - 1, index))]

    def block_fit(self) -> None:
        """Choose a block factor that roughly fits image into viewport."""
        frame = self.frames.current_frame
        if not frame or frame.original_image_data is None:
            if frame and frame.image_data is not None:
                frame.original_image_data = frame.image_data
            else:
                self.status("No image loaded", 2000)
                return
        if frame.original_image_data is None:
            self.status("No image loaded", 2000)
            return

        height, width = frame.original_image_data.shape[:2]
        viewport = self.window._effective_viewport_size()
        vw = max(1, viewport.width())
        vh = max(1, viewport.height())
        needed = max(width / vw, height / vh)
        factor = next((value for value in BLOCK_FACTORS if value >= needed), BLOCK_FACTORS[-1])
        self.set_block_factor(factor)

    def show_block_dialog(self) -> None:
        """Show block-factor parameter dialog."""
        frame = self.frames.current_frame
        current = getattr(frame, "block_factor", 1) if frame else 1
        value, ok = QInputDialog.getInt(
            self.window,
            "Block Parameters",
            "Block factor:",
            int(current),
            BLOCK_FACTORS[0],
            BLOCK_FACTORS[-1],
            1,
        )
        if not ok:
            return
        self.set_block_factor(value)

    def show_smooth_dialog(self) -> None:
        """Show smoothing parameters dialog."""
        if self.window.image_data is None:
            self.status("No image loaded", 2000)
            return
        dialog = SmoothDialog(self.window)
        dialog.smoothing_changed.connect(self.apply_smooth_settings)
        dialog.exec()

    def apply_smooth_settings(self, settings: dict) -> None:
        """Apply smoothing settings from dialog."""
        self.window._smooth_settings = settings
        self.menu.action_smooth.blockSignals(True)
        self.menu.action_smooth.setChecked(True)
        self.menu.action_smooth.blockSignals(False)
        self.set_smooth(True)

    def set_smooth(self, checked: bool) -> None:
        """Turn display smoothing on or off.

        The menu action is set here rather than assumed: the display reads
        it to decide whether to smooth, so a caller that is not the menu --
        XPA, a script, a restored session -- would otherwise turn smoothing
        on in the status bar and nowhere else.
        """
        action = self.menu.action_smooth
        if action.isChecked() != bool(checked):
            action.blockSignals(True)
            action.setChecked(bool(checked))
            action.blockSignals(False)
        self.window.z1 = None
        self.window.z2 = None
        self.window.display.display()
        self.log_command(f"smooth {'on' if checked else 'off'}")
        self.status(f"Smooth {'enabled' if checked else 'disabled'}", 2000)

    def analysis_image_data(self, frame: Frame) -> NDArray[np.floating]:
        """Return analysis-ready data with current smoothing and mask settings."""
        display_data = self.window.display.display_image_data(frame)
        return self.apply_mask(display_data)

    def apply_mask(self, data: NDArray[np.floating]) -> NDArray[np.floating]:
        """Blank the pixels the mask excludes, for the analysis tools.

        The mask shows as a colour on the display; for statistics and a
        histogram it has to actually remove pixels, which is what this does.
        With no mask loaded the data is returned untouched.
        """
        layer = self.mask_layer
        settings = self.mask_settings
        if layer is None or settings is None or np.ndim(data) != 2:
            return data

        fitted = mask_module.align(layer, (data.shape[0], data.shape[1]))
        keep = mask_module.selected(fitted, settings)
        masked = np.array(data, copy=True, dtype=np.float32)
        masked[~keep] = np.nan
        return masked

    def apply_smoothing(self, data: NDArray[np.floating]) -> NDArray[np.floating]:
        """Apply configured smoothing to an image array."""
        settings = self.window._smooth_settings
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
                # DS9's elliptical Gaussian takes a position angle. Passing
                # a pair of axis-aligned sigmas to `gaussian_smooth`, which
                # is what this did, cannot express one -- so the dialog's
                # Position angle field had no effect at all (M7-25).
                axis_ratio = max(float(settings.get("axis_ratio", 1.0)), 0.1)
                major_radius = max(1, int(float(settings.get("kernel_size", 5)) / 2.0))
                smoothed = elliptical_gaussian_smooth(
                    working,
                    major_radius=int(settings.get("major_radius", major_radius)),
                    minor_radius=int(settings.get("minor_radius", max(1, round(major_radius * axis_ratio)))),
                    major_sigma=float(settings.get("major_sigma", sigma)),
                    minor_sigma=float(settings.get("minor_sigma", sigma * axis_ratio)),
                    angle=float(settings.get("position_angle", 0.0)),
                )
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

    def set_grid(self, checked: bool) -> None:
        """Show or hide the coordinate grid, DS9's Coordinate Grid toggle."""
        self.grid_config.visible = bool(checked)
        self.refresh_grid()
        if checked and not self._grid_renderer_usable():
            self.status("This frame has no WCS, so there is no coordinate grid", 3500)
        else:
            self.status("Coordinate grid enabled" if checked else "Coordinate grid disabled", 2000)
        self.log_command(f"grid {'on' if checked else 'off'}")

    def _grid_renderer_usable(self) -> bool:
        """Whether the current frame has a WCS to draw a grid through."""
        frame = self.frame
        handler = getattr(frame, "wcs_handler", None) if frame else None
        return bool(handler is not None and getattr(handler, "is_valid", False))

    def refresh_grid(self) -> None:
        """Recompute the graticule and hand it to the overlay.

        Called on a zoom, a pan, a frame change and every settings change:
        the grid is in image coordinates, so panning does not change it,
        but loading a different frame changes the WCS and therefore all of
        it.
        """
        overlay = getattr(self.viewer, "contour_overlay", None)
        if overlay is None or not hasattr(overlay, "set_grid_geometry"):
            # Fall back to the plain visibility flag, which is all an older
            # viewer understands.
            if hasattr(self.viewer, "set_grid"):
                self.viewer.set_grid(self.grid_config.visible, None)
            return

        frame = self.frame
        data = getattr(frame, "image_data", None) if frame else None
        renderer = self._grid_renderer
        renderer.wcs = getattr(frame, "wcs_handler", None) if frame else None
        renderer.config = self.grid_config

        geometry = None
        if self.grid_config.visible and data is not None:
            geometry = renderer.compute(int(data.shape[1]), int(data.shape[0]))

        overlay.set_grid_geometry(geometry, self.grid_config)
        if hasattr(self.viewer, "set_grid"):
            self.viewer.set_grid(self.grid_config.visible, None)

    def show_grid_dialog(self) -> None:
        """Show DS9's Coordinate Grid Parameters dialog."""
        dialog = GridDialog(self.grid_config, self.window)
        dialog.grid_changed.connect(self.apply_grid_settings)
        dialog.exec()

    def apply_grid_settings(self, config) -> None:
        """Take the settings the dialog chose and redraw."""
        self.grid_config = config
        self.menu.action_coordinate_grid.blockSignals(True)
        self.menu.action_coordinate_grid.setChecked(config.visible)
        self.menu.action_coordinate_grid.blockSignals(False)
        self.refresh_grid()
        self.log_command("grid params")
        self.status("Updated coordinate grid parameters", 2000)

    def show_mask_dialog(self) -> None:
        """Show DS9's Mask Parameters dialog (M7-24)."""
        dialog = MaskDialog(
            self.mask_settings,
            str(self.mask_path or "" or ""),
            self.window,
        )
        dialog.mask_changed.connect(self.apply_mask_settings)
        dialog.mask_cleared.connect(self.clear_mask)
        dialog.exec()

    def apply_mask_settings(self, settings, path: str) -> None:
        """Load a mask file if one was chosen, and redraw with the settings."""
        self.mask_settings = settings
        if path and path != self.mask_path:
            try:
                self.mask_layer = mask_module.load(path)
            except mask_module.MaskError as exc:
                self.status(str(exc), 5000)
                return
            except OSError as exc:
                self.status(f"Cannot read {Path(path).name}: {exc}", 5000)
                return
            self.mask_path = path

        if self.mask_layer is None:
            self.status("Open a mask file first", 3000)
            return

        self.window.display.display()
        self.log_command("mask params")
        self.status(f"Mask: {settings.mode.value}, {settings.blend.value}")

    def load_mask(self, path: str) -> bool:
        """Load a mask file without asking for it, as `mask <file>` does.

        Returns:
            Whether it loaded.
        """
        try:
            self.mask_layer = mask_module.load(str(path))
        except (mask_module.MaskError, OSError) as exc:
            self.status(f"Cannot read {Path(path).name}: {exc}", 5000)
            return False
        self.mask_path = str(path)
        self.window.display.display()
        self.status(f"Mask loaded from {Path(path).name}", 3000)
        return True

    def clear_mask(self) -> None:
        """Remove the mask, DS9's Clear."""
        self.mask_layer = None
        self.mask_path = None
        self.window.display.display()
        self.status("Mask cleared")

    def show_graph_dialog(self) -> None:
        """Show graph panel visibility controls."""
        current = "None"
        if self.window.horizontal_graph.isVisible() and self.window.vertical_graph.isVisible():
            current = "Both"
        elif self.window.horizontal_graph.isVisible():
            current = "Horizontal"
        elif self.window.vertical_graph.isVisible():
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
        self.set_graph_visibility(mode)
        self.status(f"Graph panels: {mode}", 2000)

    def set_graph_visibility(self, mode: str) -> None:
        """Set visibility for horizontal/vertical graph docks."""
        show_horizontal = mode in ("Horizontal", "Both")
        show_vertical = mode in ("Vertical", "Both")
        self.window.horizontal_graph.setVisible(show_horizontal)
        self.window.vertical_graph.setVisible(show_vertical)
        self.log_command(f"graph {mode.lower()}")
        frame = self.frames.current_frame
        if frame and frame.image_data is not None:
            analysis_data = self.analysis_image_data(frame)
            self.window.horizontal_graph.set_image(analysis_data)
            self.window.vertical_graph.set_image(analysis_data)

    def refresh_overlays(self) -> None:
        """Apply the grid and crosshair overlay states to the active viewer."""
        self.refresh_grid()
        # The crosshair has its own controller as of M9-1; it used to follow
        # the pointer from here, which is not what DS9's crosshair does.
        self.window.crosshair.refresh()

    def resolve_name(self, name: str) -> str | None:
        """Resolve one object name and pan to it, without asking for it.

        What the `nameserver` XPA point calls; `resolve_object_name` is the
        menu entry that asks first and then comes here.

        Returns:
            None if it worked, or what went wrong.
        """
        query = str(name).strip()
        if not query:
            return "an object name is needed"
        try:
            coord = SkyCoord.from_name(query)
        except Exception as exc:
            self.status(f"Name resolution failed: {exc}", 3500)
            return f"could not resolve {query}: {exc}"

        self.window._last_resolved_name = query
        handler = self.window.wcs_handler
        if handler is None or not handler.is_valid:
            self.status(f"{query}: {coord.to_string('hmsdms')} (no WCS to pan to)", 4000)
            return None
        x, y = handler.world_to_pixel(coord.ra.deg, coord.dec.deg)
        self.window.zoom.on_panner_pan(float(x), float(y))
        self.status(f"{query}: panned to {x:.1f} {y:.1f}", 3000)
        return None

    def resolve_object_name(self) -> None:
        """Resolve an object name and pan to it if WCS is available."""
        name, ok = QInputDialog.getText(self.window, "Name Resolution", "Object name:")
        if not ok or not name.strip():
            return
        query = name.strip()
        try:
            coord = SkyCoord.from_name(query)
        except Exception as exc:
            self.status(f"Name resolution failed: {exc}", 3500)
            return

        if self.window.wcs_handler and self.window.wcs_handler.is_valid:
            try:
                x, y = self.window.wcs_handler.world_to_pixel(coord.ra.deg, coord.dec.deg)
                if self.window.using_gpu_rendering and hasattr(self.viewer, "set_pan"):
                    self.viewer.set_pan(float(x), float(y))
                    self.window.frame_controller.persist_view_state()
                    self.window.zoom.update_panner_rect()
                else:
                    self.window.zoom.on_panner_pan(float(x), float(y))
                self.status(
                    f"{query}: RA {coord.ra.deg:.6f} deg, Dec {coord.dec.deg:.6f} deg",
                    4000,
                )
                self.log_command(f"name {query}")
                return
            except Exception:
                pass

        self.status(
            f"{query}: RA {coord.ra.deg:.6f} deg, Dec {coord.dec.deg:.6f} deg",
            4000,
        )
        self.log_command(f"name {query}")

    def set_command_log(self, checked: bool) -> None:
        """Toggle analysis command logging preference."""
        self.window._analysis_command_log = checked
        self.status(
            f"Analysis command log {'enabled' if checked else 'disabled'}",
            2000,
        )

    def log_command(self, command: str) -> None:
        """Append an analysis command to in-memory log when enabled."""
        if not self.window._analysis_command_log:
            return
        self.window._analysis_command_entries.append(command)
        if len(self.window._analysis_command_entries) > 200:
            self.window._analysis_command_entries = self.window._analysis_command_entries[-200:]

    # -- the Plot Tool (M7-15 ... M7-20) -------------------------------------

    def open_plot_tool(self, style: PlotStyle = PlotStyle.LINE) -> PlotWindow:
        """Open an empty plot window, DS9's Analysis -> Plot Tool.

        Empty on purpose: DS9's Plot Tool opens with nothing in it and its
        File -> Load Data reads a column file. The same window is what an
        analysis task's `$plot` output lands in.
        """
        window = PlotWindow(PlotState(style=style), self.window)
        self._remember_plot(window)
        window.show()
        self.status(f"Plot Tool: {style.value}")
        return window

    def show_plot(self, state: PlotState) -> PlotWindow:
        """Open a plot window on data that already exists."""
        window = PlotWindow(state, self.window)
        self._remember_plot(window)
        window.show()
        return window

    def _remember_plot(self, window: PlotWindow) -> None:
        """Keep a plot window alive and make it the current one."""
        window.finished.connect(lambda _result, w=window: self._forget_plot(w))
        self._plots.append(window)
        self._current_plot = window

    def _forget_plot(self, window: PlotWindow) -> None:
        """Drop a closed plot window, and pick another as current."""
        if window in self._plots:
            self._plots.remove(window)
        if self._current_plot is window:
            self._current_plot = self._plots[-1] if self._plots else None

    def current_plot(self) -> PlotWindow | None:
        """The plot DS9's `plot` access point acts on: the last one made."""
        return self._current_plot

    def plots(self) -> list[PlotWindow]:
        """Every plot window open, oldest first."""
        return list(self._plots)

    def set_current_plot(self, reference: str) -> bool:
        """Make one plot current by its number or its title, DS9's `current`.

        Returns:
            Whether one was found.
        """
        if reference.isdigit():
            index = int(reference) - 1
            if 0 <= index < len(self._plots):
                self._current_plot = self._plots[index]
                return True
            return False
        for window in self._plots:
            if window.state.title == reference:
                self._current_plot = window
                return True
        return False

    def open_web_browser(self) -> None:
        """Open a browser URL from the Analysis menu."""
        QDesktopServices.openUrl(QUrl("https://sites.google.com/cfa.harvard.edu/saoimageds9"))
        self.log_command("web")
        self.status("Opened web browser", 2000)

    def sync_bin_menu(self, factor: int) -> None:
        """Tick the Block entry matching the current factor.

        Named for the Bin menu it used to also tick. The Bin menu has its own
        controller as of M5-16; this only touches Block now, and keeps the
        name because the display pipeline and XPA both call it.
        """
        self.sync_block_menu(factor)

    def set_block(self, factor: int) -> None:
        """Set the display block factor for the current frame.

        Block reduces how much data is *drawn*, not what the frame holds:
        `frame.image_data` stays at full resolution and the render pipeline
        reduces a copy on its way to the screen (`display.block_image`). That
        is what DS9 means by Block, and PLAN.md §3.4 records why this used to
        be wrong -- it overwrote `frame.image_data`, so a region drawn at
        pixel 100 read back at pixel 25 under a block of four, the WCS was
        never rescaled, and `Save` wrote the reduced array.

        Args:
            factor: Image pixels per displayed pixel, at least one.
        """
        frame = self.frames.current_frame
        if not frame or not frame.has_data:
            self.status("No image loaded", 2000)
            return

        frame.block_factor = max(1, int(factor))
        self.window.current_bin = frame.block_factor
        # Blocking averages pixels together, which narrows the distribution,
        # so the limits are no longer the ones that were measured.
        self.window.z1 = None
        self.window.z2 = None
        frame.z1 = None
        frame.z2 = None

        if self.window.frame_controller.block_is_locked():
            for other in self.frames.frames:
                other.block_factor = frame.block_factor

        self.sync_bin_menu(frame.block_factor)
        self.window.display.display()
        height, width = frame.image_data.shape[:2]
        self.status_bar.update_image_info(width, height)
        self.status(f"Block: {frame.block_factor}x{frame.block_factor}", 2000)

    def set_bin(self, factor: int) -> None:
        """Set the display block factor. Kept for XPA and the older callers.

        DS9 distinguishes Bin, which turns a FITS table into an image, from
        Block, which reduces an image for display. NCRADS9 had one operation
        doing the second under the first's name; this is that name, still
        forwarding to Block so an older caller behaves as it did. The real
        Bin is `ui/controllers/bin.py`.
        """
        self.set_block(factor)

    def show_statistics(self) -> None:
        """Show statistics dialog."""
        frame = self.frames.current_frame
        if frame is None or frame.image_data is None:
            self.status("No image loaded", 2000)
            return

        dialog = StatisticsDialog(self.analysis_image_data(frame), self.window)
        dialog.exec()
        self.log_command("statistics")

    def show_histogram(self) -> None:
        """Show histogram dialog."""
        frame = self.frames.current_frame
        if frame is None or frame.image_data is None:
            self.status("No image loaded", 2000)
            return

        dialog = HistogramDialog(self.analysis_image_data(frame), self.window)
        dialog.exec()
        self.log_command("histogram")

    def show_radial_profile(self) -> None:
        """Show radial profile plot from the current frame."""
        frame = self.frames.current_frame
        if frame is None or frame.image_data is None:
            self.status("No image loaded", 2000)
            return

        data = self.analysis_image_data(frame)
        if not np.any(np.isfinite(data)):
            self.status("No valid pixels for radial profile", 2500)
            return
        profile = RadialProfile(data)
        radii, values = profile.extract()

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        from .. import plot_theme

        dialog = QDialog(self.window)
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
        plot_theme.style_figure(figure, dialog)
        figure.tight_layout()
        layout.addWidget(canvas)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        dialog.exec()
        self.log_command("radial_profile")

    def show_contour_dialog(self) -> None:
        """Show contour dialog and apply contours."""
        if self.window.image_data is None:
            self.status("No image loaded", 2000)
            return

        dialog = ContourDialog(self.window)
        if self.window._contour_settings is not None:
            dialog.load_settings(self.window._contour_settings)
        dialog.contours_changed.connect(self.apply_contours)
        dialog.contours_export_requested.connect(self.export_contours)
        dialog.contours_file_requested.connect(self.contour_file_command)
        dialog.exec()

    def apply_contours(self, settings: dict) -> None:
        """Compute and display contours based on settings."""
        self.window._contour_settings = settings
        self.menu.action_contours.blockSignals(True)
        self.menu.action_contours.setChecked(True)
        self.menu.action_contours.blockSignals(False)
        self.update_contours()
        self.log_command("contour params")

    def set_contours(self, checked: bool) -> None:
        """Show or hide the contour overlay.

        The menu action is set here for the same reason smoothing's is: a
        caller that is not the menu would otherwise draw contours and leave
        the entry unticked, and the next click on it would turn them *on*
        again.
        """
        action = self.menu.action_contours
        if action.isChecked() != bool(checked):
            action.blockSignals(True)
            action.setChecked(bool(checked))
            action.blockSignals(False)

        if checked:
            if self.window._contour_settings is None:
                self.window._contour_settings = {
                    "method": "Linear",
                    "num_levels": 10,
                    "smooth": False,
                    "smooth_sigma": 1.0,
                    "line_width": 1.0,
                    "line_style": "Solid",
                    "color": "#00ff00",
                    "show_labels": False,
                }
            self.update_contours()
            self.log_command("contour on")
            self.status("Contours enabled", 2000)
        else:
            if hasattr(self.viewer, "clear_contours"):
                self.viewer.clear_contours()
            self.log_command("contour off")
            self.status("Contours disabled", 2000)

    def update_contours(self) -> None:
        """Recompute contours for current image."""
        if not self.menu.action_contours.isChecked():
            if hasattr(self.viewer, "clear_contours"):
                self.viewer.clear_contours()
            return
        frame = self.frames.current_frame
        if frame is None or frame.image_data is None or self.window._contour_settings is None:
            if hasattr(self.viewer, "clear_contours"):
                self.viewer.clear_contours()
            return

        contour_data = self.analysis_image_data(frame)
        settings = self.window._contour_settings
        smooth_sigma = settings.get("smooth_sigma", 1.0) if settings.get("smooth") else None
        generator = ContourGenerator(
            contour_data,
            smooth=smooth_sigma,
            method=str(settings.get("contour_method", "block")),
            smoothness=int(settings.get("smoothness", 1)),
        )

        levels = self.contour_levels(generator, settings)

        try:
            contours = generator.find_contours(levels)
            contour_paths = self.convert_skimage_contours(contours)
        except Exception:
            contours = generator.find_contours_scipy(levels)
            contour_paths = self.convert_scipy_contours(contours)

        self.window._contour_paths = contour_paths
        self.window._contour_levels = levels

        style = self.contour_style(settings)
        if hasattr(self.viewer, "set_contours"):
            self.viewer.set_contours(contour_paths, levels, style)

    # -- contour files, copy and paste (M7-21, M7-22) ------------------------

    def contour_file_command(self, name: str) -> None:
        """Run one of DS9's contour File commands."""
        handler = {
            "open": self.load_contours,
            "save": self.save_contours,
            "copy": self.copy_contours,
            "paste": self.paste_contours,
        }.get(name)
        if handler is None:
            self.status(f"Unknown contour command: {name}", 3000)
            return
        handler()

    def current_contour_set(self):
        """The contours on screen, as a `ContourSet`, or None."""
        paths = self.window._contour_paths
        levels = self.window._contour_levels
        if not paths or levels is None:
            return None
        settings = self.window._contour_settings or {}
        return contour_file.from_paths(
            paths,
            levels,
            system="image",
            color=str(settings.get("color", contour_file.DEFAULT_COLOR)),
            width=int(float(settings.get("line_width", 1)) or 1),
            dash=str(settings.get("line_style", "Solid")).lower() != "solid",
        )

    def show_contour_set(self, contours) -> None:
        """Put a loaded or pasted contour set on screen."""
        self.window._contour_paths = contour_file.to_paths(contours)
        self.window._contour_levels = contours.values
        self.menu.action_contours.blockSignals(True)
        self.menu.action_contours.setChecked(True)
        self.menu.action_contours.blockSignals(False)

        if hasattr(self.viewer, "set_contours"):
            first = contours.levels[0] if contours.levels else None
            style = (
                QColor(first.color) if first else QColor(0, 255, 0),
                float(first.width) if first else 1.0,
                Qt.PenStyle.DashLine if (first and first.dash) else Qt.PenStyle.SolidLine,
                False,
            )
            self.viewer.set_contours(self.window._contour_paths, contours.values, style)

    def load_contours(self) -> None:
        """Read a DS9 contour file and display it."""
        path, _filter = QFileDialog.getOpenFileName(self.window, "Open Contours", "", CONTOUR_FILTER)
        if not path:
            return
        try:
            contours = contour_file.load(path)
        except contour_file.ContourFileError as exc:
            self.status(f"{Path(path).name}: {exc}", 5000)
            return
        except OSError as exc:
            self.status(f"Cannot read {Path(path).name}: {exc}", 5000)
            return

        if not contours:
            self.status(f"{Path(path).name} holds no contours", 3000)
            return
        self.show_contour_set(contours)
        self.status(f"Loaded {len(contours)} contour levels from {Path(path).name}")

    def save_contours(self) -> None:
        """Write the contours on screen as a DS9 contour file."""
        contours = self.current_contour_set()
        if contours is None:
            self.status("No contours to save", 3000)
            return
        path, _filter = QFileDialog.getSaveFileName(self.window, "Save Contours", "", CONTOUR_FILTER)
        if not path:
            return
        try:
            contour_file.save(path, contours)
        except OSError as exc:
            self.status(f"Cannot write {Path(path).name}: {exc}", 5000)
            return
        self.status(f"Saved {len(contours)} contour levels to {Path(path).name}")

    def load_contour_file(self, path: str) -> str | None:
        """Read a contour file without asking, DS9's `contour load <file>`.

        Returns:
            None if it loaded, or what went wrong.
        """
        try:
            contours = contour_file.load(path)
        except contour_file.ContourFileError as exc:
            return f"{Path(path).name}: {exc}"
        except OSError as exc:
            return f"cannot read {Path(path).name}: {exc}"
        if not contours:
            return f"{Path(path).name} holds no contours"
        self.show_contour_set(contours)
        self.status(f"Loaded {len(contours)} contour levels from {Path(path).name}")
        return None

    def save_contour_file(self, path: str) -> str | None:
        """Write the contours on screen without asking.

        Returns:
            None if it wrote, or what went wrong.
        """
        contours = self.current_contour_set()
        if contours is None:
            return "no contours to save"
        try:
            contour_file.save(path, contours)
        except OSError as exc:
            return f"cannot write {Path(path).name}: {exc}"
        self.status(f"Saved {len(contours)} contour levels to {Path(path).name}")
        return None

    def copy_contours(self) -> None:
        """Copy the contours, DS9's Copy Contours.

        They go to the clipboard in DS9's own file format, so a copy is
        exactly a save and a paste exactly a load -- one thing to get right
        rather than two, and the contours can be pasted into a text editor
        as well as into another frame.
        """
        contours = self.current_contour_set()
        if contours is None:
            self.status("No contours to copy", 3000)
            return
        QGuiApplication.clipboard().setText(contour_file.to_text(contours))
        self.status(f"Copied {len(contours)} contour levels")

    def paste_contours(self) -> None:
        """Paste contours into the current frame, DS9's Paste Contours."""
        text = QGuiApplication.clipboard().text()
        if not text.strip():
            self.status("The clipboard is empty", 3000)
            return
        try:
            contours = contour_file.parse(text)
        except contour_file.ContourFileError as exc:
            self.status(f"The clipboard does not hold contours: {exc}", 4000)
            return
        if not contours:
            self.status("The clipboard does not hold contours", 3000)
            return
        self.show_contour_set(contours)
        self.status(f"Pasted {len(contours)} contour levels")

    def contour_levels(self, generator: ContourGenerator, settings: dict) -> list:
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

    def convert_skimage_contours(self, contours: list) -> list:
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

    def convert_scipy_contours(self, contours: list) -> list:
        """Convert scipy contours to x/y arrays."""
        contour_paths: list = []
        for level_paths in contours:
            converted = []
            for x_coords, y_coords in level_paths:
                coords = np.column_stack([x_coords, y_coords]).astype(np.float64)
                converted.append(coords)
            contour_paths.append(converted)
        return contour_paths

    def contour_style(self, settings: dict):
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

    def export_contours(self, settings: dict) -> None:
        """Export current contours to a file."""
        if self.window._contour_paths is None or self.window._contour_levels is None:
            self.apply_contours(settings)
            if self.window._contour_paths is None or self.window._contour_levels is None:
                self.status("No contours to export", 2000)
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
            "levels": self.window._contour_levels,
            "contours": [
                [path.tolist() for path in level_paths] for level_paths in self.window._contour_paths
            ],
            "settings": settings,
        }

        import json

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)
        self.status(f"Exported contours to {filepath}", 3000)

    def show_pixel_table(self) -> None:
        """Show the pixel table, and keep it following the cursor.

        DS9's pixel table is a window that stays open and tracks the
        pointer -- that is the whole point of it. Ours used to be modal and
        made fresh each time, so it blocked the application and showed the
        middle of the image rather than what was under the cursor. The
        dialog itself was always ready for this: it is non-modal and has
        `set_center` for exactly this purpose.
        """
        frame = self.frames.current_frame
        if frame is None or frame.image_data is None:
            self.status("No image loaded", 2000)
            return

        analysis_data = self.analysis_image_data(frame)
        height, width = analysis_data.shape
        where = self.window._last_mouse_pos or (width // 2, height // 2)

        existing = self.pixel_table
        if existing is not None:
            existing.image_data = analysis_data
            existing.reader = PixelTable(analysis_data)
            existing.wcs_handler = getattr(frame, "wcs_handler", None)
            existing.set_center(*where)
            existing.show()
            existing.raise_()
            return

        dialog = PixelTableDialog(
            analysis_data,
            where[0],
            where[1],
            parent=self.window,
            wcs_handler=getattr(frame, "wcs_handler", None),
        )
        dialog.finished.connect(lambda _result: self._forget_pixel_table())
        self.pixel_table = dialog
        dialog.show()
        self.log_command("pixel_table")

    def _forget_pixel_table(self) -> None:
        """Drop the pixel table when it is closed."""
        self.pixel_table = None

    def close_pixel_table(self) -> None:
        """Close the pixel table, as `pixeltable close` asks."""
        dialog = self.pixel_table
        self.pixel_table = None
        if dialog is not None:
            dialog.close()

    def pixel_table_open(self) -> bool:
        """Whether the pixel table window is open."""
        return self.pixel_table is not None

    def update_pixel_table(self, x: int, y: int) -> None:
        """Point the pixel table at the pixel under the cursor."""
        dialog = self.pixel_table
        if dialog is not None and dialog.isVisible():
            dialog.set_center(x, y)
