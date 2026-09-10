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

"""DS9's crop: the section of the data a frame displays (M9-2)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.frames.crop import CropRegion, blank_outside, section

SIZE = 100


def _header(scale: float = 0.001) -> fits.Header:
    return fits.Header(
        {
            "NAXIS": 2,
            "NAXIS1": SIZE,
            "NAXIS2": SIZE,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CRPIX1": SIZE / 2,
            "CRPIX2": SIZE / 2,
            "CRVAL1": 150.0,
            "CRVAL2": 2.0,
            "CDELT1": -scale,
            "CDELT2": scale,
        }
    )


# -- the rectangle -----------------------------------------------------------------


def test_any_two_opposite_corners_describe_the_same_crop():
    """A drag can start at any corner."""
    forwards = CropRegion(10.0, 20.0, 30.0, 40.0)
    backwards = CropRegion(30.0, 40.0, 10.0, 20.0)
    assert forwards == backwards
    assert forwards.x0 == 10.0 and forwards.x1 == 30.0


def test_a_crop_knows_its_centre_and_size():
    crop = CropRegion(10.0, 20.0, 30.0, 60.0)
    assert crop.center == (20.0, 40.0)
    assert (crop.width, crop.height) == (20.0, 40.0)


def test_a_centre_and_size_round_trip():
    """Which is how DS9's dialog describes a crop."""
    crop = CropRegion.from_center(50.0, 60.0, 20.0, 10.0)
    assert crop.center == (50.0, 60.0)
    assert (crop.width, crop.height) == (20.0, 10.0)


def test_the_whole_image_is_a_crop_that_hides_nothing():
    crop = CropRegion.whole((40, 60))
    assert crop == CropRegion(1.0, 1.0, 60.0, 40.0)
    assert crop.covers((40, 60))


def test_a_crop_is_clipped_to_the_image():
    """A drag can leave the image; the crop it leaves must not."""
    crop = CropRegion(-30.0, -10.0, 500.0, 400.0).clipped_to((40, 60))
    assert crop == CropRegion(1.0, 1.0, 60.0, 40.0)


def test_a_crop_of_almost_nothing_is_not_usable():
    assert CropRegion(10.0, 10.0, 10.5, 30.0).is_usable() is False
    assert CropRegion(10.0, 10.0, 30.0, 30.0).is_usable() is True


def test_a_bound_names_the_pixel_it_falls_in():
    """Pixel i counting from zero covers [i+0.5, i+1.5) in FITS coordinates,
    so a crop drawn across part of a pixel keeps that pixel."""
    rows, columns = CropRegion(2.0, 2.0, 4.0, 4.0).slices((10, 10))
    assert (columns.start, columns.stop) == (1, 4)
    assert (rows.start, rows.stop) == (1, 4)

    # 4.9 falls in pixel index 4, which covers [4.5, 5.5).
    rows, _ = CropRegion(2.0, 2.4, 4.0, 4.9).slices((10, 10))
    assert (rows.start, rows.stop) == (1, 5)


def test_a_crop_says_what_is_inside_it():
    crop = CropRegion(10.0, 10.0, 20.0, 20.0)
    assert crop.contains(15.0, 15.0)
    assert not crop.contains(15.0, 25.0)


# -- blanking ------------------------------------------------------------------------


def test_blanking_keeps_the_shape_and_the_coordinates():
    """DS9's crop leaves the pixel grid alone; only the values go."""
    data = np.arange(100.0).reshape(10, 10)
    blanked = blank_outside(data, CropRegion(2.0, 2.0, 4.0, 4.0))
    assert blanked.shape == data.shape
    assert np.isnan(blanked).sum() == 91
    assert blanked[2, 2] == data[2, 2]


def test_blanking_does_not_touch_the_frame_data():
    data = np.ones((10, 10))
    blank_outside(data, CropRegion(2.0, 2.0, 4.0, 4.0))
    assert np.isfinite(data).all()


def test_blanking_by_a_crop_that_hides_nothing_is_free():
    data = np.ones((10, 10))
    assert blank_outside(data, CropRegion.whole((10, 10))) is data
    assert blank_outside(data, None) is data


def test_blanking_an_integer_image_gives_something_that_can_hold_nan():
    """An int array cannot hold NaN, so the blanked copy must not be one."""
    data = np.arange(100, dtype=np.int16).reshape(10, 10)
    blanked = blank_outside(data, CropRegion(2.0, 2.0, 4.0, 4.0))
    assert np.isnan(blanked).any()


def test_the_section_is_just_the_cropped_pixels():
    data = np.arange(100.0).reshape(10, 10)
    assert section(data, CropRegion(2.0, 2.0, 4.0, 4.0)).shape == (3, 3)
    assert section(data, None) is data


# -- the controller --------------------------------------------------------------------


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
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32), header=_header()).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    yield window
    window.close()


def test_a_frame_starts_uncropped(main_window):
    assert main_window.crop.region() is None


def test_cropping_records_the_section(main_window):
    assert main_window.crop.crop_to(20.0, 30.0, 60.0, 70.0) is True
    assert main_window.crop.region() == CropRegion(20.0, 30.0, 60.0, 70.0)


def test_a_crop_reaches_the_displayed_data(main_window):
    """Which is the whole point: the pixels outside stop being drawn."""
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    frame = main_window.frame_manager.current_frame
    displayed = main_window.display.display_image_data(frame)
    assert np.isnan(displayed[0, 0])
    assert np.isfinite(displayed[25, 25])


def test_a_crop_does_not_change_the_data(main_window):
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    assert np.isfinite(main_window.frame_manager.current_frame.image_data).all()


def test_a_crop_is_clipped_to_the_image_and_a_whole_one_is_no_crop(main_window):
    main_window.crop.crop_to(-100.0, -100.0, 1000.0, 1000.0)
    assert main_window.crop.region() is None


def test_a_crop_of_two_pixels_is_refused(main_window):
    assert main_window.crop.crop_to(50.0, 50.0, 51.0, 51.0) is False
    assert "too small" in main_window.status_bar.currentMessage()


def test_resetting_shows_the_whole_image_again(main_window):
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    main_window.crop.reset()
    assert main_window.crop.region() is None
    assert "Crop reset" in main_window.status_bar.currentMessage()


def test_resetting_an_uncropped_frame_says_so(main_window):
    main_window.crop.reset()
    assert "not cropped" in main_window.status_bar.currentMessage()


def test_the_scale_limits_come_from_the_crop(main_window):
    """DS9's CROPSEC: the stretch should suit what is on the screen, not the
    data that is no longer displayed."""
    main_window.scale.set_limit_mode("minmax")
    whole = (main_window.z1, main_window.z2)

    main_window.crop.crop_to(1.0, 1.0, 10.0, 10.0)
    assert main_window.z2 < whole[1]
    # Data is row + column, zero-based, over a ten-pixel corner.
    assert main_window.z2 == pytest.approx(18.0)


def test_uncropping_gives_the_limits_back(main_window):
    main_window.scale.set_limit_mode("minmax")
    whole = (main_window.z1, main_window.z2)
    main_window.crop.crop_to(1.0, 1.0, 10.0, 10.0)
    main_window.crop.reset()
    assert (main_window.z1, main_window.z2) == pytest.approx(whole)


def test_the_crop_is_per_frame(main_window):
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    main_window.frame_controller.new_frame()
    assert main_window.crop.region() is None


def test_clearing_a_frame_uncrops_it(main_window):
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    main_window.frame_controller.reset_current()
    assert main_window.crop.region() is None


# -- blank pixels on screen --------------------------------------------------------------


def test_a_blank_pixel_is_painted_in_the_blank_colour(main_window):
    """A pixel with no value is not a pixel with the lowest value, which is
    all the colormap would make of it."""
    main_window.nan_color = "#ffffff"
    frame = main_window.frame_manager.current_frame
    frame.image_data = frame.image_data.copy()
    frame.image_data[0, 0] = np.nan

    rgb = main_window.display.render_frame_rgb(frame)
    assert tuple(rgb[0, 0]) == (255, 255, 255)
    assert tuple(rgb[50, 50]) != (255, 255, 255)


def test_the_blank_colour_is_a_preference(main_window):
    main_window.edit.apply_preferences({"nan_color": "#ff0000"}, persist=False)
    assert main_window.nan_color == "#ff0000"

    frame = main_window.frame_manager.current_frame
    frame.image_data = frame.image_data.copy()
    frame.image_data[0, 0] = np.nan
    rgb = main_window.display.render_frame_rgb(frame)
    assert tuple(rgb[0, 0]) == (255, 0, 0)


def test_a_nonsense_blank_colour_falls_back(main_window):
    main_window.nan_color = "not a colour"
    frame = main_window.frame_manager.current_frame
    frame.image_data = frame.image_data.copy()
    frame.image_data[0, 0] = np.nan
    rgb = main_window.display.render_frame_rgb(frame)
    assert tuple(rgb[0, 0]) == (255, 255, 255)


def test_the_cropped_out_area_is_blank_on_screen(main_window):
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    frame = main_window.frame_manager.current_frame
    rgb = main_window.display.render_frame_rgb(frame)
    assert tuple(rgb[0, 0]) == (255, 255, 255)


# -- across frames --------------------------------------------------------------------


def _second_frame(main_window, tmp_path, scale=0.001, name="other.fits"):
    path = tmp_path / name
    rows, columns = np.indices((SIZE, SIZE))
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32), header=_header(scale)).writeto(path)
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(path))
    main_window.frame_controller.first()
    return main_window.frame_manager.frames[1]


def test_match_crop_copies_the_crop(main_window, tmp_path):
    other = _second_frame(main_window, tmp_path)
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    main_window.menu_bar.action_match_crop_image.trigger()
    assert other.crop == CropRegion(20.0, 20.0, 40.0, 40.0)


def test_match_crop_does_not_move_the_other_frames_views(main_window, tmp_path):
    """It used to match pan and zoom, which is what Match -> Frame is for."""
    other = _second_frame(main_window, tmp_path)
    other.zoom = 3.0
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    main_window.menu_bar.action_match_crop_image.trigger()
    assert other.zoom == pytest.approx(3.0)


def test_match_crop_through_the_sky_lands_on_the_same_field(main_window, tmp_path):
    """Two frames of the same field at different scales have that patch of
    sky over different pixels."""
    other = _second_frame(main_window, tmp_path, scale=0.002)
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    main_window.menu_bar.action_match_crop_wcs.trigger()
    assert other.crop is not None
    # Half the scale, so half the pixel span.
    assert other.crop.width == pytest.approx(10.0, abs=1.0)


def test_match_crop_uncrops_the_others_too(main_window, tmp_path):
    other = _second_frame(main_window, tmp_path)
    other.crop = CropRegion(10.0, 10.0, 20.0, 20.0)
    main_window.menu_bar.action_match_crop_image.trigger()
    assert other.crop is None


def test_the_lock_crops_the_other_frames_as_you_drag(main_window, tmp_path):
    other = _second_frame(main_window, tmp_path)
    main_window.menu_bar.action_lock_crop_image.trigger()
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    assert other.crop == CropRegion(20.0, 20.0, 40.0, 40.0)


def test_turning_the_lock_off_leaves_the_frames_alone(main_window, tmp_path):
    other = _second_frame(main_window, tmp_path)
    main_window.menu_bar.action_lock_crop_none.trigger()
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    assert other.crop is None


def test_a_frame_without_data_is_not_cropped_by_the_lock(main_window, tmp_path):
    main_window.frame_controller.new_frame()
    main_window.frame_controller.first()
    main_window.crop.set_locked(True, "image")
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    assert main_window.frame_manager.frames[1].crop is None


# -- the dialog -------------------------------------------------------------------------


@pytest.fixture
def dialog(main_window):
    main_window.menu_bar.action_crop_parameters.trigger()
    made = main_window.crop._dialog
    assert made is not None
    yield made
    made.close()


def test_the_dialog_crops_to_a_typed_centre_and_size(dialog, main_window):
    dialog._center_x.setValue(50.0)
    dialog._center_y.setValue(50.0)
    dialog._width.setValue(20.0)
    dialog._height.setValue(10.0)
    dialog.apply_crop()
    assert main_window.crop.region() == CropRegion(40.0, 45.0, 60.0, 55.0)


def test_the_dialog_starts_on_the_whole_image(dialog):
    assert "Whole image" in dialog._summary.text()
    assert dialog._width.value() == pytest.approx(float(SIZE))


def test_the_dialog_reports_the_crop_it_has(dialog, main_window):
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    dialog.reload()
    assert "Cropped to 20 x 20" in dialog._summary.text()
    assert dialog._center_x.value() == pytest.approx(30.0)


def test_reloading_does_not_change_the_crop(dialog, main_window):
    """setValue emits, and a reload that emitted would crop to what it is
    reporting -- rounding the crop a little every time the dialog refreshed."""
    main_window.crop.crop_to(20.5, 20.5, 40.5, 40.5)
    dialog.reload()
    dialog.reload()
    assert main_window.crop.region() == CropRegion(20.5, 20.5, 40.5, 40.5)


def test_the_dialogs_reset_button_uncrops(dialog, main_window):
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    dialog.buttons["reset"].click()
    assert main_window.crop.region() is None


def test_the_dialog_follows_a_crop_made_by_dragging(dialog, main_window):
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    assert dialog._center_x.value() == pytest.approx(30.0)


def test_asking_for_the_dialog_twice_reuses_it(main_window):
    main_window.crop.show_dialog()
    first = main_window.crop._dialog
    main_window.crop.show_dialog()
    assert main_window.crop._dialog is first
    first.close()


def test_the_dialog_records_a_cube_slice_range(dialog, main_window):
    """DS9's `crop 3d`. Nothing clips a slice out until the 3D frame arrives
    in M9-21, so this only has to be remembered and reported."""
    dialog._z_low.setValue(3.0)
    dialog._z_high.setValue(7.0)
    dialog.apply_crop()
    assert main_window.frame_manager.current_frame.crop_z == (3.0, 7.0)

    dialog._z_low.setValue(0.0)
    dialog._z_high.setValue(0.0)
    dialog.apply_crop()
    assert main_window.frame_manager.current_frame.crop_z is None


def test_applying_the_dialog_keeps_both_rows(dialog, main_window):
    """Applying refills the dialog from the frame, so a row read after the
    first was applied read the refilled value instead of the typed one."""
    dialog._center_x.setValue(50.0)
    dialog._center_y.setValue(50.0)
    dialog._width.setValue(20.0)
    dialog._height.setValue(20.0)
    dialog._z_low.setValue(2.0)
    dialog._z_high.setValue(5.0)
    dialog.apply_crop()

    frame = main_window.frame_manager.current_frame
    assert frame.crop == CropRegion(40.0, 40.0, 60.0, 60.0)
    assert frame.crop_z == (2.0, 5.0)
