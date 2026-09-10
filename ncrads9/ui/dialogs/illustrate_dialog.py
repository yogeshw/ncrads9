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
DS9's Illustrate -> Get Information: one illustration's parameters.

DS9 opens a different dialog per shape (`IllustrateCircleDialog` and its
seven siblings). This is one dialog that shows the rows the selected shape
actually has, which saves seven near-identical windows and means a shape
gains its row here the moment it gains the parameter.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...illustrate.elements import (
    Box,
    Circle,
    Element,
    Ellipse,
    Image,
    Line,
    Polygon,
    Text,
)
from ..menu_bar import REGION_COLORS, REGION_WIDTHS

#: How far a coordinate box reaches, in canvas pixels.
LIMIT = 100_000.0

#: The fonts, weights, slants and justifications DS9's text dialog offers.
FONTS = ("helvetica", "times", "courier")
WEIGHTS = ("normal", "bold")
SLANTS = ("roman", "italic")
JUSTIFICATIONS = ("left", "center", "right")


class IllustrateDialog(QDialog):
    """Shows and edits the selected illustration."""

    def __init__(self, controller, parent=None) -> None:
        """
        Args:
            controller: The `IllustrateController` this dialog drives.
            parent: The main window.
        """
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Illustrate")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumWidth(340)
        self._build()
        self.reload()

    def _build(self) -> None:
        """Lay the dialog out: every row, with the unused ones hidden."""
        layout = QVBoxLayout(self)

        self._what = QLabel()
        layout.addWidget(self._what)

        form = QFormLayout()
        self._rows: dict[str, QWidget] = {}

        self._x = self._number()
        self._y = self._number()
        self._add_row(form, "position", "Center:", [self._x, self._y])

        self._radius = self._number(minimum=1.0)
        self._add_row(form, "radius", "Radius:", [self._radius])

        self._radius1 = self._number(minimum=1.0)
        self._radius2 = self._number(minimum=1.0)
        self._add_row(form, "radii", "Radius 1, 2:", [self._radius1, self._radius2])

        self._points = QLabel()
        self._add_row(form, "points", "Points:", [self._points])

        self._arrow_first = QCheckBox("at the start")
        self._arrow_last = QCheckBox("at the end")
        self._add_row(form, "arrows", "Arrowheads:", [self._arrow_first, self._arrow_last])

        self._text = QPlainTextEdit()
        self._text.setFixedHeight(60)
        self._add_row(form, "text", "Text:", [self._text])

        self._font = QComboBox()
        self._font.addItems(FONTS)
        self._font_size = QSpinBox()
        self._font_size.setRange(4, 200)
        self._add_row(form, "font", "Font:", [self._font, self._font_size])

        self._weight = QComboBox()
        self._weight.addItems(WEIGHTS)
        self._slant = QComboBox()
        self._slant.addItems(SLANTS)
        self._add_row(form, "style", "Weight, slant:", [self._weight, self._slant])

        self._angle = self._number(minimum=-360.0)
        self._justify = QComboBox()
        self._justify.addItems(JUSTIFICATIONS)
        self._add_row(form, "angle", "Angle, justify:", [self._angle, self._justify])

        self._path = QLabel()
        self._path.setWordWrap(True)
        self._size_w = self._number(minimum=1.0)
        self._size_h = self._number(minimum=1.0)
        self._add_row(form, "file", "File:", [self._path])
        self._add_row(form, "size", "Size:", [self._size_w, self._size_h])

        self._color = QComboBox()
        self._color.addItems(REGION_COLORS)
        self._width = QComboBox()
        self._width.addItems([str(value) for value in REGION_WIDTHS])
        self._add_row(form, "style_common", "Color, width:", [self._color, self._width])

        self._fill = QCheckBox("Fill")
        self._dash = QCheckBox("Dash")
        self._add_row(form, "flags", "", [self._fill, self._dash])

        layout.addLayout(form)

        buttons = QHBoxLayout()
        #: Button name -> the button, so a test can press one.
        self.buttons: dict[str, QPushButton] = {}
        for name, label, slot in (
            ("apply", "Apply", self.apply_changes),
            ("delete", "Delete", self.delete_element),
            ("close", "Close", self.close),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
            self.buttons[name] = button
        layout.addLayout(buttons)

    def _number(self, minimum: float = -LIMIT) -> QDoubleSpinBox:
        """One coordinate box."""
        box = QDoubleSpinBox()
        box.setRange(minimum, LIMIT)
        box.setDecimals(2)
        return box

    def _add_row(self, form: QFormLayout, name: str, label: str, widgets: list[QWidget]) -> None:
        """Add one row and remember it, so it can be shown or hidden."""
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        for widget in widgets:
            row.addWidget(widget)
        form.addRow(label, holder)
        self._rows[name] = holder
        # The label goes with its row, or an empty label is left behind.
        widget_label = form.labelForField(holder)
        if widget_label is not None:
            self._rows[name + "_label"] = widget_label

    def _show_rows(self, names: set[str]) -> None:
        """Show exactly the rows one shape needs."""
        for name, widget in self._rows.items():
            widget.setVisible(name.removesuffix("_label") in names)

    # -- what it shows -----------------------------------------------------------

    def reload(self) -> None:
        """Fill the dialog in from the selected illustration."""
        element = self._controller.selected()
        if element is None:
            self._what.setText("No illustration selected.")
            self._show_rows(set())
            return

        self._what.setText(f"{element.kind.title()} of {len(self._controller.layer)} illustration(s)")
        rows = {"style_common", "flags"}

        self._color.setCurrentText(element.style.color)
        self._width.setCurrentText(str(element.style.width))
        self._fill.setChecked(element.style.fill)
        self._dash.setChecked(element.style.dash)

        if isinstance(element, Circle):
            rows |= {"position", "radius"}
            self._x.setValue(element.x)
            self._y.setValue(element.y)
            self._radius.setValue(element.radius)
        elif isinstance(element, (Ellipse, Box)):
            rows |= {"position", "radii"}
            self._x.setValue(element.x)
            self._y.setValue(element.y)
            self._radius1.setValue(element.radius1)
            self._radius2.setValue(element.radius2)
        elif isinstance(element, Polygon):
            rows |= {"points"}
            self._points.setText(self._describe(element.points))
        elif isinstance(element, Line):
            rows |= {"points", "arrows"}
            self._points.setText(self._describe(element.points))
            self._arrow_first.setChecked(element.arrow_first)
            self._arrow_last.setChecked(element.arrow_last)
        elif isinstance(element, Text):
            rows |= {"position", "text", "font", "style", "angle"}
            self._x.setValue(element.x)
            self._y.setValue(element.y)
            self._text.setPlainText(element.text)
            self._font.setCurrentText(element.font)
            self._font_size.setValue(element.font_size)
            self._weight.setCurrentText(element.font_weight)
            self._slant.setCurrentText(element.font_slant)
            self._angle.setValue(element.angle)
            self._justify.setCurrentText(element.justify)
        elif isinstance(element, Image):
            rows |= {"position", "file", "size"}
            self._x.setValue(element.x)
            self._y.setValue(element.y)
            self._path.setText(element.path or "(none)")
            self._size_w.setValue(max(1.0, element.width))
            self._size_h.setValue(max(1.0, element.height))

        self._show_rows(rows)

    @staticmethod
    def _describe(points: list[tuple[float, float]]) -> str:
        """A point list, short enough to read."""
        shown = ", ".join(f"({x:g}, {y:g})" for x, y in points[:6])
        return shown + (" ..." if len(points) > 6 else "")

    # -- what its buttons do ------------------------------------------------------

    def apply_changes(self) -> None:
        """Put the typed values back on the illustration."""
        element = self._controller.selected()
        if element is None:
            return

        element.style.color = self._color.currentText()
        element.style.width = int(self._width.currentText())
        element.style.fill = self._fill.isChecked()
        element.style.dash = self._dash.isChecked()

        if isinstance(element, Circle):
            element.x, element.y = self._x.value(), self._y.value()
            element.radius = self._radius.value()
        elif isinstance(element, (Ellipse, Box)):
            element.x, element.y = self._x.value(), self._y.value()
            element.radius1 = self._radius1.value()
            element.radius2 = self._radius2.value()
        elif isinstance(element, Line):
            element.arrow_first = self._arrow_first.isChecked()
            element.arrow_last = self._arrow_last.isChecked()
        elif isinstance(element, Text):
            element.x, element.y = self._x.value(), self._y.value()
            element.text = self._text.toPlainText()
            element.font = self._font.currentText()
            element.font_size = self._font_size.value()
            element.font_weight = self._weight.currentText()
            element.font_slant = self._slant.currentText()
            element.angle = self._angle.value()
            element.justify = self._justify.currentText()
        elif isinstance(element, Image):
            element.x, element.y = self._x.value(), self._y.value()
            element.width = self._size_w.value()
            element.height = self._size_h.value()

        self._controller.refresh()

    def delete_element(self) -> None:
        """Remove the illustration this dialog is showing."""
        element: Element | None = self._controller.selected()
        if element is None:
            return
        self._controller.layer.delete(element)
        self._controller.refresh()
        self.reload()
