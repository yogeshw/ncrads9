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
DS9's Smooth Parameters window (`SmoothDialog`, `smooth.tcl`).

A File menu (Apply, Clear, Close), the Function choice -- Boxcar, Tophat,
Gaussian, Elliptical Gaussian, and NCRADS9's Median -- and the sliders that
function takes: Radius for all, Sigma for the Gaussians, and the minor
radius, minor sigma and angle for the elliptical one. Apply turns smoothing
on with these settings; Clear turns it off, as DS9's do.

It opens on the settings in force, not on defaults: reopening it used to
show a Gaussian of sigma 2 whatever was on screen, so Apply undid what the
user had chosen.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenuBar,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .modeless import make_modeless

#: DS9's functions, by the label it gives them and the kernel name kept in
#: the settings. Median is NCRADS9's.
FUNCTIONS: tuple[tuple[str, str, bool], ...] = (
    ("Boxcar", "Boxcar", False),
    ("Tophat", "Tophat", False),
    ("Gaussian", "Gaussian", False),
    ("Elliptical Gaussian", "Gaussian", True),
    ("Median", "Median", False),
)

#: DS9's defaults (`smooth.tcl`, `SmoothDef`).
DEFAULTS: dict = {
    "kernel_type": "Gaussian",
    "elliptical": False,
    "major_radius": 3,
    "minor_radius": 3,
    "sigma": 1.5,
    "major_sigma": 1.5,
    "minor_sigma": 1.5,
    "position_angle": 0.0,
    "preserve_nan": True,
    "normalize": True,
}


class _Slider(QWidget):
    """DS9's `slider`: a label, a scale and an entry."""

    def __init__(self, label: str, low: float, high: float, integer: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._low, self._high, self._integer = low, high, integer
        self._steps = int(high - low) if integer else 1000
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel(label)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, self._steps)
        self.entry = QLineEdit()
        self.entry.setFixedWidth(70)
        layout.addWidget(self.title, 0, 0)
        layout.addWidget(self.slider, 0, 1)
        layout.addWidget(self.entry, 0, 2)
        #: The value itself; the slider holds only the nearest step of it.
        self._value = float(low)
        self.slider.valueChanged.connect(self._from_slider)
        self.entry.editingFinished.connect(self._from_entry)

    def _text(self, value: float) -> str:
        return str(int(round(value))) if self._integer else f"{value:.4g}"

    def _from_slider(self, step: int) -> None:
        value = self._low + (self._high - self._low) * step / self._steps
        self._value = float(round(value)) if self._integer else value
        self.entry.setText(self._text(self._value))

    def value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        value = min(max(float(value), self._low), self._high)
        self._value = float(round(value)) if self._integer else value
        self.slider.blockSignals(True)
        self.slider.setValue(round((value - self._low) / (self._high - self._low) * self._steps))
        self.slider.blockSignals(False)
        self.entry.setText(self._text(value))

    def _from_entry(self) -> None:
        try:
            self.set_value(float(self.entry.text()))
        except ValueError:
            self.entry.setText(self._text(self.value()))


class SmoothDialog(QDialog):
    """The Smooth Parameters window.

    Args:
        parent: The main window, or nothing.
        settings: The smoothing in force, to open on.
    """

    #: Apply: the settings to smooth with.
    smoothing_changed = pyqtSignal(dict)
    #: Clear: turn smoothing off.
    smoothing_cleared = pyqtSignal()

    def __init__(self, parent: QWidget | None = None, settings: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Smooth Parameters")
        # A parameters window: read and adjusted while looking at the
        # image behind it, so it must not block or cover what it changes.
        make_modeless(self)
        self.setMinimumWidth(380)
        self._setup_ui()
        self.set_settings(settings or getattr(parent, "_smooth_settings", None) or {})

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setMenuBar(self._build_menus())

        function_group = QGroupBox("Function")
        function_layout = QHBoxLayout(function_group)
        self._functions = QButtonGroup(self)
        self._function_buttons: list[QRadioButton] = []
        for index, (label, _kernel, _elliptical) in enumerate(FUNCTIONS):
            button = QRadioButton(label)
            self._functions.addButton(button, index)
            self._function_buttons.append(button)
            function_layout.addWidget(button)
        self._functions.idToggled.connect(lambda _id, on: on and self._enable())
        layout.addWidget(function_group)

        parameters = QGroupBox("Parameters")
        parameters_layout = QVBoxLayout(parameters)
        self.radius = _Slider("Radius", 1, 20, True)
        self.radius_minor = _Slider("Radius Minor", 1, 20, True)
        self.sigma = _Slider("Sigma", 1, 20, False)
        self.sigma_minor = _Slider("Sigma Minor", 1, 20, False)
        self.angle = _Slider("Angle", 0, 180, False)
        for widget in (self.radius, self.radius_minor, self.sigma, self.sigma_minor, self.angle):
            parameters_layout.addWidget(widget)
        self._width_note = QLabel()
        parameters_layout.addWidget(self._width_note)
        self.radius.slider.valueChanged.connect(lambda _v: self._describe())
        layout.addWidget(parameters)

        self._preserve_nan = QCheckBox("Preserve NaN values")
        layout.addWidget(self._preserve_nan)

        buttons = QHBoxLayout()
        for label, slot in (("Apply", self.apply), ("Clear", self.clear), ("Close", self.close)):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, s=slot: s())
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def _build_menus(self) -> QMenuBar:
        bar = QMenuBar(self)
        file_menu = bar.addMenu("&File")
        for label, slot, key in (
            ("Apply", self.apply, None),
            ("Clear", self.clear, None),
            (None, None, None),
            ("Close", self.close, QKeySequence.StandardKey.Close),
        ):
            if label is None:
                file_menu.addSeparator()
                continue
            action = QAction(label, self)
            if key is not None:
                action.setShortcut(QKeySequence(key))
            action.triggered.connect(lambda _checked=False, s=slot: s())
            file_menu.addAction(action)
        return bar

    # -- state ---------------------------------------------------------------

    def _function(self) -> tuple[str, str, bool]:
        return FUNCTIONS[max(0, self._functions.checkedId())]

    def _enable(self) -> None:
        label, kernel, elliptical = self._function()
        self.sigma.setEnabled(kernel == "Gaussian")
        for widget in (self.radius_minor, self.sigma_minor, self.angle):
            widget.setEnabled(elliptical)
        self._describe()

    def _describe(self) -> None:
        label, kernel, _elliptical = self._function()
        width = 2 * int(self.radius.value()) + 1
        name = "Width" if kernel in ("Boxcar", "Median") else "Diameter"
        self._width_note.setText(f"{name}: 2*radius+1 = {width}")

    def set_settings(self, settings: dict) -> None:
        """Show these settings; DS9's defaults fill what is missing."""
        merged = {**DEFAULTS, **settings}
        kernel = str(merged.get("kernel_type", "Gaussian")).capitalize()
        elliptical = bool(merged.get("elliptical")) and kernel == "Gaussian"
        index = next(
            (i for i, (_l, k, e) in enumerate(FUNCTIONS) if k == kernel and e == elliptical),
            2,
        )
        self._function_buttons[index].setChecked(True)
        radius = merged.get("major_radius")
        if radius is None or ("kernel_size" in settings and "major_radius" not in settings):
            radius = max(1, (int(merged.get("kernel_size", 7)) - 1) // 2)
        self.radius.set_value(radius)
        self.radius_minor.set_value(merged.get("minor_radius", radius))
        self.sigma.set_value(merged.get("major_sigma", merged.get("sigma", 1.5)) if elliptical else merged.get("sigma", 1.5))
        self.sigma_minor.set_value(merged.get("minor_sigma", 1.5))
        self.angle.set_value(merged.get("position_angle", 0.0))
        self._preserve_nan.setChecked(bool(merged.get("preserve_nan", True)))
        self._enable()

    def settings(self) -> dict:
        """The settings shown, in the keys the smoothing code reads."""
        _label, kernel, elliptical = self._function()
        radius = int(self.radius.value())
        return {
            "kernel_type": kernel,
            "elliptical": elliptical,
            "kernel_size": 2 * radius + 1,
            "major_radius": radius,
            "minor_radius": int(self.radius_minor.value()),
            "sigma": self.sigma.value(),
            "major_sigma": self.sigma.value(),
            "minor_sigma": self.sigma_minor.value(),
            "position_angle": self.angle.value(),
            "preserve_nan": self._preserve_nan.isChecked(),
            "normalize": True,
        }

    # Kept for callers from before the rewrite.
    _get_settings = settings

    def apply(self) -> None:
        """DS9's Apply: smooth with these settings."""
        self.smoothing_changed.emit(self.settings())

    def clear(self) -> None:
        """DS9's Clear: smoothing off."""
        self.smoothing_cleared.emit()
