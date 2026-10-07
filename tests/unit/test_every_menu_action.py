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
Every menu entry, chosen once, on a loaded image: none may raise.

An exception in a Qt slot does not fail anything by itself -- PyQt prints
it and carries on -- so a menu entry can be broken for a long time with
nobody the wiser. This chooses all eight hundred-odd of them in turn, with
every dialog answering "cancel" and the network refused, and collects what
reaches `sys.excepthook`. The first run found one: Block 64 on a 64-pixel
image left a single pixel, and contouring it raised.
"""

from __future__ import annotations

import socket
import sys
import traceback

import numpy as np
import pytest
from astropy.io import fits

#: Entries that end the session or reach a printer.
SKIPPED = {"exit", "quit", "close window", "print", "page setup"}


@pytest.fixture
def quiet(monkeypatch):
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QColorDialog, QDialog, QFileDialog, QInputDialog, QMessageBox

    ok = QMessageBox.StandardButton.Ok
    monkeypatch.setattr(QMessageBox, "exec", lambda self: ok)
    for name in ("information", "warning", "critical", "about", "question", "aboutQt"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([], "")))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda *a, **k: (0, False)))
    monkeypatch.setattr(QInputDialog, "getDouble", staticmethod(lambda *a, **k: (0.0, False)))
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor()))
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    def refuse(*_args, **_kwargs):
        raise OSError("the menu walk runs offline")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    import webbrowser

    monkeypatch.setattr(webbrowser, "open", lambda *a, **k: True)


def test_no_menu_entry_raises(qapp, quiet, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QDialog

    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    rows, columns = np.indices((64, 64))
    header = fits.Header(
        {
            "CRPIX1": 32,
            "CRPIX2": 32,
            "CRVAL1": 202.48,
            "CRVAL2": 47.21,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
        }
    )
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32), header=header).writeto(path)

    window = MainWindow()
    window.resize(1000, 800)
    window.show()
    window.display.load_fits(str(path))
    qapp.processEvents()

    entries = []

    def walk(menu, trail):
        for action in menu.actions():
            if action.isSeparator():
                continue
            label = action.text().replace("&", "")
            if action.menu() is not None:
                walk(action.menu(), [*trail, label])
            else:
                entries.append((" > ".join([*trail, label]), action))

    for top in window.menuBar().actions():
        if top.menu() is not None:
            walk(top.menu(), [top.text().replace("&", "")])
    assert len(entries) > 700

    failures: list[str] = []
    current = [""]
    monkeypatch.setattr(
        sys,
        "excepthook",
        lambda kind, value, trace: failures.append(
            f"{current[0]}: {''.join(traceback.format_exception(kind, value, trace))[-600:]}"
        ),
    )
    try:
        for name, action in entries:
            if name.split(" > ")[-1].lower().rstrip(".") in SKIPPED:
                continue
            current[0] = name
            action.trigger()
            qapp.processEvents()
            for widget in qapp.topLevelWidgets():
                if widget is not window and isinstance(widget, QDialog) and widget.isVisible():
                    widget.close()
            frame = window.frame_manager.current_frame
            if frame is None or frame.image_data is None:
                window.display.load_fits(str(path))
                qapp.processEvents()
    finally:
        # The SAMP menu starts a hub; it must not outlive the test.
        samp = getattr(window, "samp", None)
        if samp is not None:
            samp.clean_exit()
            if samp.hub_running():
                samp.stop_hub()
        window.close()

    assert not failures, "\n\n".join(failures)
