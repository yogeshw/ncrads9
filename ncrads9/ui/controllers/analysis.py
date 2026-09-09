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
* The `.ds9.ans` external-task engine. `load_commands` reads a homegrown
  `label|command` format, not DS9's four task types, macro set and output
  sinks (M7-1 to M7-9).
* Mask *files*, with blend mode, colour and value range; only thresholding
  exists (M7-24).
* The Plot Tool, catalog tool, image servers, archives and footprint servers
  (M7-15, M8).

`set_bin` is knowingly misnamed. DS9's Bin builds an image from a FITS bin
table by binning two columns; this block-averages an image, which is DS9's
Block. The two menus therefore run the same code today. M5-14 to M5-19
separate them.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import numpy as np
from astropy.coordinates import SkyCoord
from numpy.typing import NDArray
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QAction, QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QPushButton,
    QVBoxLayout,
)
from scipy import ndimage

from ...analysis.contour import ContourGenerator
from ...analysis.radial_profile import RadialProfile
from ...analysis.smooth import boxcar_smooth, gaussian_smooth, tophat_smooth
from ...frames.frame import Frame
from ..dialogs.contour_dialog import ContourDialog
from ..dialogs.grid_dialog import GridDialog
from ..dialogs.histogram_dialog import HistogramDialog
from ..dialogs.pixel_table_dialog import PixelTableDialog
from ..dialogs.smooth_dialog import SmoothDialog
from ..dialogs.statistics_dialog import StatisticsDialog
from ..menu_bar import BLOCK_FACTORS
from .base import Controller

#: The block factors the menu offers, imported so the two cannot diverge.

#: The Bin menu's factors. DS9's Bin turns a FITS table into an image; this
#: menu block-averaged like Block until M5-15, and now says so rather than
#: doing the wrong thing quietly. M5-16 gives it its real behaviour.
BIN_FACTORS: tuple[int, ...] = (1, 2, 4, 8)


class AnalysisController(Controller):
    """Owns the Analysis and Bin menus."""

    def connect(self) -> None:
        """Wire the Analysis and Bin menus."""
        menu = self.menu

        menu.action_pixel_table.triggered.connect(self.show_pixel_table)
        menu.action_name_resolution.triggered.connect(self.resolve_object_name)
        menu.action_statistics.triggered.connect(self.show_statistics)
        menu.action_histogram.triggered.connect(self.show_histogram)
        menu.action_radial_profile.triggered.connect(self.show_radial_profile)

        menu.action_mask_params.triggered.connect(self.show_mask_dialog)
        menu.action_crosshair_params.triggered.connect(self.show_crosshair_dialog)
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
        menu.action_load_analysis_commands.triggered.connect(self.load_commands)
        menu.action_clear_analysis_commands.triggered.connect(self.clear_commands)
        menu.action_web_browser.triggered.connect(self.open_web_browser)

        for factor in BIN_FACTORS:
            getattr(menu, f"action_bin_{factor}").triggered.connect(
                lambda _checked=False, f=factor: self.set_bin(f)
            )

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
        """Toggle display smoothing."""
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
        """Apply analysis mask settings to image data."""
        if self.window._analysis_mask_mode == "disabled":
            return data
        masked = np.array(data, copy=True, dtype=np.float32)
        finite_mask = np.isfinite(masked)
        keep_mask = finite_mask
        if self.window._analysis_mask_mode == "range":
            low = self.window._analysis_mask_min if self.window._analysis_mask_min is not None else -np.inf
            high = self.window._analysis_mask_max if self.window._analysis_mask_max is not None else np.inf
            keep_mask = finite_mask & (masked >= low) & (masked <= high)
        masked[~keep_mask] = np.nan
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

    def set_grid(self, checked: bool) -> None:
        """Toggle coordinate grid overlay."""
        self.refresh_overlays()
        self.status(
            "Coordinate grid enabled" if checked else "Coordinate grid disabled",
            2000,
        )
        self.log_command(f"grid {'on' if checked else 'off'}")

    def show_grid_dialog(self) -> None:
        """Show coordinate grid parameters dialog."""
        dialog = GridDialog(self.window)
        if self.window._grid_settings:
            dialog._coord_combo.setCurrentText(self.window._grid_settings.get("coord_system", "WCS"))
            dialog._format_combo.setCurrentText(self.window._grid_settings.get("label_format", "Sexagesimal"))
            dialog._auto_spacing_check.setChecked(self.window._grid_settings.get("auto_spacing", True))
            dialog._ra_spacing_spin.setValue(float(self.window._grid_settings.get("ra_spacing", 1.0)))
            dialog._dec_spacing_spin.setValue(float(self.window._grid_settings.get("dec_spacing", 1.0)))
        dialog.grid_changed.connect(self.apply_grid_settings)
        dialog.exec()

    def apply_grid_settings(self, settings: dict) -> None:
        """Store coordinate grid settings."""
        self.window._grid_settings = settings
        self.menu.action_coordinate_grid.blockSignals(True)
        self.menu.action_coordinate_grid.setChecked(True)
        self.menu.action_coordinate_grid.blockSignals(False)
        self.refresh_overlays()
        self.log_command("grid params")
        self.status("Updated coordinate grid parameters", 2000)

    def show_mask_dialog(self) -> None:
        """Show mask parameter controls for analysis tools."""
        mode_labels = ["Disabled", "Finite Pixels Only", "Value Range"]
        mode_map = {
            "Disabled": "disabled",
            "Finite Pixels Only": "finite",
            "Value Range": "range",
        }
        current_label = next(
            (label for label, mode in mode_map.items() if mode == self.window._analysis_mask_mode),
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
        self.window._analysis_mask_mode = mode
        if mode == "range":
            min_default = (
                self.window._analysis_mask_min if self.window._analysis_mask_min is not None else 0.0
            )
            max_default = (
                self.window._analysis_mask_max if self.window._analysis_mask_max is not None else 1.0
            )
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
            self.window._analysis_mask_min = float(min_val)
            self.window._analysis_mask_max = float(max_val)
            self.status(
                f"Mask range set to [{self.window._analysis_mask_min:.4g}, {self.window._analysis_mask_max:.4g}]",
                3000,
            )
        else:
            self.window._analysis_mask_min = None
            self.window._analysis_mask_max = None
            self.status(f"Mask mode: {choice}", 2500)
        self.log_command(f"mask {mode}")

    def show_crosshair_dialog(self) -> None:
        """Show crosshair parameter controls."""
        enabled, ok = QInputDialog.getItem(
            self,
            "Crosshair Parameters",
            "Crosshair:",
            ["Off", "On"],
            1 if self.window._crosshair_enabled else 0,
            False,
        )
        if not ok:
            return
        self.window._crosshair_enabled = enabled == "On"
        if self.window._crosshair_enabled:
            color = QColorDialog.getColor(self.window._crosshair_color, self.window, "Crosshair Color")
            if color.isValid():
                self.window._crosshair_color = color
            size, ok_size = QInputDialog.getInt(
                self,
                "Crosshair Parameters",
                "Crosshair size (pixels):",
                self.window._crosshair_size,
                4,
                256,
            )
            if ok_size:
                self.window._crosshair_size = int(size)
        self.refresh_overlays()
        self.log_command(f"crosshair {'on' if self.window._crosshair_enabled else 'off'}")
        self.status(
            f"Crosshair {'enabled' if self.window._crosshair_enabled else 'disabled'}",
            2000,
        )

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
        """Apply grid/crosshair overlay states to the active viewer."""
        if hasattr(self.viewer, "set_grid"):
            self.viewer.set_grid(
                self.menu.action_coordinate_grid.isChecked(),
                self.window._grid_settings,
            )
        if hasattr(self.viewer, "set_crosshair"):
            position = (
                (float(self.window._last_mouse_pos[0]), float(self.window._last_mouse_pos[1]))
                if self.window._last_mouse_pos is not None
                else None
            )
            self.viewer.set_crosshair(
                self.window._crosshair_enabled,
                position=position,
                color=self.window._crosshair_color,
                size=self.window._crosshair_size,
            )

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

    def load_commands(self) -> None:
        """Load simple external analysis commands into the Analysis menu."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Analysis Commands",
            "",
            "Analysis Command Files (*.ans *.analysis *.txt *.ds9);;All Files (*)",
        )
        if not filepath:
            return

        self.clear_commands(show_message=False)
        loaded = 0
        try:
            with open(filepath, encoding="utf-8") as handle:
                lines = handle.readlines()
        except Exception as exc:
            self.status(f"Failed to load analysis commands: {exc}", 3500)
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
            action = QAction(label, self.window)
            action.triggered.connect(
                lambda checked=False, cmd=command, title=label: self.execute_command(title, cmd)
            )
            self.menu.analysis_menu.insertAction(self.menu.action_load_analysis_commands, action)
            self.window._loaded_analysis_actions.append(action)
            loaded += 1

        self.log_command(f"load_analysis_commands {loaded}")
        self.status(f"Loaded {loaded} analysis commands", 3000)

    def execute_command(self, title: str, command: str) -> None:
        """Execute a simple loaded analysis command."""
        cmd = command.strip()
        self.log_command(f"run {title}: {cmd}")
        if cmd.lower().startswith(("http://", "https://", "url:")):
            target = cmd.split(":", 1)[1].strip() if cmd.lower().startswith("url:") else cmd
            QDesktopServices.openUrl(QUrl(target))
            self.status(f"Opened {title}", 2000)
            return
        if cmd.lower().startswith("open:"):
            target = cmd.split(":", 1)[1].strip()
            if target:
                self.window.file.open_file(target)
                return
        if cmd.lower().startswith("message:"):
            self.status(cmd.split(":", 1)[1].strip(), 3000)
            return
        self.status(f"{title}: {cmd}", 3000)

    def clear_commands(self, show_message: bool = True) -> None:
        """Clear previously loaded external analysis commands."""
        if not self.window._loaded_analysis_actions:
            if show_message:
                self.status("No external analysis commands are currently loaded", 2500)
            return
        for action in self.window._loaded_analysis_actions:
            self.menu.analysis_menu.removeAction(action)
        cleared = len(self.window._loaded_analysis_actions)
        self.window._loaded_analysis_actions = []
        self.log_command(f"clear_analysis_commands {cleared}")
        if show_message:
            self.status(f"Cleared {cleared} analysis commands", 2500)

    def open_web_browser(self) -> None:
        """Open a browser URL from the Analysis menu."""
        QDesktopServices.openUrl(QUrl("https://sites.google.com/cfa.harvard.edu/saoimageds9"))
        self.log_command("web")
        self.status("Opened web browser", 2000)

    def sync_bin_menu(self, factor: int) -> None:
        """Update Bin menu checkmarks based on current factor."""
        self.menu.action_bin_1.setChecked(factor == 1)
        self.menu.action_bin_2.setChecked(factor == 2)
        self.menu.action_bin_4.setChecked(factor == 4)
        self.menu.action_bin_8.setChecked(factor == 8)
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
        doing the second under the first's name; this is that name, now
        forwarding. Real bin-table binning is M5-16.
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
        """Toggle contour overlay visibility."""
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
        generator = ContourGenerator(contour_data, smooth=smooth_sigma)

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
        """Show pixel table dialog."""
        frame = self.frames.current_frame
        if frame is None or frame.image_data is None:
            self.status("No image loaded", 2000)
            return

        # Use image center as default
        analysis_data = self.analysis_image_data(frame)
        height, width = analysis_data.shape
        x, y = width // 2, height // 2

        dialog = PixelTableDialog(analysis_data, x, y, size=11, parent=self.window)
        dialog.exec()
        self.log_command("pixel_table")
