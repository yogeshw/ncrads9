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

    def __init__(self, parent=None, is_cube: bool = False) -> None:
        """
        Args:
            parent: The main window.
            is_cube: Whether the current frame has slices, which is what
                makes a slice movie possible.
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
        # A 3D movie turns a 3D frame, which arrives with M9-21.
        self._three_d.setEnabled(False)
        self._three_d.setToolTip("3D frames arrive in M9-21")
        layout.addWidget(self._group("Format", [self._slices, self._frames, self._three_d]))

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

    def settings(self) -> dict:
        """What the dialog says to make."""
        return {
            "type": "gif" if self._gif.isChecked() else "mpeg",
            "action": (
                "slice" if self._slices.isChecked() else ("3d" if self._three_d.isChecked() else "frame")
            ),
            "transition": "fade" if self._fade.isChecked() else "blink",
            "delay": self._delay.value(),
        }

    def choose(self) -> dict | None:
        """Ask, and say what was chosen, or None if it was cancelled."""
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        return self.settings()
