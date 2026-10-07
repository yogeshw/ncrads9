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

"""DS9's Block Parameters window (`block.tcl`)."""

import numpy as np
import pytest
from astropy.io import fits


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    path = tmp_path / "img.fits"
    fits.PrimaryHDU(data=np.arange(4096, dtype=np.float32).reshape(64, 64)).writeto(path)
    made = MainWindow()
    made.display.load_fits(str(path))
    yield made
    made.close()


def _dialog(window, qapp):
    window.analysis.show_block_dialog()
    qapp.processEvents()
    return window._open_windows["BlockDialog"]


def test_apply_blocks_by_any_whole_factor(window, qapp):
    dialog = _dialog(window, qapp)
    dialog.block_x.setText("3")
    dialog.block_y.setText("3")
    dialog.apply()
    assert window.frame_manager.current_frame.block_factor == 3
    dialog.close()


def test_unequal_factors_are_refused(window, qapp):
    dialog = _dialog(window, qapp)
    dialog.block_x.setText("2")
    dialog.block_y.setText("4")
    dialog.apply()
    assert window.frame_manager.current_frame.block_factor == 1
    assert "different" in dialog.message.text()
    dialog.close()


def test_it_follows_the_block_menu(window, qapp):
    dialog = _dialog(window, qapp)
    window.analysis.set_block_factor(4)
    assert dialog.block_x.text() == "4"
    titles = [action.text() for action in dialog.layout().menuBar().actions()]
    assert titles == ["&File", "&Block"]
    dialog.close()
