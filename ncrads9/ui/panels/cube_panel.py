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
The Cube dialog: which slice of a data cube is on screen.

DS9's `Frame -> Cube` (`ds9/library/cube.tcl`) is a small dialog holding a
slider over the slice axis with first/previous/next/last buttons, an interval
in seconds, a play/stop pair that walks the slices, and an Axis Order menu
offering the six permutations `123` .. `321`. This is that dialog.

It was a `QDockWidget` before M4, with a slice axis given as a numpy axis
number and no axis-order support, and nothing ever constructed it. It is now a
dialog, as DS9 has it, and speaks `core.cube_handler.AxisOrder` so the axis
numbers mean what they mean in the FITS header and in DS9's own menu.

The dialog holds no cube of its own: it reports what the user asked for and
the Frame controller does it, so a cube can be stepped from the dialog, the
menu or an XPA `cube` command (M8) through one path.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core.cube_handler import AXIS_ORDERS, AxisOrder

#: DS9's default interval between slices, in seconds.
DEFAULT_INTERVAL = 0.5
#: The range the interval spinbox allows, in seconds.
MIN_INTERVAL, MAX_INTERVAL = 0.02, 10.0
#: Milliseconds per second, for the play timer.
MS_PER_SECOND = 1000


class CubePanel(QDialog):
    """DS9's Cube dialog.

    Args:
        parent: Optional parent widget.
    """

    #: The slice the user wants, counting from zero.
    slice_changed: pyqtSignal = pyqtSignal(int)
    #: A new axis order, as its three-digit string.
    axis_order_changed: pyqtSignal = pyqtSignal(str)
    #: True to start walking the slices, False to stop.
    play_changed: pyqtSignal = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cube")
        self.setModal(False)

        self._depth = 1
        self._slice = 0
        self._order = AxisOrder()
        #: Guards the slider/spinbox echo, so setting one does not re-emit.
        self._updating = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_slice_group())
        layout.addWidget(self._build_axis_group())

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self.close)
        layout.addWidget(box)

        self.set_depth(1)

    # -- construction --------------------------------------------------------

    def _build_slice_group(self) -> QGroupBox:
        """The slider, the readout and the transport buttons."""
        group = QGroupBox("Slice")
        grid = QGridLayout(group)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(1)
        self._slider.valueChanged.connect(self._on_slider)
        grid.addWidget(self._slider, 0, 0, 1, 4)

        self._spinbox = QSpinBox()
        self._spinbox.setMinimum(1)
        self._spinbox.valueChanged.connect(self._on_spinbox)
        grid.addWidget(self._spinbox, 1, 0)

        self._depth_label = QLabel("of 1")
        grid.addWidget(self._depth_label, 1, 1)

        self._coordinate_label = QLabel("")
        grid.addWidget(self._coordinate_label, 1, 2, 1, 2)

        transport = QHBoxLayout()
        for text, tip, handler in (
            ("|<", "First slice", self.first),
            ("<", "Previous slice", self.previous),
            (">", "Next slice", self.next),
            (">|", "Last slice", self.last),
        ):
            button = QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(handler)
            transport.addWidget(button)

        transport.addSpacing(8)
        transport.addWidget(QLabel("Interval"))
        self._interval = QDoubleSpinBox()
        self._interval.setRange(MIN_INTERVAL, MAX_INTERVAL)
        self._interval.setSingleStep(0.1)
        self._interval.setSuffix(" s")
        self._interval.setValue(DEFAULT_INTERVAL)
        self._interval.valueChanged.connect(self._on_interval)
        transport.addWidget(self._interval)

        self._play_button = QPushButton("Play")
        self._play_button.setCheckable(True)
        self._play_button.toggled.connect(self.set_playing)
        transport.addWidget(self._play_button)

        grid.addLayout(transport, 2, 0, 1, 4)
        return group

    def _build_axis_group(self) -> QGroupBox:
        """DS9's Axis Order menu."""
        group = QGroupBox("Axis Order")
        row = QHBoxLayout(group)
        self._axis_combo = QComboBox()
        for order in AXIS_ORDERS:
            self._axis_combo.addItem(str(order), str(order))
        self._axis_combo.currentTextChanged.connect(self._on_axis_order)
        row.addWidget(self._axis_combo)
        row.addStretch(1)
        return group

    # -- state ---------------------------------------------------------------

    def set_depth(self, depth: int, slice_index: int = 0) -> None:
        """Set how many slices there are, and which is shown.

        Args:
            depth: The number of slices; at least one.
            slice_index: The slice to show, counting from zero.
        """
        self._depth = max(1, int(depth))
        self._slice = max(0, min(int(slice_index), self._depth - 1))

        self._updating = True
        try:
            self._slider.setMaximum(self._depth)
            self._spinbox.setMaximum(self._depth)
            # DS9 numbers slices from one in the dialog.
            self._slider.setValue(self._slice + 1)
            self._spinbox.setValue(self._slice + 1)
        finally:
            self._updating = False

        self._depth_label.setText(f"of {self._depth}")
        enabled = self._depth > 1
        self._slider.setEnabled(enabled)
        self._spinbox.setEnabled(enabled)
        self._play_button.setEnabled(enabled)

    def set_slice(self, slice_index: int, notify: bool = True) -> None:
        """Show one slice.

        Args:
            slice_index: The slice, from zero. Clamped to the cube.
            notify: Emit `slice_changed`. False when echoing a change that
                came from the frame rather than from this dialog.
        """
        wanted = max(0, min(int(slice_index), self._depth - 1))
        if wanted == self._slice and not notify:
            return
        self._slice = wanted

        self._updating = True
        try:
            self._slider.setValue(wanted + 1)
            self._spinbox.setValue(wanted + 1)
        finally:
            self._updating = False

        if notify:
            self.slice_changed.emit(wanted)

    def set_axis_order(self, order: AxisOrder | str, notify: bool = True) -> None:
        """Set the axis order shown in the menu.

        Args:
            order: The order to select.
            notify: Emit `axis_order_changed`.
        """
        self._order = AxisOrder.parse(order)
        self._updating = not notify
        try:
            self._axis_combo.setCurrentText(str(self._order))
        finally:
            self._updating = False

    def set_coordinate(self, text: str) -> None:
        """Show the slice's world coordinate beside the slider."""
        self._coordinate_label.setText(text)

    @property
    def slice_index(self) -> int:
        """The slice on screen, from zero."""
        return self._slice

    @property
    def axis_order(self) -> AxisOrder:
        """The selected axis order."""
        return self._order

    @property
    def interval_seconds(self) -> float:
        """The play interval."""
        return float(self._interval.value())

    @property
    def is_playing(self) -> bool:
        """Whether the slices are being walked."""
        return self._timer.isActive()

    # -- transport -----------------------------------------------------------

    def first(self) -> None:
        """Show the first slice."""
        self.set_slice(0)

    def previous(self) -> None:
        """Show the previous slice, stopping at the first."""
        self.set_slice(self._slice - 1)

    def next(self) -> None:
        """Show the next slice, stopping at the last."""
        self.set_slice(self._slice + 1)

    def last(self) -> None:
        """Show the last slice."""
        self.set_slice(self._depth - 1)

    def set_playing(self, playing: bool) -> None:
        """Start or stop walking the slices."""
        if playing and self._depth > 1:
            self._timer.setInterval(int(self.interval_seconds * MS_PER_SECOND))
            self._timer.start()
        else:
            self._timer.stop()
        self._play_button.setChecked(self.is_playing)
        self._play_button.setText("Stop" if self.is_playing else "Play")
        self.play_changed.emit(self.is_playing)

    def _advance(self) -> None:
        """Step to the next slice, wrapping at the end as DS9 does."""
        self.set_slice((self._slice + 1) % self._depth)

    # -- signals from the widgets --------------------------------------------

    def _on_slider(self, value: int) -> None:
        if not self._updating:
            self.set_slice(value - 1)

    def _on_spinbox(self, value: int) -> None:
        if not self._updating:
            self.set_slice(value - 1)

    def _on_interval(self, seconds: float) -> None:
        if self.is_playing:
            self._timer.setInterval(int(seconds * MS_PER_SECOND))

    def _on_axis_order(self, text: str) -> None:
        if self._updating or not text:
            return
        self._order = AxisOrder.parse(text)
        self.axis_order_changed.emit(text)

    def closeEvent(self, event) -> None:
        """Stop walking when the dialog closes, so no timer is left running."""
        self.set_playing(False)
        super().closeEvent(event)
