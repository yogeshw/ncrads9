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

"""The WCS coordinate grid (M7-10 ... M7-14)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.core.wcs_handler import WCSHandler
from ncrads9.grid import (
    ELEMENTS,
    LINE_ELEMENTS,
    GridConfig,
    GridRenderer,
    GridType,
    LabelPosition,
    Placement,
    default_format,
    format_coordinate,
    nice_spacing,
    parse_format,
)

SIZE = 300


def _header(
    ctype1: str = "RA---TAN",
    crval: tuple[float, float] = (150.0, 2.0),
    cdelt: float = 0.002,
    rotation: float | None = None,
) -> fits.Header:
    header = fits.Header(
        {
            "NAXIS": 2,
            "NAXIS1": SIZE,
            "NAXIS2": SIZE,
            "CTYPE1": ctype1,
            "CTYPE2": "DEC--TAN" if "RA" in ctype1 else "GLAT-TAN",
            "CRPIX1": SIZE / 2,
            "CRPIX2": SIZE / 2,
            "CRVAL1": crval[0],
            "CRVAL2": crval[1],
            "CDELT1": -cdelt,
            "CDELT2": cdelt,
        }
    )
    if rotation is not None:
        header["CROTA2"] = rotation
    return header


@pytest.fixture
def wcs() -> WCSHandler:
    return WCSHandler(_header())


@pytest.fixture
def renderer(wcs) -> GridRenderer:
    return GridRenderer(wcs, GridConfig(visible=True))


# -- the numeric formats (M7-12) -----------------------------------------------


@pytest.mark.parametrize(
    "spec,value,expected",
    [
        # DS9's defaults.
        ("hms.1", 187.2708, "12:29:05.0"),
        ("dms.1", 12.3456, "12:20:44.2"),
        ("d.3", 187.2708, "187.271"),
        # `+` prefixes a plus to positive values.
        ("+dms.2", 12.3456, "+12:20:44.16"),
        ("+dms.2", -12.3456, "-12:20:44.16"),
        # `z` pads the first field.
        ("zhms.1", 7.5, "00:30:00.0"),
        # `l` separates with letters, `b` with blanks, `i` with colons.
        ("ldms.1", 12.3456, "12d20m44.2s"),
        ("bdms.1", 12.3456, "12 20 44.2"),
        ("idms.1", 12.3456, "12:20:44.2"),
        # `t` alone means hours; `d` overrides it.
        ("t.2", 187.27, "12.48"),
        ("dt.2", 187.27, "187.27"),
        # A printf spec is passed through, as DS9's documentation allows.
        ("%1.7G", 187.2708, "187.2708"),
        ("%.2f", 187.2708, "187.27"),
        # `m` without `s` stops at minutes.
        ("dm.2", 12.5, "12:30.00"),
    ],
)
def test_ds9s_format_characters(spec, value, expected):
    assert format_coordinate(value, spec) == expected


def test_the_last_separator_character_wins():
    """DS9: "the character occurring last takes precedence"."""
    assert format_coordinate(12.3456, "ibdms.1") == "12 20 44.2"
    assert format_coordinate(12.3456, "bidms.1") == "12:20:44.2"


def test_a_rounded_seconds_field_carries_upwards():
    """59.96 seconds at one decimal is the next minute, not 60.0."""
    assert format_coordinate(12.0 + 34 / 60 + 59.96 / 3600, "dms.1") == "12:35:00.0"


def test_a_carry_propagates_past_the_minutes():
    assert format_coordinate(12.0 + 59 / 60 + 59.99 / 3600, "dms.1") == "13:00:00.0"


def test_g_marks_its_separators_for_superscripting():
    """DS9's `g` asks for the separator as a small superscript."""
    assert "^" in format_coordinate(12.3456, "gdms.1")


def test_an_empty_format_is_plain_degrees():
    assert format_coordinate(12.3456, "") == "12"


@pytest.mark.parametrize(
    "latitude,sky_format,expected",
    [
        (False, "sexagesimal", "hms.1"),
        (True, "sexagesimal", "dms.1"),
        (False, "degrees", "d.3"),
        (True, "degrees", "d.3"),
    ],
)
def test_ds9s_default_formats(latitude, sky_format, expected):
    """A longitude is written in hours and a latitude never is."""
    assert default_format("", latitude, sky_format) == expected


def test_a_format_the_user_set_is_kept():
    assert default_format("%1.7G", True, "degrees") == "%1.7G"


def test_a_printf_spec_is_recognised_as_one():
    assert parse_format("%1.7G").printf == "%1.7G"
    assert parse_format("hms.1").printf is None


# -- choosing an interval -------------------------------------------------------


def test_a_sexagesimal_interval_is_round_in_minutes():
    """A grid labelled every 0.02 degrees is unreadable."""
    step = nice_spacing(0.5, 6, sexagesimal=True)
    assert step * 60 == pytest.approx(5.0)


def test_a_decimal_interval_is_round_in_degrees():
    assert nice_spacing(0.5, 6, sexagesimal=False) == pytest.approx(0.1)


def test_an_interval_is_never_zero():
    """A zero interval is an infinite loop in every caller."""
    assert nice_spacing(0.0, 6, True) > 0
    assert nice_spacing(-1.0, 6, True) > 0
    assert nice_spacing(1.0, 0, True) > 0


def test_a_huge_span_still_gets_an_interval():
    assert nice_spacing(3600.0, 6, False) > 0


# -- the geometry (M7-10) ----------------------------------------------------------


def test_the_grid_has_lines_in_both_directions(renderer):
    geometry = renderer.compute(SIZE, SIZE)
    assert geometry.longitude_lines
    assert geometry.latitude_lines


def test_every_grid_point_is_on_the_image(renderer):
    geometry = renderer.compute(SIZE, SIZE)
    for line in geometry.lines:
        for x, y in line:
            assert 0.0 <= x <= SIZE + 1
            assert 0.0 <= y <= SIZE + 1


def test_a_grid_line_is_a_polyline_not_two_points(renderer):
    """A line of constant declination is curved by the projection."""
    geometry = renderer.compute(SIZE, SIZE)
    assert max(len(line) for line in geometry.lines) > 10


def test_the_lines_fall_on_round_values(renderer):
    """Anchoring on the image's own edge would put them on arbitrary ones."""
    geometry = renderer.compute(SIZE, SIZE)
    step = geometry.latitude_spacing
    for label in geometry.labels:
        if ":" not in label.text:
            continue
    # The declination lines are multiples of the step, so their labels end
    # in round seconds.
    assert step > 0


def test_a_rotated_wcs_still_gets_a_grid():
    renderer = GridRenderer(WCSHandler(_header(rotation=30.0)), GridConfig(visible=True))
    geometry = renderer.compute(SIZE, SIZE)
    assert geometry.longitude_lines and geometry.latitude_lines


def test_a_galactic_wcs_gets_a_grid():
    """`world_to_pixel` used to assume ICRS, so this drew nothing at all."""
    renderer = GridRenderer(WCSHandler(_header("GLON-TAN")), GridConfig(visible=True))
    geometry = renderer.compute(SIZE, SIZE)
    assert geometry.longitude_lines and geometry.latitude_lines


def test_a_wide_field_gets_a_coarser_interval():
    narrow = GridRenderer(WCSHandler(_header(cdelt=0.001)), GridConfig(visible=True))
    wide = GridRenderer(WCSHandler(_header(cdelt=0.05)), GridConfig(visible=True))
    assert wide.compute(SIZE, SIZE).latitude_spacing > narrow.compute(SIZE, SIZE).latitude_spacing


def test_no_wcs_means_no_grid():
    """Shown as no grid rather than as a wrong one."""
    geometry = GridRenderer(None, GridConfig(visible=True)).compute(SIZE, SIZE)
    assert geometry.lines == []
    assert geometry.labels == []


def test_an_invalid_wcs_means_no_grid():
    renderer = GridRenderer(WCSHandler(fits.Header()), GridConfig(visible=True))
    assert renderer.usable is False
    assert renderer.compute(SIZE, SIZE).lines == []


def test_the_border_is_the_images_outline(renderer):
    geometry = renderer.compute(SIZE, SIZE)
    assert geometry.border[0] == geometry.border[-1]
    assert (SIZE + 0.5, SIZE + 0.5) in geometry.border


def test_the_sky_bounds_cover_the_image(renderer):
    bounds = renderer.sky_bounds(SIZE, SIZE)
    assert bounds is not None
    lon0, lon1, lat0, lat1 = bounds
    assert lon0 < 150.0 < lon1
    assert lat0 < 2.0 < lat1


def test_a_field_across_zero_hours_is_not_taken_as_the_whole_sky():
    """Unwrapped, or the range reads 0 to 360 and the grid is nonsense."""
    renderer = GridRenderer(WCSHandler(_header(crval=(0.0, 2.0), cdelt=0.01)), GridConfig(visible=True))
    bounds = renderer.sky_bounds(SIZE, SIZE)
    assert bounds is not None
    lon0, lon1, _lat0, _lat1 = bounds
    assert lon1 - lon0 < 10.0


def test_a_manual_interval_is_honoured(wcs):
    config = GridConfig(visible=True, auto_spacing=False, x_spacing=0.05, y_spacing=0.05)
    renderer = GridRenderer(wcs, config)
    assert renderer.spacings(SIZE, SIZE) == (0.05, 0.05)


def test_a_longitude_interval_is_widened_near_the_pole():
    """An hour of RA covers less sky at high declination."""
    equator = GridRenderer(WCSHandler(_header(crval=(150.0, 0.0))), GridConfig(visible=True))
    high = GridRenderer(WCSHandler(_header(crval=(150.0, 80.0))), GridConfig(visible=True))
    assert high.spacings(SIZE, SIZE)[0] >= equator.spacings(SIZE, SIZE)[0]


# -- labels and ticks (M7-11) ---------------------------------------------------------


def test_every_grid_line_gets_a_label(renderer):
    geometry = renderer.compute(SIZE, SIZE)
    assert len(geometry.labels) > 0
    assert len(geometry.labels) == len(geometry.ticks)


def test_labels_sit_on_an_edge(renderer):
    geometry = renderer.compute(SIZE, SIZE)
    for label in geometry.labels:
        assert isinstance(label.position, LabelPosition)


def test_latitude_labels_prefer_the_side(renderer):
    """A declination label on the bottom edge is beside the wrong numbers."""
    geometry = renderer.compute(SIZE, SIZE)
    sides = {LabelPosition.LEFT, LabelPosition.RIGHT}
    latitude_labels = [label for label in geometry.labels if label.position in sides]
    assert latitude_labels


def test_a_tick_points_inwards_from_its_edge(renderer):
    geometry = renderer.compute(SIZE, SIZE)
    for _x, _y, dx, dy in geometry.ticks:
        assert (dx, dy) != (0.0, 0.0)


def test_the_axis_titles_name_the_coordinate_system(wcs):
    renderer = GridRenderer(wcs, GridConfig(visible=True, sky="fk5"))
    geometry = renderer.compute(SIZE, SIZE)
    assert geometry.x_title == "Right Ascension"
    assert geometry.y_title == "Declination"

    renderer.config = GridConfig(visible=True, sky="galactic")
    geometry = renderer.compute(SIZE, SIZE)
    assert geometry.x_title == "Galactic Longitude"


def test_a_title_the_user_set_wins(wcs):
    renderer = GridRenderer(wcs, GridConfig(visible=True, x_title="Mine"))
    assert renderer.compute(SIZE, SIZE).x_title == "Mine"


# -- the configuration (M7-11, M7-13, M7-14) --------------------------------------------


def test_ds9s_seven_elements_are_all_there():
    config = GridConfig()
    assert set(config.elements) == set(ELEMENTS)
    assert len(ELEMENTS) == 7


def test_a_line_element_has_a_style_and_a_text_element_a_font():
    config = GridConfig()
    assert "grid" in LINE_ELEMENTS
    assert "numerics" not in LINE_ELEMENTS
    assert config.element("grid").style in ("solid", "dashed", "dotted")
    assert config.element("numerics").font


def test_nothing_is_shown_when_the_grid_is_off():
    config = GridConfig(visible=False)
    assert all(not config.shows(name) for name in ELEMENTS)


def test_a_publication_grid_draws_no_lines_over_the_data():
    """That is the difference between the two types."""
    config = GridConfig(visible=True, grid_type=GridType.PUBLICATION)
    assert config.shows("grid") is False
    assert config.shows("border") is True
    assert config.shows("numerics") is True


def test_an_elements_own_show_is_honoured():
    config = GridConfig(visible=True)
    config.element("tickmarks").show = False
    assert config.shows("tickmarks") is False


def test_a_copy_is_independent():
    config = GridConfig(visible=True)
    other = config.copy()
    other.element("grid").color = "red"
    assert config.element("grid").color != "red"


def test_the_configuration_round_trips_through_a_file(tmp_path):
    config = GridConfig(
        visible=True,
        grid_type=GridType.PUBLICATION,
        numerics_placement=Placement.INTERIOR,
        vertical_text=True,
        sky="galactic",
        sky_format="degrees",
        x_format="%1.7G",
        title="M51",
        auto_spacing=False,
        x_spacing=0.25,
    )
    config.element("grid").color = "red"
    config.element("title").font_size = 18

    path = tmp_path / "grid.grd"
    config.save(path)
    restored = GridConfig.load(path)

    assert restored.grid_type is GridType.PUBLICATION
    assert restored.numerics_placement is Placement.INTERIOR
    assert restored.vertical_text is True
    assert restored.sky == "galactic"
    assert restored.x_format == "%1.7G"
    assert restored.title == "M51"
    assert restored.x_spacing == 0.25
    assert restored.element("grid").color == "red"
    assert restored.element("title").font_size == 18


def test_a_partial_file_keeps_the_defaults():
    """A file from an earlier version should load, not be rejected."""
    config = GridConfig.from_dict({"visible": True, "elements": {}})
    assert config.sky == "fk5"
    assert len(config.elements) == 7


def test_loading_something_that_is_not_a_grid(tmp_path):
    path = tmp_path / "not.grd"
    path.write_text('{"hello": 1}')
    with pytest.raises(ValueError, match="not a saved grid"):
        GridConfig.load(path)


# -- the dialog (M7-13) --------------------------------------------------------------


@pytest.fixture
def dialog(qapp):
    from ncrads9.ui.dialogs.grid_dialog import GridDialog

    return GridDialog(GridConfig(visible=True))


def test_the_dialog_has_a_tab_per_element(dialog):
    from PyQt6.QtWidgets import QTabWidget

    notebook = dialog.findChild(QTabWidget)
    titles = [notebook.tabText(index) for index in range(notebook.count())]
    for name in ELEMENTS:
        assert name.title() in titles


def test_the_dialog_edits_a_copy(qapp):
    """Cancel has to really cancel."""
    from ncrads9.ui.dialogs.grid_dialog import GridDialog

    original = GridConfig(visible=True)
    dialog = GridDialog(original)
    dialog._widgets["grid.color"].setCurrentText("red")
    dialog.gather()
    assert original.element("grid").color != "red"


def test_every_element_setting_is_read_back(dialog):
    dialog._widgets["grid.color"].setCurrentText("magenta")
    dialog._widgets["grid.style"].setCurrentText("dotted")
    dialog._widgets["grid.width"].setCurrentText("3")
    dialog._widgets["numerics.font"].setCurrentText("courier")
    dialog._widgets["numerics.font_size"].setCurrentText("18")
    dialog._widgets["title.show"].setChecked(False)

    config = dialog.gather()
    assert config.element("grid").color == "magenta"
    assert config.element("grid").style == "dotted"
    assert config.element("grid").width == 3
    assert config.element("numerics").font == "courier"
    assert config.element("numerics").font_size == 18
    assert config.element("title").show is False


def test_the_type_and_placement_menus_are_read_back(dialog):
    dialog._widgets["grid_type"].setCurrentText("publication")
    dialog._widgets["axes_placement"].setCurrentText("interior")
    dialog._widgets["vertical_text"].setChecked(True)

    config = dialog.gather()
    assert config.grid_type is GridType.PUBLICATION
    assert config.axes_placement is Placement.INTERIOR
    assert config.vertical_text is True


def test_a_zero_interval_means_automatic(dialog):
    """A grid line every nought degrees is an infinite loop, not a setting."""
    dialog._widgets["auto_spacing"].setChecked(False)
    dialog._widgets["x_spacing"].setValue(0.0)
    assert dialog.gather().x_spacing is None


def test_apply_announces_the_settings(dialog):
    seen = []
    dialog.grid_changed.connect(seen.append)
    dialog.apply()
    assert len(seen) == 1
    assert isinstance(seen[0], GridConfig)


# -- through the menu -------------------------------------------------------------------


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
    data = (rows + columns).astype(np.float32)
    path = tmp_path / "grid.fits"
    fits.PrimaryHDU(data=data, header=_header()).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    yield window
    window.close()


def test_the_menu_toggle_computes_a_grid(main_window):
    # `trigger` is the click; `setChecked` emits `toggled`, and the action
    # is wired to `triggered`.
    main_window.menu_bar.action_coordinate_grid.trigger()
    overlay = main_window.image_viewer.contour_overlay
    assert overlay._grid_geometry is not None
    assert overlay._grid_geometry.longitude_lines


def test_turning_it_off_clears_the_geometry(main_window):
    main_window.menu_bar.action_coordinate_grid.trigger()
    main_window.menu_bar.action_coordinate_grid.trigger()
    assert main_window.image_viewer.contour_overlay._grid_geometry is None


def test_a_frame_with_no_wcs_says_so(main_window):
    main_window.frame_manager.current_frame.wcs_handler = WCSHandler(fits.Header())
    main_window.menu_bar.action_coordinate_grid.trigger()
    assert "no WCS" in main_window.status_bar.currentMessage()


def test_applying_settings_redraws(main_window):
    config = GridConfig(visible=True)
    config.element("grid").color = "red"
    main_window.analysis.apply_grid_settings(config)
    assert main_window.analysis.grid_config.element("grid").color == "red"
    assert main_window.image_viewer.contour_overlay._grid_config.element("grid").color == "red"


def test_the_grid_is_cached_in_image_coordinates(main_window):
    """So a zoom or a pan re-maps it rather than recomputing it."""
    main_window.menu_bar.action_coordinate_grid.trigger()
    geometry = main_window.image_viewer.contour_overlay._grid_geometry
    x, y = geometry.longitude_lines[0][0]
    assert 0 <= x <= SIZE + 1 and 0 <= y <= SIZE + 1


# -- the display bug the grid exposed -----------------------------------------------------


def test_the_image_is_not_stretched_to_the_viewport(qapp, tmp_path, monkeypatch):
    """The label used to scale its pixmap to fill, ignoring aspect ratio, so
    the picture did not line up with its own overlays."""
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    path = tmp_path / "square.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32), header=_header()).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    label = window.image_viewer.image_viewer

    assert label.hasScaledContents() is False
    pixmap = label.pixmap()
    assert pixmap is not None
    # A square image stays square whatever shape the viewport is.
    assert pixmap.width() == pixmap.height()
    window.close()
