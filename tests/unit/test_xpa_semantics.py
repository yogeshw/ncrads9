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
What the table's XPA points *do*, not just that they answer.

`test_xpa_conformance` runs DS9's fifteen hundred examples and checks only
that nothing raises and that the number answered ok does not fall. That
cannot see a point that says ok and changes nothing, or a read that answers
the wrong thing -- `crosshair 345 58.8 wcs fk5` putting the crosshair at
pixel (345, 58.8), `xpaget ds9 minmax interval` answering the whole
listing, `regions -system wcs` writing pixels under a `wcs` header. Each
test here sets something the DS9 way, then reads it back both through
`xpaget` and from the application itself.

The image is 64 x 64 with a TAN WCS whose reference pixel, (32, 32) in
FITS coordinates, is at RA 202.48, Dec 47.21, and 0.001 degrees a pixel.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.communication.xpa.xpa_commands import XPACommands

SIZE = 64
RA, DEC = 202.48, 47.21
SCALE = 0.001


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QDialog, QInputDialog, QMessageBox

    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    # Nothing here may wait on a dialog.
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda *a, **k: (0, False)))
    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    real_get = Preferences.get
    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else real_get(self, key, default),
    )
    monkeypatch.chdir(tmp_path)

    rows, columns = np.indices((SIZE, SIZE))
    header = fits.Header(
        {
            "CRPIX1": 32,
            "CRPIX2": 32,
            "CRVAL1": RA,
            "CRVAL2": DEC,
            "CDELT1": -SCALE,
            "CDELT2": SCALE,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
        }
    )
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32), header=header).writeto(path)

    made = MainWindow()
    made._rebuild_image_viewer(False)
    made.display.load_fits(str(path))
    yield made
    made.close()


@pytest.fixture
def xpa(window):
    return XPACommands(window)


def _set(xpa, command: str) -> dict:
    words = command.split()
    return xpa.handle(words[0], {"args": words[1:]})


def _ok(xpa, command: str) -> None:
    reply = _set(xpa, command)
    assert reply["status"] == "ok", f"{command}: {reply}"


def _refused(xpa, command: str) -> str:
    reply = _set(xpa, command)
    assert reply["status"] == "error", f"{command} should have been refused: {reply}"
    return reply["message"]


def _get(xpa, command: str) -> str:
    words = command.split()
    reply = xpa.handle(words[0], {"get": True, "args": words[1:]})
    assert reply["status"] == "ok", f"xpaget {command}: {reply}"
    return reply["result"]


def _numbers(text: str) -> list[float]:
    return [float(word.rstrip('"')) for word in text.replace(",", " ").split()]


def _frame(window):
    return window.frame_manager.current_frame


# -- coordinates ---------------------------------------------------------------------


def test_the_reference_pixel_reads_back_as_the_reference_position(xpa, window):
    """One-based FITS pixels into a zero-based WCS put every sky answer a
    pixel off; the reference pixel is where that shows."""
    window.crosshair.move_to(32, 32)
    ra, dec = _numbers(_get(xpa, "crosshair wcs fk5 degrees"))
    assert ra == pytest.approx(RA, abs=1e-7)
    assert dec == pytest.approx(DEC, abs=1e-7)
    assert window.iis.coordinate(32, 32, "wcs", "fk5") == "202.4800000 47.2100000"


def test_a_crosshair_read_honours_the_sky_frame_and_format(xpa, window):
    window.crosshair.move_to(32, 32)
    galactic = _numbers(_get(xpa, "crosshair wcs galactic degrees"))
    assert galactic[0] == pytest.approx(104.85, abs=0.01)
    assert galactic[1] == pytest.approx(68.54, abs=0.01)
    assert _get(xpa, "crosshair wcs fk5 sexagesimal") == "13:29:55.2000 +47:12:36.000"
    assert _get(xpa, "crosshair image") == "32 32"


# -- crosshair ---------------------------------------------------------------------------


def test_a_crosshair_is_set_in_the_system_named(xpa, window):
    _ok(xpa, "crosshair 202.48 47.21 wcs fk5")
    assert window.crosshair.position() == pytest.approx((32, 32), abs=1e-6)
    # DS9 puts itself in crosshair mode when the crosshair is set.
    assert window.edit_mode == "crosshair"
    assert _get(xpa, "mode") == "crosshair"


def test_a_crosshair_takes_sexagesimal(xpa, window):
    _ok(xpa, "crosshair 13:29:55.2 +47:12:36 wcs fk5")
    assert window.crosshair.position() == pytest.approx((32, 32), abs=1e-4)


def test_a_crosshair_in_image_pixels_and_its_lock(xpa, window):
    _ok(xpa, "crosshair 10 20 image")
    assert window.crosshair.position() == (10.0, 20.0)
    assert _get(xpa, "crosshair") == "10 20"
    _ok(xpa, "crosshair lock wcs")
    assert _get(xpa, "crosshair lock") == "wcs"
    assert _get(xpa, "lock crosshair") == "wcs"
    assert window.crosshair.locked


# -- crop --------------------------------------------------------------------------------


def test_a_crop_in_image_pixels(xpa, window):
    _ok(xpa, "crop 32 32 10 10 image")
    crop = window.crop.region()
    assert crop.center == (32, 32) and crop.width == 10 and crop.height == 10
    assert _get(xpa, "crop image") == "32 32 10 10"


def test_a_crop_in_degrees_is_converted(xpa, window):
    _ok(xpa, "crop 202.48 47.21 0.01 0.01 wcs fk5 degrees")
    crop = window.crop.region()
    assert crop.center == pytest.approx((32, 32), abs=1e-6)
    assert crop.width == pytest.approx(10, abs=0.01)
    values = _numbers(_get(xpa, "crop wcs fk5 degrees"))
    assert values == pytest.approx([RA, DEC, 0.01, 0.01], abs=1e-6)
    arcsec = _numbers(_get(xpa, "crop wcs fk5 degrees arcsec"))
    assert arcsec[2:] == pytest.approx([36, 36], abs=0.01)


def test_crop_reset_lock_and_dialog(xpa, window):
    _ok(xpa, "crop 32 32 10 10")
    _ok(xpa, "crop reset")
    assert window.crop.region() is None
    assert _get(xpa, "crop") == "32.5 32.5 64 64"
    _ok(xpa, "crop lock image")
    assert _get(xpa, "crop lock") == "image" and window.crop.locked
    _ok(xpa, "crop open")
    _ok(xpa, "crop 3d 2 5")
    assert _frame(window).crop_z == (2.0, 5.0)


# -- regions -----------------------------------------------------------------------------


REGION_FILE = (
    "# Region file format: DS9 version 4.1\n"
    "global color=green\n"
    "image\n"
    "circle(10,20,5) # color=red text={hi}\n"
    "fk5\n"
    'circle(202.48,47.21,3.6")\n'
    "circle(13:29:55.2,+47:12:36,0.001)\n"
)


def test_a_region_file_in_fk5_is_placed_through_the_wcs(xpa, window, tmp_path):
    (tmp_path / "a.reg").write_text(REGION_FILE)
    _ok(xpa, "regions load a.reg")
    first, second, third = _frame(window).regions
    assert first.center == (10.0, 20.0) and first.radius == 5 and first.color == "red"
    assert second.center == pytest.approx((32, 32), abs=1e-6)
    assert second.radius == pytest.approx(1.0, abs=1e-6)
    assert third.center == pytest.approx((32, 32), abs=1e-4)
    assert third.radius == pytest.approx(1.0, abs=1e-6)


def test_a_region_load_adds_and_delete_load_replaces(xpa, window, tmp_path):
    (tmp_path / "a.reg").write_text(REGION_FILE)
    _ok(xpa, "regions load a.reg")
    _ok(xpa, "regions a.reg")
    assert len(_frame(window).regions) == 6
    _ok(xpa, "regions delete load a.reg")
    assert len(_frame(window).regions) == 3
    _ok(xpa, "regions delete")
    assert _frame(window).regions == []


def test_the_region_listing_is_written_in_the_system_asked_for(xpa, window, tmp_path):
    (tmp_path / "a.reg").write_text(REGION_FILE)
    _ok(xpa, "regions load a.reg")
    image = _get(xpa, "regions -format ds9 -system image").splitlines()
    assert image[1] == "image"
    assert image[2] == "circle(10,20,5) # color=red text={hi}"
    assert image[3] == "circle(32,32,1)"
    sky = _get(xpa, "regions -format ds9 -system wcs -sky fk5").splitlines()
    assert sky[1] == "fk5"
    assert sky[3] == 'circle(202.4800000,47.2100000,3.600")'
    sexagesimal = _get(xpa, "regions -system wcs -sky fk5 -skyformat sexagesimal").splitlines()
    assert sexagesimal[3] == 'circle(13:29:55.2000,+47:12:36.000,3.600")'
    assert _get(xpa, "regions -format xy -system image").splitlines()[0] == "10 20"


def test_the_region_output_settings_stick_and_read_back(xpa, window, tmp_path):
    (tmp_path / "a.reg").write_text(REGION_FILE)
    _ok(xpa, "regions load a.reg")
    _ok(xpa, "regions system image")
    _ok(xpa, "regions format ds9")
    assert _get(xpa, "regions system") == "image"
    assert _get(xpa, "regions format") == "ds9"
    assert _get(xpa, "regions").splitlines()[1] == "image"
    _ok(xpa, "regions system wcs")
    _ok(xpa, "regions sky galactic")
    _ok(xpa, "regions skyformat degrees")
    assert _get(xpa, "regions sky") == "galactic"
    assert _get(xpa, "regions").splitlines()[1] == "galactic"
    _ok(xpa, "regions save out.reg")
    saved = (tmp_path / "out.reg").read_text().splitlines()
    assert saved[1] == "galactic"
    _refused(xpa, "regions sky nowhere")


def test_a_saved_region_file_loads_back_to_the_same_place(xpa, window, tmp_path):
    (tmp_path / "a.reg").write_text(REGION_FILE)
    _ok(xpa, "regions load a.reg")
    before = [region.center for region in _frame(window).regions]
    _set(xpa, "regions -system wcs -sky fk5 save round.reg")
    _ok(xpa, "regions delete")
    _ok(xpa, "regions load round.reg")
    after = [region.center for region in _frame(window).regions]
    # Seven decimals of a degree is a ten-thousandth of these pixels.
    assert np.ravel(after) == pytest.approx(np.ravel(before), abs=1e-3)


def test_a_region_command_and_the_selection(xpa, window):
    _ok(xpa, "regions command circle 40 40 5 # color=blue")
    region = _frame(window).regions[-1]
    assert region.center == (40.0, 40.0) and region.color == "blue"
    _ok(xpa, "regions select all")
    assert region.selected
    _ok(xpa, "regions color red")
    _ok(xpa, "regions width 3")
    _ok(xpa, "regions dash yes")
    assert (region.color, region.width, region.dash) == ("red", 3, True)
    assert _get(xpa, "regions color") == "red"
    assert _get(xpa, "regions width") == "3"
    assert "circle(40,40,5)" in _get(xpa, "regions -system image selected")
    _ok(xpa, "regions delete select")
    assert region not in _frame(window).regions


def test_region_settings_read_back(xpa, window):
    _ok(xpa, "regions fontweight bold")
    assert _get(xpa, "regions fontweight") == "bold"
    _ok(xpa, "regions showtext no")
    assert _get(xpa, "regions showtext") == "no"
    _ok(xpa, "regions show no")
    assert _get(xpa, "regions show") == "no"
    _ok(xpa, "regions centroid radius 7")
    _ok(xpa, "regions centroid iteration 12")
    assert window.region.centroid_radius == 7 and window.region.centroid_iterations == 12
    assert _get(xpa, "regions centroid radius") == "7"
    _ok(xpa, "regions shape ellipse")
    assert _get(xpa, "regions shape") == "ellipse"
    _refused(xpa, "regions shape wibble")


def test_a_region_group_needs_no_dialog(xpa, window):
    _ok(xpa, "regions command circle 40 40 5")
    _ok(xpa, "regions select all")
    _ok(xpa, "regions group foo new")
    assert _get(xpa, "regions groups") == "foo"
    _ok(xpa, "regions select none")
    _ok(xpa, "regions group foo select")
    assert all(region.selected for region in _frame(window).regions)
    _ok(xpa, "regions group foo color cyan")
    assert {region.color for region in _frame(window).regions} == {"cyan"}


# -- reads that name a key ---------------------------------------------------------------


def test_minmax_and_zscale_read_one_setting(xpa, window):
    _ok(xpa, "minmax mode sample")
    _ok(xpa, "minmax interval 20")
    assert _get(xpa, "minmax") == "sample"
    assert _get(xpa, "minmax mode") == "sample"
    assert _get(xpa, "minmax interval") == "20"
    _ok(xpa, "zscale contrast .5")
    _ok(xpa, "zscale sample 300")
    assert _get(xpa, "zscale contrast") == "0.5"
    assert _get(xpa, "zscale sample") == "300"
    assert window.scale.settings.samples == 300


def test_preserve_and_pagesetup_read_one_setting(xpa):
    _ok(xpa, "preserve pan yes")
    assert _get(xpa, "preserve pan") == "yes"
    assert _get(xpa, "preserve regions") == "no"
    _ok(xpa, "pagesetup orient landscape")
    assert _get(xpa, "pagesetup orient") == "landscape"


def test_lock_takes_and_reads_ds9s_names(xpa, window):
    _ok(xpa, "lock frame wcs")
    assert _get(xpa, "lock frame") == "wcs"
    _ok(xpa, "lock scalelimits yes")
    assert window._frame_lock_flags["scale_limits"] is True
    assert _get(xpa, "lock scalelimits") == "yes"
    _ok(xpa, "lock axes yes")
    assert _get(xpa, "lock axes") == "yes"
    _ok(xpa, "lock scale no")
    assert _get(xpa, "lock scale") == "no"
    _ok(xpa, "match scalelimits")
    _ok(xpa, "match slice image")
    _ok(xpa, "match slicewcs")


def test_block_rejects_what_it_cannot_do(xpa, window):
    _ok(xpa, "block 4")
    assert _frame(window).block_factor == 4
    _ok(xpa, "block 2 2")
    assert _get(xpa, "block") == "2"
    _refused(xpa, "block 4 2")
    assert _frame(window).block_factor == 2
    _ok(xpa, "block lock yes")
    assert _get(xpa, "block lock") == "yes"


# -- display -----------------------------------------------------------------------------


def test_smooth_parameters(xpa, window):
    _ok(xpa, "smooth function boxcar")
    _ok(xpa, "smooth radius 4")
    _ok(xpa, "smooth sigma 2.5")
    settings = window._smooth_settings
    assert settings["kernel_type"] == "Boxcar"
    assert settings["kernel_size"] == 9
    assert settings["sigma"] == 2.5
    assert _get(xpa, "smooth function") == "boxcar"
    assert _get(xpa, "smooth radius") == "4"
    _ok(xpa, "smooth yes")
    assert _get(xpa, "smooth") == "yes"
    assert window.menu_bar.action_smooth.isChecked()
    _refused(xpa, "smooth function wibble")


def test_grid_parameters(xpa, window):
    _ok(xpa, "grid yes")
    assert window.analysis.grid_config.visible
    _ok(xpa, "grid type publication")
    _ok(xpa, "grid axes color red")
    _ok(xpa, "grid numerics fontsize 14")
    config = window.analysis.grid_config
    assert config.grid_type.value == "publication"
    assert config.elements["axes"].color == "red"
    assert config.elements["numerics"].font_size == 14
    assert _get(xpa, "grid type") == "publication"
    assert _get(xpa, "grid axes color") == "red"
    _refused(xpa, "grid grid gap1 5")


def test_contour_settings_reach_the_levels(xpa, window):
    _ok(xpa, "contour yes")
    _ok(xpa, "contour levels {10 20 30}")
    assert list(window._contour_levels) == [10, 20, 30]
    assert _get(xpa, "contour levels") == "10 20 30"
    _ok(xpa, "contour nlevels 4")
    _ok(xpa, "contour limits 10 40")
    assert list(window._contour_levels) == pytest.approx([10, 20, 30, 40])
    assert _get(xpa, "contour limits") == "10 40"
    _ok(xpa, "contour method smooth")
    assert _get(xpa, "contour method") == "smooth"
    _ok(xpa, "contour scale linear")
    assert _get(xpa, "contour scale") == "linear"
    _ok(xpa, "contour log exp 100")
    assert _get(xpa, "contour log exp") == "100"


def test_magnifier_zoom(xpa, window):
    _ok(xpa, "magnifier zoom 8")
    assert window.magnifier_panel._zoom_factor == 8
    assert _get(xpa, "magnifier zoom") == "8"
    _refused(xpa, "magnifier color red")


def test_mask_grammar(xpa, window, tmp_path):
    _ok(xpa, f"mask load {tmp_path / 'sky.fits'}")
    assert window.analysis.mask_layer is not None
    assert _get(xpa, "mask") == "yes"
    _ok(xpa, "mask color blue")
    _ok(xpa, "mask transparency 20")
    _ok(xpa, "mask mark range")
    _ok(xpa, "mask range 1 5")
    settings = window.analysis.mask_settings
    assert (settings.color, settings.transparency, settings.mode.value) == ("blue", 20, "range")
    assert _get(xpa, "mask range") == "1 5"
    _ok(xpa, "mask clear")
    assert window.analysis.mask_layer is None


# -- frames ------------------------------------------------------------------------------


def test_tile_grammar(xpa, window):
    _ok(xpa, "tile column")
    assert window._frame_display_mode == "tile"
    assert _get(xpa, "tile mode") == "column"
    _ok(xpa, "tile grid layout 3 2")
    settings = window.frame_controller.tile_settings
    assert (settings.columns, settings.rows, settings.manual) == (3, 2, True)
    assert _get(xpa, "tile grid layout") == "3 2"
    _ok(xpa, "tile grid gap 7")
    assert _get(xpa, "tile grid gap") == "7"
    _ok(xpa, "tile no")
    assert _get(xpa, "tile") == "no"


def test_blink_needs_two_frames_and_reads_its_interval(xpa, window):
    _refused(xpa, "blink")
    _ok(xpa, "blink interval 0.5")
    assert _get(xpa, "blink interval") == "0.5"
    window.frame_controller.new_frame()
    _ok(xpa, "blink")
    assert _get(xpa, "blink") == "yes"
    _ok(xpa, "single")


def test_cube_settings(xpa, window):
    _ok(xpa, "cube interval 2")
    assert _get(xpa, "cube interval") == "2"
    _ok(xpa, "cube lock image")
    assert _get(xpa, "cube lock") == "image"
    assert _get(xpa, "lock slice") == "image"
    _refused(xpa, "cube next")  # this frame holds no cube


def test_the_view_reads_one_setting(xpa, window):
    _ok(xpa, "view colorbar no")
    assert _get(xpa, "view colorbar") == "no"
    assert window.view_state.colorbar is False
    _ok(xpa, "view filename no")
    assert _get(xpa, "view filename") == "no"
    _ok(xpa, "view keyvalue BITPIX")
    assert _get(xpa, "view keyvalue") == "BITPIX"
    _ok(xpa, "view layout vertical")
    assert _get(xpa, "view layout") == "vertical"


# -- data and header ----------------------------------------------------------------------


def test_data_reads_a_box_in_any_system(xpa):
    assert _get(xpa, "data image 32 32 1 1 yes") == "62"
    assert _get(xpa, "data wcs fk5 202.48 47.21 0.001 0.001 yes") == "62"
    assert _get(xpa, "data fk5 13:29:55.2 +47:12:36 0.001 0.001 yes") == "62"
    lines = _get(xpa, "data image 32 32 2 1 no").splitlines()
    assert lines == ["32 32 62", "33 32 63"]


def test_header_save_writes_the_header(xpa, tmp_path):
    _ok(xpa, "header save 1 hdr.txt")
    text = (tmp_path / "hdr.txt").read_text()
    assert text.startswith("SIMPLE")
    assert "CRVAL1" in text
    _refused(xpa, "header 5")
    _ok(xpa, "header close")


def test_export_does_not_ask_for_a_byte_order(xpa, tmp_path):
    _ok(xpa, "export nrrd ex.nrrd")
    assert (tmp_path / "ex.nrrd").exists()
    _ok(xpa, "export array ex.arr little")
    assert (tmp_path / "ex.arr").stat().st_size == SIZE * SIZE * 4


# -- preferences ---------------------------------------------------------------------------


def test_prefs_set_and_read_what_they_name(xpa, window):
    _ok(xpa, "prefs precision 8 7 4 3 8 7 5 3 8")
    assert _get(xpa, "prefs precision") == "8 7 4 3 8 7 5 3 8"
    assert window.preferences.get("precision_len_degrees") == 7
    _ok(xpa, "prefs nan color blue")
    assert window.nan_color == "blue"
    assert _get(xpa, "prefs nan color") == "blue"
    _ok(xpa, "prefs bg color red")
    assert _get(xpa, "prefs bg color") == "red"
    assert _get(xpa, "bg") == "red"
    _ok(xpa, "prefs threads 8")
    assert _get(xpa, "threads") == "8"
    _refused(xpa, "prefs irafalign yes")


def test_bg_color_takes_the_colour_not_the_word(xpa, window):
    _ok(xpa, "bg color green")
    assert window.preferences.get("background_color") == "green"
    assert _get(xpa, "background") == "green"


def test_precision_takes_ds9s_nine(xpa, window):
    _ok(xpa, "precision 9 8 5 4 9 8 6 4 9")
    assert window.preferences.get("precision_arcsec") == 4
    assert window.preferences.get("precision_angle") == 9
    _refused(xpa, "precision 1 2 3")


# -- odds and ends that were already right, kept right --------------------------------------


def test_points_that_were_already_right(xpa, window):
    _ok(xpa, "rotate 45")
    assert _frame(window).rotation == 45
    _ok(xpa, "rotate to 30")
    assert _get(xpa, "rotate") == "30"
    _ok(xpa, "orient xy")
    assert _get(xpa, "orient") == "xy"
    assert _frame(window).flip_x and _frame(window).flip_y
    _ok(xpa, "invert yes")
    assert _get(xpa, "invert") == "yes"
    _ok(xpa, "nan red")
    assert window.nan_color == "red"
    _ok(xpa, "mode region")
    assert window.edit_mode == "region"
    _ok(xpa, "pixeltable yes")
    assert _get(xpa, "pixeltable") == "yes"
    _ok(xpa, "pixeltable close")
    assert _get(xpa, "pixeltable") == "no"
    _ok(xpa, "align yes")
    assert _get(xpa, "align") == "yes"


def test_files_written_by_the_save_points(xpa, tmp_path):
    _ok(xpa, "saveimage png out.png")
    _ok(xpa, "saveimage jpeg out.jpeg 75")
    _ok(xpa, "savefits out.fits")
    assert (tmp_path / "out.png").exists() and (tmp_path / "out.jpeg").exists()
    assert fits.getdata(tmp_path / "out.fits").shape == (SIZE, SIZE)


def test_backup_and_restore(xpa, window, tmp_path):
    _ok(xpa, "rotate to 30")
    _ok(xpa, "backup bk.bck")
    _ok(xpa, "rotate to 0")
    _ok(xpa, "restore bk.bck")
    assert _get(xpa, "rotate") == "30"
