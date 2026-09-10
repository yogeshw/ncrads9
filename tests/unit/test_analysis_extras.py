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

"""Contour files, mask files, the elliptical kernel, the pixel table
(M7-21 ... M7-26)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.analysis import contour_file
from ncrads9.analysis import mask as mask_module
from ncrads9.analysis.contour import CONTOUR_METHODS, ContourGenerator
from ncrads9.analysis.mask import BlendMode, MaskMode, MaskSettings
from ncrads9.analysis.pixel_table import PixelTable
from ncrads9.analysis.smooth import elliptical_gaussian_kernel, elliptical_gaussian_smooth

#: DS9's own example, from `ds9/doc/ref/contour.html`.
DS9_CONTOUR_FILE = """\
# Contour file format: DS9 version 7.5
global color=green width=1 dash=1 dashlist=8 3
image
level=15.78775 color=pink width=2 dash=yes dashlist=2 2
(202.4836468 47.22380226
 202.4833538 47.2239185
 202.4831634 47.22409874
 202.4829883 47.22428858)
"""


# -- contour files (M7-21) ----------------------------------------------------


def test_ds9s_documented_contour_file_parses():
    contours = contour_file.parse(DS9_CONTOUR_FILE)
    assert contours.system == "image"
    assert len(contours) == 1

    (level,) = contours.levels
    assert level.value == pytest.approx(15.78775)
    assert level.color == "pink"
    assert level.width == 2
    assert level.dash is True
    assert level.dashlist == "2 2"
    assert len(level.contours) == 1
    assert level.points == 4


def test_a_level_inherits_the_globals():
    contours = contour_file.parse("global color=blue width=3\nimage\nlevel=1\n(1 2 3 4)\n")
    assert contours.levels[0].color == "blue"
    assert contours.levels[0].width == 3


def test_a_levels_own_properties_override_the_globals():
    contours = contour_file.parse("global color=blue\nimage\nlevel=1 color=red\n(1 2 3 4)\n")
    assert contours.levels[0].color == "red"


@pytest.mark.parametrize("written", ["dash=1", "dash=yes", "dash=true"])
def test_ds9s_several_spellings_of_a_flag(written):
    """Its own example uses two of them in one file."""
    contours = contour_file.parse(f"image\nlevel=1 {written}\n(1 2 3 4)\n")
    assert contours.levels[0].dash is True


def test_dashlist_takes_two_numbers():
    """A value that ran to the next space would drop the second."""
    contours = contour_file.parse("image\nlevel=1 dash=1 dashlist=8 3 color=red\n(1 2 3 4)\n")
    assert contours.levels[0].dashlist == "8 3"
    assert contours.levels[0].color == "red"


def test_a_multi_line_coordinate_block_is_one_contour():
    contours = contour_file.parse("image\nlevel=1\n(1 2\n 3 4\n 5 6)\n")
    assert len(contours.levels[0].contours) == 1
    assert contours.levels[0].points == 3


def test_commas_separate_coordinates_too():
    """DS9: "a deliminator of space or comma"."""
    contours = contour_file.parse("image\nlevel=1\n(1,2 3,4)\n")
    assert contours.levels[0].contours[0] == [(1.0, 2.0), (3.0, 4.0)]


def test_a_coordinate_system_is_recognised():
    for system in ("fk5", "galactic", "physical", "wcsa"):
        assert contour_file.parse(f"{system}\nlevel=1\n(1 2 3 4)\n").system == system


def test_a_contour_file_round_trips():
    contours = contour_file.parse(DS9_CONTOUR_FILE)
    again = contour_file.parse(contour_file.to_text(contours))
    assert again.values == contours.values
    assert again.levels[0].contours == contours.levels[0].contours
    assert again.levels[0].color == "pink"


def test_a_file_on_disk_round_trips(tmp_path):
    path = tmp_path / "x.ctr"
    contour_file.save(path, contour_file.parse(DS9_CONTOUR_FILE))
    assert contour_file.load(path).values == [pytest.approx(15.78775)]


def test_a_garbled_coordinate_block_is_reported():
    with pytest.raises(contour_file.ContourFileError, match="not a coordinate list"):
        contour_file.parse("image\nlevel=1\n(one two three four)\n")


def test_a_single_point_contour_is_dropped():
    """One point is not a curve; drawing it is a stray dot."""
    contours = contour_file.parse("image\nlevel=1\n(1 2)\n")
    assert contours.levels[0].contours == []


def test_paths_convert_to_the_file_and_back():
    """`find_contours` gives (row, column); the file format is (x, y).
    Getting that backwards writes the transpose of the picture."""
    paths = [[np.array([[10.0, 20.0], [11.0, 21.0]])]]
    contours = contour_file.from_paths(paths, [5.0])
    assert contours.levels[0].contours[0] == [(20.0, 10.0), (21.0, 11.0)]

    back = contour_file.to_paths(contours)
    assert np.allclose(back[0][0], paths[0][0])


# -- contour methods (M7-23) ---------------------------------------------------------


def _gaussian_image(size: int = 64) -> np.ndarray:
    rows, columns = np.indices((size, size))
    return (np.exp(-(((columns - 32) ** 2 + (rows - 32) ** 2) / 200.0)) * 100).astype(np.float32)


def test_ds9s_two_methods_are_offered():
    assert CONTOUR_METHODS == ("block", "smooth")


def test_block_shrinks_the_image_and_smooth_does_not():
    """DS9: BLOCK "blocks down the image"; SMOOTH "smooths the image"."""
    data = _gaussian_image()
    assert ContourGenerator(data, method="block", smoothness=4).data.shape == (16, 16)
    assert ContourGenerator(data, method="smooth", smoothness=4).data.shape == (64, 64)


def test_a_blocked_contour_lands_on_the_original_grid():
    """Computed on a 16x16 image, drawn on a 64x64 one."""
    data = _gaussian_image()
    plain = ContourGenerator(data, smoothness=1).find_contours([50.0])[0][0]
    blocked = ContourGenerator(data, method="block", smoothness=4).find_contours([50.0])[0][0]
    assert blocked[:, 1].mean() == pytest.approx(plain[:, 1].mean(), abs=1.0)
    assert blocked[:, 0].mean() == pytest.approx(plain[:, 0].mean(), abs=1.0)


def test_a_smoothness_of_one_changes_nothing():
    data = _gaussian_image()
    for method in CONTOUR_METHODS:
        assert np.allclose(ContourGenerator(data, method=method, smoothness=1).data, data)


def test_an_unknown_method_falls_back_rather_than_raising():
    assert ContourGenerator(_gaussian_image(), method="mangle").method == "block"


def test_a_partial_block_is_dropped_not_averaged_short():
    """A block of fewer pixels is brighter or fainter for no reason, and it
    shows as a bright edge on the last contour."""
    from ncrads9.analysis.contour import _block_down

    data = np.ones((10, 10))
    assert _block_down(data, 4).shape == (2, 2)


# -- mask files (M7-24) -----------------------------------------------------------------


@pytest.fixture
def mask_image() -> np.ndarray:
    return np.array([[0.0, 1.0, np.nan], [2.0, 0.0, 5.0]])


@pytest.mark.parametrize(
    "mode,expected",
    [
        (MaskMode.ZERO, [[1, 0, 0], [0, 1, 0]]),
        (MaskMode.NON_ZERO, [[0, 1, 0], [1, 0, 1]]),
        (MaskMode.NAN, [[0, 0, 1], [0, 0, 0]]),
        (MaskMode.NON_NAN, [[1, 1, 0], [1, 1, 1]]),
        (MaskMode.RANGE, [[0, 1, 0], [1, 0, 0]]),
    ],
)
def test_ds9s_five_mask_modes(mask_image, mode, expected):
    settings = MaskSettings(mode=mode, low=1.0, high=2.0)
    assert mask_module.selected(mask_image, settings).astype(int).tolist() == expected


def test_a_reversed_range_is_still_a_range(mask_image):
    settings = MaskSettings(mode=MaskMode.RANGE, low=2.0, high=1.0)
    assert mask_module.selected(mask_image, settings).sum() == 2


def test_a_mask_is_read_from_a_fits_file(tmp_path):
    path = tmp_path / "mask.fits"
    fits.PrimaryHDU(data=np.ones((4, 4), dtype=np.int16)).writeto(path)
    assert mask_module.load(path).shape == (4, 4)


def test_a_mask_in_an_extension_is_found(tmp_path):
    """A file whose primary HDU is empty is the usual shape of a mask."""
    path = tmp_path / "mask.fits"
    fits.HDUList(
        [fits.PrimaryHDU(), fits.ImageHDU(data=np.ones((3, 3), dtype=np.int16), name="MASK")]
    ).writeto(path)
    assert mask_module.load(path).shape == (3, 3)


def test_a_file_with_no_image_is_refused(tmp_path):
    path = tmp_path / "empty.fits"
    fits.PrimaryHDU().writeto(path)
    with pytest.raises(mask_module.MaskError, match="no two-dimensional image"):
        mask_module.load(path)


def test_a_mask_of_a_different_shape_is_fitted():
    """A trimmed exposure map is common; refusing it is less useful than
    lining up what overlaps."""
    fitted = mask_module.align(np.ones((3, 3)), (5, 6))
    assert fitted.shape == (5, 6)
    assert np.isnan(fitted[4, 5])
    assert fitted[0, 0] == 1.0


def test_a_mask_the_same_shape_is_not_copied():
    original = np.ones((3, 3))
    assert mask_module.align(original, (3, 3)) is original


@pytest.mark.parametrize(
    "blend,expected",
    [
        (BlendMode.SOURCE, [1.0, 0.0, 0.0]),
        (BlendMode.SCREEN, [1.0, 0.5, 0.5]),
        (BlendMode.DARKEN, [0.5, 0.0, 0.0]),
        (BlendMode.LIGHTEN, [1.0, 0.5, 0.5]),
    ],
)
def test_ds9s_four_blend_modes(blend, expected):
    image = np.full((1, 1, 3), 0.5)
    chosen = np.ones((1, 1), dtype=bool)
    painted = mask_module.blend(image, chosen, (1.0, 0.0, 0.0), 1.0, blend)
    assert painted[0, 0].tolist() == pytest.approx(expected)


def test_transparency_scales_the_blend():
    image = np.zeros((1, 1, 3))
    chosen = np.ones((1, 1), dtype=bool)
    settings = MaskSettings(transparency=50.0)
    painted = mask_module.blend(image, chosen, (1.0, 1.0, 1.0), settings.alpha)
    assert painted[0, 0, 0] == pytest.approx(0.5)


def test_a_fully_transparent_mask_changes_nothing():
    image = np.full((2, 2, 3), 0.25)
    chosen = np.ones((2, 2), dtype=bool)
    settings = MaskSettings(transparency=100.0)
    painted = mask_module.blend(image, chosen, (1.0, 0.0, 0.0), settings.alpha)
    assert np.allclose(painted, image)


def test_blending_does_not_touch_the_input():
    """It is the displayed frame; masking must not be destructive."""
    image = np.full((2, 2, 3), 0.25)
    mask_module.blend(image, np.ones((2, 2), dtype=bool), (1.0, 0.0, 0.0), 1.0)
    assert np.allclose(image, 0.25)


# -- the elliptical Gaussian (M7-25) --------------------------------------------------


def test_the_kernel_sums_to_one():
    """So smoothing preserves flux."""
    assert elliptical_gaussian_kernel(5, 2, 2.0, 1.0, 30.0).sum() == pytest.approx(1.0)


def test_the_kernel_has_a_centre_pixel():
    """DS9's diameter is 2*radius+1; an even kernel shifts the image."""
    for radius in (1, 3, 6):
        assert elliptical_gaussian_kernel(radius, radius, 1.0, 1.0).shape[0] % 2 == 1


def test_the_kernel_rotates():
    """Long in x at zero degrees, long in y at ninety."""

    def extent(angle: float) -> tuple[int, int]:
        kernel = elliptical_gaussian_kernel(6, 2, 3.0, 1.0, angle)
        rows, columns = np.nonzero(kernel > kernel.max() * 0.05)
        return (columns.max() - columns.min(), rows.max() - rows.min())

    wide_x, tall_x = extent(0.0)
    wide_y, tall_y = extent(90.0)
    assert wide_x > tall_x
    assert tall_y > wide_y


def test_a_round_kernel_is_round():
    kernel = elliptical_gaussian_kernel(4, 4, 2.0, 2.0, 0.0)
    assert np.allclose(kernel, kernel.T)


def test_smoothing_preserves_total_flux():
    data = np.zeros((41, 41))
    data[20, 20] = 1.0
    assert elliptical_gaussian_smooth(data, 6, 2, 3.0, 1.0).sum() == pytest.approx(1.0, abs=1e-6)


def test_the_position_angle_reaches_the_smoothed_image(qapp, monkeypatch):
    """The dialog had a Position angle field that did nothing at all."""
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    data = np.zeros((41, 41), dtype=np.float32)
    data[20, 20] = 100.0

    settings = {
        "kernel_type": "Gaussian",
        "elliptical": True,
        "sigma": 3.0,
        "major_radius": 8,
        "minor_radius": 2,
        "major_sigma": 4.0,
        "minor_sigma": 1.0,
        "preserve_nan": False,
    }
    window._smooth_settings = {**settings, "position_angle": 0.0}
    flat = window.analysis.apply_smoothing(data)
    window._smooth_settings = {**settings, "position_angle": 90.0}
    upright = window.analysis.apply_smoothing(data)

    # Smeared along x at 0 degrees and along y at 90.
    assert flat[20, 26] > flat[26, 20]
    assert upright[26, 20] > upright[20, 26]
    window.close()


# -- the pixel table (M7-26) --------------------------------------------------------


def test_ds9s_table_sizes_are_offered(qapp):
    from ncrads9.ui.dialogs.pixel_table_dialog import TABLE_SIZES, PixelTableDialog

    assert TABLE_SIZES == (3, 5, 7, 9)
    dialog = PixelTableDialog(np.zeros((20, 20)), 10, 10)
    offered = [dialog._size_combo.itemText(index) for index in range(dialog._size_combo.count())]
    assert offered == ["3x3", "5x5", "7x7", "9x9"]


def test_changing_the_size_refills_the_table(qapp):
    from ncrads9.ui.dialogs.pixel_table_dialog import PixelTableDialog

    dialog = PixelTableDialog(np.arange(400, dtype=float).reshape(20, 20), 10, 10, size=3)
    assert dialog.table.rowCount() == 3
    dialog._size_combo.setCurrentText("9x9")
    assert dialog.table.rowCount() == 9
    assert dialog.table.item(4, 4).text() == "210"


def test_an_even_size_falls_back_rather_than_rounding(qapp):
    """A 4x4 table has no centre pixel to be a table about."""
    from ncrads9.ui.dialogs.pixel_table_dialog import DEFAULT_TABLE_SIZE, PixelTableDialog

    assert PixelTableDialog(np.zeros((20, 20)), 5, 5, size=4).size == DEFAULT_TABLE_SIZE


def test_a_region_off_the_edge_is_padded_not_clipped():
    """Clipping returns a smaller array whose centre is not the centre, so
    the table shows the wrong values against the wrong coordinates."""
    table = PixelTable(np.arange(100, dtype=float).reshape(10, 10))
    region = table.get_region(1, 1, 5)
    assert region.shape == (5, 5)
    assert np.isnan(region[0, 0])
    # The centre of the returned square is still the pixel asked for.
    assert region[2, 2] == 11.0


def test_a_region_entirely_off_the_image_is_all_blank():
    table = PixelTable(np.zeros((10, 10)))
    assert np.isnan(table.get_region(100, 100, 5)).all()


def test_the_table_shows_the_centre_pixels_coordinates(qapp):
    from ncrads9.ui.dialogs.pixel_table_dialog import PixelTableDialog

    dialog = PixelTableDialog(np.arange(100, dtype=float).reshape(10, 10), 5, 5)
    assert "Image: 5 5" in dialog._coordinates.text()
    assert "Value: 55" in dialog._coordinates.text()


def test_the_table_shows_a_sky_position_when_there_is_one(qapp):
    from ncrads9.core.wcs_handler import WCSHandler
    from ncrads9.ui.dialogs.pixel_table_dialog import PixelTableDialog

    header = fits.Header(
        {
            "NAXIS": 2,
            "NAXIS1": 10,
            "NAXIS2": 10,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CRPIX1": 5,
            "CRPIX2": 5,
            "CRVAL1": 150.0,
            "CRVAL2": 2.0,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
        }
    )
    dialog = PixelTableDialog(np.zeros((10, 10)), 5, 5, wcs_handler=WCSHandler(header))
    assert "WCS:" in dialog._coordinates.text()


def test_an_edge_pixel_reads_as_blank_not_as_nan(qapp):
    from ncrads9.ui.dialogs.pixel_table_dialog import PixelTableDialog

    dialog = PixelTableDialog(np.arange(100, dtype=float).reshape(10, 10), 0, 0, size=3)
    assert dialog.table.item(0, 0).text() == "--"


def test_moving_the_table_follows_the_cursor(qapp):
    from ncrads9.ui.dialogs.pixel_table_dialog import PixelTableDialog

    dialog = PixelTableDialog(np.arange(100, dtype=float).reshape(10, 10), 5, 5, size=3)
    dialog.set_center(2, 2)
    assert dialog.table.item(1, 1).text() == "22"
