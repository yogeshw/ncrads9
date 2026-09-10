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

"""DS9's Import, Export and Create Movie (M9-13, M9-14, M9-15)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.io import array_reader, envi_writer, movie, nrrd_writer, raster
from ncrads9.io.array_reader import ArraySpec, ArraySpecError
from ncrads9.io.envi_reader import ENVIReader
from ncrads9.io.nrrd_reader import NRRDReader

SIZE = 16


# -- DS9's array specification -----------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # The examples out of DS9's own documentation (`file.html`).
        ("[xdim=512,ydim=512,zdim=1,bitpix=16]", ArraySpec(512, 512, 1, 16)),
        ("[dim=256,bitpix=-32,skip=4]", ArraySpec(256, 256, 1, -32, 4)),
        ("[dim=512,bitpix=32,arch=little]", ArraySpec(512, 512, 1, 32, 0, False)),
        ("[array(s512)]", ArraySpec(512, 512, 1, 16)),
        ("[array(r256:4)]", ArraySpec(256, 256, 1, -32, 4)),
        ("[array(i512l)]", ArraySpec(512, 512, 1, 32, 0, False)),
    ],
)
def test_ds9s_own_array_examples_parse(text, expected):
    assert array_reader.parse_spec(text) == expected


def test_both_spellings_of_endian_are_read():
    assert array_reader.parse_spec("[dim=8,endian=littleendian]").big_endian is False
    assert array_reader.parse_spec("[dim=8,arch=bigendian]").big_endian is True


def test_the_compact_form_takes_three_dimensions():
    assert array_reader.parse_spec("[array(r64.32.3)]") == ArraySpec(64, 32, 3, -32)


def test_dims_is_the_same_as_dim():
    assert array_reader.parse_spec("[dims=128]").xdim == 128


def test_a_specification_with_no_dimensions_is_refused():
    with pytest.raises(ArraySpecError, match="needs xdim and ydim"):
        array_reader.parse_spec("[bitpix=-32]")


def test_a_bitpix_that_is_not_ds9s_is_refused():
    with pytest.raises(ArraySpecError, match="bitpix"):
        array_reader.parse_spec("[dim=8,bitpix=7]")


def test_something_that_is_not_a_number_is_refused():
    with pytest.raises(ArraySpecError, match="not a number"):
        array_reader.parse_spec("[xdim=wide,ydim=8]")


def test_an_unknown_compact_type_is_refused():
    with pytest.raises(ArraySpecError, match="array type"):
        array_reader.parse_spec("[array(z512)]")


def test_a_specification_fills_in_from_the_defaults():
    """Which is what `$DS9_ARRAY` is for: the dimensions once, in the
    environment, and the filename says nothing."""
    default = ArraySpec(256, 256, 1, -32)
    assert array_reader.parse_spec("[bitpix=16]", default) == ArraySpec(256, 256, 1, 16)


def test_the_environment_variable_is_read(monkeypatch):
    monkeypatch.setenv("DS9_ARRAY", "[dim=256,bitpix=-32]")
    assert array_reader.environment_spec() == ArraySpec(256, 256, 1, -32)


def test_a_nonsense_environment_variable_is_ignored(monkeypatch):
    monkeypatch.setenv("DS9_ARRAY", "[not a spec]")
    assert array_reader.environment_spec() is None


def test_no_environment_variable_is_no_default(monkeypatch):
    monkeypatch.delenv("DS9_ARRAY", raising=False)
    assert array_reader.environment_spec() is None


def test_the_shape_and_the_type_follow_the_specification():
    spec = ArraySpec(4, 3, 2, 16, big_endian=False)
    assert spec.shape == (2, 3, 4)
    assert spec.dtype == np.dtype("<i2")
    assert spec.expected_bytes == 4 * 3 * 2 * 2


# -- reading and writing raw arrays --------------------------------------------------


def test_a_raw_array_round_trips(tmp_path):
    data = np.arange(12.0, dtype=np.float32).reshape(3, 4)
    spec = array_reader.write(tmp_path / "a.arr", data)
    assert spec == ArraySpec(4, 3, 1, -32)

    back = array_reader.read(tmp_path / "a.arr", spec)
    assert back.dtype == np.float32
    assert np.array_equal(back, data)


def test_a_raw_array_round_trips_little_endian(tmp_path):
    data = np.arange(6, dtype=np.int16).reshape(2, 3)
    spec = array_reader.write(tmp_path / "a.arr", data, big_endian=False)
    assert np.array_equal(array_reader.read(tmp_path / "a.arr", spec), data)


def test_the_specification_can_ride_in_the_filename(tmp_path):
    data = np.arange(12.0, dtype=np.float32).reshape(3, 4)
    array_reader.write(tmp_path / "a.arr", data)
    path = f"{tmp_path / 'a.arr'}[xdim=4,ydim=3,bitpix=-32]"
    assert np.array_equal(array_reader.read(path), data)


def test_a_header_is_stepped_over(tmp_path):
    """DS9's `skip`: a raw array behind somebody else's header."""
    data = np.arange(6, dtype=np.int16)
    path = tmp_path / "with_header.arr"
    path.write_bytes(b"XXXX" + data.astype(">i2").tobytes())
    read = array_reader.read(path, ArraySpec(3, 2, bitpix=16, skip=4))
    assert np.array_equal(read.ravel(), data)


def test_a_file_too_small_for_its_specification_is_refused(tmp_path):
    path = tmp_path / "short.arr"
    path.write_bytes(b"\\x00" * 8)
    with pytest.raises(ArraySpecError, match="needs"):
        array_reader.read(path, ArraySpec(64, 64, bitpix=-32))


def test_reading_with_no_specification_at_all_says_what_to_do(tmp_path, monkeypatch):
    monkeypatch.delenv("DS9_ARRAY", raising=False)
    path = tmp_path / "a.arr"
    path.write_bytes(b"\\x00" * 64)
    with pytest.raises(ArraySpecError, match="DS9_ARRAY"):
        array_reader.read(path)


def test_a_type_with_no_bitpix_goes_out_as_float(tmp_path):
    """Rather than the export being refused."""
    data = np.arange(4, dtype=np.float16).reshape(2, 2)
    spec = array_reader.write(tmp_path / "a.arr", data)
    assert spec.bitpix == -32


def test_a_cube_keeps_its_depth(tmp_path):
    data = np.arange(24.0, dtype=np.float32).reshape(2, 3, 4)
    spec = array_reader.write(tmp_path / "c.arr", data)
    assert (spec.xdim, spec.ydim, spec.zdim) == (4, 3, 2)
    assert array_reader.read(tmp_path / "c.arr", spec).shape == (2, 3, 4)


# -- NRRD and ENVI ------------------------------------------------------------------


@pytest.mark.parametrize("big_endian", [True, False])
def test_nrrd_round_trips_either_way_round(tmp_path, big_endian):
    """The reader ignored the header's `endian` until M9-13, which read
    every value wrong on half the machines while the shape stayed right."""
    data = np.arange(12.0, dtype=np.float32).reshape(3, 4)
    nrrd_writer.write(tmp_path / "x.nrrd", data, big_endian=big_endian)
    assert np.array_equal(NRRDReader(tmp_path / "x.nrrd").read_data(), data)


def test_a_gzipped_nrrd_round_trips(tmp_path):
    data = np.arange(12.0, dtype=np.float32).reshape(3, 4)
    nrrd_writer.write(tmp_path / "x.nrrd", data, compress=True)
    assert "encoding: gzip" in (tmp_path / "x.nrrd").read_bytes().decode("ascii", "replace")
    assert np.array_equal(NRRDReader(tmp_path / "x.nrrd").read_data(), data)


def test_nrrds_sizes_are_written_fastest_axis_first(tmp_path):
    nrrd_writer.write(tmp_path / "x.nrrd", np.zeros((3, 4), dtype=np.float32))
    text = (tmp_path / "x.nrrd").read_bytes().decode("ascii", "replace")
    assert "sizes: 4 3" in text


def test_a_type_nrrd_has_no_name_for_goes_out_as_float(tmp_path):
    nrrd_writer.write(tmp_path / "x.nrrd", np.zeros((2, 2), dtype=np.float16))
    assert "type: float" in (tmp_path / "x.nrrd").read_bytes().decode("ascii", "replace")


@pytest.mark.parametrize("big_endian", [True, False])
def test_envi_round_trips_either_way_round(tmp_path, big_endian):
    data = np.arange(12.0, dtype=np.float32).reshape(3, 4)
    envi_writer.write(tmp_path / "x.img", data, big_endian=big_endian)
    read = ENVIReader(tmp_path / "x.img").read_data()
    assert np.array_equal(read.reshape(3, 4), data)


def test_envi_writes_its_header_beside_the_data(tmp_path):
    _data, header = envi_writer.write(tmp_path / "x.img", np.zeros((3, 4), dtype=np.float32))
    assert header == tmp_path / "x.hdr"
    text = header.read_text()
    assert "samples = 4" in text
    assert "lines = 3" in text


def test_envis_header_can_be_put_somewhere_else(tmp_path):
    """DS9's Export -> ENVI asks for both names."""
    _data, header = envi_writer.write(
        tmp_path / "x.img", np.zeros((2, 2), dtype=np.float32), header=tmp_path / "other.hdr"
    )
    assert header == tmp_path / "other.hdr"


# -- the four raster formats --------------------------------------------------------


@pytest.mark.parametrize("name", ["png", "gif", "tiff", "jpeg"])
def test_a_picture_round_trips_the_right_way_up(tmp_path, name):
    """A picture counts rows from the top and FITS from the bottom, so a
    photograph imported without the flip is upside down -- and exported
    right way up again, which is how the mistake hides."""
    rgb = np.zeros((4, 6, 3), dtype=np.uint8)
    rgb[0, 0] = (255, 255, 255)
    path = raster.write(tmp_path / f"x.{name}", rgb, name)

    read = raster.read(path)
    assert read.shape == (4, 6)
    assert read[0, 0] > read[3, 5]


def test_a_picture_can_be_read_as_three_planes(tmp_path):
    rgb = np.zeros((4, 6, 3), dtype=np.uint8)
    rgb[0, 0] = (255, 0, 0)
    path = raster.write(tmp_path / "x.png", rgb, "png")

    planes = raster.read(path, colour=True)
    assert planes.shape == (3, 4, 6)
    assert planes[0, 0, 0] == 255
    assert planes[1, 0, 0] == 0


def test_a_greyscale_array_can_be_written(tmp_path):
    raster.write(tmp_path / "x.png", np.zeros((4, 4), dtype=np.uint8), "png")
    assert raster.read(tmp_path / "x.png").shape == (4, 4)


def test_a_format_ds9_does_not_export_is_refused(tmp_path):
    with pytest.raises(ValueError, match="not a raster format"):
        raster.write(tmp_path / "x.bmp", np.zeros((2, 2, 3), dtype=np.uint8), "bmp")


def test_each_format_has_a_file_filter():
    assert "*.png" in raster.file_filter("png")
    assert "*.tif" in raster.file_filter("tiff")


# -- the movie ----------------------------------------------------------------------


def test_a_blink_movie_is_one_image_per_frame():
    images = [np.zeros((4, 4, 3), np.uint8), np.full((4, 4, 3), 255, np.uint8)]
    assert len(movie.sequence(images, "blink")) == 2


def test_a_fade_movie_blends_between_them_and_back():
    images = [np.zeros((4, 4, 3), np.uint8), np.full((4, 4, 3), 255, np.uint8)]
    run = movie.sequence(images, "fade")
    assert len(run) == 1 + 2 * movie.FADE_STEPS
    # Somewhere in the middle is a grey that is in neither original.
    assert any(0 < int(image[0, 0, 0]) < 255 for image in run)


def test_a_fade_of_one_image_is_that_image():
    images = [np.zeros((4, 4, 3), np.uint8)]
    assert len(movie.sequence(images, "fade")) == 1


def test_frames_of_different_sizes_are_padded_not_refused():
    """Two frames of two files are two sizes, and no writer takes a run
    that changes shape."""
    padded = movie.frames_of([np.ones((4, 4, 3), np.uint8), np.ones((6, 8, 3), np.uint8)])
    assert {image.shape for image in padded} == {(6, 8, 3)}


def test_a_greyscale_render_is_padded_into_colour():
    padded = movie.frames_of([np.ones((4, 4), np.uint8)])
    assert padded[0].shape == (4, 4, 3)


def test_an_animated_gif_is_written(tmp_path):
    images = [np.zeros((4, 4, 3), np.uint8), np.full((4, 4, 3), 255, np.uint8)]
    path = movie.write(tmp_path / "m.gif", images, "gif", "blink", 10)
    assert path.stat().st_size > 0

    from PIL import Image

    with Image.open(path) as opened:
        assert opened.n_frames == 2
        assert opened.info["duration"] == 100


def test_a_movie_of_nothing_is_refused(tmp_path):
    with pytest.raises(movie.MovieError, match="nothing"):
        movie.write(tmp_path / "m.gif", [], "gif")


def test_a_kind_of_movie_ds9_does_not_make_is_refused(tmp_path):
    with pytest.raises(movie.MovieError, match="not a kind"):
        movie.write(tmp_path / "m.avi", [np.zeros((4, 4, 3), np.uint8)], "avi")


def test_an_mpeg_without_ffmpeg_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(movie, "have_ffmpeg", lambda: False)
    with pytest.raises(movie.MovieError, match="ffmpeg"):
        movie.write(tmp_path / "m.mpg", [np.zeros((4, 4, 3), np.uint8)], "mpeg")


# -- the menus over them --------------------------------------------------------------


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
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32)).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    yield window
    window.close()


def test_the_import_and_export_menus_are_ds9s_ten_formats(main_window):
    expected = ["array", "nrrd", "envi", "rgb_array", "hsv_array", "hls_array", "gif", "tiff", "jpeg", "png"]
    assert [name for name in main_window.menu_bar.export_actions] == expected
    # Import has the same ten plus DS9's Slice cascade over the four rasters.
    assert [name for name in main_window.menu_bar.import_actions if not name.startswith("slice_")] == expected
    assert [name for name in main_window.menu_bar.import_actions if name.startswith("slice_")] == [
        "slice_gif",
        "slice_tiff",
        "slice_jpeg",
        "slice_png",
    ]


def test_importing_a_png_puts_its_pixels_on_a_frame(main_window, tmp_path):
    rgb = np.zeros((4, 6, 3), dtype=np.uint8)
    rgb[0, 0] = (255, 255, 255)
    raster.write(tmp_path / "photo.png", rgb, "png")

    assert main_window.file.import_file("png", str(tmp_path / "photo.png")) is True
    data = main_window.frame_manager.current_frame.image_data
    assert data.shape == (4, 6)
    # And it has no file behind it, so Save would ask where to put it.
    assert main_window.frame_manager.current_frame.filepath is None


def test_importing_a_raw_array_with_its_spec_in_the_name(main_window, tmp_path):
    data = np.arange(12.0, dtype=np.float32).reshape(3, 4)
    array_reader.write(tmp_path / "a.arr", data)
    spec = f"{tmp_path / 'a.arr'}[xdim=4,ydim=3,bitpix=-32]"

    assert main_window.file.import_file("array", spec) is True
    assert np.array_equal(main_window.frame_manager.current_frame.image_data, data)


def test_importing_a_raw_array_asks_when_the_name_says_nothing(main_window, tmp_path, monkeypatch):
    from ncrads9.ui.dialogs import array_dialog

    data = np.arange(12.0, dtype=np.float32).reshape(3, 4)
    array_reader.write(tmp_path / "a.arr", data)
    monkeypatch.setattr(array_dialog.ArrayDialog, "choose", lambda self: ArraySpec(4, 3, 1, -32))

    assert main_window.file.import_file("array", str(tmp_path / "a.arr")) is True
    assert main_window.frame_manager.current_frame.image_data.shape == (3, 4)


def test_cancelling_the_array_dialog_imports_nothing(main_window, tmp_path, monkeypatch):
    from ncrads9.ui.dialogs import array_dialog

    array_reader.write(tmp_path / "a.arr", np.zeros((2, 2), dtype=np.float32))
    monkeypatch.setattr(array_dialog.ArrayDialog, "choose", lambda self: None)
    assert main_window.file.import_file("array", str(tmp_path / "a.arr")) is False


def test_importing_nrrd_and_envi(main_window, tmp_path):
    data = np.arange(12.0, dtype=np.float32).reshape(3, 4)
    nrrd_writer.write(tmp_path / "x.nrrd", data)
    envi_writer.write(tmp_path / "x.img", data)

    assert main_window.file.import_file("nrrd", str(tmp_path / "x.nrrd")) is True
    assert np.array_equal(main_window.frame_manager.current_frame.image_data, data)
    assert main_window.file.import_file("envi", str(tmp_path / "x.img")) is True


def test_importing_something_unreadable_is_reported(main_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    bad = tmp_path / "bad.png"
    bad.write_text("not a picture")
    assert main_window.file.import_file("png", str(bad)) is False


def test_a_colour_array_import_makes_a_colour_frame(main_window, tmp_path, monkeypatch):
    from ncrads9.ui.dialogs import array_dialog

    planes = np.arange(36.0, dtype=np.float32).reshape(3, 3, 4)
    array_reader.write(tmp_path / "c.arr", planes)
    monkeypatch.setattr(array_dialog.ArrayDialog, "choose", lambda self: ArraySpec(4, 3, 3, -32))

    assert main_window.file.import_file("rgb_array", str(tmp_path / "c.arr")) is True
    assert main_window.frame_manager.current_frame.frame_type == "rgb"


def test_exporting_the_data_as_a_raw_array(main_window, tmp_path, monkeypatch):
    from ncrads9.ui.dialogs import array_dialog

    monkeypatch.setattr(array_dialog.ArrayDialog, "choose", lambda self: ArraySpec(1, 1))
    path = tmp_path / "out.arr"
    assert main_window.file.export_file("array", str(path)) is True

    read = array_reader.read(path, ArraySpec(SIZE, SIZE, bitpix=-32))
    assert np.array_equal(read, main_window.frame_manager.current_frame.image_data)


def test_the_array_export_says_how_to_read_it_back(main_window, tmp_path, monkeypatch):
    """A raw array carries no header, so if we do not say, nobody knows."""
    from ncrads9.ui.dialogs import array_dialog

    monkeypatch.setattr(array_dialog.ArrayDialog, "choose", lambda self: ArraySpec(1, 1))
    main_window.file.export_file("array", str(tmp_path / "out.arr"))
    message = main_window.status_bar.currentMessage()
    assert f"xdim={SIZE}" in message
    assert "bitpix=-32" in message


def test_exporting_nrrd_and_envi(main_window, tmp_path, monkeypatch):
    from ncrads9.ui.dialogs import array_dialog

    monkeypatch.setattr(array_dialog.ArrayDialog, "choose", lambda self: ArraySpec(1, 1))
    assert main_window.file.export_file("nrrd", str(tmp_path / "out.nrrd")) is True
    assert np.array_equal(
        NRRDReader(tmp_path / "out.nrrd").read_data(),
        main_window.frame_manager.current_frame.image_data,
    )
    assert main_window.file.export_file("envi", str(tmp_path / "out.img")) is True
    assert (tmp_path / "out.hdr").is_file()


def test_exporting_a_raster_writes_the_rendered_picture(main_window, tmp_path):
    """Export writes what is rendered, because a GIF has no room for a
    stretch."""
    path = tmp_path / "out.png"
    assert main_window.file.export_file("png", str(path)) is True
    assert raster.read(path).shape[0] > 0


def test_exporting_with_no_image_is_refused(main_window, tmp_path):
    main_window.frame_controller.new_frame()
    assert main_window.file.export_file("png", str(tmp_path / "x.png")) is False
    assert "No image to export" in main_window.status_bar.currentMessage()


def test_a_colour_array_export_writes_three_planes(main_window, tmp_path, monkeypatch):
    from ncrads9.ui.dialogs import array_dialog

    monkeypatch.setattr(array_dialog.ArrayDialog, "choose", lambda self: ArraySpec(1, 1))
    path = tmp_path / "c.arr"
    assert main_window.file.export_file("rgb_array", str(path)) is True
    read = array_reader.read(path, ArraySpec(SIZE, SIZE, 3, -32))
    assert read.shape == (3, SIZE, SIZE)


def test_save_image_writes_the_four_raster_formats(main_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    for name in ("png", "gif", "tiff", "jpeg"):
        path = tmp_path / f"view.{name}"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, chosen=str(path), **k: (chosen, ""))
        main_window.menu_bar.save_image_actions[name].trigger()
        assert path.is_file(), name


def test_save_image_as_eps_still_says_it_is_coming(main_window):
    main_window.menu_bar.save_image_actions["eps"].trigger()
    assert "M9-18" in main_window.status_bar.currentMessage()


# -- Create Movie -----------------------------------------------------------------------


def test_a_frames_movie_has_one_image_per_frame(main_window, tmp_path):
    main_window.frame_controller.new_frame()
    rows, columns = np.indices((SIZE, SIZE))
    path = tmp_path / "second.fits"
    fits.PrimaryHDU(data=(rows * columns).astype(np.float32)).writeto(path)
    main_window.display.load_fits(str(path))

    out = tmp_path / "movie.gif"
    assert (
        main_window.file.create_movie(
            str(out), {"type": "gif", "action": "frame", "transition": "blink", "delay": 5}
        )
        is True
    )
    from PIL import Image

    with Image.open(out) as opened:
        assert opened.n_frames == 2


def test_a_slice_movie_has_one_image_per_slice(main_window, tmp_path):
    cube = np.random.default_rng(1).normal(size=(4, SIZE, SIZE)).astype(np.float32)
    path = tmp_path / "cube.fits"
    fits.PrimaryHDU(data=cube).writeto(path)
    main_window.display.load_fits(str(path))

    out = tmp_path / "slices.gif"
    assert (
        main_window.file.create_movie(
            str(out), {"type": "gif", "action": "slice", "transition": "blink", "delay": 5}
        )
        is True
    )
    from PIL import Image

    with Image.open(out) as opened:
        assert opened.n_frames == 4


def test_a_slice_movie_puts_the_slice_back(main_window, tmp_path):
    """Making a movie should not move the view."""
    cube = np.zeros((4, SIZE, SIZE), dtype=np.float32)
    path = tmp_path / "cube.fits"
    fits.PrimaryHDU(data=cube).writeto(path)
    main_window.display.load_fits(str(path))
    main_window.frame_controller.set_slice(2)

    main_window.file.create_movie(
        str(tmp_path / "m.gif"), {"type": "gif", "action": "slice", "transition": "blink", "delay": 5}
    )
    assert main_window.frame_manager.current_frame.slice_index == 2


def test_a_3d_movie_says_which_milestone_it_needs(main_window, tmp_path):
    assert main_window.file.create_movie(str(tmp_path / "m.gif"), {"type": "gif", "action": "3d"}) is False
    assert "M9-21" in main_window.status_bar.currentMessage()


def test_a_movie_of_an_empty_frame_is_refused(main_window, tmp_path):
    main_window.frame_controller.new_frame()
    assert main_window.file.create_movie(str(tmp_path / "m.gif"), {"type": "gif"}) is False


def test_an_mpeg_without_ffmpeg_is_reported_not_raised(main_window, tmp_path, monkeypatch):
    monkeypatch.setattr(movie, "have_ffmpeg", lambda: False)
    assert (
        main_window.file.create_movie(
            str(tmp_path / "m.mpg"), {"type": "mpeg", "action": "frame", "delay": 5}
        )
        is False
    )
    assert "ffmpeg" in main_window.status_bar.currentMessage()


def test_the_movie_dialog_offers_what_the_frame_supports(main_window):
    from ncrads9.ui.dialogs.movie_dialog import MovieDialog

    plain = MovieDialog(main_window, is_cube=False)
    assert plain._slices.isEnabled() is False
    assert plain._three_d.isEnabled() is False
    plain.close()

    cube = MovieDialog(main_window, is_cube=True)
    assert cube._slices.isEnabled() is True
    cube.close()


def test_the_delay_is_only_for_a_blinking_gif(main_window):
    """An MPEG has one frame rate rather than a delay per image, and a fade
    sets its own pace; DS9 greys the box in both cases."""
    from ncrads9.ui.dialogs.movie_dialog import MovieDialog

    dialog = MovieDialog(main_window)
    assert dialog._delay_group.isEnabled() is True
    dialog._fade.setChecked(True)
    assert dialog._delay_group.isEnabled() is False
    dialog._blink.setChecked(True)
    if dialog._mpeg.isEnabled():
        dialog._mpeg.setChecked(True)
        assert dialog._delay_group.isEnabled() is False
    dialog.close()


def test_the_dialogs_settings_are_what_the_movie_takes(main_window):
    from ncrads9.ui.dialogs.movie_dialog import MovieDialog

    dialog = MovieDialog(main_window)
    dialog._fade.setChecked(True)
    settings = dialog.settings()
    assert settings == {"type": "gif", "action": "frame", "transition": "fade", "delay": 10}
    dialog.close()
