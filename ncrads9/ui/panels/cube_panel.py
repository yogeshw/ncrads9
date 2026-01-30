# This file is part of ncrads9.
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
Cube panel for data cube slice navigation.

Author: Yogesh Wadadekar
"""

from typing import Optional, Any

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QGroupBox,
    QComboBox,
    QPushButton,
)


class CubePanel(QDockWidget):
    """Dockable panel for data cube slice navigation."""

    slice_changed = pyqtSignal(int)
    axis_changed = pyqtSignal(int)
    animation_requested = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the cube panel.

        Args:
            parent: Parent widget.
        """
        super().__init__("Data Cube", parent)
        self.setObjectName("CubePanel")

        self._cube: Optional[NDArray[np.float64]] = None
        self._current_slice: int = 0
        self._slice_axis: int = 0
        self._n_slices: int = 1
        self._wcs: Optional[Any] = None
        self._is_animating: bool = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        container = QWidget()
        layout = QVBoxLayout(container)

        # Cube info group
        info_group = QGroupBox("Cube Information")
        info_layout = QVBoxLayout(info_group)

        self._dimensions_label = QLabel("Dimensions: ---")
        info_layout.addWidget(self._dimensions_label)

        self._current_slice_label = QLabel("Current Slice: ---")
        info_layout.addWidget(self._current_slice_label)

        layout.addWidget(info_group)

        # Axis selection
        axis_group = QGroupBox("Slice Axis")
        axis_layout = QHBoxLayout(axis_group)

        axis_layout.addWidget(QLabel("Axis:"))
        self._axis_combo = QComboBox()
        self._axis_combo.addItems(["0 (Z)", "1 (Y)", "2 (X)"])
        self._axis_combo.currentIndexChanged.connect(self._on_axis_changed)
        axis_layout.addWidget(self._axis_combo)

        layout.addWidget(axis_group)

        # Slice navigation group
        nav_group = QGroupBox("Slice Navigation")
        nav_layout = QVBoxLayout(nav_group)

        # Slider
        slider_layout = QHBoxLayout()
        self._slice_slider = QSlider(Qt.Orientation.Horizontal)
        self._slice_slider.setMinimum(0)
        self._slice_slider.setMaximum(0)
        self._slice_slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self._slice_slider)
        nav_layout.addLayout(slider_layout)

        # Spinbox and buttons
        controls_layout = QHBoxLayout()

        self._first_button = QPushButton("⏮")
        self._first_button.setMaximumWidth(40)
        self._first_button.clicked.connect(self._go_first)
        controls_layout.addWidget(self._first_button)

        self._prev_button = QPushButton("◀")
        self._prev_button.setMaximumWidth(40)
        self._prev_button.clicked.connect(self._go_prev)
        controls_layout.addWidget(self._prev_button)

        self._slice_spinbox = QSpinBox()
        self._slice_spinbox.setMinimum(0)
        self._slice_spinbox.setMaximum(0)
        self._slice_spinbox.valueChanged.connect(self._on_spinbox_changed)
        controls_layout.addWidget(self._slice_spinbox)

        self._next_button = QPushButton("▶")
        self._next_button.setMaximumWidth(40)
        self._next_button.clicked.connect(self._go_next)
        controls_layout.addWidget(self._next_button)

        self._last_button = QPushButton("⏭")
        self._last_button.setMaximumWidth(40)
        self._last_button.clicked.connect(self._go_last)
        controls_layout.addWidget(self._last_button)

        nav_layout.addLayout(controls_layout)

        # Animation controls
        anim_layout = QHBoxLayout()
        self._play_button = QPushButton("▶ Play")
        self._play_button.setCheckable(True)
        self._play_button.clicked.connect(self._toggle_animation)
        anim_layout.addWidget(self._play_button)

        anim_layout.addWidget(QLabel("Speed:"))
        self._speed_spinbox = QSpinBox()
        self._speed_spinbox.setRange(1, 30)
        self._speed_spinbox.setValue(10)
        self._speed_spinbox.setSuffix(" fps")
        anim_layout.addWidget(self._speed_spinbox)

        nav_layout.addLayout(anim_layout)

        layout.addWidget(nav_group)

        # Spectral info group (for spectral cubes)
        spectral_group = QGroupBox("Spectral Information")
        spectral_layout = QVBoxLayout(spectral_group)

        self._frequency_label = QLabel("Frequency: ---")
        spectral_layout.addWidget(self._frequency_label)

        self._wavelength_label = QLabel("Wavelength: ---")
        spectral_layout.addWidget(self._wavelength_label)

        self._velocity_label = QLabel("Velocity: ---")
        spectral_layout.addWidget(self._velocity_label)

        layout.addWidget(spectral_group)

        layout.addStretch()
        self.setWidget(container)

        self._set_enabled(False)

    def _set_enabled(self, enabled: bool) -> None:
        """Enable or disable controls."""
        self._slice_slider.setEnabled(enabled)
        self._slice_spinbox.setEnabled(enabled)
        self._first_button.setEnabled(enabled)
        self._prev_button.setEnabled(enabled)
        self._next_button.setEnabled(enabled)
        self._last_button.setEnabled(enabled)
        self._play_button.setEnabled(enabled)
        self._axis_combo.setEnabled(enabled)

    def set_cube(self, cube: NDArray[np.float64]) -> None:
        """
        Set the data cube.

        Args:
            cube: 3D numpy array.
        """
        if cube.ndim < 3:
            self._cube = None
            self._set_enabled(False)
            self._dimensions_label.setText("Dimensions: Not a cube")
            return

        self._cube = cube
        self._update_for_axis()
        self._set_enabled(True)

        dims_str = " × ".join(str(d) for d in cube.shape)
        self._dimensions_label.setText(f"Dimensions: {dims_str}")

    def set_wcs(self, wcs: Any) -> None:
        """
        Set the WCS for spectral information.

        Args:
            wcs: Astropy WCS object.
        """
        self._wcs = wcs
        self._update_spectral_info()

    def _update_for_axis(self) -> None:
        """Update controls for current slice axis."""
        if self._cube is None:
            return

        self._n_slices = self._cube.shape[self._slice_axis]
        self._current_slice = min(self._current_slice, self._n_slices - 1)

        self._slice_slider.setMaximum(self._n_slices - 1)
        self._slice_spinbox.setMaximum(self._n_slices - 1)

        self._update_slice_display()

    def _update_slice_display(self) -> None:
        """Update the slice display labels."""
        self._current_slice_label.setText(
            f"Current Slice: {self._current_slice + 1} / {self._n_slices}"
        )
        self._update_spectral_info()

    def _update_spectral_info(self) -> None:
        """Update spectral information display."""
        if self._wcs is None or self._cube is None:
            self._frequency_label.setText("Frequency: ---")
            self._wavelength_label.setText("Wavelength: ---")
            self._velocity_label.setText("Velocity: ---")
            return

        try:
            # Try to get spectral coordinate
            if hasattr(self._wcs, "spectral"):
                spec_wcs = self._wcs.spectral
                spec_coord = spec_wcs.pixel_to_world(self._current_slice)
                self._frequency_label.setText(f"Frequency: {spec_coord}")
            else:
                self._frequency_label.setText("Frequency: N/A")
        except Exception:
            self._frequency_label.setText("Frequency: Error")

        self._wavelength_label.setText("Wavelength: ---")
        self._velocity_label.setText("Velocity: ---")

    def _on_axis_changed(self, index: int) -> None:
        """Handle axis selection change."""
        self._slice_axis = index
        self._update_for_axis()
        self.axis_changed.emit(index)

    def _on_slider_changed(self, value: int) -> None:
        """Handle slider value change."""
        if value != self._current_slice:
            self._current_slice = value
            self._slice_spinbox.blockSignals(True)
            self._slice_spinbox.setValue(value)
            self._slice_spinbox.blockSignals(False)
            self._update_slice_display()
            self.slice_changed.emit(value)

    def _on_spinbox_changed(self, value: int) -> None:
        """Handle spinbox value change."""
        if value != self._current_slice:
            self._current_slice = value
            self._slice_slider.blockSignals(True)
            self._slice_slider.setValue(value)
            self._slice_slider.blockSignals(False)
            self._update_slice_display()
            self.slice_changed.emit(value)

    def _go_first(self) -> None:
        """Go to first slice."""
        self._slice_slider.setValue(0)

    def _go_prev(self) -> None:
        """Go to previous slice."""
        if self._current_slice > 0:
            self._slice_slider.setValue(self._current_slice - 1)

    def _go_next(self) -> None:
        """Go to next slice."""
        if self._current_slice < self._n_slices - 1:
            self._slice_slider.setValue(self._current_slice + 1)

    def _go_last(self) -> None:
        """Go to last slice."""
        self._slice_slider.setValue(self._n_slices - 1)

    def _toggle_animation(self) -> None:
        """Toggle animation playback."""
        self._is_animating = self._play_button.isChecked()
        if self._is_animating:
            self._play_button.setText("⏸ Pause")
        else:
            self._play_button.setText("▶ Play")
        self.animation_requested.emit(self._is_animating)

    def get_current_slice(self) -> int:
        """
        Get the current slice index.

        Returns:
            Current slice index.
        """
        return self._current_slice

    def get_slice_axis(self) -> int:
        """
        Get the current slice axis.

        Returns:
            Current slice axis index.
        """
        return self._slice_axis

    def get_animation_fps(self) -> int:
        """
        Get the animation frames per second.

        Returns:
            Animation FPS.
        """
        return self._speed_spinbox.value()

    def get_current_slice_data(self) -> Optional[NDArray[np.float64]]:
        """
        Get the current slice data.

        Returns:
            2D array of current slice, or None if no cube loaded.
        """
        if self._cube is None:
            return None

        if self._slice_axis == 0:
            return self._cube[self._current_slice, :, :]
        elif self._slice_axis == 1:
            return self._cube[:, self._current_slice, :]
        else:
            return self._cube[:, :, self._current_slice]
