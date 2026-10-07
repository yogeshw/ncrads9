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

"""DS9's CoordMenuButton and DistMenuButton on Crop, Crosshair and Cube."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.coordinates import positions
from ncrads9.core.cube_handler import CubeHandler
from ncrads9.ui.widgets.coord_menu_button import CoordEntry, CoordMenuButton, DistMenuButton

SIZE = 100
#: Degrees per pixel of the test image.
SCALE = 0.001


def _header() -> fits.Header:
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
            "CDELT1": -SCALE,
            "CDELT2": SCALE,
            # An alternate WCS, A, twice the scale.
            "CTYPE1A": "RA---TAN",
            "CTYPE2A": "DEC--TAN",
            "CRPIX1A": SIZE / 2,
            "CRPIX2A": SIZE / 2,
            "CRVAL1A": 150.0,
            "CRVAL2A": 2.0,
            "CDELT1A": -2 * SCALE,
            "CDELT2A": 2 * SCALE,
            # A physical system offset by 10 pixels.
            "LTV1": 10.0,
            "LTV2": 10.0,
        }
    )


def _cube_header() -> fits.Header:
    header = fits.Header()
    header["CTYPE3"] = "VELO-LSR"
    header["CRVAL3"] = 1000.0
    header["CDELT3"] = 10.0
    header["CRPIX3"] = 1.0
    header["CUNIT3"] = "m/s"
    return header


def _window(qapp, monkeypatch, path):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    return window


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path):
    rows, columns = np.indices((SIZE, SIZE))
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32), header=_header()).writeto(path)
    window = _window(qapp, monkeypatch, path)
    yield window
    window.close()


@pytest.fixture
def cube_window(qapp, monkeypatch, tmp_path):
    path = tmp_path / "cube.fits"
    data = np.arange(6 * 20 * 30, dtype=np.float32).reshape(6, 20, 30)
    fits.PrimaryHDU(data=data, header=_cube_header()).writeto(path)
    window = _window(qapp, monkeypatch, path)
    yield window
    window.cube_dialog.close()
    window.close()


# -- the widgets ----------------------------------------------------------------------


def test_the_coord_menu_offers_ds9s_entries(qapp):
    button = CoordMenuButton()
    values = set(button.actions_by_value)
    assert {"wcs", "image", "physical", "amplifier", "detector"} <= values
    assert {f"wcs{letter}" for letter in "abcdefghijklmnopqrstuvwxyz"} <= values
    assert {"fk4", "fk5", "icrs", "galactic", "ecliptic", "degrees", "sexagesimal"} <= values
    assert button.system == "wcs"


def test_a_3d_coord_menu_offers_wcs_and_image_only(qapp):
    button = CoordMenuButton(other=2, sky=False, sky_format=False)
    assert "image" in button.actions_by_value
    assert "physical" not in button.actions_by_value
    assert "fk5" not in button.actions_by_value


def test_the_dist_menu_offers_angular_units(qapp):
    button = DistMenuButton()
    assert {"wcs", "wcsz", "image", "physical", "degrees", "arcmin", "arcsec"} <= set(button.actions_by_value)


def test_choosing_from_the_menu_changes_the_system_and_emits(qapp):
    button = CoordMenuButton()
    seen = []
    button.changed.connect(lambda: seen.append(button.system))
    button.actions_by_value["image"].trigger()
    assert button.system == "image" and seen == ["image"]
    assert button.text() == "image"
    button.actions_by_value["galactic"].trigger()
    assert button.sky == "galactic"


def test_the_face_reads_the_sky_frame_for_a_celestial_wcs(main_window):
    button = CoordMenuButton()
    button.adjust_to_frame(main_window.frame_manager.current_frame)
    assert button.text() == "fk5"
    distance = DistMenuButton()
    distance.adjust_to_frame(main_window.frame_manager.current_frame)
    distance.set_distance_format("arcsec")
    assert distance.text() == "arcsec"


def test_missing_wcs_letters_are_greyed_out(main_window):
    button = CoordMenuButton()
    button.adjust_to_frame(main_window.frame_manager.current_frame)
    assert button.actions_by_value["wcsa"].isEnabled()
    assert not button.actions_by_value["wcsb"].isEnabled()


def test_a_frame_without_wcs_falls_back_to_physical(qapp):
    class Bare:
        wcs_handler = None

        def wcs_for(self, key=""):
            return None

    button = CoordMenuButton()
    button.adjust_to_frame(Bare())
    assert button.system == "physical"
    assert not button.actions_by_value["wcs"].isEnabled()
    assert not button.actions_by_value["fk5"].isEnabled()


def test_a_coord_entry_reads_and_writes_numbers(qapp):
    entry = CoordEntry()
    entry.setValue(12.5)
    assert entry.text() == "12.5" and entry.value() == 12.5


# -- distances ------------------------------------------------------------------------


def test_a_wcs_distance_converts_through_the_pixel_scale(main_window):
    frame = main_window.frame_manager.current_frame
    width, height = positions.distance_from_image(frame, 20.0, 10.0, "wcs", "arcsec")
    assert width == pytest.approx(20 * SCALE * 3600)
    assert height == pytest.approx(10 * SCALE * 3600)
    back = positions.distance_to_image(frame, width, height, "wcs", "arcsec")
    assert back == pytest.approx((20.0, 10.0))
    # The alternate's pixels are twice as large.
    assert positions.distance_to_image(
        frame, 2 * SCALE * 60, 2 * SCALE * 60, "wcsa", "arcmin"
    ) == pytest.approx((1.0, 1.0))


# -- Crop Parameters ------------------------------------------------------------------


@pytest.fixture
def crop_dialog(main_window):
    main_window.crop.show_dialog()
    dialog = main_window.crop._dialog
    yield dialog
    dialog.close()


def test_the_crop_dialog_starts_in_wcs(crop_dialog):
    assert crop_dialog.center_system.system == "wcs"
    assert crop_dialog.size_system.system == "wcs"
    # The whole image's width, in degrees.
    assert crop_dialog._width.value() == pytest.approx(SIZE * SCALE)


def test_the_crop_dialog_crops_to_a_sky_centre_and_angular_size(crop_dialog, main_window):
    frame = main_window.frame_manager.current_frame
    ra, dec = positions.from_image(frame, 40.0, 60.0, "wcs").split()
    crop_dialog._center_x.setText(ra)
    crop_dialog._center_y.setText(dec)
    crop_dialog.size_system.set_distance_format("arcsec")
    crop_dialog._width.setValue(20 * SCALE * 3600)
    crop_dialog._height.setValue(10 * SCALE * 3600)
    assert crop_dialog.apply_crop() is True
    crop = main_window.crop.region()
    assert crop.center == pytest.approx((40.0, 60.0), abs=1e-2)
    assert (crop.width, crop.height) == pytest.approx((20.0, 10.0), abs=1e-2)


def test_the_crop_dialog_reads_sexagesimal(crop_dialog, main_window):
    frame = main_window.frame_manager.current_frame
    crop_dialog.center_system.set_sky_format("sexagesimal", notify=True)
    assert ":" in crop_dialog._center_x.text()
    ra, dec = positions.from_image(frame, 30.0, 30.0, "wcs", "fk5", "sexagesimal").split()
    crop_dialog._center_x.setText(ra)
    crop_dialog._center_y.setText(dec)
    crop_dialog.size_system.set_system("image")
    crop_dialog._width.setValue(10.0)
    crop_dialog._height.setValue(10.0)
    crop_dialog.apply_crop()
    assert main_window.crop.region().center == pytest.approx((30.0, 30.0), abs=1e-2)


def test_the_crop_dialog_speaks_physical(crop_dialog, main_window):
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    crop_dialog.center_system.set_system("physical", notify=True)
    # physical = image - LTV
    assert crop_dialog._center_x.value() == pytest.approx(30.0 - 10.0)
    crop_dialog._center_x.setValue(40.0)
    crop_dialog.size_system.set_system("physical")
    crop_dialog._width.setValue(20.0)
    crop_dialog._height.setValue(20.0)
    crop_dialog.apply_crop()
    assert main_window.crop.region().center[0] == pytest.approx(50.0)


def test_changing_the_menu_rewrites_the_current_crop(crop_dialog, main_window):
    main_window.crop.crop_to(20.0, 20.0, 40.0, 40.0)
    crop_dialog.size_system.actions_by_value["image"].trigger()
    assert crop_dialog._width.value() == pytest.approx(20.0)
    crop_dialog.size_system.actions_by_value["wcs"].trigger()
    crop_dialog.size_system.actions_by_value["arcmin"].trigger()
    assert crop_dialog._width.value() == pytest.approx(20 * SCALE * 60)


def test_the_crop_dialog_follows_a_crop_while_open(crop_dialog, main_window):
    crop_dialog.center_system.set_system("image", notify=True)
    main_window.crop.crop_to(10.0, 10.0, 30.0, 30.0)
    assert crop_dialog._center_x.value() == pytest.approx(20.0)


def test_unreadable_crop_entries_are_reported_not_applied(crop_dialog, main_window):
    crop_dialog._center_x.setText("nonsense")
    assert crop_dialog.apply_crop() is False
    assert "Cannot apply" in crop_dialog._summary.text()
    assert main_window.crop.region() is None


def test_the_crop_3d_row_takes_slice_world_values(cube_window):
    cube_window.crop.show_dialog()
    dialog = cube_window.crop._dialog
    assert dialog.range_system.system == "wcs"
    dialog._z_low.setValue(1020.0)
    dialog._z_high.setValue(1040.0)
    dialog.apply_crop()
    assert cube_window.frame_manager.current_frame.crop_z == pytest.approx((3.0, 5.0))
    dialog.range_system.set_system("image", notify=True)
    assert dialog._z_low.value() == pytest.approx(3.0)
    dialog.close()


def test_a_cube_without_slice_wcs_falls_back_to_image(qapp, monkeypatch, tmp_path):
    path = tmp_path / "plain.fits"
    fits.PrimaryHDU(data=np.zeros((4, 8, 8), dtype=np.float32)).writeto(path)
    window = _window(qapp, monkeypatch, path)
    window.crop.show_dialog()
    assert window.crop._dialog.range_system.system == "image"
    window.crop._dialog.close()
    window.close()


# -- Crosshair Parameters --------------------------------------------------------------


@pytest.fixture
def crosshair_dialog(main_window):
    main_window.crosshair.show_dialog()
    dialog = main_window.crosshair._dialog
    yield dialog
    dialog.close()


def test_the_crosshair_dialog_places_in_wcs(crosshair_dialog, main_window):
    frame = main_window.frame_manager.current_frame
    ra, dec = positions.from_image(frame, 33.0, 44.0, "wcs").split()
    crosshair_dialog._x.setText(ra)
    crosshair_dialog._y.setText(dec)
    assert crosshair_dialog.apply_position() is True
    assert main_window.crosshair.position() == pytest.approx((33.0, 44.0), abs=1e-2)


def test_the_crosshair_dialog_places_in_an_alternate_wcs(crosshair_dialog, main_window):
    frame = main_window.frame_manager.current_frame
    crosshair_dialog.system.set_system("wcsa", notify=True)
    ra, dec = positions.from_image(frame, 60.0, 20.0, "wcsa").split()
    crosshair_dialog._x.setText(ra)
    crosshair_dialog._y.setText(dec)
    crosshair_dialog.apply_position()
    assert main_window.crosshair.position() == pytest.approx((60.0, 20.0), abs=1e-2)


def test_the_crosshair_dialog_follows_the_crosshair(crosshair_dialog, main_window):
    crosshair_dialog.system.set_system("image", notify=True)
    main_window.crosshair.move_to(12.0, 34.0)
    assert crosshair_dialog._x.value() == pytest.approx(12.0)
    assert crosshair_dialog._y.value() == pytest.approx(34.0)
    crosshair_dialog.system.set_system("physical", notify=True)
    assert crosshair_dialog._x.value() == pytest.approx(2.0)


def test_the_crosshair_dialog_shows_galactic_sexagesimal(crosshair_dialog, main_window):
    main_window.crosshair.move_to(50.0, 50.0)
    crosshair_dialog.system.actions_by_value["galactic"].trigger()
    crosshair_dialog.system.actions_by_value["sexagesimal"].trigger()
    assert crosshair_dialog.system.text() == "galactic"
    assert ":" in crosshair_dialog._x.text()


# -- Cube ---------------------------------------------------------------------------------


def test_the_cube_handler_converts_world_values_to_slices():
    handler = CubeHandler(np.zeros((6, 4, 4)), _cube_header())
    assert handler.world_to_image_z(1020.0) == pytest.approx(3.0)
    assert handler.slice_from_world(1024.0) == 2
    assert handler.slice_from_world(99999.0) == 5
    assert handler.slice_from_world(-99999.0) == 0
    assert handler.slice_axis_name() == "VELO-LSR"
    assert handler.slice_from_world(1000.0, key="A") is None


def test_the_cube_dialog_jumps_to_a_typed_world_value(cube_window):
    cube_window.frame_controller.show_cube_dialog()
    dialog = cube_window.cube_dialog
    assert dialog.coord_system == "wcs"
    assert dialog._wcs_entry.text() == "1000"
    assert dialog._axis_label.text() == "VELO-LSR"
    dialog._wcs_entry.setText("1031")
    dialog._wcs_entry.returnPressed.emit()
    frame = cube_window.frame_manager.current_frame
    assert frame.slice_index == 3
    assert dialog.slice_index == 3
    assert dialog._wcs_entry.text() == "1030"


def test_the_cube_dialog_coordinate_menu_offers_image(cube_window):
    cube_window.frame_controller.show_cube_dialog()
    dialog = cube_window.cube_dialog
    assert not dialog.system_button.actions_by_value["wcsa"].isEnabled()
    dialog.system_button.actions_by_value["image"].trigger()
    assert dialog._axis_label.text() == "image"
    assert cube_window.frame_controller.goto_cube_coordinate("5") is True
    assert cube_window.frame_manager.current_frame.slice_index == 4
    assert dialog._wcs_entry.text() == "5"


def test_a_nonsense_cube_coordinate_is_refused(cube_window):
    cube_window.frame_controller.show_cube_dialog()
    assert cube_window.frame_controller.goto_cube_coordinate("abc") is False
    assert cube_window.frame_manager.current_frame.slice_index == 0
