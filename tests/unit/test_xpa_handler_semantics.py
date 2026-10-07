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
What DS9's documented commands *do*, for the hand-written access points.

The conformance test (`test_xpa_conformance.py`) runs every example DS9
documents and asserts that none raises. That let through answers that were
"ok" and changed nothing: `zoom to 4` zoomed to 6, `cmap invert yes` was
refused as a colormap called "invert", every `wcs` and `scale` read
answered with the same word, and `frame show 2` showed the current frame.
These pin down the state each command leaves behind.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.communication.xpa.xpa_commands import XPACommands

SIZE = 64


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    rows, columns = np.indices((SIZE, SIZE))
    header = fits.Header(
        {
            "CRPIX1": SIZE // 2,
            "CRPIX2": SIZE // 2,
            "CRVAL1": 202.48,
            "CRVAL2": 47.21,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CTYPE1A": "LINEAR",
            "CTYPE2A": "LINEAR",
            "CRPIX1A": 1,
            "CRPIX2A": 1,
            "CRVAL1A": 0,
            "CRVAL2A": 0,
            "CDELT1A": 2,
            "CDELT2A": 2,
            "LTV1": -10.0,
            "LTV2": -20.0,
            "LTM1_1": 1.0,
            "LTM2_2": 1.0,
        }
    )
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32), header=header).writeto(path)
    made = MainWindow()
    made.resize(900, 800)
    made.display.load_fits(str(path))
    made.tmp_path = tmp_path
    yield made
    made.close()


def _set(commands, line):
    words = line.split()
    return commands.handle(words[0], {"args": words[1:]})


def _get(commands, line):
    words = line.split()
    reply = commands.handle(words[0], {"get": True, "args": words[1:]})
    assert reply["status"] == "ok", reply
    return reply["result"]


@pytest.fixture
def xpa(window):
    return XPACommands(window)


# -- zoom ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "expected"), [("zoom to 4", 4.0), ("zoom 2", 2.0), ("zoom 1/4", 0.25), ("zoom to 2 2", 2.0)]
)
def test_zoom_sets_exactly_what_was_asked(xpa, command, expected):
    assert _set(xpa, command)["status"] == "ok"
    assert float(_get(xpa, "zoom")) == pytest.approx(expected)


def test_zoom_in_and_out_step_from_the_current_zoom(xpa):
    _set(xpa, "zoom to 2")
    _set(xpa, "zoom in")
    raised = float(_get(xpa, "zoom"))
    _set(xpa, "zoom out")
    assert raised > 2.0
    assert float(_get(xpa, "zoom")) == pytest.approx(2.0)


def test_zoom_x_and_y_apart_is_refused_rather_than_half_done(xpa):
    _set(xpa, "zoom to 2")
    assert _set(xpa, "zoom 2 4")["status"] == "error"
    assert float(_get(xpa, "zoom")) == pytest.approx(2.0)


# -- pan -----------------------------------------------------------------------


def test_pan_to_image_and_relative_pan(xpa):
    assert _set(xpa, "pan to 10 12 image")["status"] == "ok"
    assert [float(v) for v in _get(xpa, "pan").split()] == pytest.approx([10, 12], abs=1e-3)
    assert _set(xpa, "pan 5 -2 image")["status"] == "ok"
    assert [float(v) for v in _get(xpa, "pan image").split()] == pytest.approx([15, 10], abs=1e-3)


def test_pan_to_a_sky_position_lands_on_the_reference_pixel(xpa):
    assert _set(xpa, "pan to 13:29:55.2 +47:12:36 wcs fk5")["status"] == "ok"
    assert [float(v) for v in _get(xpa, "pan image").split()] == pytest.approx([32, 32], abs=1e-2)
    ra, dec = (float(v) for v in _get(xpa, "pan wcs fk5 degrees").split())
    assert (ra, dec) == pytest.approx((202.48, 47.21), abs=1e-5)
    assert _get(xpa, "pan wcs fk5 sexagesimal").startswith("13:29:55")


def test_pan_in_physical_coordinates_uses_ltv(xpa):
    _set(xpa, "pan to 30 40 physical")
    # physical = image - LTV, with LTV = (-10, -20) here.
    assert [float(v) for v in _get(xpa, "pan image").split()] == pytest.approx([20, 20], abs=1e-3)
    assert [float(v) for v in _get(xpa, "pan physical").split()] == pytest.approx([30, 40], abs=1e-3)


# -- cmap ----------------------------------------------------------------------


def test_cmap_name_invert_and_value(window, xpa):
    assert _set(xpa, "cmap Heat")["status"] == "ok"
    assert _get(xpa, "cmap") == "heat"
    assert _set(xpa, "cmap invert yes")["status"] == "ok"
    assert window.invert_colormap is True
    assert _get(xpa, "cmap invert") == "yes"
    assert _set(xpa, "cmap 5 .2")["status"] == "ok"
    assert [float(v) for v in _get(xpa, "cmap value").split()] == pytest.approx([5, 0.2])
    assert _set(xpa, "cmap value 1 0.5")["status"] == "ok"
    assert window.color.contrast_bias() == pytest.approx((1.0, 0.5))


def test_cmap_refuses_an_unknown_name_and_bad_values(xpa):
    assert _set(xpa, "cmap nosuchmap")["status"] == "error"
    assert _set(xpa, "cmap value 20 0.5")["status"] == "error"


def test_cmap_save_then_load_round_trips(window, xpa):
    target = window.tmp_path / "mine.lut"
    _set(xpa, "cmap heat")
    assert _set(xpa, f"cmap save {target}")["status"] == "ok"
    assert target.is_file()
    _set(xpa, "cmap grey")
    assert _set(xpa, f"cmap load {target}")["status"] == "ok"
    assert _get(xpa, "cmap") == "mine"


# -- colorbar ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "setting", "expected"),
    [
        ("colorbar vertical", "orientation", "vertical"),
        ("colorbar orientation horizontal", "orientation", "horizontal"),
        ("colorbar numerics no", "numerics", "no"),
        ("colorbar space distance", "space", "distance"),
        ("colorbar font courier", "font", "courier"),
        ("colorbar fontsize 14", "fontsize", "14"),
        ("colorbar fontweight bold", "fontweight", "bold"),
        ("colorbar fontslant italic", "fontslant", "italic"),
        ("colorbar size 30", "size", "30"),
        ("colorbar ticks 11", "ticks", "11"),
        ("colorbar lock yes", "lock", "yes"),
    ],
)
def test_each_colorbar_setting_is_set_and_read_back(xpa, command, setting, expected):
    assert _set(xpa, command)["status"] == "ok"
    assert _get(xpa, f"colorbar {setting}") == expected


def test_colorbar_shown_or_not(window, xpa):
    _set(xpa, "colorbar no")
    assert _get(xpa, "colorbar") == "no"
    _set(xpa, "colorbar yes")
    assert _get(xpa, "colorbar") == "yes"


# -- scale ---------------------------------------------------------------------


@pytest.mark.parametrize("name", ["linear", "log", "pow", "sqrt", "squared", "asinh", "sinh", "histequ"])
def test_every_scale_reads_back_under_its_ds9_name(xpa, name):
    assert _set(xpa, f"scale {name}")["status"] == "ok"
    assert _get(xpa, "scale") == name


def test_squared_and_pow_are_different_scales(window, xpa):
    from ncrads9.rendering.scale_algorithms import ScaleAlgorithm

    _set(xpa, "scale squared")
    assert window.current_scale is ScaleAlgorithm.SQUARED
    _set(xpa, "scale pow")
    assert window.current_scale is ScaleAlgorithm.POWER


def test_scale_reads(xpa):
    _set(xpa, "scale log exp 100")
    assert _get(xpa, "scale log exp") == "100"
    _set(xpa, "scale limits 1 100")
    assert [float(v) for v in _get(xpa, "scale limits").split()] == pytest.approx([1, 100])
    assert _get(xpa, "scale mode") == "user"
    _set(xpa, "scale mode 99.5")
    assert _get(xpa, "scale mode") == "99.5"
    _set(xpa, "scale scope global")
    assert _get(xpa, "scale scope") == "global"
    _set(xpa, "scale datasec no")
    assert _get(xpa, "scale datasec") == "no"


def test_scale_lock_and_lock_limits_are_separate(window, xpa):
    assert _set(xpa, "scale lock limits yes")["status"] == "ok"
    assert _get(xpa, "scale lock limits") == "yes"
    assert _get(xpa, "scale lock") == "no"
    assert _set(xpa, "scale lock yes")["status"] == "ok"
    assert window.frame_controller.is_locked("scale")
    assert _set(xpa, "scale match limits")["status"] == "ok"


# -- fits and file -------------------------------------------------------------


def test_fits_reads(window, xpa):
    assert _get(xpa, "fits width") == str(SIZE)
    assert _get(xpa, "fits height") == str(SIZE)
    assert _get(xpa, "fits depth") == "1"
    assert _get(xpa, "fits bitpix") == "-32"
    assert _get(xpa, "fits size") == f"{SIZE} {SIZE}"
    width, height = (float(v) for v in _get(xpa, "fits size wcs fk5 arcmin").split())
    assert width == pytest.approx(SIZE * 0.06)
    assert _get(xpa, "fits header keyword CTYPE1") == "RA---TAN"
    assert "CRVAL1" in _get(xpa, "fits header")
    assert _get(xpa, "file").endswith("sky.fits")


def test_xpaget_fits_is_the_file_itself(window, xpa):
    import io

    raw = _get(xpa, "fits")
    assert isinstance(raw, bytes)
    with fits.open(io.BytesIO(raw)) as hdus:
        assert hdus[0].data.shape == (SIZE, SIZE)
        assert hdus[0].header["CTYPE1"] == "RA---TAN"


def test_save_writes_fits_not_a_picture(window, xpa):
    target = window.tmp_path / "out.fits"
    assert _set(xpa, f"save {target}")["status"] == "ok"
    with fits.open(target) as hdus:
        assert hdus[0].data.shape == (SIZE, SIZE)
    other = window.tmp_path / "out2.fits"
    assert _set(xpa, f"save fits {other} image")["status"] == "ok"
    assert other.is_file()


# -- frame ---------------------------------------------------------------------


def test_frames_keep_their_numbers_as_ds9s_do(xpa):
    _set(xpa, "frame new")
    _set(xpa, "frame new")
    assert _get(xpa, "frame all") == "1 2 3"
    _set(xpa, "frame 1")
    _set(xpa, "frame delete")
    assert _get(xpa, "frame all") == "2 3"
    _set(xpa, "frame 3")
    assert _get(xpa, "frame") == "3"
    _set(xpa, "frame move first")
    assert _get(xpa, "frame all") == "3 2"


def test_going_to_a_missing_frame_makes_that_frame_alone(xpa):
    _set(xpa, "frame 7")
    assert _get(xpa, "frame") == "7"
    assert _get(xpa, "frame all") == "1 7"


def test_hide_and_show_name_the_frame(xpa):
    _set(xpa, "frame new")
    _set(xpa, "frame 1")
    _set(xpa, "frame hide 2")
    assert _get(xpa, "frame active") == "1"
    _set(xpa, "frame show 2")
    assert _get(xpa, "frame active") == "1 2"
    _set(xpa, "frame frameno 2")
    assert _get(xpa, "frame") == "2"


def test_frame_lock_and_match_reach_frame_lock(window, xpa):
    assert _set(xpa, "frame lock wcs")["status"] == "ok"
    assert window._frame_lock_scope["frame"] == "wcs"
    assert _set(xpa, "frame lock none")["status"] == "ok"
    assert window._frame_lock_scope["frame"] == "none"
    assert _set(xpa, "frame match wcs")["status"] == "ok"


def test_frame_delete_all_leaves_one_frame(xpa):
    _set(xpa, "frame new")
    _set(xpa, "frame new rgb")
    _set(xpa, "frame delete all")
    assert _get(xpa, "frame all") == "1"


def test_frame_has_reads_the_header(xpa):
    assert _get(xpa, "frame has wcs") == "yes"
    assert _get(xpa, "frame has wcs celestial wcs") == "yes"
    assert _get(xpa, "frame has wcs wcsa") == "yes"
    assert _get(xpa, "frame has wcs linear wcsa") == "yes"
    assert _get(xpa, "frame has wcs celestial wcsa") == "no"
    assert _get(xpa, "frame has wcs wcsb") == "no"
    assert _get(xpa, "frame has system physical") == "yes"
    assert _get(xpa, "frame has system image") == "yes"


# -- data on standard input ----------------------------------------------------


def test_regions_piped_on_standard_input_are_added(window, xpa):
    frame = window.frame_manager.current_frame
    before = len(frame.regions)
    reply = xpa.handle("regions", {"args": [], "data": "circle 10 10 5"})
    assert reply["status"] == "ok", reply
    assert len(frame.regions) == before + 1


def test_a_fits_file_piped_on_standard_input_is_loaded(window, xpa):
    import io

    buffer = io.BytesIO()
    fits.PrimaryHDU(data=np.ones((8, 9), dtype=np.float32)).writeto(buffer)
    reply = xpa.handle("fits", {"args": [], "data": buffer.getvalue()})
    assert reply["status"] == "ok", reply
    assert window.frame_manager.current_frame.image_data.shape == (8, 9)


def test_the_protocol_keeps_a_binary_payload_as_bytes():
    import io

    from ncrads9.communication.xpa.xpa_protocol import XPAProtocol

    buffer = io.BytesIO()
    fits.PrimaryHDU(data=np.arange(4, dtype=np.int16).reshape(2, 2) + 200).writeto(buffer)
    payload = buffer.getvalue() + bytes([0xFF, 0xFE])
    request = XPAProtocol().parse_request(b"xpaset ds9 fits\n" + payload)
    assert request["command"] == "fits"
    assert request["params"]["data"] == payload


# -- rotation changes the renderer, not the view -------------------------------


def test_rotating_keeps_the_zoom_and_the_pan(window, xpa, qapp):
    window.show()
    window.zoom.set_zoom(32)
    _set(xpa, "pan to 20 25 image")
    window.zoom.set_rotation(90)
    for _ in range(3):
        qapp.processEvents()
    assert float(_get(xpa, "zoom")) == pytest.approx(32)
    assert [float(v) for v in _get(xpa, "pan").split()] == pytest.approx([20, 25], abs=0.6)
    window.zoom.set_rotation(0)
    for _ in range(3):
        qapp.processEvents()
    assert window.using_gpu_rendering, "an upright frame goes back to the GPU viewer"
    assert float(_get(xpa, "zoom")) == pytest.approx(32)


def test_the_cpu_viewer_scrolls_when_zoomed_past_the_window(window, qapp):
    window.show()
    window._rebuild_image_viewer(False)
    window.zoom.set_zoom(32)
    for _ in range(3):
        qapp.processEvents()
    assert window.scroll_area.horizontalScrollBar().maximum() > 0
    assert window.scroll_area.verticalScrollBar().maximum() > 0
