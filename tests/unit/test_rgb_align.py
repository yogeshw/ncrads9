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

"""DS9's RGB Align: channels registered through WCS, image or physical."""

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.communication.xpa.xpa_commands import XPACommands
from ncrads9.frames.rgb_align import align

SIZE = 32


def _header(crpix: float, **extra) -> fits.Header:
    return fits.Header(
        {
            "CRPIX1": crpix,
            "CRPIX2": crpix,
            "CRVAL1": 202.48,
            "CRVAL2": 47.21,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            **extra,
        }
    )


def _sky(shift: int) -> np.ndarray:
    """The same sky, on a grid moved by `shift` pixels."""
    rows, columns = np.indices((SIZE, SIZE))
    return ((rows + shift) * 100 + (columns + shift)).astype(np.float32)


def test_wcs_alignment_puts_the_same_sky_on_the_same_pixel():
    red, green = _sky(0), _sky(3)
    aligned, used = align(
        {"red": red, "green": green, "blue": None},
        {"red": _header(16), "green": _header(13)},
        key="red",
        system="wcs",
    )
    assert used == "wcs"
    inner = (slice(5, 25), slice(5, 25))
    assert np.array_equal(aligned["green"][inner], red[inner])


def test_image_alignment_is_pixel_for_pixel():
    red, green = _sky(0), _sky(3)
    aligned, used = align(
        {"red": red, "green": green, "blue": None},
        {"red": _header(16), "green": _header(13)},
        key="red",
        system="image",
    )
    assert used == "image"
    assert np.array_equal(aligned["green"], green)


def test_a_channel_without_the_wcs_falls_back_to_image():
    aligned, used = align(
        {"red": _sky(0), "green": _sky(3), "blue": None},
        {"red": _header(16), "green": fits.Header()},
        key="red",
        system="wcs",
    )
    assert used == "image"


def test_physical_alignment_uses_ltv():
    red, green = _sky(0), _sky(3)
    aligned, used = align(
        {"red": red, "green": green, "blue": None},
        {"red": fits.Header({"LTV1": 0.0, "LTV2": 0.0}), "green": fits.Header({"LTV1": -3.0, "LTV2": -3.0})},
        key="red",
        system="physical",
    )
    assert used == "physical"
    assert np.array_equal(aligned["green"][5:25, 5:25], red[5:25, 5:25])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    made = MainWindow()
    made.tmp_path = tmp_path
    yield made
    made.close()


def test_rgb_system_through_xpa(window):
    tmp = window.tmp_path
    fits.PrimaryHDU(_sky(0), _header(16)).writeto(tmp / "r.fits")
    fits.PrimaryHDU(_sky(3), _header(13)).writeto(tmp / "g.fits")
    xpa = XPACommands(window)
    for line in ("rgb", "rgb channel red", f"fits {tmp / 'r.fits'}", "rgb channel green", f"fits {tmp / 'g.fits'}"):
        words = line.split()
        assert xpa.handle(words[0], {"args": words[1:]})["status"] == "ok", line
    frame = window.frame_manager.current_frame
    assert frame.rgb_key == "red"
    assert np.array_equal(frame.rgb_channels["green"][5:25, 5:25], frame.rgb_channels["red"][5:25, 5:25])
    assert xpa.handle("rgb", {"args": ["system", "image"]})["status"] == "ok"
    assert xpa.handle("rgb", {"get": True, "args": ["system"]})["result"] == "image"
    assert not np.array_equal(frame.rgb_channels["green"], frame.rgb_channels["red"])
    assert xpa.handle("rgb", {"args": ["system", "sideways"]})["status"] == "error"


def test_the_dialog_has_ds9s_align_menu(window, qapp):
    window.frame_controller.new_frame_of_type("rgb")
    window.frame_controller.show_rgb_dialog()
    qapp.processEvents()
    dialog = next(w for w in qapp.topLevelWidgets() if hasattr(w, "align_actions") and w.isVisible())
    assert {"wcs", "wcsa", "image", "physical", "amplifier", "detector"} <= set(dialog.align_actions)
    assert dialog.align_actions["wcs"].isChecked()
    dialog.close()
