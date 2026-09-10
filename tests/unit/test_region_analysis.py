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

"""What a region says about the pixels under it (M6-22 ... M6-26)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from ncrads9.regions import region_analysis as analysis
from ncrads9.regions.region_parser import RegionParser
from ncrads9.ui.dialogs.region_dialog import RegionDialog, analysis_commands_for


def _parse(text: str):
    return RegionParser().parse_string(f"image\n{text}\n")[0]


@pytest.fixture
def flat() -> np.ndarray:
    """An image of ones: every sum is a pixel count."""
    return np.ones((64, 64), dtype=np.float32)


@pytest.fixture
def ramp() -> np.ndarray:
    """An image whose value is its column number, for a predictable cut."""
    return np.tile(np.arange(64, dtype=np.float32), (64, 1))


# -- which pixels are inside ------------------------------------------------------


def test_a_circle_covers_about_pi_r_squared(flat):
    inside = analysis.mask_for(_parse("circle(32,32,10)"), flat.shape)
    assert inside.sum() == pytest.approx(math.pi * 100, rel=0.05)


def test_a_box_covers_its_area(flat):
    inside = analysis.mask_for(_parse("box(32,32,10,6,0)"), flat.shape)
    assert inside.sum() == pytest.approx(10 * 6, rel=0.2)


def test_a_rotated_box_covers_the_same_area(flat):
    upright = analysis.mask_for(_parse("box(32,32,12,6,0)"), flat.shape).sum()
    turned = analysis.mask_for(_parse("box(32,32,12,6,45)"), flat.shape).sum()
    assert turned == pytest.approx(upright, rel=0.2)


def test_a_polygon_covers_its_interior(flat):
    inside = analysis.mask_for(_parse("polygon(20,20,30,20,30,30,20,30)"), flat.shape)
    assert inside.sum() == pytest.approx(100, rel=0.25)


def test_a_region_off_the_edge_covers_what_is_on_it(flat):
    """Half a circle at the corner is half a circle, not an IndexError."""
    inside = analysis.mask_for(_parse("circle(1,1,10)"), flat.shape)
    assert 0 < inside.sum() < math.pi * 100


def test_a_region_entirely_off_the_image_covers_nothing(flat):
    assert analysis.mask_for(_parse("circle(500,500,10)"), flat.shape).sum() == 0


# -- statistics ----------------------------------------------------------------------


def test_the_statistics_of_a_flat_region(flat):
    (measured,) = analysis.statistics(_parse("circle(32,32,10)"), flat)
    assert measured.total == measured.npix
    assert measured.mean == pytest.approx(1.0)
    assert measured.median == pytest.approx(1.0)
    assert measured.variance == pytest.approx(0.0, abs=1e-9)
    assert measured.stddev == pytest.approx(0.0, abs=1e-6)
    assert measured.rms == pytest.approx(1.0)


def test_the_error_is_the_root_of_the_sum(flat):
    """DS9's counting error, `sqrt(|sum|)` (`frblt.C`, markerAnalysisStats2)."""
    (measured,) = analysis.statistics(_parse("circle(32,32,10)"), flat)
    assert measured.error == pytest.approx(math.sqrt(measured.total))


def test_surface_brightness_is_the_sum_per_pixel(flat):
    (measured,) = analysis.statistics(_parse("circle(32,32,10)"), flat)
    assert measured.surface_brightness == pytest.approx(measured.total / measured.area)


def test_the_variance_is_ds9s_population_form():
    """`|sum2/n - (sum/n)^2|`, not the sample variance -- they differ by n/(n-1)."""
    data = np.zeros((32, 32), dtype=np.float32)
    data[10:20, 10:20] = np.arange(100, dtype=np.float32).reshape(10, 10)
    (measured,) = analysis.statistics(_parse("box(15.5,15.5,10,10,0)"), data)
    values = data[10:20, 10:20].ravel()
    assert measured.variance == pytest.approx(float(np.var(values)), rel=1e-6)


def test_nans_are_left_out(flat):
    flat[30:35, 30:35] = np.nan
    (measured,) = analysis.statistics(_parse("circle(32,32,10)"), flat)
    assert np.isfinite(measured.total)
    assert measured.npix < math.pi * 100


def test_a_region_covering_nothing_measures_as_nothing(flat):
    (measured,) = analysis.statistics(_parse("circle(500,500,5)"), flat)
    assert (measured.npix, measured.total) == (0, 0.0)


def test_statistics_need_an_image():
    with pytest.raises(analysis.AnalysisError, match="no image"):
        analysis.statistics(_parse("circle(1,1,1)"), None)


# -- annuli ---------------------------------------------------------------------------


def test_a_plain_shape_is_one_ring():
    assert len(analysis.annuli(_parse("circle(32,32,10)"))) == 1


def test_an_annulus_is_one_ring():
    rings = analysis.annuli(_parse("annulus(32,32,5,10)"))
    assert [(ring.inner_radius, ring.outer_radius) for ring in rings] == [(5.0, 10.0)]


def test_a_panda_is_one_ring_per_annulus():
    """Reporting them together would say nothing a plain circle does not."""
    rings = analysis.annuli(_parse("panda(32,32,0,360,4,4,12,2)"))
    assert [(ring.inner_radius, ring.outer_radius) for ring in rings] == [(4.0, 8.0), (8.0, 12.0)]


def test_statistics_report_one_row_per_ring(flat):
    measured = analysis.statistics(_parse("panda(32,32,0,360,4,4,12,2)"), flat)
    assert len(measured) == 2
    # The outer ring is the larger one.
    assert measured[1].npix > measured[0].npix


def test_the_text_has_both_of_ds9s_tables(flat):
    text = analysis.describe(_parse("circle(32,32,10)"), flat)
    assert "surf_bri" in text
    assert "stddev" in text
    assert text.startswith("center=")


# -- radial profile ---------------------------------------------------------------------


def test_a_radial_profile_has_a_point_per_ring(flat):
    radii, brightness, errors = analysis.radial_profile(_parse("panda(32,32,0,360,4,4,16,3)"), flat)
    assert len(radii) == len(brightness) == len(errors) == 3
    assert radii == sorted(radii)


def test_a_radial_profile_follows_the_data():
    """A source at the centre is brightest in the innermost ring."""
    rows, columns = np.indices((64, 64))
    data = np.exp(-(((columns - 31) ** 2 + (rows - 31) ** 2) / 50.0)).astype(np.float32)
    _radii, brightness, _errors = analysis.radial_profile(_parse("panda(32,32,0,360,4,0,16,4)"), data)
    assert brightness == sorted(brightness, reverse=True)


def test_a_circle_has_no_radial_profile(flat):
    with pytest.raises(analysis.AnalysisError, match="annuli"):
        analysis.radial_profile(_parse("circle(32,32,10)"), flat)


# -- cuts and cubes -------------------------------------------------------------------------


def test_a_cut_reads_along_the_line(ramp):
    distances, values = analysis.cut(_parse("projection(10,32,50,32,0)"), ramp)
    assert distances[0] == pytest.approx(0.0)
    assert distances[-1] == pytest.approx(40.0)
    # The ramp's value is its column, counting from zero.
    assert values[0] == pytest.approx(9.0)
    assert values[-1] == pytest.approx(49.0)


def test_a_cut_works_along_a_plain_line(ramp):
    _distances, values = analysis.cut(_parse("line(10,32,50,32)"), ramp)
    assert values[-1] > values[0]


def test_a_circle_cannot_be_cut(ramp):
    with pytest.raises(analysis.AnalysisError, match="needs a line"):
        analysis.cut(_parse("circle(32,32,10)"), ramp)


def test_a_depth_profile_has_a_point_per_slice():
    cube = np.stack([np.full((32, 32), value, dtype=np.float32) for value in (1, 2, 3, 4)])
    slices, totals = analysis.depth_profile(_parse("circle(16,16,5)"), cube)
    assert slices == [1, 2, 3, 4]
    assert totals[1] == pytest.approx(totals[0] * 2)


def test_a_depth_profile_needs_a_cube(ramp):
    with pytest.raises(analysis.AnalysisError, match="cube"):
        analysis.depth_profile(_parse("circle(32,32,5)"), ramp)


# -- histogram -----------------------------------------------------------------------------


def test_a_histogram_counts_every_pixel_inside(flat):
    _centres, counts = analysis.histogram(_parse("circle(32,32,10)"), flat, bins=10)
    (measured,) = analysis.statistics(_parse("circle(32,32,10)"), flat)
    assert int(counts.sum()) == measured.npix


def test_a_histogram_of_nothing_says_so(flat):
    with pytest.raises(analysis.AnalysisError, match="no pixels"):
        analysis.histogram(_parse("circle(500,500,5)"), flat)


# -- which shapes get which entries ------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("circle(1,2,3)", ("statistics", "histogram", "plot3d")),
        ("annulus(1,2,3,4)", ("statistics", "histogram", "radial", "plot3d")),
        ("panda(1,2,0,360,4,2,8,1)", ("statistics", "histogram", "radial", "plot3d")),
        ("line(1,2,3,4)", ("plot2d",)),
        ("projection(1,2,3,4,0)", ("plot2d",)),
        ("point(1,2)", ()),
        ("text(1,2) # text={x}", ()),
    ],
)
def test_the_analysis_menu_matches_the_shape(text, expected):
    """A radial profile needs annuli, a cut needs a line; DS9 offers neither
    where they mean nothing rather than offering them and refusing."""
    assert analysis_commands_for(_parse(text)) == expected


def test_the_dialog_offers_exactly_those(qapp):
    dialog = RegionDialog(_parse("annulus(1,2,3,4)"))
    assert set(dialog.analysis_actions) == {"statistics", "histogram", "radial", "plot3d"}


def test_a_shape_with_no_analysis_has_none(qapp):
    assert RegionDialog(_parse("point(1,2)")).analysis_actions == {}


# -- the windows, and the Auto toggles (M6-26) -----------------------------------------------


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
    frame.image_data = np.ones((64, 64), dtype=np.float32)
    frame.original_image_data = frame.image_data
    frame.regions = RegionParser().parse_string("image\ncircle(32,32,10)\nprojection(10,32,50,32,0)\n")
    yield window
    for window_ in list(window.region._analysis.values()):
        window_.close()
    window.close()


def test_statistics_opens_a_window_with_ds9s_tables(main_window):
    region = main_window.frame_manager.current_frame.regions[0]
    main_window.region.open_analysis(region, "statistics")
    (opened,) = main_window.region._analysis.values()
    assert "surf_bri" in opened._text.toPlainText()


def test_asking_twice_reuses_the_window(main_window):
    region = main_window.frame_manager.current_frame.regions[0]
    main_window.region.open_analysis(region, "statistics")
    main_window.region.open_analysis(region, "statistics")
    assert len(main_window.region._analysis) == 1


def test_closing_a_window_forgets_it(main_window):
    region = main_window.frame_manager.current_frame.regions[0]
    main_window.region.open_analysis(region, "statistics")
    next(iter(main_window.region._analysis.values())).close()
    assert main_window.region._analysis == {}


@pytest.mark.parametrize("name", ["histogram", "plot3d"])
def test_the_plot_windows_open(main_window, name):
    region = main_window.frame_manager.current_frame.regions[0]
    main_window.region.open_analysis(region, name)
    assert len(main_window.region._analysis) == 1


def test_a_cut_window_opens_on_a_projection(main_window):
    projection = main_window.frame_manager.current_frame.regions[1]
    main_window.region.open_analysis(projection, "plot2d")
    assert len(main_window.region._analysis) == 1


def test_a_window_says_why_it_cannot_measure(main_window):
    """A 3D plot of a 2D image has no answer; it says so rather than crashing."""
    region = main_window.frame_manager.current_frame.regions[0]
    main_window.region.open_analysis(region, "plot3d")
    # The provider raises AnalysisError, which the window catches and draws.
    assert len(main_window.region._analysis) == 1


def test_moving_a_region_remeasures_its_windows(main_window):
    region = main_window.frame_manager.current_frame.regions[0]
    main_window.region.open_analysis(region, "statistics")
    window = next(iter(main_window.region._analysis.values()))
    before = window._text.toPlainText()

    region.radius = 3.0
    main_window.region.refresh_analysis(region)
    assert window._text.toPlainText() != before


def test_the_analysis_menu_on_the_dialog_opens_a_window(main_window):
    region = main_window.frame_manager.current_frame.regions[0]
    main_window.region.show_information(region)
    dialog = main_window.region._dialogs[id(region)]
    dialog.analysis_actions["statistics"].trigger()
    assert len(main_window.region._analysis) == 1
    dialog.close()


def test_an_auto_toggle_opens_a_window_for_a_new_region(main_window):
    from PyQt6.QtCore import QPointF

    from ncrads9.ui.widgets.region_overlay import RegionMode

    main_window.menu_bar.region_auto_actions["statistics"].setChecked(True)
    overlay = main_window.image_viewer.region_overlay
    overlay._finalize(RegionMode.CIRCLE, [QPointF(20, 20), QPointF(30, 20)])
    assert len(main_window.region._analysis) == 1


def test_without_the_toggle_a_new_region_opens_nothing(main_window):
    from PyQt6.QtCore import QPointF

    from ncrads9.ui.widgets.region_overlay import RegionMode

    overlay = main_window.image_viewer.region_overlay
    overlay._finalize(RegionMode.CIRCLE, [QPointF(20, 20), QPointF(30, 20)])
    assert main_window.region._analysis == {}


def test_an_auto_toggle_only_opens_what_the_shape_supports(main_window):
    """A projection has no statistics window to open."""
    main_window.region.select_none()
    main_window.frame_manager.current_frame.regions[1].selected = True
    main_window.menu_bar.region_auto_actions["statistics"].setChecked(True)
    assert main_window.region._analysis == {}


def test_turning_a_toggle_on_opens_for_what_is_selected(main_window):
    main_window.frame_manager.current_frame.regions[0].selected = True
    main_window.menu_bar.region_auto_actions["statistics"].setChecked(True)
    assert len(main_window.region._analysis) == 1
