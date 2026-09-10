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

"""The catalog tool: filters, symbols, the list window, the overlay
(M8-1, M8-2, M8-3, M8-4, M8-7, M8-8, M8-9).

No network: the controller's `transport` is replaced throughout.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits
from astropy.table import Table

from ncrads9.catalogs.catalog_filter import (
    FilterError,
    columns_used,
    evaluate,
    evaluate_text,
    evaluate_values,
    translate,
)
from ncrads9.catalogs.catalog_set import (
    CatalogSet,
    LoadedCatalog,
    Symbol,
    load_symbols,
    save_symbols,
)

SIZE = 200


def _header() -> fits.Header:
    return fits.Header(
        {
            "NAXIS": 2,
            "NAXIS1": SIZE,
            "NAXIS2": SIZE,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CRPIX1": SIZE / 2,
            "CRPIX2": SIZE / 2,
            "CRVAL1": 150.0,
            "CRVAL2": 2.0,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
        }
    )


@pytest.fixture
def rows() -> Table:
    return Table(
        {
            "_RAJ2000": [150.00, 150.02, 149.98],
            "_DEJ2000": [2.00, 2.02, 1.98],
            "Jmag": [9.0, 11.0, 13.0],
            "Class": ["SNR", "HII", "SNR"],
        }
    )


@pytest.fixture
def catalog(rows) -> LoadedCatalog:
    return LoadedCatalog(name="GAIA DR2", table=rows, source="cds:I/345/gaia2")


# -- filter expressions (M8-4) ---------------------------------------------------


@pytest.mark.parametrize(
    "expression,expected",
    [
        # Every example in DS9's own documentation.
        ("$_RAJ2000>150.01 && $_RAJ2000<151.", [0, 1, 0]),
        ("$Jmag>11", [0, 0, 1]),
        ("[string equal $Class SNR]", [1, 0, 1]),
        ("[regexp {*SNR*} $Class]", [1, 0, 1]),
        # And its four constants.
        ("1", [1, 1, 1]),
        ("0", [0, 0, 0]),
        ("true", [1, 1, 1]),
        ("false", [0, 0, 0]),
        # An empty filter keeps everything.
        ("", [1, 1, 1]),
    ],
)
def test_ds9s_documented_filters(rows, expression, expected):
    assert evaluate(rows, expression).astype(int).tolist() == expected


def test_conjuncts_are_parenthesised():
    """Python binds `&` tighter than `>`, so a bare substitution turns
    `a>1 && a<2` into `a > (1 & a) < 2` -- a different question."""
    assert translate("$a>1 && $a<2") == '(_c["a"]>1) & (_c["a"]<2)'


def test_a_string_comparison_compares_values_not_names(rows):
    """Quoting the column reference too makes every row false."""
    assert evaluate(rows, "[string equal $Class HII]").astype(int).tolist() == [0, 1, 0]


def test_negation_works(rows):
    assert evaluate(rows, "!($Jmag>10)").astype(int).tolist() == [1, 0, 0]


def test_maths_functions_are_available(rows):
    assert evaluate(rows, "log($Jmag)>2.3").astype(int).tolist() == [0, 1, 1]


def test_a_missing_column_is_reported(rows):
    with pytest.raises(FilterError, match="no such column"):
        evaluate(rows, "$Nope>1")


def test_an_expression_that_is_not_per_row_is_reported(rows):
    with pytest.raises(FilterError, match="true or false for each row"):
        evaluate(rows, "min($Jmag, 1)[0:2]")


def test_the_namespace_has_no_builtins(rows):
    """A symbol expression can arrive inside a saved symbol file."""
    with pytest.raises(FilterError):
        evaluate(rows, "__import__('os').system('true')")


def test_columns_used_are_reported_in_order():
    assert columns_used("$Jmag>1 && $Class=='x' && $Jmag<2") == ["Jmag", "Class"]


def test_a_braced_column_name_works():
    table = Table({"J mag": [1.0, 5.0]})
    assert evaluate(table, "${J mag}>2").astype(int).tolist() == [0, 1]


# -- symbol expressions (M8-3) ------------------------------------------------------


def test_a_size_expression_gives_a_number_per_row(rows):
    assert evaluate_values(rows, "$Jmag/2.").tolist() == [4.5, 5.5, 6.5]


def test_a_constant_size_applies_to_every_row(rows):
    assert evaluate_values(rows, "2").tolist() == [2.0, 2.0, 2.0]


def test_an_unusable_size_falls_back(rows):
    """A symbol with a bad size expression still draws."""
    assert evaluate_values(rows, "$Nope", default=7.0).tolist() == [7.0, 7.0, 7.0]


@pytest.mark.parametrize(
    "expression,expected",
    [
        # "It is assumed to be text, unless you explicitly use an expr
        # operator" -- DS9's own words, and its own four examples.
        ("foo", ["foo", "foo", "foo"]),
        ("$Jmag", ["9", "11", "13"]),
        ("(4+2)/3", ["(4+2)/3"] * 3),
        ("[expr (4+2)/3]", ["2", "2", "2"]),
    ],
)
def test_ds9s_symbol_text_rules(rows, expression, expected):
    assert evaluate_text(rows, expression) == expected


def test_an_empty_text_is_empty(rows):
    assert evaluate_text(rows, "") == ["", "", ""]


# -- drawing symbols (M8-3) -----------------------------------------------------------


def test_a_catalogue_draws_one_symbol_per_row(catalog):
    assert len(catalog.draw()) == 3


def test_the_first_matching_rule_wins(catalog):
    """That is what makes a list of rules a classification."""
    catalog.symbols = [
        Symbol(condition="[string equal $Class SNR]", color="red"),
        Symbol(condition="1", color="cyan"),
    ]
    assert [symbol.color for symbol in catalog.draw()] == ["red", "cyan", "red"]


def test_a_row_matching_no_rule_is_not_drawn(catalog):
    catalog.symbols = [Symbol(condition="$Jmag>10", color="red")]
    assert [symbol.row for symbol in catalog.draw()] == [1, 2]


def test_a_rule_with_an_unusable_condition_is_skipped(catalog):
    """The other rules still classify the catalogue."""
    catalog.symbols = [Symbol(condition="$Nope>1", color="red"), Symbol(condition="1", color="cyan")]
    assert [symbol.color for symbol in catalog.draw()] == ["cyan"] * 3


def test_symbols_come_back_in_row_order(catalog):
    """Or the overlay flickers as a rule changes."""
    catalog.symbols = [Symbol(condition="$Jmag>10"), Symbol(condition="1")]
    assert [symbol.row for symbol in catalog.draw()] == [0, 1, 2]


def test_sizes_and_text_reach_the_symbols(catalog):
    catalog.symbols = [Symbol(condition="1", size="$Jmag", text="$Class")]
    drawn = catalog.draw()
    assert [symbol.size for symbol in drawn] == [9.0, 11.0, 13.0]
    assert [symbol.text for symbol in drawn] == ["SNR", "HII", "SNR"]


def test_a_catalogue_with_no_coordinates_draws_nothing():
    catalog = LoadedCatalog("x", Table({"Jmag": [9.0]}))
    assert catalog.draw() == []


def test_the_filter_hides_symbols(catalog):
    catalog.filter_expression = "$Jmag>10"
    assert [symbol.row for symbol in catalog.draw()] == [1, 2]


def test_a_bad_filter_keeps_every_row(catalog):
    """Hiding the catalogue over a typo, with no way to see the typo, is
    worse than ignoring it."""
    catalog.filter_expression = "$Nope>1"
    assert len(catalog.rows()) == 3
    assert "no such column" in catalog.filter_error


def test_the_selection_is_carried_on_the_symbols(catalog):
    catalog.select([1])
    assert [symbol.selected for symbol in catalog.draw()] == [False, True, False]


def test_a_selection_outside_the_table_is_ignored(catalog):
    catalog.select([0, 99])
    assert catalog.selected == {0}


def test_symbol_sets_round_trip(tmp_path):
    symbols = [
        Symbol(condition="$Jmag>10", shape="box point", color="red", size="$Jmag", text="$Class"),
        Symbol(condition="1", shape="diamond point", color="cyan"),
    ]
    path = tmp_path / "symbols.json"
    save_symbols(path, symbols)
    again = load_symbols(path)
    assert [entry.shape for entry in again] == ["box point", "diamond point"]
    assert again[0].size == "$Jmag"


def test_loading_something_that_is_not_a_symbol_set(tmp_path):
    path = tmp_path / "no.json"
    path.write_text('{"hello": 1}')
    with pytest.raises(ValueError, match="not a saved symbol set"):
        load_symbols(path)


# -- the set of catalogues (M8-9) --------------------------------------------------------


def test_two_catalogues_of_the_same_name_are_told_apart(rows):
    """They cannot be distinguished in a menu otherwise."""
    catalogs = CatalogSet()
    catalogs.add(LoadedCatalog("GAIA", rows))
    catalogs.add(LoadedCatalog("GAIA", rows))
    assert [entry.name for entry in catalogs] == ["GAIA", "GAIA (2)"]


def test_a_hidden_catalogue_draws_nothing(rows):
    catalogs = CatalogSet()
    catalogs.add(LoadedCatalog("A", rows, visible=False))
    assert catalogs.draw() == []


def test_clear_all_removes_everything(rows):
    catalogs = CatalogSet()
    catalogs.add(LoadedCatalog("A", rows))
    catalogs.add(LoadedCatalog("B", rows))
    assert catalogs.clear() == 2
    assert not catalogs


def test_one_catalogue_can_be_removed(rows):
    catalogs = CatalogSet()
    catalogs.add(LoadedCatalog("A", rows))
    catalogs.add(LoadedCatalog("B", rows))
    assert catalogs.remove("A") is True
    assert [entry.name for entry in catalogs] == ["B"]
    assert catalogs.remove("A") is False


def test_the_header_names_the_catalogue(catalog):
    header = catalog.header()
    assert "GAIA DR2" in header
    assert "cds:I/345/gaia2" in header
    assert "Rows\t3" in header


# -- the list window (M8-1, M8-2, M8-4) ----------------------------------------------------


@pytest.fixture
def window(qapp, catalog):
    from ncrads9.ui.dialogs.catalog_window import CatalogWindow

    made = CatalogWindow(catalog)
    yield made
    made.close()


def test_the_window_shows_every_row_and_column(window, catalog):
    assert window._table.rowCount() == 3
    assert window._table.columnCount() == len(catalog.columns)


def test_the_window_is_sortable(window):
    assert window._table.isSortingEnabled() is True


def test_numbers_sort_as_numbers(window):
    """A table item compares its display text, so a magnitude column would
    put 10 before 9."""
    from PyQt6.QtCore import Qt

    column = window.catalog.columns.index("Jmag")
    window._table.sortItems(column, Qt.SortOrder.AscendingOrder)
    shown = [window._table.item(row, column).text() for row in range(3)]
    assert shown == ["9", "11", "13"]


def test_selecting_a_row_here_announces_it(window):
    seen = []
    window.selection_changed.connect(seen.append)
    window.select_rows([1])
    assert seen == [[1]]
    assert window.catalog.selected == {1}


def test_a_symbol_click_highlights_the_row_without_a_loop(window):
    """`sync_selection` must not announce, or the two directions chase."""
    seen = []
    window.selection_changed.connect(seen.append)
    window.catalog.select([2])
    window.sync_selection()
    assert seen == []
    assert window._table.selectedItems()


def test_the_filter_narrows_the_table(window):
    window._filter.setText("$Jmag>10")
    window.apply_filter()
    assert window._table.rowCount() == 2


def test_clearing_the_filter_brings_the_rows_back(window):
    window._filter.setText("$Jmag>10")
    window.apply_filter()
    window.clear_filter()
    assert window._table.rowCount() == 3


def test_the_filter_change_is_announced(window):
    seen = []
    window.filter_changed.connect(seen.append)
    window._filter.setText("$Jmag>10")
    window.apply_filter()
    assert seen == ["$Jmag>10"]


def test_a_bad_filter_says_so_in_the_count_line(window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    window._filter.setText("$Nope>1")
    window.apply_filter()
    assert "filter ignored" in window._count.text()


def test_select_all_and_none(window):
    window.actions_by_name["select_all"].trigger()
    assert len(window.catalog.selected) == 3
    window.actions_by_name["select_none"].trigger()
    assert window.catalog.selected == set()


def test_the_window_can_be_printed_as_text(window):
    text = window.as_text()
    assert text.splitlines()[0].startswith("_RAJ2000")
    assert len(text.splitlines()) == 4


def test_copying_a_row_puts_it_on_the_clipboard(window):
    from PyQt6.QtGui import QGuiApplication

    window._table.setCurrentCell(0, 0)
    window.copy_row()
    assert "9" in QGuiApplication.clipboard().text()


def test_the_row_map_survives_a_sort(window):
    """The catalogue row travels with the cell, so a sort cannot break the
    link back to the data."""
    from PyQt6.QtCore import Qt

    column = window.catalog.columns.index("Jmag")
    window._table.sortItems(column, Qt.SortOrder.DescendingOrder)
    window._table.setCurrentCell(0, 0)
    assert window._current_row() == 2


# -- the overlay (M8-2) ----------------------------------------------------------------------


@pytest.fixture
def overlay(qapp):
    from ncrads9.ui.widgets.catalog_overlay import CatalogOverlay

    made = CatalogOverlay()
    made.resize(SIZE, SIZE)
    made.set_zoom(1.0, (0.0, 0.0), image_width=SIZE, image_height=SIZE)
    # A trivial projection, so the test is about the overlay and not the WCS.
    made.set_projection(lambda longitude, latitude: (longitude, latitude))
    return made


def test_the_overlay_draws_what_it_is_given(overlay, catalog):
    overlay.set_symbols(catalog.draw(), catalog.name)
    assert len(overlay.symbols) == 3


def test_a_click_on_a_symbol_reports_its_row(overlay):
    from ncrads9.catalogs.catalog_set import DrawnSymbol

    overlay.set_symbols([DrawnSymbol(row=7, longitude=50.0, latitude=50.0)], "GAIA")
    picked = overlay.symbol_at(overlay._image_to_widget(50.0, 50.0))
    assert picked is not None and picked.row == 7


def test_the_nearest_symbol_is_picked(overlay):
    """Symbols overlap in a crowded field; the closest is the one aimed at."""
    from ncrads9.catalogs.catalog_set import DrawnSymbol

    overlay.set_symbols(
        [
            DrawnSymbol(row=0, longitude=50.0, latitude=50.0),
            DrawnSymbol(row=1, longitude=53.0, latitude=50.0),
        ],
        "GAIA",
    )
    picked = overlay.symbol_at(overlay._image_to_widget(53.0, 50.0))
    assert picked.row == 1


def test_a_click_on_nothing_picks_nothing(overlay):
    from PyQt6.QtCore import QPointF

    from ncrads9.catalogs.catalog_set import DrawnSymbol

    overlay.set_symbols([DrawnSymbol(row=0, longitude=50.0, latitude=50.0)], "GAIA")
    assert overlay.symbol_at(QPointF(5.0, 5.0)) is None


def test_no_projection_means_no_symbols_drawn(overlay, catalog):
    """A frame with no WCS has nowhere to put them."""
    overlay.set_projection(None)
    overlay.set_symbols(catalog.draw(), catalog.name)
    assert overlay.symbol_at(overlay._image_to_widget(0.0, 0.0)) is None


# -- the controller (M8-7, M8-8, M8-9, M8-12) ---------------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path, rows):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32), header=_header()).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    # Every query answers from memory: no network, ever.
    window.catalog.transport = lambda request: rows
    yield window
    for catalog_window in list(window.catalog._windows.values()):
        catalog_window.close()
    window.close()


def test_a_menu_query_loads_a_catalogue(main_window):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    assert len(main_window.catalog.catalogs) == 1
    assert main_window.catalog.catalogs.catalogs[0].name == "GAIA DR2"


def test_a_query_opens_its_list_window(main_window):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    assert len(main_window.catalog._windows) == 1


def test_a_query_draws_its_symbols(main_window):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    assert len(main_window.image_viewer.catalog_overlay.symbols) == 3


def test_a_query_on_a_frame_with_no_wcs_says_so(main_window):
    from ncrads9.core.wcs_handler import WCSHandler

    main_window.frame_manager.current_frame.wcs_handler = WCSHandler(fits.Header())
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    assert "no WCS" in main_window.status_bar.currentMessage()
    assert len(main_window.catalog.catalogs) == 0


def test_an_empty_result_loads_nothing(main_window):
    main_window.catalog.transport = lambda request: None
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    assert len(main_window.catalog.catalogs) == 0
    assert "no objects found" in main_window.status_bar.currentMessage()


def test_a_failed_query_is_reported_not_raised(main_window):
    def broken(request):
        raise RuntimeError("server down")

    main_window.catalog.transport = broken
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    assert "server down" in main_window.status_bar.currentMessage()


def test_clear_all_removes_the_catalogues_and_their_windows(main_window):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    main_window.menu_bar.catalog_actions["catsimbad"].trigger()
    main_window.menu_bar.action_catalog_clear_all.trigger()
    assert len(main_window.catalog.catalogs) == 0
    assert main_window.catalog._windows == {}
    assert main_window.image_viewer.catalog_overlay.symbols == ()


def test_loading_a_local_file(main_window, tmp_path):
    path = tmp_path / "mine.rdb"
    path.write_text("RA\tDec\n--\t---\n150.0\t2.0\n")
    loaded = main_window.catalog.load_file(str(path))
    assert loaded is not None
    assert loaded.name == "mine"
    assert len(loaded.table) == 1


def test_loading_an_unreadable_file_is_reported(main_window, tmp_path):
    path = tmp_path / "bad.rdb"
    path.write_text("no rule here\n")
    assert main_window.catalog.load_file(str(path)) is None
    assert "bad.rdb" in main_window.status_bar.currentMessage()


def test_copying_a_catalogue_to_regions(main_window):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    catalog = main_window.catalog.catalogs.catalogs[0]
    main_window.catalog.to_regions(catalog)
    assert len(main_window.frame_manager.current_frame.regions) == 3


def test_copying_only_the_selection_when_there_is_one(main_window):
    """Which is what makes it useful for feeding an analysis task."""
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    catalog = main_window.catalog.catalogs.catalogs[0]
    catalog.select([1])
    main_window.catalog.to_regions(catalog)
    assert len(main_window.frame_manager.current_frame.regions) == 1


def test_plotting_two_columns(main_window, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog

    columns = iter([("Jmag", True), ("_RAJ2000", True)])
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: next(columns)))
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    main_window.catalog.plot(main_window.catalog.catalogs.catalogs[0])

    assert len(main_window.analysis._plots) == 1
    plot = next(iter(main_window.analysis._plots))
    assert plot.state.x_axis.label == "Jmag"
    assert len(plot.state.datasets[0].x) == 3
    plot.close()


def test_a_symbol_click_reaches_the_controller(main_window):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    main_window.catalog.on_symbol_picked("GAIA DR2", 2)
    assert main_window.catalog.catalogs.catalogs[0].selected == {2}


def test_the_symbols_follow_a_frame_change(main_window):
    """A different frame has a different WCS, so the symbols move."""
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    before = len(main_window.image_viewer.catalog_overlay.symbols)
    main_window.catalog.sync()
    assert len(main_window.image_viewer.catalog_overlay.symbols) == before


# -- the symbol editor (M8-3) ------------------------------------------------------


@pytest.fixture
def editor(qapp):
    from ncrads9.ui.dialogs.symbol_editor_dialog import SymbolEditorDialog

    made = SymbolEditorDialog(
        [Symbol(condition="$Jmag>10", color="red", shape="box point"), Symbol(color="cyan")],
        ["RA", "Dec", "Jmag"],
    )
    yield made
    made.close()


def test_the_editor_shows_a_row_per_rule(editor):
    assert editor._table.rowCount() == 2


def test_the_editor_reads_its_rules_back(editor):
    rules = editor.gather()
    assert [(rule.condition, rule.color, rule.shape) for rule in rules] == [
        ("$Jmag>10", "red", "box point"),
        ("", "cyan", "circle point"),
    ]


def test_the_editor_edits_a_copy(qapp):
    """Cancel has to really cancel."""
    from ncrads9.ui.dialogs.symbol_editor_dialog import SymbolEditorDialog

    original = [Symbol(color="red")]
    dialog = SymbolEditorDialog(original)
    dialog.symbols[0].color = "blue"
    assert original[0].color == "red"
    dialog.close()


def test_adding_and_removing_rules(editor):
    editor.buttons["add"].click()
    assert editor._table.rowCount() == 3
    editor._table.selectRow(0)
    editor.buttons["remove"].click()
    assert editor._table.rowCount() == 2


def test_the_last_rule_cannot_be_removed(qapp):
    """A catalogue with no rules draws nothing and offers no way back."""
    from ncrads9.ui.dialogs.symbol_editor_dialog import SymbolEditorDialog

    dialog = SymbolEditorDialog([Symbol(color="red")])
    dialog._table.selectRow(0)
    dialog.buttons["remove"].click()
    assert len(dialog.symbols) == 1
    dialog.close()


def test_reordering_changes_which_rule_wins(editor):
    """The order of the rules is the whole point."""
    editor._table.selectRow(0)
    editor.buttons["down"].click()
    assert [rule.color for rule in editor.gather()] == ["cyan", "red"]


def test_moving_past_the_end_does_nothing(editor):
    editor._table.selectRow(1)
    editor.buttons["down"].click()
    assert [rule.color for rule in editor.gather()] == ["red", "cyan"]


def test_the_editor_announces_its_rules(editor):
    seen = []
    editor.symbols_changed.connect(seen.append)
    editor.apply()
    assert len(seen) == 1 and len(seen[0]) == 2


def test_the_editor_saves_and_loads(editor, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    path = tmp_path / "rules.sym"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))
    editor.buttons["save"].click()

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
    editor.symbols = [Symbol(color="green")]
    editor.reload()
    editor.buttons["load"].click()
    assert [rule.color for rule in editor.symbols] == ["red", "cyan"]


def test_editing_symbols_from_the_window_redraws(main_window, monkeypatch):
    from ncrads9.ui.controllers import catalog as controller_module

    class Accepted(controller_module.SymbolEditorDialog):
        def exec(self):
            self.symbols_changed.emit([Symbol(condition="1", color="magenta")])
            return 1

    monkeypatch.setattr(controller_module, "SymbolEditorDialog", Accepted)
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    catalog = main_window.catalog.catalogs.catalogs[0]
    main_window.catalog.edit_symbols(catalog)

    assert [rule.color for rule in catalog.symbols] == ["magenta"]
    assert all(symbol.color == "magenta" for symbol in main_window.image_viewer.catalog_overlay.symbols)


# -- matching (M8-6) ---------------------------------------------------------------------


@pytest.fixture
def pair() -> tuple[Table, Table]:
    first = Table({"RA": [150.000, 150.010, 150.020], "DEC": [2.0, 2.0, 2.0], "Jmag": [9.0, 10.0, 11.0]})
    second = Table({"RA": [150.0001, 150.0102, 150.500], "DEC": [2.0, 2.0, 2.0], "Kmag": [8.0, 9.0, 10.0]})
    return (first, second)


def test_matching_finds_the_pairs_within_the_radius(pair):
    from ncrads9.catalogs.catalog_match import match

    matched = match(*pair, radius=5.0)
    assert len(matched) == 2
    assert "separation" in matched.colnames


def test_both_catalogues_columns_are_prefixed(pair):
    """Both have an RA; joining without a prefix keeps one of them."""
    from ncrads9.catalogs.catalog_match import match

    matched = match(*pair, radius=5.0)
    assert "1_RA" in matched.colnames
    assert "2_RA" in matched.colnames


def test_first_only_columns(pair):
    from ncrads9.catalogs.catalog_match import MatchReturn, match

    matched = match(*pair, radius=5.0, columns=MatchReturn.FIRST)
    assert matched.colnames == ["RA", "DEC", "Jmag", "separation"]


def test_one_not_two(pair):
    from ncrads9.catalogs.catalog_match import MatchFunction, match

    unmatched = match(*pair, radius=5.0, function=MatchFunction.FIRST_ONLY)
    assert len(unmatched) == 1
    assert unmatched["Jmag"][0] == pytest.approx(11.0)


def test_two_not_one(pair):
    from ncrads9.catalogs.catalog_match import MatchFunction, match

    unmatched = match(*pair, radius=5.0, function=MatchFunction.SECOND_ONLY)
    assert len(unmatched) == 1
    assert unmatched["Kmag"][0] == pytest.approx(10.0)


def test_unique_keeps_one_pair_per_row():
    """A crowded field gives a row per pair otherwise: one star five times."""
    from ncrads9.catalogs.catalog_match import match

    first = Table({"RA": [150.0], "DEC": [2.0]})
    crowd = Table({"RA": [150.0, 150.0001, 150.0002], "DEC": [2.0, 2.0, 2.0]})
    assert len(match(first, crowd, 5.0, unique=False)) == 3
    assert len(match(first, crowd, 5.0, unique=True)) == 1


def test_unique_keeps_the_closest_counterpart():
    from ncrads9.catalogs.catalog_match import match

    first = Table({"RA": [150.0], "DEC": [2.0]})
    crowd = Table({"RA": [150.0004, 150.0001], "DEC": [2.0, 2.0], "id": [1.0, 2.0]})
    matched = match(first, crowd, 5.0, unique=True)
    assert matched["2_id"][0] == pytest.approx(2.0)


def test_an_empty_match_still_has_its_columns(pair):
    """The caller has nothing to show otherwise, and no way to say what was
    asked."""
    from ncrads9.catalogs.catalog_match import match

    far = Table({"RA": [10.0], "DEC": [80.0]})
    matched = match(pair[0], far, radius=1.0)
    assert len(matched) == 0
    assert "1_RA" in matched.colnames


def test_matching_needs_positions():
    from ncrads9.catalogs.catalog_match import MatchError, match

    with pytest.raises(MatchError, match="no sky positions"):
        match(Table({"Jmag": [1.0]}), Table({"RA": [1.0], "DEC": [2.0]}))


def test_matching_from_the_controller(main_window, rows):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    main_window.menu_bar.catalog_actions["catsimbad"].trigger()
    names = [entry.name for entry in main_window.catalog.catalogs]

    matched = main_window.catalog.match(names[0], names[1], radius_arcsec=5.0)
    assert matched is not None
    assert len(main_window.catalog.catalogs) == 3
    assert "1and2" in matched.name


def test_matching_needs_two_loaded_catalogues(main_window):
    assert main_window.catalog.match("nope", "also nope") is None
    assert "Two loaded catalogs" in main_window.status_bar.currentMessage()


def test_a_match_with_no_pairs_is_reported(main_window, monkeypatch):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    main_window.catalog.transport = lambda request: Table({"_RAJ2000": [10.0], "_DEJ2000": [80.0]})
    main_window.menu_bar.catalog_actions["catsimbad"].trigger()
    names = [entry.name for entry in main_window.catalog.catalogs]

    assert main_window.catalog.match(names[0], names[1], radius_arcsec=1.0) is None
    assert "No matches" in main_window.status_bar.currentMessage()


# -- searching for catalogues (M8-10) --------------------------------------------------


def test_the_search_query_is_ds9s():
    """`CATCDSSrch` in `catcdssrchdialog.tcl:310`."""
    from ncrads9.catalogs.catalog_search import SearchRequest

    query = SearchRequest(source="I/345", words="gaia", wavelength="optical").query()
    assert query.startswith("-meta&")
    assert "-out.form=VOTable" in query
    assert "-source=I%2F345" in query
    assert "-kw.Wavelength=optical" in query


def test_a_keyword_of_none_is_not_a_filter():
    from ncrads9.catalogs.catalog_search import SearchRequest

    assert "-kw.Mission" not in SearchRequest(words="x", mission="none").query()


def test_a_search_with_no_terms_is_refused():
    """It is a download of twenty thousand descriptions and no way to read them."""
    from ncrads9.catalogs.catalog_search import SearchRequest, search

    assert search(SearchRequest()).message == "Enter something to search for"


def test_ds9s_keyword_lists_are_transcribed():
    from ncrads9.catalogs.catalog_search import ASTRONOMY, MISSIONS, WAVELENGTHS

    assert WAVELENGTHS == ("Radio", "IR", "optical", "UV", "EUV", "X-ray", "Gamma-ray")
    assert "Chandra" in MISSIONS and "XMM" in MISSIONS
    assert "SuperNovae_Remnants" in ASTRONOMY


def test_a_search_reads_a_votable_reply():
    from ncrads9.catalogs.catalog_search import SearchRequest, search

    votable = """<?xml version="1.0"?>
<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE><TABLE>
<FIELD name="name" datatype="char" arraysize="*"/>
<FIELD name="title" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>
<TR><TD>I/345/gaia2</TD><TD>Gaia DR2</TD></TR>
<TR><TD>I/337/gaia</TD><TD>Gaia DR1</TD></TR>
</TABLEDATA></DATA>
</TABLE></RESOURCE></VOTABLE>"""

    result = search(SearchRequest(words="gaia"), fetcher=lambda url, timeout: votable)
    assert result.found == [("I/345/gaia2", "Gaia DR2"), ("I/337/gaia", "Gaia DR1")]
    assert "2 catalogs found" in result.message


def test_a_search_that_finds_nothing_says_so():
    from ncrads9.catalogs.catalog_search import SearchRequest, search

    empty = '<?xml version="1.0"?><VOTABLE><RESOURCE/></VOTABLE>'
    assert search(SearchRequest(words="x"), fetcher=lambda u, t: empty).message == "No catalogs found"


def test_an_unreadable_reply_is_reported():
    from ncrads9.catalogs.catalog_search import SearchRequest, search

    result = search(SearchRequest(words="x"), fetcher=lambda u, t: "not xml at all")
    assert "could not read" in result.message


def test_a_search_failure_is_reported_not_raised():
    from ncrads9.catalogs.catalog_search import SearchRequest, search

    def broken(url, timeout):
        raise RuntimeError("down")

    assert "down" in search(SearchRequest(words="x"), fetcher=broken).message


def test_the_fetcher_refuses_a_non_http_url():
    from ncrads9.catalogs.catalog_search import SearchError, fetch

    with pytest.raises(SearchError, match="not an http URL"):
        fetch("file:///etc/passwd")


def test_the_search_dialog_builds_a_request(qapp):
    from ncrads9.ui.dialogs.catalog_search_dialog import CatalogSearchDialog

    dialog = CatalogSearchDialog()
    dialog._words.setText("gamma ray burst")
    dialog._wavelength.setCurrentText("X-ray")
    request = dialog.build_request()
    assert request.words == "gamma ray burst"
    assert request.wavelength == "X-ray"
    dialog.close()


def test_the_search_dialog_shows_and_chooses_a_result(qapp):
    from ncrads9.catalogs.catalog_search import SearchResult
    from ncrads9.ui.dialogs.catalog_search_dialog import CatalogSearchDialog

    dialog = CatalogSearchDialog()
    dialog.show_result(SearchResult(message="2 found", found=[("I/345", "Gaia"), ("V/147", "SDSS")]))
    assert dialog._results.rowCount() == 2

    chosen = []
    dialog.catalog_chosen.connect(chosen.append)
    dialog._results.selectRow(1)
    dialog.choose()
    assert chosen == ["V/147"]
    dialog.close()


def test_choosing_a_searched_catalogue_queries_it(main_window):
    """It is not on DS9's menu, so it has no `catXXX` name."""
    loaded = main_window.catalog.query_identifier("I/345/gaia2")
    assert loaded is not None
    assert loaded.name == "I/345/gaia2"
    assert "cds:I/345/gaia2" in loaded.source
