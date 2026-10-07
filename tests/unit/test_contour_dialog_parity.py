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
The Contour Parameters dialog against DS9's (`ContourDialog`, `contour.tcl`).

Generate fills an editable Levels box from the number of levels, the
scale and the limits; Apply draws exactly what the box holds; the Limits,
Scale, Scope and Method menus are DS9's; levels files round-trip; and
Convert to Polygons turns contours into polygon regions.
"""

from __future__ import annotations

import numpy as np
import pytest

from ncrads9.analysis.contour import (
    CONTOUR_LIMIT_MODES,
    CONTOUR_SCALES,
    contour_limits,
    ds9_levels,
    parse_levels,
    parse_levels_file,
)


def _blobs() -> np.ndarray:
    """Two Gaussian sources on a ramp, 64 x 64."""
    yy, xx = np.mgrid[0:64, 0:64].astype(float)
    data = 100.0 * np.exp(-((xx - 18) ** 2 + (yy - 20) ** 2) / 30.0)
    data += 60.0 * np.exp(-((xx - 44) ** 2 + (yy - 42) ** 2) / 40.0)
    return data + 0.01 * xx


@pytest.fixture
def window(qapp, monkeypatch):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    real = Preferences.get
    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else real(self, key, default),
    )
    made = MainWindow()
    made._rebuild_image_viewer(False)
    frame = made.frame_manager.current_frame
    frame.image_data = _blobs().astype(np.float32)
    frame.original_image_data = frame.image_data
    yield made
    for dialog in list((getattr(made, "_open_windows", None) or {}).values()):
        dialog.close()
    made.close()


@pytest.fixture
def dialog(window):
    window.analysis.show_contour_dialog()
    found = window._open_windows["ContourDialog"]
    yield found


# -- the levels themselves -----------------------------------------------------


def test_linear_levels_run_from_low_to_high():
    assert ds9_levels(5, 0.0, 100.0, "linear") == [0.0, 25.0, 50.0, 75.0, 100.0]


def test_one_level_is_the_high_limit():
    assert ds9_levels(1, 3.0, 9.0, "log") == [9.0]


@pytest.mark.parametrize(
    ("scale", "fraction"),
    [
        ("log", lambda t: (1000.0**t - 1) / 1000.0),
        ("pow", lambda t: np.log10(1000.0 * t + 1) / np.log10(1000.0)),
        ("sqrt", lambda t: t * t),
        ("squared", lambda t: np.sqrt(t)),
        ("asinh", lambda t: np.sinh(3 * t) / 10),
        ("sinh", lambda t: np.arcsinh(10 * t) / 3),
    ],
)
def test_each_scale_is_dss9s_inverse_scale(scale, fraction):
    """`tksao/frame/inversescale.C`, transcribed."""
    got = ds9_levels(5, 10.0, 110.0, scale, 1000.0)
    steps = np.arange(5) / 4.0
    assert got == pytest.approx([fraction(t) * 100.0 + 10.0 for t in steps])


def test_the_log_exponent_changes_log_levels():
    assert ds9_levels(4, 0, 1, "log", 10.0) != ds9_levels(4, 0, 1, "log", 1000.0)


def test_histogram_equalization_follows_the_data():
    data = np.concatenate([np.zeros(900), np.linspace(0, 100, 100)])
    levels = ds9_levels(5, 0.0, 100.0, "histequ", data=data)
    assert levels == sorted(levels)
    # Ninety percent of the pixels are at zero, so most levels crowd there
    # -- unlike linear.
    assert levels[2] < 25.0 < ds9_levels(5, 0.0, 100.0, "linear")[2]


def test_the_scale_menu_is_ds9s():
    assert [label for _value, label in CONTOUR_SCALES] == [
        "Linear",
        "Log",
        "Power",
        "Square Root",
        "Squared",
        "ASINH",
        "SINH",
        "Histogram Equalization",
    ]


def test_the_limits_menu_is_ds9s():
    labels = [entry[1] if entry else "-" for entry in CONTOUR_LIMIT_MODES]
    assert labels == [
        "Min Max",
        "-",
        "99.5%",
        "99%",
        "98%",
        "97%",
        "96%",
        "95%",
        "92.5%",
        "90%",
        "-",
        "ZScale",
        "ZMax",
        "User",
    ]


def test_limits_from_each_mode():
    data = np.arange(1000, dtype=float)
    assert contour_limits(data, "minmax") == (0.0, 999.0)
    low, high = contour_limits(data, "90")
    assert low == pytest.approx(np.percentile(data, 5))
    assert high == pytest.approx(np.percentile(data, 95))
    assert contour_limits(data, "user") is None
    assert contour_limits(_blobs(), "zscale") is not None
    assert contour_limits(_blobs(), "zmax")[1] == pytest.approx(_blobs().max())


def test_levels_parse_from_whitespace_and_newlines():
    assert parse_levels("1 2\n3\t4.5\n\n") == [1.0, 2.0, 3.0, 4.5]


def test_a_contour_file_yields_its_level_lines():
    assert parse_levels_file("image\nlevel=3\n(1 2 3 4)\nlevel=7.5\n(1 2 3 4)\n") == [3.0, 7.5]


# -- the dialog ----------------------------------------------------------------


def test_the_dialog_has_ds9s_menus_and_buttons(dialog):
    assert list(dialog.menus) == ["File", "Edit", "Color", "Width", "Scale", "Limits", "Scope", "Method"]
    assert list(dialog.buttons) == ["Apply", "Generate", "Clear", "Close"]
    file_entries = [a.text() for a in dialog.menus["File"].actions() if not a.isSeparator()]
    assert file_entries == [
        "Open...",
        "Save...",
        "Apply",
        "Generate",
        "Clear",
        "Copy Contours",
        "Paste Contours",
        "Load Contour Levels...",
        "Save Contour Levels...",
        "Convert to Polygons",
        "Close",
    ]
    assert dialog.windowTitle() == "Contour Parameters"
    assert not dialog.isModal()


def test_the_dialog_opens_with_generated_levels(dialog):
    """DS9's `UpdateContourDialog`: no contours yet, so the box is generated."""
    assert len(dialog.levels()) == 5
    assert dialog.limits() is not None


def test_generate_edit_apply_draws_exactly_those_levels(window, dialog):
    dialog.set_limit_mode("minmax")
    dialog._num_levels_spin.setValue(4)
    dialog.set_scale("linear")
    generated = dialog.generate()
    low, high = float(_blobs().min()), float(_blobs().max())
    assert generated == pytest.approx(ds9_levels(4, low, high, "linear"), rel=1e-5)

    dialog.set_levels_text("12.5\n40\n77.25\n")
    dialog.buttons["Apply"].click()

    assert window.menu_bar.action_contours.isChecked()
    assert window._contour_levels == [12.5, 40.0, 77.25]
    assert len(window._contour_paths) == 3
    # And the frame keeps those levels when redrawn.
    window.analysis.update_contours()
    assert window._contour_levels == [12.5, 40.0, 77.25]


def test_apply_with_an_empty_box_generates_first(window, dialog):
    dialog.set_levels_text("")
    dialog.apply()
    assert window._contour_levels is not None and len(window._contour_levels) == 5


def test_the_limits_menu_fills_low_and_high(dialog):
    data = _blobs()
    dialog.menu_actions[("Limits", "minmax")].trigger()
    assert dialog.limits() == pytest.approx((data.min(), data.max()), rel=1e-6)
    dialog.menu_actions[("Limits", "95")].trigger()
    expected = (np.percentile(data, 2.5), np.percentile(data, 97.5))
    assert dialog.limits() == pytest.approx(expected, rel=1e-4)
    assert dialog.settings()["mode"] == "95"
    dialog.menu_actions[("Limits", "zscale")].trigger()
    assert dialog.settings()["mode"] == "zscale"


def test_typing_a_limit_is_user_mode(dialog):
    dialog._low_edit.setText("5")
    dialog._low_edit.textEdited.emit("5")
    assert dialog.settings()["mode"] == "user"
    assert dialog.menu_actions[("Limits", "user")].isChecked()


def test_the_scale_menu_changes_the_generated_levels(dialog):
    dialog.set_limits(0.0, 100.0)
    for value, _label in CONTOUR_SCALES:
        dialog.menu_actions[("Scale", value)].trigger()
        assert dialog.settings()["scale"] == value
        if value != "histequ":
            assert dialog.generate() == pytest.approx(ds9_levels(5, 0.0, 100.0, value), abs=1e-6)
    dialog.set_log_exponent(10.0)
    dialog.set_scale("log")
    assert dialog.generate() == pytest.approx(ds9_levels(5, 0.0, 100.0, "log", 10.0), abs=1e-6)


def test_color_width_dash_and_method_reach_the_settings(dialog):
    dialog.menu_actions[("Color", "red")].trigger()
    dialog.menu_actions[("Width", "3")].trigger()
    dialog.menu_actions[("Width", "dash")].trigger()
    dialog.menu_actions[("Method", "block")].trigger()
    dialog.menu_actions[("Scope", "global")].trigger()
    settings = dialog.settings()
    assert settings["color"] == "red"
    assert settings["line_width"] == 3
    assert settings["line_style"] == "Dashed"
    assert settings["contour_method"] == "block"
    assert settings["scope"] == "global"


def test_levels_save_and_load_round_trip(dialog, tmp_path):
    dialog.set_levels_text("1.5\n2.5\n10\n")
    target = tmp_path / "my.lev"
    dialog.save_levels_file(str(target))
    assert parse_levels(target.read_text()) == [1.5, 2.5, 10.0]

    dialog.set_levels_text("")
    assert dialog.load_levels_file(str(target)) == [1.5, 2.5, 10.0]
    assert dialog.levels() == [1.5, 2.5, 10.0]


def test_a_plain_numbers_file_loads_too(dialog, tmp_path):
    target = tmp_path / "levels.txt"
    target.write_text("3 4\n5\n")
    assert dialog.load_levels_file(str(target)) == [3.0, 4.0, 5.0]


def test_the_dialog_seeds_from_the_contours_on_screen(window, dialog):
    dialog.menu_actions[("Color", "cyan")].trigger()
    dialog.set_levels_text("20 50")
    dialog.apply()
    dialog.close()
    window._open_windows.pop("ContourDialog", None)

    window.analysis.show_contour_dialog()
    again = window._open_windows["ContourDialog"]
    assert again is not dialog
    assert again.levels() == [20.0, 50.0]
    assert again.settings()["color"] == "cyan"


def test_clear_takes_the_contours_off(window, dialog):
    dialog.apply()
    assert window.menu_bar.action_contours.isChecked()
    dialog.buttons["Clear"].click()
    assert not window.menu_bar.action_contours.isChecked()
    assert dialog.levels(), "Clear regenerates the box, as DS9's does"


def test_convert_to_polygons_makes_polygon_regions(window, dialog):
    from ncrads9.regions.shapes.polygon import Polygon

    frame = window.frame_manager.current_frame
    frame.regions = []
    dialog.set_levels_text("50")
    dialog.menu_actions[("Color", "red")].trigger()
    dialog.apply()
    paths = [path for level in window._contour_paths for path in level]
    assert paths

    dialog.menu_actions[("File", "polygons")].trigger()

    polygons = [region for region in frame.regions if isinstance(region, Polygon)]
    assert len(polygons) == len(paths)
    assert all(polygon.color == "red" for polygon in polygons)
    assert not window.menu_bar.action_contours.isChecked(), "DS9 deletes the contours"
    # The polygon sits around the brighter source at (18, 20).
    xs = [x for x, _y in polygons[0].vertices]
    ys = [y for _x, y in polygons[0].vertices]
    centre = (np.mean(xs), np.mean(ys))
    assert min(np.hypot(centre[0] - 18, centre[1] - 20), np.hypot(centre[0] - 44, centre[1] - 42)) < 2


# -- the XPA access point still drives it ------------------------------------------


def test_xpa_levels_limits_and_scale(window):
    from ncrads9.communication.xpa.access_points import _contour, _contour_text

    assert _contour(window, ["levels", "10", "30", "60"]) is None
    assert window._contour_levels == [10.0, 30.0, 60.0]
    assert _contour_text(window, ["levels"]) == "10 30 60"

    assert _contour(window, ["limits", "0", "100"]) is None
    assert window._contour_settings["mode"] == "user"
    assert _contour(window, ["nlevels", "3"]) is None
    assert window._contour_levels == pytest.approx([0.0, 50.0, 100.0])

    assert _contour(window, ["scale", "sqrt"]) is None
    assert window._contour_levels == pytest.approx([0.0, 25.0, 100.0])
    assert _contour_text(window, ["scale"]) == "sqrt"
    assert _contour_text(window, ["limits"]) == "0 100"

    assert _contour(window, ["method", "block"]) is None
    assert _contour_text(window, ["method"]) == "block"


def test_xpa_convert_makes_polygons(window):
    from ncrads9.communication.xpa.access_points import _contour

    frame = window.frame_manager.current_frame
    frame.regions = []
    _contour(window, ["levels", "50"])
    assert _contour(window, ["convert"]) is None
    assert frame.regions


def test_an_image_too_small_to_contour_has_no_contours():
    """Block 64 on a 64-pixel image left one pixel, and contouring it raised."""
    import numpy as np

    from ncrads9.analysis.contour import _paths

    assert _paths(np.ones((1, 1)), 0.5) == []
    assert _paths(np.ones((1, 5)), 0.5) == []
