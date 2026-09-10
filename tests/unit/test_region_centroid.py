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

"""Region -> Centroid, and its parameters (M6-20)."""

from __future__ import annotations

import numpy as np
import pytest

from ncrads9.analysis.centroid import (
    DEFAULT_ITERATIONS,
    DEFAULT_RADIUS,
    centroid_at,
)
from ncrads9.regions.region_parser import RegionParser
from ncrads9.ui.dialogs.centroid_dialog import CentroidDialog


def _gaussian(width: int, x: float, y: float, sigma: float = 2.0) -> np.ndarray:
    """An image with one round source at (x, y), in 1-based image pixels."""
    rows, columns = np.indices((width, width))
    return np.exp(-(((columns - (x - 1)) ** 2 + (rows - (y - 1)) ** 2) / (2 * sigma**2))).astype(np.float32)


# -- the algorithm ---------------------------------------------------------------


def test_the_defaults_are_ds9s():
    """`ds9/library/marker.tcl:28`."""
    assert (DEFAULT_ITERATIONS, DEFAULT_RADIUS) == (30, 10.0)


def test_a_position_on_a_source_stays_on_it():
    data = _gaussian(64, 32, 40)
    assert centroid_at(data, 32, 40) == pytest.approx((32.0, 40.0), abs=0.05)


def test_a_position_near_a_source_walks_onto_it():
    data = _gaussian(64, 32, 40)
    assert centroid_at(data, 28, 36) == pytest.approx((32.0, 40.0), abs=0.2)


def test_a_position_over_nothing_does_not_move():
    """Empty sky has nothing to be drawn towards; drifting would be worse."""
    data = np.zeros((64, 64), dtype=np.float32)
    assert centroid_at(data, 20, 20) == (20.0, 20.0)


def test_nans_are_skipped():
    data = _gaussian(64, 32, 40)
    data[30:34, 20:24] = np.nan
    assert centroid_at(data, 30, 38) == pytest.approx((32.0, 40.0), abs=0.3)


def test_a_source_at_the_edge_does_not_walk_off_the_image():
    data = _gaussian(64, 2, 2)
    x, y = centroid_at(data, 4, 4)
    assert 1 <= x <= 64 and 1 <= y <= 64


def test_a_bigger_radius_reaches_a_further_source():
    data = _gaussian(64, 32, 32, sigma=1.0)
    near = centroid_at(data, 20, 32, radius=4, iterations=1)
    far = centroid_at(data, 20, 32, radius=20, iterations=1)
    assert abs(far[0] - 32) < abs(near[0] - 32)


def test_one_pass_is_not_thirty():
    data = _gaussian(64, 32, 32, sigma=1.5)
    once = centroid_at(data, 22, 32, radius=8, iterations=1)
    many = centroid_at(data, 22, 32, radius=8, iterations=30)
    assert abs(many[0] - 32) < abs(once[0] - 32)


# -- the dialog --------------------------------------------------------------------


def test_the_dialog_shows_and_returns_the_settings(qapp):
    dialog = CentroidDialog(radius=7.5, iterations=12)
    assert dialog.values() == (7.5, 12)
    dialog._radius.setValue(3.0)
    dialog._iterations.setValue(5)
    assert dialog.values() == (3.0, 5)


# -- through the menu ----------------------------------------------------------------


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
    frame.image_data = _gaussian(64, 32, 40)
    frame.original_image_data = frame.image_data
    frame.regions = RegionParser().parse_string("image\ncircle(28,36,5)\n")
    yield window
    window.close()


def test_centroid_moves_the_selected_region_onto_the_source(main_window):
    region = main_window.frame_manager.current_frame.regions[0]
    region.selected = True
    main_window.menu_bar.action_region_centroid.trigger()
    assert region.center == pytest.approx((32.0, 40.0), abs=0.3)


def test_centroid_with_nothing_selected_says_so(main_window):
    """Moving every region because none was chosen is not what anyone meant."""
    region = main_window.frame_manager.current_frame.regions[0]
    main_window.menu_bar.action_region_centroid.trigger()
    assert region.center == (28.0, 36.0)
    assert "Select a region" in main_window.status_bar.currentMessage()


def test_a_region_that_cannot_move_is_left_alone(main_window):
    region = main_window.frame_manager.current_frame.regions[0]
    region.selected = True
    region.can_move = False
    main_window.menu_bar.action_region_centroid.trigger()
    assert region.center == (28.0, 36.0)


def test_the_parameters_dialog_changes_what_centroid_uses(main_window, monkeypatch):
    from ncrads9.ui.controllers import region as region_module

    class Chosen:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def values(self):
            return (4.0, 3)

    monkeypatch.setattr(region_module, "CentroidDialog", Chosen)
    main_window.menu_bar.action_region_centroid_params.trigger()
    assert main_window.region.centroid_radius == 4.0
    assert main_window.region.centroid_iterations == 3


def test_auto_centroid_snaps_a_newly_drawn_region(main_window):
    from ncrads9.ui.widgets.region_overlay import RegionMode

    main_window.menu_bar.action_region_auto_centroid.setChecked(True)
    overlay = main_window.image_viewer.region_overlay
    overlay.mode = RegionMode.CIRCLE
    from PyQt6.QtCore import QPointF

    overlay._finalize(RegionMode.CIRCLE, [QPointF(28, 36), QPointF(38, 36)])
    drawn = main_window.frame_manager.current_frame.regions[-1]
    assert drawn.center == pytest.approx((32.0, 40.0), abs=0.3)


def test_without_auto_centroid_a_new_region_stays_put(main_window):
    from PyQt6.QtCore import QPointF

    from ncrads9.ui.widgets.region_overlay import RegionMode

    overlay = main_window.image_viewer.region_overlay
    overlay._finalize(RegionMode.CIRCLE, [QPointF(28, 36), QPointF(38, 36)])
    assert main_window.frame_manager.current_frame.regions[-1].center == (28.0, 36.0)


def test_show_text_reaches_the_renderer(main_window):
    overlay = main_window.image_viewer.region_overlay
    main_window.menu_bar.action_region_show_text.setChecked(False)
    assert overlay.renderer.show_labels is False
    main_window.menu_bar.action_region_show_text.setChecked(True)
    assert overlay.renderer.show_labels is True


def test_show_hides_the_overlay(main_window):
    overlay = main_window.image_viewer.region_overlay
    main_window.menu_bar.action_region_show.setChecked(False)
    assert overlay.isVisible() is False
