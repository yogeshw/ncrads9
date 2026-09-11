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
What an end-to-end test needs: a real window, and nothing that blocks it.

The unit tests each build the part they are testing. These build the whole
application and drive it the way a user or a script does, so what they need
is a window with a file in it, every modal dialog answered, and no socket.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

#: The test image: big enough to zoom and crop, small enough to be quick.
SIZE = 64


@pytest.fixture
def quiet(monkeypatch):
    """Answer every modal dialog, so a flow never stops to ask.

    Each entry point is stubbed, not just `exec`: the static helpers
    (`QMessageBox.information`, `QFileDialog.getSaveFileName`) do not go
    through it, and one unstubbed helper hangs the whole run.
    """
    from PyQt6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox

    answers: dict[str, object] = {"file": "", "text": "", "item": ""}

    ok = QMessageBox.StandardButton.Ok
    monkeypatch.setattr(QMessageBox, "exec", lambda self: ok)
    for name in ("information", "warning", "critical", "about"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(answers["file"]), ""))
    )
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(answers["file"]), ""))
    )
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: (answers["text"], True)))
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: (answers["item"], True)))
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    return answers


@pytest.fixture
def offline(monkeypatch):
    """No socket. An end-to-end test must not depend on an archive."""
    import socket

    def refuse(*_args, **_kwargs):
        raise OSError("the integration tests run offline")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


@pytest.fixture
def image(tmp_path) -> Path:
    """A FITS image with a WCS, a gradient, and a blank in it.

    The gradient makes a scale change visible, the WCS makes a coordinate
    conversion meaningful, and the blank is there because a NaN is what
    catches an arithmetic path that assumed there were none.
    """
    rows, columns = np.indices((SIZE, SIZE))
    data = (rows + columns * 2).astype(np.float32)
    data[10, 10] = np.nan
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
            "OBJECT": "NGC 5194",
            "BUNIT": "Jy/beam",
        }
    )
    path = tmp_path / "galaxy.fits"
    fits.PrimaryHDU(data=data, header=header).writeto(path)
    return path


@pytest.fixture
def cube(tmp_path) -> Path:
    """A three-plane cube, for the flows that step through one."""
    planes = np.stack([np.full((16, 16), value, dtype=np.float32) for value in (1.0, 2.0, 3.0)])
    path = tmp_path / "cube.fits"
    fits.PrimaryHDU(data=planes).writeto(path)
    return path


@pytest.fixture
def window(qapp, quiet, tmp_path, monkeypatch):
    """The whole application, with its own preferences file.

    Its own file because these flows *change* preferences, and a test must
    not edit the ones the user is running with.
    """
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

    made = MainWindow()
    made._rebuild_image_viewer(False)
    yield made
    made.close()


@pytest.fixture
def xpa(window):
    """XPA over the same window, so a flow can be driven as a script would."""
    from ncrads9.communication.xpa.xpa_commands import XPACommands

    return XPACommands(window)
