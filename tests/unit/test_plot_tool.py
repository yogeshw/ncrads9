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

"""DS9's Plot Tool (M7-15 ... M7-20)."""

from __future__ import annotations

import pytest

from ncrads9.analysis.plot import (
    Axis,
    AxisFormat,
    DataFormat,
    Dataset,
    LegendPosition,
    PlotDataError,
    PlotState,
    PlotStyle,
    ZoomStack,
    parse_data,
    parse_stdin,
)

# -- reading data -------------------------------------------------------------


@pytest.mark.parametrize(
    "data_format,columns,x_error,y_error",
    [
        (DataFormat.XY, 2, False, False),
        (DataFormat.XYEX, 3, True, False),
        (DataFormat.XYEY, 3, False, True),
        (DataFormat.XYEXEY, 4, True, True),
    ],
)
def test_ds9s_four_data_formats(data_format, columns, x_error, y_error):
    assert data_format.columns == columns
    assert data_format.has_x_error is x_error
    assert data_format.has_y_error is y_error


def test_two_columns_read_as_points():
    dataset = parse_data("1 2\n3 4\n")
    assert (dataset.x, dataset.y) == ([1.0, 3.0], [2.0, 4.0])


def test_error_columns_are_read():
    dataset = parse_data("1 2 0.1 0.2\n", DataFormat.XYEXEY)
    assert (dataset.x_error, dataset.y_error) == ([0.1], [0.2])


def test_a_negative_error_is_taken_as_a_magnitude():
    """An error bar of -0.1 is 0.1 long; drawing it downwards is meaningless."""
    assert parse_data("1 2 -0.1\n", DataFormat.XYEY).y_error == [0.1]


def test_commas_separate_as_well_as_spaces():
    assert parse_data("1,2\n3,4\n").x == [1.0, 3.0]


def test_comments_and_blank_lines_are_skipped():
    assert len(parse_data("# a header\n\n1 2\n3 4\n")) == 2


def test_a_short_line_is_skipped_not_fatal():
    """A task that prints a stray line should still plot the rest."""
    assert len(parse_data("1 2\nonly-one\n3 4\n")) == 2


def test_a_non_numeric_line_is_skipped():
    assert len(parse_data("1 2\nfoo bar\n3 4\n")) == 2


def test_a_nan_point_is_dropped():
    assert len(parse_data("1 2\nnan 3\n4 5\n")) == 2


def test_output_with_no_points_is_an_error():
    with pytest.raises(PlotDataError, match="no plottable points"):
        parse_data("nothing here\n")


# -- the $plot(stdin) header ------------------------------------------------------


def test_the_header_gives_the_title_labels_and_format():
    parsed = parse_stdin("Counts {Radius (pixels)} {Counts} xyey\n1 2 0.1\n2 3 0.2\n")
    assert parsed.title == "Counts"
    assert parsed.x_label == "Radius (pixels)"
    assert parsed.y_label == "Counts"
    assert parsed.dataset.y_error == [0.1, 0.2]


def test_a_multi_word_title_survives():
    """The format is the last word and the labels the two before it, so
    everything earlier is the title -- read left to right it would break."""
    parsed = parse_stdin("A long title here {X} {Y} xy\n1 2\n")
    assert parsed.title == "A long title here"


def test_a_braced_label_is_one_word():
    parsed = parse_stdin("T {X Axis} {Y Axis} xy\n1 2\n")
    assert (parsed.x_label, parsed.y_label) == ("X Axis", "Y Axis")


def test_an_error_marker_means_there_is_no_plot():
    """One analysis task, one pipe, either a plot or a problem down it."""
    parsed = parse_stdin("$ERROR the fit did not converge\n")
    assert parsed.failed is True
    assert parsed.dataset is None
    assert "did not converge" in parsed.message


def test_the_older_error_marker_too():
    assert parse_stdin("ERROR: no such file\n").failed is True


def test_begintext_is_shown_beside_the_plot():
    parsed = parse_stdin("$BEGINTEXT\nfit chi2 = 1.02\n$ENDTEXT\nT {X} {Y} xy\n1 2\n3 4\n")
    assert parsed.message == "fit chi2 = 1.02"
    assert len(parsed.dataset) == 2


def test_begintext_with_no_end_is_all_prose():
    parsed = parse_stdin("$BEGINTEXT\njust a note\n")
    assert parsed.dataset is None
    assert "just a note" in parsed.message


def test_a_missing_header_is_an_error():
    with pytest.raises(PlotDataError, match="expected a header"):
        parse_stdin("1 2\n3 4\n")


def test_an_unknown_format_in_the_header_is_an_error():
    with pytest.raises(PlotDataError, match="unknown plot data format"):
        parse_stdin("T {X} {Y} xyzzy\n1 2\n")


# -- axes -------------------------------------------------------------------------


def test_an_axis_starts_automatic():
    axis = Axis()
    assert axis.automatic is True
    assert axis.range is None


def test_setting_a_range_stops_it_being_automatic():
    axis = Axis()
    axis.set_range(1, 10)
    assert axis.range == (1.0, 10.0)


def test_a_reversed_range_is_swapped():
    """Dragging a zoom box right to left means the same rectangle."""
    axis = Axis()
    axis.set_range(10, 1)
    assert axis.range == (1.0, 10.0)


def test_clearing_a_range_goes_back_to_the_data():
    axis = Axis(minimum=1, maximum=2)
    axis.clear_range()
    assert axis.automatic is True


def test_an_axis_round_trips_through_plain_data():
    axis = Axis(
        label="R", log=True, flip=True, grid=False, minimum=1, maximum=9, number_format=AxisFormat.EXPONENTIAL
    )
    assert Axis.from_dict(axis.to_dict()) == axis


# -- plot state ---------------------------------------------------------------------


def test_a_second_dataset_gets_a_different_colour():
    """Two curves in the same colour are one curve to a reader."""
    state = PlotState()
    first = state.add(Dataset(x=[1], y=[1]))
    second = state.add(Dataset(x=[1], y=[2]))
    assert first.color != second.color


def test_no_dataset_is_ever_handed_white():
    """The background is white; an invisible curve reads as a missing one."""
    state = PlotState()
    for _ in range(10):
        state.add(Dataset(x=[1], y=[1]))
    assert "white" not in [dataset.color for dataset in state.datasets]


def test_datasets_get_distinct_names():
    state = PlotState()
    state.add(Dataset(x=[1], y=[1]))
    state.add(Dataset(x=[1], y=[1]))
    assert state.datasets[0].name != state.datasets[1].name


def test_a_hidden_dataset_is_not_visible():
    state = PlotState()
    state.add(Dataset(x=[1], y=[1], show=False))
    assert state.visible == []


def test_an_empty_dataset_is_not_visible():
    state = PlotState()
    state.add(Dataset())
    assert state.visible == []


def test_bounds_span_every_visible_dataset():
    state = PlotState()
    state.add(Dataset(x=[1, 2], y=[5, 6]))
    state.add(Dataset(x=[10], y=[0]))
    assert state.bounds() == (1.0, 10.0, 0.0, 6.0)


def test_bounds_of_nothing_is_none():
    assert PlotState().bounds() is None


def test_duplicating_a_dataset_copies_its_points():
    """A copy sharing its lists would move when the original was edited."""
    state = PlotState()
    state.add(Dataset(x=[1, 2], y=[3, 4]))
    copy = state.duplicate(0)
    copy.x.append(9)
    assert state.datasets[0].x == [1, 2]


def test_removing_a_dataset():
    state = PlotState()
    state.add(Dataset(x=[1], y=[1]))
    state.remove(0)
    assert state.datasets == []


def test_a_dataset_writes_back_out_as_columns():
    dataset = Dataset(x=[1, 2], y=[3, 4], y_error=[0.1, 0.2])
    assert dataset.to_text() == "1 3 0.1\n2 4 0.2"
    assert dataset.data_format is DataFormat.XYEY


def test_list_data_names_each_dataset():
    state = PlotState()
    state.load_data("1 2\n")
    assert "Data 1" in state.list_data()


# -- saving and restoring (M7-19) ------------------------------------------------------


def test_a_plot_round_trips_through_a_file(tmp_path):
    state = PlotState(title="Radial", style=PlotStyle.BAR, legend_position=LegendPosition.TOP)
    state.x_axis = Axis(label="R", log=True)
    state.add(Dataset(name="ring", x=[1, 2], y=[3, 4], y_error=[0.1, 0.2], color="red", width=3))

    path = tmp_path / "saved.plot"
    state.save(path)
    restored = PlotState.load(path)

    assert restored.title == "Radial"
    assert restored.style is PlotStyle.BAR
    assert restored.legend_position is LegendPosition.TOP
    assert restored.x_axis.label == "R" and restored.x_axis.log is True
    assert restored.datasets[0].name == "ring"
    assert restored.datasets[0].y_error == [0.1, 0.2]
    assert restored.datasets[0].color == "red"


def test_restoring_something_that_is_not_a_plot(tmp_path):
    path = tmp_path / "not.plot"
    path.write_text('{"hello": 1}')
    with pytest.raises(ValueError, match="not a saved plot"):
        PlotState.load(path)


# -- the zoom stack (M7-18) --------------------------------------------------------------


def test_a_fresh_stack_is_empty():
    stack = ZoomStack()
    assert not stack
    assert stack.pop() is None


def test_pushing_and_popping():
    stack = ZoomStack()
    stack.push((0, 1, 0, 1))
    stack.push((0, 2, 0, 2))
    assert stack.depth == 2
    assert stack.pop() == (0, 2, 0, 2)
    assert stack.pop() == (0, 1, 0, 1)
    assert stack.pop() is None


def test_the_same_view_is_not_pushed_twice():
    """A click that changed nothing should not cost a zoom-out."""
    stack = ZoomStack()
    stack.push((0, 1, 0, 1))
    stack.push((0, 1, 0, 1))
    assert stack.depth == 1


def test_reset_forgets_the_way_in():
    stack = ZoomStack()
    stack.push((0, 1, 0, 1))
    stack.reset()
    assert stack.depth == 0


def test_the_stack_has_a_depth_limit():
    from ncrads9.analysis.plot.zoom_stack import MAX_DEPTH

    stack = ZoomStack()
    for index in range(MAX_DEPTH + 20):
        stack.push((index, index + 1, 0, 1))
    assert stack.depth == MAX_DEPTH


# -- the window -------------------------------------------------------------------------


@pytest.fixture
def window(qapp):
    from ncrads9.ui.dialogs.plot_window import PlotWindow

    plot = PlotWindow()
    plot.add_dataset(parse_data("1 2\n2 4\n3 9\n"))
    yield plot
    plot.close()


def test_the_window_has_ds9s_four_menus(window):
    labels = [action.text() for action in window.layout().menuBar().actions()]
    assert labels == ["&File", "&Edit", "&Graph", "&Data"]


@pytest.mark.parametrize("style", list(PlotStyle))
def test_every_style_draws(window, style):
    window.actions_by_name[f"style_{style.value}"].trigger()
    assert window.state.style is style
    assert window.figure.axes


def test_a_bar_plot_gets_a_sensible_bar_width():
    """Matplotlib's default of 0.8 makes hairlines of widely spaced data."""
    from ncrads9.ui.dialogs.plot_window import _bar_width

    assert _bar_width([0, 100, 200]) == pytest.approx(80.0)
    assert _bar_width([5]) > 0


@pytest.mark.parametrize("flag", ["log", "flip", "grid"])
def test_the_axis_flags_reach_the_axis(window, flag):
    action = window.actions_by_name[f"x_{flag}"]
    action.setChecked(not getattr(window.state.x_axis, flag))
    action.trigger()
    assert getattr(window.state.x_axis, flag) is action.isChecked()


def test_a_log_axis_with_non_positive_data_falls_back(window):
    """Matplotlib would draw an empty plot and say nothing."""
    window.state.datasets[0].y = [0.0, -1.0, 5.0]
    window.state.y_axis.log = True
    window.draw()
    assert window.figure.axes[0].get_yscale() == "linear"


def test_a_log_axis_with_positive_data_is_log(window):
    window.state.y_axis.log = True
    window.draw()
    assert window.figure.axes[0].get_yscale() == "log"


def test_zooming_pushes_and_zooming_out_pops(window):
    window.zoom_to(1, 2, 2, 4)
    assert window.state.x_axis.range == (1.0, 2.0)
    assert window.zoom_stack.depth == 1
    window.zoom_out()
    assert window.state.x_axis.range is None


def test_zooming_out_past_the_bottom_fits_the_data(window):
    window.state.x_axis.set_range(1, 2)
    window.zoom_out()
    assert window.state.x_axis.automatic is True


def test_a_degenerate_zoom_box_is_ignored(window):
    window.zoom_to(1, 1, 2, 2)
    assert window.zoom_stack.depth == 0


def test_the_legend_can_be_moved_and_hidden(window):
    window.set_legend_position(LegendPosition.BOTTOM)
    assert window.state.legend_position is LegendPosition.BOTTOM
    # `trigger` on a checkable action toggles it, so one call is the click.
    window.actions_by_name["legend_show"].trigger()
    assert window.state.show_legend is False


def test_the_data_menu_acts_on_the_selected_dataset(window):
    window.add_dataset(parse_data("1 5\n2 6\n"))
    window.select_dataset(1)
    window.set_dataset_property("color", "magenta")
    assert window.state.datasets[1].color == "magenta"
    assert window.state.datasets[0].color != "magenta"


def test_hiding_a_dataset_takes_it_off_the_plot(window):
    window.set_dataset_shown(False)
    assert window.state.visible == []


def test_deleting_the_last_dataset_leaves_the_menu_usable(window):
    window.delete_dataset()
    assert window.state.datasets == []
    # Rebuilding the Data menu with nothing in it must not raise.
    window._build_data_menu()


def test_duplicating_from_the_menu(window):
    window.actions_by_name["data_duplicate"].trigger()
    assert len(window.state.datasets) == 2


def test_an_empty_window_still_draws(qapp):
    from ncrads9.ui.dialogs.plot_window import PlotWindow

    plot = PlotWindow()
    plot.draw()
    assert plot.figure.axes
    plot.close()


def test_titles_reach_the_plot(window):
    from ncrads9.ui.dialogs.plot_window import PlotTitlesDialog

    dialog = PlotTitlesDialog(window.state)
    dialog._title.setText("Counts")
    dialog._x_label.setText("Radius")
    dialog.apply()
    assert (window.state.title, window.state.x_axis.label) == ("Counts", "Radius")


def test_the_range_dialog_sets_both_axes(window):
    from ncrads9.ui.dialogs.plot_window import AxisRangeDialog

    dialog = AxisRangeDialog(window.state.x_axis, window.state.y_axis)
    dialog._boxes["x minimum"].setValue(2.0)
    dialog._boxes["x maximum"].setValue(8.0)
    dialog.apply()
    assert window.state.x_axis.range == (2.0, 8.0)


def test_the_range_dialogs_reset_means_automatic(window):
    from ncrads9.ui.dialogs.plot_window import AxisRangeDialog

    window.state.x_axis.set_range(1, 2)
    dialog = AxisRangeDialog(window.state.x_axis, window.state.y_axis)
    dialog._reset()
    dialog.apply()
    assert window.state.x_axis.automatic is True


def test_exporting_writes_a_picture(window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    path = tmp_path / "plot.png"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))
    window.actions_by_name["export"].trigger()
    assert path.exists() and path.stat().st_size > 0


def test_backup_and_restore_through_the_menu(window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    path = tmp_path / "saved.plot"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))
    window.state.title = "Kept"
    window.actions_by_name["backup"].trigger()

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
    window.state.title = "Lost"
    window.actions_by_name["restore"].trigger()
    assert window.state.title == "Kept"


def test_loading_data_from_a_file(window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog, QInputDialog

    path = tmp_path / "more.dat"
    path.write_text("5 6\n7 8\n")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("xy", True)))
    window.actions_by_name["load_data"].trigger()
    assert len(window.state.datasets) == 2
    assert window.state.datasets[1].name == "more"


def test_saving_data_writes_columns(window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    path = tmp_path / "out.dat"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))
    window.actions_by_name["save_data"].trigger()
    assert path.read_text().strip().splitlines()[0] == "1 2"


# -- reaching it from the menu (M7-20) ----------------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    created = MainWindow()
    created._rebuild_image_viewer(False)
    yield created
    for plot in list(created.analysis._plots):
        plot.close()
    created.close()


@pytest.mark.parametrize(
    "action,style",
    [("action_plot_tool_line", PlotStyle.LINE), ("action_plot_tool_bar", PlotStyle.BAR)],
)
def test_the_plot_tool_menu_entries_open_a_window(main_window, action, style):
    """Both were dead entries."""
    getattr(main_window.menu_bar, action).trigger()
    assert len(main_window.analysis._plots) == 1
    assert next(iter(main_window.analysis._plots)).state.style is style


def test_closing_a_plot_window_forgets_it(main_window):
    main_window.menu_bar.action_plot_tool_line.trigger()
    next(iter(main_window.analysis._plots)).close()
    assert main_window.analysis._plots == []


def test_each_controller_keeps_its_own_plot_windows(main_window):
    """A set on the class would outlive the window that opened them."""
    from ncrads9.ui.controllers.analysis import AnalysisController

    other = AnalysisController(main_window)
    main_window.menu_bar.action_plot_tool_line.trigger()
    assert other._plots == []
