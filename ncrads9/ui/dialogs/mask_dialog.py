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
DS9's Mask Parameters dialog.

Which pixels of the mask file count, what colour to paint them, how
transparent, and how to blend -- plus Open, to load the file, and Clear.
What it replaced was a three-item `QInputDialog` that thresholded the
displayed data, which is not what DS9's Mask does at all.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ...analysis.mask import MASK_COLORS, BlendMode, MaskMode, MaskSettings

#: The FITS filter Open offers.
MASK_FILTER = "FITS Files (*.fits *.fit *.fts *.fits.gz);;All Files (*)"


class MaskDialog(QDialog):
    """The settings for one mask layer.

    Args:
        settings: The current settings, edited in place on Apply.
        path: The mask file already loaded, if any.
        parent: Optional parent widget.
    """

    #: Emitted with (settings, path) when Apply or OK is pressed. The path
    #: is empty when the loaded mask is to be kept.
    mask_changed = pyqtSignal(object, str)
    #: Emitted when Clear is pressed.
    mask_cleared = pyqtSignal()

    def __init__(
        self,
        settings: MaskSettings | None = None,
        path: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mask Parameters")
        self.settings = settings or MaskSettings()
        self._path = path

        layout = QVBoxLayout(self)

        file_group = QGroupBox("Mask file")
        file_layout = QHBoxLayout(file_group)
        self._file_label = QLabel(Path(path).name if path else "(none loaded)")
        file_layout.addWidget(self._file_label)
        file_layout.addStretch()
        open_button = QPushButton("Open...")
        open_button.clicked.connect(self._open)
        file_layout.addWidget(open_button)
        layout.addWidget(file_group)

        which = QGroupBox("Which pixels")
        form = QFormLayout(which)
        self._mode = QComboBox()
        self._mode.addItems([mode.value for mode in MaskMode])
        self._mode.setCurrentText(self.settings.mode.value)
        self._mode.currentTextChanged.connect(self._on_mode_changed)
        form.addRow("Mode:", self._mode)

        self._low = QDoubleSpinBox()
        self._low.setRange(-1e12, 1e12)
        self._low.setDecimals(6)
        self._low.setValue(self.settings.low)
        form.addRow("Range low:", self._low)

        self._high = QDoubleSpinBox()
        self._high.setRange(-1e12, 1e12)
        self._high.setDecimals(6)
        self._high.setValue(self.settings.high)
        form.addRow("Range high:", self._high)
        layout.addWidget(which)

        appearance = QGroupBox("Appearance")
        form = QFormLayout(appearance)
        self._color = QComboBox()
        self._color.addItems(MASK_COLORS)
        self._color.setCurrentText(self.settings.color)
        form.addRow("Colour:", self._color)

        self._blend = QComboBox()
        self._blend.addItems([mode.value for mode in BlendMode])
        self._blend.setCurrentText(self.settings.blend.value)
        form.addRow("Blend:", self._blend)

        self._transparency = QSlider(Qt.Orientation.Horizontal)
        self._transparency.setRange(0, 100)
        self._transparency.setValue(int(self.settings.transparency))
        form.addRow("Transparency:", self._transparency)
        layout.addWidget(appearance)

        self._on_mode_changed(self._mode.currentText())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Close
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear)
        buttons.addButton(clear, QDialogButtonBox.ButtonRole.DestructiveRole)
        layout.addWidget(buttons)

    def _on_mode_changed(self, name: str) -> None:
        """Only the Range mode has a range to set."""
        is_range = name == MaskMode.RANGE.value
        self._low.setEnabled(is_range)
        self._high.setEnabled(is_range)

    def _open(self) -> None:
        """Choose the mask file."""
        from PyQt6.QtWidgets import QFileDialog

        path, _filter = QFileDialog.getOpenFileName(self, "Open Mask", "", MASK_FILTER)
        if not path:
            return
        self._path = path
        self._file_label.setText(Path(path).name)

    def gather(self) -> MaskSettings:
        """Read the fields back into the settings."""
        self.settings.mode = MaskMode(self._mode.currentText())
        self.settings.low = self._low.value()
        self.settings.high = self._high.value()
        self.settings.color = self._color.currentText()
        self.settings.blend = BlendMode(self._blend.currentText())
        self.settings.transparency = float(self._transparency.value())
        return self.settings

    def apply(self) -> None:
        """Announce the settings without closing."""
        self.mask_changed.emit(self.gather(), self._path)

    def _accept(self) -> None:
        """Announce them and close."""
        self.apply()
        self.accept()

    def _clear(self) -> None:
        """Ask for the mask to be removed, and close."""
        self.mask_cleared.emit()
        self.accept()
