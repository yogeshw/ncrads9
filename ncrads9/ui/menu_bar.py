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

from typing import Optional

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

        self.action_delete_frame: QAction = QAction("&Delete Frame", self)
        self.frame_menu.addAction(self.action_delete_frame)

        self.frame_menu.addSeparator()

        self.action_first_frame: QAction = QAction("&First", self)
        self.frame_menu.addAction(self.action_first_frame)

        self.action_prev_frame: QAction = QAction("&Previous", self)
        self.frame_menu.addAction(self.action_prev_frame)

        self.action_next_frame: QAction = QAction("&Next", self)
        self.frame_menu.addAction(self.action_next_frame)

        self.action_last_frame: QAction = QAction("&Last", self)
        self.frame_menu.addAction(self.action_last_frame)

        self.frame_menu.addSeparator()

        self.match_menu: QMenu = self.frame_menu.addMenu("&Match")
        self.action_match_image: QAction = QAction("&Image", self)
        self.match_menu.addAction(self.action_match_image)
        self.action_match_wcs: QAction = QAction("&WCS", self)
        self.match_menu.addAction(self.action_match_wcs)

        self.frame_menu.addSeparator()

        self.action_tile_frames: QAction = QAction("&Tile", self)
        self.frame_menu.addAction(self.action_tile_frames)

        self.action_blink_frames: QAction = QAction("&Blink", self)
        self.action_blink_frames.setCheckable(True)
        self.frame_menu.addAction(self.action_blink_frames)

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

        self.colormap_submenu: QMenu = self.color_menu.addMenu("&Colormap")

        self.action_cmap_gray: QAction = QAction("&Gray", self)
        self.action_cmap_gray.setCheckable(True)
        self.action_cmap_gray.setChecked(True)
        self.colormap_submenu.addAction(self.action_cmap_gray)

        self.action_cmap_heat: QAction = QAction("&Heat", self)
        self.action_cmap_heat.setCheckable(True)
        self.colormap_submenu.addAction(self.action_cmap_heat)

        self.action_cmap_cool: QAction = QAction("&Cool", self)
        self.action_cmap_cool.setCheckable(True)
        self.colormap_submenu.addAction(self.action_cmap_cool)

        self.action_cmap_rainbow: QAction = QAction("&Rainbow", self)
        self.action_cmap_rainbow.setCheckable(True)
        self.colormap_submenu.addAction(self.action_cmap_rainbow)

        self.action_cmap_viridis: QAction = QAction("&Viridis", self)
        self.action_cmap_viridis.setCheckable(True)
        self.colormap_submenu.addAction(self.action_cmap_viridis)

        self.color_menu.addSeparator()

        self.action_invert_colormap: QAction = QAction("&Invert", self)
        self.action_invert_colormap.setCheckable(True)
        self.color_menu.addAction(self.action_invert_colormap)

        self.action_colorbar: QAction = QAction("Color&bar", self)
        self.action_colorbar.setCheckable(True)
        self.color_menu.addAction(self.action_colorbar)

    def _setup_region_menu(self) -> None:
        """Set up the Region menu."""
        self.region_menu: QMenu = self.addMenu("&Region")

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

    def _setup_analysis_menu(self) -> None:
        """Set up the Analysis menu."""
        self.analysis_menu: QMenu = self.addMenu("&Analysis")

        self.action_statistics: QAction = QAction("&Statistics", self)
        self.analysis_menu.addAction(self.action_statistics)

        self.action_histogram: QAction = QAction("&Histogram", self)
        self.analysis_menu.addAction(self.action_histogram)

        self.action_radial_profile: QAction = QAction("&Radial Profile", self)
        self.analysis_menu.addAction(self.action_radial_profile)

        self.action_contours: QAction = QAction("&Contours", self)
        self.analysis_menu.addAction(self.action_contours)

        self.analysis_menu.addSeparator()

        self.action_pixel_table: QAction = QAction("&Pixel Table", self)
        self.analysis_menu.addAction(self.action_pixel_table)

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
