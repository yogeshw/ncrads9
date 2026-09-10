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

"""DS9's Prism: a FITS browser, not a spectrum tool (M9-9, M9-10)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.prism.browser import BLOCK, PrismBrowser

ROWS = 2500


@pytest.fixture
def fits_file(tmp_path):
    """A file with the three kinds of extension Prism has to tell apart."""
    path = tmp_path / "browse.fits"
    fits.HDUList(
        [
            fits.PrimaryHDU(),
            fits.ImageHDU(data=np.arange(16.0, dtype=np.float32).reshape(4, 4), name="IM"),
            fits.BinTableHDU.from_columns(
                [
                    fits.Column(name="X", format="E", array=np.arange(ROWS, dtype=np.float32)),
                    fits.Column(name="Y", format="E", array=np.arange(ROWS, dtype=np.float32) * 2),
                    fits.Column(name="NAME", format="8A", array=np.array([f"s{n}" for n in range(ROWS)])),
                ],
                name="EVENTS",
            ),
        ]
    ).writeto(path)
    return path


@pytest.fixture
def browser(fits_file):
    made = PrismBrowser()
    made.open(fits_file)
    return made


# -- the browser ----------------------------------------------------------------------


def test_opening_a_file_lists_every_extension(browser):
    assert [info.name for info in browser.extensions] == ["PRIMARY", "IM", "EVENTS"]
    assert [info.kind.value for info in browser.extensions] == ["empty", "image", "events"]


def test_the_dimensions_column_is_what_ds9_shows(browser):
    assert browser.extensions[1].dimensions == "4x4"
    assert browser.extensions[2].dimensions == f"{ROWS} rows x 3 cols"


def test_an_empty_primary_is_skipped_when_choosing_what_to_show(browser):
    """The primary of a multi-extension file says nothing about the file."""
    assert browser.index == 1


def test_a_single_image_file_shows_its_primary(tmp_path):
    path = tmp_path / "plain.fits"
    fits.PrimaryHDU(data=np.zeros((4, 4), dtype=np.float32)).writeto(path)
    made = PrismBrowser()
    made.open(path)
    assert made.index == 0


def test_a_file_that_is_not_there_raises(tmp_path):
    with pytest.raises(OSError):
        PrismBrowser().open(tmp_path / "missing.fits")


def test_the_header_is_the_extensions_own_cards(browser):
    text = browser.header_text(1)
    assert text.startswith("XTENSION= 'IMAGE")
    assert "EXTNAME = 'IM" in text
    # And not another extension's.
    assert "EVENTS" not in text


def test_the_header_of_no_file_is_empty():
    assert PrismBrowser().header_text() == ""


def test_an_image_extension_has_no_rows(browser):
    browser.select(1)
    assert browser.is_table is False
    assert browser.block() == ([], [])


def test_a_table_extension_gives_a_block_of_rows(browser):
    browser.select(2)
    names, rows = browser.block()
    assert names == ["X", "Y", "NAME"]
    assert len(rows) == BLOCK
    assert rows[0] == ["0", "0", "s0"]


def test_a_string_column_is_read_as_text_not_bytes(browser):
    browser.select(2)
    _names, rows = browser.block()
    assert rows[5][2] == "s5"


def test_the_blocks_page_through_the_rows(browser):
    browser.select(2)
    assert browser.start == 0
    assert browser.next_block() == BLOCK
    assert browser.next_block() == 2000
    # Past the end stops on the last block, not beyond it.
    assert browser.next_block() == 2000
    assert browser.previous_block() == 1000
    assert browser.first_block() == 0
    assert browser.previous_block() == 0
    assert browser.last_block() == 2000


def test_the_last_block_of_an_exact_multiple_is_the_last_full_one(tmp_path):
    """2000 rows is two full blocks: the last one starts at 1000, not 2000,
    where there is nothing to show."""
    path = tmp_path / "exact.fits"
    fits.BinTableHDU.from_columns(
        [fits.Column(name="X", format="E", array=np.arange(2 * BLOCK, dtype=np.float32))]
    ).writeto(path)
    made = PrismBrowser()
    made.open(path)
    assert made.last_block() == BLOCK


def test_the_last_block_of_an_image_is_the_first(browser):
    browser.select(1)
    assert browser.last_block() == 0


def test_going_to_a_row_shows_the_block_it_is_in(browser):
    browser.select(2)
    assert browser.goto_row(1500) == 499
    assert browser.start == 1000
    assert browser.goto_row(1) == 0
    assert browser.start == 0


def test_going_past_the_last_row_stops_at_it(browser):
    browser.select(2)
    assert browser.goto_row(99999) == ROWS - 1 - 2000
    assert browser.start == 2000


def test_selecting_an_extension_goes_back_to_its_first_block(browser):
    browser.select(2)
    browser.last_block()
    browser.select(2)
    assert browser.start == 0


def test_selecting_an_extension_that_is_not_there_does_nothing(browser):
    assert browser.select(99) is None
    assert browser.index == 1


def test_a_column_is_read_whole_not_just_the_block(browser):
    """A plot of a thousand rows out of a million is a plot of the wrong
    thing."""
    browser.select(2)
    browser.last_block()
    values = browser.column("Y")
    assert len(values) == ROWS
    assert values[-1] == pytest.approx((ROWS - 1) * 2)


def test_a_column_that_is_not_there_raises(browser):
    browser.select(2)
    with pytest.raises(KeyError):
        browser.column("NOPE")


def test_an_images_columns_cannot_be_read(browser):
    browser.select(1)
    with pytest.raises(KeyError):
        browser.column("X")


def test_a_vector_column_is_read_as_its_first_element(tmp_path):
    path = tmp_path / "vector.fits"
    fits.BinTableHDU.from_columns(
        [fits.Column(name="V", format="3E", array=np.arange(12.0).reshape(4, 3))]
    ).writeto(path)
    made = PrismBrowser()
    made.open(path)
    assert list(made.column("V")) == [0.0, 3.0, 6.0, 9.0]


def test_a_vector_cell_is_shown_short_enough_to_read(tmp_path):
    path = tmp_path / "wide.fits"
    fits.BinTableHDU.from_columns(
        [fits.Column(name="V", format="6E", array=np.arange(12.0).reshape(2, 6))]
    ).writeto(path)
    made = PrismBrowser()
    made.open(path)
    _names, rows = made.block()
    assert rows[0][0].startswith("[0, 1, 2, 3 ...")


def test_clearing_forgets_the_file(browser):
    browser.clear()
    assert browser.is_open is False
    assert browser.extensions == []
    assert browser.header_text() == ""


def test_a_browser_holds_no_file_open(fits_file):
    """A Prism window can sit on a file for as long as it likes; keeping a
    descriptor per window would not scale and would lock the file on
    Windows."""
    made = PrismBrowser()
    made.open(fits_file)
    made.select(2)
    made.block()
    # Nothing to assert about descriptors portably; what matters is that the
    # file can be replaced underneath us without an error.
    fits_file.write_bytes(fits_file.read_bytes())
    assert made.header_text() != ""


# -- the window ----------------------------------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=np.zeros((32, 32), dtype=np.float32)).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    yield window
    window.close()


@pytest.fixture
def prism(main_window, fits_file):
    made = main_window.prism.show(fits_file)
    yield made
    made.close()


def test_the_menus_are_ds9s(prism):
    for name in (
        "open",
        "import_votable",
        "import_starbase",
        "import_tsv",
        "export_votable",
        "export_starbase",
        "export_tsv",
        "image",
        "clear",
        "close",
        "cut",
        "copy",
        "paste",
        "select_all",
        "select_none",
        "find",
        "find_next",
        "plot",
        "histogram",
        "first_block",
        "next_block",
        "previous_block",
        "last_block",
        "goto_row",
    ):
        assert name in prism.actions_by_name


def test_cut_and_paste_are_disabled_as_they_are_in_ds9(prism):
    """Prism browses a file: there is nothing to cut and nowhere to paste."""
    assert prism.actions_by_name["cut"].isEnabled() is False
    assert prism.actions_by_name["paste"].isEnabled() is False


def test_the_extension_list_is_filled(prism):
    assert prism.extensions.topLevelItemCount() == 3
    row = prism.extensions.topLevelItem(2)
    assert [row.text(column) for column in range(3)] == ["EVENTS", "events", f"{ROWS} rows x 3 cols"]


def test_the_default_selection_is_the_first_real_extension(prism):
    assert prism.extensions.indexOfTopLevelItem(prism.extensions.currentItem()) == 1
    assert "EXTNAME = 'IM" in prism.header.toPlainText()


def test_choosing_an_extension_shows_its_header_and_rows(prism):
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(2))
    assert "EVENTS" in prism.header.toPlainText()
    assert prism.data.horizontalHeaderItem(0).text() == "X"
    assert prism.data.item(0, 0).text() == "0"


def test_an_image_extension_shows_no_rows(prism):
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(1))
    assert prism.data.item(0, 0) is None
    assert "image 4x4" in prism._rows_label.text()


def test_the_row_numbers_are_the_files_not_the_blocks(prism):
    """Paging to row 1001 must not label it row 1."""
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(2))
    prism.next_block()
    assert prism.data.verticalHeaderItem(0).text() == "1001"
    assert "rows 1001-2000 of 2500" in prism._rows_label.text()


def test_the_block_buttons_page_the_table(prism):
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(2))
    prism.last_block()
    assert prism.data.item(0, 0).text() == "2000"
    prism.first_block()
    assert prism.data.item(0, 0).text() == "0"


def test_goto_row_selects_it(prism):
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(2))
    prism.goto_row(1500)
    assert prism.browser.start == 1000
    assert prism.data.currentRow() == 499


def test_paging_is_off_for_an_image_and_on_for_a_table(prism):
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(1))
    assert prism.actions_by_name["next_block"].isEnabled() is False
    assert prism.actions_by_name["plot"].isEnabled() is False

    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(2))
    assert prism.actions_by_name["next_block"].isEnabled() is True
    assert prism.actions_by_name["plot"].isEnabled() is True


def test_image_is_offered_for_any_fits_extension(prism):
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(1))
    assert prism.actions_by_name["image"].isEnabled() is True


def test_clearing_empties_every_pane(prism):
    prism.clear()
    assert prism.extensions.topLevelItemCount() == 0
    assert prism.header.toPlainText() == ""
    assert "No file loaded" in prism._rows_label.text()
    assert prism.actions_by_name["image"].isEnabled() is False


def test_opening_a_file_that_is_not_fits_is_reported(prism, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    bad = tmp_path / "notfits.txt"
    bad.write_text("hello")
    assert prism.open_file(str(bad)) is False


def test_image_loads_the_chosen_extension_into_a_new_frame(prism, main_window):
    before = main_window.frame_manager.num_frames
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(1))
    assert prism.load_image() is True
    assert main_window.frame_manager.num_frames == before + 1
    # The image extension's data, not the empty primary's.
    assert main_window.frame_manager.current_frame.image_data.shape == (4, 4)


def test_image_with_nothing_loaded_says_so(prism, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warned.append(args[-1]))
    prism.clear()
    assert prism.load_image() is False
    assert "No file loaded" in warned[0]


# -- Plot and Histogram ------------------------------------------------------------------


def test_plotting_two_columns_opens_a_plot(prism):
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(2))
    plot = prism.plot("X", "Y")
    assert plot is not None
    dataset = plot.state.datasets[0]
    assert len(dataset.x) == ROWS
    assert dataset.y[10] == pytest.approx(20.0)
    plot.close()


def test_a_histogram_bins_one_column(prism):
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(2))
    plot = prism.histogram("X", bins=5)
    assert plot is not None
    dataset = plot.state.datasets[0]
    assert len(dataset.y) == 5
    assert sum(dataset.y) == ROWS
    plot.close()


def test_a_histogram_is_drawn_as_bars(prism):
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(2))
    plot = prism.histogram("X", bins=3)
    assert plot.state.style.value == "bar"
    plot.close()


def test_plotting_an_image_extension_is_refused(prism, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warned.append(args[-1]))
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(1))
    assert prism.plot() is None
    assert "two numeric columns" in warned[0]


def test_only_numeric_columns_are_offered(prism):
    """The string column cannot be plotted against anything."""
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(2))
    assert prism._numeric_columns() == ["X", "Y"]


# -- Import and Export --------------------------------------------------------------------


def test_importing_a_table_replaces_the_fits_view(prism, tmp_path):
    from ncrads9.catalogs import catalog_file

    path = tmp_path / "cat.tsv"
    path.write_text("A\tB\n1\t2\n3\t4\n")
    assert prism.import_table(catalog_file.CatalogFormat.TSV, str(path)) is True

    assert prism.extensions.topLevelItemCount() == 0
    assert prism.data.item(0, 0).text() == "1"
    assert "2 rows x 2 columns" in prism._rows_label.text()
    # An imported table has no extension to load into a frame.
    assert prism.actions_by_name["image"].isEnabled() is False
    assert prism.actions_by_name["plot"].isEnabled() is True


def test_an_imported_table_can_be_plotted(prism, tmp_path):
    from ncrads9.catalogs import catalog_file

    path = tmp_path / "cat.tsv"
    path.write_text("A\tB\n1\t2\n3\t4\n")
    prism.import_table(catalog_file.CatalogFormat.TSV, str(path))
    plot = prism.plot("A", "B")
    assert plot.state.datasets[0].y == [2.0, 4.0]
    plot.close()


def test_importing_something_unreadable_is_reported(prism, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from ncrads9.catalogs import catalog_file

    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    path = tmp_path / "bad.xml"
    path.write_text("<not a votable>")
    assert prism.import_table(catalog_file.CatalogFormat.VOTABLE, str(path)) is False


def test_exporting_writes_the_fits_table_out(prism, tmp_path):
    from ncrads9.catalogs import catalog_file

    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(2))
    path = tmp_path / "out.tsv"
    assert prism.export_table(catalog_file.CatalogFormat.TSV, str(path)) is True

    written = catalog_file.load(path, catalog_file.CatalogFormat.TSV)
    assert list(written.colnames) == ["X", "Y"]
    assert len(written) == ROWS


def test_exporting_with_no_table_is_refused(prism, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from ncrads9.catalogs import catalog_file

    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warned.append(args[-1]))
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(1))
    assert prism.export_table(catalog_file.CatalogFormat.TSV, str(tmp_path / "x.tsv")) is False
    assert "no table to export" in warned[0]


# -- the Edit menu ------------------------------------------------------------------------


def test_copying_the_table_selection(prism):
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(2))
    prism.data.setCurrentCell(0, 0)
    assert prism.copy() == "0"


def test_find_searches_the_header(prism):
    assert prism.find("EXTNAME") is True
    assert prism.find("NOT-A-KEYWORD") is False


def test_find_next_carries_on_from_the_last_search(prism):
    prism.extensions.setCurrentItem(prism.extensions.topLevelItem(2))
    assert prism.find("TTYPE") is True
    assert prism.find_next() is True


def test_find_next_with_nothing_searched_yet_asks(prism, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("", False))
    assert prism.find_next() is False


def test_select_all_and_none_work_on_the_header(prism):
    prism.select_all()
    assert prism.header.textCursor().hasSelection() is True
    prism.select_none()
    assert prism.header.textCursor().hasSelection() is False


# -- File -> Prism ------------------------------------------------------------------------


def test_the_file_menu_opens_prism_on_the_current_frames_file(main_window):
    main_window.menu_bar.action_prism.trigger()
    dialog = main_window.prism.latest
    assert dialog is not None
    assert dialog.browser.is_open is True
    assert dialog.browser.path == main_window.frame_manager.current_frame.filepath
    dialog.close()


def test_prism_opens_empty_when_the_frame_has_no_file(main_window):
    main_window.frame_controller.new_frame()
    main_window.menu_bar.action_prism.trigger()
    dialog = main_window.prism.latest
    assert dialog.browser.is_open is False
    dialog.close()


def test_the_extension_specifier_is_stripped_before_browsing(main_window, fits_file):
    """Prism browses the whole file, not the one extension on screen."""
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(f"{fits_file}[2]")
    assert main_window.prism.current_path() == fits_file


def test_more_than_one_prism_window_can_be_open(main_window, fits_file):
    first = main_window.prism.show(fits_file)
    second = main_window.prism.show(fits_file)
    assert len(main_window.prism.windows) == 2
    assert main_window.prism.latest is second
    first.close()
    second.close()


def test_closing_a_prism_window_is_noticed(main_window, fits_file):
    dialog = main_window.prism.show(fits_file)
    dialog.close()
    dialog.reject()
    assert main_window.prism.windows == []


# -- the prism XPA point (M9-10) -------------------------------------------------------


@pytest.fixture
def xpa(main_window):
    from ncrads9.communication.xpa.xpa_commands import XPACommands

    return XPACommands(main_window)


def _set(xpa, *args):
    return xpa.handle("prism", {"args": list(args)})


def test_xpaget_prism_lists_the_open_windows(xpa, main_window, fits_file):
    first = main_window.prism.show(fits_file)
    second = main_window.prism.show(fits_file)
    assert xpa.handle("prism", {"get": True})["result"].split("\n") == ["prism", "prism2"]
    first.close()
    second.close()


def test_xpaset_prism_with_no_arguments_opens_one(xpa, main_window):
    assert _set(xpa)["status"] == "ok"
    assert len(main_window.prism.windows) == 1
    main_window.prism.latest.close()


def test_prism_open_uses_the_current_frames_file(xpa, main_window):
    """As DS9's parser has it: bare `prism` and `prism open` both go through
    `PrismDialogLoad` (`prismparser.tac:49`)."""
    _set(xpa, "open")
    assert main_window.prism.latest.browser.path == main_window.frame_manager.current_frame.filepath
    for dialog in list(main_window.prism.windows):
        dialog.close()


def test_prism_load_opens_a_window_on_that_file(xpa, main_window, fits_file):
    _set(xpa, "load", str(fits_file))
    assert main_window.prism.latest.browser.path == fits_file
    for dialog in list(main_window.prism.windows):
        dialog.close()


def test_a_bare_filename_opens_a_window_on_it(xpa, main_window, fits_file):
    """`xpaset -p ds9 prism foo.fits` (`prismparser.tac:51`)."""
    assert _set(xpa, str(fits_file))["status"] == "ok"
    assert main_window.prism.latest.browser.path == fits_file
    for dialog in list(main_window.prism.windows):
        dialog.close()


def test_prism_load_needs_a_filename(xpa):
    assert _set(xpa, "load")["status"] == "error"


def test_prism_current_switches_which_window_xpa_talks_to(xpa, main_window, fits_file):
    first = main_window.prism.show(fits_file)
    second = main_window.prism.show(fits_file)
    assert main_window.prism.latest is second
    assert _set(xpa, "current", "prism")["status"] == "ok"
    assert main_window.prism.latest is first
    assert _set(xpa, "current", "prism9")["status"] == "error"
    first.close()
    second.close()


def test_prism_ext_by_number_and_by_name(xpa, main_window, fits_file):
    dialog = main_window.prism.show(fits_file)
    assert _set(xpa, "ext", "2")["status"] == "ok"
    assert dialog.browser.index == 2
    assert _set(xpa, "ext", "IM")["status"] == "ok"
    assert dialog.browser.index == 1
    assert _set(xpa, "ext", "NOPE")["status"] == "error"
    dialog.close()


def test_prism_pages_and_goes_to_a_row(xpa, main_window, fits_file):
    dialog = main_window.prism.show(fits_file)
    _set(xpa, "ext", "EVENTS")
    _set(xpa, "next")
    assert dialog.browser.start == BLOCK
    _set(xpa, "last")
    assert dialog.browser.start == 2000
    _set(xpa, "prev")
    assert dialog.browser.start == 1000
    _set(xpa, "first")
    assert dialog.browser.start == 0
    _set(xpa, "goto", "1500")
    assert dialog.browser.start == 1000
    dialog.close()


def test_prism_image_loads_the_extension(xpa, main_window, fits_file):
    dialog = main_window.prism.show(fits_file)
    _set(xpa, "ext", "IM")
    before = main_window.frame_manager.num_frames
    assert _set(xpa, "image")["status"] == "ok"
    assert main_window.frame_manager.num_frames == before + 1
    dialog.close()


def test_prism_clear(xpa, main_window, fits_file):
    dialog = main_window.prism.show(fits_file)
    assert _set(xpa, "clear")["status"] == "ok"
    assert dialog.browser.is_open is False
    dialog.close()


def test_prism_plot_with_the_column_shapes(xpa, main_window, fits_file):
    dialog = main_window.prism.show(fits_file)
    _set(xpa, "ext", "EVENTS")

    assert _set(xpa, "plot", "X", "Y", "xy")["status"] == "ok"
    assert dialog._plots[-1].state.datasets[0].y_error == []

    assert _set(xpa, "plot", "X", "Y", "Y", "xyey")["status"] == "ok"
    assert len(dialog._plots[-1].state.datasets[0].y_error) == ROWS

    assert _set(xpa, "plot", "X", "Y", "X", "Y", "xyexey")["status"] == "ok"
    dataset = dialog._plots[-1].state.datasets[0]
    assert len(dataset.x_error) == ROWS and len(dataset.y_error) == ROWS

    for plot in dialog._plots:
        plot.close()
    dialog.close()


def test_prism_plot_needs_two_columns(xpa, main_window, fits_file):
    dialog = main_window.prism.show(fits_file)
    _set(xpa, "ext", "EVENTS")
    assert _set(xpa, "plot", "X")["status"] == "error"
    dialog.close()


def test_prism_histogram_with_and_without_limits(xpa, main_window, fits_file):
    dialog = main_window.prism.show(fits_file)
    _set(xpa, "ext", "EVENTS")

    assert _set(xpa, "histogram", "X", "40")["status"] == "ok"
    assert len(dialog._plots[-1].state.datasets[0].y) == 40

    assert _set(xpa, "histogram", "X", "10", "0", "100")["status"] == "ok"
    counts = dialog._plots[-1].state.datasets[0].y
    # Only the rows in 0..100 are counted when a range is given.
    assert sum(counts) == pytest.approx(101.0)

    for plot in dialog._plots:
        plot.close()
    dialog.close()


def test_prism_mode_overplots_onto_the_last_plot(xpa, main_window, fits_file):
    dialog = main_window.prism.show(fits_file)
    _set(xpa, "ext", "EVENTS")
    _set(xpa, "plot", "X", "Y", "xy")
    assert _set(xpa, "mode", "overplot")["status"] == "ok"
    _set(xpa, "plot", "Y", "X", "xy")

    assert len(dialog._plots) == 1
    assert len(dialog._plots[0].state.datasets) == 2
    dialog._plots[0].close()
    dialog.close()


def test_prism_mode_is_reported_back(xpa, main_window, fits_file):
    dialog = main_window.prism.show(fits_file)
    assert _set(xpa, "mode")["result"] == "newplot"
    dialog.close()


def test_prism_import_and_export_through_xpa(xpa, main_window, tmp_path):
    from ncrads9.catalogs import catalog_file

    source = tmp_path / "in.tsv"
    source.write_text("A\tB\n1\t2\n3\t4\n")
    assert _set(xpa, "import", "tsv", str(source))["status"] == "ok"

    out = tmp_path / "out.rdb"
    assert _set(xpa, "export", "rdb", str(out))["status"] == "ok"
    assert list(catalog_file.load(out, catalog_file.CatalogFormat.STARBASE).colnames) == ["A", "B"]

    for dialog in list(main_window.prism.windows):
        dialog.close()


def test_prism_import_needs_a_known_format(xpa):
    assert _set(xpa, "import", "sqlite", "/tmp/x")["status"] == "error"


def test_an_unknown_prism_command_is_reported(xpa, main_window, fits_file):
    dialog = main_window.prism.show(fits_file)
    assert "Unknown prism command" in _set(xpa, "wibble")["message"]
    dialog.close()


def test_prism_commands_need_a_window(xpa):
    assert _set(xpa, "clear")["status"] == "error"
