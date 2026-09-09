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
The Colour Tag dialog: one stretch of the colorbar, painted flat.

DS9's `ColorTagDialog` (`ds9/library/colorbar.tcl`): a start, a stop, a
colour, and OK or Cancel. This adds a Delete button, since a tag created by
a stray click on the colorbar is otherwise awkward to be rid of -- DS9 makes
you use the Colormap Parameters dialog's Delete Color Tag, which deletes all
of them.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...colormaps.color_tags import TAG_COLORS, ColorTag

#: How many decimals the position spinboxes offer.
POSITION_DECIMALS = 4


class ColorTagDialog(QDialog):
    """Edit one colour tag.

    Args:
        tag: The tag to edit.
        parent: Optional parent widget.
    """

    #: `exec()` returns this when the user pressed Delete.
    DELETED = 2

    def __init__(self, tag: ColorTag, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Color Tag")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._start = self._position_box(tag.start)
        form.addRow("Start:", self._start)
        self._stop = self._position_box(tag.stop)
        form.addRow("Stop:", self._stop)

        self._color = QComboBox()
        self._color.setEditable(True)
        self._color.addItems(sorted(TAG_COLORS))
        self._color.setCurrentText(tag.color)
        self._color.setToolTip("A colour name, or #rrggbb")
        form.addRow("Color:", self._color)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        delete = QPushButton("Delete")
        delete.clicked.connect(lambda: self.done(self.DELETED))
        buttons.addButton(delete, QDialogButtonBox.ButtonRole.DestructiveRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _position_box(value: float) -> QDoubleSpinBox:
        """A 0-to-1 position along the colorbar."""
        box = QDoubleSpinBox()
        box.setRange(0.0, 1.0)
        box.setSingleStep(0.01)
        box.setDecimals(POSITION_DECIMALS)
        box.setValue(float(value))
        return box

    def tag(self) -> ColorTag:
        """The tag the user settled on."""
        return ColorTag(
            self._start.value(),
            self._stop.value(),
            self._color.currentText().strip() or "red",
        )
