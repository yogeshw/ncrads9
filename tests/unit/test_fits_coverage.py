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


"""FITS coverage: the extension model, sections, events, cubes and mosaics.

Everything here works on files written by the fixtures below rather than on
the bundled samples, so each shape M4 has to cope with -- a multi-extension
file, an events table, a cube, an IRAF mosaic -- is present and minimal.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.core import fits_loaders
from ncrads9.core.cube_handler import AXIS_ORDERS, AxisOrder, CubeHandler, is_cube
from ncrads9.core.file_spec import Section, parse
from ncrads9.core.fits_handler import (
    EVENTS_EXTNAMES,
    FITSHandler,
    FITSLoadError,
    HDUKind,
    apply_section,
    classify,
)
from ncrads9.core.image_data import ImageData
from ncrads9.core.mosaic import MosaicError, MosaicKind, build_mosaic, parse_section
from ncrads9.core.wcs_handler import WCSHandler, available_alternates


def _wcs_header(width: int, height: int, crval1: float = 10.0) -> fits.Header:
    """A minimal tangent-plane header."""
    return fits.Header(
        {
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CRVAL1": crval1,
            "CRVAL2": 20.0,
            "CRPIX1": width / 2 + 0.5,
            "CRPIX2": height / 2 + 0.5,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
        }
    )


@pytest.fixture
def mef(tmp_path):
    """A file with an empty primary and three same-shaped image extensions."""
    path = tmp_path / "mef.fits"
    header = _wcs_header(20, 16)
    header["OBJECT"] = "M51"
    header["BUNIT"] = "Jy/beam"
    fits.HDUList(
        [
            fits.PrimaryHDU(),
            fits.ImageHDU(np.full((16, 20), 1.0, np.float32), header, name="SCI"),
            fits.ImageHDU(np.full((16, 20), 2.0, np.float32), header, name="ERR"),
            fits.ImageHDU(np.full((16, 20), 3.0, np.float32), header, name="DQ"),
        ]
    ).writeto(path)
    return path


@pytest.fixture
def events(tmp_path):
    """An events table with X, Y and PHA columns and declared limits."""
    path = tmp_path / "evt.fits"
    rng = np.random.default_rng(7)
    table = fits.BinTableHDU.from_columns(
        [
            fits.Column("X", "E", array=rng.integers(1, 33, 400).astype(np.float32)),
            fits.Column("Y", "E", array=rng.integers(1, 17, 400).astype(np.float32)),
            fits.Column("PHA", "J", array=rng.integers(0, 100, 400)),
        ],
        name="EVENTS",
    )
    table.header["TLMIN1"], table.header["TLMAX1"] = 1, 32
    table.header["TLMIN2"], table.header["TLMAX2"] = 1, 16
    fits.HDUList([fits.PrimaryHDU(), table]).writeto(path)
    return path


@pytest.fixture
def cube(tmp_path):
    """A 5-plane cube with a spectral third axis."""
    path = tmp_path / "cube.fits"
    header = _wcs_header(12, 8)
    header["CRVAL3"], header["CDELT3"], header["CRPIX3"] = 1000.0, 10.0, 1.0
    header["CUNIT3"], header["CTYPE3"] = "m/s", "VELO-LSR"
    fits.PrimaryHDU(np.arange(5 * 8 * 12, dtype=np.float32).reshape(5, 8, 12), header).writeto(path)
    return path


# -- the extension model (M4-1) ----------------------------------------------


def test_extensions_are_described(mef):
    with FITSHandler(str(mef)) as handler:
        infos = handler.extensions()
    assert [info.name for info in infos] == ["PRIMARY", "SCI", "ERR", "DQ"]
    assert [info.kind for info in infos] == [HDUKind.EMPTY, *[HDUKind.IMAGE] * 3]
    assert infos[1].dimensions == "20x16"
    assert infos[1].bitpix == -32


def test_an_empty_primary_is_not_displayable(mef):
    with FITSHandler(str(mef)) as handler:
        assert not handler.extensions()[0].displayable
        assert [info.name for info in handler.displayable_extensions()] == ["SCI", "ERR", "DQ"]


def test_default_extension_follows_ds9s_algorithm(mef):
    """Primary if it is an image, else the first extension that is one."""
    with FITSHandler(str(mef)) as handler:
        assert handler.default_extension().name == "SCI"


def test_an_image_primary_is_the_default(cube):
    with FITSHandler(str(cube)) as handler:
        assert handler.default_extension().index == 0


def test_extension_by_name_is_case_insensitive(mef):
    with FITSHandler(str(mef)) as handler:
        assert handler.resolve_extension("err").index == 2
        assert handler.resolve_extension("ERR").index == 2


def test_a_missing_extension_says_so(mef):
    with FITSHandler(str(mef)) as handler:
        with pytest.raises(FITSLoadError, match="no extension named"):
            handler.resolve_extension("NOSUCH")
        with pytest.raises(FITSLoadError, match="no extension 99"):
            handler.resolve_extension(99)


def test_a_file_with_nothing_displayable_says_so(tmp_path):
    path = tmp_path / "empty.fits"
    fits.HDUList([fits.PrimaryHDU()]).writeto(path)
    with FITSHandler(str(path)) as handler, pytest.raises(FITSLoadError, match="no displayable"):
        handler.default_extension()


def test_a_cube_is_recognised_as_one(cube):
    with FITSHandler(str(cube)) as handler:
        assert handler.extensions()[0].is_cube


def test_a_degenerate_third_axis_is_not_a_cube(tmp_path):
    """`NAXIS3 = 1` is what many instruments write for a plain image."""
    path = tmp_path / "flat.fits"
    fits.PrimaryHDU(np.zeros((1, 8, 12), np.float32)).writeto(path)
    with FITSHandler(str(path)) as handler:
        assert not handler.extensions()[0].is_cube


def test_events_extnames_are_ds9s(events):
    assert "EVENTS" in EVENTS_EXTNAMES
    with FITSHandler(str(events)) as handler:
        info = handler.extensions()[1]
    assert info.kind is HDUKind.EVENTS
    assert info.displayable
    assert info.columns == ("X", "Y", "PHA")
    assert info.rows == 400


def test_a_table_without_x_and_y_is_not_displayable(tmp_path):
    path = tmp_path / "cat.fits"
    table = fits.BinTableHDU.from_columns(
        [fits.Column("RA", "D", array=np.zeros(3)), fits.Column("DEC", "D", array=np.zeros(3))],
        name="CATALOG",
    )
    fits.HDUList([fits.PrimaryHDU(), table]).writeto(path)
    with FITSHandler(str(path)) as handler:
        assert handler.extensions()[1].kind is HDUKind.TABLE
        assert not handler.extensions()[1].displayable


def test_a_healpix_table_is_recognised_but_not_displayable(tmp_path):
    path = tmp_path / "hpx.fits"
    table = fits.BinTableHDU.from_columns([fits.Column("SIGNAL", "E", array=np.zeros(12))], name="HPX")
    table.header["PIXTYPE"] = "HEALPIX"
    fits.HDUList([fits.PrimaryHDU(), table]).writeto(path)
    with FITSHandler(str(path)) as handler:
        info = handler.extensions()[1]
    assert info.kind is HDUKind.HEALPIX
    # Reprojecting HEALPIX is M9 work.
    assert not info.displayable


def test_a_compressed_image_is_displayable(tmp_path):
    path = tmp_path / "comp.fits"
    data = np.arange(16 * 20, dtype=np.int16).reshape(16, 20)
    fits.HDUList([fits.PrimaryHDU(), fits.CompImageHDU(data, name="COMP")]).writeto(path)
    with FITSHandler(str(path)) as handler:
        info = handler.extensions()[1]
        assert info.kind is HDUKind.COMPRESSED
        assert info.displayable
        assert info.dimensions == "20x16"
        image = handler.load_spec(parse(f"{path}[COMP]"))
    assert image.data.shape == (16, 20)


def test_classify_reads_only_the_header(mef):
    """It must not touch the data, so a lazily-opened file stays lazy."""
    with fits.open(str(mef), lazy_load_hdus=True) as hdus:
        info = classify(hdus[1], 1)
        assert info.shape == (16, 20)


# -- sections (M4-3) ---------------------------------------------------------


def test_section_cuts_and_shifts_the_reference_pixel(mef):
    with FITSHandler(str(mef)) as handler:
        whole = handler.load_spec(parse(f"{mef}[SCI]"))
        cut = handler.load_spec(parse(f"{mef}[SCI][5:14,3:10]"))
    assert cut.data.shape == (8, 10)
    assert cut.header["CRPIX1"] == whole.header["CRPIX1"] - 4
    assert cut.header["CRPIX2"] == whole.header["CRPIX2"] - 2


def test_a_section_keeps_the_sky_position_of_a_pixel(mef):
    """The point of shifting CRPIX: the same sky lands on the same data."""
    with FITSHandler(str(mef)) as handler:
        whole = handler.load_spec(parse(f"{mef}[SCI]"))
        cut = handler.load_spec(parse(f"{mef}[SCI][5:14,3:10]"))
    # Whole-image pixel (6, 4) zero-based is the cut's (2, 2).
    before = WCSHandler(whole.header).pixel_to_world(6.0, 4.0)
    after = WCSHandler(cut.header).pixel_to_world(2.0, 2.0)
    assert after[0] == pytest.approx(before[0])
    assert after[1] == pytest.approx(before[1])


def test_a_wildcard_axis_takes_the_whole_extent(mef):
    with FITSHandler(str(mef)) as handler:
        cut = handler.load_spec(parse(f"{mef}[SCI][*,3:10]"))
    assert cut.data.shape == (8, 20)


def test_a_section_is_clipped_to_the_data(mef):
    with FITSHandler(str(mef)) as handler:
        cut = handler.load_spec(parse(f"{mef}[SCI][1:9999,1:9999]"))
    assert cut.data.shape == (16, 20)


def test_a_cube_section_cuts_the_third_axis(cube):
    with FITSHandler(str(cube)) as handler:
        cut = handler.load_spec(parse(f"{cube}[*,*,2:4]"))
    assert cut.data.shape == (3, 8, 12)


def test_a_physical_section_goes_through_ltv(mef):
    image = ImageData(
        data=np.arange(16 * 20, dtype=np.float32).reshape(16, 20),
        header=fits.Header({"LTV1": -100.0, "LTM1_1": 1.0, "LTV2": 0.0, "LTM2_2": 1.0}),
    )
    section = parse("x[101:110,1:8p]").section
    cut = apply_section(image, section)
    # Physical 101 is image 1 with LTV1 = -100.
    assert cut.data.shape == (8, 10)
    assert cut.data[0, 0] == image.data[0, 0]


def test_a_section_leaves_the_original_alone(mef):
    with FITSHandler(str(mef)) as handler:
        whole = handler.load_spec(parse(f"{mef}[SCI]"))
        crpix = whole.header["CRPIX1"]
        apply_section(whole, Section())
    assert whole.header["CRPIX1"] == crpix


def test_the_section_block_factor_reaches_the_spec(mef):
    assert parse(f"{mef}[SCI][*,*,4]").section.block == 4


# -- events binning ----------------------------------------------------------


def test_binning_keeps_every_event(events):
    with FITSHandler(str(events)) as handler:
        image = handler.load_spec(parse(str(events)))
    # TLMIN..TLMAX inclusive: 32 by 16 pixels.
    assert image.data.shape == (16, 32)
    assert image.data.sum() == 400


def test_binning_honours_the_named_columns(events):
    with FITSHandler(str(events)) as handler:
        image = handler.load_spec(parse(f"{events}[bin=x,y]"))
    assert image.data.sum() == 400


def test_binning_an_unknown_column_says_which_exist(events):
    with (
        FITSHandler(str(events)) as handler,
        pytest.raises(FITSLoadError, match=r"the table has X, Y, PHA"),
    ):
        handler.load_spec(parse(f"{events}[bin=nosuch,y]"))


def test_a_binned_image_carries_the_columns_wcs(tmp_path):
    """DS9 builds a binned image's WCS from the columns' own TC* cards."""
    path = tmp_path / "wcsevt.fits"
    table = fits.BinTableHDU.from_columns(
        [
            fits.Column("X", "E", array=np.array([16.0])),
            fits.Column("Y", "E", array=np.array([8.0])),
        ],
        name="EVENTS",
    )
    table.header["TLMIN1"], table.header["TLMAX1"] = 1, 32
    table.header["TLMIN2"], table.header["TLMAX2"] = 1, 16
    for axis, (ctype, crval, crpix, cdelt) in enumerate(
        (("RA---TAN", 10.0, 16.0, -0.001), ("DEC--TAN", 20.0, 8.0, 0.001)), start=1
    ):
        table.header[f"TCTYP{axis}"] = ctype
        table.header[f"TCRVL{axis}"] = crval
        table.header[f"TCRPX{axis}"] = crpix
        table.header[f"TCDLT{axis}"] = cdelt
    fits.HDUList([fits.PrimaryHDU(), table]).writeto(path)

    with FITSHandler(str(path)) as handler:
        image = handler.load_spec(parse(str(path)))

    rows, columns = np.nonzero(image.data)
    sky = WCSHandler(image.header).pixel_to_world(float(columns[0]), float(rows[0]))
    assert sky[0] == pytest.approx(10.0)
    assert sky[1] == pytest.approx(20.0)


def test_a_table_without_limits_uses_its_own_range(tmp_path):
    path = tmp_path / "nolimits.fits"
    table = fits.BinTableHDU.from_columns(
        [
            fits.Column("X", "E", array=np.array([5.0, 9.0])),
            fits.Column("Y", "E", array=np.array([2.0, 4.0])),
        ],
        name="EVENTS",
    )
    fits.HDUList([fits.PrimaryHDU(), table]).writeto(path)
    with FITSHandler(str(path)) as handler:
        image = handler.load_spec(parse(str(path)))
    assert image.data.shape == (3, 5)
    assert image.data.sum() == 2


# -- cubes (M4-4) ------------------------------------------------------------


def test_is_cube_needs_three_real_axes():
    assert is_cube(np.zeros((3, 4, 5)))
    assert not is_cube(np.zeros((1, 4, 5)))
    assert not is_cube(np.zeros((4, 5)))
    assert not is_cube(None)


def test_axis_order_parses_ds9s_three_digits():
    assert AxisOrder.parse("321") == AxisOrder(3, 2, 1)
    assert AxisOrder.parse(AxisOrder(1, 3, 2)).y == 3
    assert AxisOrder().is_default


@pytest.mark.parametrize("text", ["113", "12", "1234", "abc", "023"])
def test_a_bad_axis_order_is_rejected(text):
    with pytest.raises(ValueError):
        AxisOrder.parse(text)


def test_ds9_offers_six_axis_orders():
    assert len(AXIS_ORDERS) == 6
    assert len({str(order) for order in AXIS_ORDERS}) == 6


def test_every_axis_order_slices_the_right_shape():
    # numpy (a3, a2, a1) = (4, 3, 2), so FITS axis 1 is 2 long.
    handler = CubeHandler(np.arange(24, dtype=np.float32).reshape(4, 3, 2))
    lengths = {1: 2, 2: 3, 3: 4}
    for order in AXIS_ORDERS:
        assert handler.depth(order) == lengths[order.z]
        plane = handler.get_slice(0, order)
        assert plane.shape == (lengths[order.y], lengths[order.x])


def test_every_axis_order_slices_the_right_values():
    """Checked against explicit FITS-order indexing, not against itself."""
    data = np.arange(24, dtype=np.float32).reshape(4, 3, 2)
    handler = CubeHandler(data)
    lengths = {1: 2, 2: 3, 3: 4}
    for order in AXIS_ORDERS:
        for channel in range(handler.depth(order)):
            plane = handler.get_slice(channel, order)
            for row in range(lengths[order.y]):
                for column in range(lengths[order.x]):
                    index = {order.x: column, order.y: row, order.z: channel}
                    assert plane[row, column] == data[index[3], index[2], index[1]]


def test_a_slice_outside_the_cube_is_rejected():
    handler = CubeHandler(np.zeros((3, 4, 5), np.float32))
    with pytest.raises(IndexError, match=r"outside 0\.\.2"):
        handler.get_slice(3)


def test_a_two_dimensional_array_is_not_a_cube():
    with pytest.raises(ValueError, match="expected a cube"):
        CubeHandler(np.zeros((4, 5)))


def test_slice_coordinate_reads_the_third_axis(cube):
    with FITSHandler(str(cube)) as handler:
        image = handler.load_spec(parse(str(cube)))
    handler = CubeHandler(image.data, image.header)
    assert handler.slice_coordinate(0) == (1000.0, "m/s")
    assert handler.slice_coordinate(3) == (1030.0, "m/s")


def test_slice_coordinate_is_none_without_a_scale():
    handler = CubeHandler(np.zeros((3, 4, 5), np.float32), fits.Header())
    assert handler.slice_coordinate(0) is None


def test_spectrum_walks_the_slice_axis():
    data = np.arange(24, dtype=np.float32).reshape(4, 3, 2)
    assert CubeHandler(data).get_spectrum(0, 0).tolist() == [0.0, 6.0, 12.0, 18.0]


def test_collapse_methods():
    data = np.arange(24, dtype=np.float32).reshape(4, 3, 2)
    handler = CubeHandler(data)
    assert handler.collapse(method="sum").shape == (3, 2)
    assert handler.collapse(0, 2, method="mean")[0, 0] == pytest.approx(3.0)
    with pytest.raises(ValueError, match="unknown collapse method"):
        handler.collapse(method="median")


def test_a_four_dimensional_file_is_sliced_on_the_third_axis():
    """DS9 takes the extra axes at their first element."""
    data = np.arange(2 * 3 * 4 * 5, dtype=np.float32).reshape(2, 3, 4, 5)
    plane = CubeHandler(data).get_slice(0)
    assert plane.shape == (4, 5)


# -- Open as loaders (M4-5, M4-6) --------------------------------------------


def test_extension_frames_returns_every_displayable_one(mef):
    with FITSHandler(str(mef)) as handler:
        images = fits_loaders.extension_images(handler)
    assert [info.name for info, _image in images] == ["SCI", "ERR", "DQ"]
    assert [float(image.data[0, 0]) for _info, image in images] == [1.0, 2.0, 3.0]


def test_extension_cube_stacks_them(mef):
    with FITSHandler(str(mef)) as handler:
        stacked = fits_loaders.extension_cube(handler)
    assert stacked.data.shape == (3, 16, 20)
    assert stacked.header["NAXIS3"] == 3


def test_extension_cube_refuses_mismatched_shapes(tmp_path):
    path = tmp_path / "ragged.fits"
    fits.HDUList(
        [
            fits.PrimaryHDU(),
            fits.ImageHDU(np.zeros((4, 5), np.float32), name="A"),
            fits.ImageHDU(np.zeros((6, 7), np.float32), name="B"),
        ]
    ).writeto(path)
    with FITSHandler(str(path)) as handler, pytest.raises(FITSLoadError, match="differ in shape"):
        fits_loaders.extension_cube(handler)


def test_extension_cube_needs_two_extensions(cube):
    with FITSHandler(str(cube)) as handler, pytest.raises(FITSLoadError, match="at least"):
        fits_loaders.extension_cube(handler)


def test_channels_from_three_extensions(mef):
    with FITSHandler(str(mef)) as handler:
        channels = fits_loaders.channel_images(handler)
    assert set(channels) == {"red", "green", "blue"}
    assert float(channels["blue"].data[0, 0]) == 3.0


def test_channels_from_a_cube(cube):
    with FITSHandler(str(cube)) as handler:
        channels = fits_loaders.channel_images(handler, from_cube=True)
    assert float(channels["red"].data[0, 0]) == 0.0
    assert float(channels["green"].data[0, 0]) == 96.0


def test_channels_from_a_cube_needs_a_cube(mef):
    with FITSHandler(str(mef)) as handler, pytest.raises(FITSLoadError, match="colour cube needs"):
        fits_loaders.channel_images(handler, from_cube=True)


def test_slice_image_drops_the_third_axis(cube):
    with FITSHandler(str(cube)) as handler:
        sliced = fits_loaders.slice_image(handler, parse(str(cube)), 2)
    assert sliced.data.shape == (8, 12)
    assert sliced.header["NAXIS"] == 2
    assert "CRVAL3" not in sliced.header


def test_slice_image_needs_a_cube(mef):
    with FITSHandler(str(mef)) as handler, pytest.raises(FITSLoadError, match="not a data cube"):
        fits_loaders.slice_image(handler, parse(f"{mef}[SCI]"), 0)


def test_slice_image_range(cube):
    with FITSHandler(str(cube)) as handler, pytest.raises(FITSLoadError, match=r"outside 1\.\.5"):
        fits_loaders.slice_image(handler, parse(str(cube)), 9)


# -- mosaics (M4-7) ----------------------------------------------------------


def _iraf_chip(x0: int, value: float) -> ImageData:
    header = fits.Header()
    header["DETSIZE"] = "[1:20,1:8]"
    header["DETSEC"] = f"[{x0}:{x0 + 9},1:8]"
    header["CRPIX1"], header["CRPIX2"] = 5.0, 4.0
    return ImageData(data=np.full((8, 10), value, np.float32), header=header)


def test_iraf_mosaic_places_chips_exactly():
    mosaic = build_mosaic([_iraf_chip(1, 1.0), _iraf_chip(11, 2.0)], MosaicKind.IRAF)
    assert mosaic.data.shape == (8, 20)
    assert mosaic.data[0, 0] == 1.0
    assert mosaic.data[0, 15] == 2.0
    assert not np.isnan(mosaic.data).any()


def test_iraf_mosaic_shifts_the_reference_pixel():
    mosaic = build_mosaic([_iraf_chip(11, 2.0)], MosaicKind.IRAF)
    # DETSIZE starts at 1 and the chip at 11, so CRPIX moves by 10.
    assert mosaic.data.shape == (8, 20)
    assert mosaic.header["CRPIX1"] == 15.0


def test_iraf_mosaic_leaves_gaps_blank():
    mosaic = build_mosaic([_iraf_chip(1, 1.0)], MosaicKind.IRAF)
    assert np.isnan(mosaic.data[0, 15])


def test_an_iraf_segment_fills_the_blanks():
    first = build_mosaic([_iraf_chip(1, 1.0)], MosaicKind.IRAF)
    second = build_mosaic([_iraf_chip(11, 2.0)], MosaicKind.IRAF, existing=first)
    assert second.data[0, 0] == 1.0
    assert second.data[0, 15] == 2.0


def test_iraf_mosaic_without_detsec_says_what_is_missing():
    image = ImageData(data=np.zeros((4, 4), np.float32), header=fits.Header())
    with pytest.raises(MosaicError, match="DETSEC"):
        build_mosaic([image], MosaicKind.IRAF)


#: Two tiles this far apart in right ascension do not overlap at all, so
#: every input pixel has an output pixel of its own.
DISJOINT_SEPARATION = 0.03


def _wcs_tile(crval1: float, value: float) -> ImageData:
    header = _wcs_header(20, 20, crval1=crval1)
    header["NAXIS"], header["NAXIS1"], header["NAXIS2"] = 2, 20, 20
    return ImageData(data=np.full((20, 20), value, np.float32), header=header)


def test_wcs_mosaic_covers_both_footprints():
    mosaic = build_mosaic([_wcs_tile(10.0, 1.0), _wcs_tile(10.0 + DISJOINT_SEPARATION, 2.0)], MosaicKind.WCS)
    assert mosaic.data.shape[1] > 20
    assert set(np.unique(mosaic.data[np.isfinite(mosaic.data)])) == {1.0, 2.0}


def test_wcs_mosaic_samples_each_input_pixel_once():
    """Nearest-neighbour at a matched pixel scale: no holes, no doubling.

    The canvas is sized from the corner pixels' outer edges, not their
    centres; measuring centre-to-centre used to clip the last row and column
    of every input.
    """
    mosaic = build_mosaic([_wcs_tile(10.0, 1.0), _wcs_tile(10.0 + DISJOINT_SEPARATION, 2.0)], MosaicKind.WCS)
    assert int(np.isfinite(mosaic.data).sum()) == 2 * 20 * 20
    assert int((mosaic.data == 1.0).sum()) == 20 * 20
    assert int((mosaic.data == 2.0).sum()) == 20 * 20


def test_a_later_tile_wins_an_overlap():
    """Overlapping tiles leave no holes, and the last one painted wins.

    The two tiles together cover fewer output pixels than they have input
    pixels, and the shortfall is entirely the first tile's -- the second
    keeps all four hundred of its own.
    """
    mosaic = build_mosaic([_wcs_tile(10.0, 1.0), _wcs_tile(10.005, 2.0)], MosaicKind.WCS)
    filled = int(np.isfinite(mosaic.data).sum())
    assert int((mosaic.data == 2.0).sum()) == 20 * 20
    assert int((mosaic.data == 1.0).sum()) == filled - 20 * 20
    assert filled < 2 * 20 * 20


def test_wcs_mosaic_without_a_wcs_says_what_is_missing():
    image = ImageData(data=np.zeros((4, 4), np.float32), header=fits.Header())
    with pytest.raises(MosaicError, match="usable WCS"):
        build_mosaic([image], MosaicKind.WCS)


def test_a_wcs_segment_merges_into_the_existing_grid():
    first = build_mosaic([_wcs_tile(10.0, 1.0)], MosaicKind.WCS)
    second = build_mosaic([_wcs_tile(10.0 + DISJOINT_SEPARATION, 2.0)], MosaicKind.WCS, existing=first)
    # The grid does not grow, so the frame's coordinates do not shift -- and
    # a segment landing entirely outside it contributes nothing.
    assert second.data.shape == first.data.shape
    assert int((second.data == 1.0).sum()) == 20 * 20


def test_a_wcs_segment_keeps_what_is_already_there():
    first = build_mosaic([_wcs_tile(10.0, 1.0), _wcs_tile(10.0 + DISJOINT_SEPARATION, 0.0)])
    filled_before = int((first.data == 1.0).sum())
    second = build_mosaic([_wcs_tile(10.0 + DISJOINT_SEPARATION, 2.0)], MosaicKind.WCS, existing=first)
    assert int((second.data == 1.0).sum()) == filled_before
    assert int((second.data == 2.0).sum()) == 20 * 20


def test_wfpc2_needs_a_four_plane_cube():
    image = ImageData(data=np.zeros((4, 5), np.float32), header=fits.Header())
    with pytest.raises(MosaicError, match="4-plane cube"):
        build_mosaic([image], MosaicKind.WFPC2)


def test_wfpc2_assembles_its_four_planes():
    header = _wcs_header(10, 10)
    header["NAXIS"], header["NAXIS1"], header["NAXIS2"], header["NAXIS3"] = 3, 10, 10, 4
    cube = ImageData(
        data=np.stack([np.full((10, 10), value, np.float32) for value in (1, 2, 3, 4)]),
        header=header,
    )
    mosaic = build_mosaic([cube], MosaicKind.WFPC2)
    assert mosaic.data.shape[0] >= 10


def test_a_mosaic_too_large_is_refused():
    """A wild WCS must not be allowed to ask for a terabyte of canvas."""
    header = _wcs_header(20, 20)
    header["NAXIS"], header["NAXIS1"], header["NAXIS2"] = 2, 20, 20
    # A degree-per-pixel tile beside an arcsecond-per-pixel one needs a
    # canvas of millions of pixels a side.
    coarse = _wcs_header(20, 20)
    coarse["NAXIS"], coarse["NAXIS1"], coarse["NAXIS2"] = 2, 20, 20
    coarse["CDELT1"], coarse["CDELT2"] = -1.0, 1.0
    with pytest.raises(MosaicError, match="over the"):
        build_mosaic(
            [
                ImageData(data=np.zeros((20, 20), np.float32), header=header),
                ImageData(data=np.zeros((20, 20), np.float32), header=coarse),
            ]
        )


def test_a_tile_that_cannot_be_projected_is_skipped():
    """A tile 180 degrees away has no tangent-plane position; it is dropped."""
    near = _wcs_tile(10.0, 1.0)
    far = _wcs_tile(190.0, 2.0)
    mosaic = build_mosaic([near, far], MosaicKind.WCS)
    assert int((mosaic.data == 1.0).sum()) == 20 * 20
    assert not (mosaic.data == 2.0).any()


def test_no_images_is_refused():
    with pytest.raises(MosaicError, match="no images"):
        build_mosaic([])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[1:20,1:8]", (0, 0, 20, 8)),
        ("[ 11 : 20 , 3 : 8 ]", (10, 2, 20, 8)),
        ("[20:11,8:3]", (10, 2, 20, 8)),
        ("nonsense", None),
        (None, None),
    ],
)
def test_parse_section_reads_iraf_sections(text, expected):
    placement = parse_section(text)
    if expected is None:
        assert placement is None
    else:
        assert (placement.x0, placement.y0, placement.x1, placement.y1) == expected


# -- alternate WCS -----------------------------------------------------------


def test_alternate_wcs_keys_are_found(mef):
    with FITSHandler(str(mef)) as handler:
        assert available_alternates(handler.get_header(1)) == ()


def test_an_alternate_wcs_is_read_in_its_own_frame(tmp_path):
    path = tmp_path / "alt.fits"
    header = _wcs_header(10, 10)
    header.update(
        {
            "CTYPE1A": "GLON-TAN",
            "CTYPE2A": "GLAT-TAN",
            "CRVAL1A": 104.85,
            "CRVAL2A": 68.56,
            "CRPIX1A": 5.5,
            "CRPIX2A": 5.5,
            "CDELT1A": -0.001,
            "CDELT2A": 0.001,
        }
    )
    fits.PrimaryHDU(np.zeros((10, 10), np.float32), header).writeto(path)
    with FITSHandler(str(path)) as handler:
        assert available_alternates(handler.get_header(0)) == ("a",)
        primary = WCSHandler(handler.get_header(0)).pixel_to_world(5.0, 5.0)
        alternate = WCSHandler(handler.get_header(0), key="a").pixel_to_world(5.0, 5.0)
    assert primary[0] == pytest.approx(10.0, abs=0.01)
    assert alternate[0] == pytest.approx(104.85, abs=0.01)
