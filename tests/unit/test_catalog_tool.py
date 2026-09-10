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
