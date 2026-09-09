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


"""Clip limits and transfer functions: DS9's Scale menu.

The transfer functions are checked against the formulas in DS9's
`tksao/frame/colorscale.C` rather than against what looks reasonable, since
matching them is what makes the two applications render an image alike.
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.rendering.scale_algorithms import (
    ASINH_DIVISOR,
    ASINH_GAIN,
    DEFAULT_LOG_EXPONENT,
    SINH_DIVISOR,
    SINH_GAIN,
    ScaleAlgorithm,
    apply_scale,
)
from ncrads9.rendering.scale_limits import (
    FALLBACK_LIMITS,
    PERCENT_PRESETS,
    LimitMode,
    LimitScope,
    MinMaxMethod,
    ScaleLimits,
    compute_limits,
    datasec_slice,
    percentile_limits,
)

#: A ramp from 0 to 1, the input DS9's own scale tables are built from.
RAMP = np.linspace(0.0, 1.0, 11, dtype=np.float32)


def _ds9(name: str, x: float, exponent: float = DEFAULT_LOG_EXPONENT) -> float:
    """DS9's transfer functions, transcribed from tksao/frame/colorscale.C."""
    return {
        "linear": x,
        "log": math.log10(exponent * x + 1.0) / math.log10(exponent),
        "power": (exponent**x - 1.0) / exponent,
        "sqrt": math.sqrt(x),
        "squared": x * x,
        "asinh": math.asinh(ASINH_GAIN * x) / ASINH_DIVISOR,
        "sinh": math.sinh(SINH_GAIN * x) / SINH_DIVISOR,
    }[name]


# -- transfer functions ------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "algorithm"),
    [
        ("linear", ScaleAlgorithm.LINEAR),
        ("log", ScaleAlgorithm.LOG),
        ("power", ScaleAlgorithm.POWER),
        ("sqrt", ScaleAlgorithm.SQRT),
        ("squared", ScaleAlgorithm.SQUARED),
        ("asinh", ScaleAlgorithm.ASINH),
        ("sinh", ScaleAlgorithm.SINH),
    ],
)
def test_transfer_functions_match_ds9(name, algorithm):
    got = apply_scale(RAMP, algorithm, vmin=0.0, vmax=1.0)
    expected = [min(max(_ds9(name, float(x)), 0.0), 1.0) for x in RAMP]
    assert got.tolist() == pytest.approx(expected, abs=1e-6)


def test_power_is_not_squared():
    """These were the same function before M5, and DS9 has both."""
    power = apply_scale(RAMP, ScaleAlgorithm.POWER, vmin=0.0, vmax=1.0)
    squared = apply_scale(RAMP, ScaleAlgorithm.SQUARED, vmin=0.0, vmax=1.0)
    assert not np.allclose(power, squared)
    # DS9's power is far more aggressive: at the half-way point it is near
    # zero where squared is a quarter.
    assert power[5] < 0.05
    assert squared[5] == pytest.approx(0.25)


def test_the_log_exponent_changes_the_log_curve():
    gentle = apply_scale(RAMP, ScaleAlgorithm.LOG, vmin=0.0, vmax=1.0, exponent=10.0)
    steep = apply_scale(RAMP, ScaleAlgorithm.LOG, vmin=0.0, vmax=1.0, exponent=10000.0)
    assert steep[1] > gentle[1]


def test_an_exponent_of_one_is_refused_quietly():
    """`log10(1)` is zero, so the formula would divide by it."""
    result = apply_scale(RAMP, ScaleAlgorithm.LOG, vmin=0.0, vmax=1.0, exponent=1.0)
    assert np.isfinite(result).all()


@pytest.mark.parametrize(
    "algorithm",
    [
        ScaleAlgorithm.LINEAR,
        ScaleAlgorithm.LOG,
        ScaleAlgorithm.POWER,
        ScaleAlgorithm.SQRT,
        ScaleAlgorithm.SQUARED,
        ScaleAlgorithm.ASINH,
        ScaleAlgorithm.SINH,
        ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
    ],
)
def test_every_function_stays_inside_the_unit_range(algorithm):
    data = np.array([-100.0, 0.0, 0.5, 1.0, 100.0], dtype=np.float32)
    result = apply_scale(data, algorithm, vmin=0.0, vmax=1.0)
    assert result.min() >= 0.0
    assert result.max() <= 1.0


def test_every_menu_entry_has_an_algorithm():
    from ncrads9.ui.controllers.scale import SCALE_ACTIONS
    from ncrads9.ui.menu_bar import SCALE_FUNCTIONS

    assert {name for name, _label in SCALE_FUNCTIONS} == set(SCALE_ACTIONS)


# -- limit modes -------------------------------------------------------------


@pytest.fixture
def data():
    """Normal noise with one hot pixel, so clipping modes visibly differ."""
    rng = np.random.default_rng(0)
    values = rng.normal(100.0, 10.0, (200, 200)).astype(np.float32)
    values[0, 0] = 1.0e6
    return values


def test_minmax_takes_the_extremes(data):
    low, high = compute_limits(data, ScaleLimits())
    assert high == pytest.approx(1.0e6)
    assert low == pytest.approx(float(np.min(data)))


def test_percentile_presets_exclude_the_hot_pixel(data):
    for percent in PERCENT_PRESETS:
        low, high = compute_limits(data, ScaleLimits().with_mode(LimitMode.PERCENT, percent))
        assert high < 200.0, percent
        assert low > 0.0, percent


def test_a_tighter_preset_is_a_narrower_range(data):
    ranges = [
        compute_limits(data, ScaleLimits().with_mode(LimitMode.PERCENT, percent))
        for percent in PERCENT_PRESETS
    ]
    widths = [high - low for low, high in ranges]
    # PERCENT_PRESETS runs from 99.5% down to 90%, so the widths shrink.
    assert widths == sorted(widths, reverse=True)


def test_the_presets_are_ds9s():
    assert PERCENT_PRESETS == (99.5, 99.0, 98.0, 97.0, 96.0, 95.0, 92.5, 90.0)


def test_an_unknown_preset_is_refused():
    with pytest.raises(ValueError, match="not one of DS9's presets"):
        ScaleLimits().with_mode(LimitMode.PERCENT, 42.0)


def test_percentile_limits_are_symmetric():
    values = np.arange(0.0, 101.0, dtype=np.float32)
    low, high = percentile_limits(values, 90.0)
    assert low == pytest.approx(5.0)
    assert high == pytest.approx(95.0)


def test_zscale_ignores_the_hot_pixel(data):
    _low, high = compute_limits(data, ScaleLimits().with_mode(LimitMode.ZSCALE))
    assert high < 1000.0


def test_zmax_keeps_zscales_low_and_the_datas_high(data):
    zscale = compute_limits(data, ScaleLimits().with_mode(LimitMode.ZSCALE))
    zmax = compute_limits(data, ScaleLimits().with_mode(LimitMode.ZMAX))
    assert zmax[0] == pytest.approx(zscale[0])
    assert zmax[1] == pytest.approx(1.0e6)


def test_user_limits_are_taken_verbatim(data):
    settings = replace(ScaleLimits(), mode=LimitMode.USER, user_low=3.0, user_high=7.0)
    assert compute_limits(data, settings) == (3.0, 7.0)


def test_user_limits_are_ordered(data):
    settings = replace(ScaleLimits(), mode=LimitMode.USER, user_low=7.0, user_high=3.0)
    assert compute_limits(data, settings) == (3.0, 7.0)


def test_the_contrast_parameter_changes_zscale(data):
    tight = compute_limits(data, replace(ScaleLimits(), mode=LimitMode.ZSCALE, contrast=1.0))
    loose = compute_limits(data, replace(ScaleLimits(), mode=LimitMode.ZSCALE, contrast=0.05))
    assert (loose[1] - loose[0]) > (tight[1] - tight[0])


# -- min/max methods ---------------------------------------------------------


def test_sampling_looks_at_fewer_pixels(data):
    """The hot pixel is at index 0, so sampling still sees it; a sparse
    sample of the rest gives a higher minimum than a full scan."""
    scan = compute_limits(data, replace(ScaleLimits(), method=MinMaxMethod.SCAN))
    sample = compute_limits(data, replace(ScaleLimits(), method=MinMaxMethod.SAMPLE))
    assert sample[0] > scan[0]


def test_the_sample_increment_matters(data):
    coarse = compute_limits(data, replace(ScaleLimits(), method=MinMaxMethod.SAMPLE, sample_increment=997))
    fine = compute_limits(data, replace(ScaleLimits(), method=MinMaxMethod.SAMPLE, sample_increment=2))
    assert coarse[0] > fine[0]


def test_datamin_reads_the_header(data):
    header = fits.Header({"DATAMIN": -3.0, "DATAMAX": 42.0})
    settings = replace(ScaleLimits(), method=MinMaxMethod.DATAMIN)
    assert compute_limits(data, settings, header=header) == (-3.0, 42.0)


def test_iraf_minmax_reads_its_own_cards(data):
    header = fits.Header({"IRAF-MIN": 1.0, "IRAF-MAX": 9.0})
    settings = replace(ScaleLimits(), method=MinMaxMethod.IRAF)
    assert compute_limits(data, settings, header=header) == (1.0, 9.0)


def test_a_header_method_falls_back_to_a_scan(data):
    """A header without the cards must not leave the image unscaled."""
    settings = replace(ScaleLimits(), method=MinMaxMethod.DATAMIN)
    low, high = compute_limits(data, settings, header=fits.Header())
    assert high == pytest.approx(1.0e6)


def test_the_header_methods_only_apply_to_minmax(data):
    """A percentile preset measures pixels whatever the method says."""
    header = fits.Header({"DATAMIN": -3.0, "DATAMAX": 42.0})
    settings = ScaleLimits().with_mode(LimitMode.PERCENT, 90.0)
    settings = replace(settings, method=MinMaxMethod.DATAMIN)
    low, high = compute_limits(data, settings, header=header)
    assert (low, high) != (-3.0, 42.0)


# -- DATASEC -----------------------------------------------------------------


def test_datasec_restricts_the_measurement(data):
    header = fits.Header({"DATASEC": "[11:20,11:20]"})
    inside = compute_limits(data, ScaleLimits(), header=header)
    whole = compute_limits(data, replace(ScaleLimits(), use_datasec=False), header=header)
    assert inside[1] < whole[1]


def test_datasec_is_read_as_one_based_inclusive():
    rows, columns = datasec_slice(fits.Header({"DATASEC": "[11:20,3:8]"}))
    assert (columns.start, columns.stop) == (10, 20)
    assert (rows.start, rows.stop) == (2, 8)


@pytest.mark.parametrize("value", [None, "", "nonsense", "[1:2]"])
def test_an_unusable_datasec_is_ignored(value):
    assert datasec_slice(fits.Header({"DATASEC": value}) if value is not None else None) is None


def test_datasec_is_ignored_when_it_selects_nothing(data):
    """A section entirely outside the array must not blank the limits."""
    header = fits.Header({"DATASEC": "[9000:9100,9000:9100]"})
    low, high = compute_limits(data, ScaleLimits(), header=header)
    assert high == pytest.approx(1.0e6)


# -- scope -------------------------------------------------------------------


@pytest.fixture
def cube():
    """A cube whose slices brighten, so scope visibly matters."""
    return np.stack([np.full((10, 10), 10.0 * (index + 1), np.float32) for index in range(4)])


def test_local_scope_measures_the_slice(cube):
    settings = replace(ScaleLimits(), scope=LimitScope.LOCAL)
    assert compute_limits(cube[0], settings, global_data=cube) == (10.0, 11.0)


def test_global_scope_measures_the_whole_extension(cube):
    settings = replace(ScaleLimits(), scope=LimitScope.GLOBAL)
    assert compute_limits(cube[0], settings, global_data=cube) == (10.0, 40.0)


def test_global_scope_without_a_cube_uses_the_slice(cube):
    settings = replace(ScaleLimits(), scope=LimitScope.GLOBAL)
    assert compute_limits(cube[0], settings) == (10.0, 11.0)


# -- degenerate inputs -------------------------------------------------------


def test_a_flat_image_gets_a_widened_range():
    """`low == high` would make every consumer divide by zero."""
    low, high = compute_limits(np.full((4, 4), 7.0, np.float32), ScaleLimits())
    assert low == 7.0
    assert high > low


def test_an_all_nan_image_falls_back():
    assert compute_limits(np.full((4, 4), np.nan, np.float32), ScaleLimits()) == FALLBACK_LIMITS


def test_no_data_falls_back():
    assert compute_limits(None, ScaleLimits()) == FALLBACK_LIMITS
    assert compute_limits(np.array([], dtype=np.float32), ScaleLimits()) == FALLBACK_LIMITS


def test_limits_always_come_back_ordered(data):
    for mode in LimitMode:
        settings = (
            ScaleLimits().with_mode(LimitMode.PERCENT, 95.0)
            if mode is LimitMode.PERCENT
            else replace(ScaleLimits(), mode=mode)
        )
        low, high = compute_limits(data, settings)
        assert low <= high, mode


def test_describe_names_the_mode():
    assert "minmax" in ScaleLimits().describe()
    assert ScaleLimits().with_mode(LimitMode.PERCENT, 95.0).describe() == "95%"
    assert "user" in replace(ScaleLimits(), mode=LimitMode.USER).describe()


def test_defaults_are_ds9s():
    settings = ScaleLimits()
    assert settings.mode is LimitMode.MINMAX
    assert settings.method is MinMaxMethod.SCAN
    assert settings.scope is LimitScope.LOCAL
    assert settings.use_datasec
    assert settings.contrast == pytest.approx(0.25)
    assert settings.log_exponent == pytest.approx(1000.0)


# -- the Scale menu, in a window --------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    window._rebuild_image_viewer(False)
    frame = window.frame_manager.current_frame
    rng = np.random.default_rng(1)
    image = rng.normal(100.0, 10.0, (40, 50)).astype(np.float32)
    image[0, 0] = 1.0e6
    frame.image_data = image
    frame.original_image_data = image
    from ncrads9.core.image_data import ImageData

    frame.image = ImageData(data=image, header=fits.Header())
    frame.header = fits.Header()
    yield window
    window.close()


def test_every_limit_mode_is_reachable_from_the_menu(main_window):
    from ncrads9.ui.menu_bar import SCALE_LIMIT_MODES

    for name, _label in SCALE_LIMIT_MODES:
        main_window.menu_bar.scale_limit_actions[name].trigger()
        assert main_window.scale.mode_key(main_window.scale_limits) == name


def test_choosing_a_mode_restretches_at_once(main_window):
    """`frame.z1`/`z2` are what Match and Lock copy, so they must be filled."""
    main_window.menu_bar.scale_limit_actions["minmax"].trigger()
    frame = main_window.frame_manager.current_frame
    assert frame.z1 == pytest.approx(main_window.z1)
    assert frame.z2 == pytest.approx(1.0e6)

    main_window.menu_bar.scale_limit_actions["99.5"].trigger()
    assert frame.z2 < 1000.0


def test_every_transfer_function_is_reachable_from_the_menu(main_window):
    from ncrads9.ui.controllers.scale import SCALE_ACTIONS

    for name, algorithm in SCALE_ACTIONS.items():
        main_window.menu_bar.scale_function_actions[name].trigger()
        assert main_window.current_scale is algorithm


def test_the_scope_actions_reach_the_settings(main_window):
    main_window.menu_bar.scale_scope_actions["global"].trigger()
    assert main_window.scale_limits.scope is LimitScope.GLOBAL
    main_window.menu_bar.scale_scope_actions["local"].trigger()
    assert main_window.scale_limits.scope is LimitScope.LOCAL


def test_the_method_actions_reach_the_settings(main_window):
    for name, method in (
        ("scan", MinMaxMethod.SCAN),
        ("sample", MinMaxMethod.SAMPLE),
        ("datamin", MinMaxMethod.DATAMIN),
        ("irafminmax", MinMaxMethod.IRAF),
    ):
        main_window.menu_bar.minmax_method_actions[name].trigger()
        assert main_window.scale_limits.method is method


def test_use_datasec_reaches_the_settings(main_window):
    main_window.menu_bar.action_use_datasec.setChecked(False)
    assert not main_window.scale_limits.use_datasec
    main_window.menu_bar.action_use_datasec.setChecked(True)
    assert main_window.scale_limits.use_datasec


def test_the_log_exponent_presets_reach_the_settings(main_window):
    for exponent, action in main_window.menu_bar.log_exponent_actions.items():
        action.trigger()
        assert main_window.scale_limits.log_exponent == pytest.approx(exponent)


def test_an_impossible_log_exponent_is_reported(main_window):
    main_window.scale.set_log_exponent(0.5)
    assert "must be between" in main_window.status_bar.currentMessage()


def test_user_limits_switch_the_mode(main_window):
    main_window.scale.set_user_limits(5.0, 9.0)
    assert main_window.scale_limits.mode is LimitMode.USER
    assert (main_window.z1, main_window.z2) == (5.0, 9.0)


def test_user_limits_are_ordered_by_the_controller(main_window):
    main_window.scale.set_user_limits(9.0, 5.0)
    assert (main_window.z1, main_window.z2) == (5.0, 9.0)


def test_sync_ticks_the_menu_from_the_settings(main_window):
    main_window.window_settings = None
    main_window.scale.update(scope=LimitScope.GLOBAL, method=MinMaxMethod.SAMPLE)
    main_window.scale.sync()
    assert main_window.menu_bar.scale_scope_actions["global"].isChecked()
    assert main_window.menu_bar.minmax_method_actions["sample"].isChecked()


def test_an_unknown_scope_or_method_is_reported(main_window):
    main_window.scale.set_scope("sideways")
    assert "Unknown scale scope" in main_window.status_bar.currentMessage()
    main_window.scale.set_minmax_method("guess")
    assert "Unknown min/max method" in main_window.status_bar.currentMessage()


def test_the_display_pipeline_uses_the_current_mode(main_window):
    """The mode has to reach the render path, not just the menu."""
    main_window.menu_bar.scale_limit_actions["minmax"].trigger()
    wide = main_window.z2
    main_window.menu_bar.scale_limit_actions["90"].trigger()
    assert main_window.z2 < wide


def test_the_button_bar_labels_match_the_menu(main_window):
    from ncrads9.ui.button_bar import CATEGORIES
    from ncrads9.ui.controllers.scale import BUTTON_LABELS

    labels = {spec.label for category, specs in CATEGORIES if category == "Scale" for spec in specs}
    assert set(BUTTON_LABELS.values()) <= labels | {"squared", "power", "sinh"}
