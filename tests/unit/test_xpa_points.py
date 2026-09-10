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


@pytest.fixture
def xpa(main_window):
    return XPACommands(main_window)


def _set(xpa, name, *args):
    return xpa.handle(name, {"args": list(args)})


def _get(xpa, name):
    return xpa.handle(name, {"get": True})


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
