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
DS9's Pan Zoom Rotate Parameters dialog (`PanZoomDialog`, `panzoom.tcl`).

A modeless window you leave open beside the image: its fields follow the
current frame as it is panned, zoomed and rotated, and Apply sends what
you typed back. The Pan row is a position in any of DS9's coordinate
systems, chosen with the button beside it, so `13:29:52.7 +47:11:43`
in FK5 is as good as an image pixel.

The Zoom row has DS9's two fields, x and y, which may differ.

The menus are DS9's: File, Edit, Pan, Zoom, Orientation and Rotate. The
last four hold the main window's own Zoom-menu actions -- one QAction can
sit in several menus and shares its check mark among them -- so the two
can never disagree about the frame's zoom or rotation.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..widgets.coord_menu_button import CoordMenuButton


class PanZoomRotateDialog(QDialog):
    """Pan, zoom and rotate the current frame by typing the values."""

    #: Emitted by Apply with zoom, rotation, pan (two words), system and sky.
    parameters_changed = pyqtSignal(dict)

    #: Emitted when the Pan row's coordinate system, sky or format changes,
    #: so the owner can rewrite the position in the new system.
    coordinates_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pan Zoom Rotate Parameters")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self._window: Any = parent

        layout = QVBoxLayout(self)
        layout.setMenuBar(self._build_menus())

        grid = QGridLayout()
        self.zoom_x_edit = QLineEdit()
        self.zoom_y_edit = QLineEdit()
        grid.addWidget(QLabel("Zoom"), 0, 0)
        grid.addWidget(self.zoom_x_edit, 0, 1)
        grid.addWidget(self.zoom_y_edit, 0, 2)

        self.rotate_edit = QLineEdit()
        grid.addWidget(QLabel("Rotate"), 1, 0)
        grid.addWidget(self.rotate_edit, 1, 1)
        grid.addWidget(QLabel("Degrees"), 1, 2)

        self.pan_x_edit = QLineEdit()
        self.pan_y_edit = QLineEdit()
        self.coord_button = CoordMenuButton(self)
        self.coord_button.changed.connect(lambda *_: self.coordinates_changed.emit())
        grid.addWidget(QLabel("Pan"), 2, 0)
        grid.addWidget(self.pan_x_edit, 2, 1)
        grid.addWidget(self.pan_y_edit, 2, 2)
        grid.addWidget(self.coord_button, 2, 3)
        for edit in (self.zoom_x_edit, self.zoom_y_edit, self.rotate_edit, self.pan_x_edit, self.pan_y_edit):
            edit.setMinimumWidth(110)
            # Return applies, as it does in DS9's entries.
            edit.returnPressed.connect(self.apply)
        layout.addLayout(grid)

        buttons = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.apply_button.setAutoDefault(False)
        self.apply_button.clicked.connect(self.apply)
        self.close_button = QPushButton("Close")
        self.close_button.setAutoDefault(False)
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    # -- menus ---------------------------------------------------------------

    def _build_menus(self) -> QMenuBar:
        """DS9's File, Edit, Pan, Zoom, Orientation and Rotate menus."""
        bar = QMenuBar(self)
        #: Menu title -> the menu, so a test can look inside one.
        self.menus = {}

        file_menu = bar.addMenu("&File")
        self.menus["File"] = file_menu
        self.action_apply = QAction("Apply", self)
        self.action_apply.triggered.connect(lambda _checked=False: self.apply())
        file_menu.addAction(self.action_apply)
        file_menu.addSeparator()
        self.action_close = QAction("Close", self)
        self.action_close.setShortcut(QKeySequence("Ctrl+W"))
        self.action_close.triggered.connect(lambda _checked=False: self.close())
        file_menu.addAction(self.action_close)

        edit_menu = bar.addMenu("&Edit")
        self.menus["Edit"] = edit_menu
        for label, key, method in (("Cut", "Ctrl+X", "cut"), ("Copy", "Ctrl+C", "copy"), ("Paste", "Ctrl+V", "paste")):
            action = QAction(label, self)
            action.setShortcut(QKeySequence(key))
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.triggered.connect(lambda _checked=False, m=method: self._edit(m))
            edit_menu.addAction(action)

        menu = getattr(self._window, "menu_bar", None)
        pan_menu = bar.addMenu("&Pan")
        zoom_menu = bar.addMenu("&Zoom")
        orient_menu = bar.addMenu("&Orientation")
        rotate_menu = bar.addMenu("&Rotate")
        self.menus.update({"Pan": pan_menu, "Zoom": zoom_menu, "Orientation": orient_menu, "Rotate": rotate_menu})
        if menu is None:
            return bar

        pan_menu.addAction(menu.action_zoom_center)
        pan_menu.addAction(menu.action_zoom_align)

        zoom_menu.addAction(menu.action_zoom_in)
        zoom_menu.addAction(menu.action_zoom_out)
        zoom_menu.addAction(menu.action_zoom_fit)
        zoom_menu.addSeparator()
        for action in menu.zoom_preset_actions.values():
            zoom_menu.addAction(action)

        for action in menu.zoom_orientation_actions.values():
            orient_menu.addAction(action)
        for action in menu.zoom_rotation_actions.values():
            rotate_menu.addAction(action)
        return bar

    def _edit(self, method: str) -> None:
        """Cut, copy or paste in whichever entry has the focus."""
        widget = self.focusWidget()
        if isinstance(widget, QLineEdit):
            getattr(widget, method)()

    # -- values --------------------------------------------------------------

    def set_values(
        self, *, zoom: float, rotation: float, pan: tuple[str, str], zoom_y: float | None = None
    ) -> None:
        """Show a frame's zooms, rotation and pan (already in the Pan system)."""
        self.zoom_x_edit.setText(f"{zoom:.8g}")
        self.zoom_y_edit.setText(f"{zoom if zoom_y is None else zoom_y:.8g}")
        self.rotate_edit.setText(f"{rotation:.8g}")
        self.pan_x_edit.setText(pan[0])
        self.pan_y_edit.setText(pan[1])

    def clear_values(self) -> None:
        """Empty every field, as DS9 does when there is no frame."""
        for edit in (self.zoom_x_edit, self.zoom_y_edit, self.rotate_edit, self.pan_x_edit, self.pan_y_edit):
            edit.clear()

    def warn(self, message: str) -> None:
        """Say why the values were not applied."""
        QMessageBox.warning(self, "Pan Zoom Rotate Parameters", message)

    def apply(self) -> None:
        """Read the fields and emit them, refusing what cannot be applied."""
        try:
            zoom_x = float(self.zoom_x_edit.text())
            zoom_y = float(self.zoom_y_edit.text() or self.zoom_x_edit.text())
            rotation = float(self.rotate_edit.text() or 0.0)
        except ValueError:
            self.warn("Zoom and rotation must be numbers.")
            return
        if zoom_x <= 0 or zoom_y <= 0:
            self.warn("Zoom must be greater than zero.")
            return
        pan = (self.pan_x_edit.text().strip(), self.pan_y_edit.text().strip())
        self.parameters_changed.emit(
            {
                "zoom": zoom_x,
                "zoom_y": zoom_y,
                "rotation": rotation,
                "pan": pan if all(pan) else None,
                "system": self.coord_button.system,
                "sky": self.coord_button.sky,
            }
        )
