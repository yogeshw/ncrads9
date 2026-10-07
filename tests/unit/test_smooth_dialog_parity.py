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

"""The Smooth Parameters window as DS9's (`smooth.tcl`)."""

from ncrads9.ui.dialogs.smooth_dialog import SmoothDialog


def test_it_opens_on_the_settings_in_force(qapp):
    dialog = SmoothDialog(settings={"kernel_type": "Boxcar", "kernel_size": 9, "major_radius": 4})
    assert dialog.settings()["kernel_type"] == "Boxcar"
    assert dialog.settings()["major_radius"] == 4
    assert dialog.settings()["kernel_size"] == 9
    dialog.close()


def test_elliptical_gaussian_round_trips(qapp):
    wanted = {
        "kernel_type": "Gaussian",
        "elliptical": True,
        "major_radius": 6,
        "minor_radius": 2,
        "major_sigma": 3.0,
        "minor_sigma": 1.5,
        "position_angle": 45.0,
    }
    dialog = SmoothDialog(settings=wanted)
    got = dialog.settings()
    for key, value in wanted.items():
        assert got[key] == value, key
    assert dialog.angle.isEnabled()
    dialog.close()


def test_apply_and_clear(qapp):
    dialog = SmoothDialog()
    applied, cleared = [], []
    dialog.smoothing_changed.connect(applied.append)
    dialog.smoothing_cleared.connect(lambda: cleared.append(True))
    dialog.apply()
    dialog.clear()
    assert applied and applied[0]["kernel_type"] == "Gaussian"
    assert cleared == [True]
    menu = dialog.layout().menuBar().actions()[0].menu()
    assert [action.text() for action in menu.actions() if action.text()] == ["Apply", "Clear", "Close"]
    dialog.close()
