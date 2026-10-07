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

"""DS9's RGB Lock: the three channels of one colour frame share a setting."""

import numpy as np
import pytest

from ncrads9.communication.xpa.xpa_commands import XPACommands
from ncrads9.rendering.scale_algorithms import ScaleAlgorithm


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    made = MainWindow()
    made.frame_controller.new_frame_of_type("rgb")
    frame = made.frame_manager.current_frame
    for index, name in enumerate(("red", "green", "blue")):
        frame.rgb_channels[name] = np.full((16, 16), float(index + 1), dtype=np.float32)
    frame.image_data = frame.rgb_channels["red"]
    yield made
    made.close()


def _set(xpa, line):
    words = line.split()
    return xpa.handle(words[0], {"args": words[1:]})


def test_an_unlocked_scale_stays_on_its_channel(window):
    frame = window.frame_manager.current_frame
    frame.rgb_current_channel = "red"
    window.scale.set_scale(ScaleAlgorithm.LOG)
    assert frame.rgb_channel_scale["red"] is ScaleAlgorithm.LOG
    assert frame.rgb_channel_scale["green"] is ScaleAlgorithm.LINEAR


def test_a_locked_scale_reaches_every_channel(window):
    xpa = XPACommands(window)
    assert _set(xpa, "rgb lock scale yes")["status"] == "ok"
    assert xpa.handle("rgb", {"get": True, "args": ["lock", "scale"]})["result"] == "yes"
    frame = window.frame_manager.current_frame
    frame.rgb_current_channel = "red"
    window.scale.set_scale(ScaleAlgorithm.SQRT)
    assert set(frame.rgb_channel_scale.values()) == {ScaleAlgorithm.SQRT}


def test_scale_and_limits_shares_the_clip_limits(window):
    frame = window.frame_manager.current_frame
    window.frame_controller.set_rgb_lock("scalelimits", True)
    frame.rgb_current_channel = "green"
    window.scale.set_user_limits(0.5, 9.0)
    assert frame.rgb_channel_z1 == {"red": 0.5, "green": 0.5, "blue": 0.5}
    assert frame.rgb_channel_z2 == {"red": 9.0, "green": 9.0, "blue": 9.0}


def test_the_dialog_has_ds9s_lock_menu(window, qapp):
    window.frame_controller.show_rgb_dialog()
    qapp.processEvents()
    dialog = next(
        widget for widget in qapp.topLevelWidgets() if hasattr(widget, "lock_actions") and widget.isVisible()
    )
    assert len(dialog.lock_actions) == 10
    dialog.lock_actions["colorbar"].setChecked(True)
    assert window.frame_manager.current_frame.rgb_locks["colorbar"]
    dialog.close()


def test_an_unknown_lock_is_refused(window):
    assert _set(XPACommands(window), "rgb lock sideways yes")["status"] == "error"
