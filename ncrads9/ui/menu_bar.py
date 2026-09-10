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


from PyQt6.QtGui import QAction, QActionGroup, QKeySequence
from PyQt6.QtWidgets import QMenu, QMenuBar, QWidget

from ..catalogs.footprints import SERVERS as FOOTPRINT_SERVERS
from ..catalogs.servers import SECTIONS as CATALOG_SECTIONS
from ..catalogs.servers import in_section as catalogs_in_section
from ..colormaps.bundled import CATEGORIES, colormap_label
from ..core.bin_table import BUFFER_SIZES, DEFAULT_BUFFER_SIZE
from ..image_servers.servers import SERVERS as IMAGE_SERVERS
from ..regions.region_template import bundled_templates
from .layout.view_state import DEFAULT_INFO_FIELDS, WCS_SUFFIXES

#: The shapes the Region menu's Shape cascade offers, in DS9's order. Every
#: one of DS9's nineteen descriptions except Composite, which has a cascade
#: of its own, and Text, which is created by typing rather than dragging.
REGION_SHAPES: tuple[tuple[str, str], ...] = (
    ("circle", "&Circle"),
    ("ellipse", "&Ellipse"),
    ("box", "&Box"),
    ("polygon", "&Polygon"),
    ("point", "Poi&nt"),
    ("line", "&Line"),
    ("vector", "&Vector"),
    ("segment", "Se&gment"),
    ("text", "&Text"),
    ("ruler", "&Ruler"),
    ("compass", "Co&mpass"),
    ("projection", "Pro&jection"),
    ("annulus", "&Annulus"),
    ("ellipseannulus", "Ellipse Ann&ulus"),
    ("boxannulus", "Box Annul&us"),
    ("panda", "Pa&nda"),
    ("epanda", "Epa&nda"),
    ("bpanda", "Bpand&a"),
)

#: The archive web links DS9's Archives menu offers, grouped as it groups
#: them. DS9's own handlers for these (`HVArchSIMBADSAO` and friends) do not
#: exist in 8.x -- the entries are there and do nothing -- so the endpoints
#: here are the services' current ones.
ARCHIVE_LINKS: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...] = (
    (
        "SIMBAD",
        (
            ("simbad_sao", "&SAO", "https://simbad.cfa.harvard.edu/simbad/"),
            ("simbad_cds", "&CDS", "https://simbad.u-strasbg.fr/simbad/"),
        ),
    ),
    (
        "ADS",
        (
            ("ads_sao", "&SAO", "https://ui.adsabs.harvard.edu/"),
            ("ads_cds", "&CDS", "https://cdsads.u-strasbg.fr/"),
        ),
    ),
)

#: DS9's three Auto Plot toggles, under Region -> Region Parameters.
REGION_AUTO_TOGGLES: tuple[tuple[str, str], ...] = (
    ("plot2d", "Auto Plot &2D"),
    ("plot3d", "Auto Plot &3D"),
    ("statistics", "Auto Plot &Statistics"),
)

#: The colours DS9's Region -> Color cascade offers, and its default.
REGION_COLORS: tuple[str, ...] = (
    "black",
    "white",
    "red",
    "green",
    "blue",
    "cyan",
    "magenta",
    "yellow",
)
DEFAULT_REGION_COLOR = "green"

#: DS9's four raster formats, in the order Import and Export list them.
RASTER_ENTRIES: tuple[tuple[str, str], ...] = (
    ("gif", "&GIF"),
    ("tiff", "&TIFF"),
    ("jpeg", "&JPEG"),
    ("png", "&PNG"),
)

#: DS9's Import and Export cascades hold the same ten formats in the same
#: three groups (`mfile.tcl`), so one table describes both.
IMPORT_ENTRIES: tuple[tuple[tuple[str, str], ...], ...] = (
    (("array", "&Array"), ("nrrd", "&NRRD"), ("envi", "&ENVI")),
    (
        ("rgb_array", "&RGB Array"),
        ("hsv_array", "&HSV Array"),
        ("hls_array", "&HLS Array"),
    ),
    RASTER_ENTRIES,
)

#: The line widths DS9's Region -> Width cascade offers.
REGION_WIDTHS: tuple[int, ...] = (1, 2, 3, 4)

#: The shapes DS9's Illustrate -> Shape cascade offers, in its order
#: (`millustrate.tcl:62`).
ILLUSTRATE_SHAPES: tuple[str, ...] = (
    "circle",
    "ellipse",
    "box",
    "polygon",
    "line",
    "text",
    "image",
)

#: What DS9 draws a new illustration in.
DEFAULT_ILLUSTRATE_COLOR = "cyan"

#: DS9's Region -> Properties cascade: the flags a region carries, with the
#: value a new region takes.
REGION_PROPERTIES: tuple[tuple[str, str, bool], ...] = (
    ("fixed", "Fi&xed in Size", False),
    ("can_edit", "&Edit", True),
    ("can_move", "&Move", True),
    ("can_rotate", "&Rotate", True),
    ("can_delete", "&Delete", True),
    ("include", "&Include", True),
    ("source", "&Source", True),
    ("dash", "Das&h", False),
    ("fill", "&Fill", False),
)

#: The fonts DS9's Region -> Font cascade offers, and its defaults.
REGION_FONTS: tuple[str, ...] = ("helvetica", "times", "courier")
REGION_FONT_SIZES: tuple[int, ...] = (9, 10, 12, 14, 16, 18, 24)
DEFAULT_REGION_FONT = "helvetica"
DEFAULT_REGION_FONT_SIZE = 10

#: DS9's selection and ordering commands, in menu order.
REGION_SELECTION_COMMANDS: tuple[tuple[str | None, str], ...] = (
    ("all", "&All"),
    ("none", "N&one"),
    ("invert", "In&vert"),
    ("front", "&Front"),
    ("back", "Bac&k"),
    (None, ""),
    ("move_front", "Move to Fron&t"),
    ("move_back", "Move to Bac&k"),
    (None, ""),
    ("save_selection", "Save Se&lection..."),
    ("list_selection", "List Selectio&n"),
    ("delete_selection", "Delete Selec&tion"),
)

#: DS9's pointer modes, in the order its Edit menu lists them.
EDIT_MODES: tuple[tuple[str, str], ...] = (
    ("none", "&None"),
    ("region", "&Region"),
    ("crosshair", "Cross&hair"),
    ("colorbar", "Color&bar"),
    ("pan", "&Pan"),
    ("zoom", "&Zoom"),
    ("rotate", "Ro&tate"),
    ("crop", "&Crop"),
    ("catalog", "C&atalog"),
    ("footprint", "&Footprint"),
    ("examine", "&Examine"),
    ("3d", "&3D"),
    ("illustrate", "&Illustrate"),
)

#: The bin factors and buffer sizes the Bin menu offers, from the module
#: that does the binning so the two cannot diverge.
BIN_FACTORS: tuple[int, ...] = (1, 2, 4, 8, 16, 32, 64, 128, 256)
BIN_BUFFER_SIZES: tuple[int, ...] = BUFFER_SIZES
DEFAULT_BIN_BUFFER_SIZE = DEFAULT_BUFFER_SIZE

#: The block factors the Block menu offers. DS9 goes to 256.
BLOCK_FACTORS: tuple[int, ...] = (1, 2, 4, 8, 16, 32, 64, 128, 256)

#: DS9's eight transfer functions, in the order its Scale menu lists them.
SCALE_FUNCTIONS: tuple[tuple[str, str], ...] = (
    ("linear", "&Linear"),
    ("log", "Lo&g"),
    ("power", "&Power"),
    ("sqrt", "Square &Root"),
    ("squared", "S&quared"),
    ("asinh", "&ASINH"),
    ("sinh", "S&INH"),
    ("histeq", "&Histogram Equalization"),
)

#: The exponents DS9 offers for its log transfer function, and its default.
LOG_EXPONENTS: tuple[float, ...] = (100.0, 200.0, 400.0, 600.0, 800.0, 1000.0, 2000.0, 5000.0)
DEFAULT_LOG_EXPONENT = 1000.0

#: DS9's limit modes. The percentile presets are keyed by their own figure.
SCALE_LIMIT_MODES: tuple[tuple[str, str], ...] = (
    ("minmax", "&Min Max"),
    ("99.5", "99.&5%"),
    ("99", "&99%"),
    ("98", "9&8%"),
    ("97", "97&%"),
    ("96", "96%"),
    ("95", "95%"),
    ("92.5", "92.5%"),
    ("90", "90%"),
    ("zscale", "&ZScale"),
    ("zmax", "Z&Max"),
    ("user", "&User"),
)

#: DS9's Min Max methods.
MINMAX_METHODS: tuple[tuple[str, str], ...] = (
    ("scan", "&Scan"),
    ("sample", "Sa&mple"),
    ("datamin", "&DATAMIN DATAMAX"),
    ("irafminmax", "&IRAF-MIN IRAF-MAX"),
)

#: DS9's `File -> Open as`, in DS9's order. A None name is a separator.
OPEN_AS_ENTRIES: tuple[tuple[str | None, str], ...] = (
    ("slice", "&Slice..."),
    (None, ""),
    ("rgb_image", "&RGB Image..."),
    ("rgb_cube", "RGB &Cube..."),
    ("hsv_image", "&HSV Image..."),
    ("hsv_cube", "HSV C&ube..."),
    ("hls_image", "H&LS Image..."),
    ("hls_cube", "HLS Cu&be..."),
    (None, ""),
    ("mef_cube", "&Multiple Extension Cube..."),
    ("mef_frames", "Multiple &Extension Frames..."),
    (None, ""),
    ("mosaic_wcs", "Mosaic &WCS..."),
    ("mosaic_wcs_segment", "Mosaic WCS Se&gment..."),
    ("mosaic_iraf", "Mosaic &IRAF..."),
    ("mosaic_iraf_segment", "Mosaic IRAF Segmen&t..."),
    ("mosaic_wfpc2", "Mosaic WF&PC2..."),
    (None, ""),
    ("url", "U&RL..."),
)

#: DS9's `File -> Save as`, in DS9's order.
SAVE_AS_ENTRIES: tuple[tuple[str | None, str], ...] = (
    ("slice", "&Slice..."),
    (None, ""),
    ("rgb_image", "&RGB Image..."),
    ("rgb_cube", "RGB &Cube..."),
    ("hsv_image", "&HSV Image..."),
    ("hsv_cube", "HSV C&ube..."),
    ("hls_image", "H&LS Image..."),
    ("hls_cube", "HLS Cu&be..."),
    (None, ""),
    ("mef_cube", "&Multiple Extension Cube..."),
    (None, ""),
    ("mosaic_wcs", "Mosaic &WCS..."),
    ("mosaic_wcs_segment", "Mosaic WCS Se&gment..."),
)

#: DS9's `File -> Save Image`. Only FITS is written by M4; the raster
#: formats are M9-14, and EPS needs the PostScript driver of M9-18.
SAVE_IMAGE_ENTRIES: tuple[tuple[str, str], ...] = (
    ("fits", "&FITS..."),
    ("eps", "&EPS..."),
    ("gif", "&GIF..."),
    ("tiff", "&TIFF..."),
    ("jpeg", "&JPEG..."),
    ("png", "&PNG..."),
)


class MenuBar(QMenuBar):
    """Menu bar with DS9-style menus."""

    def __init__(self, parent: QWidget | None = None) -> None:
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
        self._setup_illustrate_menu()
        self._setup_analysis_menu()
        self._setup_help_menu()

        if self.vo_menu is not None:
            self.vo_menu.setVisible(True)

    def _setup_file_menu(self) -> None:
        """Set up the File menu.

        DS9's `Open as` and `Save as` submenus each hold one entry per way of
        reading or writing the same file (`ds9/library/mfile.tcl`). The lists
        below are DS9's, in DS9's order.
        """
        self.file_menu: QMenu = self.addMenu("&File")

        self.action_open: QAction = QAction("&Open...", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.file_menu.addAction(self.action_open)

        self.open_as_menu: QMenu = self.file_menu.addMenu("Open &as")
        #: Loader name -> its action, so the File controller can wire them in
        #: one loop and a guard test can check none is left unconnected.
        self.open_as_actions: dict[str, QAction] = {}
        for name, label in OPEN_AS_ENTRIES:
            if name is None:
                self.open_as_menu.addSeparator()
                continue
            action = QAction(label, self)
            self.open_as_menu.addAction(action)
            self.open_as_actions[name] = action
            setattr(self, f"action_open_{name}", action)

        self.action_save: QAction = QAction("&Save...", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.file_menu.addAction(self.action_save)

        self.action_save_as: QAction = QAction("Save &As...", self)
        self.action_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.file_menu.addAction(self.action_save_as)

        self.save_as_menu: QMenu = self.file_menu.addMenu("Save a&s")
        #: Writer name -> its action. As `open_as_actions`.
        self.save_as_actions: dict[str, QAction] = {}
        for name, label in SAVE_AS_ENTRIES:
            if name is None:
                self.save_as_menu.addSeparator()
                continue
            action = QAction(label, self)
            self.save_as_menu.addAction(action)
            self.save_as_actions[name] = action
            setattr(self, f"action_save_{name}", action)

        self.file_menu.addSeparator()

        # DS9 puts Prism here, between the save entries and Save Image
        # (`mfile.tcl`).
        self.action_prism: QAction = QAction("&Prism...", self)
        self.file_menu.addAction(self.action_prism)

        self.file_menu.addSeparator()

        self.save_image_menu: QMenu = self.file_menu.addMenu("Save &Image")
        #: Format name -> its action.
        self.save_image_actions: dict[str, QAction] = {}
        for name, label in SAVE_IMAGE_ENTRIES:
            action = QAction(label, self)
            self.save_image_menu.addAction(action)
            self.save_image_actions[name] = action
            setattr(self, f"action_save_image_{name}", action)

        # DS9's Import and Export cascades (`mfile.tcl`), which replaced a
        # single `Export...` of ours: DS9 has ten formats each way, and one
        # entry could not say which.
        self.import_menu: QMenu = self.file_menu.addMenu("&Import")
        self.import_slice_menu: QMenu = self.import_menu.addMenu("S&lice")
        #: Import format name -> its action.
        self.import_actions: dict[str, QAction] = {}
        for name, label in RASTER_ENTRIES:
            action = QAction(label, self)
            self.import_slice_menu.addAction(action)
            self.import_actions[f"slice_{name}"] = action
        self.import_menu.addSeparator()
        for group in IMPORT_ENTRIES:
            for name, label in group:
                action = QAction(label, self)
                self.import_menu.addAction(action)
                self.import_actions[name] = action
                setattr(self, f"action_import_{name}", action)
            self.import_menu.addSeparator()

        self.export_menu: QMenu = self.file_menu.addMenu("&Export")
        #: Export format name -> its action.
        self.export_actions: dict[str, QAction] = {}
        for group in IMPORT_ENTRIES:
            for name, label in group:
                action = QAction(label, self)
                self.export_menu.addAction(action)
                self.export_actions[name] = action
                setattr(self, f"action_export_{name}", action)
            self.export_menu.addSeparator()

        self.action_create_movie: QAction = QAction("Create &Movie...", self)
        self.file_menu.addAction(self.action_create_movie)

        self.file_menu.addSeparator()

        # DS9 puts Backup and Restore here, after the image-saving entries
        # and before Header (`mfile.tcl`).
        self.action_backup: QAction = QAction("&Backup...", self)
        self.file_menu.addAction(self.action_backup)
        self.action_restore: QAction = QAction("&Restore...", self)
        self.file_menu.addAction(self.action_restore)

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

        self.edit_menu.addSeparator()

        # DS9's pointer modes: what a drag on the image does. Only a few are
        # live -- the rest are recorded with the milestone that implements
        # them, in `ui/controllers/edit.py`.
        mode_group = QActionGroup(self)
        mode_group.setExclusive(True)
        #: Pointer-mode name -> its action.
        self.edit_mode_actions: dict[str, QAction] = {}
        for name, label in EDIT_MODES:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(name == "none")
            mode_group.addAction(action)
            self.edit_menu.addAction(action)
            self.edit_mode_actions[name] = action

        self.edit_menu.addSeparator()

        self.action_preferences: QAction = QAction("Pre&ferences...", self)
        self.edit_menu.addAction(self.action_preferences)

    def _setup_view_menu(self) -> None:
        """Set up the View menu.

        DS9's `ViewMainMenu` (`ds9/library/mview.tcl`) in order: the four
        layouts as one radio group, then the panel toggles, then the frame
        decorations, then one toggle per information-panel field with the
        twenty-six alternate WCS systems on a submenu. NCRADS9 adds Fullscreen
        and Show Status Bar at the end, which DS9 has nowhere.

        DS9's `Icons` toggle shows and hides its icon bars; the closest thing
        NCRADS9 has is the toolbar, so `action_show_toolbar` is an alias of
        the same action rather than a second entry that could disagree with it.
        """
        self.view_menu: QMenu = self.addMenu("&View")

        layout_group = QActionGroup(self)
        layout_group.setExclusive(True)
        for attribute, label, checked in (
            ("action_view_horizontal", "&Horizontal", True),
            ("action_view_vertical", "&Vertical", False),
            ("action_view_basic", "&Basic", False),
            ("action_view_advanced", "&Advanced", False),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(checked)
            layout_group.addAction(action)
            self.view_menu.addAction(action)
            setattr(self, attribute, action)

        self.view_menu.addSeparator()

        for attribute, label, checked in (
            ("action_view_info", "&Information Panel", True),
            ("action_view_panner", "&Panner", True),
            ("action_view_magnifier", "&Magnifier", True),
            ("action_view_buttons", "B&uttons", True),
            ("action_view_icons", "&Icons", True),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(checked)
            self.view_menu.addAction(action)
            setattr(self, attribute, action)

        #: DS9 has no separate toolbar toggle; its icon bars are `Icons`.
        self.action_show_toolbar: QAction = self.action_view_icons

        self.view_menu.addSeparator()

        for attribute, label, checked in (
            ("action_view_colorbar", "Color&bar", True),
            ("action_view_multi_colorbar", "Multiple Colorbar&s", True),
            ("action_view_graph_horizontal", "Hori&zontal Graph", False),
            ("action_view_graph_vertical", "Vertica&l Graph", False),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(checked)
            self.view_menu.addAction(action)
            setattr(self, attribute, action)

        self.view_menu.addSeparator()

        #: Information-panel field name -> its toggle. Keyed by the names in
        #: `ui/layout/view_state.INFO_FIELDS`, so the controller can walk the
        #: two together.
        self.info_field_actions: dict[str, QAction] = {}
        for name, label in (
            ("filename", "Filename"),
            ("object", "Object"),
            ("keyword", "Keyword"),
            ("minmax", "Min Max"),
            ("lowhigh", "Low High"),
            ("bunit", "Units"),
            ("wcs", "WCS"),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(name in DEFAULT_INFO_FIELDS)
            self.view_menu.addAction(action)
            self.info_field_actions[name] = action

        self.multiple_wcs_menu: QMenu = self.view_menu.addMenu("Multiple &WCS")
        for suffix in WCS_SUFFIXES:
            action = QAction(f"WCS {suffix}", self)
            action.setCheckable(True)
            self.multiple_wcs_menu.addAction(action)
            self.info_field_actions[f"wcs_{suffix}"] = action

        for name, label in (
            ("image", "Image"),
            ("physical", "Physical"),
            ("amplifier", "Amplifier"),
            ("detector", "Detector"),
            ("frame", "Frame Information"),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(name in DEFAULT_INFO_FIELDS)
            self.view_menu.addAction(action)
            self.info_field_actions[name] = action

        self.view_menu.addSeparator()

        self.action_fullscreen: QAction = QAction("&Fullscreen", self)
        self.action_fullscreen.setShortcut("F11")
        self.action_fullscreen.setCheckable(True)
        self.view_menu.addAction(self.action_fullscreen)

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
        self.blink_interval_actions: dict[int, QAction] = {}
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
        self.fade_interval_actions: dict[int, QAction] = {}
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
        """Set up the Bin menu.

        DS9's order (`ds9/library/mbin.tcl`): the bin function as a radio
        pair, Bin In / Out / Fit, nine bin factors, seven buffer sizes, and
        the Binning Parameters dialog.

        Bin applies to a FITS table, which is the difference from Block on
        the Analysis menu -- see `core/bin_table.py` and PLAN.md §3.4. The
        four `1x1` .. `8x8` entries that used to be this whole menu did
        block-averaging, which is Block's job.
        """
        self.bin_menu: QMenu = self.addMenu("&Bin")

        function_group = QActionGroup(self)
        function_group.setExclusive(True)
        #: Bin function name -> its action.
        self.bin_function_actions: dict[str, QAction] = {}
        for name, label, checked in (("average", "&Average", False), ("sum", "&Sum", True)):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(checked)
            function_group.addAction(action)
            self.bin_menu.addAction(action)
            self.bin_function_actions[name] = action

        self.bin_menu.addSeparator()

        self.action_bin_in: QAction = QAction("Bin &In", self)
        self.bin_menu.addAction(self.action_bin_in)
        self.action_bin_out: QAction = QAction("Bin &Out", self)
        self.bin_menu.addAction(self.action_bin_out)
        self.action_bin_fit: QAction = QAction("Bin &Fit", self)
        self.bin_menu.addAction(self.action_bin_fit)

        self.bin_menu.addSeparator()

        factor_group = QActionGroup(self)
        factor_group.setExclusive(True)
        #: Bin factor -> its action.
        self.bin_factor_actions: dict[int, QAction] = {}
        for factor in BIN_FACTORS:
            action = QAction(f"Bin {factor}", self)
            action.setCheckable(True)
            action.setChecked(factor == 1)
            factor_group.addAction(action)
            self.bin_menu.addAction(action)
            self.bin_factor_actions[factor] = action
            setattr(self, f"action_bin_{factor}", action)

        self.bin_menu.addSeparator()

        buffer_group = QActionGroup(self)
        buffer_group.setExclusive(True)
        #: Buffer size -> its action.
        self.bin_buffer_actions: dict[int, QAction] = {}
        for size in BIN_BUFFER_SIZES:
            action = QAction(f"{size}x{size}", self)
            action.setCheckable(True)
            action.setChecked(size == DEFAULT_BIN_BUFFER_SIZE)
            buffer_group.addAction(action)
            self.bin_menu.addAction(action)
            self.bin_buffer_actions[size] = action

        self.bin_menu.addSeparator()

        self.action_bin_params: QAction = QAction("Binning &Parameters...", self)
        self.bin_menu.addAction(self.action_bin_params)

    def _setup_zoom_menu(self) -> None:
        """Set up the Zoom menu."""
        self.zoom_menu: QMenu = self.addMenu("&Zoom")

        self.action_zoom_center: QAction = QAction("&Center Image", self)
        self.zoom_menu.addAction(self.action_zoom_center)

        self.action_zoom_align: QAction = QAction("&Align", self)
        self.action_zoom_align.setCheckable(True)
        self.zoom_menu.addAction(self.action_zoom_align)

        self.zoom_menu.addSeparator()

        self.action_zoom_in: QAction = QAction("Zoom &In", self)
        self.action_zoom_in.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self.zoom_menu.addAction(self.action_zoom_in)

        self.action_zoom_out: QAction = QAction("Zoom &Out", self)
        self.action_zoom_out.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self.zoom_menu.addAction(self.action_zoom_out)

        self.action_zoom_fit: QAction = QAction("Zoom &Fit", self)
        self.zoom_menu.addAction(self.action_zoom_fit)

        self.zoom_menu.addSeparator()
        self.zoom_preset_group = QActionGroup(self)
        self.zoom_preset_group.setExclusive(True)
        self.zoom_preset_actions: dict[float, QAction] = {}
        zoom_presets = [
            ("Zoom 1/32", 0.03125),
            ("Zoom 1/16", 0.0625),
            ("Zoom 1/8", 0.125),
            ("Zoom 1/4", 0.25),
            ("Zoom 1/2", 0.5),
            ("Zoom 1", 1.0),
            ("Zoom 2", 2.0),
            ("Zoom 4", 4.0),
            ("Zoom 8", 8.0),
            ("Zoom 16", 16.0),
            ("Zoom 32", 32.0),
        ]
        for label, value in zoom_presets:
            action = QAction(label, self)
            action.setCheckable(True)
            self.zoom_menu.addAction(action)
            self.zoom_preset_group.addAction(action)
            self.zoom_preset_actions[value] = action

        self.action_zoom_1 = self.zoom_preset_actions[1.0]

        self.zoom_menu.addSeparator()
        self.zoom_orientation_group = QActionGroup(self)
        self.zoom_orientation_group.setExclusive(True)
        self.action_zoom_orient_none = QAction("&None", self)
        self.action_zoom_orient_x = QAction("Invert &X", self)
        self.action_zoom_orient_y = QAction("Invert &Y", self)
        self.action_zoom_orient_xy = QAction("Invert X&Y", self)
        self.zoom_orientation_actions: dict[str, QAction] = {
            "none": self.action_zoom_orient_none,
            "x": self.action_zoom_orient_x,
            "y": self.action_zoom_orient_y,
            "xy": self.action_zoom_orient_xy,
        }
        for action in self.zoom_orientation_actions.values():
            action.setCheckable(True)
            self.zoom_menu.addAction(action)
            self.zoom_orientation_group.addAction(action)
        self.action_zoom_orient_none.setChecked(True)

        self.zoom_menu.addSeparator()
        self.zoom_rotation_group = QActionGroup(self)
        self.zoom_rotation_group.setExclusive(True)
        self.zoom_rotation_actions: dict[int, QAction] = {}
        for degrees in (0, 90, 180, 270):
            action = QAction(f"{degrees} Degrees", self)
            action.setCheckable(True)
            self.zoom_menu.addAction(action)
            self.zoom_rotation_group.addAction(action)
            self.zoom_rotation_actions[degrees] = action
        self.action_zoom_rotate_0 = self.zoom_rotation_actions[0]
        self.action_zoom_rotate_90 = self.zoom_rotation_actions[90]
        self.action_zoom_rotate_180 = self.zoom_rotation_actions[180]
        self.action_zoom_rotate_270 = self.zoom_rotation_actions[270]
        self.action_zoom_rotate_0.setChecked(True)

        self.zoom_menu.addSeparator()
        self.action_crop_parameters: QAction = QAction("Crop &Parameters", self)
        self.zoom_menu.addAction(self.action_crop_parameters)

        self.zoom_menu.addSeparator()
        self.action_pan_zoom_rotate_parameters: QAction = QAction("&Pan Zoom Rotate Parameters", self)
        self.zoom_menu.addAction(self.action_pan_zoom_rotate_parameters)

    def _setup_scale_menu(self) -> None:
        """Set up the Scale menu.

        DS9's order (`ds9/library/mscale.tcl`): the eight transfer functions
        as one radio group, the Log Exponent submenu, then the limit modes as
        a second radio group -- Min Max, eight percentile presets, ZScale,
        ZMax, User -- then the scope, the Min Max method submenu, Use DATASEC,
        and the two parameter dialogs.
        """
        self.scale_menu: QMenu = self.addMenu("&Scale")

        function_group = QActionGroup(self)
        function_group.setExclusive(True)
        #: Transfer-function name -> its action.
        self.scale_function_actions: dict[str, QAction] = {}
        for name, label in SCALE_FUNCTIONS:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(name == "linear")
            function_group.addAction(action)
            self.scale_menu.addAction(action)
            self.scale_function_actions[name] = action
            setattr(self, f"action_scale_{name}", action)

        self.log_exponent_menu: QMenu = self.scale_menu.addMenu("Log &Exponent")
        exponent_group = QActionGroup(self)
        exponent_group.setExclusive(True)
        #: Exponent -> its action.
        self.log_exponent_actions: dict[float, QAction] = {}
        for exponent in LOG_EXPONENTS:
            action = QAction(f"{exponent:g}", self)
            action.setCheckable(True)
            action.setChecked(exponent == DEFAULT_LOG_EXPONENT)
            exponent_group.addAction(action)
            self.log_exponent_menu.addAction(action)
            self.log_exponent_actions[exponent] = action
        self.log_exponent_menu.addSeparator()
        self.action_log_exponent_other: QAction = QAction("&Other...", self)
        self.log_exponent_menu.addAction(self.action_log_exponent_other)

        self.scale_menu.addSeparator()

        limit_group = QActionGroup(self)
        limit_group.setExclusive(True)
        #: Limit-mode name -> its action. Percentile presets are keyed by
        #: their figure, e.g. "99.5".
        self.scale_limit_actions: dict[str, QAction] = {}
        for name, label in SCALE_LIMIT_MODES:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(name == "minmax")
            limit_group.addAction(action)
            self.scale_menu.addAction(action)
            self.scale_limit_actions[name] = action

        #: DS9 calls the min/max entry `Min Max`; the old attribute name is
        #: kept because XPA and the button bar already use it.
        self.action_scale_minmax: QAction = self.scale_limit_actions["minmax"]
        self.action_scale_zscale: QAction = self.scale_limit_actions["zscale"]

        self.action_scale_user_limits: QAction = QAction("Ot&her...", self)
        self.scale_menu.addAction(self.action_scale_user_limits)

        self.scale_menu.addSeparator()

        scope_group = QActionGroup(self)
        scope_group.setExclusive(True)
        #: Scope name -> its action.
        self.scale_scope_actions: dict[str, QAction] = {}
        for name, label in (("global", "&Global"), ("local", "&Local")):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(name == "local")
            scope_group.addAction(action)
            self.scale_menu.addAction(action)
            self.scale_scope_actions[name] = action

        self.scale_menu.addSeparator()

        self.minmax_method_menu: QMenu = self.scale_menu.addMenu("&Min Max")
        method_group = QActionGroup(self)
        method_group.setExclusive(True)
        #: Method name -> its action.
        self.minmax_method_actions: dict[str, QAction] = {}
        for name, label in MINMAX_METHODS:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(name == "scan")
            method_group.addAction(action)
            self.minmax_method_menu.addAction(action)
            self.minmax_method_actions[name] = action
        self.minmax_method_menu.addSeparator()
        self.action_sample_parameters: QAction = QAction("Sample &Parameters...", self)
        self.minmax_method_menu.addAction(self.action_sample_parameters)

        self.scale_menu.addSeparator()

        self.action_use_datasec: QAction = QAction("Use &DATASEC", self)
        self.action_use_datasec.setCheckable(True)
        self.action_use_datasec.setChecked(True)
        self.scale_menu.addAction(self.action_use_datasec)

        self.action_zscale_parameters: QAction = QAction("&ZScale Parameters...", self)
        self.scale_menu.addAction(self.action_zscale_parameters)

        self.scale_menu.addSeparator()

        self.action_scale_params: QAction = QAction("Scale &Parameters...", self)
        self.scale_menu.addAction(self.action_scale_params)

    def _setup_color_menu(self) -> None:
        """Set up the Color menu."""
        self.color_menu: QMenu = self.addMenu("&Color")
        self.colormap_action_group = QActionGroup(self)
        self.colormap_action_group.setExclusive(True)
        self.colormap_actions: dict[str, QAction] = {}

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
            # DS9's eighteen built-ins end here. The four below are NCRADS9
            # additions at the top level: DS9 accepts these names on its
            # command line but reaches the tables through its Matplotlib
            # Uniform cascade, where they also appear as `mpl_viridis` and
            # friends.
            ("Viridis", "viridis"),
            ("Plasma", "plasma"),
            ("Inferno", "inferno"),
            ("Magma", "magma"),
        ]
        for label, cmap_name in default_maps:
            self._add_colormap_action(self.color_menu, label, cmap_name, checked=(cmap_name == "grey"))

        self.color_menu.addSeparator()

        # DS9's ten cascades of bundled tables, with its own membership --
        # see `colormaps/bundled.py`. The `viridis`, `plasma`, `inferno` and
        # `magma` entries above are NCRADS9 built-ins carrying the same names
        # DS9 uses at the top level; the same tables appear below as
        # `mpl_viridis` and friends, which is what DS9's cascades call them.
        self.colormap_submenus: dict[str, QMenu] = {}
        for category, names in CATEGORIES.items():
            submenu = self.color_menu.addMenu(category)
            self.colormap_submenus[category] = submenu
            for name in names:
                self._add_colormap_action(submenu, colormap_label(name), name)

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

        # DS9 keeps colorbar visibility in the View menu only; NCRADS9 also
        # offers it here. Same action in both menus, so the two tick marks
        # cannot disagree.
        self.action_colorbar: QAction = self.action_view_colorbar
        self.color_menu.addAction(self.action_colorbar)

        self.colorbar_submenu: QMenu = self.color_menu.addMenu("Colorbar &Options")

        self.colorbar_orientation_menu: QMenu = self.colorbar_submenu.addMenu("&Orientation")
        self.colorbar_orientation_group = QActionGroup(self)
        self.colorbar_orientation_group.setExclusive(True)
        # Horizontal by default, matching DS9, which lays the colorbar out
        # under the canvas.
        self.action_colorbar_horizontal: QAction = QAction("&Horizontal", self)
        self.action_colorbar_horizontal.setCheckable(True)
        self.action_colorbar_horizontal.setChecked(True)
        self.action_colorbar_vertical: QAction = QAction("&Vertical", self)
        self.action_colorbar_vertical.setCheckable(True)
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

        # DS9 keeps colour tags on the Colormap Parameters dialog's own
        # menus; they are here as well so they can be reached without
        # opening it.
        self.color_tag_menu: QMenu = self.color_menu.addMenu("Color &Tags")
        self.action_load_color_tags: QAction = QAction("&Load Color Tag...", self)
        self.color_tag_menu.addAction(self.action_load_color_tags)
        self.action_save_color_tags: QAction = QAction("&Save Color Tag...", self)
        self.color_tag_menu.addAction(self.action_save_color_tags)
        self.action_delete_color_tags: QAction = QAction("&Delete Color Tag", self)
        self.color_tag_menu.addAction(self.action_delete_color_tags)

        self.color_menu.addSeparator()
        self.action_colormap_params: QAction = QAction("Colormap &Parameters...", self)
        self.color_menu.addAction(self.action_colormap_params)
        self.action_reset_colorbar: QAction = QAction("&Reset Contrast/Bias", self)
        self.color_menu.addAction(self.action_reset_colorbar)

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
        """Set up the Region menu.

        DS9's order (`ds9/library/mregion.tcl`): Get Information; the Shape,
        Composite Region, Instrument FOV and Template cascades; Color, Width,
        Properties and Font; Centroid; the group entries; the selection
        entries; and the file entries.

        Shape is a cascade in DS9 and a flat list here, because NCRADS9's
        shape list is also what the button bar shows and a cascade would put
        every shape two clicks away.
        """
        self.region_menu: QMenu = self.addMenu("&Region")

        self.action_region_info: QAction = QAction("Get &Information", self)
        self.region_menu.addAction(self.action_region_info)

        self.region_menu.addSeparator()

        self.region_shape_menu: QMenu = self.region_menu.addMenu("&Shape")
        shape_group = QActionGroup(self)
        shape_group.setExclusive(True)
        #: Shape name -> its action.
        self.region_shape_actions: dict[str, QAction] = {}
        for name, label in REGION_SHAPES:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(name == "circle")
            shape_group.addAction(action)
            self.region_shape_menu.addAction(action)
            self.region_shape_actions[name] = action
            setattr(self, f"action_region_{name}", action)

        # The six shapes the button bar and toolbar already reach by name.
        self.action_region_none: QAction = QAction("&None", self)
        self.action_region_none.setCheckable(True)
        shape_group.addAction(self.action_region_none)
        self.region_shape_menu.addSeparator()
        self.region_shape_menu.addAction(self.action_region_none)

        composite_menu = self.region_menu.addMenu("&Composite Region")
        self.action_composite_create: QAction = QAction("C&reate", self)
        composite_menu.addAction(self.action_composite_create)
        self.action_composite_dissolve: QAction = QAction("&Dissolve", self)
        composite_menu.addAction(self.action_composite_dissolve)
        fov_menu = self.region_menu.addMenu("&Instrument FOV")
        #: Template path (e.g. "chandra/acis/acis-i") -> its action.
        self.region_fov_actions: dict[str, QAction] = {}
        self._fill_fov_menu(fov_menu)

        template_menu = self.region_menu.addMenu("&Template")
        self.action_template_open: QAction = QAction("&Open...", self)
        template_menu.addAction(self.action_template_open)
        self.action_template_save: QAction = QAction("&Save...", self)
        template_menu.addAction(self.action_template_save)

        self.region_menu.addSeparator()

        self.region_color_menu: QMenu = self.region_menu.addMenu("&Color")
        color_group = QActionGroup(self)
        color_group.setExclusive(True)
        #: Colour name -> its action.
        self.region_color_actions: dict[str, QAction] = {}
        for name in REGION_COLORS:
            action = QAction(name.title(), self)
            action.setCheckable(True)
            action.setChecked(name == DEFAULT_REGION_COLOR)
            color_group.addAction(action)
            self.region_color_menu.addAction(action)
            self.region_color_actions[name] = action

        self.region_width_menu: QMenu = self.region_menu.addMenu("&Width")
        width_group = QActionGroup(self)
        width_group.setExclusive(True)
        #: Line width -> its action.
        self.region_width_actions: dict[int, QAction] = {}
        for value in REGION_WIDTHS:
            action = QAction(str(value), self)
            action.setCheckable(True)
            action.setChecked(value == 1)
            width_group.addAction(action)
            self.region_width_menu.addAction(action)
            self.region_width_actions[value] = action

        self.region_properties_menu: QMenu = self.region_menu.addMenu("&Properties")
        #: Property name -> its action.
        self.region_property_actions: dict[str, QAction] = {}
        for name, label, default in REGION_PROPERTIES:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(default)
            self.region_properties_menu.addAction(action)
            self.region_property_actions[name] = action

        self.region_font_menu: QMenu = self.region_menu.addMenu("&Font")
        font_group = QActionGroup(self)
        font_group.setExclusive(True)
        #: Font family -> its action.
        self.region_font_actions: dict[str, QAction] = {}
        for family in REGION_FONTS:
            action = QAction(family.title(), self)
            action.setCheckable(True)
            action.setChecked(family == DEFAULT_REGION_FONT)
            font_group.addAction(action)
            self.region_font_menu.addAction(action)
            self.region_font_actions[family] = action

        self.region_font_menu.addSeparator()
        size_group = QActionGroup(self)
        size_group.setExclusive(True)
        #: Font size -> its action.
        self.region_font_size_actions: dict[int, QAction] = {}
        for size in REGION_FONT_SIZES:
            action = QAction(str(size), self)
            action.setCheckable(True)
            action.setChecked(size == DEFAULT_REGION_FONT_SIZE)
            size_group.addAction(action)
            self.region_font_menu.addAction(action)
            self.region_font_size_actions[size] = action

        self.region_menu.addSeparator()

        self.action_region_centroid: QAction = QAction("Cen&troid", self)
        self.region_menu.addAction(self.action_region_centroid)

        self.region_menu.addSeparator()

        self.action_region_new_group: QAction = QAction("New &Group", self)
        self.region_menu.addAction(self.action_region_new_group)
        self.action_region_groups: QAction = QAction("Gro&ups", self)
        self.region_menu.addAction(self.action_region_groups)

        self.region_menu.addSeparator()

        #: Selection command name -> its action.
        self.region_selection_actions: dict[str, QAction] = {}
        for name, label in REGION_SELECTION_COMMANDS:
            if name is None:
                self.region_menu.addSeparator()
                continue
            action = QAction(label, self)
            self.region_menu.addAction(action)
            self.region_selection_actions[name] = action

        self.region_menu.addSeparator()

        self.action_region_load: QAction = QAction("&Open...", self)
        self.region_menu.addAction(self.action_region_load)

        self.action_region_save: QAction = QAction("&Save...", self)
        self.region_menu.addAction(self.action_region_save)

        self.action_region_list: QAction = QAction("&List", self)
        self.region_menu.addAction(self.action_region_list)

        self.action_region_delete_all: QAction = QAction("&Delete All", self)
        self.region_menu.addAction(self.action_region_delete_all)

        self.region_menu.addSeparator()

        params_menu = self.region_menu.addMenu("Region &Parameters")
        self.action_region_show: QAction = QAction("Sho&w", self)
        self.action_region_show.setCheckable(True)
        self.action_region_show.setChecked(True)
        params_menu.addAction(self.action_region_show)
        self.action_region_show_text: QAction = QAction("Show &Text", self)
        self.action_region_show_text.setCheckable(True)
        self.action_region_show_text.setChecked(True)
        params_menu.addAction(self.action_region_show_text)
        params_menu.addSeparator()

        #: The three Auto Plot toggles, by name. M6-26 gives them behaviour.
        self.region_auto_actions: dict[str, QAction] = {}
        for name, label in REGION_AUTO_TOGGLES:
            action = QAction(label, self)
            action.setCheckable(True)
            params_menu.addAction(action)
            self.region_auto_actions[name] = action
        params_menu.addSeparator()

        self.action_region_auto_centroid: QAction = QAction("Auto &Centroid", self)
        self.action_region_auto_centroid.setCheckable(True)
        params_menu.addAction(self.action_region_auto_centroid)
        self.action_region_centroid_params: QAction = QAction("Centroid Parameters...", self)
        params_menu.addAction(self.action_region_centroid_params)

    def _fill_catalogs_menu(self, menu: QMenu) -> None:
        """Build DS9's Catalogs cascade from its own catalogue list.

        Six sections of forty-odd catalogues (`icat(def)` in
        `ds9/library/cat.tcl:48`), each a submenu. Read from
        `catalogs/servers.py` rather than listed here, so the menu and the
        query layer cannot name different catalogues.
        """
        #: DS9's catalogue name (e.g. `catgaia`) -> its action.
        self.catalog_actions: dict[str, QAction] = {}

        for section in CATALOG_SECTIONS:
            entries = catalogs_in_section(section)
            if not entries:
                continue
            submenu = menu.addMenu(section)
            for entry in entries:
                action = QAction(entry.label, self)
                submenu.addAction(action)
                self.catalog_actions[entry.name] = action

    def _fill_fov_menu(self, menu: QMenu) -> None:
        """Build the Instrument FOV cascade from the bundled templates.

        DS9 builds its own the same way (`CreateFOVMenu` in
        `ds9/library/template.tcl`): the directory tree under `template/` is
        the menu tree, upper-cased. Reading the tree rather than listing the
        instruments here means a template dropped in appears in the menu.
        """
        submenus: dict[str, QMenu] = {}

        for path in bundled_templates():
            parts = path.split("/")
            parent = menu
            trail = ""
            for part in parts[:-1]:
                trail = f"{trail}/{part}" if trail else part
                if trail not in submenus:
                    submenus[trail] = parent.addMenu(part.upper())
                parent = submenus[trail]

            action = QAction(parts[-1], self)
            parent.addAction(action)
            self.region_fov_actions[path] = action

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

        self.action_vo_registry: QAction = QAction("&Registry Browser...", self)
        self.vo_menu.addAction(self.action_vo_registry)

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

        # Off by default since M3: the compass lives in the panner, as it
        # does in DS9. This draws it over the image as well.
        self.action_show_direction_arrows: QAction = QAction("Show &Direction Arrows", self)
        self.action_show_direction_arrows.setCheckable(True)
        self.wcs_menu.addAction(self.action_show_direction_arrows)

    def _setup_illustrate_menu(self) -> None:
        """Set up the Illustrate menu (`millustrate.tcl`).

        DS9 puts it between WCS and Analysis, and so do we.
        """
        self.illustrate_menu: QMenu = self.addMenu("&Illustrate")

        self.action_illustrate_info: QAction = QAction("&Get Information", self)
        self.illustrate_menu.addAction(self.action_illustrate_info)
        self.illustrate_menu.addSeparator()

        self.illustrate_shape_menu: QMenu = self.illustrate_menu.addMenu("&Shape")
        shape_group = QActionGroup(self)
        shape_group.setExclusive(True)
        #: Shape name -> its action.
        self.illustrate_shape_actions: dict[str, QAction] = {}
        for name in ILLUSTRATE_SHAPES:
            action = QAction(name.title(), self)
            action.setCheckable(True)
            action.setChecked(name == "circle")
            shape_group.addAction(action)
            self.illustrate_shape_menu.addAction(action)
            self.illustrate_shape_actions[name] = action

        self.illustrate_menu.addSeparator()

        self.illustrate_color_menu: QMenu = self.illustrate_menu.addMenu("&Color")
        color_group = QActionGroup(self)
        color_group.setExclusive(True)
        #: Colour name -> its action.
        self.illustrate_color_actions: dict[str, QAction] = {}
        for name in REGION_COLORS:
            action = QAction(name.title(), self)
            action.setCheckable(True)
            action.setChecked(name == DEFAULT_ILLUSTRATE_COLOR)
            color_group.addAction(action)
            self.illustrate_color_menu.addAction(action)
            self.illustrate_color_actions[name] = action

        self.illustrate_width_menu: QMenu = self.illustrate_menu.addMenu("&Width")
        width_group = QActionGroup(self)
        width_group.setExclusive(True)
        #: Line width -> its action.
        self.illustrate_width_actions: dict[int, QAction] = {}
        for value in REGION_WIDTHS:
            action = QAction(str(value), self)
            action.setCheckable(True)
            action.setChecked(value == 1)
            width_group.addAction(action)
            self.illustrate_width_menu.addAction(action)
            self.illustrate_width_actions[value] = action

        self.illustrate_menu.addSeparator()

        #: Command name -> its action, for everything the menu simply does.
        self.illustrate_actions: dict[str, QAction] = {}
        for group in (
            (
                ("all", "&All"),
                ("none", "&None"),
                ("invert", "&Invert"),
                ("front", "&Front"),
                ("back", "&Back"),
            ),
            (("move_front", "Move to &Front"), ("move_back", "Move to &Back")),
            (
                ("save_selection", "&Save Selection..."),
                ("list_selection", "&List Selection"),
                ("delete_selection", "&Delete Selection"),
            ),
            (("open", "&Open..."), ("save", "Sa&ve..."), ("list", "Lis&t")),
            (("delete_all", "Delete A&ll"),),
        ):
            for name, label in group:
                action = QAction(label, self)
                self.illustrate_menu.addAction(action)
                self.illustrate_actions[name] = action
            self.illustrate_menu.addSeparator()

        self.action_illustrate_show: QAction = QAction("Sho&w", self)
        self.action_illustrate_show.setCheckable(True)
        self.action_illustrate_show.setChecked(True)
        self.illustrate_menu.addAction(self.action_illustrate_show)

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
        #: Block factor -> its action.
        self.block_factor_actions: dict[int, QAction] = {}
        for factor in BLOCK_FACTORS:
            action = QAction(f"Block {factor}", self)
            action.setCheckable(True)
            action.setChecked(factor == 1)
            self.analysis_block_menu.addAction(action)
            self.analysis_block_group.addAction(action)
            self.block_factor_actions[factor] = action
            setattr(self, f"action_block_{factor}", action)

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
        #: Image server name -> its action.
        self.image_server_actions: dict[str, QAction] = {}
        for server in IMAGE_SERVERS:
            action = QAction(f"{server.label}...", self)
            self.analysis_image_servers_menu.addAction(action)
            self.image_server_actions[server.name] = action
        # Kept as a name of its own: the VO menu and the XPA reach it.
        self.action_analysis_2mass: QAction = self.image_server_actions["twomass"]
        self.analysis_catalogs_menu: QMenu = self.analysis_menu.addMenu("&Catalogs")
        self._fill_catalogs_menu(self.analysis_catalogs_menu)
        # Kept as a name of its own: the VO menu and the XPA both reach it.
        self.action_analysis_vizier: QAction = QAction("&VizieR...", self)
        self.analysis_catalogs_menu.addSeparator()
        self.analysis_catalogs_menu.addAction(self.action_analysis_vizier)
        self.action_catalog_search: QAction = QAction("&Search for Catalogs...", self)
        self.analysis_catalogs_menu.addAction(self.action_catalog_search)
        self.analysis_catalogs_menu.addSeparator()
        self.action_catalog_load: QAction = QAction("&Load Catalog...", self)
        self.analysis_catalogs_menu.addAction(self.action_catalog_load)
        self.action_catalog_match: QAction = QAction("&Match Catalogs...", self)
        self.analysis_catalogs_menu.addAction(self.action_catalog_match)
        self.action_catalog_clear_all: QAction = QAction("&Clear All Catalogs", self)
        self.analysis_catalogs_menu.addAction(self.action_catalog_clear_all)

        self.analysis_menu.addSeparator()
        archives_menu = self.analysis_menu.addMenu("&Archives")
        self.action_archive_chandra_obsid: QAction = QAction("Chandra Public Archive by &ObsId...", self)
        archives_menu.addAction(self.action_archive_chandra_obsid)
        self.action_archive_chandra_cone: QAction = QAction("Chandra Public Archive by &Cone Search...", self)
        archives_menu.addAction(self.action_archive_chandra_cone)
        archives_menu.addSeparator()

        #: Archive web link name -> its action.
        self.archive_actions: dict[str, QAction] = {}
        for group, entries in ARCHIVE_LINKS:
            submenu = archives_menu.addMenu(group)
            for name, label, _url in entries:
                action = QAction(label, self)
                submenu.addAction(action)
                self.archive_actions[name] = action

        footprints_menu = self.analysis_menu.addMenu("&Footprint Servers")
        #: Footprint server name -> its action.
        self.footprint_actions: dict[str, QAction] = {}
        for server in FOOTPRINT_SERVERS:
            action = QAction(f"{server.label}...", self)
            footprints_menu.addAction(action)
            self.footprint_actions[server.name] = action
        footprints_menu.addSeparator()
        self.action_footprint_clear_all: QAction = QAction("&Clear All", self)
        footprints_menu.addAction(self.action_footprint_clear_all)

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
