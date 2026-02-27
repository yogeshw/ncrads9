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
Menu bar for NCRADS9 application.

Author: Yogesh Wadadekar
"""

from typing import Dict, Optional

from PyQt6.QtGui import QAction, QActionGroup, QKeySequence
from PyQt6.QtWidgets import QMenuBar, QMenu, QWidget


class MenuBar(QMenuBar):
    """Menu bar with DS9-style menus."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the menu bar.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        self._setup_file_menu()
        self._setup_edit_menu()
        self._setup_view_menu()
        self._setup_frame_menu()
        self._setup_bin_menu()
        self._setup_zoom_menu()
        self._setup_scale_menu()
        self._setup_color_menu()
        self._setup_region_menu()
        self._setup_vo_menu()
        self._setup_wcs_menu()
        self._setup_analysis_menu()
        self._setup_help_menu()

        if self.vo_menu is not None:
            self.vo_menu.setVisible(True)

    def _setup_file_menu(self) -> None:
        """Set up the File menu."""
        self.file_menu: QMenu = self.addMenu("&File")

        self.action_open: QAction = QAction("&Open...", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.file_menu.addAction(self.action_open)

        self.action_save: QAction = QAction("&Save...", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.file_menu.addAction(self.action_save)

        self.action_save_as: QAction = QAction("Save &As...", self)
        self.action_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.file_menu.addAction(self.action_save_as)

        self.file_menu.addSeparator()

        self.action_export: QAction = QAction("&Export...", self)
        self.file_menu.addAction(self.action_export)

        self.action_print: QAction = QAction("&Print...", self)
        self.action_print.setShortcut(QKeySequence.StandardKey.Print)
        self.file_menu.addAction(self.action_print)

        self.file_menu.addSeparator()

        self.action_exit: QAction = QAction("E&xit", self)
        self.action_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self.file_menu.addAction(self.action_exit)

    def _setup_edit_menu(self) -> None:
        """Set up the Edit menu."""
        self.edit_menu: QMenu = self.addMenu("&Edit")

        self.action_undo: QAction = QAction("&Undo", self)
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.edit_menu.addAction(self.action_undo)

        self.action_redo: QAction = QAction("&Redo", self)
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.edit_menu.addAction(self.action_redo)

        self.edit_menu.addSeparator()

        self.action_cut: QAction = QAction("Cu&t", self)
        self.action_cut.setShortcut(QKeySequence.StandardKey.Cut)
        self.edit_menu.addAction(self.action_cut)

        self.action_copy: QAction = QAction("&Copy", self)
        self.action_copy.setShortcut(QKeySequence.StandardKey.Copy)
        self.edit_menu.addAction(self.action_copy)

        self.action_paste: QAction = QAction("&Paste", self)
        self.action_paste.setShortcut(QKeySequence.StandardKey.Paste)
        self.edit_menu.addAction(self.action_paste)

        self.edit_menu.addSeparator()

        self.action_preferences: QAction = QAction("Pre&ferences...", self)
        self.edit_menu.addAction(self.action_preferences)

    def _setup_view_menu(self) -> None:
        """Set up the View menu."""
        self.view_menu: QMenu = self.addMenu("&View")

        self.action_fullscreen: QAction = QAction("&Fullscreen", self)
        self.action_fullscreen.setShortcut("F11")
        self.action_fullscreen.setCheckable(True)
        self.view_menu.addAction(self.action_fullscreen)

        self.view_menu.addSeparator()

        self.action_show_toolbar: QAction = QAction("Show &Toolbar", self)
        self.action_show_toolbar.setCheckable(True)
        self.action_show_toolbar.setChecked(True)
        self.view_menu.addAction(self.action_show_toolbar)

        self.action_show_statusbar: QAction = QAction("Show &Status Bar", self)
        self.action_show_statusbar.setCheckable(True)
        self.action_show_statusbar.setChecked(True)
        self.view_menu.addAction(self.action_show_statusbar)

    def _setup_frame_menu(self) -> None:
        """Set up the Frame menu."""
        self.frame_menu: QMenu = self.addMenu("F&rame")

        self.action_new_frame: QAction = QAction("&New Frame", self)
        self.frame_menu.addAction(self.action_new_frame)
        self.action_new_frame_rgb: QAction = QAction("New Frame &RGB", self)
        self.frame_menu.addAction(self.action_new_frame_rgb)
        self.action_new_frame_hsv: QAction = QAction("New Frame H&SV", self)
        self.frame_menu.addAction(self.action_new_frame_hsv)
        self.action_new_frame_hls: QAction = QAction("New Frame H&LS", self)
        self.frame_menu.addAction(self.action_new_frame_hls)
        self.action_new_frame_3d: QAction = QAction("New Frame &3D", self)
        self.frame_menu.addAction(self.action_new_frame_3d)

        self.frame_menu.addSeparator()
        self.action_delete_frame: QAction = QAction("&Delete Frame", self)
        self.frame_menu.addAction(self.action_delete_frame)
        self.action_delete_all_frames: QAction = QAction("Delete &All Frames", self)
        self.frame_menu.addAction(self.action_delete_all_frames)

        self.frame_menu.addSeparator()
        self.action_clear_frame: QAction = QAction("C&lear Frame", self)
        self.frame_menu.addAction(self.action_clear_frame)
        self.action_reset_frame: QAction = QAction("&Reset Frame", self)
        self.frame_menu.addAction(self.action_reset_frame)
        self.action_refresh_frame: QAction = QAction("Re&fresh Frame", self)
        self.frame_menu.addAction(self.action_refresh_frame)

        self.frame_menu.addSeparator()

        self.frame_display_group = QActionGroup(self)
        self.frame_display_group.setExclusive(True)
        self.action_single_frame: QAction = QAction("&Single Frame", self)
        self.action_single_frame.setCheckable(True)
        self.action_single_frame.setChecked(True)
        self.frame_menu.addAction(self.action_single_frame)
        self.frame_display_group.addAction(self.action_single_frame)
        self.action_tile_frames: QAction = QAction("&Tile Frames", self)
        self.action_tile_frames.setCheckable(True)
        self.frame_menu.addAction(self.action_tile_frames)
        self.frame_display_group.addAction(self.action_tile_frames)
        self.action_blink_frames: QAction = QAction("&Blink Frames", self)
        self.action_blink_frames.setCheckable(True)
        self.frame_menu.addAction(self.action_blink_frames)
        self.frame_display_group.addAction(self.action_blink_frames)
        self.action_fade_frames: QAction = QAction("&Fade Frames", self)
        self.action_fade_frames.setCheckable(True)
        self.frame_menu.addAction(self.action_fade_frames)
        self.frame_display_group.addAction(self.action_fade_frames)

        self.frame_menu.addSeparator()

        self.match_menu: QMenu = self.frame_menu.addMenu("&Match")
        self.match_frame_menu: QMenu = self.match_menu.addMenu("&Frame")
        self.match_crosshair_menu: QMenu = self.match_menu.addMenu("&Crosshair")
        self.match_crop_menu: QMenu = self.match_menu.addMenu("&Crop")
        self.match_slice_menu: QMenu = self.match_menu.addMenu("S&lice")

        self.action_match_frame_wcs: QAction = QAction("&WCS", self)
        self.match_frame_menu.addAction(self.action_match_frame_wcs)
        self.match_frame_menu.addSeparator()
        self.action_match_image: QAction = QAction("&Image", self)
        self.match_frame_menu.addAction(self.action_match_image)
        self.action_match_frame_physical: QAction = QAction("&Physical", self)
        self.match_frame_menu.addAction(self.action_match_frame_physical)
        self.action_match_frame_amplifier: QAction = QAction("&Amplifier", self)
        self.match_frame_menu.addAction(self.action_match_frame_amplifier)
        self.action_match_frame_detector: QAction = QAction("&Detector", self)
        self.match_frame_menu.addAction(self.action_match_frame_detector)
        self.action_match_wcs = self.action_match_frame_wcs

        self.action_match_crosshair_wcs: QAction = QAction("&WCS", self)
        self.match_crosshair_menu.addAction(self.action_match_crosshair_wcs)
        self.match_crosshair_menu.addSeparator()
        self.action_match_crosshair_image: QAction = QAction("&Image", self)
        self.match_crosshair_menu.addAction(self.action_match_crosshair_image)
        self.action_match_crosshair_physical: QAction = QAction("&Physical", self)
        self.match_crosshair_menu.addAction(self.action_match_crosshair_physical)
        self.action_match_crosshair_amplifier: QAction = QAction("&Amplifier", self)
        self.match_crosshair_menu.addAction(self.action_match_crosshair_amplifier)
        self.action_match_crosshair_detector: QAction = QAction("&Detector", self)
        self.match_crosshair_menu.addAction(self.action_match_crosshair_detector)

        self.action_match_crop_wcs: QAction = QAction("&WCS", self)
        self.match_crop_menu.addAction(self.action_match_crop_wcs)
        self.match_crop_menu.addSeparator()
        self.action_match_crop_image: QAction = QAction("&Image", self)
        self.match_crop_menu.addAction(self.action_match_crop_image)
        self.action_match_crop_physical: QAction = QAction("&Physical", self)
        self.match_crop_menu.addAction(self.action_match_crop_physical)
        self.action_match_crop_amplifier: QAction = QAction("&Amplifier", self)
        self.match_crop_menu.addAction(self.action_match_crop_amplifier)
        self.action_match_crop_detector: QAction = QAction("&Detector", self)
        self.match_crop_menu.addAction(self.action_match_crop_detector)

        self.action_match_slice_wcs: QAction = QAction("&WCS", self)
        self.match_slice_menu.addAction(self.action_match_slice_wcs)
        self.match_slice_menu.addSeparator()
        self.action_match_slice_image: QAction = QAction("&Image", self)
        self.match_slice_menu.addAction(self.action_match_slice_image)

        self.action_match_bin: QAction = QAction("&Bin", self)
        self.match_menu.addAction(self.action_match_bin)
        self.action_match_axes_order: QAction = QAction("A&xes Order", self)
        self.match_menu.addAction(self.action_match_axes_order)
        self.action_match_scale: QAction = QAction("&Scale", self)
        self.match_menu.addAction(self.action_match_scale)
        self.action_match_scale_limits: QAction = QAction("Scale and &Limits", self)
        self.match_menu.addAction(self.action_match_scale_limits)
        self.action_match_colorbar: QAction = QAction("&Colorbar", self)
        self.match_menu.addAction(self.action_match_colorbar)
        self.action_match_block: QAction = QAction("&Block", self)
        self.match_menu.addAction(self.action_match_block)
        self.action_match_smooth: QAction = QAction("S&mooth", self)
        self.match_menu.addAction(self.action_match_smooth)
        self.action_match_3d: QAction = QAction("&3D", self)
        self.match_menu.addAction(self.action_match_3d)

        self.lock_menu: QMenu = self.frame_menu.addMenu("&Lock")
        self.lock_frame_menu: QMenu = self.lock_menu.addMenu("&Frame")
        self.lock_crosshair_menu: QMenu = self.lock_menu.addMenu("&Crosshair")
        self.lock_crop_menu: QMenu = self.lock_menu.addMenu("&Crop")
        self.lock_slice_menu: QMenu = self.lock_menu.addMenu("S&lice")

        self.lock_frame_group = QActionGroup(self)
        self.lock_frame_group.setExclusive(True)
        self.action_lock_frame_none: QAction = QAction("&None", self)
        self.action_lock_frame_none.setCheckable(True)
        self.action_lock_frame_none.setChecked(True)
        self.lock_frame_menu.addAction(self.action_lock_frame_none)
        self.lock_frame_group.addAction(self.action_lock_frame_none)
        self.lock_frame_menu.addSeparator()
        self.action_lock_frame_wcs: QAction = QAction("&WCS", self)
        self.action_lock_frame_wcs.setCheckable(True)
        self.lock_frame_menu.addAction(self.action_lock_frame_wcs)
        self.lock_frame_group.addAction(self.action_lock_frame_wcs)
        self.lock_frame_menu.addSeparator()
        self.action_lock_frame_image: QAction = QAction("&Image", self)
        self.action_lock_frame_image.setCheckable(True)
        self.lock_frame_menu.addAction(self.action_lock_frame_image)
        self.lock_frame_group.addAction(self.action_lock_frame_image)
        self.action_lock_frame_physical: QAction = QAction("&Physical", self)
        self.action_lock_frame_physical.setCheckable(True)
        self.lock_frame_menu.addAction(self.action_lock_frame_physical)
        self.lock_frame_group.addAction(self.action_lock_frame_physical)
        self.action_lock_frame_amplifier: QAction = QAction("&Amplifier", self)
        self.action_lock_frame_amplifier.setCheckable(True)
        self.lock_frame_menu.addAction(self.action_lock_frame_amplifier)
        self.lock_frame_group.addAction(self.action_lock_frame_amplifier)
        self.action_lock_frame_detector: QAction = QAction("&Detector", self)
        self.action_lock_frame_detector.setCheckable(True)
        self.lock_frame_menu.addAction(self.action_lock_frame_detector)
        self.lock_frame_group.addAction(self.action_lock_frame_detector)

        self.lock_crosshair_group = QActionGroup(self)
        self.lock_crosshair_group.setExclusive(True)
        self.action_lock_crosshair_none: QAction = QAction("&None", self)
        self.action_lock_crosshair_none.setCheckable(True)
        self.action_lock_crosshair_none.setChecked(True)
        self.lock_crosshair_menu.addAction(self.action_lock_crosshair_none)
        self.lock_crosshair_group.addAction(self.action_lock_crosshair_none)
        self.lock_crosshair_menu.addSeparator()
        self.action_lock_crosshair_wcs: QAction = QAction("&WCS", self)
        self.action_lock_crosshair_wcs.setCheckable(True)
        self.lock_crosshair_menu.addAction(self.action_lock_crosshair_wcs)
        self.lock_crosshair_group.addAction(self.action_lock_crosshair_wcs)
        self.lock_crosshair_menu.addSeparator()
        self.action_lock_crosshair_image: QAction = QAction("&Image", self)
        self.action_lock_crosshair_image.setCheckable(True)
        self.lock_crosshair_menu.addAction(self.action_lock_crosshair_image)
        self.lock_crosshair_group.addAction(self.action_lock_crosshair_image)
        self.action_lock_crosshair_physical: QAction = QAction("&Physical", self)
        self.action_lock_crosshair_physical.setCheckable(True)
        self.lock_crosshair_menu.addAction(self.action_lock_crosshair_physical)
        self.lock_crosshair_group.addAction(self.action_lock_crosshair_physical)
        self.action_lock_crosshair_amplifier: QAction = QAction("&Amplifier", self)
        self.action_lock_crosshair_amplifier.setCheckable(True)
        self.lock_crosshair_menu.addAction(self.action_lock_crosshair_amplifier)
        self.lock_crosshair_group.addAction(self.action_lock_crosshair_amplifier)
        self.action_lock_crosshair_detector: QAction = QAction("&Detector", self)
        self.action_lock_crosshair_detector.setCheckable(True)
        self.lock_crosshair_menu.addAction(self.action_lock_crosshair_detector)
        self.lock_crosshair_group.addAction(self.action_lock_crosshair_detector)

        self.lock_crop_group = QActionGroup(self)
        self.lock_crop_group.setExclusive(True)
        self.action_lock_crop_none: QAction = QAction("&None", self)
        self.action_lock_crop_none.setCheckable(True)
        self.action_lock_crop_none.setChecked(True)
        self.lock_crop_menu.addAction(self.action_lock_crop_none)
        self.lock_crop_group.addAction(self.action_lock_crop_none)
        self.lock_crop_menu.addSeparator()
        self.action_lock_crop_wcs: QAction = QAction("&WCS", self)
        self.action_lock_crop_wcs.setCheckable(True)
        self.lock_crop_menu.addAction(self.action_lock_crop_wcs)
        self.lock_crop_group.addAction(self.action_lock_crop_wcs)
        self.lock_crop_menu.addSeparator()
        self.action_lock_crop_image: QAction = QAction("&Image", self)
        self.action_lock_crop_image.setCheckable(True)
        self.lock_crop_menu.addAction(self.action_lock_crop_image)
        self.lock_crop_group.addAction(self.action_lock_crop_image)
        self.action_lock_crop_physical: QAction = QAction("&Physical", self)
        self.action_lock_crop_physical.setCheckable(True)
        self.lock_crop_menu.addAction(self.action_lock_crop_physical)
        self.lock_crop_group.addAction(self.action_lock_crop_physical)
        self.action_lock_crop_amplifier: QAction = QAction("&Amplifier", self)
        self.action_lock_crop_amplifier.setCheckable(True)
        self.lock_crop_menu.addAction(self.action_lock_crop_amplifier)
        self.lock_crop_group.addAction(self.action_lock_crop_amplifier)
        self.action_lock_crop_detector: QAction = QAction("&Detector", self)
        self.action_lock_crop_detector.setCheckable(True)
        self.lock_crop_menu.addAction(self.action_lock_crop_detector)
        self.lock_crop_group.addAction(self.action_lock_crop_detector)

        self.lock_slice_group = QActionGroup(self)
        self.lock_slice_group.setExclusive(True)
        self.action_lock_slice_none: QAction = QAction("&None", self)
        self.action_lock_slice_none.setCheckable(True)
        self.action_lock_slice_none.setChecked(True)
        self.lock_slice_menu.addAction(self.action_lock_slice_none)
        self.lock_slice_group.addAction(self.action_lock_slice_none)
        self.lock_slice_menu.addSeparator()
        self.action_lock_slice_wcs: QAction = QAction("&WCS", self)
        self.action_lock_slice_wcs.setCheckable(True)
        self.lock_slice_menu.addAction(self.action_lock_slice_wcs)
        self.lock_slice_group.addAction(self.action_lock_slice_wcs)
        self.lock_slice_menu.addSeparator()
        self.action_lock_slice_image: QAction = QAction("&Image", self)
        self.action_lock_slice_image.setCheckable(True)
        self.lock_slice_menu.addAction(self.action_lock_slice_image)
        self.lock_slice_group.addAction(self.action_lock_slice_image)

        self.action_lock_bin: QAction = QAction("&Bin", self)
        self.action_lock_bin.setCheckable(True)
        self.lock_menu.addAction(self.action_lock_bin)
        self.action_lock_axes_order: QAction = QAction("A&xes Order", self)
        self.action_lock_axes_order.setCheckable(True)
        self.lock_menu.addAction(self.action_lock_axes_order)
        self.action_lock_scale: QAction = QAction("&Scale", self)
        self.action_lock_scale.setCheckable(True)
        self.lock_menu.addAction(self.action_lock_scale)
        self.action_lock_scale_limits: QAction = QAction("Scale and &Limits", self)
        self.action_lock_scale_limits.setCheckable(True)
        self.lock_menu.addAction(self.action_lock_scale_limits)
        self.action_lock_colorbar: QAction = QAction("&Colorbar", self)
        self.action_lock_colorbar.setCheckable(True)
        self.lock_menu.addAction(self.action_lock_colorbar)
        self.action_lock_block: QAction = QAction("&Block", self)
        self.action_lock_block.setCheckable(True)
        self.lock_menu.addAction(self.action_lock_block)
        self.action_lock_smooth: QAction = QAction("S&mooth", self)
        self.action_lock_smooth.setCheckable(True)
        self.lock_menu.addAction(self.action_lock_smooth)
        self.action_lock_3d: QAction = QAction("&3D", self)
        self.action_lock_3d.setCheckable(True)
        self.lock_menu.addAction(self.action_lock_3d)

        self.frame_menu.addSeparator()

        self.goto_frame_menu: QMenu = self.frame_menu.addMenu("&Goto Frame")
        self.show_hide_frames_menu: QMenu = self.frame_menu.addMenu("S&how/Hide Frames")
        self.action_show_all_frames: QAction = QAction("Show &All", self)
        self.show_hide_frames_menu.addAction(self.action_show_all_frames)
        self.action_hide_all_frames: QAction = QAction("Hide A&ll", self)
        self.show_hide_frames_menu.addAction(self.action_hide_all_frames)
        self.show_hide_frames_menu.addSeparator()
        self.move_frame_menu: QMenu = self.frame_menu.addMenu("&Move Frame")
        self.action_move_frame_first: QAction = QAction("&First", self)
        self.move_frame_menu.addAction(self.action_move_frame_first)
        self.action_move_frame_back: QAction = QAction("&Back", self)
        self.move_frame_menu.addAction(self.action_move_frame_back)
        self.action_move_frame_forward: QAction = QAction("&Forward", self)
        self.move_frame_menu.addAction(self.action_move_frame_forward)
        self.action_move_frame_last: QAction = QAction("&Last", self)
        self.move_frame_menu.addAction(self.action_move_frame_last)

        self.frame_menu.addSeparator()

        self.action_first_frame: QAction = QAction("F&irst Frame", self)
        self.frame_menu.addAction(self.action_first_frame)
        self.action_prev_frame: QAction = QAction("&Previous Frame", self)
        self.frame_menu.addAction(self.action_prev_frame)
        self.action_next_frame: QAction = QAction("&Next Frame", self)
        self.frame_menu.addAction(self.action_next_frame)
        self.action_last_frame: QAction = QAction("&Last Frame", self)
        self.frame_menu.addAction(self.action_last_frame)

        self.frame_menu.addSeparator()
        self.action_frame_cube_dialog: QAction = QAction("&Cube", self)
        self.frame_menu.addAction(self.action_frame_cube_dialog)
        self.action_frame_rgb_dialog: QAction = QAction("&RGB", self)
        self.frame_menu.addAction(self.action_frame_rgb_dialog)
        self.action_frame_hsv_dialog: QAction = QAction("&HSV", self)
        self.frame_menu.addAction(self.action_frame_hsv_dialog)
        self.action_frame_hls_dialog: QAction = QAction("&HLS", self)
        self.frame_menu.addAction(self.action_frame_hls_dialog)
        self.action_frame_3d_dialog: QAction = QAction("&3D", self)
        self.frame_menu.addAction(self.action_frame_3d_dialog)

        self.frame_menu.addSeparator()
        self.frame_params_menu: QMenu = self.frame_menu.addMenu("Frame &Parameters")
        self.tile_params_menu: QMenu = self.frame_params_menu.addMenu("&Tile")
        self.blink_interval_menu: QMenu = self.frame_params_menu.addMenu("&Blink Interval")
        self.fade_interval_menu: QMenu = self.frame_params_menu.addMenu("&Fade Interval")

        self.tile_mode_group = QActionGroup(self)
        self.tile_mode_group.setExclusive(True)
        self.action_tile_mode_grid: QAction = QAction("&Grid", self)
        self.action_tile_mode_grid.setCheckable(True)
        self.action_tile_mode_grid.setChecked(True)
        self.tile_params_menu.addAction(self.action_tile_mode_grid)
        self.tile_mode_group.addAction(self.action_tile_mode_grid)
        self.action_tile_mode_columns: QAction = QAction("&Columns", self)
        self.action_tile_mode_columns.setCheckable(True)
        self.tile_params_menu.addAction(self.action_tile_mode_columns)
        self.tile_mode_group.addAction(self.action_tile_mode_columns)
        self.action_tile_mode_rows: QAction = QAction("&Rows", self)
        self.action_tile_mode_rows.setCheckable(True)
        self.tile_params_menu.addAction(self.action_tile_mode_rows)
        self.tile_mode_group.addAction(self.action_tile_mode_rows)

        self.blink_interval_group = QActionGroup(self)
        self.blink_interval_group.setExclusive(True)
        self.blink_interval_actions: Dict[int, QAction] = {}
        for label, ms in (
            (".125 Seconds", 125),
            (".25 Seconds", 250),
            (".5 Seconds", 500),
            ("1 Second", 1000),
            ("2 Seconds", 2000),
            ("4 Seconds", 4000),
            ("8 Seconds", 8000),
            ("16 Seconds", 16000),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            if ms == 500:
                action.setChecked(True)
            action.setData(ms)
            self.blink_interval_menu.addAction(action)
            self.blink_interval_group.addAction(action)
            self.blink_interval_actions[ms] = action

        self.fade_interval_group = QActionGroup(self)
        self.fade_interval_group.setExclusive(True)
        self.fade_interval_actions: Dict[int, QAction] = {}
        for label, ms in (
            ("1 Second", 1000),
            ("2 Seconds", 2000),
            ("4 Seconds", 4000),
            ("8 Seconds", 8000),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            if ms == 1000:
                action.setChecked(True)
            action.setData(ms)
            self.fade_interval_menu.addAction(action)
            self.fade_interval_group.addAction(action)
            self.fade_interval_actions[ms] = action

    def _setup_bin_menu(self) -> None:
        """Set up the Bin menu."""
        self.bin_menu: QMenu = self.addMenu("&Bin")

        self.action_bin_1: QAction = QAction("1x1", self)
        self.action_bin_1.setCheckable(True)
        self.action_bin_1.setChecked(True)
        self.bin_menu.addAction(self.action_bin_1)

        self.action_bin_2: QAction = QAction("2x2", self)
        self.action_bin_2.setCheckable(True)
        self.bin_menu.addAction(self.action_bin_2)

        self.action_bin_4: QAction = QAction("4x4", self)
        self.action_bin_4.setCheckable(True)
        self.bin_menu.addAction(self.action_bin_4)

        self.action_bin_8: QAction = QAction("8x8", self)
        self.action_bin_8.setCheckable(True)
        self.bin_menu.addAction(self.action_bin_8)

    def _setup_zoom_menu(self) -> None:
        """Set up the Zoom menu."""
        self.zoom_menu: QMenu = self.addMenu("&Zoom")

        self.action_zoom_in: QAction = QAction("Zoom &In", self)
        self.action_zoom_in.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self.zoom_menu.addAction(self.action_zoom_in)

        self.action_zoom_out: QAction = QAction("Zoom &Out", self)
        self.action_zoom_out.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self.zoom_menu.addAction(self.action_zoom_out)

        self.action_zoom_fit: QAction = QAction("Zoom to &Fit", self)
        self.zoom_menu.addAction(self.action_zoom_fit)

        self.action_zoom_1: QAction = QAction("Zoom &1:1", self)
        self.zoom_menu.addAction(self.action_zoom_1)

        self.zoom_menu.addSeparator()

        self.action_zoom_center: QAction = QAction("&Center", self)
        self.zoom_menu.addAction(self.action_zoom_center)

    def _setup_scale_menu(self) -> None:
        """Set up the Scale menu."""
        self.scale_menu: QMenu = self.addMenu("&Scale")

        self.action_scale_linear: QAction = QAction("&Linear", self)
        self.action_scale_linear.setCheckable(True)
        self.action_scale_linear.setChecked(True)
        self.scale_menu.addAction(self.action_scale_linear)

        self.action_scale_log: QAction = QAction("Lo&g", self)
        self.action_scale_log.setCheckable(True)
        self.scale_menu.addAction(self.action_scale_log)

        self.action_scale_sqrt: QAction = QAction("&Sqrt", self)
        self.action_scale_sqrt.setCheckable(True)
        self.scale_menu.addAction(self.action_scale_sqrt)

        self.action_scale_squared: QAction = QAction("S&quared", self)
        self.action_scale_squared.setCheckable(True)
        self.scale_menu.addAction(self.action_scale_squared)

        self.action_scale_asinh: QAction = QAction("&Asinh", self)
        self.action_scale_asinh.setCheckable(True)
        self.scale_menu.addAction(self.action_scale_asinh)

        self.action_scale_histeq: QAction = QAction("&Histogram Equalization", self)
        self.action_scale_histeq.setCheckable(True)
        self.scale_menu.addAction(self.action_scale_histeq)

        self.scale_menu.addSeparator()

        self.action_scale_minmax: QAction = QAction("&MinMax", self)
        self.scale_menu.addAction(self.action_scale_minmax)

        self.action_scale_zscale: QAction = QAction("&ZScale", self)
        self.scale_menu.addAction(self.action_scale_zscale)

        self.action_scale_params: QAction = QAction("&Parameters...", self)
        self.scale_menu.addAction(self.action_scale_params)

    def _setup_color_menu(self) -> None:
        """Set up the Color menu."""
        self.color_menu: QMenu = self.addMenu("&Color")
        self.colormap_action_group = QActionGroup(self)
        self.colormap_action_group.setExclusive(True)
        self.colormap_actions: Dict[str, QAction] = {}

        default_maps = [
            ("Gray", "grey"),
            ("Red", "red"),
            ("Green", "green"),
            ("Blue", "blue"),
            ("A", "a"),
            ("B", "b"),
            ("BB", "bb"),
            ("HE", "he"),
            ("I8", "i8"),
            ("AIPS0", "aips0"),
            ("SLS", "sls"),
            ("HSV", "hsv"),
            ("Heat", "heat"),
            ("Cool", "cool"),
            ("Rainbow", "rainbow"),
            ("Standard", "standard"),
            ("Staircase", "staircase"),
            ("Color", "color"),
        ]
        for label, cmap_name in default_maps:
            self._add_colormap_action(self.color_menu, label, cmap_name, checked=(cmap_name == "grey"))

        self.color_menu.addSeparator()

        self.colormap_submenus: Dict[str, QMenu] = {}
        category_maps = {
            "Matplotlib Uniform": [("Viridis", "viridis"), ("Plasma", "plasma"), ("Inferno", "inferno"), ("Magma", "magma")],
        }
        for category, maps in category_maps.items():
            submenu = self.color_menu.addMenu(category)
            self.colormap_submenus[category] = submenu
            for label, cmap_name in maps:
                self._add_colormap_action(submenu, label, cmap_name)

        self.user_colormap_menu: QMenu = self.color_menu.addMenu("&User")
        self.action_load_user_colormap: QAction = QAction("&Load Colormap...", self)
        self.user_colormap_menu.addAction(self.action_load_user_colormap)
        self.action_save_user_colormap: QAction = QAction("&Save Current Colormap...", self)
        self.user_colormap_menu.addAction(self.action_save_user_colormap)
        self.user_colormap_menu.addSeparator()

        self.color_menu.addSeparator()

        self.action_invert_colormap: QAction = QAction("&Invert Colormap", self)
        self.action_invert_colormap.setCheckable(True)
        self.color_menu.addAction(self.action_invert_colormap)

        self.action_reset_colormap: QAction = QAction("&Reset Colormap", self)
        self.color_menu.addAction(self.action_reset_colormap)

        self.color_menu.addSeparator()

        self.action_colorbar: QAction = QAction("Show Color&bar", self)
        self.action_colorbar.setCheckable(True)
        self.action_colorbar.setChecked(True)
        self.color_menu.addAction(self.action_colorbar)

        self.colorbar_submenu: QMenu = self.color_menu.addMenu("Colorbar &Options")

        self.colorbar_orientation_menu: QMenu = self.colorbar_submenu.addMenu("&Orientation")
        self.colorbar_orientation_group = QActionGroup(self)
        self.colorbar_orientation_group.setExclusive(True)
        self.action_colorbar_horizontal: QAction = QAction("&Horizontal", self)
        self.action_colorbar_horizontal.setCheckable(True)
        self.action_colorbar_vertical: QAction = QAction("&Vertical", self)
        self.action_colorbar_vertical.setCheckable(True)
        self.action_colorbar_vertical.setChecked(True)
        self.colorbar_orientation_menu.addAction(self.action_colorbar_horizontal)
        self.colorbar_orientation_menu.addAction(self.action_colorbar_vertical)
        self.colorbar_orientation_group.addAction(self.action_colorbar_horizontal)
        self.colorbar_orientation_group.addAction(self.action_colorbar_vertical)

        self.colorbar_numerics_menu: QMenu = self.colorbar_submenu.addMenu("&Numerics")
        self.action_colorbar_numerics_show: QAction = QAction("&Show", self)
        self.action_colorbar_numerics_show.setCheckable(True)
        self.action_colorbar_numerics_show.setChecked(True)
        self.colorbar_numerics_menu.addAction(self.action_colorbar_numerics_show)
        self.colorbar_numerics_menu.addSeparator()
        self.colorbar_spacing_group = QActionGroup(self)
        self.colorbar_spacing_group.setExclusive(True)
        self.action_colorbar_space_value: QAction = QAction("Space Equal &Value", self)
        self.action_colorbar_space_value.setCheckable(True)
        self.action_colorbar_space_value.setChecked(True)
        self.action_colorbar_space_distance: QAction = QAction("Space Equal &Distance", self)
        self.action_colorbar_space_distance.setCheckable(True)
        self.colorbar_numerics_menu.addAction(self.action_colorbar_space_value)
        self.colorbar_numerics_menu.addAction(self.action_colorbar_space_distance)
        self.colorbar_spacing_group.addAction(self.action_colorbar_space_value)
        self.colorbar_spacing_group.addAction(self.action_colorbar_space_distance)

        self.colorbar_font_menu: QMenu = self.colorbar_submenu.addMenu("&Font")
        self.colorbar_font_group = QActionGroup(self)
        self.colorbar_font_group.setExclusive(True)
        self.action_colorbar_font_small: QAction = QAction("&Small", self)
        self.action_colorbar_font_small.setCheckable(True)
        self.action_colorbar_font_medium: QAction = QAction("&Medium", self)
        self.action_colorbar_font_medium.setCheckable(True)
        self.action_colorbar_font_medium.setChecked(True)
        self.action_colorbar_font_large: QAction = QAction("&Large", self)
        self.action_colorbar_font_large.setCheckable(True)
        self.colorbar_font_menu.addAction(self.action_colorbar_font_small)
        self.colorbar_font_menu.addAction(self.action_colorbar_font_medium)
        self.colorbar_font_menu.addAction(self.action_colorbar_font_large)
        self.colorbar_font_group.addAction(self.action_colorbar_font_small)
        self.colorbar_font_group.addAction(self.action_colorbar_font_medium)
        self.colorbar_font_group.addAction(self.action_colorbar_font_large)

        self.colorbar_submenu.addSeparator()
        self.action_colorbar_size: QAction = QAction("&Size...", self)
        self.colorbar_submenu.addAction(self.action_colorbar_size)
        self.action_colorbar_ticks: QAction = QAction("&Number of Ticks...", self)
        self.colorbar_submenu.addAction(self.action_colorbar_ticks)

        self.color_menu.addSeparator()
        self.action_colormap_params: QAction = QAction("Colormap &Parameters...", self)
        self.color_menu.addAction(self.action_colormap_params)

        self.action_cmap_gray = self.colormap_actions["grey"]
        self.action_cmap_heat = self.colormap_actions["heat"]
        self.action_cmap_cool = self.colormap_actions["cool"]
        self.action_cmap_rainbow = self.colormap_actions["rainbow"]
        self.action_cmap_viridis = self.colormap_actions["viridis"]
        self.action_cmap_plasma = self.colormap_actions["plasma"]
        self.action_cmap_inferno = self.colormap_actions["inferno"]
        self.action_cmap_magma = self.colormap_actions["magma"]

    def _add_colormap_action(
        self,
        menu: QMenu,
        label: str,
        colormap_name: str,
        checked: bool = False,
    ) -> QAction:
        """Create and register a colormap action."""
        action = QAction(label, self)
        action.setCheckable(True)
        action.setChecked(checked)
        menu.addAction(action)
        self.colormap_action_group.addAction(action)
        self.colormap_actions[colormap_name.lower()] = action
        return action

    def add_user_colormap_action(self, colormap_name: str) -> QAction:
        """Add or return a runtime-loaded user colormap action."""
        cmap_key = colormap_name.lower()
        if cmap_key in self.colormap_actions:
            return self.colormap_actions[cmap_key]
        return self._add_colormap_action(self.user_colormap_menu, colormap_name, cmap_key)

    def _setup_region_menu(self) -> None:
        """Set up the Region menu."""
        self.region_menu: QMenu = self.addMenu("&Region")

        self.action_region_none: QAction = QAction("&None", self)
        self.region_menu.addAction(self.action_region_none)
        self.region_menu.addSeparator()

        self.action_region_circle: QAction = QAction("&Circle", self)
        self.region_menu.addAction(self.action_region_circle)

        self.action_region_ellipse: QAction = QAction("&Ellipse", self)
        self.region_menu.addAction(self.action_region_ellipse)

        self.action_region_box: QAction = QAction("&Box", self)
        self.region_menu.addAction(self.action_region_box)

        self.action_region_polygon: QAction = QAction("&Polygon", self)
        self.region_menu.addAction(self.action_region_polygon)

        self.action_region_line: QAction = QAction("&Line", self)
        self.region_menu.addAction(self.action_region_line)

        self.action_region_point: QAction = QAction("Poi&nt", self)
        self.region_menu.addAction(self.action_region_point)

        self.region_menu.addSeparator()

        self.action_region_load: QAction = QAction("&Load...", self)
        self.region_menu.addAction(self.action_region_load)

        self.action_region_save: QAction = QAction("&Save...", self)
        self.region_menu.addAction(self.action_region_save)

        self.action_region_delete_all: QAction = QAction("&Delete All", self)
        self.region_menu.addAction(self.action_region_delete_all)

    def _setup_vo_menu(self) -> None:
        """Set up the VO menu."""
        vo_action = self.addMenu("&VO")
        self.vo_menu: QMenu = vo_action
        self.vo_menu.setTitle("&VO")
        self.vo_menu.menuAction().setVisible(True)
        self.vo_menu.menuAction().setEnabled(True)

        self.siap_menu: QMenu = self.vo_menu.addMenu("&SIAP")
        self.action_siap_2mass: QAction = QAction("2MASS &Image...", self)
        self.siap_menu.addAction(self.action_siap_2mass)

        self.catalog_menu: QMenu = self.vo_menu.addMenu("&Catalog")
        self.action_catalog_vizier: QAction = QAction("&VizieR...", self)
        self.catalog_menu.addAction(self.action_catalog_vizier)

        self.samp_menu: QMenu = self.vo_menu.addMenu("&SAMP")
        self.action_samp_connect: QAction = QAction("&Connect", self)
        self.samp_menu.addAction(self.action_samp_connect)
        self.action_samp_disconnect: QAction = QAction("&Disconnect", self)
        self.samp_menu.addAction(self.action_samp_disconnect)
        self.samp_menu.addSeparator()
        self.action_samp_marker_color: QAction = QAction("Marker &Color...", self)
        self.samp_menu.addAction(self.action_samp_marker_color)
        self.action_samp_marker_shape: QAction = QAction("Marker &Shape...", self)
        self.samp_menu.addAction(self.action_samp_marker_shape)
        self.action_samp_marker_size: QAction = QAction("Marker Si&ze...", self)
        self.samp_menu.addAction(self.action_samp_marker_size)

    def _setup_wcs_menu(self) -> None:
        """Set up the WCS menu."""
        self.wcs_menu: QMenu = self.addMenu("&WCS")

        self.wcs_system_group = QActionGroup(self)
        self.wcs_system_group.setExclusive(True)

        self.action_wcs_fk5: QAction = QAction("FK&5", self)
        self.action_wcs_fk5.setCheckable(True)
        self.action_wcs_fk5.setChecked(True)
        self.wcs_menu.addAction(self.action_wcs_fk5)
        self.wcs_system_group.addAction(self.action_wcs_fk5)

        self.action_wcs_fk4: QAction = QAction("FK&4", self)
        self.action_wcs_fk4.setCheckable(True)
        self.wcs_menu.addAction(self.action_wcs_fk4)
        self.wcs_system_group.addAction(self.action_wcs_fk4)

        self.action_wcs_icrs: QAction = QAction("&ICRS", self)
        self.action_wcs_icrs.setCheckable(True)
        self.wcs_menu.addAction(self.action_wcs_icrs)
        self.wcs_system_group.addAction(self.action_wcs_icrs)

        self.action_wcs_galactic: QAction = QAction("&Galactic", self)
        self.action_wcs_galactic.setCheckable(True)
        self.wcs_menu.addAction(self.action_wcs_galactic)
        self.wcs_system_group.addAction(self.action_wcs_galactic)

        self.action_wcs_ecliptic: QAction = QAction("&Ecliptic", self)
        self.action_wcs_ecliptic.setCheckable(True)
        self.wcs_menu.addAction(self.action_wcs_ecliptic)
        self.wcs_system_group.addAction(self.action_wcs_ecliptic)

        self.wcs_menu.addSeparator()

        self.action_wcs_sexagesimal: QAction = QAction("&Sexagesimal", self)
        self.action_wcs_sexagesimal.setCheckable(True)
        self.action_wcs_sexagesimal.setChecked(True)
        self.wcs_menu.addAction(self.action_wcs_sexagesimal)

        self.action_wcs_degrees: QAction = QAction("&Degrees", self)
        self.action_wcs_degrees.setCheckable(True)
        self.wcs_menu.addAction(self.action_wcs_degrees)

        self.wcs_menu.addSeparator()

        self.action_show_direction_arrows: QAction = QAction("Show &Direction Arrows", self)
        self.action_show_direction_arrows.setCheckable(True)
        self.action_show_direction_arrows.setChecked(True)
        self.wcs_menu.addAction(self.action_show_direction_arrows)

    def _setup_analysis_menu(self) -> None:
        """Set up the Analysis menu."""
        self.analysis_menu: QMenu = self.addMenu("&Analysis")

        self.action_pixel_table: QAction = QAction("&Pixel Table", self)
        self.analysis_menu.addAction(self.action_pixel_table)

        self.action_name_resolution: QAction = QAction("&Name Resolution...", self)
        self.analysis_menu.addAction(self.action_name_resolution)

        self.action_statistics: QAction = QAction("&Statistics", self)
        self.analysis_menu.addAction(self.action_statistics)

        self.action_histogram: QAction = QAction("&Histogram", self)
        self.analysis_menu.addAction(self.action_histogram)

        self.action_radial_profile: QAction = QAction("&Radial Profile", self)
        self.analysis_menu.addAction(self.action_radial_profile)

        self.analysis_menu.addSeparator()

        self.action_mask_params: QAction = QAction("&Mask Parameters...", self)
        self.analysis_menu.addAction(self.action_mask_params)

        self.action_crosshair_params: QAction = QAction("C&rosshair Parameters...", self)
        self.analysis_menu.addAction(self.action_crosshair_params)

        self.action_graph_params: QAction = QAction("&Graph Parameters...", self)
        self.analysis_menu.addAction(self.action_graph_params)

        self.analysis_menu.addSeparator()

        self.action_contours: QAction = QAction("&Contours", self)
        self.action_contours.setCheckable(True)
        self.analysis_menu.addAction(self.action_contours)

        self.action_contour_params: QAction = QAction("Contour &Parameters...", self)
        self.analysis_menu.addAction(self.action_contour_params)

        self.analysis_menu.addSeparator()

        self.action_coordinate_grid: QAction = QAction("Coordinate &Grid", self)
        self.action_coordinate_grid.setCheckable(True)
        self.analysis_menu.addAction(self.action_coordinate_grid)

        self.action_coordinate_grid_params: QAction = QAction("Coordinate Grid P&arameters...", self)
        self.analysis_menu.addAction(self.action_coordinate_grid_params)

        self.analysis_menu.addSeparator()

        self.analysis_block_menu: QMenu = self.analysis_menu.addMenu("&Block")
        self.action_block_in: QAction = QAction("Block &In", self)
        self.analysis_block_menu.addAction(self.action_block_in)
        self.action_block_out: QAction = QAction("Block &Out", self)
        self.analysis_block_menu.addAction(self.action_block_out)
        self.action_block_fit: QAction = QAction("Block &Fit", self)
        self.analysis_block_menu.addAction(self.action_block_fit)
        self.analysis_block_menu.addSeparator()
        self.analysis_block_group = QActionGroup(self)
        self.analysis_block_group.setExclusive(True)
        self.action_block_1: QAction = QAction("Block &1", self)
        self.action_block_1.setCheckable(True)
        self.action_block_1.setChecked(True)
        self.action_block_2: QAction = QAction("Block &2", self)
        self.action_block_2.setCheckable(True)
        self.action_block_4: QAction = QAction("Block &4", self)
        self.action_block_4.setCheckable(True)
        self.action_block_8: QAction = QAction("Block &8", self)
        self.action_block_8.setCheckable(True)
        self.action_block_16: QAction = QAction("Block 1&6", self)
        self.action_block_16.setCheckable(True)
        self.action_block_32: QAction = QAction("Block 3&2", self)
        self.action_block_32.setCheckable(True)
        for action in (
            self.action_block_1,
            self.action_block_2,
            self.action_block_4,
            self.action_block_8,
            self.action_block_16,
            self.action_block_32,
        ):
            self.analysis_block_menu.addAction(action)
            self.analysis_block_group.addAction(action)

        self.action_block_params: QAction = QAction("Block Parameters...", self)
        self.analysis_menu.addAction(self.action_block_params)

        self.analysis_menu.addSeparator()

        self.action_smooth: QAction = QAction("&Smooth", self)
        self.action_smooth.setCheckable(True)
        self.analysis_menu.addAction(self.action_smooth)
        self.action_smooth_params: QAction = QAction("Smooth Parameters...", self)
        self.analysis_menu.addAction(self.action_smooth_params)

        self.analysis_menu.addSeparator()
        self.analysis_image_servers_menu: QMenu = self.analysis_menu.addMenu("Image &Servers")
        self.action_analysis_2mass: QAction = QAction("2MASS &Image...", self)
        self.analysis_image_servers_menu.addAction(self.action_analysis_2mass)
        self.analysis_catalogs_menu: QMenu = self.analysis_menu.addMenu("&Catalogs")
        self.action_analysis_vizier: QAction = QAction("&VizieR...", self)
        self.analysis_catalogs_menu.addAction(self.action_analysis_vizier)

        self.analysis_menu.addSeparator()
        self.action_catalog_tool: QAction = QAction("Catalog &Tool", self)
        self.analysis_menu.addAction(self.action_catalog_tool)
        self.analysis_plot_tool_menu: QMenu = self.analysis_menu.addMenu("P&lot Tool")
        self.action_plot_tool_line: QAction = QAction("&Line", self)
        self.analysis_plot_tool_menu.addAction(self.action_plot_tool_line)
        self.action_plot_tool_bar: QAction = QAction("&Bar", self)
        self.analysis_plot_tool_menu.addAction(self.action_plot_tool_bar)

        self.analysis_menu.addSeparator()
        self.action_virtual_observatory: QAction = QAction("&Virtual Observatory", self)
        self.analysis_menu.addAction(self.action_virtual_observatory)
        self.action_web_browser: QAction = QAction("&Web Browser", self)
        self.analysis_menu.addAction(self.action_web_browser)

        self.analysis_menu.addSeparator()
        self.action_analysis_command_log: QAction = QAction("Analysis Command &Log", self)
        self.action_analysis_command_log.setCheckable(True)
        self.analysis_menu.addAction(self.action_analysis_command_log)

        self.analysis_menu.addSeparator()
        self.action_load_analysis_commands: QAction = QAction("&Load Analysis Commands...", self)
        self.analysis_menu.addAction(self.action_load_analysis_commands)
        self.action_clear_analysis_commands: QAction = QAction("C&lear Analysis Commands", self)
        self.analysis_menu.addAction(self.action_clear_analysis_commands)

        self.analysis_menu.addSeparator()
        self.action_fits_header: QAction = QAction("FITS &Header", self)
        self.analysis_menu.addAction(self.action_fits_header)

    def _setup_help_menu(self) -> None:
        """Set up the Help menu."""
        self.help_menu: QMenu = self.addMenu("&Help")

        self.action_help_contents: QAction = QAction("&Contents", self)
        self.action_help_contents.setShortcut(QKeySequence.StandardKey.HelpContents)
        self.help_menu.addAction(self.action_help_contents)

        self.action_keyboard_shortcuts: QAction = QAction("&Keyboard Shortcuts", self)
        self.help_menu.addAction(self.action_keyboard_shortcuts)

        self.help_menu.addSeparator()

        self.action_about: QAction = QAction("&About NCRADS9", self)
        self.help_menu.addAction(self.action_about)

        self.action_about_qt: QAction = QAction("About &Qt", self)
        self.help_menu.addAction(self.action_about_qt)
