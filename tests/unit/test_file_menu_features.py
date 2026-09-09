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


"""The File menu in a real window: Open, Open as, Save and Save as.

`test_fits_coverage.py` covers the loaders on their own; this drives them
through `FileController` and checks what lands on the frame.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.core.cube_handler import CubeHandler
from ncrads9.core.mosaic import MosaicKind
from ncrads9.ui.controllers.file import COLOUR_LOADERS, DEFERRED_IMAGE_FORMATS, MOSAIC_LOADERS
from ncrads9.ui.dialogs.open_dialog import HDUChoice, HDUSelection, OpenDialog
from ncrads9.ui.main_window import MainWindow
from ncrads9.utils.preferences import Preferences


@pytest.fixture
def main_window(qapp, monkeypatch):
    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    window._rebuild_image_viewer(False)
    yield window
    window.close()


def _header(width: int, height: int, crval1: float = 10.0) -> fits.Header:
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
            "OBJECT": "M51",
            "BUNIT": "Jy/beam",
        }
    )


@pytest.fixture
def mef(tmp_path):
    path = tmp_path / "mef.fits"
    header = _header(20, 16)
    fits.HDUList(
        [
            fits.PrimaryHDU(),
            fits.ImageHDU(np.full((16, 20), 1.0, np.float32), header, name="SCI"),
            fits.ImageHDU(np.full((16, 20), 2.0, np.float32), header, name="ERR"),
        ]
    ).writeto(path)
    return path


@pytest.fixture
def cube(tmp_path):
    path = tmp_path / "cube.fits"
    header = _header(12, 8)
    header["CRVAL3"], header["CDELT3"], header["CRPIX3"] = 1000.0, 10.0, 1.0
    header["CUNIT3"] = "m/s"
    fits.PrimaryHDU(np.arange(5 * 8 * 12, dtype=np.float32).reshape(5, 8, 12), header).writeto(path)
    return path


@pytest.fixture
def single(tmp_path):
    path = tmp_path / "single.fits"
    fits.PrimaryHDU(np.arange(200, dtype=np.float32).reshape(10, 20), _header(20, 10)).writeto(path)
    return path


# -- loading a specification -------------------------------------------------


def test_loading_a_plain_file(main_window, single):
    main_window.display.load_fits(str(single))
    frame = main_window.frame_manager.current_frame
    assert frame.image_data.shape == (10, 20)
    assert frame.filepath == single
    assert frame.file_spec is None
    assert frame.hdu_index == 0


def test_loading_a_named_extension(main_window, mef):
    main_window.display.load_fits(f"{mef}[ERR]")
    frame = main_window.frame_manager.current_frame
    assert float(frame.image_data[0, 0]) == 2.0
    assert frame.hdu_index == 2
    assert frame.file_spec == f"{mef}[ERR]"


def test_the_title_names_the_extension(main_window, mef):
    main_window.display.load_fits(f"{mef}[ERR]")
    assert "mef.fits[ERR]" in main_window.windowTitle()


def test_loading_a_section(main_window, mef):
    main_window.display.load_fits(f"{mef}[SCI][5:14,3:10]")
    frame = main_window.frame_manager.current_frame
    assert frame.image_data.shape == (8, 10)


def test_a_sections_block_factor_reaches_the_frame(main_window, mef):
    main_window.display.load_fits(f"{mef}[SCI][*,*,4]")
    assert main_window.frame_manager.current_frame.block_factor == 4


def test_the_default_extension_is_chosen_when_none_is_named(main_window, mef):
    main_window.display.load_fits(str(mef))
    assert main_window.frame_manager.current_frame.hdu_index == 1


def test_loading_a_cube_shows_its_first_slice(main_window, cube):
    main_window.display.load_fits(str(cube))
    frame = main_window.frame_manager.current_frame
    assert frame.image_data.shape == (8, 12)
    assert frame.image.data.shape == (5, 8, 12)
    assert frame.slice_index == 0
    assert frame.axis_order == "123"


def test_a_bad_specification_raises(main_window, single):
    from ncrads9.core.file_spec import FileSpecError

    with pytest.raises(FileSpecError):
        main_window.display.load_fits(f"{single}[2][3]")


def test_a_missing_extension_raises(main_window, mef):
    from ncrads9.core.fits_handler import FITSLoadError

    with pytest.raises(FITSLoadError):
        main_window.display.load_fits(f"{mef}[NOSUCH]")


# -- the extension chooser (M4-2) --------------------------------------------


def test_a_single_extension_file_is_not_queried(main_window, single, monkeypatch):
    """No ambiguity, no dialog."""
    monkeypatch.setattr(OpenDialog, "exec", lambda self: pytest.fail("dialog shown"))
    main_window.file.open_file(filepath=str(single))
    assert main_window.frame_manager.current_frame.image_data is not None


def test_a_named_extension_is_not_queried(main_window, mef, monkeypatch):
    monkeypatch.setattr(OpenDialog, "exec", lambda self: pytest.fail("dialog shown"))
    main_window.file.open_file(filepath=f"{mef}[ERR]")
    assert main_window.frame_manager.current_frame.hdu_index == 2


def test_the_preference_turns_the_prompt_off(main_window, mef, monkeypatch):
    monkeypatch.setattr(OpenDialog, "exec", lambda self: pytest.fail("dialog shown"))
    monkeypatch.setattr(
        Preferences, "get", lambda self, key, default=None: False if key == "prompt_for_hdu" else default
    )
    main_window.file.open_file(filepath=str(mef))
    # DS9's own behaviour: the first displayable extension, silently.
    assert main_window.frame_manager.current_frame.hdu_index == 1


def test_choosing_an_extension_loads_it(main_window, mef, monkeypatch):
    monkeypatch.setattr(OpenDialog, "exec", lambda self: 1)
    monkeypatch.setattr(OpenDialog, "selection", lambda self: HDUSelection(HDUChoice.SINGLE, 2))
    main_window.file.open_file(filepath=str(mef))
    assert main_window.frame_manager.current_frame.hdu_index == 2


def test_cancelling_the_chooser_loads_nothing(main_window, mef, monkeypatch):
    monkeypatch.setattr(OpenDialog, "exec", lambda self: 0)
    main_window.file.open_file(filepath=str(mef))
    assert main_window.frame_manager.current_frame.image_data is None


def test_choosing_all_frames_from_the_chooser(main_window, mef, monkeypatch):
    monkeypatch.setattr(OpenDialog, "exec", lambda self: 1)
    monkeypatch.setattr(OpenDialog, "selection", lambda self: HDUSelection(HDUChoice.ALL_FRAMES))
    main_window.file.open_file(filepath=str(mef))
    assert main_window.frame_manager.num_frames == 2


def test_choosing_all_as_a_cube_from_the_chooser(main_window, mef, monkeypatch):
    monkeypatch.setattr(OpenDialog, "exec", lambda self: 1)
    monkeypatch.setattr(OpenDialog, "selection", lambda self: HDUSelection(HDUChoice.ALL_CUBE))
    main_window.file.open_file(filepath=str(mef))
    frame = main_window.frame_manager.current_frame
    assert frame.image.data.shape == (2, 16, 20)
    assert frame.image_data.shape == (16, 20)


def test_the_chooser_only_offers_displayable_rows(qapp, mef):
    from ncrads9.core.fits_handler import FITSHandler

    with FITSHandler(str(mef)) as handler:
        dialog = OpenDialog(mef, handler.extensions(), 1)
    assert [info.name for info in dialog.displayable] == ["SCI", "ERR"]
    assert dialog.stackable


# -- Open as (M4-5, M4-6, M4-7) ----------------------------------------------


def test_open_as_slice(main_window, cube, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog

    from ncrads9.core.file_spec import parse

    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda *a, **k: (3, True)))
    main_window.file.load_slice(parse(str(cube)))
    frame = main_window.frame_manager.current_frame
    assert frame.image_data.shape == (8, 12)
    # Slice 3 of the cube, and no cube left behind it.
    assert float(frame.image_data[0, 0]) == 2 * 8 * 12
    assert frame.image.data.ndim == 2


def test_open_as_slice_needs_a_cube(main_window, single, monkeypatch):
    from ncrads9.core.file_spec import parse

    main_window.file.load_slice(parse(str(single)))
    assert "not a data cube" in main_window.status_bar.currentMessage()


def test_open_as_extension_frames(main_window, mef):
    from ncrads9.core.file_spec import parse

    main_window.file.load_extension_frames(parse(str(mef)))
    assert main_window.frame_manager.num_frames == 2
    values = []
    for index in range(2):
        main_window.frame_manager.goto_frame(index)
        values.append(float(main_window.frame_manager.current_frame.image_data[0, 0]))
    assert values == [1.0, 2.0]


def test_open_as_extension_cube(main_window, mef):
    from ncrads9.core.file_spec import parse

    main_window.file.load_extension_cube(parse(str(mef)))
    frame = main_window.frame_manager.current_frame
    assert frame.image.data.shape == (2, 16, 20)
    assert CubeHandler(frame.image.data, frame.image.header).depth() == 2


@pytest.fixture
def three_extensions(tmp_path):
    """Three same-shaped extensions, for the `RGB Image` style loaders."""
    path = tmp_path / "three.fits"
    header = _header(20, 16)
    fits.HDUList(
        [
            fits.PrimaryHDU(),
            *[
                fits.ImageHDU(np.full((16, 20), float(value), np.float32), header, name=name)
                for value, name in enumerate(("R", "G", "B"), start=1)
            ],
        ]
    ).writeto(path)
    return path


@pytest.mark.parametrize("loader", sorted(COLOUR_LOADERS))
def test_open_as_colour(main_window, three_extensions, cube, loader):
    """All six of DS9's colour loaders fill all three channels."""
    from ncrads9.core.file_spec import parse

    frame_type, from_cube = COLOUR_LOADERS[loader]
    path = cube if from_cube else three_extensions
    main_window.file.load_colour(parse(str(path)), frame_type, from_cube)
    frame = main_window.frame_manager.current_frame
    assert frame.frame_type == frame_type
    assert all(frame.rgb_channels[name] is not None for name in ("red", "green", "blue"))


def test_open_as_colour_image_takes_the_first_three_extensions(main_window, three_extensions):
    from ncrads9.core.file_spec import parse

    main_window.file.load_colour(parse(str(three_extensions)), "rgb", False)
    frame = main_window.frame_manager.current_frame
    assert [float(frame.rgb_channels[name][0, 0]) for name in ("red", "green", "blue")] == [1.0, 2.0, 3.0]


def test_open_as_rgb_cube_fills_three_channels(main_window, cube):
    from ncrads9.core.file_spec import parse

    main_window.file.load_colour(parse(str(cube)), "rgb", True)
    frame = main_window.frame_manager.current_frame
    assert frame.frame_type == "rgb"
    assert float(frame.rgb_channels["red"][0, 0]) == 0.0
    assert float(frame.rgb_channels["green"][0, 0]) == 96.0


@pytest.fixture
def iraf_mosaic(tmp_path):
    """Two chips with DETSEC/DETSIZE, side by side."""
    path = tmp_path / "iraf.fits"
    hdus = [fits.PrimaryHDU()]
    for index, x0 in enumerate((1, 11)):
        header = fits.Header()
        header["DETSIZE"] = "[1:20,1:8]"
        header["DETSEC"] = f"[{x0}:{x0 + 9},1:8]"
        hdus.append(
            fits.ImageHDU(np.full((8, 10), float(index + 1), np.float32), header, name=f"IM{index + 1}")
        )
    fits.HDUList(hdus).writeto(path)
    return path


def test_open_as_mosaic_iraf(main_window, iraf_mosaic):
    from ncrads9.core.file_spec import parse

    main_window.file.load_mosaic(parse(str(iraf_mosaic)), MosaicKind.IRAF, segment=False)
    frame = main_window.frame_manager.current_frame
    assert frame.image_data.shape == (8, 20)
    assert float(frame.image_data[0, 0]) == 1.0
    assert float(frame.image_data[0, 15]) == 2.0


def test_open_as_mosaic_segment_needs_something_to_add_to(main_window, iraf_mosaic):
    from ncrads9.core.file_spec import parse

    main_window.file.load_mosaic(parse(str(iraf_mosaic)), MosaicKind.IRAF, segment=True)
    assert "No mosaic on screen" in main_window.status_bar.currentMessage()


def test_open_as_mosaic_wcs(main_window, mef):
    from ncrads9.core.file_spec import parse

    main_window.file.load_mosaic(parse(str(mef)), MosaicKind.WCS, segment=False)
    frame = main_window.frame_manager.current_frame
    assert frame.image_data.shape[0] >= 16


def test_every_mosaic_menu_entry_has_a_convention():
    assert set(MOSAIC_LOADERS) == {
        "mosaic_wcs",
        "mosaic_wcs_segment",
        "mosaic_iraf",
        "mosaic_iraf_segment",
        "mosaic_wfpc2",
    }


def test_a_mosaic_failure_is_reported_not_raised(main_window, single, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(single), "")))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    main_window.file.open_as("mosaic_iraf")
    assert "DETSEC" in main_window.status_bar.currentMessage()


# -- URL (M4-9) --------------------------------------------------------------


def test_open_url_rejects_a_non_http_scheme(main_window):
    with pytest.raises(ValueError, match="http"):
        main_window.file._download("ftp://example.invalid/foo.fits")


def test_open_url_downloads_and_loads(main_window, single, monkeypatch):
    """The download is stubbed; what is checked is that the file gets loaded."""
    from PyQt6.QtWidgets import QInputDialog

    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *a, **k: ("http://example.invalid/x.fits", True))
    )
    monkeypatch.setattr(main_window.file, "_download", lambda url: single)
    main_window.file.open_url()
    assert main_window.frame_manager.current_frame.image_data is not None


# -- saving (M4-10, M4-11) ---------------------------------------------------


def test_save_writes_the_displayed_array(main_window, single, tmp_path):
    main_window.display.load_fits(str(single))
    target = tmp_path / "out.fits"
    main_window.file._write(target, overwrite=True)

    with fits.open(target) as hdus:
        assert hdus[0].data.shape == (10, 20)
        assert np.array_equal(hdus[0].data, main_window.frame_manager.current_frame.image_data)
        assert hdus[0].header["OBJECT"] == "M51"
        assert hdus[0].header["CRVAL1"] == pytest.approx(10.0)


def test_save_of_an_empty_frame_says_so(main_window, tmp_path):
    main_window.file.save_file()
    assert "Nothing to save" in main_window.status_bar.currentMessage()


def test_save_updates_the_axis_cards_for_a_slice(main_window, cube, tmp_path):
    """A cube's slice must not be written with the cube's NAXIS3."""
    main_window.display.load_fits(str(cube))
    target = tmp_path / "slice.fits"
    main_window.file._write(target, overwrite=True)

    with fits.open(target) as hdus:
        assert hdus[0].header["NAXIS"] == 2
        assert "NAXIS3" not in hdus[0].header
        assert "CRVAL3" not in hdus[0].header


def test_save_records_the_source_specification(main_window, mef, tmp_path):
    main_window.display.load_fits(f"{mef}[ERR]")
    target = tmp_path / "spec.fits"
    main_window.file._write(target, overwrite=True)
    with fits.open(target) as hdus:
        assert "ERR" in hdus[0].header["NCSPEC"]


def test_save_repoints_the_frame_at_the_new_file(main_window, single, tmp_path):
    main_window.display.load_fits(str(single))
    target = tmp_path / "moved.fits"
    main_window.file._write(target, overwrite=True)
    assert main_window.frame_manager.current_frame.filepath == target


def test_a_save_round_trip_reloads(main_window, single, tmp_path):
    main_window.display.load_fits(str(single))
    original = main_window.frame_manager.current_frame.image_data.copy()
    target = tmp_path / "round.fits"
    main_window.file._write(target, overwrite=True)

    main_window.display.load_fits(str(target))
    assert np.array_equal(main_window.frame_manager.current_frame.image_data, original)


def test_save_as_a_colour_cube(main_window, cube, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    from ncrads9.core.file_spec import parse

    main_window.file.load_colour(parse(str(cube)), "rgb", True)
    target = tmp_path / "rgb.fits"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
    main_window.file.save_as("rgb_cube")
    with fits.open(target) as hdus:
        assert hdus[0].data.shape[0] == 3


def test_save_as_a_colour_image_writes_three_extensions(main_window, cube, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    from ncrads9.core.file_spec import parse

    main_window.file.load_colour(parse(str(cube)), "rgb", True)
    target = tmp_path / "rgbimg.fits"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
    main_window.file.save_as("rgb_image")
    with fits.open(target) as hdus:
        assert [hdu.name for hdu in hdus[1:]] == ["GREEN", "BLUE"]


def test_save_as_a_colour_frame_without_channels_is_reported(main_window, single, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    main_window.display.load_fits(str(single))
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(tmp_path / "x.fits"), ""))
    )
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    main_window.file.save_as("rgb_cube")
    assert "colour channels" in main_window.status_bar.currentMessage()


def test_save_image_as_fits_writes_the_rendered_picture(main_window, single, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    main_window.display.load_fits(str(single))
    target = tmp_path / "render.fits"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
    main_window.file.save_image("fits")

    with fits.open(target) as hdus:
        assert hdus[0].data.shape[0] == 3
        assert hdus[0].header["NCRENDER"]


@pytest.mark.parametrize("image_format", sorted(DEFERRED_IMAGE_FORMATS))
def test_deferred_save_image_formats_say_their_milestone(main_window, image_format):
    main_window.file.save_image(image_format)
    assert DEFERRED_IMAGE_FORMATS[image_format] in main_window.status_bar.currentMessage()


# -- the header dialog (M4-12) -----------------------------------------------


def test_the_header_dialog_lists_every_extension(main_window, mef, monkeypatch):
    from ncrads9.ui.dialogs import header_dialog as module

    captured = {}

    class _Dialog:
        def __init__(self, header, parent, extensions=None, handler=None, index=0):
            captured["extensions"] = extensions
            captured["index"] = index

        def exec(self):
            return 0

    monkeypatch.setattr(module, "HeaderDialog", _Dialog)
    main_window.display.load_fits(f"{mef}[ERR]")
    main_window.file.show_header()
    assert [info.name for info in captured["extensions"]] == ["PRIMARY", "SCI", "ERR"]
    assert captured["index"] == 2


def test_the_header_dialog_switches_extension(qapp, mef):
    from ncrads9.core.fits_handler import FITSHandler
    from ncrads9.ui.dialogs.header_dialog import HeaderDialog

    with FITSHandler(str(mef)) as handler:
        dialog = HeaderDialog(
            handler.get_header(1), None, extensions=handler.extensions(), handler=handler, index=1
        )
        assert dialog._ext_combo.currentIndex() == 1
        dialog._ext_combo.setCurrentIndex(2)
        assert dialog._index == 2
        assert "ERR" in dialog._header_text.toPlainText()


def test_the_header_dialog_without_a_list_is_disabled(qapp):
    from ncrads9.ui.dialogs.header_dialog import HeaderDialog

    dialog = HeaderDialog(fits.Header({"NAXIS": 0}))
    assert not dialog._ext_combo.isEnabled()
