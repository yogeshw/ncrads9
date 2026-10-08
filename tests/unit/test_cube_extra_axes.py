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

"""Cube axes beyond the third: a slider each, and XPA's `cube axis`."""

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.communication.xpa.xpa_commands import XPACommands
from ncrads9.core.cube_handler import CubeHandler

#: numpy shape (axis 4, axis 3, y, x): 2 Stokes planes of 5 channels.
SHAPE = (2, 5, 8, 9)


def _data():
    return np.arange(np.prod(SHAPE), dtype=np.float32).reshape(SHAPE)


def test_the_handler_names_the_extra_axes_and_slices_through_them():
    handler = CubeHandler(_data(), None)
    assert handler.extra_axes() == [(4, 2)]
    assert np.array_equal(handler.get_slice(3), _data()[0, 3])
    assert np.array_equal(handler.get_slice(3, extra={4: 1}), _data()[1, 3])
    with pytest.raises(IndexError):
        handler.get_slice(0, extra={4: 5})


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    path = tmp_path / "stokes.fits"
    fits.PrimaryHDU(_data()).writeto(path)
    made = MainWindow()
    made.display.load_fits(str(path))
    yield made
    made.close()


def _run(xpa, line, get=False):
    words = line.split()
    return xpa.handle(words[0], {"args": words[1:], **({"get": True} if get else {})})


def test_xpa_steps_the_fourth_axis(window):
    xpa = XPACommands(window)
    frame = window.frame_manager.current_frame
    assert _run(xpa, "cube 4")["status"] == "ok"
    assert frame.slice_index == 3
    assert _run(xpa, "cube axis 4")["status"] == "ok"
    assert _run(xpa, "cube axis", get=True)["result"] == "4"
    assert _run(xpa, "cube 2")["status"] == "ok"
    assert frame.axis_slices == {4: 1}
    assert np.array_equal(frame.image_data, _data()[1, 3])
    assert _run(xpa, "cube next")["status"] == "ok"
    assert frame.axis_slices[4] == 0, "next wraps round the axis"
    assert _run(xpa, "cube axis 5")["status"] == "error"


def test_the_dialog_has_a_slider_for_the_fourth_axis(window, qapp):
    window.frame_controller.show_cube_dialog()
    qapp.processEvents()
    panel = window.cube_dialog
    assert set(panel._extra_rows) == {4}
    slider, _spinbox, label = panel._extra_rows[4]
    assert label.text() == "of 2"
    slider.setValue(2)
    assert window.frame_manager.current_frame.axis_slices == {4: 1}
    panel.close()
