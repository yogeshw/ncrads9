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

"""The horizontal and vertical cut graphs, and DS9's `graph` settings (M9-25).

Before this the two panels read a single row or column and drew it with no
settings at all, so `xpaset ds9 graph thickness 10` had nothing to set.
"""

from __future__ import annotations

import numpy as np
import pytest

from ncrads9.analysis.cut_graph import (
    DEFAULT_SIZE,
    MAXIMUM_SIZE,
    MAXIMUM_THICKNESS,
    MINIMUM_SIZE,
    GraphSettings,
    cut,
    limits,
    scaled,
)


@pytest.fixture
def image():
    """A 4x5 image whose value is `10 * row + column`, so a cut can be read
    off by eye and a mistaken axis is obvious."""
    rows, columns = np.indices((4, 5))
    return (rows * 10 + columns).astype(float)


# -- the cut itself ---------------------------------------------------------------


def test_a_thin_cut_is_the_row_or_column_asked_for(image):
    assert list(cut(image, "horizontal", 2)) == [20, 21, 22, 23, 24]
    assert list(cut(image, "vertical", 3)) == [3, 13, 23, 33]


def test_a_cut_off_the_image_is_none(image):
    assert cut(image, "horizontal", 4) is None
    assert cut(image, "horizontal", -1) is None
    assert cut(image, "vertical", 5) is None


def test_no_image_is_none():
    assert cut(None, "horizontal", 0) is None
    assert cut(np.arange(5, dtype=float), "horizontal", 0) is None


def test_a_thick_cut_averages_across_its_width(image):
    """DS9's default method. Rows 1, 2 and 3 at column 0 are 10, 20, 30."""
    values = cut(image, "horizontal", 2, GraphSettings(thickness=3))
    assert list(values) == [20, 21, 22, 23, 24]


def test_a_thick_cut_can_be_summed_instead(image):
    values = cut(image, "horizontal", 2, GraphSettings(thickness=3, method="sum"))
    assert list(values) == [60, 63, 66, 69, 72]


def test_a_thick_cut_at_the_edge_stays_on_the_image(image):
    """A band centred on row 0 would run off the top; DS9 slides it back
    rather than returning a shorter cut."""
    values = cut(image, "horizontal", 0, GraphSettings(thickness=3, method="sum"))
    assert list(values) == [30, 33, 36, 39, 42]  # rows 0, 1 and 2
    assert len(values) == image.shape[1]


def test_a_cut_thicker_than_the_image_is_the_whole_image(image):
    values = cut(image, "vertical", 2, GraphSettings(thickness=99, method="sum"))
    # Every column summed, per row: 0+1+2+3+4, then 10+11+...+14, and so on.
    assert list(values) == [10, 60, 110, 160]


def test_a_thick_cut_ignores_blanks(image):
    """A NaN in the band should not wipe out the column it is in."""
    image[1, 2] = np.nan
    values = cut(image, "horizontal", 1, GraphSettings(thickness=3))
    assert values[2] == pytest.approx((2 + 22) / 2)
    assert not np.isnan(values[0])


def test_a_band_of_nothing_but_blanks_stays_blank(image):
    image[:, 1] = np.nan
    values = cut(image, "horizontal", 1, GraphSettings(thickness=3))
    assert np.isnan(values[1])
    assert not np.isnan(values[0])


def test_the_thickness_is_clamped_to_what_is_allowed():
    assert GraphSettings().with_thickness(0).thickness == 1
    assert GraphSettings().with_thickness(-5).thickness == 1
    assert GraphSettings().with_thickness(10_000).thickness == MAXIMUM_THICKNESS


def test_the_size_is_clamped_to_what_is_allowed():
    assert GraphSettings().size == DEFAULT_SIZE
    assert GraphSettings().with_size(1).size == MINIMUM_SIZE
    assert GraphSettings().with_size(10_000).size == MAXIMUM_SIZE


# -- the value axis ---------------------------------------------------------------


def test_limits_are_the_range_of_the_finite_values():
    assert limits(np.array([3.0, np.nan, 7.0, np.inf])) == (3.0, 7.0)


def test_a_flat_cut_still_has_a_range():
    """Nothing may divide by zero, however flat the data."""
    low, high = limits(np.array([5.0, 5.0, 5.0]))
    assert high > low


def test_a_cut_of_nothing_has_a_default_range():
    assert limits(np.array([np.nan, np.nan])) == (0.0, 1.0)


def test_a_log_axis_measures_the_logarithms():
    assert limits(np.array([1.0, 10.0, 100.0]), log=True) == (0.0, 2.0)


def test_a_log_axis_ignores_what_it_cannot_show():
    """A zero or a negative value has no logarithm; it must not drag the
    range down to something that cannot be drawn."""
    assert limits(np.array([0.0, -5.0, 1.0, 100.0]), log=True) == (0.0, 2.0)


def test_scaling_maps_a_cut_onto_zero_to_one():
    assert list(scaled(np.array([0.0, 5.0, 10.0]))) == [0.0, 0.5, 1.0]


def test_scaling_a_log_axis_spaces_the_decades_evenly():
    assert list(scaled(np.array([1.0, 10.0, 100.0]), log=True)) == [0.0, 0.5, 1.0]


def test_a_value_the_axis_cannot_show_comes_back_blank():
    """Drawn as a gap in the curve, which is the honest picture; drawn as
    zero it would look like a real measurement."""
    values = scaled(np.array([1.0, 0.0, -3.0, 100.0]), log=True)
    assert values[0] == 0.0
    assert np.isnan(values[1])
    assert np.isnan(values[2])
    assert values[3] == 1.0


def test_a_blank_stays_blank_on_a_linear_axis():
    assert np.isnan(scaled(np.array([1.0, np.nan, 3.0]))[1])


# -- the panels -------------------------------------------------------------------


@pytest.fixture
def panels(qapp):
    from ncrads9.ui.panels.horizontal_graph import HorizontalGraph
    from ncrads9.ui.panels.vertical_graph import VerticalGraph

    made = (HorizontalGraph(), VerticalGraph())
    yield made
    for panel in made:
        panel.close()


def test_both_panels_take_ds9s_settings(panels):
    for panel in panels:
        panel.set_grid(True)
        panel.set_log(True)
        panel.set_method("sum")
        panel.set_thickness(5)
        panel.set_size(220)
        assert panel.settings.grid is True
        assert panel.settings.log is True
        assert panel.settings.method == "sum"
        assert panel.settings.thickness == 5
        assert panel.settings.size == 220
        # The drawing widget reads the same object, not a copy of it.
        assert panel._graph_widget.settings is panel.settings


def test_a_method_that_is_neither_is_refused(panels):
    for panel in panels:
        with pytest.raises(ValueError, match="averaged or summed"):
            panel.set_method("median")


def test_the_size_sets_the_across_the_cut_dimension(panels):
    horizontal, vertical = panels
    horizontal.set_size(180)
    vertical.set_size(180)
    assert horizontal.height() == 180
    assert vertical.width() == 180


def test_a_panel_cuts_where_the_cursor_is(panels, image):
    horizontal, vertical = panels
    for panel in panels:
        panel.set_image(image)
    horizontal.update_cursor_position(1, 2)
    assert list(horizontal._graph_widget._data) == [20, 21, 22, 23, 24]
    vertical.update_cursor_position(3, 1)
    assert list(vertical._graph_widget._data) == [3, 13, 23, 33]


def test_a_panel_says_when_the_cursor_is_off_the_image(panels, image):
    horizontal, _vertical = panels
    horizontal.set_image(image)
    horizontal.update_cursor_position(1, 99)
    assert horizontal._info_label.text() == "Y: ---"


def test_a_panel_re_cuts_when_the_thickness_changes(panels, image):
    """Without this the new setting would not show until the pointer moved
    again, which looks like the setting did nothing."""
    horizontal, _vertical = panels
    horizontal.set_image(image)
    horizontal.update_cursor_position(1, 2)
    horizontal.set_method("sum")
    horizontal.set_thickness(3)
    assert list(horizontal._graph_widget._data) == [60, 63, 66, 69, 72]
    assert "3 sum" in horizontal._info_label.text()


def test_a_panel_with_no_image_does_nothing(panels):
    horizontal, _vertical = panels
    horizontal.update_cursor_position(1, 1)
    assert horizontal._graph_widget._data is None


def test_the_panels_paint_with_every_setting_on(panels, image):
    """A grid on a log axis with a thick cut is the combination that draws
    the most, and a painter that throws takes the window with it."""
    from PyQt6.QtGui import QPixmap

    for panel in panels:
        panel.set_image(image)
        panel.set_grid(True)
        panel.set_log(True)
        panel.set_thickness(3)
        panel.update_cursor_position(1, 2)
        panel.resize(300, 200)
        panel._graph_widget.render(QPixmap(300, 200))


def test_a_panel_paints_with_nothing_in_it(panels):
    from PyQt6.QtGui import QPixmap

    for panel in panels:
        panel._graph_widget.render(QPixmap(100, 100))
