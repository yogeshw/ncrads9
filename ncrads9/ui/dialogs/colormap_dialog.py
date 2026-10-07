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
DS9's Colormap Parameters window (`ColormapDialog`, `colorbar.tcl`).

A menubar -- File, Colormap -- over two sliders, Contrast from 0 to 10 and
Bias from 0 to 1, and Apply and Close. The sliders act as they are dragged,
as DS9's do. The Colormap menu holds the main window's own colormap
actions rather than copies of them, so a tick in one is a tick in the other
and there is nothing to keep in step.

A ramp through the current colormap is drawn under the sliders; DS9 has
none, but the colorbar it would be compared against is usually behind the
dialog.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QImage, QKeySequence, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenuBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ...colormaps.builtin_maps import get_builtin_colormap
from .modeless import make_modeless

#: Slider steps across each range, so a step is a hundredth of bias.
SLIDER_STEPS = 1000

#: DS9's ranges.
CONTRAST_RANGE = (0.0, 10.0)
BIAS_RANGE = (0.0, 1.0)

CONTRAST_BIAS_FILTER = "Contrast/Bias Files (*.bias *.txt);;All Files (*)"


class _Slider(QWidget):
    """DS9's `slider`: a label, a scale and an entry that agree."""

    changed = pyqtSignal(float)

    def __init__(self, label: str, low: float, high: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._low, self._high = low, high
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel(label)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, SLIDER_STEPS)
        self.entry = QLineEdit()
        self.entry.setFixedWidth(80)
        layout.addWidget(self.title, 0, 0, 1, 2)
        layout.addWidget(self.slider, 1, 0)
        layout.addWidget(self.entry, 1, 1)
        self.slider.valueChanged.connect(self._from_slider)
        self.entry.editingFinished.connect(self._from_entry)

    def value(self) -> float:
        return self._low + (self._high - self._low) * self.slider.value() / SLIDER_STEPS

    def set_value(self, value: float) -> None:
        value = min(max(float(value), self._low), self._high)
        self.slider.blockSignals(True)
        self.slider.setValue(round((value - self._low) / (self._high - self._low) * SLIDER_STEPS))
        self.slider.blockSignals(False)
        self.entry.setText(f"{value:.6g}")

    def _from_slider(self, _step: int) -> None:
        self.entry.setText(f"{self.value():.6g}")
        self.changed.emit(self.value())

    def _from_entry(self) -> None:
        try:
            value = float(self.entry.text())
        except ValueError:
            self.entry.setText(f"{self.value():.6g}")
            return
        self.set_value(value)
        self.changed.emit(self.value())


class ColormapDialog(QDialog):
    """The Colormap Parameters window.

    Args:
        parent: The main window, whose Color menu and colour controller the
            dialog works through. Without one it is a bare pair of sliders,
            which is what the tests build.
    """

    #: Emitted with `{"colormap", "invert", "contrast", "bias"}` on Apply.
    colormap_changed = pyqtSignal(dict)

    def __init__(self, parent: Any | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Colormap Parameters")
        # A parameters window: read and adjusted while looking at the
        # image behind it, so it must not block or cover what it changes.
        make_modeless(self)
        self.setMinimumWidth(420)
        self._window = parent if hasattr(parent, "color") else None
        self._current_colormap = getattr(parent, "current_colormap", "grey") if self._window else "grey"
        self._setup_ui()
        self.sync()

    # -- construction --------------------------------------------------------

    @property
    def _color(self):
        return self._window.color if self._window is not None else None

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setMenuBar(self._build_menus())

        self.contrast_slider = _Slider("Contrast", *CONTRAST_RANGE)
        self.bias_slider = _Slider("Bias", *BIAS_RANGE)
        self.contrast_slider.changed.connect(self._adjust)
        self.bias_slider.changed.connect(self._adjust)
        layout.addWidget(self.contrast_slider)
        layout.addWidget(self.bias_slider)

        self._preview_label = QLabel()
        self._preview_label.setMinimumHeight(30)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._preview_label)

        buttons = QHBoxLayout()
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self._apply)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        buttons.addWidget(apply_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _build_menus(self) -> QMenuBar:
        bar = QMenuBar(self)
        file_menu = bar.addMenu("&File")

        def add(menu, label: str, slot, shortcut: QKeySequence.StandardKey | None = None) -> QAction:
            action = QAction(label, self)
            if shortcut is not None:
                action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda _checked=False: slot())
            menu.addAction(action)
            return action

        self.action_open = add(file_menu, "Open...", self._open, QKeySequence.StandardKey.Open)
        self.action_save = add(file_menu, "Save...", self._save, QKeySequence.StandardKey.Save)
        file_menu.addSeparator()
        add(file_menu, "Apply", self._apply)
        file_menu.addSeparator()
        add(file_menu, "Load Contrast/Bias...", self._load_contrast_bias)
        add(file_menu, "Save Contrast/Bias...", self._save_contrast_bias)
        file_menu.addSeparator()
        add(file_menu, "Load Color Tags...", lambda: self._color and self._color.load_tags())
        add(file_menu, "Save Color Tags...", lambda: self._color and self._color.save_tags())
        add(file_menu, "Delete Color Tags", lambda: self._color and self._color.delete_tags())
        file_menu.addSeparator()
        add(file_menu, "Close", self.close, QKeySequence.StandardKey.Close)

        self.colormap_menu = bar.addMenu("&Colormap")
        menu = getattr(self._window, "menu_bar", None)
        if menu is not None:
            # The main window's own actions: one QAction may sit in any
            # number of menus, and its check mark is shared by all of them.
            submenus = set(getattr(menu, "colormap_submenus", {}).values())
            for action in menu.color_menu.actions():
                child = action.menu()
                if child is not None and (child in submenus or child is menu.user_colormap_menu):
                    self.colormap_menu.addMenu(child)
                elif action in menu.colormap_actions.values():
                    self.colormap_menu.addAction(action)
                elif action.isSeparator() and self.colormap_menu.actions():
                    if not self.colormap_menu.actions()[-1].isSeparator():
                        self.colormap_menu.addSeparator()
            if self.colormap_menu.actions() and not self.colormap_menu.actions()[-1].isSeparator():
                self.colormap_menu.addSeparator()
            self.colormap_menu.addAction(menu.action_invert_colormap)
            reset = QAction("Reset Colormap", self)
            reset.triggered.connect(self._reset)
            self.colormap_menu.addAction(reset)
            for action in menu.colormap_actions.values():
                action.triggered.connect(self._after_colormap_change)
        return bar

    # -- state ---------------------------------------------------------------

    def sync(self) -> None:
        """Show the window's current contrast, bias and colormap."""
        if self._color is not None:
            contrast, bias = self._color.contrast_bias()
            self._current_colormap = self._window.current_colormap
        else:
            contrast, bias = 1.0, 0.5
        self.contrast_slider.set_value(contrast)
        self.bias_slider.set_value(bias)
        self._update_preview()

    def _after_colormap_change(self, _checked: bool = False) -> None:
        try:
            if self.isVisible():
                self.sync()
        except RuntimeError:
            # The dialog has been destroyed; the connection outlived it.
            pass

    def _adjust(self, _value: float = 0.0) -> None:
        """Apply the sliders as they move, as DS9's `AdjustColormap` does."""
        if self._color is not None:
            self._color.set_contrast_bias(self.contrast_slider.value(), self.bias_slider.value())

    def _apply(self) -> None:
        self._adjust()
        self.colormap_changed.emit(self._get_settings())

    def _reset(self) -> None:
        self.contrast_slider.set_value(1.0)
        self.bias_slider.set_value(0.5)
        self._adjust()

    def _get_settings(self) -> dict:
        return {
            "colormap": self._current_colormap,
            "invert": bool(getattr(self._window, "invert_colormap", False)),
            "contrast": self.contrast_slider.value(),
            "bias": self.bias_slider.value(),
        }

    def get_colormap(self) -> str:
        """The colormap the dialog shows."""
        return self._current_colormap

    # -- files ---------------------------------------------------------------

    def _open(self) -> None:
        if self._color is not None:
            self._color.load_user_colormap()
            self.sync()

    def _save(self) -> None:
        if self._color is not None:
            self._color.save_current_colormap()

    def _load_contrast_bias(self, path: str | None = None) -> str | None:
        """Read DS9's contrast/bias file: one line, `<contrast> <bias>`."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Load Contrast/Bias", "", CONTRAST_BIAS_FILTER)
            if not path:
                return None
        try:
            with open(path, encoding="utf-8") as handle:
                words = handle.readline().split()
            contrast, bias = float(words[0]), float(words[1])
        except (OSError, IndexError, ValueError) as exc:
            return f"could not read {path}: {exc}"
        self.contrast_slider.set_value(contrast)
        self.bias_slider.set_value(bias)
        self._apply()
        return None

    def _save_contrast_bias(self, path: str | None = None) -> str | None:
        """Write DS9's contrast/bias file."""
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Save Contrast/Bias", "", CONTRAST_BIAS_FILTER)
            if not path:
                return None
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(f"{self.contrast_slider.value():g} {self.bias_slider.value():g}\n")
        except OSError as exc:
            return f"could not write {path}: {exc}"
        return None

    # -- preview -------------------------------------------------------------

    def _update_preview(self) -> None:
        """Draw a ramp through the current colormap."""
        width, height = 400, 24
        ramp = np.linspace(0.0, 1.0, width, dtype=np.float64)
        if getattr(self._window, "invert_colormap", False):
            ramp = 1.0 - ramp
        colours = self._ramp_colours(ramp)
        image = QImage(width, height, QImage.Format.Format_RGB32)
        for x in range(width):
            red, green, blue = (int(component) for component in colours[x])
            colour = QColor(red, green, blue)
            for y in range(height):
                image.setPixelColor(x, y, colour)
        self._preview_label.setPixmap(QPixmap.fromImage(image))

    def _ramp_colours(self, ramp: NDArray[np.floating]) -> NDArray[np.uint8]:
        """The ramp through the current colormap, as RGB rows."""
        colormap = None
        if self._color is not None:
            try:
                colormap = self._color.colormap(self._current_colormap)
            except ValueError:
                colormap = None
        if colormap is None:
            colormap = get_builtin_colormap(self._current_colormap)
        if colormap is None:
            grey = np.clip(ramp * 255.0, 0, 255).astype(np.uint8)
            return np.stack([grey, grey, grey], axis=-1)
        return colormap.apply_normalized(ramp)
