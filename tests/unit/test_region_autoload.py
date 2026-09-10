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

"""Regions carried in a FITS REGION extension, and autoloading them (M6-21)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.regions import fits_regions
from ncrads9.regions.shapes.box import Box
from ncrads9.regions.shapes.circle import Circle
from ncrads9.regions.shapes.point import Point
from ncrads9.regions.shapes.polygon import Polygon


def _region_table(shapes, xs, ys, rs, angles=None, width: int = 4) -> fits.BinTableHDU:
    """A REGION table in the FITS region convention."""
    count = len(shapes)
    angles = angles if angles is not None else [0.0] * count

    def pad(rows):
        out = np.zeros((count, width), dtype=np.float32)
        for index, row in enumerate(rows):
            out[index, : len(row)] = row
        return out

    columns = fits.ColDefs(
        [
            fits.Column(name="X", format=f"{width}E", array=pad(xs)),
            fits.Column(name="Y", format=f"{width}E", array=pad(ys)),
            fits.Column(name="SHAPE", format="20A", array=np.array(shapes)),
            fits.Column(name="R", format=f"{width}E", array=pad(rs)),
            fits.Column(name="ROTANG", format="1E", array=np.array(angles, dtype=np.float32)),
        ]
    )
    return fits.BinTableHDU.from_columns(columns, name="REGION")


def _file(hdus) -> fits.HDUList:
    primary = fits.PrimaryHDU(np.zeros((64, 64), dtype=np.float32))
    return fits.HDUList([primary, *hdus])


# -- reading the table -----------------------------------------------------------


def test_a_file_without_the_extension_has_none():
    assert fits_regions.has_region_extension(_file([])) is False


def test_a_file_with_it_is_found():
    table = _region_table(["circle"], [[10]], [[10]], [[5]])
    assert fits_regions.has_region_extension(_file([table])) is True


def test_a_circle_is_read():
    table = _region_table(["circle"], [[10]], [[20]], [[5]])
    (region,) = fits_regions.load_from_file(_file([table]))
    assert isinstance(region, Circle)
    assert (region.center, region.radius) == ((10.0, 20.0), 5.0)


def test_a_box_is_read_from_radii_not_widths():
    """The convention gives half-widths; taking them as widths halves the box."""
    table = _region_table(["rotbox"], [[10]], [[20]], [[4, 3]], angles=[30.0])
    (region,) = fits_regions.load_from_file(_file([table]))
    assert isinstance(region, Box)
    assert (region.width_box, region.height_box, region.angle) == (8.0, 6.0, 30.0)


def test_a_polygon_takes_every_vertex():
    """Polygons come as variable-length columns, one entry per vertex."""
    columns = fits.ColDefs(
        [
            fits.Column(name="X", format="PE()", array=np.array([[1.0, 5.0, 5.0]], dtype=object)),
            fits.Column(name="Y", format="PE()", array=np.array([[1.0, 1.0, 6.0]], dtype=object)),
            fits.Column(name="SHAPE", format="20A", array=np.array(["polygon"])),
        ]
    )
    table = fits.BinTableHDU.from_columns(columns, name="REGION")
    (region,) = fits_regions.load_from_file(_file([table]))
    assert isinstance(region, Polygon)
    assert region.vertices == [(1.0, 1.0), (5.0, 1.0), (5.0, 6.0)]


def test_a_point_is_read():
    table = _region_table(["point"], [[3]], [[4]], [[0]])
    assert isinstance(fits_regions.load_from_file(_file([table]))[0], Point)


@pytest.mark.parametrize("mark", ["!", "-"])
def test_a_marked_shape_is_an_exclusion(mark):
    table = _region_table([f"{mark}circle"], [[10]], [[10]], [[5]])
    (region,) = fits_regions.load_from_file(_file([table]))
    assert region.include is False


def test_a_shape_with_no_equivalent_is_skipped_not_fatal():
    """One unreadable row must not lose the rest of the table."""
    table = _region_table(["sector", "circle"], [[1], [10]], [[1], [10]], [[1], [5]])
    regions = fits_regions.load_from_file(_file([table]))
    assert len(regions) == 1
    assert isinstance(regions[0], Circle)


def test_a_table_with_no_shape_column_reads_as_nothing():
    columns = fits.ColDefs([fits.Column(name="X", format="1E", array=np.array([1.0]))])
    table = fits.BinTableHDU.from_columns(columns, name="REGION")
    assert fits_regions.load_from_file(_file([table])) == []


def test_an_empty_table_reads_as_nothing():
    table = _region_table([], [], [], [])
    assert fits_regions.load_from_file(_file([table])) == []


# -- autoloading -------------------------------------------------------------------


@pytest.fixture
def with_regions(tmp_path):
    """A FITS file carrying two regions in a REGION extension."""
    table = _region_table(["circle", "rotbox"], [[10], [30]], [[20], [40]], [[5], [4, 3]])
    path = tmp_path / "withregions.fits"
    _file([table]).writeto(path)
    return path


@pytest.fixture
def plain(tmp_path):
    path = tmp_path / "plain.fits"
    _file([]).writeto(path)
    return path


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
    yield window
    window.close()


def test_the_preference_is_on_by_default():
    """DS9 has it on (`ds9/library/ds9.tcl:124`)."""
    from ncrads9.utils.preferences import Preferences

    assert Preferences.DEFAULT_PREFS["autoload_fits_regions"] is True


def test_opening_a_file_loads_its_regions(main_window, with_regions):
    main_window.display.load_fits(str(with_regions))
    regions = main_window.frame_manager.current_frame.regions
    assert len(regions) == 2
    assert isinstance(regions[0], Circle)


def test_the_preference_turns_it_off(main_window, with_regions, monkeypatch):
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key in ("use_gpu", "autoload_fits_regions") else default,
    )
    main_window.display.load_fits(str(with_regions))
    assert main_window.frame_manager.current_frame.regions == []


def test_a_file_without_regions_loads_as_before(main_window, plain):
    main_window.display.load_fits(str(plain))
    assert main_window.frame_manager.current_frame.regions == []
    assert main_window.frame_manager.current_frame.image_data is not None


def test_a_malformed_region_table_does_not_stop_the_image(main_window, tmp_path):
    """The picture matters more than the regions on it."""
    columns = fits.ColDefs([fits.Column(name="SHAPE", format="20A", array=np.array(["circle"]))])
    broken = fits.BinTableHDU.from_columns(columns, name="REGION")
    path = tmp_path / "broken.fits"
    _file([broken]).writeto(path)

    main_window.display.load_fits(str(path))
    assert main_window.frame_manager.current_frame.image_data is not None
