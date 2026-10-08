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

"""DS9's 3D movie (`Movie3d`): a 3D frame turned, step by step."""

import numpy as np
import pytest
from astropy.io import fits
from PIL import Image, ImageSequence

from ncrads9.communication.xpa.xpa_commands import XPACommands


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    made = MainWindow()
    cube = np.zeros((8, 16, 16), dtype=np.float32)
    # Off centre in every axis, so no two views of it coincide.
    cube[1:3, 2:7, 9:14] = 10.0
    cube[5:8, 10:15, 1:4] = 5.0
    path = tmp_path / "cube.fits"
    fits.PrimaryHDU(cube).writeto(path)
    xpa = XPACommands(made)
    assert xpa.handle("frame", {"args": ["new", "3d"]})["status"] == "ok"
    assert xpa.handle("fits", {"args": [str(path)]})["status"] == "ok"
    made.tmp_path = tmp_path
    made.xpa_test = xpa
    yield made
    made.close()


def _frames(path):
    with Image.open(path) as movie:
        return [np.asarray(frame.convert("RGB")) for frame in ImageSequence.Iterator(movie)]


def test_a_3d_movie_turns_the_cube(window):
    target = window.tmp_path / "turn.gif"
    command = f"3d gif {target} number 4 az from -60 az to 60 oscillate 1".split()
    reply = window.xpa_test.handle("movie", {"args": command})
    assert reply["status"] == "ok", reply
    frames = _frames(target)
    # number 4 is five steps, both ends included; oscillating once runs
    # them forwards and then back: ten, less the turnaround's repeat, which
    # the GIF writer folds into one frame shown twice as long.
    assert len(frames) == 9
    assert not np.array_equal(frames[0], frames[2]), "the cube should have turned"
    assert np.array_equal(frames[0], frames[-1]), "and come back"


def test_the_view_is_put_back(window):
    before = window.frame_3d.view()
    window.xpa_test.handle("movie", {"args": f"3d gif {window.tmp_path / 'a.gif'} number 2".split()})
    assert window.frame_3d.view() == before


def test_the_dialog_offers_3d_only_for_a_3d_frame(window, qapp):
    from ncrads9.ui.dialogs.movie_dialog import MovieDialog

    assert MovieDialog(is_three_d=True)._three_d.isEnabled()
    assert not MovieDialog(is_three_d=False)._three_d.isEnabled()
    dialog = MovieDialog(is_three_d=True, three_d={"az": (-10, 10), "num": 6})
    dialog._three_d.setChecked(True)
    settings = dialog.settings()
    assert settings["action"] == "3d"
    assert settings["three_d"]["az"] == (-10, 10)
    assert settings["three_d"]["num"] == 6


def test_3d_options_on_another_movie_are_refused(window):
    reply = window.xpa_test.handle("movie", {"args": f"frame gif {window.tmp_path / 'b.gif'} number 3".split()})
    assert reply["status"] == "error"
