"""
Crop parameter dialog.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QVBoxLayout,
)


class CropParametersDialog(QDialog):
    """Dialog for defining a crop/view rectangle."""

    parameters_changed = pyqtSignal(dict)

    def __init__(self, parent: Optional[QDialog] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Crop Parameters")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._center_x_spin = QDoubleSpinBox()
        self._center_x_spin.setRange(-1_000_000.0, 1_000_000.0)
        self._center_x_spin.setDecimals(3)
        form.addRow("Center X:", self._center_x_spin)

        self._center_y_spin = QDoubleSpinBox()
        self._center_y_spin.setRange(-1_000_000.0, 1_000_000.0)
        self._center_y_spin.setDecimals(3)
        form.addRow("Center Y:", self._center_y_spin)

        self._width_spin = QDoubleSpinBox()
        self._width_spin.setRange(1.0, 1_000_000.0)
        self._width_spin.setDecimals(3)
        self._width_spin.setValue(100.0)
        form.addRow("Width:", self._width_spin)

        self._height_spin = QDoubleSpinBox()
        self._height_spin.setRange(1.0, 1_000_000.0)
        self._height_spin.setDecimals(3)
        self._height_spin.setValue(100.0)
        form.addRow("Height:", self._height_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(self._emit_and_accept)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._emit_parameters)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_values(
        self,
        *,
        center_x: float,
        center_y: float,
        width: float,
        height: float,
    ) -> None:
        """Populate the dialog with current crop parameters."""
        self._center_x_spin.setValue(float(center_x))
        self._center_y_spin.setValue(float(center_y))
        self._width_spin.setValue(max(1.0, float(width)))
        self._height_spin.setValue(max(1.0, float(height)))

    def _emit_parameters(self) -> None:
        self.parameters_changed.emit(
            {
                "center_x": self._center_x_spin.value(),
                "center_y": self._center_y_spin.value(),
                "width": self._width_spin.value(),
                "height": self._height_spin.value(),
            }
        )

    def _emit_and_accept(self) -> None:
        self._emit_parameters()
        self.accept()
