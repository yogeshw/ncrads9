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
DS9's 3D dialog: the two angles, the z scale, and what is drawn over it.

Laid out as DS9's is (`3d.tcl:35`): azimuth and elevation on sliders, the
Z axis scale in a box, and the Render, Highlite, Border and Compass menus
above them.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenuBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from ...frames.frame_3d import BACKGROUNDS, METHODS
from ..menu_bar import REGION_COLORS

#: What each rendering method is called on DS9's Render menu.
METHOD_LABELS: dict[str, str] = {"mip": "MIP", "aip": "AIP"}


class Frame3DDialog(QDialog):
    """Where the cube is seen from."""

    def __init__(self, controller, parent=None) -> None:
        """
        Args:
            controller: The `Frame3DController` this drives.
            parent: The main window.
        """
        super().__init__(parent)
        self._controller = controller
        self._loading = False
        self.setWindowTitle("3D")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setMenuBar(self._menus())

        form = QFormLayout()
        self._azimuth = self._slider(-180, 180)
        self._azimuth_value = QLabel()
        form.addRow("Azimuth:", self._row(self._azimuth, self._azimuth_value))

        self._elevation = self._slider(-90, 90)
        self._elevation_value = QLabel()
        form.addRow("Elevation:", self._row(self._elevation, self._elevation_value))

        self._scale = QDoubleSpinBox()
        self._scale.setRange(0.01, 100.0)
        self._scale.setDecimals(2)
        self._scale.setSingleStep(0.5)
        self._scale.valueChanged.connect(lambda _value: self.apply_view())
        form.addRow("Z Axis Scale:", self._scale)
        layout.addLayout(form)

        self._what = QLabel()
        self._what.setWordWrap(True)
        layout.addWidget(self._what)

        buttons = QHBoxLayout()
        #: Button name -> the button, so a test can press one.
        self.buttons: dict[str, QPushButton] = {}
        for name, label, slot in (
            ("apply", "Apply", self.apply_view),
            ("reset", "Reset", self.reset),
            ("close", "Close", self.close),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
            self.buttons[name] = button
        layout.addLayout(buttons)

        self.reload()

    def _slider(self, low: int, high: int) -> QSlider:
        """One of DS9's angle sliders."""
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(low, high)
        slider.valueChanged.connect(lambda _value: self.apply_view())
        return slider

    @staticmethod
    def _row(slider: QSlider, label: QLabel) -> QLabel:
        """A slider with its value beside it, as one widget for the form."""
        holder = QLabel()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(slider)
        label.setMinimumWidth(48)
        row.addWidget(label)
        return holder

    def _menus(self) -> QMenuBar:
        """DS9's Render, Highlite, Border and Compass menus."""
        bar = QMenuBar(self)
        #: Action name -> the action, so a test can trigger one.
        self.actions_by_name: dict[str, QAction] = {}

        render = bar.addMenu("&Render")
        method_group = QActionGroup(self)
        for method in METHODS:
            action = self._add(render, f"method_{method}", METHOD_LABELS[method], checkable=True)
            method_group.addAction(action)
            action.triggered.connect(
                lambda _checked=False, chosen=method: self._controller.set_method(chosen)
            )
        render.addSeparator()
        background_group = QActionGroup(self)
        for kind in BACKGROUNDS:
            action = self._add(render, f"background_{kind}", kind.title(), checkable=True)
            background_group.addAction(action)
            action.triggered.connect(
                lambda _checked=False, chosen=kind: self._controller.set_background(chosen)
            )

        for name, label in (("highlite", "&Highlite"), ("border", "&Border"), ("compass", "&Compass")):
            menu = bar.addMenu(label)
            show = self._add(menu, f"{name}_show", "Show", checkable=True)
            show.triggered.connect(lambda checked=False, key=name: self._controller.set_setting(key, checked))
            menu.addSeparator()
            colors = menu.addMenu("Color")
            group = QActionGroup(self)
            for color in REGION_COLORS:
                action = self._add(colors, f"{name}_{color}", color.title(), checkable=True)
                group.addAction(action)
                action.triggered.connect(
                    lambda _checked=False, key=name, chosen=color: self._controller.set_setting(
                        f"{key}_color", chosen
                    )
                )
        return bar

    def _add(self, menu, name: str, label: str, checkable: bool = False) -> QAction:
        """One menu entry, remembered by name."""
        action = QAction(label, self)
        action.setCheckable(checkable)
        menu.addAction(action)
        self.actions_by_name[name] = action
        return action

    # -- what it shows -------------------------------------------------------------

    def reload(self) -> None:
        """Fill the dialog in from the frame."""
        self._loading = True
        try:
            view = self._controller.view()
            self._azimuth.setValue(int(round(view.azimuth)))
            self._elevation.setValue(int(round(view.elevation)))
            self._scale.setValue(view.scale)
            self._azimuth_value.setText(f"{view.azimuth:g}°")
            self._elevation_value.setText(f"{view.elevation:g}°")

            for method in METHODS:
                self.actions_by_name[f"method_{method}"].setChecked(
                    self._controller.setting("method") == method
                )
            for kind in BACKGROUNDS:
                self.actions_by_name[f"background_{kind}"].setChecked(
                    self._controller.setting("background") == kind
                )
            for name in ("highlite", "border", "compass"):
                self.actions_by_name[f"{name}_show"].setChecked(bool(self._controller.setting(name)))
                chosen = self._controller.setting(f"{name}_color")
                for color in REGION_COLORS:
                    self.actions_by_name[f"{name}_{color}"].setChecked(color == chosen)

            cube = self._controller.cube()
            if cube is None:
                self._what.setText(
                    "The current frame is not a 3D frame. " "Frame -> New Frame 3D, then load a cube."
                )
            else:
                depth, height, width = cube.shape
                self._what.setText(f"Cube: {width} x {height} x {depth}")
        finally:
            self._loading = False

    # -- what its controls do --------------------------------------------------------

    def apply_view(self) -> None:
        """Turn the cube to what the sliders say."""
        if self._loading:
            return
        self._controller.set_view(
            azimuth=float(self._azimuth.value()),
            elevation=float(self._elevation.value()),
            scale=self._scale.value(),
        )
        self._azimuth_value.setText(f"{self._azimuth.value()}°")
        self._elevation_value.setText(f"{self._elevation.value()}°")

    def reset(self) -> None:
        """Back to face-on, DS9's Reset."""
        self._controller.reset()
        self.reload()
