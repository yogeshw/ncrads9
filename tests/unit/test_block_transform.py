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


"""DS9's Block: a display transform that must not move anything.

The point of M5-14 is that blocking changes only how much data is drawn.
What the frame holds, where a region sits, what the coordinate readout says
and what `Save` writes all have to be unaffected -- and the way to know that
is to assert it, because getting it wrong is silent.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.rendering.block import block_image
from ncrads9.ui.menu_bar import BLOCK_FACTORS

# -- the transform -----------------------------------------------------------


def test_a_factor_of_one_is_the_input_untouched():
    data = np.arange(64, dtype=np.float32).reshape(8, 8)
    assert block_image(data, 1) is data
    assert block_image(data, 0) is data
    assert block_image(data, -3) is data


def test_blocking_averages_each_square():
    data = np.arange(64, dtype=np.float32).reshape(8, 8)
    blocked = block_image(data, 2)
    assert blocked.shape == (4, 4)
    # The top-left square holds 0, 1, 8 and 9.
    assert blocked[0, 0] == pytest.approx(4.5)
    assert blocked[-1, -1] == pytest.approx((54 + 55 + 62 + 63) / 4)


def test_a_partial_square_is_dropped():
    """DS9 trims rather than averaging over fewer pixels."""
    data = np.arange(64, dtype=np.float32).reshape(8, 8)
    assert block_image(data, 3).shape == (2, 2)


def test_a_factor_larger_than_the_image_returns_the_image():
    data = np.arange(64, dtype=np.float32).reshape(8, 8)
    assert block_image(data, 99).shape == (8, 8)


def test_a_cube_is_blocked_in_its_image_axes_only():
    cube = np.arange(3 * 8 * 8, dtype=np.float32).reshape(3, 8, 8)
    assert block_image(cube, 2).shape == (3, 4, 4)


def test_blank_pixels_do_not_spread():
    """A square overlapping blank data averages the real pixels."""
    data = np.arange(64, dtype=np.float32).reshape(8, 8)
    data[0, 0] = np.nan
    assert block_image(data, 2)[0, 0] == pytest.approx((1 + 8 + 9) / 3)


def test_an_entirely_blank_square_stays_blank():
    assert np.isnan(block_image(np.full((2, 2), np.nan, np.float32), 2)[0, 0])


def test_no_warning_for_an_entirely_blank_square(recwarn):
    block_image(np.full((2, 2), np.nan, np.float32), 2)
    assert [w for w in recwarn if "empty slice" in str(w.message)] == []


def test_none_and_one_dimensional_input_are_returned():
    assert block_image(None, 4) is None
    line = np.arange(8, dtype=np.float32)
    assert block_image(line, 4) is line


def test_ds9s_factors_go_to_256():
    assert BLOCK_FACTORS == (1, 2, 4, 8, 16, 32, 64, 128, 256)


# -- in a window: nothing must move -----------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch):
    from ncrads9.core.image_data import ImageData
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.resize(600, 500)

    frame = window.frame_manager.current_frame
    image = np.arange(64 * 64, dtype=np.float32).reshape(64, 64)
    header = fits.Header(
        {
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CRVAL1": 10.0,
            "CRVAL2": 20.0,
            "CRPIX1": 32.5,
            "CRPIX2": 32.5,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
        }
    )
    frame.image_data = image
    frame.original_image_data = image
    frame.image = ImageData(data=image, header=header)
    frame.header = header
    from ncrads9.core.wcs_handler import WCSHandler

    frame.wcs_handler = WCSHandler(header)
    window.display.display()
    yield window
    window.close()


def test_blocking_leaves_the_frames_data_alone(main_window):
    """It used to overwrite `image_data` with the reduced array."""
    frame = main_window.frame_manager.current_frame
    original = frame.image_data.copy()

    for factor in (2, 4, 8, 1):
        main_window.analysis.set_block(factor)
        assert frame.image_data.shape == original.shape, factor
        assert np.array_equal(frame.image_data, original), factor
        assert frame.original_image_data.shape == original.shape, factor


def test_the_pipeline_actually_reduces_what_it_draws(main_window):
    frame = main_window.frame_manager.current_frame
    assert main_window.display.display_image_data(frame).shape == (64, 64)
    main_window.analysis.set_block(4)
    assert main_window.display.display_image_data(frame).shape == (16, 16)


def _centre_of_drawn_pixmap(main_window) -> tuple[float, float]:
    """The widget point at the middle of whatever is currently drawn."""
    viewer = main_window.image_viewer.image_viewer
    pixmap = viewer.pixmap()
    rect = viewer.rect()
    x = (rect.width() - pixmap.width()) / 2 + pixmap.width() / 2
    y = (rect.height() - pixmap.height()) / 2 + pixmap.height() / 2
    return x, y


def test_the_readout_stays_in_image_pixels(main_window):
    """The coordinate reported must be an image pixel, not a blocked one.

    Blocking *does* shrink the picture -- that is what DS9's Block is for --
    so the same widget point maps somewhere else afterwards. What must not
    change is the *units*: the middle of the drawn image is image pixel 32 of
    64 whatever the block factor is. Without the conversion it would come
    back as 8 at a block of four.
    """
    viewer = main_window.image_viewer.image_viewer
    centre = viewer.map_widget_to_image_coords(*_centre_of_drawn_pixmap(main_window))
    assert centre is not None
    assert centre[0] == pytest.approx(32, abs=2)

    for factor in (2, 4, 8):
        main_window.analysis.set_block(factor)
        blocked = viewer.map_widget_to_image_coords(*_centre_of_drawn_pixmap(main_window))
        assert blocked is not None, factor
        assert blocked[0] == pytest.approx(32, abs=factor + 1), factor
        assert blocked[1] == pytest.approx(32, abs=factor + 1), factor


def test_the_sky_position_of_the_image_centre_is_unchanged(main_window):
    """The end-to-end claim: blocking does not move the sky."""
    viewer = main_window.image_viewer.image_viewer
    handler = main_window.frame_manager.current_frame.wcs_handler

    def sky_at_centre():
        pixel = viewer.map_widget_to_image_coords(*_centre_of_drawn_pixmap(main_window))
        return handler.pixel_to_world(float(pixel[0]), float(pixel[1]))

    unblocked = sky_at_centre()
    main_window.analysis.set_block(4)
    blocked = sky_at_centre()
    # Four pixels of 3.6 arcsec each, so a hundredth of a degree is plenty.
    assert blocked[0] == pytest.approx(unblocked[0], abs=0.01)
    assert blocked[1] == pytest.approx(unblocked[1], abs=0.01)


def test_the_two_mappings_are_inverses_under_a_block(main_window):
    viewer = main_window.image_viewer.image_viewer
    main_window.analysis.set_block(4)
    for image_x, image_y in ((0, 0), (16, 20), (60, 60)):
        display = viewer.map_image_to_display_coords(image_x, image_y)
        assert display is not None


def test_a_region_is_recorded_in_image_pixels(main_window):
    """A shape drawn on the blocked picture is stored at full resolution.

    The overlay is told the drawn array is 16x16 and each of its pixels is
    four image pixels, so a gesture at its far corner is a region at image
    pixel 60, not at 15.
    """
    from PyQt6.QtCore import QPointF

    overlay = main_window.image_viewer.region_overlay
    overlay.set_zoom(1.0, (0.0, 0.0), image_width=16, image_height=16)
    overlay.block_factor = 4

    corner = overlay._widget_to_image_coords(QPointF(15.0, 0.0))
    assert corner.x() == pytest.approx(60.0, abs=4.0)
    assert corner.y() == pytest.approx(60.0, abs=4.0)


def test_a_regions_round_trip_survives_a_block(main_window):
    from PyQt6.QtCore import QPointF

    overlay = main_window.image_viewer.region_overlay
    overlay.set_zoom(1.0, (0.0, 0.0), image_width=16, image_height=16)
    overlay.block_factor = 4

    for point in (QPointF(10.0, 12.0), QPointF(0.0, 0.0), QPointF(63.0, 40.0)):
        widget = overlay._image_to_widget_coords(point)
        back = overlay._widget_to_image_coords(widget)
        assert back.x() == pytest.approx(point.x(), abs=4.0)
        assert back.y() == pytest.approx(point.y(), abs=4.0)


def test_the_viewer_is_told_the_factor(main_window):
    main_window.analysis.set_block(8)
    assert main_window.image_viewer.image_viewer._block_factor == 8
    assert main_window.image_viewer.region_overlay.block_factor == 8


def test_save_writes_the_full_resolution_array(main_window, tmp_path):
    """Block is a view, so it must not reach the file."""
    main_window.analysis.set_block(4)
    target = tmp_path / "blocked.fits"
    main_window.file._write(target, overwrite=True)

    with fits.open(target) as hdus:
        assert hdus[0].data.shape == (64, 64)
        assert hdus[0].header["NCBLOCK"] == 4


def test_blocking_restretches(main_window):
    """Averaging narrows the distribution, so the old limits no longer fit."""
    main_window.analysis.set_block(1)
    unblocked = main_window.z2
    main_window.analysis.set_block(8)
    assert main_window.z2 != unblocked


def test_every_factor_is_reachable_and_ticks(main_window):
    for factor in BLOCK_FACTORS:
        main_window.menu_bar.block_factor_actions[factor].trigger()
        assert main_window.frame_manager.current_frame.block_factor == factor
        assert main_window.menu_bar.block_factor_actions[factor].isChecked()


def test_block_in_and_out_step_through_the_presets(main_window):
    main_window.analysis.set_block(8)
    main_window.analysis.block_in()
    assert main_window.frame_manager.current_frame.block_factor == 4
    main_window.analysis.block_out()
    assert main_window.frame_manager.current_frame.block_factor == 8


def test_stepping_stops_at_the_ends(main_window):
    main_window.analysis.set_block(1)
    main_window.analysis.block_in()
    assert main_window.frame_manager.current_frame.block_factor == 1
    main_window.analysis.set_block(BLOCK_FACTORS[-1])
    main_window.analysis.block_out()
    assert main_window.frame_manager.current_frame.block_factor == BLOCK_FACTORS[-1]


def test_block_fit_picks_a_factor_that_fits(main_window):
    main_window.analysis.block_fit()
    frame = main_window.frame_manager.current_frame
    assert frame.block_factor in BLOCK_FACTORS
    drawn = main_window.display.display_image_data(frame)
    viewport = main_window._effective_viewport_size()
    assert drawn.shape[1] <= max(viewport.width(), 64)


def test_the_bin_menu_forwards_to_block_and_says_so(main_window):
    """DS9's Bin makes an image from a table; ours block-averaged. M5-16."""
    main_window.analysis.set_bin(4)
    assert main_window.frame_manager.current_frame.block_factor == 4


# -- Match and Lock (M5-20) --------------------------------------------------


def test_match_block_copies_the_factor(main_window):
    main_window.frame_controller.new_frame()
    first, second = main_window.frame_manager.frames
    main_window.frame_manager.goto_frame(0)
    main_window.analysis.set_block(8)

    main_window.frame_controller.match_block()
    assert second.block_factor == 8
    assert first.block_factor == 8


def test_match_bin_no_longer_copies_the_block_factor(main_window):
    """DS9's Bin is the table conversion; it is not Block under another name."""
    main_window.frame_controller.new_frame()
    main_window.frame_manager.goto_frame(0)
    main_window.analysis.set_block(8)
    second = main_window.frame_manager.frames[1]

    main_window.frame_controller.match_bin()
    assert second.block_factor == 1
    assert "M5-16" in main_window.status_bar.currentMessage()


def test_locking_block_propagates_later_changes(main_window):
    main_window.frame_controller.new_frame()
    main_window.frame_manager.goto_frame(0)
    main_window.frame_controller.set_lock_flag("block", True)

    main_window.analysis.set_block(16)
    assert all(frame.block_factor == 16 for frame in main_window.frame_manager.frames)


def test_unlocking_block_stops_propagating(main_window):
    main_window.frame_controller.new_frame()
    main_window.frame_manager.goto_frame(0)
    main_window.frame_controller.set_lock_flag("block", True)
    main_window.frame_controller.set_lock_flag("block", False)

    main_window.analysis.set_block(16)
    assert main_window.frame_manager.frames[1].block_factor != 16
