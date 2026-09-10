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

"""DS9's XPA access points, and File -> XPA (M9-25, M9-26)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.communication.xpa import access_points
from ncrads9.communication.xpa.xpa_commands import XPACommands

SIZE = 24

#: Every name DS9 registers, from `ds9/library/xpa.tcl`. `3d`/`3D` and
#: `iexam`/`imexam` are one point each under two names, so DS9's 145
#: registrations are 143 distinct names.
DS9_POINTS: tuple[str, ...] = (
    "2mass",
    "3d",
    "about",
    "align",
    "analysis",
    "array",
    "backup",
    "bin",
    "blink",
    "block",
    "catalog",
    "cd",
    "cmap",
    "colorbar",
    "console",
    "contour",
    "crop",
    "crosshair",
    "cube",
    "cursor",
    "data",
    "dsssao",
    "dsseso",
    "dssstsci",
    "envi",
    "exit",
    "export",
    "fade",
    "file",
    "fits",
    "footprint",
    "frame",
    "gif",
    "graph",
    "grid",
    "header",
    "height",
    "hls",
    "hlsarray",
    "hlscube",
    "hlsimage",
    "hsv",
    "hsvarray",
    "hsvcube",
    "hsvimage",
    "iconify",
    "iexam",
    "iis",
    "illustrate",
    "jpeg",
    "lock",
    "lower",
    "magnifier",
    "mask",
    "match",
    "mecube",
    "minmax",
    "mode",
    "mosaic",
    "mosaicimage",
    "movie",
    "multiframe",
    "nameserver",
    "notes",
    "nrrd",
    "nvss",
    "orient",
    "pagesetup",
    "pan",
    "pixeltable",
    "plot",
    "png",
    "prefs",
    "preserve",
    "prism",
    "psprint",
    "print",
    "quit",
    "raise",
    "region",
    "restore",
    "rgb",
    "rgbarray",
    "rgbcube",
    "rgbimage",
    "rotate",
    "samp",
    "save",
    "saveimage",
    "scale",
    "shm",
    "sia",
    "single",
    "skyview",
    "sleep",
    "smooth",
    "source",
    "tcl",
    "tile",
    "update",
    "url",
    "version",
    "view",
    "vla",
    "vlss",
    "vo",
    "wcs",
    "web",
    "width",
    "xpa",
    "zscale",
    "zoom",
    # DS9's remaining names, which its documentation lists but its
    # alphabetical index above does not repeat.
    "bg",
    "background",
    "dss",
    "hsvarray",
    "imexam",
    "memf",
    "precision",
    "pspagesetup",
    "regions",
    "sfits",
    "srgbcube",
    "theme",
    "threads",
)


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path):
    # A preferences file of its own: several points here *write* one, and
    # a test must not edit the preferences the user is running with. Only
    # `use_gpu` is forced, since the offscreen platform has no GL.
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    real_get = Preferences.get
    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else real_get(self, key, default),
    )
    rows, columns = np.indices((SIZE, SIZE))
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32)).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    yield window
    window.close()


@pytest.fixture
def xpa(main_window):
    return XPACommands(main_window)


def _set(xpa, name, *args):
    return xpa.handle(name, {"args": list(args)})


def _get(xpa, name, *args):
    """`xpaget ds9 <name> [args]`. A read may take arguments -- `xpaget ds9
    dsssao size`, `xpaget ds9 data image 3 3 2 2` -- which the table
    answers through a point's `query`."""
    return xpa.handle(name, {"get": True, "args": list(args)})


# -- the table itself -------------------------------------------------------------


def test_no_two_points_answer_to_the_same_name():
    """An alias that collides silently shadows the point it collides with."""
    seen: dict[str, str] = {}
    for point in access_points.ALL_POINTS:
        for name in point.names:
            assert name not in seen, f"{name} is both {seen.get(name)} and {point.name}"
            seen[name] = point.name


def test_every_point_can_do_something():
    for point in access_points.ALL_POINTS:
        assert point.get is not None or point.set is not None, point.name


def test_every_point_says_what_it_is_for():
    """`xpaget ds9 xpa` lists them, and a list of bare names says nothing."""
    for point in access_points.ALL_POINTS:
        assert point.summary, point.name


def test_ds9s_booleans_are_read_and_written_as_ds9_writes_them():
    assert access_points.on_off(True) == "yes"
    assert access_points.on_off(False) == "no"
    for text in ("yes", "on", "true", "1"):
        assert access_points.as_bool(text) is True
    for text in ("no", "off", "false", "0"):
        assert access_points.as_bool(text) is False
    assert access_points.as_bool("maybe") is None


def test_the_table_covers_most_of_ds9s_list(xpa):
    """DS9 registers 145 access points counting aliases. This is the ratchet
    that keeps the count going up rather than down."""
    assert len(xpa.get_available_commands()) >= 100


def test_an_unknown_point_is_reported(xpa):
    assert _set(xpa, "wibble", "1")["status"] == "error"


def test_a_point_with_no_getter_says_so(xpa):
    assert _get(xpa, "raise")["status"] == "error"


# -- (a) display ------------------------------------------------------------------


def test_orient(xpa, main_window):
    assert _set(xpa, "orient", "xy")["status"] == "ok"
    frame = main_window.frame_manager.current_frame
    assert (frame.flip_x, frame.flip_y) == (True, True)
    assert _get(xpa, "orient")["result"] == "xy"
    assert _set(xpa, "orient", "sideways")["status"] == "error"


def test_align(xpa, main_window):
    assert _set(xpa, "align", "yes")["status"] == "ok"
    assert main_window.frame_manager.current_frame.align_wcs is True
    assert _get(xpa, "align")["result"] == "yes"


def test_rotate_turns_by_an_amount_and_to_an_angle(xpa, main_window):
    """DS9's two forms, and getting them the wrong way round would turn the
    frame by 90 degrees every time a script asked for 90."""
    assert _set(xpa, "rotate", "30")["status"] == "ok"
    assert _set(xpa, "rotate", "30")["status"] == "ok"
    assert main_window.frame_manager.current_frame.rotation == pytest.approx(60.0)

    assert _set(xpa, "rotate", "to", "90")["status"] == "ok"
    assert main_window.frame_manager.current_frame.rotation == pytest.approx(90.0)
    assert _get(xpa, "rotate")["result"] == "90"
    assert _set(xpa, "rotate", "sideways")["status"] == "error"


def test_block(xpa, main_window):
    assert _set(xpa, "block", "2")["status"] == "ok"
    assert main_window.frame_manager.current_frame.block_factor == 2
    assert _get(xpa, "block")["result"] == "2"

    assert _set(xpa, "block", "to", "4")["status"] == "ok"
    assert main_window.frame_manager.current_frame.block_factor == 4
    assert _set(xpa, "block", "in")["status"] == "ok"
    assert _set(xpa, "block", "out")["status"] == "ok"
    assert _set(xpa, "block", "to", "fit")["status"] == "ok"
    assert _set(xpa, "block", "match")["status"] == "ok"
    assert _set(xpa, "block", "lock", "yes")["status"] == "ok"
    assert main_window._frame_lock_flags["block"] is True
    assert _set(xpa, "block", "wide")["status"] == "error"


def test_smooth_and_grid_and_contour(xpa, main_window):
    for name in ("smooth", "grid", "contour"):
        assert _set(xpa, name, "yes")["status"] == "ok", name
        assert _get(xpa, name)["result"] == "yes", name
        assert _set(xpa, name, "no")["status"] == "ok", name
        assert _get(xpa, name)["result"] == "no", name


def test_contours_is_an_alias_of_contour(xpa):
    assert _set(xpa, "contours", "yes")["status"] == "ok"
    assert _get(xpa, "contour")["result"] == "yes"


def test_crop_and_reset(xpa, main_window):
    assert _set(xpa, "crop", "10", "12", "8", "6")["status"] == "ok"
    crop = main_window.crop.region()
    assert crop is not None
    assert crop.center == (10.0, 12.0)
    assert _get(xpa, "crop")["result"] == "10 12 8 6"

    assert _set(xpa, "crop", "reset")["status"] == "ok"
    assert main_window.crop.region() is None
    assert _set(xpa, "crop", "10")["status"] == "error"


def test_zscale_parameters(xpa, main_window):
    assert _set(xpa, "zscale", "contrast", ".3")["status"] == "ok"
    assert main_window.scale_limits.contrast == pytest.approx(0.3)
    assert _set(xpa, "zscale", "sample", "600")["status"] == "ok"
    assert _set(xpa, "zscale", "line", "120")["status"] == "ok"
    assert "contrast 0.3" in _get(xpa, "zscale")["result"]

    assert _set(xpa, "zscale")["status"] == "ok"
    assert main_window.scale_limits.mode.value == "zscale"
    assert _set(xpa, "zscale", "wibble", "1")["status"] == "error"


def test_minmax_parameters(xpa, main_window):
    assert _set(xpa, "minmax", "sample")["status"] == "ok"
    assert main_window.scale_limits.method.value == "sample"
    assert _set(xpa, "minmax", "mode", "scan")["status"] == "ok"
    assert main_window.scale_limits.method.value == "scan"
    assert _set(xpa, "minmax", "interval", "5")["status"] == "ok"
    assert main_window.scale_limits.sample_increment == 5
    assert _set(xpa, "minmax", "rescan")["status"] == "ok"
    assert "mode scan" in _get(xpa, "minmax")["result"]
    assert _set(xpa, "minmax", "wibble")["status"] == "error"


def test_invert(xpa, main_window):
    assert _set(xpa, "invert", "yes")["status"] == "ok"
    assert main_window.invert_colormap is True
    assert _get(xpa, "invert")["result"] == "yes"


def test_mask(xpa, main_window, tmp_path):
    path = tmp_path / "mask.fits"
    fits.PrimaryHDU(data=np.ones((SIZE, SIZE), dtype=np.float32)).writeto(path)

    assert _set(xpa, "mask", str(path))["status"] == "ok"
    assert _get(xpa, "mask")["result"] == "yes"
    assert _set(xpa, "mask", "clear")["status"] == "ok"
    assert _get(xpa, "mask")["result"] == "no"


def test_magnifier_and_panner(xpa, main_window):
    for name in ("magnifier", "panner"):
        assert _set(xpa, name, "no")["status"] == "ok", name
        assert _get(xpa, name)["result"] == "no", name
        assert _set(xpa, name, "open")["status"] == "ok", name
        assert _get(xpa, name)["result"] == "yes", name
        assert _set(xpa, name, "sideways")["status"] == "error", name


# -- (b) frames --------------------------------------------------------------------


def test_the_display_modes(xpa, main_window, tmp_path):
    # Blink and fade need something to blink between.
    path = tmp_path / "second.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32)).writeto(path)
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(path))

    assert _set(xpa, "tile")["status"] == "ok"
    assert main_window._frame_display_mode == "tile"
    assert _get(xpa, "tile")["result"] == "yes"

    assert _set(xpa, "single")["status"] == "ok"
    assert main_window._frame_display_mode == "single"
    assert _get(xpa, "single")["result"] == "yes"

    assert _set(xpa, "blink")["status"] == "ok"
    assert main_window._frame_display_mode == "blink"
    assert _set(xpa, "fade")["status"] == "ok"
    assert main_window._frame_display_mode == "fade"


def test_tile_mode_implies_tiling(xpa, main_window):
    """`tile mode column` says how to tile, which is not much use without
    tiling."""
    assert _set(xpa, "tile", "mode", "column")["status"] == "ok"
    assert main_window._frame_display_mode == "tile"
    assert _set(xpa, "tile", "mode")["status"] == "error"


def test_blink_interval_is_in_seconds(xpa, main_window):
    assert _set(xpa, "blink", "interval", "2")["status"] == "ok"
    assert main_window._blink_timer.interval() == 2000
    assert _set(xpa, "blink", "interval", "soon")["status"] == "error"


def test_walking_the_frames(xpa, main_window, tmp_path):
    path = tmp_path / "second.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32)).writeto(path)
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(path))

    assert _set(xpa, "first")["status"] == "ok"
    assert main_window.frame_manager.current_index == 0
    assert _set(xpa, "next")["status"] == "ok"
    assert main_window.frame_manager.current_index == 1
    assert _set(xpa, "prev")["status"] == "ok"
    assert main_window.frame_manager.current_index == 0
    assert _set(xpa, "last")["status"] == "ok"
    assert main_window.frame_manager.current_index == 1


def test_the_slice_counts_from_one_as_ds9s_dialog_does(xpa, main_window, tmp_path):
    cube = np.zeros((4, SIZE, SIZE), dtype=np.float32)
    path = tmp_path / "cube.fits"
    fits.PrimaryHDU(data=cube).writeto(path)
    main_window.display.load_fits(str(path))

    assert _set(xpa, "slice", "3")["status"] == "ok"
    assert main_window.frame_manager.current_frame.slice_index == 2
    assert _get(xpa, "slice")["result"] == "3"
    assert _get(xpa, "cube")["result"] == "3"
    assert _set(xpa, "slice", "middle")["status"] == "error"


def test_lock_reads_every_scope_and_sets_one(xpa, main_window):
    assert _set(xpa, "lock", "crosshair", "wcs")["status"] == "ok"
    assert main_window.crosshair.locked is True
    assert "crosshair wcs" in _get(xpa, "lock")["result"]

    assert _set(xpa, "lock", "scale", "yes")["status"] == "ok"
    assert main_window._frame_lock_flags["scale"] is True
    assert "scale yes" in _get(xpa, "lock")["result"]
    assert _set(xpa, "lock", "wibble")["status"] == "error"


def test_match_takes_a_scope_rather_than_matching_frames_regardless(xpa, main_window, tmp_path):
    """The old handler matched frames whatever the scope word said, so
    `match crosshair` moved the views."""
    path = tmp_path / "second.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32)).writeto(path)
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(path))
    other = main_window.frame_manager.current_frame
    main_window.frame_controller.first()
    main_window.crosshair.move_to(5.0, 6.0)
    before = other.zoom

    assert _set(xpa, "match", "crosshair", "image")["status"] == "ok"
    assert other.crosshair == (5.0, 6.0)
    assert other.zoom == pytest.approx(before)
    assert _set(xpa, "match", "wibble")["status"] == "error"


# -- (c) files ---------------------------------------------------------------------


def test_importing_through_xpa(xpa, main_window, tmp_path):
    from ncrads9.io import raster

    rgb = np.zeros((4, 6, 3), dtype=np.uint8)
    raster.write(tmp_path / "photo.png", rgb, "png")

    assert _set(xpa, "png", str(tmp_path / "photo.png"))["status"] == "ok"
    assert main_window.frame_manager.current_frame.image_data.shape == (4, 6)
    assert _set(xpa, "png")["status"] == "error"


def test_the_raster_aliases_ds9_registers(xpa, main_window, tmp_path):
    from ncrads9.io import raster

    raster.write(tmp_path / "x.tif", np.zeros((4, 4, 3), dtype=np.uint8), "tiff")
    assert _set(xpa, "tif", str(tmp_path / "x.tif"))["status"] == "ok"


def test_exporting_through_xpa(xpa, main_window, tmp_path, monkeypatch):
    from ncrads9.ui.dialogs import array_dialog

    monkeypatch.setattr(
        array_dialog.ArrayDialog,
        "choose",
        lambda self: __import__("ncrads9.io.array_reader", fromlist=["ArraySpec"]).ArraySpec(1, 1),
    )
    path = tmp_path / "out.arr"
    assert _set(xpa, "export", "array", str(path))["status"] == "ok"
    assert path.is_file()
    assert _set(xpa, "export", "array")["status"] == "error"


def test_saveimage_writes_whatever_the_name_asks_for(xpa, main_window, tmp_path):
    for name in ("view.png", "view.jpeg", "view.eps"):
        path = tmp_path / name
        assert _set(xpa, "saveimage", str(path))["status"] == "ok", name
        assert path.is_file(), name
    assert _set(xpa, "saveimage", str(tmp_path / "view.xyz"))["status"] == "error"


def test_a_movie_through_xpa(xpa, main_window, tmp_path):
    path = tmp_path / "m.gif"
    assert _set(xpa, "movie", "frame", str(path))["status"] == "ok"
    assert path.is_file()
    assert _set(xpa, "movie")["status"] == "error"


def test_backup_and_restore_through_xpa(xpa, main_window, tmp_path):
    path = tmp_path / "s.bck"
    main_window.zoom.set_zoom(4.0)
    assert _set(xpa, "backup", str(path))["status"] == "ok"

    main_window.zoom.set_zoom(1.0)
    assert _set(xpa, "restore", str(path))["status"] == "ok"
    assert main_window.frame_manager.current_frame.zoom == pytest.approx(4.0)
    assert _set(xpa, "backup")["status"] == "error"


# -- (d) tools ---------------------------------------------------------------------


def test_the_notes_point(xpa, main_window):
    assert _set(xpa, "notes", "append", "a line")["status"] == "ok"
    assert _get(xpa, "notes")["result"] == "a line\n"
    assert _set(xpa, "notes", "insert", "first")["status"] == "ok"
    assert _get(xpa, "notes")["result"].startswith("first")
    assert _set(xpa, "notes", "clear")["status"] == "ok"
    assert _get(xpa, "notes")["result"] == ""
    assert _set(xpa, "notes", "wibble")["status"] == "error"


def test_the_notes_point_reads_and_writes_files(xpa, main_window, tmp_path):
    path = tmp_path / "n.txt"
    main_window.notes.append("kept")
    assert _set(xpa, "notes", "save", str(path))["status"] == "ok"
    main_window.notes.clear()
    assert _set(xpa, "notes", "load", str(path))["status"] == "ok"
    assert "kept" in main_window.notes.text


def test_the_pixel_table_point(xpa, main_window):
    assert _set(xpa, "pixeltable", "yes")["status"] == "ok"
    assert _get(xpa, "pixeltable")["result"] == "yes"
    assert _set(xpa, "pixeltable", "close")["status"] == "ok"
    assert _get(xpa, "pixeltable")["result"] == "no"


def test_the_illustrate_point(xpa, main_window, tmp_path):
    main_window.illustrate.layer.create("circle", 10.0, 10.0)
    path = tmp_path / "i.ill"
    assert _set(xpa, "illustrate", "save", str(path))["status"] == "ok"
    assert _set(xpa, "illustrate", "delete")["status"] == "ok"
    assert len(main_window.illustrate.layer) == 0
    assert _set(xpa, "illustrate", "open", str(path))["status"] == "ok"
    assert len(main_window.illustrate.layer) == 1

    assert _set(xpa, "illustrate", "show", "no")["status"] == "ok"
    assert _get(xpa, "illustrate")["result"] == "no"
    assert _set(xpa, "illustrate", "wibble")["status"] == "error"


# -- (e) application ---------------------------------------------------------------


def test_the_pointer_mode_point_actually_changes_the_mode(xpa, main_window):
    """The old handler echoed the mode back and changed nothing."""
    assert _set(xpa, "mode", "pan")["status"] == "ok"
    assert main_window.edit_mode == "pan"
    assert _get(xpa, "mode")["result"] == "pan"
    assert _set(xpa, "mode", "teleport")["status"] == "error"


def test_the_cursor_point_moves_the_crosshair(xpa, main_window):
    """The old handler reported the last mouse position and could not move
    anything, which is not what DS9's `cursor` is for."""
    assert _set(xpa, "cursor", "7", "8")["status"] == "ok"
    assert main_window.crosshair.position() == (7.0, 8.0)
    assert _get(xpa, "cursor")["result"] == "7 8"
    assert _set(xpa, "cursor", "7")["status"] == "error"


def test_the_crosshair_point_moves_locks_and_matches(xpa, main_window):
    assert _set(xpa, "crosshair", "3", "4")["status"] == "ok"
    assert main_window.crosshair.position() == (3.0, 4.0)
    assert _set(xpa, "crosshair", "lock", "wcs")["status"] == "ok"
    assert main_window.crosshair.locked is True
    assert _set(xpa, "crosshair", "lock", "none")["status"] == "ok"
    assert main_window.crosshair.locked is False
    assert _set(xpa, "crosshair", "match", "image")["status"] == "ok"


def test_the_nan_colour_point(xpa, main_window):
    assert _set(xpa, "nan", "#00ff00")["status"] == "ok"
    assert main_window.nan_color == "#00ff00"
    assert _get(xpa, "nan")["result"] == "#00ff00"
    assert _set(xpa, "nan")["status"] == "error"


def test_the_preserve_point(xpa, main_window):
    assert _set(xpa, "preserve", "pan", "yes")["status"] == "ok"
    assert main_window.file.preserving("pan") is True
    assert "pan yes" in _get(xpa, "preserve")["result"]
    assert _set(xpa, "preserve", "everything", "yes")["status"] == "error"


def test_the_page_setup_point(xpa, main_window):
    assert _set(xpa, "pagesetup", "orient", "landscape")["status"] == "ok"
    assert _set(xpa, "pagesetup", "size", "a4")["status"] == "ok"
    assert _set(xpa, "pagesetup", "scale", "50")["status"] == "ok"

    page = main_window.file.print_settings.page
    assert page.orientation.value == "landscape"
    assert page.paper_size.value == "a4"
    assert page.scale == pytest.approx(50.0)
    assert "orient landscape" in _get(xpa, "pagesetup")["result"]
    assert _set(xpa, "pagesetup", "orient", "sideways")["status"] == "error"


def test_the_print_point_writes_a_file(xpa, main_window, tmp_path):
    path = tmp_path / "printed.ps"
    assert _set(xpa, "psprint", "filename", str(path))["status"] == "ok"
    assert _set(xpa, "psprint", "destination", "file")["status"] == "ok"
    assert _set(xpa, "psprint")["status"] == "ok"
    assert path.read_text(encoding="ascii").startswith("%!PS-Adobe")


def test_the_print_points_settings(xpa, main_window):
    assert _set(xpa, "psprint", "resolution", "300")["status"] == "ok"
    assert main_window.file.print_settings.resolution == 300
    assert _set(xpa, "psprint", "level", "3")["status"] == "ok"
    assert main_window.file.print_settings.level == 3
    assert _set(xpa, "psprint", "color", "cmyk")["status"] == "ok"
    assert main_window.file.print_settings.color_model == "cmyk"
    assert _set(xpa, "psprint", "level", "high")["status"] == "error"


def test_the_window_points(xpa, main_window):
    assert _set(xpa, "iconify", "no")["status"] == "ok"
    assert _get(xpa, "iconify")["result"] == "no"
    assert _set(xpa, "raise")["status"] == "ok"
    assert _set(xpa, "lower")["status"] == "ok"
    assert _set(xpa, "width", "400")["status"] == "ok"
    assert _set(xpa, "height", "400")["status"] == "ok"
    assert _set(xpa, "width", "wide")["status"] == "error"


def test_the_working_directory_point(xpa, main_window, tmp_path):
    import os

    was = os.getcwd()
    try:
        assert _set(xpa, "cd", str(tmp_path))["status"] == "ok"
        assert _get(xpa, "cd")["result"].endswith(tmp_path.name)
        assert _set(xpa, "cd", str(tmp_path / "nowhere"))["status"] == "error"
    finally:
        os.chdir(was)


def test_sleep_and_update(xpa):
    assert _set(xpa, "sleep", "0")["status"] == "ok"
    assert _set(xpa, "sleep", "soon")["status"] == "error"
    assert _set(xpa, "update")["status"] == "ok"


def test_the_name_server_point(xpa, main_window, monkeypatch):
    """Never over the network in a test: what is checked is that the point
    reaches the resolver and reports what it says."""
    from astropy.coordinates import SkyCoord

    monkeypatch.setattr(SkyCoord, "from_name", classmethod(lambda cls, name: SkyCoord("10d 20d")))
    assert _set(xpa, "nameserver", "M31")["status"] == "ok"
    assert _get(xpa, "nameserver")["result"] == "M31"

    def refuse(cls, name):
        raise ValueError("no such object")

    monkeypatch.setattr(SkyCoord, "from_name", classmethod(refuse))
    assert _set(xpa, "nameserver", "NoSuchThing")["status"] == "error"


def test_the_version_point(xpa):
    assert "ncrads9" in _get(xpa, "version")["result"].lower()


# -- File -> XPA (M9-26) -----------------------------------------------------------


class FakeServer:
    """A server that starts and stops without a socket."""

    def __init__(self, name="ncrads9", address="localhost:14285", starts=True) -> None:
        self.name = name
        self.address = address
        self.running = False
        self._starts = starts

    def start(self) -> bool:
        self.running = self._starts
        return self.running

    def stop(self) -> None:
        self.running = False


def test_the_file_menu_has_ds9s_xpa_submenu(main_window):
    labels = [
        action.text().replace("&", "")
        for action in main_window.menu_bar.xpa_menu.actions()
        if not action.isSeparator()
    ]
    assert labels == ["Information", "Connect", "Disconnect"]


def test_information_says_what_to_address(main_window, xpa):
    server = FakeServer()
    server.running = True
    main_window.xpa.attach(server, xpa)

    text = main_window.xpa.information()
    assert "localhost:14285" in text
    assert "connected" in text
    assert "xpaget ncrads9 frame" in text
    # And how many points there are, which is the other thing it is for.
    assert "Access points:" in text


def test_information_with_no_server_says_so(main_window):
    main_window.xpa.attach(None)
    assert "switched off" in main_window.xpa.information()


def test_connect_and_disconnect(main_window, xpa):
    server = FakeServer()
    main_window.xpa.attach(server, xpa)

    assert main_window.xpa.start() is True
    assert server.running is True
    assert "XPA connected" in main_window.status_bar.currentMessage()

    assert main_window.xpa.stop() is True
    assert server.running is False
    assert "disconnected" in main_window.status_bar.currentMessage()


def test_the_menu_greys_out_what_makes_no_sense(main_window, xpa):
    server = FakeServer()
    main_window.xpa.attach(server, xpa)
    assert main_window.menu_bar.action_xpa_connect.isEnabled() is True
    assert main_window.menu_bar.action_xpa_disconnect.isEnabled() is False

    main_window.xpa.start()
    assert main_window.menu_bar.action_xpa_connect.isEnabled() is False
    assert main_window.menu_bar.action_xpa_disconnect.isEnabled() is True


def test_connecting_twice_is_harmless(main_window, xpa):
    server = FakeServer()
    main_window.xpa.attach(server, xpa)
    main_window.xpa.start()
    assert main_window.xpa.start() is True
    assert "already connected" in main_window.status_bar.currentMessage()


def test_a_server_that_will_not_start_is_reported(main_window, xpa):
    main_window.xpa.attach(FakeServer(starts=False), xpa)
    assert main_window.xpa.start() is False
    assert "could not connect" in main_window.status_bar.currentMessage()


def test_connecting_with_no_server_says_so(main_window):
    main_window.xpa.attach(None)
    assert main_window.xpa.start() is False
    assert "switched off" in main_window.status_bar.currentMessage()


def test_the_information_dialog_lists_the_access_points(main_window, xpa, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    shown = {}
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.update(detail=self.detailedText()))
    main_window.xpa.attach(FakeServer(), xpa)
    main_window.xpa.show_information()
    assert "zoom" in shown["detail"]
    assert "the flip" in shown["detail"]


# -- the image servers (M9-25) ----------------------------------------------------


@pytest.fixture
def servers(main_window, tmp_path, monkeypatch):
    """The image servers with the network taken out from under them.

    The transport hands back a real FITS file, so a retrieval that DS9
    would answer with an image gets one here too, and every point that
    ends in a fetch can be checked all the way to a loaded frame.
    """
    from astropy.coordinates import SkyCoord

    rows, columns = np.indices((8, 8))
    path = tmp_path / "cutout.fits"
    fits.PrimaryHDU(data=(rows * columns).astype(np.float32)).writeto(path)
    payload = path.read_bytes()

    asked: list[str] = []

    def transport(url, timeout=0):
        asked.append(url)
        return payload

    main_window.image_servers.transport = transport
    monkeypatch.setattr(SkyCoord, "from_name", classmethod(lambda cls, name, *a, **k: SkyCoord("10d 20d")))
    main_window.image_servers.asked = asked
    return main_window.image_servers


def test_every_server_ds9_names_has_a_point(xpa):
    """DS9 names 2MASS `2mass` where our server is `twomass`, so the point
    and the server are not the same name and the mapping has to hold."""
    for name in ("dsssao", "dsseso", "dssstsci", "dss", "2mass", "skyview", "vla", "nvss", "vlss"):
        assert name in xpa.get_available_commands()


def test_opening_a_server_opens_its_dialog(xpa, servers):
    assert _set(xpa, "dsssao", "open")["status"] == "ok"
    assert "dsssao" in servers._dialogs
    assert _set(xpa, "dsssao", "close")["status"] == "ok"
    assert "dsssao" not in servers._dialogs


def test_dss_is_ds9s_short_name_for_the_sao_server(xpa, servers):
    _set(xpa, "dss", "open")
    assert "dsssao" in servers._dialogs


def test_a_position_is_taken_in_degrees_and_fetched(xpa, servers):
    """DS9's `<ra> <dec>` rule ends in IMGSVRApply, so it fetches."""
    assert _set(xpa, "dsssao", "10.5", "-20.25")["status"] == "ok"
    assert servers.asked, "a position should have fetched"
    assert "10.5" in servers.asked[0]
    assert _get(xpa, "dsssao")["result"] == "10.5 -20.25"


def test_a_position_is_also_taken_in_sexagesimal(xpa, servers):
    assert _set(xpa, "dsssao", "00:42:44.404", "+41:16:08.78")["status"] == "ok"
    longitude, latitude = (float(word) for word in _get(xpa, "dsssao")["result"].split())
    assert longitude == pytest.approx(10.6850, abs=1e-3)
    assert latitude == pytest.approx(41.2691, abs=1e-3)


def test_a_size_is_set_and_not_fetched(xpa, servers):
    """`size` is one of DS9's rules that does not end in IMGSVRApply."""
    assert _set(xpa, "dsssao", "size", "30", "30", "arcmin")["status"] == "ok"
    assert servers.asked == []
    assert _get(xpa, "dsssao", "size")["result"] == "30 30 arcmin"


def test_a_size_is_converted_into_the_servers_own_unit(xpa, servers):
    """SkyView asks in degrees, the SAO DSS in arcmin; a script says which
    unit it means and should not have to know which the server wants."""
    _set(xpa, "skyview", "size", "30", "30", "arcmin")
    assert _get(xpa, "skyview", "size")["result"] == "0.5 0.5 degrees"
    _set(xpa, "dsssao", "size", "1", "1", "degrees")
    assert _get(xpa, "dsssao", "size")["result"] == "60 60 arcmin"


def test_a_survey_is_matched_whatever_its_case(xpa, servers):
    """DS9's grammar tokenises `dss1` and sends `DSS1`."""
    assert _set(xpa, "dsseso", "survey", "dss1")["status"] == "ok"
    assert _get(xpa, "dsseso", "survey")["result"] == "DSS1"
    assert _set(xpa, "dsseso", "survey", "DSS2-red")["status"] == "ok"
    assert _get(xpa, "dsseso", "survey")["result"] == "DSS2-red"


def test_a_survey_a_server_does_not_offer_is_reported(xpa, servers):
    assert "not a survey" in _set(xpa, "dsseso", "survey", "wibble")["message"]


def test_a_server_with_one_survey_says_it_has_no_choice(xpa, servers):
    """DS9's SAO DSS point has no `survey` rule; saying so beats a lie."""
    assert "no choice of survey" in _set(xpa, "dsssao", "survey", "dss1")["message"]


def test_skyviews_pixels_are_its_own_size_rule(xpa, servers):
    """SkyView takes the sky size in degrees and the image size in pixels
    separately, and DS9 gives the second its own rule. Setting one must
    not move the other."""
    _set(xpa, "skyview", "size", "1", "1", "degrees")
    assert _set(xpa, "skyview", "pixels", "600", "600")["status"] == "ok"
    assert _get(xpa, "skyview", "pixels")["result"] == "600 600"
    assert _get(xpa, "skyview", "size")["result"] == "1 1 degrees"

    # And it reaches the query, rather than stopping at the dialog.
    _set(xpa, "skyview", "10", "20")
    assert "Pixels=600%2C600" in servers.asked[-1]


def test_a_server_without_a_pixel_size_says_so(xpa, servers):
    assert "no separate image size" in _set(xpa, "dsssao", "pixels", "600", "600")["message"]


def test_a_name_is_resolved_and_fetched(xpa, servers):
    assert _set(xpa, "dsssao", "name", "m31")["status"] == "ok"
    assert servers.asked, "a name should have fetched"
    assert _get(xpa, "dsssao")["result"] == "10 20"


def test_clearing_a_name_does_not_fetch(xpa, servers):
    _set(xpa, "dsssao", "name", "clear")
    assert servers.asked == []
    assert _get(xpa, "dsssao", "name")["result"] == ""


def test_a_bare_word_is_an_object_name(xpa, servers):
    assert _set(xpa, "dsssao", "m31")["status"] == "ok"
    assert servers.asked


def test_save_and_frame_are_remembered(xpa, servers):
    for name, value in (("save", "yes"), ("frame", "current")):
        assert _set(xpa, "dsssao", name, value)["status"] == "ok"
        assert _get(xpa, "dsssao", name)["result"] == value
    for name, bad in (("save", "sometimes"), ("frame", "old"), ("update", "wibble")):
        assert _set(xpa, "dsssao", name, bad)["status"] == "error"


def test_update_re_centres_on_the_frame_and_fetches(xpa, servers, main_window, tmp_path):
    """DS9's `update frame` rule ends in IMGSVRApply, so it fetches -- but
    it needs somewhere to fetch, and the fixture image carries no WCS."""
    assert "no WCS" in _set(xpa, "dsssao", "update", "frame")["message"]

    path = tmp_path / "wcs.fits"
    header = fits.Header(
        {
            "CRPIX1": 4,
            "CRPIX2": 4,
            "CRVAL1": 10.0,
            "CRVAL2": 20.0,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
        }
    )
    fits.PrimaryHDU(data=np.zeros((8, 8), dtype=np.float32), header=header).writeto(path)
    main_window.display.load_fits(str(path))
    assert _set(xpa, "dsssao", "update", "frame")["status"] == "ok"
    assert servers.asked
    assert _get(xpa, "dsssao", "update")["result"] == "frame"


def test_frame_current_loads_into_the_frame_that_is_there(xpa, servers, main_window):
    before = len(main_window.frame_manager.frames)
    _set(xpa, "dsssao", "frame", "current")
    _set(xpa, "dsssao", "10", "20")
    assert len(main_window.frame_manager.frames) == before


def test_frame_new_makes_one(xpa, servers, main_window):
    before = len(main_window.frame_manager.frames)
    _set(xpa, "dsssao", "10", "20")
    assert len(main_window.frame_manager.frames) == before + 1


def test_save_keeps_the_download_where_it_can_be_found(xpa, servers, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _set(xpa, "dsssao", "save", "yes")
    _set(xpa, "dsssao", "10", "20")
    assert list(tmp_path.glob("dsssao_*.fits")), "save yes should have kept the file"


def test_a_read_with_no_dialog_open_answers_for_the_frame(xpa, servers):
    assert _get(xpa, "dsssao")["result"] == "0 0"
    assert _get(xpa, "dsssao", "name")["result"] == ""


# -- what was left of DS9's list (M9-25) ------------------------------------------


def test_every_name_ds9_registers_now_answers(xpa):
    """The point of M9-25. DS9 registers 143 distinct names (145 counting
    `3d`/`3D` and `iexam`/`imexam` twice); every one has to answer, or a
    script written for DS9 breaks on a name rather than on a feature."""
    ours = set(xpa.get_available_commands())
    for name in DS9_POINTS:
        assert name in ours, f"DS9's {name} has no access point"


def test_the_background_colour_is_set(xpa, main_window):
    assert _set(xpa, "bg", "#123456")["status"] == "ok"
    assert main_window.preferences.get("background_color") == "#123456"
    # `background` is the same point under DS9's other name for it.
    _set(xpa, "background", "black")
    assert main_window.preferences.get("background_color") == "black"


def test_the_theme_is_set_and_an_unknown_one_refused(xpa, main_window):
    assert _set(xpa, "theme", "dark")["status"] == "ok"
    assert main_window.preferences.get("theme") == "Dark"
    assert _set(xpa, "theme", "neon")["status"] == "error"


def test_the_thread_count_is_set(xpa, main_window):
    assert _set(xpa, "threads", "8")["status"] == "ok"
    assert _get(xpa, "threads")["result"] == "8"
    assert _set(xpa, "threads", "0")["status"] == "error"
    assert _set(xpa, "threads", "many")["status"] == "error"


def test_precision_takes_ds9s_six_numbers_positionally(xpa, main_window):
    assert _set(xpa, "precision", "9", "10", "4", "3", "5", "6")["status"] == "ok"
    assert _get(xpa, "precision")["result"] == "9 10 4 3 5 6"
    assert main_window.preferences.get("precision_hms") == 4


def test_precision_also_takes_a_name_and_a_number(xpa, main_window):
    _set(xpa, "precision", "dms", "7")
    assert main_window.preferences.get("precision_dms") == 7
    assert _set(xpa, "precision", "dms", "many")["status"] == "error"


def test_the_data_point_answers_with_a_box_of_values(xpa):
    """`xpaget ds9 data image 3 3 2 2 yes`: DS9 gives the lower-left corner
    in FITS coordinates, so the values are the ones a reader would expect
    at those coordinates rather than one pixel off."""
    values = _get(xpa, "data", "image", "3", "3", "2", "2", "yes")["result"].split("\n")
    # The fixture's image is row + column, indexed from zero.
    assert values == ["4", "5", "5", "6"]


def test_the_data_point_can_keep_the_coordinates(xpa):
    lines = _get(xpa, "data", "image", "3", "3", "2", "2", "no")["result"].split("\n")
    assert lines[0] == "3 3 4"
    assert lines[-1] == "4 4 6"


def test_the_data_point_takes_an_optional_sky_frame(xpa):
    """DS9's grammar puts the sky frame between the system and the numbers,
    where it is optional; the geometry has to be found either way."""
    assert _get(xpa, "data", "wcs", "fk5", "3", "3", "2", "2")["result"].count("\n") == 3


def test_the_data_point_clips_to_the_image(xpa):
    values = _get(xpa, "data", "image", str(SIZE - 1), str(SIZE - 1), "4", "4")["result"]
    assert values.count("\n") == 3  # 2x2 of the 4x4 asked for is on the image
    assert _get(xpa, "data", "image", "500", "500", "2", "2")["result"] == ""


def test_the_graphs_take_ds9s_settings(xpa, main_window):
    graphs = (main_window.horizontal_graph, main_window.vertical_graph)
    for name, attribute, value in (
        ("grid", "grid", True),
        ("log", "log", True),
    ):
        assert _set(xpa, "graph", name, "yes")["status"] == "ok"
        for graph in graphs:
            assert getattr(graph.settings, attribute) is value

    assert _set(xpa, "graph", "method", "sum")["status"] == "ok"
    assert _set(xpa, "graph", "thickness", "7")["status"] == "ok"
    assert _set(xpa, "graph", "size", "220")["status"] == "ok"
    for graph in graphs:
        assert graph.settings.method == "sum"
        assert graph.settings.thickness == 7
        assert graph.settings.size == 220


def test_the_graph_point_reports_what_it_cannot_do(xpa):
    """DS9's graph has its own font; ours draws with the widget's, and
    saying so beats reporting success and changing nothing."""
    assert "font" in _set(xpa, "graph", "fontsize", "12")["message"]
    assert _set(xpa, "graph", "method", "median")["status"] == "error"
    assert _set(xpa, "graph", "wibble")["status"] == "error"


def test_the_graph_point_shows_and_hides_the_panels(xpa, main_window):
    # `isVisibleTo`, not `isVisible`: the window itself is never shown in
    # a test, and a child of a hidden window is never visible.
    assert _set(xpa, "graph", "both")["status"] == "ok"
    assert main_window.horizontal_graph.isVisibleTo(main_window)
    assert _get(xpa, "graph")["result"] == "both"
    assert _set(xpa, "graph", "close")["status"] == "ok"
    assert not main_window.horizontal_graph.isVisibleTo(main_window)
    assert _get(xpa, "graph")["result"] == "none"


def test_the_view_point_sets_the_panels(xpa, main_window):
    assert _set(xpa, "view", "panner", "no")["status"] == "ok"
    assert main_window.view_state.panner is False
    assert _set(xpa, "view", "colorbar", "yes")["status"] == "ok"
    assert main_window.view_state.colorbar is True
    assert "panner no" in _get(xpa, "view")["result"]


def test_the_view_point_sets_the_layout(xpa, main_window):
    assert _set(xpa, "view", "layout", "vertical")["status"] == "ok"
    assert main_window.view_state.layout.value == "vertical"
    assert _set(xpa, "view", "layout", "diagonal")["status"] == "error"


def test_the_view_point_sets_the_information_fields(xpa, main_window):
    assert _set(xpa, "view", "minmax", "yes")["status"] == "ok"
    assert main_window.view_state.info_fields["minmax"] is True
    # DS9 calls the BUNIT field `units`.
    assert _set(xpa, "view", "units", "yes")["status"] == "ok"
    assert main_window.view_state.info_fields["bunit"] is True
    # And its alternate WCS letters are one word, where ours are two.
    assert _set(xpa, "view", "wcsa", "yes")["status"] == "ok"
    assert main_window.view_state.info_fields["wcs_a"] is True


def test_the_view_point_refuses_what_it_does_not_know(xpa):
    assert _set(xpa, "view", "wibble", "yes")["status"] == "error"
    assert _set(xpa, "view", "panner", "sometimes")["status"] == "error"
    assert _set(xpa, "view")["status"] == "error"


def test_the_view_point_sets_the_keyword_field(xpa, main_window):
    assert _set(xpa, "view", "keyvalue", "BITPIX")["status"] == "ok"
    assert main_window.view.info_panel.keyword_entry.text() == "BITPIX"


def test_the_bin_point_sets_what_ds9s_bin_menu_holds(xpa, main_window):
    assert _set(xpa, "bin", "function", "average")["status"] == "ok"
    assert main_window.bin_settings.function.value == "average"
    assert _set(xpa, "bin", "factor", "4")["status"] == "ok"
    assert main_window.bin_settings.factor == 4
    assert _set(xpa, "bin", "buffersize", "512")["status"] == "ok"
    assert main_window.bin_settings.buffer_size == 512
    assert _set(xpa, "bin", "depth", "3")["status"] == "ok"
    assert main_window.bin_settings.depth == 3
    assert _set(xpa, "bin", "filter", "pha>5")["status"] == "ok"
    assert main_window.bin_settings.filter == "pha>5"
    assert _set(xpa, "bin", "filter", "clear")["status"] == "ok"
    assert main_window.bin_settings.filter == ""
    assert "function average" in _get(xpa, "bin")["result"]


def test_the_bin_point_sets_the_columns(xpa, main_window):
    assert _set(xpa, "bin", "cols", "RAWX", "RAWY")["status"] == "ok"
    assert main_window.bin_spec.columns == ("RAWX", "RAWY")
    assert _set(xpa, "bin", "colsz", "X", "Y", "PHA")["status"] == "ok"
    assert main_window.bin_spec.columns == ("X", "Y", "PHA")
    assert _set(xpa, "bin", "cols", "X")["status"] == "error"


def test_the_bin_point_reports_what_it_cannot_do(xpa):
    assert "about center" in _set(xpa, "bin", "about", "10", "10")["message"]
    assert _set(xpa, "bin", "about", "center")["status"] == "ok"
    assert _set(xpa, "bin", "wibble")["status"] == "error"


def test_the_region_point_loads_and_saves(xpa, main_window, tmp_path):
    source = tmp_path / "in.reg"
    source.write_text("# Region file format: DS9 version 4.1\nimage\ncircle(6,6,3)\n")
    assert _set(xpa, "region", "load", str(source))["status"] == "ok"
    assert len(main_window.frame_manager.current_frame.regions) == 1

    target = tmp_path / "out.reg"
    assert _set(xpa, "region", "save", str(target))["status"] == "ok"
    assert "circle" in target.read_text()

    # A bare filename is DS9's first rule: load it.
    _set(xpa, "region", "delete")
    assert _set(xpa, "region", str(source))["status"] == "ok"
    assert len(main_window.frame_manager.current_frame.regions) == 1


def test_the_region_point_answers_with_the_regions(xpa, main_window, tmp_path):
    source = tmp_path / "in.reg"
    source.write_text("# Region file format: DS9 version 4.1\nimage\ncircle(6,6,3)\n")
    _set(xpa, "region", "load", str(source))
    assert "circle" in _get(xpa, "region")["result"]
    # `regions` is DS9's other name for the same point.
    assert "circle" in _get(xpa, "regions")["result"]


def test_the_region_point_deletes(xpa, main_window, tmp_path):
    source = tmp_path / "in.reg"
    source.write_text("# Region file format: DS9 version 4.1\nimage\ncircle(6,6,3)\n")
    _set(xpa, "region", "load", str(source))
    assert _set(xpa, "region", "delete")["status"] == "ok"
    assert main_window.frame_manager.current_frame.regions == []


def test_the_region_point_takes_ds9s_marker_command_syntax(xpa, main_window):
    """`region command` is given a region in the marker syntax, which puts
    its arguments after the shape with spaces rather than in brackets."""
    assert _set(xpa, "region", "command", "circle 8 8 3")["status"] == "ok"
    regions = main_window.frame_manager.current_frame.regions
    assert len(regions) == 1
    assert regions[0].center == (8.0, 8.0)

    # And a line straight out of a region file, which is as likely.
    assert _set(xpa, "region", "command", "box(4,4,2,2,0)")["status"] == "ok"
    assert len(main_window.frame_manager.current_frame.regions) == 2
    assert _set(xpa, "region", "command", "wibble 1 2")["status"] == "error"


def test_the_region_point_sets_the_defaults(xpa, main_window):
    assert _set(xpa, "region", "shape", "box")["status"] == "ok"
    assert _set(xpa, "region", "color", "red")["status"] == "ok"
    assert main_window.region.defaults["color"] == "red"
    assert _set(xpa, "region", "width", "3")["status"] == "ok"
    assert main_window.region.defaults["width"] == 3
    assert _set(xpa, "region", "width", "thick")["status"] == "error"


def test_the_region_point_remembers_the_format_for_the_next_save(xpa, main_window, tmp_path):
    assert _set(xpa, "region", "format", "ciao")["status"] == "ok"
    assert main_window.preferences.get("region_format") == "ciao"
    assert _set(xpa, "region", "format", "wibble")["status"] == "error"

    source = tmp_path / "in.reg"
    source.write_text("# Region file format: DS9 version 4.1\nimage\ncircle(6,6,3)\n")
    _set(xpa, "region", "load", str(source))
    target = tmp_path / "out.reg"
    _set(xpa, "region", "save", str(target))
    # CIAO writes `circle(6,6,3)` with no DS9 header, which is how the
    # format is told apart from ours.
    assert "DS9 version" not in target.read_text()


def test_the_region_point_selects(xpa, main_window, tmp_path):
    source = tmp_path / "in.reg"
    source.write_text("# Region file format: DS9 version 4.1\nimage\ncircle(6,6,3)\ncircle(9,9,2)\n")
    _set(xpa, "region", "load", str(source))
    assert _set(xpa, "region", "select", "all")["status"] == "ok"
    assert len(main_window.region.selection()) == 2
    assert _set(xpa, "region", "select", "none")["status"] == "ok"
    assert main_window.region.selection() == []
    assert _set(xpa, "region", "select", "sideways")["status"] == "error"


def test_the_region_point_reports_what_the_wcs_menu_owns(xpa):
    """`region system` is a window-wide setting in ours, and saying which
    menu owns it beats a silent no-op."""
    assert "WCS menu" in _set(xpa, "region", "system", "wcs")["message"]


def test_the_colour_frame_points_make_frames(xpa, main_window):
    for kind in ("rgb", "hsv", "hls"):
        before = len(main_window.frame_manager.frames)
        assert _set(xpa, kind)["status"] == "ok"
        assert len(main_window.frame_manager.frames) == before + 1
        assert main_window.frame_manager.current_frame.frame_type == kind


def test_the_rgb_point_picks_a_channel(xpa, main_window):
    _set(xpa, "rgb")
    assert _set(xpa, "rgb", "channel", "green")["status"] == "ok"
    assert main_window.frame_manager.current_frame.rgb_current_channel == "green"
    # DS9's bare `rgb blue` is the same thing.
    assert _set(xpa, "rgb", "blue")["status"] == "ok"
    assert main_window.frame_manager.current_frame.rgb_current_channel == "blue"
    assert _get(xpa, "rgb")["result"] == "blue"
    assert _set(xpa, "rgb", "channel", "purple")["status"] == "error"


def test_the_rgb_point_shows_and_hides_a_channel(xpa, main_window):
    _set(xpa, "rgb")
    assert _set(xpa, "rgb", "view", "red", "no")["status"] == "ok"
    assert main_window.frame_manager.current_frame.rgb_view["red"] is False
    # And `view rgb red yes` is the same setting from DS9's other point.
    assert _set(xpa, "view", "rgb", "red", "yes")["status"] == "ok"
    assert main_window.frame_manager.current_frame.rgb_view["red"] is True


def test_a_channel_on_a_plain_frame_is_reported(xpa, main_window):
    assert "not rgb" in _set(xpa, "rgb", "channel", "red")["message"]
    assert "no colour channels" in _set(xpa, "view", "rgb", "red", "no")["message"]


def test_savefits_writes_the_frame(xpa, tmp_path):
    target = tmp_path / "out.fits"
    assert _set(xpa, "savefits", str(target))["status"] == "ok"
    with fits.open(target) as handle:
        assert handle[0].data.shape == (SIZE, SIZE)
    assert _set(xpa, "savefits")["status"] == "error"


def test_sfits_and_memf_open_a_fits_file(xpa, main_window, tmp_path):
    path = tmp_path / "other.fits"
    fits.PrimaryHDU(data=np.zeros((6, 6), dtype=np.float32)).writeto(path)
    assert _set(xpa, "sfits", str(path))["status"] == "ok"
    assert _set(xpa, "memf", str(path))["status"] == "ok"
    assert _set(xpa, "sfits")["status"] == "error"


def test_the_cube_and_mosaic_points_take_the_filename_they_are_given(xpa, tmp_path):
    """These loaders used to ask for a file with a dialog even when XPA had
    named one, which hung any script that called them."""
    path = tmp_path / "cube.fits"
    fits.PrimaryHDU(data=np.zeros((3, 6, 6), dtype=np.float32)).writeto(path)
    for name in ("rgbcube", "hsvcube", "hlscube", "srgbcube"):
        assert _set(xpa, name, str(path))["status"] == "ok", name

    # And the multi-extension ones, which need a file with extensions.
    extensions = tmp_path / "mef.fits"
    plane = np.zeros((6, 6), dtype=np.float32)
    fits.HDUList(
        [fits.PrimaryHDU(), fits.ImageHDU(plane, name="ONE"), fits.ImageHDU(plane, name="TWO")]
    ).writeto(extensions)
    for name in ("mecube", "multiframe"):
        assert _set(xpa, name, str(extensions))["status"] == "ok", name


def test_the_plot_point_opens_and_lists_plots(xpa, main_window):
    assert _set(xpa, "plot", "line")["status"] == "ok"
    assert len(main_window.analysis.plots()) == 1
    assert _set(xpa, "plot", "bar")["status"] == "ok"
    assert len(main_window.analysis.plots()) == 2
    listing = _get(xpa, "plot")["result"].split("\n")
    assert len(listing) == 2
    # The last one made is the current one, which DS9 marks and acts on.
    assert listing[-1].endswith("*")
    for plot in main_window.analysis.plots():
        plot.close()


def test_the_plot_point_loads_a_data_file(xpa, main_window, tmp_path):
    path = tmp_path / "curve.dat"
    path.write_text("1 2\n2 4\n3 6\n")
    assert _set(xpa, "plot", "line", str(path), "xy")["status"] == "ok"
    plot = main_window.analysis.current_plot()
    assert plot.state.datasets[0].y == [2.0, 4.0, 6.0]
    assert _set(xpa, "plot", "load", str(path), "xy")["status"] == "ok"
    assert len(plot.state.datasets) == 2
    plot.close()


def test_the_plot_point_reports_a_file_that_holds_no_points(xpa, main_window, tmp_path):
    path = tmp_path / "prose.dat"
    path.write_text("nothing here is a number\n")
    assert _set(xpa, "plot", "line", str(path))["status"] == "error"
    for plot in main_window.analysis.plots():
        plot.close()


def test_the_plot_point_saves_and_picks_the_current_plot(xpa, main_window, tmp_path):
    _set(xpa, "plot", "line")
    _set(xpa, "plot", "line")
    first, second = main_window.analysis.plots()
    assert _set(xpa, "plot", "current", "1")["status"] == "ok"
    assert main_window.analysis.current_plot() is first
    assert _set(xpa, "plot", "current", "9")["status"] == "error"

    target = tmp_path / "plot.json"
    assert _set(xpa, "plot", "save", str(target))["status"] == "ok"
    assert target.exists()
    assert _set(xpa, "plot", "close")["status"] == "ok"
    second.close()


def test_the_plot_point_says_when_there_is_no_plot(xpa):
    assert "no plot is open" in _set(xpa, "plot", "save", "/tmp/x.json")["message"]


def test_the_plot_point_reports_what_it_cannot_do(xpa, main_window):
    _set(xpa, "plot", "line")
    assert "one graph" in _set(xpa, "plot", "layout", "strip")["message"]
    assert _set(xpa, "plot", "wibble")["status"] == "error"
    for plot in main_window.analysis.plots():
        plot.close()


def test_the_xpa_point_reports_and_connects(xpa, main_window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "exec", lambda self: None)
    assert "XPA" in _get(xpa, "xpa")["result"]
    assert _set(xpa, "xpa", "info")["status"] == "ok"

    main_window.xpa.attach(FakeServer(), xpa)
    assert _set(xpa, "xpa", "connect")["status"] == "ok"
    assert main_window.xpa.is_running() is True
    assert _set(xpa, "xpa", "disconnect")["status"] == "ok"
    assert main_window.xpa.is_running() is False
    assert _set(xpa, "xpa", "wibble")["status"] == "error"


def test_the_console_point_opens_a_console_and_runs_a_line(xpa, main_window):
    """DS9 runs Tcl, being written in it; this runs Python, for the reason."""
    assert _set(xpa, "console")["status"] == "ok"
    console = main_window.file._console
    assert console is not None
    assert _set(xpa, "tcl", "answer = 6 * 7")["status"] == "ok"
    assert console.namespace["answer"] == 42
    assert _set(xpa, "console", "close")["status"] == "ok"


def test_the_source_point_runs_a_file(xpa, main_window, tmp_path):
    script = tmp_path / "hello.py"
    script.write_text("recorded = 'ran'\n")
    assert _set(xpa, "source", str(script))["status"] == "ok"
    assert main_window.file._console.namespace["recorded"] == "ran"
    assert _set(xpa, "source", str(tmp_path / "nonesuch.py"))["status"] == "error"
    assert _set(xpa, "source")["status"] == "error"
    main_window.file._console.close()


def test_the_web_point_opens_a_url(xpa, monkeypatch):
    from PyQt6.QtGui import QDesktopServices

    opened: list[str] = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toString())))
    assert _set(xpa, "web")["status"] == "ok"
    assert opened, "a bare `web` opens DS9's own page"
    assert "the system browser" in _set(xpa, "web", "close")["message"]


def test_the_analysis_point_loads_runs_and_clears_tasks(xpa, main_window, tmp_path):
    commands = tmp_path / "tasks.ans"
    commands.write_text("Say hello\n*\nmenu\necho hello | $text\n")

    assert _set(xpa, "analysis", "load", str(commands))["status"] == "ok"
    assert _get(xpa, "analysis")["result"] == "0 Say hello"

    assert _set(xpa, "analysis", "task", "0")["status"] == "ok"
    assert _set(xpa, "analysis", "task", "Say hello")["status"] == "ok"
    assert _set(xpa, "analysis", "task", "9")["status"] == "error"
    assert _set(xpa, "analysis", "task", "Nonesuch")["status"] == "error"

    assert _set(xpa, "analysis", "clear")["status"] == "ok"
    assert _get(xpa, "analysis")["result"] == ""
    assert "no analysis tasks" in _set(xpa, "analysis", "task", "0")["message"]
    main_window.analysis_tasks.cancel_all()


def test_the_analysis_point_loads_a_bare_filename(xpa, main_window, tmp_path):
    commands = tmp_path / "tasks.ans"
    commands.write_text("Say hello\n*\nmenu\necho hello | $text\n")
    assert _set(xpa, "analysis", str(commands))["status"] == "ok"
    assert "Say hello" in _get(xpa, "analysis")["result"]
    assert _set(xpa, "analysis", "/nonesuch/tasks.ans")["status"] == "error"
    assert _set(xpa, "analysis")["status"] == "error"


def test_the_analysis_point_shows_a_message_and_a_text_window(xpa, main_window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    # `$message(ok, ...)` uses the static helper, which is modal.
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    )
    assert _set(xpa, "analysis", "message", "ok", "all done")["status"] == "ok"
    assert _set(xpa, "analysis", "message", "maybe", "eh")["status"] == "error"
    assert _set(xpa, "analysis", "text")["status"] == "ok"
    for window in list(main_window.analysis_tasks._windows.values()):
        window.close()


def test_pspagesetup_is_ds9s_postscript_name_for_the_page(xpa, main_window):
    assert _set(xpa, "pspagesetup", "orient", "landscape")["status"] == "ok"
    assert "landscape" in _get(xpa, "pspagesetup")["result"]


def test_the_sia_point_opens_a_service_or_the_registry(xpa, main_window, servers, monkeypatch):
    """DS9's `sia` names one of ten services. Where we have a server for
    one, that dialog is the search; the rest are in the VO registry."""
    shown: list[bool] = []
    monkeypatch.setattr(main_window.vo, "show_registry", lambda: shown.append(True))
    assert _set(xpa, "sia")["status"] == "ok"
    assert shown

    assert _set(xpa, "sia", "2mass", "open")["status"] == "ok"
    assert "twomass" in main_window.image_servers._dialogs
    assert _set(xpa, "sia", "radius", "0.25", "degrees")["status"] == "ok"
    assert _get(xpa, "2mass", "size")["result"] == "30 30 arcmin"
    assert "no SIA service" in _set(xpa, "sia", "cadc")["message"]
    _set(xpa, "sia", "close")


def test_ds9s_two_spellings_of_3d_reach_the_same_point(xpa):
    """DS9 registers `3d` and `3D` separately; ours lowers the name."""
    assert _get(xpa, "3d")["result"] == _get(xpa, "3D")["result"]
