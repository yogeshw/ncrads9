# NCRADS9 - NCRA DS9 Viewer
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

"""The Scale Parameters window against DS9's `ScaleDialog` (scale.tcl).

What matters most is that opening the window and pressing Apply changes
nothing: the fields must open on the limits in force, not on zero, and no
control may quietly reset the transfer function or the limit mode.
"""

import numpy as np
import pytest
from PyQt6.QtCore import Qt

from ncrads9.rendering.scale_algorithms import ScaleAlgorithm
from ncrads9.rendering.scale_limits import LimitMode, LimitScope, MinMaxMethod
from ncrads9.ui.dialogs.scale_dialog import HISTOGRAM_BINS, ScaleDialog, pixel_distribution
from ncrads9.ui.main_window import MainWindow
from ncrads9.utils.preferences import Preferences


@pytest.fixture
def window(qapp, monkeypatch):
    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    made = MainWindow()
    yield made
    for dialog in list(getattr(made, "_open_windows", {}).values()):
        dialog.close()
    made.close()


def _load(window, width=64, height=48, offset=0.0):
    frame = window.frame_manager.current_frame
    image = np.arange(width * height, dtype=np.float32).reshape(height, width) + offset
    frame.image_data = image.copy()
    frame.original_image_data = image.copy()
    window.z1 = None
    window.z2 = None
    window.frame_controller.update_display()
    return frame


def _open(window) -> ScaleDialog:
    window.scale.show_dialog()
    dialog = window.scale.open_dialog()
    assert dialog is not None
    return dialog


# -- seeding ------------------------------------------------------------------


def test_fields_open_on_the_limits_in_force(window):
    _load(window)
    window.scale.set_user_limits(100.0, 2000.0)
    dialog = _open(window)
    assert float(dialog.low_entry.text()) == pytest.approx(100.0)
    assert float(dialog.high_entry.text()) == pytest.approx(2000.0)
    assert dialog.low_entry.isEnabled() and dialog.high_entry.isEnabled()


def test_apply_straight_after_opening_changes_nothing(window):
    _load(window)
    window.scale.set_scale(ScaleAlgorithm.LOG)
    window.scale.set_limit_mode("zscale")
    before = window.scale.current_limits()
    dialog = _open(window)
    dialog.apply()
    assert window.current_scale is ScaleAlgorithm.LOG
    after = window.scale.current_limits()
    assert after == pytest.approx(before, rel=1e-5)


def test_menus_show_current_function_and_mode(window):
    _load(window)
    window.scale.set_scale(ScaleAlgorithm.SQRT)
    window.scale.set_limit_mode("99")
    dialog = _open(window)
    assert dialog.function_actions["sqrt"].isChecked()
    assert dialog.limit_actions["99"].isChecked()
    assert not dialog.function_actions["linear"].isChecked()


def test_dialog_opens_without_an_image(window):
    dialog = _open(window)
    assert dialog.low_entry.text() == ""
    assert dialog.isVisible()


def test_dialog_is_modeless_with_apply_and_close(window):
    dialog = _open(window)
    assert dialog.windowModality() == Qt.WindowModality.NonModal
    assert dialog.apply_button.text() == "Apply"
    assert dialog.close_button.text() == "Close"
    dialog.close_button.click()
    assert not dialog.isVisible()


def test_opening_twice_raises_the_same_window(window):
    first = _open(window)
    second = _open(window)
    assert first is second


# -- refresh while open -------------------------------------------------------


def test_follows_a_limit_change_made_elsewhere(window):
    _load(window)
    dialog = _open(window)
    window.scale.set_user_limits(5.0, 50.0)
    assert float(dialog.low_entry.text()) == pytest.approx(5.0)
    assert float(dialog.high_entry.text()) == pytest.approx(50.0)


def test_follows_new_data(window):
    _load(window)
    dialog = _open(window)
    _load(window, offset=10_000.0)
    assert dialog._distribution is not None
    assert dialog._distribution[2] == pytest.approx(10_000.0)
    assert float(dialog.low_entry.text()) == pytest.approx(window.scale.current_limits()[0], rel=1e-5)


# -- apply of each control ----------------------------------------------------


def test_apply_sets_user_limits(window):
    _load(window)
    dialog = _open(window)
    dialog.low_entry.setText("12")
    dialog.high_entry.setText("345")
    dialog.apply_button.click()
    assert window.scale_limits.mode is LimitMode.USER
    assert (window.z1, window.z2) == (12.0, 345.0)


def test_apply_with_bad_text_restores_the_fields(window):
    _load(window)
    dialog = _open(window)
    before = window.scale.current_limits()
    dialog.low_entry.setText("abc")
    dialog.apply()
    assert window.scale.current_limits() == before
    assert float(dialog.low_entry.text()) == pytest.approx(before[0], rel=1e-5)


@pytest.mark.parametrize(
    ("key", "algorithm"),
    [
        ("log", ScaleAlgorithm.LOG),
        ("histeq", ScaleAlgorithm.HISTOGRAM_EQUALIZATION),
        ("sinh", ScaleAlgorithm.SINH),
    ],
)
def test_scale_menu_sets_the_function(window, key, algorithm):
    _load(window)
    dialog = _open(window)
    dialog.function_actions[key].trigger()
    assert window.current_scale is algorithm
    assert window.menu_bar.scale_function_actions[key].isChecked()


@pytest.mark.parametrize("key", ["zscale", "zmax", "minmax", "95", "99.5"])
def test_limits_menu_sets_the_mode(window, key):
    _load(window)
    dialog = _open(window)
    dialog.limit_actions[key].trigger()
    assert window.scale.mode_key(window.scale_limits) == key


def test_scope_menu(window):
    _load(window)
    dialog = _open(window)
    dialog.scope_actions["global"].trigger()
    assert window.scale_limits.scope is LimitScope.GLOBAL


def test_minmax_menu(window):
    _load(window)
    dialog = _open(window)
    dialog.method_actions["sample"].trigger()
    assert window.scale_limits.method is MinMaxMethod.SAMPLE


def test_datasec_menu(window):
    _load(window)
    dialog = _open(window)
    assert dialog.action_use_datasec.isChecked()
    dialog.action_use_datasec.trigger()
    assert window.scale_limits.use_datasec is False


@pytest.mark.parametrize(
    ("params", "check"),
    [
        ({"clip_algorithm": "ZScale"}, lambda w: w.scale_limits.mode is LimitMode.ZSCALE),
        ({"clip_algorithm": "Percentile", "percentile": 98}, lambda w: w.scale_limits.percent == 98.0),
        ({"limit_mode": "zmax"}, lambda w: w.scale_limits.mode is LimitMode.ZMAX),
        ({"log_exponent": 200}, lambda w: w.scale_limits.log_exponent == 200.0),
        ({"exponent": 400}, lambda w: w.scale_limits.log_exponent == 400.0),
        ({"scope": "global"}, lambda w: w.scale_limits.scope is LimitScope.GLOBAL),
        ({"minmax_method": "datamin"}, lambda w: w.scale_limits.method is MinMaxMethod.DATAMIN),
        ({"use_datasec": False}, lambda w: w.scale_limits.use_datasec is False),
        ({"sample_increment": 7}, lambda w: w.scale_limits.sample_increment == 7),
        ({"scale_function": "asinh"}, lambda w: w.current_scale is ScaleAlgorithm.ASINH),
        ({"scale_function": "Power"}, lambda w: w.current_scale is ScaleAlgorithm.POWER),
    ],
)
def test_apply_dialog_params_honours_every_key(window, params, check):
    _load(window)
    window.scale.apply_dialog_params(params)
    assert check(window)


def test_auto_limits_no_longer_forces_minmax(window):
    _load(window)
    window.scale.set_limit_mode("zscale")
    window.scale.apply_dialog_params({"scale_function": "Log", "auto_limits": True})
    assert window.scale_limits.mode is LimitMode.ZSCALE
    assert window.current_scale is ScaleAlgorithm.LOG


def test_limits_alone_keep_the_function(window):
    _load(window)
    window.scale.set_scale(ScaleAlgorithm.SQUARED)
    window.scale.apply_dialog_params({"limit_mode": "user", "low": 9.0, "high": 3.0})
    assert window.current_scale is ScaleAlgorithm.SQUARED
    assert (window.z1, window.z2) == (3.0, 9.0)


def test_unsupported_values_change_nothing(window):
    _load(window)
    before = window.scale_limits
    window.scale.apply_dialog_params({"clip_algorithm": "Sigma Clip"})
    window.scale.apply_dialog_params({"scope": "nowhere"})
    window.scale.apply_dialog_params({"log_exponent": 0.5})
    assert window.scale_limits == before


# -- the histogram and its limit lines ----------------------------------------


def test_histogram_is_drawn_with_two_lines(window):
    _load(window)
    dialog = _open(window)
    centres, counts, dmin, dmax = dialog._distribution
    assert len(centres) == HISTOGRAM_BINS
    assert counts.sum() == 64 * 48
    assert (dmin, dmax) == (0.0, 64 * 48 - 1.0)
    assert dialog._low_line.get_color() == "red"
    assert dialog._high_line.get_color() == "green"


def test_dragging_a_line_moves_the_field_then_applies_on_release(window):
    _load(window)
    dialog = _open(window)
    dialog.drag_limit("low", 500.0)
    assert float(dialog.low_entry.text()) == pytest.approx(500.0)
    assert window.scale_limits.mode is not LimitMode.USER  # not until release
    dialog.drag_limit("high", 1500.0)
    dialog.release_limit()
    assert window.scale_limits.mode is LimitMode.USER
    assert (window.z1, window.z2) == (500.0, 1500.0)
    assert list(dialog._low_line.get_xdata()) == [500.0, 500.0]


def test_a_line_cannot_pass_the_other(window):
    _load(window)
    dialog = _open(window)
    high = dialog.high
    dialog.drag_limit("low", high + 1000.0)
    assert dialog.low == high
    dialog.drag_limit("high", -1e6)
    assert dialog.high == dialog.low


def test_press_near_a_line_grabs_it(window):
    _load(window)
    dialog = _open(window)
    dialog.canvas.draw()
    x, _y = dialog.axes.transData.transform((dialog.low, 1.0))

    class Event:
        button = 1
        inaxes = dialog.axes

    press = Event()
    press.x = x + 2
    dialog._on_press(press)
    assert dialog._dragging == "low"
    move = Event()
    move.xdata = 300.0
    dialog._on_motion(move)
    dialog._on_release(move)
    assert dialog._dragging is None
    assert window.z1 == pytest.approx(300.0)


def test_graph_menu_axes(window):
    _load(window)
    dialog = _open(window)
    assert dialog.axes.get_yscale() == "log"
    dialog.y_axis_actions["linear"].trigger()
    assert dialog.axes.get_yscale() == "linear"
    window.scale.set_user_limits(1000.0, 2000.0)
    dialog.x_axis_actions["current"].trigger()
    assert dialog.axes.get_xlim() == pytest.approx((900.0, 2100.0))
    dialog.x_axis_actions["full"].trigger()
    assert dialog.axes.get_xlim()[0] < 0.0


def test_pixel_distribution_handles_empty_and_flat_data():
    assert pixel_distribution(None) is None
    assert pixel_distribution(np.full((4, 4), np.nan)) is None
    centres, counts, low, high = pixel_distribution(np.ones((4, 4)))
    assert counts.sum() == 16 and high > low


# -- menus --------------------------------------------------------------------


def _titles(dialog):
    bar = dialog.layout().menuBar()
    return [action.text().replace("&", "") for action in bar.actions()]


def test_menus_in_ds9s_order(window):
    dialog = _open(window)
    assert _titles(dialog) == [
        "File",
        "Edit",
        "Scale",
        "Limits",
        "Scope",
        "Min Max",
        "Parameters",
        "Graph",
    ]


def test_menus_share_the_main_windows_actions(window):
    dialog = _open(window)
    menu = window.menu_bar
    assert set(dialog.scale_menu.actions()) >= set(menu.scale_function_actions.values())
    assert set(dialog.limits_menu.actions()) >= set(menu.scale_limit_actions.values())
    assert menu.action_scale_user_limits in dialog.limits_menu.actions()
    assert set(dialog.scope_menu.actions()) == set(menu.scale_scope_actions.values())
    assert set(dialog.minmax_menu.actions()) >= set(menu.minmax_method_actions.values())
    assert menu.action_sample_parameters in dialog.minmax_menu.actions()
    assert menu.action_use_datasec in dialog.parameters_menu.actions()
    assert menu.action_zscale_parameters in dialog.parameters_menu.actions()
    assert menu.log_exponent_menu.menuAction() in dialog.scale_menu.actions()


def test_limits_menu_order(window):
    dialog = _open(window)
    keys = {action: key for key, action in dialog.limit_actions.items()}
    order = [keys[a] for a in dialog.limits_menu.actions() if a in keys]
    assert order == ["minmax", "99.5", "99", "98", "97", "96", "95", "92.5", "90", "zscale", "zmax", "user"]


def test_file_and_edit_menus():
    dialog = ScaleDialog()
    bar = dialog.layout().menuBar()
    menus = {a.text().replace("&", ""): a.menu() for a in bar.actions()}
    assert [a.text() for a in menus["File"].actions() if not a.isSeparator()] == ["Apply", "Close"]
    assert [a.text() for a in menus["Edit"].actions()] == ["Cut", "Copy", "Paste"]
    dialog.close()


def test_standalone_dialog_reports_menu_choices(qapp):
    dialog = ScaleDialog()
    seen = []
    dialog.scale_changed.connect(seen.append)
    dialog.function_actions["log"].trigger()
    dialog.limit_actions["zscale"].trigger()
    dialog.scope_actions["global"].trigger()
    dialog.method_actions["irafminmax"].trigger()
    dialog.action_use_datasec.trigger()
    dialog.set_state(np.arange(100.0).reshape(10, 10), 10.0, 90.0)
    dialog.apply()
    assert seen == [
        {"scale_function": "log"},
        {"limit_mode": "zscale"},
        {"scope": "global"},
        {"minmax_method": "irafminmax"},
        {"use_datasec": False},
        {"limit_mode": "user", "low": 10.0, "high": 90.0},
    ]
    dialog.close()
