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
The two-row buttonbar: a category row, and that category's buttons.

DS9's buttonbar (`ds9/library/buttons.tcl`) is two rows. The first is a
radio group of the menu names -- file, edit, view, frame, bin, zoom, scale,
color, region, wcs, analysis, help -- and the second shows the buttons of
whichever one is selected, so the bar is a flattened copy of the menu tree
that costs one click instead of two. `CreateButtonsMajor` builds the first row
and a `CreateButtons<Category>` procedure builds each page.

NCRADS9's bar was four `QGroupBox`es -- Zoom, Scale, Color, Region -- stacked
in a dock down the left-hand side, twenty-three buttons in total against
DS9's several hundred, and nothing else reachable. This is DS9's structure,
with the buttons NCRADS9 can actually service today.

Most buttons name a `MenuBar` action and simply trigger it, so a button and
its menu entry cannot drift apart, and a checkable action keeps its button
ticked for free. The rest carry a `command` id for the cases where the menu
has no equivalent single action -- the zoom multipliers, the scale and
colormap presets, the region shapes -- and are dispatched by the window.

One divergence from DS9: a category with more buttons than fit is wrapped
onto further rows rather than run off the edge, because DS9's Tk buttons are
narrower than Qt's and its window is wider than our 800-pixel minimum.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QBoxLayout,
    QButtonGroup,
    QGridLayout,
    QPushButton,
    QStackedWidget,
    QWidget,
)

#: How many buttons go on one row before wrapping.
MAX_BUTTONS_PER_ROW = 14


@dataclass(frozen=True)
class ButtonSpec:
    """One button of the bar.

    Exactly one of `action` and `command` is set: `action` names an attribute
    of `MenuBar` whose `QAction` the button triggers and mirrors, `command` is
    an id of the form "family:label" emitted on `ButtonBar.command`.
    """

    label: str
    action: str | None = None
    command: str | None = None

    def __post_init__(self) -> None:
        if (self.action is None) == (self.command is None):
            raise ValueError(f"{self.label}: set exactly one of action, command")


def _menu(label: str, action: str) -> ButtonSpec:
    """A button that triggers a menu action."""
    return ButtonSpec(label, action=action)


def _cmd(label: str, family: str) -> ButtonSpec:
    """A button that emits "family:label"."""
    return ButtonSpec(label, command=f"{family}:{label}")


#: Category name -> its buttons, in DS9's order. Categories match DS9's
#: `CreateButtonsMajor` list, less Illustrate (an M9 feature NCRADS9 has none
#: of) and with VO added, which DS9 spreads across File and Analysis.
#: The category an analysis file's `button` tasks appear under. Not in
#: `CATEGORIES`, because it exists only once a file declares a buttonbar --
#: and deliberately not "Analysis", which is already the category mirroring
#: the Analysis *menu*. Sharing it would mix the two and let Clear Analysis
#: Commands delete the built-in buttons.
ANALYSIS_CATEGORY = "Tasks"

CATEGORIES: tuple[tuple[str, tuple[ButtonSpec, ...]], ...] = (
    (
        "File",
        (
            _menu("open", "action_open"),
            _menu("save", "action_save"),
            _menu("save as", "action_save_as"),
            _menu("header", "action_fits_header"),
            # DS9's own File bar carries one button per import format
            # (`mfile.tcl:512`); ours carries the first of them, since the
            # single `Export...` action this used to point at is gone --
            # M9-13 replaced it with DS9's ten-format cascades.
            _menu("import array", "action_import_array"),
            _menu("export array", "action_export_array"),
            _menu("print", "action_print"),
            _menu("prefs", "action_preferences"),
            _menu("exit", "action_exit"),
        ),
    ),
    (
        "Edit",
        (
            _menu("undo", "action_undo"),
            _menu("redo", "action_redo"),
            _menu("cut", "action_cut"),
            _menu("copy", "action_copy"),
            _menu("paste", "action_paste"),
        ),
    ),
    (
        "View",
        (
            _menu("horizontal", "action_view_horizontal"),
            _menu("vertical", "action_view_vertical"),
            _menu("basic", "action_view_basic"),
            _menu("advanced", "action_view_advanced"),
            _menu("info", "action_view_info"),
            _menu("panner", "action_view_panner"),
            _menu("magnifier", "action_view_magnifier"),
            _menu("buttons", "action_view_buttons"),
            _menu("icons", "action_view_icons"),
            _menu("colorbar", "action_view_colorbar"),
            _menu("graph horz", "action_view_graph_horizontal"),
            _menu("graph vert", "action_view_graph_vertical"),
        ),
    ),
    (
        "Frame",
        (
            _menu("new", "action_new_frame"),
            _menu("new rgb", "action_new_frame_rgb"),
            _menu("delete", "action_delete_frame"),
            _menu("clear", "action_clear_frame"),
            _menu("reset", "action_reset_frame"),
            _menu("refresh", "action_refresh_frame"),
            _menu("single", "action_single_frame"),
            _menu("tile", "action_tile_frames"),
            _menu("blink", "action_blink_frames"),
            _menu("first", "action_first_frame"),
            _menu("prev", "action_prev_frame"),
            _menu("next", "action_next_frame"),
            _menu("last", "action_last_frame"),
        ),
    ),
    (
        "Bin",
        (
            _menu("block in", "action_block_in"),
            _menu("block out", "action_block_out"),
            _menu("block fit", "action_block_fit"),
            _menu("block 1", "action_block_1"),
            _menu("block 2", "action_block_2"),
            _menu("block 4", "action_block_4"),
            _menu("block 8", "action_block_8"),
            _menu("block 16", "action_block_16"),
            _menu("block 32", "action_block_32"),
            _menu("params", "action_block_params"),
        ),
    ),
    (
        "Zoom",
        (
            _menu("center", "action_zoom_center"),
            _menu("align", "action_zoom_align"),
            _menu("in", "action_zoom_in"),
            _menu("out", "action_zoom_out"),
            _menu("fit", "action_zoom_fit"),
            _cmd("1/8", "zoom"),
            _cmd("1/4", "zoom"),
            _cmd("1/2", "zoom"),
            _menu("zoom 1", "action_zoom_1"),
            _cmd("2", "zoom"),
            _cmd("4", "zoom"),
            _cmd("8", "zoom"),
            _menu("none", "action_zoom_orient_none"),
            _menu("x", "action_zoom_orient_x"),
            _menu("y", "action_zoom_orient_y"),
            _menu("xy", "action_zoom_orient_xy"),
            _menu("0", "action_zoom_rotate_0"),
            _menu("90", "action_zoom_rotate_90"),
            _menu("180", "action_zoom_rotate_180"),
            _menu("270", "action_zoom_rotate_270"),
            _menu("params", "action_pan_zoom_rotate_parameters"),
        ),
    ),
    (
        "Scale",
        (
            _menu("linear", "action_scale_linear"),
            _menu("log", "action_scale_log"),
            _menu("sqrt", "action_scale_sqrt"),
            _menu("squared", "action_scale_squared"),
            _menu("asinh", "action_scale_asinh"),
            _menu("hist", "action_scale_histeq"),
            _menu("minmax", "action_scale_minmax"),
            _menu("zscale", "action_scale_zscale"),
            _menu("params", "action_scale_params"),
        ),
    ),
    (
        "Color",
        (
            _menu("grey", "action_cmap_gray"),
            _menu("heat", "action_cmap_heat"),
            _menu("cool", "action_cmap_cool"),
            _menu("rainbow", "action_cmap_rainbow"),
            _menu("viridis", "action_cmap_viridis"),
            _menu("invert", "action_invert_colormap"),
            _menu("reset", "action_reset_colormap"),
            _menu("horz", "action_colorbar_horizontal"),
            _menu("vert", "action_colorbar_vertical"),
            _menu("numerics", "action_colorbar_numerics_show"),
            _menu("params", "action_colormap_params"),
        ),
    ),
    (
        "Region",
        (
            _cmd("None", "region"),
            _cmd("Circle", "region"),
            _cmd("Ellipse", "region"),
            _cmd("Box", "region"),
            _cmd("Polygon", "region"),
            _cmd("Line", "region"),
            _cmd("Point", "region"),
            _menu("load", "action_region_load"),
            _menu("save", "action_region_save"),
            _menu("delete", "action_region_delete_all"),
        ),
    ),
    (
        "WCS",
        (
            _menu("fk5", "action_wcs_fk5"),
            _menu("fk4", "action_wcs_fk4"),
            _menu("icrs", "action_wcs_icrs"),
            _menu("galactic", "action_wcs_galactic"),
            _menu("ecliptic", "action_wcs_ecliptic"),
            _menu("sexagesimal", "action_wcs_sexagesimal"),
            _menu("degrees", "action_wcs_degrees"),
        ),
    ),
    (
        "Analysis",
        (
            _menu("pixel table", "action_pixel_table"),
            _menu("contours", "action_contours"),
            _menu("grid", "action_coordinate_grid"),
            _menu("smooth", "action_smooth"),
            _menu("statistics", "action_statistics"),
            _menu("histogram", "action_histogram"),
            _menu("radial", "action_radial_profile"),
        ),
    ),
    (
        "Help",
        (
            _menu("reference", "action_help_contents"),
            _menu("keys", "action_keyboard_shortcuts"),
            _menu("about", "action_about"),
        ),
    ),
)

#: The `command` families the bar emits, and the label of each family's
#: initially-checked button.
COMMAND_DEFAULTS: dict[str, str] = {"zoom": "zoom 1", "region": "None"}


class ButtonBar(QWidget):
    """DS9's two-row buttonbar."""

    #: Emitted with a "family:label" id when a button with no menu action is
    #: pressed. The window dispatches these to the owning controller.
    command: pyqtSignal = pyqtSignal(str)

    def __init__(self, menu_bar: QWidget, parent: QWidget | None = None) -> None:
        """
        Initialize the button bar.

        Args:
            menu_bar: The window's `MenuBar`, whose actions the buttons drive.
            parent: Optional parent widget.

        Raises:
            AttributeError: If a `ButtonSpec` names an action the menu bar
                does not have. Failing loudly here is the point: a button
                whose action was renamed would otherwise sit there dead.
        """
        super().__init__(parent)
        self._menu_bar = menu_bar

        #: Category name -> its page of buttons.
        self._pages: dict[str, QWidget] = {}
        #: Command family -> {label: button}, for the `set_*` methods below.
        self._command_buttons: dict[str, dict[str, QPushButton]] = {}

        self._outer = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self._outer.setContentsMargins(2, 2, 2, 2)
        self._outer.setSpacing(2)

        self._category_group = QButtonGroup(self)
        self._category_group.setExclusive(True)
        self._category_buttons: dict[str, QPushButton] = {}
        self._category_row = self._build_category_row()
        self._outer.addWidget(self._category_row)

        self._stack = QStackedWidget()
        self._outer.addWidget(self._stack)
        #: Category name -> its buttons, for re-gridding on an orientation
        #: change. The grid itself is rebuilt; the buttons are reused.
        self._page_buttons: dict[str, list[QPushButton]] = {}
        for name, specs in CATEGORIES:
            page = self._build_page(name, specs)
            self._pages[name] = page
            self._stack.addWidget(page)

        self._vertical = False
        self.set_category(CATEGORIES[0][0])
        for family, label in COMMAND_DEFAULTS.items():
            self._check_command(family, label)

    # -- construction --------------------------------------------------------

    def _build_category_row(self) -> QWidget:
        """The first row: one checkable button per menu."""
        row = QWidget()
        grid = QGridLayout(row)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(1)

        for name, _specs in CATEGORIES:
            button = QPushButton(name.lower())
            button.setCheckable(True)
            button.setFlat(True)
            button.clicked.connect(lambda _checked=False, n=name: self.set_category(n))
            self._category_buttons[name] = button
            self._category_group.addButton(button)
        self._grid_buttons(grid, list(self._category_buttons.values()), vertical=False)
        return row

    def _build_page(self, name: str, specs: tuple[ButtonSpec, ...]) -> QWidget:
        """One category's buttons, wrapped at `MAX_BUTTONS_PER_ROW`."""
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(1)

        buttons = [self._build_button(spec) for spec in specs]
        self._page_buttons[name] = buttons
        self._grid_buttons(grid, buttons, vertical=False)
        return page

    @staticmethod
    def _grid_buttons(grid: QGridLayout, buttons: list[QPushButton], *, vertical: bool) -> None:
        """(Re)place buttons in a grid, wrapping along the long axis."""
        while grid.count():
            grid.takeAt(0)
        for index in range(grid.rowCount()):
            grid.setRowStretch(index, 0)
        for index in range(grid.columnCount()):
            grid.setColumnStretch(index, 0)

        for index, button in enumerate(buttons):
            major, minor = divmod(index, MAX_BUTTONS_PER_ROW)
            row, column = (minor, major) if vertical else (major, minor)
            grid.addWidget(button, row, column)
            button.show()

        span = min(len(buttons), MAX_BUTTONS_PER_ROW)
        if vertical:
            grid.setRowStretch(span, 1)
        else:
            grid.setColumnStretch(span, 1)

    # -- orientation ---------------------------------------------------------

    def set_orientation(self, vertical: bool) -> None:
        """Run the bar down a column instead of across a row.

        DS9's vertical and advanced layouts grid the buttonbar beside the
        canvas rather than above it (`LayoutViewVert`), where a row of a
        dozen categories does not fit.
        """
        vertical = bool(vertical)
        if vertical == self._vertical:
            return
        self._vertical = vertical

        self._outer.setDirection(
            QBoxLayout.Direction.LeftToRight if vertical else QBoxLayout.Direction.TopToBottom
        )
        self._grid_buttons(
            self._category_row.layout(),
            list(self._category_buttons.values()),
            vertical=vertical,
        )
        for name, buttons in self._page_buttons.items():
            self._grid_buttons(self._pages[name].layout(), buttons, vertical=vertical)

    def _build_button(self, spec: ButtonSpec) -> QPushButton:
        """One button, wired either to its action or to the command signal."""
        button = QPushButton(spec.label)
        button.setFlat(True)

        if spec.command is not None:
            family, label = spec.command.split(":", 1)
            button.setCheckable(True)
            button.setAutoExclusive(False)
            button.clicked.connect(lambda _checked=False, c=spec.command: self._on_command(c))
            self._command_buttons.setdefault(family, {})[label] = button
            return button

        action: QAction = getattr(self._menu_bar, spec.action)
        button.setToolTip(action.text().replace("&", ""))
        if action.isCheckable():
            button.setCheckable(True)
            button.setChecked(action.isChecked())
            # Mirror the action rather than the click: the menu, an XPA
            # command or a keyboard shortcut can all change it too.
            action.toggled.connect(button.setChecked)
            button.clicked.connect(action.setChecked)
        else:
            button.clicked.connect(action.trigger)
        return button

    # -- categories ----------------------------------------------------------

    # -- analysis buttons (M7-2) ---------------------------------------------

    def add_analysis_button(self, label: str, handler) -> QPushButton:
        """Add a button for a `button` task from an analysis file.

        DS9's `buttonbar` ... `endbuttonbar` puts these on a bar of their
        own, which appears only once a file declares one -- a category with
        no buttons in it is an empty page nobody can use.
        """
        page = self._pages.get(ANALYSIS_CATEGORY)
        if page is None:
            page = self._build_page(ANALYSIS_CATEGORY, ())
            self._pages[ANALYSIS_CATEGORY] = page
            self._stack.addWidget(page)
            button = QPushButton(ANALYSIS_CATEGORY.lower())
            button.setCheckable(True)
            button.setFlat(True)
            button.clicked.connect(lambda _checked=False: self.set_category(ANALYSIS_CATEGORY))
            self._category_buttons[ANALYSIS_CATEGORY] = button
            self._category_group.addButton(button)
            self._grid_buttons(
                self._category_row.layout(),
                list(self._category_buttons.values()),
                vertical=False,
            )

        button = QPushButton(label)
        button.setFlat(True)
        button.clicked.connect(lambda _checked=False: handler())
        self._page_buttons.setdefault(ANALYSIS_CATEGORY, []).append(button)
        self._grid_buttons(page.layout(), self._page_buttons[ANALYSIS_CATEGORY], vertical=self._vertical)
        return button

    def clear_analysis_buttons(self) -> int:
        """Remove every analysis button, for Clear Analysis Commands.

        Returns:
            How many went.
        """
        buttons = self._page_buttons.get(ANALYSIS_CATEGORY, [])
        count = len(buttons)
        for button in buttons:
            button.setParent(None)
            button.deleteLater()
        self._page_buttons[ANALYSIS_CATEGORY] = []
        return count

    def set_category(self, name: str) -> None:
        """Show one category's buttons.

        Unknown names are ignored, so an XPA `buttons` command (M8) cannot
        raise from the UI thread.
        """
        page = self._pages.get(name)
        if page is None:
            return
        self._stack.setCurrentWidget(page)
        self._category_buttons[name].setChecked(True)

    def current_category(self) -> str:
        """The category whose buttons are showing."""
        for name, page in self._pages.items():
            if page is self._stack.currentWidget():
                return name
        return CATEGORIES[0][0]

    # -- command buttons -----------------------------------------------------

    def _on_command(self, command: str) -> None:
        """Tick the pressed button within its family, and emit the id."""
        family, label = command.split(":", 1)
        self._check_command(family, label)
        self.command.emit(command)

    def _check_command(self, family: str, label: str) -> None:
        """Tick one button of a family and untick the rest.

        The buttons are not in a `QButtonGroup` because a family's buttons can
        be spread over more than one wrapped row and the exclusive group would
        also swallow the untick when the controller rejects the change.
        """
        buttons = self._command_buttons.get(family, {})
        for text, button in buttons.items():
            button.setChecked(text == label)

    def set_zoom(self, level: str) -> None:
        """Tick the button for a zoom level, e.g. "1/2"."""
        self._check_command("zoom", level)

    def set_region_mode(self, mode: str) -> None:
        """Tick the button for a region shape, e.g. "Circle"."""
        self._check_command("region", mode)

    def set_scale(self, scale: str) -> None:
        """Tick the button for a scale algorithm.

        Kept for callers from before the bar was action-driven. The scale
        buttons now mirror the Scale menu's own checkable actions, so there is
        nothing left to do here.
        """

    def set_colormap(self, colormap: str) -> None:
        """Tick the button for a colormap.

        As `set_scale`: the colormap buttons mirror the Color menu's actions.
        """
