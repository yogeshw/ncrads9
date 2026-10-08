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
DS9's Create Movie dialog: what kind, over what, how it changes, how fast.

Laid out as DS9's is (`movie.tcl:38`), with its four groups and its
disabling: an MPEG has no per-frame delay, so the delay box is off for one;
and a fade has no delay of its own either.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from ...io.movie import DEFAULT_DELAY, have_ffmpeg


class MovieDialog(QDialog):
    """Asks what movie to make."""

    def __init__(self, parent=None, is_cube: bool = False, is_three_d: bool = False, three_d: dict | None = None) -> None:
        """
        Args:
            parent: The main window.
            is_cube: Whether the current frame has slices, which is what
                makes a slice movie possible.
            is_three_d: Whether the current frame is a 3D frame, which is
                what a 3D movie turns.
            three_d: The 3D movie's starting values -- DS9 opens its
                dialog on the frame's current view, slice and zoom.
        """
        super().__init__(parent)
        self.setWindowTitle("Create Movie")

        layout = QVBoxLayout(self)

        self._gif = QRadioButton("Animated GIF")
        self._mpeg = QRadioButton("MPEG")
        self._gif.setChecked(True)
        if not have_ffmpeg():
            self._mpeg.setEnabled(False)
            self._mpeg.setToolTip("An MPEG needs ffmpeg on the path")
        layout.addWidget(self._group("Type", [self._gif, self._mpeg]))

        self._frames = QRadioButton("Frames Movie")
        self._slices = QRadioButton("Slice Movie")
        self._three_d = QRadioButton("3D Movie")
        self._frames.setChecked(True)
        self._slices.setEnabled(is_cube)
        self._three_d.setEnabled(is_three_d)
        if not is_three_d:
            self._three_d.setToolTip("A 3D movie turns a 3D frame")
        layout.addWidget(self._group("Format", [self._slices, self._frames, self._three_d]))
        layout.addWidget(self._three_d_group(three_d or {}))
        self._three_d.toggled.connect(lambda _checked=False: self.update_state())

        self._blink = QRadioButton("Blink")
        self._fade = QRadioButton("Fade")
        self._blink.setChecked(True)
        layout.addWidget(self._group("Transition", [self._blink, self._fade], horizontal=True))

        self._delay = QSpinBox()
        self._delay.setRange(1, 1000)
        self._delay.setValue(DEFAULT_DELAY)
        delay_row = QHBoxLayout()
        delay_row.addWidget(self._delay)
        delay_row.addWidget(QLabel("hundredths of a second"))
        holder = QGroupBox("Delay")
        holder.setLayout(delay_row)
        layout.addWidget(holder)
        self._delay_group = holder

        for button in (self._gif, self._mpeg, self._blink, self._fade):
            button.toggled.connect(lambda _checked=False: self.update_state())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.update_state()

    def _three_d_group(self, start: dict) -> QGroupBox:
        """DS9's `Movie3dDialog`: how many frames, and what changes over them."""
        from PyQt6.QtWidgets import QGridLayout, QLineEdit

        holder = QGroupBox("3D Movie")
        grid = QGridLayout(holder)
        grid.addWidget(QLabel("Number"), 0, 0)
        self._number = QSpinBox()
        self._number.setRange(1, 3600)
        self._number.setValue(int(start.get("num", 24)))
        grid.addWidget(self._number, 0, 1)
        grid.addWidget(QLabel("Frames"), 0, 2)
        self._ranges: dict[str, tuple[QLineEdit, QLineEdit]] = {}
        defaults = {"az": (-45, 45), "el": (0, 0), "sl": (1, 1), "zm": (1, 1)}
        for row, (key, label) in enumerate((("az", "Azimuth"), ("el", "Elevation"), ("sl", "Slice"), ("zm", "Zoom")), 1):
            low, high = start.get(key, defaults[key])
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(QLabel("From"), row, 1)
            first, last = QLineEdit(f"{low:g}"), QLineEdit(f"{high:g}")
            grid.addWidget(first, row, 2)
            grid.addWidget(QLabel("To"), row, 3)
            grid.addWidget(last, row, 4)
            self._ranges[key] = (first, last)
        self._repeat = QRadioButton("Repeat")
        self._oscillate = QRadioButton("Oscillate")
        self._repeat.setChecked(start.get("repeat", "repeat") == "repeat")
        self._oscillate.setChecked(start.get("repeat") == "oscillate")
        self._times = QSpinBox()
        self._times.setRange(0, 100)
        self._times.setValue(int(start.get("times", 0)))
        grid.addWidget(self._repeat, 5, 0)
        grid.addWidget(self._oscillate, 5, 1)
        grid.addWidget(self._times, 5, 2)
        grid.addWidget(QLabel("Times"), 5, 3)
        self._three_d_box = holder
        return holder

    @staticmethod
    def _group(title: str, buttons: list[QRadioButton], horizontal: bool = False) -> QGroupBox:
        """One of DS9's labelled groups of choices."""
        holder = QGroupBox(title)
        inner = QHBoxLayout() if horizontal else QVBoxLayout()
        for button in buttons:
            inner.addWidget(button)
        holder.setLayout(inner)
        return holder

    def update_state(self) -> None:
        """Turn off what the chosen combination has no use for."""
        # An MPEG has one frame rate rather than a delay per image, and a
        # fade sets its own pace; DS9 greys the box in both cases.
        self._delay_group.setEnabled(self._gif.isChecked() and self._blink.isChecked())
        self._three_d_box.setVisible(self._three_d.isChecked())

    def settings(self) -> dict:
        """What the dialog says to make."""
        return {
            "type": "gif" if self._gif.isChecked() else "mpeg",
            "action": (
                "slice" if self._slices.isChecked() else ("3d" if self._three_d.isChecked() else "frame")
            ),
            "transition": "fade" if self._fade.isChecked() else "blink",
            "delay": self._delay.value(),
            "three_d": self.three_d_settings(),
        }

    def three_d_settings(self) -> dict:
        """The 3D movie's parameters; a field that is not a number keeps 0."""

        def number(entry) -> float:
            try:
                return float(entry.text())
            except ValueError:
                return 0.0

        settings: dict = {key: (number(a), number(b)) for key, (a, b) in self._ranges.items()}
        settings["num"] = self._number.value()
        settings["repeat"] = "oscillate" if self._oscillate.isChecked() else "repeat"
        settings["times"] = self._times.value()
        return settings

    def choose(self) -> dict | None:
        """Ask, and say what was chosen, or None if it was cancelled."""
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        return self.settings()
