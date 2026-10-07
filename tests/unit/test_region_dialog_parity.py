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

"""The region dialogs against DS9's: following a drag, coordinate and
distance menus, fonts and colours, radii with Generate, live analysis with
saving and a Method menu, and the Save and Open follow-up dialogs."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from astropy.io import fits
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QColor, QMouseEvent

from ncrads9.coordinates import ds9_coords
from ncrads9.core.wcs_handler import WCSHandler
from ncrads9.regions import region_analysis, region_coords
from ncrads9.regions.region_formats import RegionFormat
from ncrads9.regions.region_parser import RegionParser
from ncrads9.regions.shapes.annulus import generate_radii
from ncrads9.ui.dialogs.region_analysis_dialog import RegionPlotDialog, RegionStatisticsDialog
from ncrads9.ui.dialogs.region_dialog import OTHER_COLOR, RegionDialog
from ncrads9.ui.dialogs.region_file_dialog import RegionFileDialog, RegionFileOptions
from ncrads9.ui.widgets.region_overlay import RegionMode, RegionOverlay

#: 3.6 arcsec pixels, centred on (150, +2).
HEADER = {
    "NAXIS": 2,
    "NAXIS1": 100,
    "NAXIS2": 100,
    "CTYPE1": "RA---TAN",
    "CTYPE2": "DEC--TAN",
    "CRPIX1": 50.0,
    "CRPIX2": 50.0,
    "CRVAL1": 150.0,
    "CRVAL2": 2.0,
    "CDELT1": -0.001,
    "CDELT2": 0.001,
}


def _parse(text: str):
    return RegionParser().parse_string(f"image\n{text}\n")[0]


def _frame(**extra):
    header = fits.Header({**HEADER, **extra})
    return SimpleNamespace(wcs_handler=WCSHandler(header), header=header)


@pytest.fixture
def frame():
    return _frame()


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
    y, x = np.mgrid[0:64, 0:64]
    frame.image_data = (x + 100.0 * y).astype(np.float32)
    frame.original_image_data = frame.image_data
    frame.header = fits.Header(HEADER)
    frame.wcs_handler = WCSHandler(frame.header)
    frame.regions = RegionParser().parse_string("image\ncircle(32,32,5)\nannulus(32,32,2,4,6)\n")
    window.region.show_frame_regions(frame)
    yield window
    for dialog in list(window.region._dialogs.values()):
        dialog.close()
    for analysis in list(window.region._analysis.values()):
        analysis.close()
    window.close()


# -- 1. the dialog follows its region ---------------------------------------------


def test_a_drag_reloads_the_open_dialog(main_window):
    """Apply after a drag used to snap the region back to where the dialog
    last saw it, because nothing told the dialog the region had moved."""
    circle = main_window.frame_manager.current_frame.regions[0]
    main_window.region.show_information(circle)
    dialog = main_window.region._dialogs[id(circle)]
    circle.selected = True

    main_window.region.on_edit("begin")
    circle.move(10, 0)
    main_window.region.on_edit("move")
    assert dialog._editors["center"].text() == "42 32"
    main_window.region.on_edit("finish")

    dialog.apply()
    assert circle.center == (42.0, 32.0)


def test_the_overlay_reports_every_step_of_a_drag(qapp):
    overlay = RegionOverlay()
    overlay.mode = RegionMode.NONE
    circle = _parse("circle(50,50,20)")
    overlay.manager.add_region(circle)
    phases: list[str] = []
    overlay.edit_notifier = phases.append

    def event(kind, x, y, buttons):
        point = overlay._to_widget(x, y)
        return QMouseEvent(kind, QPointF(point), QPointF(point), Qt.MouseButton.LeftButton, buttons,
                           Qt.KeyboardModifier.NoModifier)

    overlay.mousePressEvent(event(QEvent.Type.MouseButtonPress, 50, 50, Qt.MouseButton.LeftButton))
    overlay.mouseMoveEvent(event(QEvent.Type.MouseMove, 55, 50, Qt.MouseButton.LeftButton))
    overlay.mouseMoveEvent(event(QEvent.Type.MouseMove, 60, 50, Qt.MouseButton.LeftButton))
    overlay.mouseReleaseEvent(event(QEvent.Type.MouseButtonRelease, 60, 50, Qt.MouseButton.NoButton))
    assert phases == ["begin", "move", "move", "finish"]


def test_an_apply_from_the_dialog_reloads_the_others(main_window):
    circle = main_window.frame_manager.current_frame.regions[0]
    main_window.region.show_information(circle)
    dialog = main_window.region._dialogs[id(circle)]
    circle.radius = 8.0
    main_window.region._on_region_changed(circle)
    assert dialog._editors["radius"].text() == "8"


# -- 2. coordinate and distance menus ------------------------------------------------


def test_the_position_menu_offers_wcs_image_and_physical(qapp, frame):
    dialog = RegionDialog(_parse("circle(50,50,20)"), frame=frame)
    assert dialog.systems() == ("wcs", "image", "physical")
    menu = dialog._coord.actions_by_value
    assert {"fk4", "fk5", "icrs", "galactic", "ecliptic", "degrees", "sexagesimal"} <= set(menu)
    assert not menu["galactic"].isEnabled()
    assert not menu["wcsa"].isEnabled()
    dialog._coord.set_system("wcs", notify=True)
    dialog._coord.adjust(dialog._has, "physical", dialog._has)
    assert menu["galactic"].isEnabled() and menu["sexagesimal"].isEnabled()


def test_an_alternate_wcs_is_offered(qapp):
    frame = _frame(CTYPE1A="RA---TAN", CTYPE2A="DEC--TAN", CRPIX1A=1.0, CRPIX2A=1.0,
                   CRVAL1A=10.0, CRVAL2A=20.0, CDELT1A=-0.01, CDELT2A=0.01)
    dialog = RegionDialog(_parse("circle(50,50,20)"), frame=frame)
    assert "wcsa" in dialog.systems()
    dialog._coord.set_system("wcsa", notify=True)
    dialog._coord.set_sky(notify=True, sky="fk5")
    dialog._coord.set_sky_format(notify=True, sky_format="degrees")
    lon, lat = (float(v) for v in dialog._editors["center"].text().split())
    assert lon == pytest.approx(10.0, abs=1.0)
    assert lat == pytest.approx(20.5, abs=0.1)


@pytest.mark.parametrize("sky", ["fk4", "fk5", "icrs", "galactic", "ecliptic"])
@pytest.mark.parametrize("sky_format", ["degrees", "sexagesimal"])
def test_every_sky_frame_round_trips(qapp, frame, sky, sky_format):
    dialog = RegionDialog(_parse("circle(40,60,20)"), frame=frame)
    dialog._coord.set_system("wcs", notify=True)
    dialog._coord.set_sky(notify=True, sky=sky)
    dialog._coord.set_sky_format(notify=True, sky_format=sky_format)
    dialog.apply()
    assert dialog.region.center == pytest.approx((40.0, 60.0), abs=0.01)


def test_galactic_is_not_equatorial(qapp, frame):
    """The old dialog transformed out of the frame but not back into it."""
    dialog = RegionDialog(_parse("circle(40,60,20)"), frame=frame)
    dialog._coord.set_system("wcs", notify=True)
    dialog._coord.set_sky_format(notify=True, sky_format="degrees")
    dialog._coord.set_sky(notify=True, sky="fk5")
    fk5 = dialog._editors["center"].text()
    dialog._coord.set_sky(notify=True, sky="galactic")
    assert dialog._editors["center"].text() != fk5


def test_physical_uses_the_headers_transform(qapp):
    frame = _frame(LTV1=-10.0, LTV2=-20.0, LTM1_1=0.5, LTM2_2=0.5)
    dialog = RegionDialog(_parse("circle(40,60,20)"), frame=frame)
    dialog._coord.set_system("physical", notify=True)
    assert dialog._editors["center"].text() == "100 160"
    dialog._dist.set_system(notify=True, system="physical")
    assert dialog._editors["radius"].text() == "40"
    dialog._editors["radius"].setText("20")
    dialog.apply()
    assert dialog.region.radius == pytest.approx(10.0)
    assert dialog.region.center == pytest.approx((40.0, 60.0))


@pytest.mark.parametrize("unit,shown", [("arcsec", 72.0), ("arcmin", 1.2), ("degrees", 0.02)])
def test_a_radius_in_each_unit(qapp, frame, unit, shown):
    dialog = RegionDialog(_parse("circle(50,50,20)"), frame=frame)
    dialog._dist.set_system(notify=True, system="wcs")
    dialog._dist.set_distance_format(notify=True, distance_format=unit)
    assert float(dialog._editors["radius"].text()) == pytest.approx(shown)
    dialog._editors["radius"].setText(str(shown / 2))
    dialog.apply()
    assert dialog.region.radius == pytest.approx(10.0)


def test_the_unit_menu_is_only_live_for_a_wcs(qapp, frame):
    dialog = RegionDialog(_parse("circle(50,50,20)"), frame=frame)
    dialog._dist.set_system("physical")
    dialog._dist.adjust(dialog._has, "physical", dialog._has)
    assert not dialog._dist.actions_by_value["arcsec"].isEnabled()
    dialog._dist.set_system("wcs", notify=True)
    dialog._dist.adjust(dialog._has, "physical", dialog._has)
    assert dialog._dist.actions_by_value["arcsec"].isEnabled()


# -- 3. fonts and colours ------------------------------------------------------------


def test_apply_keeps_bold_and_italic(qapp):
    region = _parse('circle(50,50,20) # font="times 14 bold italic"')
    dialog = RegionDialog(region)
    assert dialog._font_weight.currentText() == "bold"
    assert dialog._font_slant.currentText() == "italic"
    dialog.apply()
    assert region.font == "times 14 bold italic"


def test_the_font_weight_and_slant_can_be_changed(qapp):
    region = _parse("circle(50,50,20)")
    dialog = RegionDialog(region)
    dialog._font_weight.setCurrentText("bold")
    dialog.apply()
    assert region.font == "helvetica 10 bold roman"


def test_other_opens_a_colour_chooser(qapp, monkeypatch):
    from PyQt6.QtWidgets import QColorDialog

    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor("#ff8800")))
    region = _parse("circle(50,50,20)")
    dialog = RegionDialog(region)
    dialog._on_color_activated(dialog._color.findText(OTHER_COLOR))
    assert dialog._color.currentText() == "#ff8800"
    dialog.apply()
    assert region.color == "#ff8800"


def test_cancelling_the_chooser_keeps_the_colour(qapp, monkeypatch):
    from PyQt6.QtWidgets import QColorDialog

    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor()))
    region = _parse("circle(50,50,20) # color=red")
    dialog = RegionDialog(region)
    dialog._on_color_activated(dialog._color.findText(OTHER_COLOR))
    assert dialog._color.currentText() == "red"


def test_a_colour_off_the_list_is_shown(qapp):
    dialog = RegionDialog(_parse("circle(50,50,20) # color=#123456"))
    assert dialog._color.currentText() == "#123456"


# -- 4. radii and Generate -------------------------------------------------------------


def test_an_annulus_keeps_every_radius():
    region = _parse("annulus(50,50,5,10,15)")
    assert region.radii == [5.0, 10.0, 15.0]
    assert region.to_ds9_string() == "annulus(50.0,50.0,5.0,10.0,15.0)"
    assert len(region_analysis.annuli(region)) == 2


def test_generate_matches_ds9():
    assert generate_radii(0, 10, 4) == [0.0, 2.5, 5.0, 7.5, 10.0]
    area = generate_radii(0, 10, 2, "area")
    assert area[1] == pytest.approx(10 / np.sqrt(2))


def test_the_annulus_dialog_generates_radii(qapp):
    region = _parse("annulus(50,50,5,15)")
    dialog = RegionDialog(region)
    assert dialog._radii.toPlainText().split() == ["5", "15"]
    dialog._generate_inner.setText("2")
    dialog._generate_outer.setText("12")
    dialog._generate_count.setValue(5)
    dialog.generate()
    dialog.apply()
    assert region.radii == pytest.approx([2, 4, 6, 8, 10, 12])
    assert dialog._editors["inner_radius"].text() == "2"


def test_editing_inner_alone_keeps_the_rings_inside(qapp):
    region = _parse("annulus(50,50,5,10,15)")
    dialog = RegionDialog(region)
    dialog._editors["inner_radius"].setText("7")
    dialog.apply()
    assert region.radii == [7.0, 10.0, 15.0]


def test_a_pandas_radii_list_sets_its_span_and_count(qapp):
    region = _parse("panda(50,50,0,360,4,8,18,2)")
    dialog = RegionDialog(region)
    assert len(dialog._radii.toPlainText().split()) == 3
    dialog._generate_inner.setText("4")
    dialog._generate_outer.setText("20")
    dialog._generate_count.setValue(4)
    dialog.generate()
    dialog.apply()
    assert (region.inner_radius, region.outer_radius, region.num_radii) == (4.0, 20.0, 4)


def test_radii_are_shown_in_the_distance_unit(qapp, frame):
    dialog = RegionDialog(_parse("annulus(50,50,5,10)"), frame=frame)
    dialog._dist.set_system(notify=True, system="wcs")
    dialog._dist.set_distance_format(notify=True, distance_format="arcsec")
    assert [float(v) for v in dialog._radii.toPlainText().split()] == pytest.approx([18.0, 36.0])


# -- 5. live analysis, saving data, the Method menu -----------------------------------


def test_a_statistics_window_follows_a_drag(main_window):
    circle = main_window.frame_manager.current_frame.regions[0]
    main_window.region.open_analysis(circle, "statistics")
    window = main_window.region._analysis[(id(circle), "statistics")]
    before = window.text()
    circle.selected = True
    main_window.region.on_edit("begin")
    circle.move(0, 10)
    main_window.region.on_edit("move")
    assert window.text() != before


def test_a_radial_profile_follows_a_drag(main_window):
    annulus = main_window.frame_manager.current_frame.regions[1]
    main_window.region.open_analysis(annulus, "radial")
    window = main_window.region._analysis[(id(annulus), "radial")]
    before = window.data
    annulus.selected = True
    annulus.move(5, 5)
    main_window.region.on_edit("move")
    assert window.data != before
    assert len(window.data[0]) == 2


def test_a_plot_saves_its_data(main_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    annulus = main_window.frame_manager.current_frame.regions[1]
    main_window.region.open_analysis(annulus, "radial")
    window = main_window.region._analysis[(id(annulus), "radial")]
    path = tmp_path / "radial.dat"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))
    window.action_save_data.trigger()
    rows = [line.split() for line in path.read_text().splitlines()]
    assert len(rows) == 2 and all(len(row) == 3 for row in rows)
    assert float(rows[0][0]) == pytest.approx(3.0)


def test_statistics_save(main_window, tmp_path):
    circle = main_window.frame_manager.current_frame.regions[0]
    main_window.region.open_analysis(circle, "statistics")
    window = main_window.region._analysis[(id(circle), "statistics")]
    path = tmp_path / "stats.txt"
    assert window.save(str(path))
    assert "surf_bri" in path.read_text()


def test_the_statistics_window_has_a_save_button(qapp):
    from PyQt6.QtWidgets import QDialogButtonBox

    window = RegionStatisticsDialog(_parse("circle(5,5,2)"), lambda region: "text")
    box = window.findChild(QDialogButtonBox)
    assert box.button(QDialogButtonBox.StandardButton.Save) is not None


@pytest.mark.parametrize("method,expected", [("sum", 9 * 6.0), ("average", 6.0), ("median", 6.0)])
def test_plot3d_methods(method, expected):
    cube = np.full((3, 20, 20), 6.0)
    box = _parse("box(10,10,3,3,0)")
    _slices, values = region_analysis.depth_profile(box, cube, method)
    assert values[0] == pytest.approx(expected)


def test_plot2d_methods_across_a_thick_projection():
    data = np.tile(np.array([1.0, 2.0, 9.0])[:, None], (1, 20))  # rows 1, 2, 3
    projection = _parse("projection(2,2,18,2,3)")
    _d, average = region_analysis.cut(projection, data, "average")
    _d, total = region_analysis.cut(projection, data, "sum")
    _d, median = region_analysis.cut(projection, data, "median")
    assert average[0] == pytest.approx(4.0)
    assert total[0] == pytest.approx(12.0)
    assert median[0] == pytest.approx(2.0)


def test_the_plot_windows_offer_the_method_menu(main_window):
    frame = main_window.frame_manager.current_frame
    frame.image = SimpleNamespace(data=np.stack([frame.image_data, 2 * frame.image_data, 3 * frame.image_data]))
    circle = frame.regions[0]
    main_window.region.open_analysis(circle, "plot3d")
    window = main_window.region._analysis[(id(circle), "plot3d")]
    assert set(window.method_actions) == {"average", "sum", "median"}
    assert window.method == "average"
    average = list(window.data[1])
    window.method_actions["sum"].trigger()
    assert window.method == "sum"
    assert window.data[1][0] > average[0]


def test_a_plot_without_methods_has_no_method_menu(qapp):
    window = RegionPlotDialog(_parse("circle(5,5,2)"), lambda region: ([1, 2], [3, 4], None), "T", ("x", "y"))
    assert window.method_actions == {}


# -- 6. Save and Open ----------------------------------------------------------------


def test_the_writer_restates_regions_in_a_sky_frame(frame):
    regions = RegionParser().parse_string("image\ncircle(50,50,20)\n")
    text = region_coords.write(regions, frame, system="wcs", sky="fk5", sky_format="sexagesimal")
    assert "\nfk5\n" in text
    assert "circle(10:00:00.0000,+02:00:00.000,72" in text
    assert '72' in text and '"' in text
    assert regions[0].center == (50.0, 50.0), "the regions on screen must not move"


@pytest.mark.parametrize("system", ["wcs", "galactic", "ecliptic", "physical", "icrs"])
@pytest.mark.parametrize("sky_format", ["degrees", "sexagesimal"])
def test_a_saved_file_reads_back_onto_the_same_pixels(frame, system, sky_format):
    regions = RegionParser().parse_string("image\ncircle(40,60,20)\npolygon(1,1,9,1,9,9)\nannulus(30,30,2,4,8)\n")
    text = region_coords.write(regions, frame, system=system, sky_format=sky_format)
    back = region_coords.place(RegionParser().parse_string(text), frame)
    assert back[0].center == pytest.approx((40.0, 60.0), abs=1e-3)
    assert back[0].radius == pytest.approx(20.0, abs=1e-3)
    assert back[1].vertices[2] == pytest.approx((9.0, 9.0), abs=1e-3)
    assert back[2].radii == pytest.approx([2.0, 4.0, 8.0], abs=1e-3)


def test_the_save_dialog_asks_ds9s_questions(qapp):
    dialog = RegionFileDialog("save", ("wcs",))
    assert dialog._current.isHidden()
    dialog._format.setCurrentIndex(dialog._format.findData(RegionFormat.CIAO))
    dialog._coord.set_system("wcs")
    dialog._coord.set_sky("galactic")
    dialog._coord.set_sky_format("sexagesimal")
    assert dialog.options() == RegionFileOptions(RegionFormat.CIAO, "wcs", "galactic", "sexagesimal", False)


def test_the_open_dialog_only_asks_a_system_for_xy(qapp):
    dialog = RegionFileDialog("load", ("wcs",))
    assert not dialog._coord.isEnabled()
    dialog._format.setCurrentIndex(dialog._format.findData(RegionFormat.XY))
    assert dialog._coord.isEnabled()
    dialog._all.setChecked(True)
    assert dialog.options().all_frames


def _choose(monkeypatch, options: RegionFileOptions):
    monkeypatch.setattr(RegionFileDialog, "exec", lambda self: 1)
    monkeypatch.setattr(RegionFileDialog, "options", lambda self: options)


def test_region_save_writes_the_chosen_system(main_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    path = tmp_path / "out.reg"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))
    _choose(monkeypatch, RegionFileOptions(RegionFormat.DS9, "wcs", "galactic", "degrees"))
    main_window.region.save_regions()
    text = path.read_text()
    assert "\ngalactic\n" in text
    assert "circle(236." in text


def test_region_save_cancelled_writes_nothing(main_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    path = tmp_path / "out.reg"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))
    monkeypatch.setattr(RegionFileDialog, "exec", lambda self: 0)
    main_window.region.save_regions()
    assert not path.exists()


def test_region_open_places_a_sky_file_on_the_image(main_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    frame = main_window.frame_manager.current_frame
    path = tmp_path / "sky.reg"
    path.write_text(region_coords.write(frame.regions, frame, system="wcs", sky_format="sexagesimal"))
    frame.regions = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
    _choose(monkeypatch, RegionFileOptions(RegionFormat.DS9))
    main_window.region.load_regions()
    assert frame.regions[0].center == pytest.approx((32.0, 32.0), abs=1e-3)
    assert frame.regions[0].radius == pytest.approx(5.0, abs=1e-3)


def test_region_open_reads_an_xy_file_in_the_chosen_system(main_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    frame = main_window.frame_manager.current_frame
    lon, lat = ds9_coords.from_image(frame, 20.0, 30.0, "wcs", "fk5")
    path = tmp_path / "points.xy"
    path.write_text(f"{lon} {lat}\n")
    frame.regions = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
    _choose(monkeypatch, RegionFileOptions(RegionFormat.XY, "wcs", "fk5"))
    main_window.region.load_regions()
    assert frame.regions[0].center == pytest.approx((20.0, 30.0), abs=1e-3)


def test_region_open_into_all_frames(main_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    second = main_window.frame_manager.new_frame()
    first = main_window.frame_manager.frames[0]
    main_window.frame_manager.goto_frame(0)
    path = tmp_path / "pix.reg"
    path.write_text("image\ncircle(10,10,3)\n")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
    _choose(monkeypatch, RegionFileOptions(RegionFormat.DS9, all_frames=True))
    before = len(first.regions)
    main_window.region.load_regions()
    assert len(first.regions) == before + 1
    assert [region.center for region in second.regions] == [(10.0, 10.0)]
    assert first.regions[-1] is not second.regions[0]
