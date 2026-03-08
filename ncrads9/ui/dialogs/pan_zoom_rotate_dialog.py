"""
Pan/zoom/rotate parameter dialog.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QVBoxLayout,
)


class PanZoomRotateDialog(QDialog):
    """Dialog for editing pan, zoom, rotation, and align parameters."""

    parameters_changed = pyqtSignal(dict)

    def __init__(self, parent: Optional[QDialog] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pan Zoom Rotate Parameters")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._zoom_spin = QDoubleSpinBox()
        self._zoom_spin.setRange(0.01, 512.0)
        self._zoom_spin.setDecimals(5)
        self._zoom_spin.setValue(1.0)
        form.addRow("Zoom:", self._zoom_spin)

        self._rotate_spin = QDoubleSpinBox()
        self._rotate_spin.setRange(-360.0, 360.0)
        self._rotate_spin.setDecimals(2)
        self._rotate_spin.setSingleStep(90.0)
        form.addRow("Rotate (degrees):", self._rotate_spin)

        self._pan_x_spin = QDoubleSpinBox()
        self._pan_x_spin.setRange(-1_000_000.0, 1_000_000.0)
        self._pan_x_spin.setDecimals(3)
        form.addRow("Pan X:", self._pan_x_spin)

        self._pan_y_spin = QDoubleSpinBox()
        self._pan_y_spin.setRange(-1_000_000.0, 1_000_000.0)
        self._pan_y_spin.setDecimals(3)
        form.addRow("Pan Y:", self._pan_y_spin)

        self._align_check = QCheckBox("Align")
        form.addRow("", self._align_check)

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
        zoom: float,
        pan_x: float,
        pan_y: float,
        rotation: float,
        align: bool,
    ) -> None:
        """Populate the dialog with current view values."""
        self._zoom_spin.setValue(float(zoom))
        self._pan_x_spin.setValue(float(pan_x))
        self._pan_y_spin.setValue(float(pan_y))
        self._rotate_spin.setValue(float(rotation))
        self._align_check.setChecked(bool(align))

    def _emit_parameters(self) -> None:
        self.parameters_changed.emit(
            {
                "zoom": self._zoom_spin.value(),
                "pan_x": self._pan_x_spin.value(),
                "pan_y": self._pan_y_spin.value(),
                "rotation": self._rotate_spin.value(),
                "align": self._align_check.isChecked(),
            }
        )

    def _emit_and_accept(self) -> None:
        self._emit_parameters()
        self.accept()
