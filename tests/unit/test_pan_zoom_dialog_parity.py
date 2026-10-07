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
The Pan Zoom Rotate dialog against DS9's `PanZoomDialog` (`panzoom.tcl`).

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.wcs import WCS
from PyQt6.QtWidgets import QMessageBox

from ncrads9.core.wcs_handler import WCSHandler
from ncrads9.ui.dialogs.pan_zoom_rotate_dialog import PanZoomRotateDialog
from ncrads9.ui.main_window import MainWindow


@pytest.fixture
def window(qapp):
    # The default renderer, as the XPA pan tests use: the GL canvas pans
    # to any point, where the CPU view can only scroll within its range.
    main = MainWindow()
    main.resize(900, 800)
    yield main
    main.close()


def _load(window: MainWindow, size: int = 400, with_wcs: bool = False) -> None:
    frame = window.frame_manager.current_frame
    image = np.arange(size * size, dtype=np.float32).reshape(size, size)
    frame.image_data = image.copy()
    frame.original_image_data = image.copy()
    if with_wcs:
        wcs = WCS(naxis=2)
        wcs.wcs.crpix = [size / 2.0, size / 2.0]
        wcs.wcs.cdelt = [-0.0002777778, 0.0002777778]
        wcs.wcs.crval = [202.4708, 47.1953]
        wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
        frame.wcs_handler = WCSHandler(wcs=wcs)
    window.z1 = window.z2 = None
    window.frame_controller.update_display()


def _open(window: MainWindow) -> PanZoomRotateDialog:
    window.zoom.show_pan_zoom_rotate_dialog()
    dialog = window.zoom._live_pan_zoom_dialog()
    assert dialog is not None
    return dialog


def test_fields_are_seeded_from_the_frame(window):
    _load(window)
    window.zoom.set_rotation(90)
    window.zoom.set_zoom(2.0)
    dialog = _open(window)

    assert float(dialog.zoom_x_edit.text()) == pytest.approx(2.0)
    assert float(dialog.zoom_y_edit.text()) == pytest.approx(2.0)
    assert float(dialog.rotate_edit.text()) == pytest.approx(90.0)
    # No WCS: DS9's default system, wcs, falls back to physical.
    assert dialog.coord_button.system == "physical"
    assert not dialog.coord_button.actions_by_value["wcs"].isEnabled()
    x, y = window.zoom.pan_position()
    assert float(dialog.pan_x_edit.text()) == pytest.approx(x, abs=1.0)
    assert float(dialog.pan_y_edit.text()) == pytest.approx(y, abs=1.0)


def test_pan_to_a_sexagesimal_wcs_position(window):
    # Large enough that the scrolled CPU view can reach the target.
    _load(window, size=1000, with_wcs=True)
    dialog = _open(window)
    assert dialog.coord_button.system == "wcs"
    assert dialog.coord_button.text() == "fk5"

    dialog.coord_button.actions_by_value["sexagesimal"].trigger()
    assert ":" in dialog.pan_x_edit.text()

    frame = window.frame_manager.current_frame
    target = frame.wcs_handler.wcs.pixel_to_world(399.0, 599.0)  # image (400, 600)
    ra = target.ra.to_string(unit="hourangle", sep=":", precision=4)
    dec = target.dec.to_string(unit="deg", sep=":", precision=3, alwayssign=True)
    dialog.zoom_x_edit.setText("2")
    dialog.zoom_y_edit.setText("2")
    dialog.pan_x_edit.setText(ra)
    dialog.pan_y_edit.setText(dec)
    dialog.apply_button.click()

    assert frame.zoom == pytest.approx(2.0)
    x, y = window.zoom.pan_position()
    assert x == pytest.approx(400.0, abs=1.0)
    assert y == pytest.approx(600.0, abs=1.0)
    # And the dialog now shows where the view went.
    assert dialog.pan_x_edit.text().startswith(ra[:8])


def test_unequal_zooms_are_refused(window, monkeypatch):
    _load(window)
    dialog = _open(window)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    dialog.zoom_x_edit.setText("2")
    dialog.zoom_y_edit.setText("4")
    dialog.apply_button.click()
    assert warnings and "equal" in warnings[0]
    assert window.frame_manager.current_frame.zoom != pytest.approx(4.0)


def test_fields_follow_zoom_rotation_and_frame_changes(window):
    _load(window)
    dialog = _open(window)

    window.zoom.set_zoom(4.0)
    assert float(dialog.zoom_x_edit.text()) == pytest.approx(4.0)
    window.zoom.pan_to_image(120.0, 80.0)
    assert float(dialog.pan_x_edit.text()) == pytest.approx(120.0, abs=0.5)
    assert float(dialog.pan_y_edit.text()) == pytest.approx(80.0, abs=0.5)
    # Last: offscreen, a rotation drops the GL canvas for the CPU view.
    window.zoom.set_rotation(180)
    assert float(dialog.rotate_edit.text()) == pytest.approx(180.0)

    other = window.frame_manager.new_frame()
    other.image_data = np.ones((64, 64), dtype=np.float32)
    other.original_image_data = other.image_data.copy()
    other.zoom = 0.5
    other.rotation = 0.0
    window.frame_controller.goto_index(1)
    assert float(dialog.zoom_x_edit.text()) == pytest.approx(0.5)
    assert float(dialog.rotate_edit.text()) == pytest.approx(0.0)


def test_menus_match_ds9(window):
    _load(window)
    dialog = _open(window)
    assert list(dialog.menus) == ["File", "Edit", "Pan", "Zoom", "Orientation", "Rotate"]

    labels = {name: [a.text() for a in menu.actions() if not a.isSeparator()] for name, menu in dialog.menus.items()}
    assert labels["File"] == ["Apply", "Close"]
    assert labels["Edit"] == ["Cut", "Copy", "Paste"]
    menu = window.menu_bar
    assert dialog.menus["Pan"].actions() == [menu.action_zoom_center, menu.action_zoom_align]
    assert menu.zoom_preset_actions[0.03125] in dialog.menus["Zoom"].actions()
    assert menu.action_zoom_fit in dialog.menus["Zoom"].actions()
    assert dialog.menus["Orientation"].actions() == list(menu.zoom_orientation_actions.values())
    assert dialog.menus["Rotate"].actions() == list(menu.zoom_rotation_actions.values())
    assert dialog.apply_button.text() == "Apply" and dialog.close_button.text() == "Close"

    # The shared actions act on the frame, and the dialog follows.
    menu.zoom_preset_actions[8.0].trigger()
    assert float(dialog.zoom_x_edit.text()) == pytest.approx(8.0)


def test_reopening_raises_the_same_dialog(window):
    _load(window)
    first = _open(window)
    second = _open(window)
    assert first is second
    assert not first.isModal()
    first.close()
    assert window.zoom._live_pan_zoom_dialog() is None
    third = _open(window)
    assert third is not first
