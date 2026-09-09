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


"""The window layout: `ViewState`, `WindowShell` and the information panel.

Covers M3's three new pieces separately from the window that hosts them:
the state DS9 keeps in its `view(...)` array, the grid that reads it, and the
information panel's field table.
"""

from __future__ import annotations

import numpy as np
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel

from ncrads9.ui.layout.shell import WindowShell
from ncrads9.ui.layout.view_state import (
    DEFAULT_INFO_FIELDS,
    INFO_FIELDS,
    PANEL_NAMES,
    WCS_SUFFIXES,
    ViewLayout,
    ViewState,
)
from ncrads9.ui.panels.info_panel import MAX_CELL_WIDTH, STRETCH_COLUMN, InfoPanel

# -- ViewState ---------------------------------------------------------------


def test_defaults_match_ds9_viewdef():
    """DS9's `ViewDef` in ds9/library/layout.tcl."""
    state = ViewState()
    assert state.layout is ViewLayout.HORIZONTAL
    assert (state.info, state.panner, state.magnifier) == (True, True, True)
    assert (state.buttons, state.icons, state.colorbar, state.multi) == (True, True, True, True)
    assert (state.graph_horizontal, state.graph_vertical) == (False, False)


def test_default_info_fields_match_ds9():
    state = ViewState()
    shown = {name for name in INFO_FIELDS if state.field_visible(name)}
    assert shown == set(DEFAULT_INFO_FIELDS)


def test_every_alternate_wcs_is_a_field():
    assert len(WCS_SUFFIXES) == 26
    for suffix in WCS_SUFFIXES:
        assert f"wcs_{suffix}" in INFO_FIELDS


def test_alternate_wcs_fields_start_hidden():
    state = ViewState()
    assert not any(state.field_visible(f"wcs_{s}") for s in WCS_SUFFIXES)


def test_value_field_is_always_visible():
    """DS9 grids the Value row unconditionally -- it has no menu toggle."""
    state = ViewState()
    assert state.field_visible("value")
    state.set_field_visible("value", False)
    assert state.field_visible("value")


def test_set_field_visible_rejects_unknown_names():
    with pytest.raises(KeyError):
        ViewState().set_field_visible("no_such_field", True)


@pytest.mark.parametrize(
    ("info", "panner", "magnifier", "expected"),
    [
        (True, True, True, True),
        (False, False, True, True),
        (False, True, False, True),
        (False, False, False, False),
    ],
)
def test_header_visible_needs_one_of_three(info, panner, magnifier, expected):
    """DS9 grids the header row if any of the three is on."""
    state = ViewState(info=info, panner=panner, magnifier=magnifier)
    assert state.header_visible is expected


def test_panel_names_are_all_attributes():
    state = ViewState()
    for name in PANEL_NAMES:
        assert isinstance(getattr(state, name), bool)


def test_states_do_not_share_their_field_table():
    """A mutable default would make every window's panel the same object."""
    first, second = ViewState(), ViewState()
    first.set_field_visible("keyword", True)
    assert not second.field_visible("keyword")


# -- WindowShell -------------------------------------------------------------


@pytest.fixture
def shell(qapp):
    """A shell over labelled stand-ins, so placement is all that is tested."""
    parts = {
        name: QLabel(name)
        for name in ("info", "panner", "magnifier", "buttons", "image", "colorbar", "graph_h", "graph_v")
    }
    widget = WindowShell(
        info_panel=parts["info"],
        panner=parts["panner"],
        magnifier=parts["magnifier"],
        button_bar=parts["buttons"],
        image_area=parts["image"],
        colorbar=parts["colorbar"],
        graph_horizontal=parts["graph_h"],
        graph_vertical=parts["graph_v"],
    )
    widget.parts = parts
    yield widget
    widget.deleteLater()


def _placed(shell) -> dict[str, tuple[int, int]]:
    """Grid position of every widget the shell's top-level grid holds."""
    grid = shell.layout()
    found = {}
    for index in range(grid.count()):
        item = grid.itemAt(index)
        row, column, _rows, _columns = grid.getItemPosition(index)
        found[item.widget()] = (row, column)
    return found


def test_horizontal_stacks_header_buttons_canvas(shell):
    shell.relayout(ViewState(layout=ViewLayout.HORIZONTAL))
    rows = {position[0] for position in _placed(shell).values()}
    # DS9's LayoutViewHorz: header 0, separator 1, buttons 2, separator 3,
    # canvas 4 -- all in column 0.
    assert rows == {0, 1, 2, 3, 4}
    assert {position[1] for position in _placed(shell).values()} == {0}


def test_vertical_runs_along_the_columns(shell):
    shell.relayout(ViewState(layout=ViewLayout.VERTICAL))
    positions = _placed(shell).values()
    assert {position[0] for position in positions} == {0}
    assert {position[1] for position in positions} == {0, 1, 2, 3, 4}


def test_basic_shows_only_the_canvas(shell):
    shell.relayout(ViewState(layout=ViewLayout.BASIC))
    assert len(_placed(shell)) == 1
    for name in ("info", "panner", "magnifier", "buttons"):
        assert shell.parts[name].isHidden()


def test_advanced_puts_the_canvas_first(shell):
    shell.relayout(ViewState(layout=ViewLayout.ADVANCED))
    placed = _placed(shell)
    canvas_column = next(c for w, (_r, c) in placed.items() if w is shell._canvas)
    buttons_column = next(c for w, (_r, c) in placed.items() if w is shell.parts["buttons"])
    assert canvas_column < buttons_column


def test_hiding_buttons_drops_them_from_the_grid(shell):
    shell.relayout(ViewState(buttons=False))
    assert shell.parts["buttons"] not in _placed(shell)
    assert shell.parts["buttons"].isHidden()


def test_hiding_every_header_panel_drops_the_header(shell):
    shell.relayout(ViewState(info=False, panner=False, magnifier=False))
    rows = {position[0] for position in _placed(shell).values()}
    assert 0 not in rows


def test_header_order_is_info_magnifier_panner(shell):
    """DS9 packs info left, then the magnifier, then the panner."""
    shell.relayout(ViewState(layout=ViewLayout.HORIZONTAL))
    box = shell._header_box
    order = [box.itemAt(i).widget() for i in range(box.count())]
    assert order == [shell.parts["info"], shell.parts["magnifier"], shell.parts["panner"]]


def test_stacked_layouts_put_the_magnifier_first(shell):
    """DS9's LayoutViewVert packs the magnifier above the info panel."""
    shell.relayout(ViewState(layout=ViewLayout.VERTICAL))
    box = shell._header_box
    order = [box.itemAt(i).widget() for i in range(box.count())]
    assert order == [shell.parts["magnifier"], shell.parts["info"], shell.parts["panner"]]


def test_hiding_the_info_panel_keeps_the_others_at_the_edge(shell):
    shell.relayout(ViewState(info=False))
    box = shell._header_box
    # A stretch takes the info panel's place, so the panner and magnifier do
    # not drift into the middle of the row.
    assert box.itemAt(0).widget() is None
    assert box.itemAt(1).widget() is shell.parts["magnifier"]


def test_separators_turn_with_the_layout(shell):
    shell.relayout(ViewState(layout=ViewLayout.HORIZONTAL))
    assert shell._header_separator.frameShape() == QFrame.Shape.HLine
    shell.relayout(ViewState(layout=ViewLayout.VERTICAL))
    assert shell._header_separator.frameShape() == QFrame.Shape.VLine


def test_colorbar_and_graphs_follow_their_flags(shell):
    shell.relayout(ViewState(colorbar=False, graph_horizontal=True, graph_vertical=False))
    assert shell.parts["colorbar"].isHidden()
    assert not shell.parts["graph_h"].isHidden()
    assert shell.parts["graph_v"].isHidden()


def test_relayout_is_idempotent(shell):
    """Re-gridding the same state twice must not duplicate a widget."""
    state = ViewState()
    shell.relayout(state)
    first = _placed(shell)
    shell.relayout(state)
    assert _placed(shell) == first


def test_every_layout_shows_the_canvas(shell):
    for layout in ViewLayout:
        shell.relayout(ViewState(layout=layout))
        assert shell._canvas in _placed(shell), layout


# -- InfoPanel ---------------------------------------------------------------


@pytest.fixture
def panel(qapp):
    widget = InfoPanel()
    yield widget
    widget.deleteLater()


def test_panel_starts_at_ds9_defaults(panel):
    assert panel.visible_fields() == (
        "filename",
        "object",
        "value",
        "wcs",
        "physical",
        "image",
        "frame",
    )


def test_fields_appear_in_ds9_grid_order(panel):
    for name in INFO_FIELDS:
        panel.set_field_visible(name, True)
    assert panel.visible_fields() == INFO_FIELDS


def test_shown_rows_are_packed_without_gaps(panel):
    """Turning a middle field off must not leave a blank row behind."""
    panel.set_field_visible("object", False)
    rows = {panel._grid.getItemPosition(i)[0] for i in range(panel._grid.count())}
    assert rows == set(range(len(rows)))


def test_minmax_occupies_two_rows(panel):
    """DS9 grids Min and Max as separate rows under one toggle."""
    before = len(panel.visible_fields())
    panel.set_field_visible("minmax", True)
    rows = {panel._grid.getItemPosition(i)[0] for i in range(panel._grid.count())}
    assert len(rows) == before + 2


def test_unknown_field_is_rejected(panel):
    with pytest.raises(KeyError):
        panel.set_field_visible("not_a_field", True)


def test_readout_setters_write_their_cells(panel):
    panel.set_filename("m51.fits")
    panel.set_object("M51")
    panel.set_units("Jy/beam")
    panel.set_value("1.25")
    panel.set_lowhigh("0.1", "9.9")
    panel.set_coords("image", "101", "121")
    panel.set_wcs("fk5", "13:29:52", "+47:11:43")
    panel.set_frame("Frame 1", "2", "90")

    assert panel._values["filename"].text() == "m51.fits"
    assert panel._values["object"].text() == "M51"
    assert panel._values["bunit"].text() == "Jy/beam"
    assert panel._values["value"].text() == "1.25"
    assert (panel._values["low"].text(), panel._values["high"].text()) == ("0.1", "9.9")
    assert (panel._values["image_x"].text(), panel._values["image_y"].text()) == ("101", "121")
    assert panel._values["wcs_label"].text() == "fk5"
    assert panel._values["frame"].text() == "Frame 1"
    assert panel._values["angle"].text() == "90"


def test_minmax_records_both_values_and_positions(panel):
    panel.set_minmax("-1", "9", ("3", "4"), ("5", "6"))
    assert panel._values["min"].text() == "-1"
    assert panel._values["max"].text() == "9"
    assert (panel._values["min_x"].text(), panel._values["min_y"].text()) == ("3", "4")
    assert (panel._values["max_x"].text(), panel._values["max_y"].text()) == ("5", "6")


def test_alternate_wcs_rows_are_addressable(panel):
    panel.set_wcs("wcsa", "10.5", "-20.25", suffix="a")
    assert panel._values["wcs_a_label"].text() == "wcsa"
    assert panel._values["wcs_a_x"].text() == "10.5"


def test_unknown_cell_is_ignored(panel):
    """A caller may offer a field the panel does not have."""
    panel.set_text("no_such_cell", "x")


def test_clear_cursor_keeps_the_image_description(panel):
    """DS9 leaves the file and object on screen when the pointer leaves."""
    panel.set_filename("m51.fits")
    panel.set_object("M51")
    panel.set_coords("image", "101", "121")
    panel.set_value("1.25")

    panel.clear_cursor()
    assert panel._values["filename"].text() == "m51.fits"
    assert panel._values["object"].text() == "M51"
    assert panel._values["image_x"].text() == ""
    assert panel._values["value"].text() == ""


def test_clear_blanks_everything(panel):
    panel.set_filename("m51.fits")
    panel.clear()
    assert panel._values["filename"].text() == ""


def test_apply_state_follows_the_state(panel):
    state = ViewState()
    state.set_field_visible("minmax", True)
    state.set_field_visible("object", False)
    panel.apply_state(state)
    assert panel.field_visible("minmax")
    assert not panel.field_visible("object")


def test_values_are_monospaced_and_selectable(panel):
    """The readout updates on every mouse move; proportional digits jitter."""
    label = panel._values["value"]
    assert label.font().styleHint() == label.font().StyleHint.TypeWriter
    assert label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse


def test_value_cells_never_shrink_below_their_text(panel):
    """An Ignored size policy let the columns print over each other."""
    label = panel._values["image_x"]
    assert label.minimumWidth() > 0
    assert label.sizePolicy().horizontalPolicy() != label.sizePolicy().Policy.Ignored


def test_panel_is_not_a_dock(panel):
    """The shell grids it; it must not be tearable."""
    from PyQt6.QtWidgets import QDockWidget

    assert not isinstance(panel, QDockWidget)


def test_statistics_are_not_part_of_the_panel(panel):
    """DS9's panel has no whole-image statistics; the dialog does."""
    assert not any(key in panel._values for key in ("mean", "std"))


def test_min_max_positions_are_blank_until_set(panel):
    panel.set_minmax("0", "1")
    assert panel._values["min_x"].text() == ""


def test_setting_an_image_does_not_need_data(panel):
    """The panel is a readout: it formats what it is handed, nothing more."""
    assert not hasattr(panel, "set_image")
    assert isinstance(np.float64(1.0), np.floating)


# -- InfoPanel: DS9's narrow layout ------------------------------------------


def _panel_rows(panel: InfoPanel) -> int:
    """How many grid rows the panel currently occupies."""
    positions = [panel._grid.getItemPosition(i)[0] for i in range(panel._grid.count())]
    return max(positions, default=-1) + 1


def _row_of(panel: InfoPanel, key: str) -> int:
    """The grid row one value cell sits on."""
    label = panel._values[key]
    for index in range(panel._grid.count()):
        if panel._grid.itemAt(index).widget() is label:
            return panel._grid.getItemPosition(index)[0]
    raise AssertionError(f"{key} is not gridded")


def _column_of(panel: InfoPanel, key: str) -> int:
    """The grid column one value cell sits in."""
    label = panel._values[key]
    for index in range(panel._grid.count()):
        if panel._grid.itemAt(index).widget() is label:
            return panel._grid.getItemPosition(index)[1]
    raise AssertionError(f"{key} is not gridded")


@pytest.mark.parametrize("layout", [ViewLayout.VERTICAL, ViewLayout.ADVANCED])
def test_narrow_layouts_break_fields_over_lines(panel, layout):
    """DS9's LayoutInfoPanelVert, which its Advanced procedure duplicates.

    The seven default fields take one line each across the seven columns, and
    2 + 2 + 2 + 3 + 3 + 3 + 3 = 18 lines in two columns.
    """
    panel.apply_state(ViewState())
    assert _panel_rows(panel) == 7
    panel.apply_state(ViewState(layout=layout))
    assert _panel_rows(panel) == 18


def test_narrow_layout_uses_two_columns(panel):
    state = ViewState(layout=ViewLayout.VERTICAL)
    panel.apply_state(state)
    columns = {panel._grid.getItemPosition(i)[1] for i in range(panel._grid.count())}
    assert columns == {0, 1}


def test_narrow_layout_puts_the_value_under_its_title(panel):
    panel.apply_state(ViewState(layout=ViewLayout.VERTICAL))
    # File on one line, its value on the next.
    assert _row_of(panel, "filename") == 1
    assert _column_of(panel, "filename") == 1


def test_narrow_layout_puts_axis_labels_in_column_zero(panel):
    panel.apply_state(ViewState(layout=ViewLayout.VERTICAL))
    # Image: title, then "x <value>", then "y <value>".
    x_row = _row_of(panel, "image_x")
    assert _row_of(panel, "image_y") == x_row + 1
    assert _column_of(panel, "image_x") == 1
    labels = [
        panel._grid.itemAt(i).widget()
        for i in range(panel._grid.count())
        if panel._grid.getItemPosition(i)[:2] == (x_row, 0)
    ]
    assert [w.text() for w in labels] == ["x"]


def test_narrow_minmax_takes_four_lines_each(panel):
    """DS9: title, x, y, then the extremum on its own line."""
    state = ViewState(layout=ViewLayout.VERTICAL)
    state.set_field_visible("minmax", True)
    panel.apply_state(state)
    assert _row_of(panel, "min_y") == _row_of(panel, "min_x") + 1
    assert _row_of(panel, "min") == _row_of(panel, "min_y") + 1
    # Four lines per block, so Max's extremum lands four rows after Min's.
    assert _row_of(panel, "max") == _row_of(panel, "min") + 4


def test_narrow_frame_row_labels_the_angle_before_its_value(panel):
    """The horizontal layout writes `Angle` after the value, the narrow one before."""
    panel.apply_state(ViewState())
    angle_column = _column_of(panel, "angle")
    panel.apply_state(ViewState(layout=ViewLayout.VERTICAL))
    assert _column_of(panel, "angle") == 1
    assert angle_column == 4


def test_switching_back_restores_the_wide_layout(panel):
    panel.apply_state(ViewState(layout=ViewLayout.VERTICAL))
    panel.apply_state(ViewState(layout=ViewLayout.HORIZONTAL))
    assert _panel_rows(panel) == 7
    assert _column_of(panel, "image_y") == 4


def test_narrow_layout_caps_the_wide_cells(panel):
    """DS9 drops every cell to thirteen characters in a column."""
    panel.apply_state(ViewState(layout=ViewLayout.VERTICAL))
    label = panel._values["filename"]
    assert label.maximumWidth() < MAX_CELL_WIDTH
    panel.apply_state(ViewState(layout=ViewLayout.HORIZONTAL))
    assert panel._values["filename"].maximumWidth() == MAX_CELL_WIDTH


def test_narrow_layout_has_nothing_in_the_stretch_column(panel):
    panel.apply_state(ViewState(layout=ViewLayout.VERTICAL))
    assert panel._grid.columnStretch(STRETCH_COLUMN) == 0
    panel.apply_state(ViewState(layout=ViewLayout.HORIZONTAL))
    assert panel._grid.columnStretch(STRETCH_COLUMN) == 1


def test_a_clipped_cell_keeps_its_value_on_hover(panel):
    panel.set_filename("/very/long/path/to/an/observation.fits")
    assert panel._values["filename"].toolTip() == "/very/long/path/to/an/observation.fits"


def test_hiding_a_field_removes_all_of_its_lines(panel):
    state = ViewState(layout=ViewLayout.VERTICAL)
    panel.apply_state(state)
    before = _panel_rows(panel)
    state.set_field_visible("image", False)
    panel.apply_state(state)
    assert _panel_rows(panel) == before - 3
