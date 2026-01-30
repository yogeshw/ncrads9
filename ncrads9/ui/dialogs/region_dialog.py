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
Region properties dialog.

Author: Yogesh Wadadekar
"""

from typing import Optional, Dict, Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QDoubleSpinBox,
    QCheckBox,
    QLineEdit,
    QColorDialog,
    QSpinBox,
    QTabWidget,
    QWidget,
)
from PyQt6.QtGui import QColor


class RegionDialog(QDialog):
    """Dialog for editing region properties."""

    region_changed = pyqtSignal(dict)

    def __init__(
        self, region_data: Optional[Dict[str, Any]] = None, parent: Optional[QDialog] = None
    ) -> None:
        """Initialize the region dialog.

        Args:
            region_data: Initial region properties.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Region Properties")
        self.setMinimumWidth(450)
        self._region_data = region_data or {}
        self._color = QColor(0, 255, 0)
        self._setup_ui()
        self._load_region_data()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Tab widget
        tabs = QTabWidget()

        # Properties tab
        props_widget = QWidget()
        props_layout = QVBoxLayout(props_widget)

        # Shape properties
        shape_group = QGroupBox("Shape")
        shape_layout = QFormLayout(shape_group)

        self._shape_combo = QComboBox()
        self._shape_combo.addItems([
            "Circle",
            "Ellipse",
            "Box",
            "Polygon",
            "Line",
            "Vector",
            "Text",
            "Point",
            "Annulus",
        ])
        self._shape_combo.currentTextChanged.connect(self._on_shape_changed)
        shape_layout.addRow("Type:", self._shape_combo)

        self._x_spin = QDoubleSpinBox()
        self._x_spin.setRange(-1e10, 1e10)
        self._x_spin.setDecimals(6)
        shape_layout.addRow("X center:", self._x_spin)

        self._y_spin = QDoubleSpinBox()
        self._y_spin.setRange(-1e10, 1e10)
        self._y_spin.setDecimals(6)
        shape_layout.addRow("Y center:", self._y_spin)

        self._radius_spin = QDoubleSpinBox()
        self._radius_spin.setRange(0.001, 1e10)
        self._radius_spin.setDecimals(4)
        shape_layout.addRow("Radius:", self._radius_spin)

        self._width_spin = QDoubleSpinBox()
        self._width_spin.setRange(0.001, 1e10)
        self._width_spin.setDecimals(4)
        shape_layout.addRow("Width:", self._width_spin)

        self._height_spin = QDoubleSpinBox()
        self._height_spin.setRange(0.001, 1e10)
        self._height_spin.setDecimals(4)
        shape_layout.addRow("Height:", self._height_spin)

        self._angle_spin = QDoubleSpinBox()
        self._angle_spin.setRange(0, 360)
        self._angle_spin.setDecimals(2)
        self._angle_spin.setSuffix(" deg")
        shape_layout.addRow("Angle:", self._angle_spin)

        props_layout.addWidget(shape_group)

        # Coordinate system
        coord_group = QGroupBox("Coordinates")
        coord_layout = QFormLayout(coord_group)

        self._coord_combo = QComboBox()
        self._coord_combo.addItems(["Image", "Physical", "WCS", "FK5", "Galactic", "Ecliptic"])
        coord_layout.addRow("System:", self._coord_combo)

        props_layout.addWidget(coord_group)

        tabs.addTab(props_widget, "Properties")

        # Appearance tab
        appear_widget = QWidget()
        appear_layout = QVBoxLayout(appear_widget)

        style_group = QGroupBox("Style")
        style_layout = QFormLayout(style_group)

        color_layout = QHBoxLayout()
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(60, 25)
        self._update_color_button()
        self._color_btn.clicked.connect(self._choose_color)
        color_layout.addWidget(self._color_btn)
        color_layout.addStretch()
        style_layout.addRow("Color:", color_layout)

        self._line_width_spin = QSpinBox()
        self._line_width_spin.setRange(1, 10)
        self._line_width_spin.setValue(1)
        style_layout.addRow("Line width:", self._line_width_spin)

        self._line_style_combo = QComboBox()
        self._line_style_combo.addItems(["Solid", "Dashed", "Dotted"])
        style_layout.addRow("Line style:", self._line_style_combo)

        self._fill_check = QCheckBox("Fill region")
        style_layout.addRow("", self._fill_check)

        self._fill_opacity_spin = QSpinBox()
        self._fill_opacity_spin.setRange(0, 100)
        self._fill_opacity_spin.setValue(30)
        self._fill_opacity_spin.setSuffix(" %")
        style_layout.addRow("Fill opacity:", self._fill_opacity_spin)

        appear_layout.addWidget(style_group)

        # Label settings
        label_group = QGroupBox("Label")
        label_layout = QFormLayout(label_group)

        self._label_edit = QLineEdit()
        label_layout.addRow("Text:", self._label_edit)

        self._show_label_check = QCheckBox("Show label")
        self._show_label_check.setChecked(True)
        label_layout.addRow("", self._show_label_check)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(6, 72)
        self._font_size_spin.setValue(12)
        label_layout.addRow("Font size:", self._font_size_spin)

        appear_layout.addWidget(label_group)

        tabs.addTab(appear_widget, "Appearance")

        layout.addWidget(tabs)

        # Button row
        button_layout = QHBoxLayout()

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_region)
        button_layout.addWidget(delete_btn)

        button_layout.addStretch()

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply)
        button_layout.addWidget(apply_btn)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._ok)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _on_shape_changed(self, shape: str) -> None:
        """Handle shape type change.

        Args:
            shape: Selected shape type.
        """
        is_circle = shape == "Circle"
        is_ellipse_or_box = shape in ("Ellipse", "Box")
        is_point = shape == "Point"

        self._radius_spin.setEnabled(is_circle or shape == "Annulus")
        self._width_spin.setEnabled(is_ellipse_or_box)
        self._height_spin.setEnabled(is_ellipse_or_box)
        self._angle_spin.setEnabled(is_ellipse_or_box)

    def _choose_color(self) -> None:
        """Open color picker dialog."""
        color = QColorDialog.getColor(self._color, self, "Choose Region Color")
        if color.isValid():
            self._color = color
            self._update_color_button()

    def _update_color_button(self) -> None:
        """Update the color button appearance."""
        self._color_btn.setStyleSheet(
            f"background-color: {self._color.name()}; border: 1px solid black;"
        )

    def _load_region_data(self) -> None:
        """Load region data into the form."""
        if not self._region_data:
            return

        if "shape" in self._region_data:
            idx = self._shape_combo.findText(self._region_data["shape"])
            if idx >= 0:
                self._shape_combo.setCurrentIndex(idx)

        if "x" in self._region_data:
            self._x_spin.setValue(self._region_data["x"])
        if "y" in self._region_data:
            self._y_spin.setValue(self._region_data["y"])
        if "radius" in self._region_data:
            self._radius_spin.setValue(self._region_data["radius"])
        if "color" in self._region_data:
            self._color = QColor(self._region_data["color"])
            self._update_color_button()
        if "label" in self._region_data:
            self._label_edit.setText(self._region_data["label"])

    def _get_settings(self) -> dict:
        """Get current region settings.

        Returns:
            Dictionary of region settings.
        """
        return {
            "shape": self._shape_combo.currentText(),
            "x": self._x_spin.value(),
            "y": self._y_spin.value(),
            "radius": self._radius_spin.value(),
            "width": self._width_spin.value(),
            "height": self._height_spin.value(),
            "angle": self._angle_spin.value(),
            "coord_system": self._coord_combo.currentText(),
            "color": self._color.name(),
            "line_width": self._line_width_spin.value(),
            "line_style": self._line_style_combo.currentText(),
            "fill": self._fill_check.isChecked(),
            "fill_opacity": self._fill_opacity_spin.value() / 100.0,
            "label": self._label_edit.text(),
            "show_label": self._show_label_check.isChecked(),
            "font_size": self._font_size_spin.value(),
        }

    def _delete_region(self) -> None:
        """Delete the region."""
        self.region_changed.emit({"action": "delete"})
        self.reject()

    def _apply(self) -> None:
        """Apply current settings."""
        settings = self._get_settings()
        settings["action"] = "update"
        self.region_changed.emit(settings)

    def _ok(self) -> None:
        """Apply settings and close dialog."""
        self._apply()
        self.accept()
