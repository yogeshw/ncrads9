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

"""The Python console, Tile Parameters and Display Size (M9-34..M9-36)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.frames.tile_layout import TileLayout, TileMode, TileSettings

SIZE = 16


# -- the tile grid ----------------------------------------------------------------


def test_the_automatic_grid_is_as_square_as_it_can_be():
    layout = TileLayout.compute(5, 10, 10, TileMode.GRID)
    assert (layout.rows, layout.cols) == (2, 3)


def test_a_manual_grid_is_the_one_asked_for():
    layout = TileLayout.compute(4, 10, 10, manual=(2, 2))
    assert (layout.rows, layout.cols) == (2, 2)


def test_a_manual_grid_too_small_is_grown_rather_than_losing_a_frame():
    """DS9's dialog asks for a shape, not for some of the frames."""
    layout = TileLayout.compute(5, 10, 10, manual=(2, 2))
    assert layout.rows * layout.cols >= 5
    assert len(layout.placements()) == 5


def test_a_manual_grid_grows_the_way_the_direction_fills_last():
    across = TileLayout.compute(5, 10, 10, manual=(2, 2), direction="x")
    down = TileLayout.compute(5, 10, 10, manual=(2, 2), direction="y")
    assert (across.rows, across.cols) == (3, 2)
    assert (down.rows, down.cols) == (2, 3)


def test_only_the_columns_can_be_asked_for():
    layout = TileLayout.compute(6, 10, 10, manual=(0, 3))
    assert layout.cols == 3
    assert layout.rows == 2


def test_only_the_rows_can_be_asked_for():
    layout = TileLayout.compute(6, 10, 10, manual=(3, 0))
    assert layout.rows == 3
    assert layout.cols == 2


def test_a_manual_grid_of_nothing_falls_back_to_automatic():
    layout = TileLayout.compute(4, 10, 10, manual=(0, 0))
    assert layout.rows * layout.cols >= 4


def test_the_x_direction_fills_a_row_first():
    layout = TileLayout.compute(4, 10, 10, manual=(2, 2), direction="x")
    assert [(layout.placement(i).row, layout.placement(i).col) for i in range(4)] == [
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
    ]


def test_the_y_direction_fills_a_column_first():
    layout = TileLayout.compute(4, 10, 10, manual=(2, 2), direction="y")
    assert [(layout.placement(i).row, layout.placement(i).col) for i in range(4)] == [
        (0, 0),
        (1, 0),
        (0, 1),
        (1, 1),
    ]


def test_a_click_finds_the_tile_it_looks_like_it_found_either_direction():
    """The hit test and the placement have to agree, or clicking a tiled
    frame selects its neighbour."""
    for direction in ("x", "y"):
        layout = TileLayout.compute(4, 10, 10, manual=(2, 2), direction=direction, gap=2)
        for index in range(4):
            placed = layout.placement(index)
            found = layout.tile_at(placed.x + 5, placed.y + 5)
            assert found == index, (direction, index)


def test_the_gap_widens_the_mosaic():
    tight = TileLayout.compute(4, 10, 10, manual=(2, 2), gap=0)
    loose = TileLayout.compute(4, 10, 10, manual=(2, 2), gap=6)
    assert loose.width > tight.width


def test_the_settings_start_where_ds9s_do():
    settings = TileSettings()
    assert settings.manual is False
    assert settings.direction == "x"
    assert (settings.rows, settings.columns) == (2, 2)


# -- the dialogs over them ---------------------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    rows, columns = np.indices((SIZE, SIZE))
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32)).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    yield window
    window.close()


def test_the_menu_has_tile_parameters_and_display_size(main_window):
    labels = [
        action.text().replace("&", "")
        for action in main_window.menu_bar.tile_params_menu.actions()
        if not action.isSeparator()
    ]
    assert labels == ["Grid", "Columns", "Rows", "Tile Parameters..."]

    params = [
        action.text().replace("&", "")
        for action in main_window.menu_bar.frame_params_menu.actions()
        if not action.isSeparator()
    ]
    assert "Display Size..." in params


def test_the_tile_dialog_round_trips_its_settings(main_window):
    from ncrads9.ui.dialogs.tile_dialog import TileParametersDialog

    main_window._tile_settings = TileSettings(manual=True, rows=3, columns=4, direction="y", gap=8)
    dialog = TileParametersDialog(main_window.frame_controller, main_window)
    assert dialog.settings() == main_window._tile_settings
    dialog.close()


def test_the_grids_shape_is_only_asked_for_when_it_is_manual(main_window):
    from ncrads9.ui.dialogs.tile_dialog import TileParametersDialog

    dialog = TileParametersDialog(main_window.frame_controller, main_window)
    assert dialog._layout_group.isEnabled() is False
    dialog._manual.setChecked(True)
    assert dialog._layout_group.isEnabled() is True
    dialog.close()


def test_applying_the_dialog_changes_the_layout(main_window, tmp_path):
    from ncrads9.ui.dialogs.tile_dialog import TileParametersDialog

    path = tmp_path / "second.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32)).writeto(path)
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(path))
    main_window.frame_controller.set_display_mode("tile")

    dialog = TileParametersDialog(main_window.frame_controller, main_window)
    dialog._manual.setChecked(True)
    dialog._rows.setValue(2)
    dialog._columns.setValue(1)
    dialog._gap.setValue(10)
    dialog.buttons["apply"].click()

    layout = main_window._tile_layout
    assert layout is not None
    assert (layout.rows, layout.cols) == (2, 1)
    assert layout.gap == 10
    assert "2x2" not in main_window.status_bar.currentMessage()
    dialog.close()


def test_the_tile_dialog_is_reused(main_window):
    first = main_window.frame_controller.show_tile_dialog()
    assert main_window.frame_controller.show_tile_dialog() is first
    first.close()


def test_the_menu_opens_the_tile_dialog(main_window):
    main_window.menu_bar.action_tile_parameters.trigger()
    assert main_window.frame_controller._tile_dialog is not None
    main_window.frame_controller._tile_dialog.close()


def test_display_size_resizes_the_window_by_what_the_display_is_short(main_window, monkeypatch):
    """DS9 sizes the *display*, not the window around it, so the window is
    grown by the difference."""
    from ncrads9.ui.dialogs import tile_dialog

    viewer = main_window.image_viewer
    wanted = (viewer.width() + 40, viewer.height() + 30)
    monkeypatch.setattr(tile_dialog.DisplaySizeDialog, "choose", lambda self: wanted)

    before = main_window.size()
    assert main_window.frame_controller.show_display_size_dialog() is True
    assert main_window.width() == before.width() + 40
    assert main_window.height() == before.height() + 30


def test_cancelling_display_size_changes_nothing(main_window, monkeypatch):
    from ncrads9.ui.dialogs import tile_dialog

    monkeypatch.setattr(tile_dialog.DisplaySizeDialog, "choose", lambda self: None)
    before = main_window.size()
    assert main_window.frame_controller.show_display_size_dialog() is False
    assert main_window.size() == before


def test_the_display_size_dialog_shows_the_size_it_has(main_window):
    from ncrads9.ui.dialogs.tile_dialog import DisplaySizeDialog

    dialog = DisplaySizeDialog(640, 480, main_window)
    assert dialog.size() == (640, 480)
    dialog.close()


# -- the Python console (M9-34) ------------------------------------------------------


@pytest.fixture
def console(main_window):
    made = main_window.file.show_console()
    yield made
    made.close()


def test_the_file_menu_has_a_python_console_where_ds9_has_a_tcl_one(main_window):
    labels = [
        action.text().replace("&", "")
        for action in main_window.menu_bar.file_menu.actions()
        if not action.isSeparator()
    ]
    assert "Open Python Console" in labels
    assert "Run Python Script..." in labels


def test_the_console_evaluates_an_expression(console):
    assert console.run("1 + 1").strip() == "2"


def test_the_console_prints(console):
    assert console.run("print('hello')").strip() == "hello"


def test_the_console_can_drive_the_application(console, main_window):
    """Which is the whole point of having one."""
    console.run("window.zoom.set_zoom(3)")
    assert main_window.image_viewer.get_zoom() == pytest.approx(3.0)


def test_the_window_and_the_package_are_in_scope(console, main_window):
    assert console.namespace["window"] is main_window
    assert console.run("ncrads9.__name__").strip() == "'ncrads9'"


def test_an_error_is_shown_rather_than_raised(console):
    output = console.run("nosuchname")
    assert "NameError" in output or "not defined" in output
    # And the console still works afterwards.
    assert console.run("2 * 2").strip() == "4"


def test_a_statement_can_span_several_lines(console):
    assert console.run("for i in range(2):") == ""
    assert console.run("    print(i)") == ""
    assert console.run("").split() == ["0", "1"]


def test_the_prompt_says_when_a_statement_is_unfinished(console):
    console.run("if True:")
    assert console.prompt.placeholderText() == "..."
    console.run("    pass")
    console.run("")
    assert console.prompt.placeholderText() == ">>>"


def test_exit_closes_nothing(console):
    """`exit()` in a console should not take the application with it."""
    console.run("exit()")
    assert "Close button" in console.output.toPlainText()


def test_what_was_typed_is_echoed(console):
    console.prompt.setText("1 + 1")
    console.run_prompt()
    text = console.output.toPlainText()
    assert ">>> 1 + 1" in text
    assert "2" in text


def test_the_history_walks_back_and_forth(console):
    for line in ("first", "second"):
        console.prompt.setText(line)
        console.run_prompt()

    console.recall(-1)
    assert console.prompt.text() == "second"
    console.recall(-1)
    assert console.prompt.text() == "first"
    console.recall(1)
    assert console.prompt.text() == "second"
    console.recall(1)
    assert console.prompt.text() == ""


def test_the_history_of_nothing_does_nothing(console):
    console.recall(-1)
    assert console.prompt.text() == ""


def test_an_empty_line_at_the_prompt_does_nothing(console):
    before = console.output.toPlainText()
    console.run_prompt()
    assert console.output.toPlainText() == before


def test_a_script_is_run_and_its_output_shown(console, main_window, tmp_path):
    script = tmp_path / "s.py"
    script.write_text("window.zoom.set_zoom(5)\nprint('done')\n")

    output = console.run_script(str(script))
    assert "done" in output
    assert main_window.image_viewer.get_zoom() == pytest.approx(5.0)
    assert "done" in console.output.toPlainText()


def test_a_script_that_raises_is_reported_not_fatal(console, tmp_path):
    script = tmp_path / "bad.py"
    script.write_text("raise ValueError('no')\n")
    output = console.run_script(str(script))
    assert "ValueError" in output
    assert console.run("1 + 1").strip() == "2"


def test_a_script_that_is_not_there_is_reported(console, tmp_path):
    output = console.run_script(str(tmp_path / "missing.py"))
    assert "Could not read" in output


def test_running_a_script_opens_the_console_to_show_it(main_window, tmp_path):
    """A script that failed silently would be worse than no script."""
    script = tmp_path / "s.py"
    script.write_text("print('from a script')\n")

    assert main_window.file.run_script(str(script)) is True
    console = main_window.file._console
    assert console is not None
    assert "from a script" in console.output.toPlainText()
    console.close()


def test_cancelling_the_script_dialog_runs_nothing(main_window, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    assert main_window.file.run_script() is False


def test_the_console_is_reused(main_window):
    first = main_window.file.show_console()
    assert main_window.file.show_console() is first
    first.close()
