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
Application preferences dialog.

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
    QSpinBox,
    QCheckBox,
    QLineEdit,
    QColorDialog,
    QTabWidget,
    QWidget,
    QFileDialog,
)
from PyQt6.QtGui import QColor


class PreferencesDialog(QDialog):
    """Dialog for configuring application preferences."""

    preferences_changed = pyqtSignal(dict)

    def __init__(self, parent: Optional[QDialog] = None) -> None:
        """Initialize the preferences dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumSize(550, 500)
        self._bg_color = QColor(0, 0, 0)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Tab widget
        tabs = QTabWidget()

        # General tab
        general_widget = QWidget()
        general_layout = QVBoxLayout(general_widget)

        startup_group = QGroupBox("Startup")
        startup_layout = QFormLayout(startup_group)

        self._restore_session_check = QCheckBox("Restore previous session")
        startup_layout.addRow("", self._restore_session_check)

        self._check_updates_check = QCheckBox("Check for updates on startup")
        startup_layout.addRow("", self._check_updates_check)

        self._recent_files_spin = QSpinBox()
        self._recent_files_spin.setRange(0, 50)
        self._recent_files_spin.setValue(10)
        startup_layout.addRow("Recent files to remember:", self._recent_files_spin)

        general_layout.addWidget(startup_group)

        # Default directories
        dir_group = QGroupBox("Default Directories")
        dir_layout = QFormLayout(dir_group)

        data_layout = QHBoxLayout()
        self._data_dir_edit = QLineEdit()
        data_layout.addWidget(self._data_dir_edit)
        data_browse_btn = QPushButton("Browse...")
        data_browse_btn.clicked.connect(lambda: self._browse_directory(self._data_dir_edit))
        data_layout.addWidget(data_browse_btn)
        dir_layout.addRow("Data directory:", data_layout)

        export_layout = QHBoxLayout()
        self._export_dir_edit = QLineEdit()
        export_layout.addWidget(self._export_dir_edit)
        export_browse_btn = QPushButton("Browse...")
        export_browse_btn.clicked.connect(lambda: self._browse_directory(self._export_dir_edit))
        export_layout.addWidget(export_browse_btn)
        dir_layout.addRow("Export directory:", export_layout)

        general_layout.addWidget(dir_group)
        general_layout.addStretch()

        tabs.addTab(general_widget, "General")

        # Display tab
        display_widget = QWidget()
        display_layout = QVBoxLayout(display_widget)

        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["System", "Light", "Dark"])
        appearance_layout.addRow("Theme:", self._theme_combo)

        bg_color_layout = QHBoxLayout()
        self._bg_color_btn = QPushButton()
        self._bg_color_btn.setFixedSize(60, 25)
        self._update_bg_color_button()
        self._bg_color_btn.clicked.connect(self._choose_bg_color)
        bg_color_layout.addWidget(self._bg_color_btn)
        bg_color_layout.addStretch()
        appearance_layout.addRow("Background color:", bg_color_layout)

        self._anti_alias_check = QCheckBox("Anti-aliasing")
        self._anti_alias_check.setChecked(True)
        appearance_layout.addRow("", self._anti_alias_check)

        display_layout.addWidget(appearance_group)

        # Default display settings
        defaults_group = QGroupBox("Default Display Settings")
        defaults_layout = QFormLayout(defaults_group)

        self._default_scale_combo = QComboBox()
        self._default_scale_combo.addItems(["Linear", "Log", "Sqrt", "Power", "Asinh"])
        defaults_layout.addRow("Default scale:", self._default_scale_combo)

        self._default_cmap_combo = QComboBox()
        self._default_cmap_combo.addItems(["gray", "heat", "cool", "viridis", "plasma"])
        defaults_layout.addRow("Default colormap:", self._default_cmap_combo)

        self._default_clip_combo = QComboBox()
        self._default_clip_combo.addItems(["MinMax", "ZScale", "Percentile"])
        defaults_layout.addRow("Default clip:", self._default_clip_combo)

        display_layout.addWidget(defaults_group)
        display_layout.addStretch()

        tabs.addTab(display_widget, "Display")

        # Performance tab
        perf_widget = QWidget()
        perf_layout = QVBoxLayout(perf_widget)

        memory_group = QGroupBox("Memory")
        memory_layout = QFormLayout(memory_group)

        self._cache_size_spin = QSpinBox()
        self._cache_size_spin.setRange(100, 10000)
        self._cache_size_spin.setValue(1000)
        self._cache_size_spin.setSuffix(" MB")
        memory_layout.addRow("Image cache size:", self._cache_size_spin)

        self._tile_size_spin = QSpinBox()
        self._tile_size_spin.setRange(128, 2048)
        self._tile_size_spin.setValue(512)
        self._tile_size_spin.setSingleStep(128)
        memory_layout.addRow("Tile size:", self._tile_size_spin)

        perf_layout.addWidget(memory_group)

        rendering_group = QGroupBox("Rendering")
        rendering_layout = QFormLayout(rendering_group)

        self._use_gpu_check = QCheckBox("Use GPU acceleration")
        self._use_gpu_check.setChecked(True)
        rendering_layout.addRow("", self._use_gpu_check)

        self._threads_spin = QSpinBox()
        self._threads_spin.setRange(1, 32)
        self._threads_spin.setValue(4)
        rendering_layout.addRow("Worker threads:", self._threads_spin)

        perf_layout.addWidget(rendering_group)
        perf_layout.addStretch()

        tabs.addTab(perf_widget, "Performance")

        # Keyboard tab
        keyboard_widget = QWidget()
        keyboard_layout = QVBoxLayout(keyboard_widget)

        shortcuts_group = QGroupBox("Keyboard Shortcuts")
        shortcuts_layout = QFormLayout(shortcuts_group)

        self._pan_key_combo = QComboBox()
        self._pan_key_combo.addItems(["Arrow Keys", "WASD", "HJKL"])
        shortcuts_layout.addRow("Pan:", self._pan_key_combo)

        self._zoom_key_combo = QComboBox()
        self._zoom_key_combo.addItems(["+/-", "Scroll Wheel", "Ctrl+Scroll"])
        shortcuts_layout.addRow("Zoom:", self._zoom_key_combo)

        keyboard_layout.addWidget(shortcuts_group)
        keyboard_layout.addStretch()

        tabs.addTab(keyboard_widget, "Keyboard")

        layout.addWidget(tabs)

        # Button row
        button_layout = QHBoxLayout()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        button_layout.addWidget(reset_btn)

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

    def _browse_directory(self, line_edit: QLineEdit) -> None:
        """Open directory browser.

        Args:
            line_edit: Line edit to populate with selected path.
        """
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            line_edit.setText(directory)

    def _choose_bg_color(self) -> None:
        """Open color picker for background color."""
        color = QColorDialog.getColor(self._bg_color, self, "Choose Background Color")
        if color.isValid():
            self._bg_color = color
            self._update_bg_color_button()

    def _update_bg_color_button(self) -> None:
        """Update the background color button appearance."""
        self._bg_color_btn.setStyleSheet(
            f"background-color: {self._bg_color.name()}; border: 1px solid gray;"
        )

    def _reset_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._restore_session_check.setChecked(False)
        self._check_updates_check.setChecked(True)
        self._recent_files_spin.setValue(10)
        self._data_dir_edit.clear()
        self._export_dir_edit.clear()
        self._theme_combo.setCurrentText("System")
        self._bg_color = QColor(0, 0, 0)
        self._update_bg_color_button()
        self._anti_alias_check.setChecked(True)
        self._default_scale_combo.setCurrentText("Linear")
        self._default_cmap_combo.setCurrentText("gray")
        self._default_clip_combo.setCurrentText("ZScale")
        self._cache_size_spin.setValue(1000)
        self._tile_size_spin.setValue(512)
        self._use_gpu_check.setChecked(True)
        self._threads_spin.setValue(4)

    def _get_settings(self) -> dict:
        """Get current preference settings.

        Returns:
            Dictionary of preference settings.
        """
        return {
            "restore_session": self._restore_session_check.isChecked(),
            "check_updates": self._check_updates_check.isChecked(),
            "recent_files_count": self._recent_files_spin.value(),
            "data_directory": self._data_dir_edit.text(),
            "export_directory": self._export_dir_edit.text(),
            "theme": self._theme_combo.currentText(),
            "background_color": self._bg_color.name(),
            "anti_aliasing": self._anti_alias_check.isChecked(),
            "default_scale": self._default_scale_combo.currentText(),
            "default_colormap": self._default_cmap_combo.currentText(),
            "default_clip": self._default_clip_combo.currentText(),
            "cache_size_mb": self._cache_size_spin.value(),
            "tile_size": self._tile_size_spin.value(),
            "use_gpu": self._use_gpu_check.isChecked(),
            "worker_threads": self._threads_spin.value(),
            "pan_keys": self._pan_key_combo.currentText(),
            "zoom_keys": self._zoom_key_combo.currentText(),
        }

    def _apply(self) -> None:
        """Apply current settings."""
        self.preferences_changed.emit(self._get_settings())

    def _ok(self) -> None:
        """Apply settings and close dialog."""
        self._apply()
        self.accept()

    def load_preferences(self, prefs: Dict[str, Any]) -> None:
        """Load preferences into the dialog.

        Args:
            prefs: Dictionary of preference values.
        """
        if "restore_session" in prefs:
            self._restore_session_check.setChecked(prefs["restore_session"])
        if "check_updates" in prefs:
            self._check_updates_check.setChecked(prefs["check_updates"])
        if "recent_files_count" in prefs:
            self._recent_files_spin.setValue(prefs["recent_files_count"])
        if "data_directory" in prefs:
            self._data_dir_edit.setText(prefs["data_directory"])
        if "export_directory" in prefs:
            self._export_dir_edit.setText(prefs["export_directory"])
        if "theme" in prefs:
            self._theme_combo.setCurrentText(prefs["theme"])
        if "background_color" in prefs:
            self._bg_color = QColor(prefs["background_color"])
            self._update_bg_color_button()
        if "anti_aliasing" in prefs:
            self._anti_alias_check.setChecked(prefs["anti_aliasing"])
        if "default_scale" in prefs:
            self._default_scale_combo.setCurrentText(prefs["default_scale"])
        if "default_colormap" in prefs:
            self._default_cmap_combo.setCurrentText(prefs["default_colormap"])
        if "default_clip" in prefs:
            self._default_clip_combo.setCurrentText(prefs["default_clip"])
        if "cache_size_mb" in prefs:
            self._cache_size_spin.setValue(prefs["cache_size_mb"])
        if "tile_size" in prefs:
            self._tile_size_spin.setValue(prefs["tile_size"])
        if "use_gpu" in prefs:
            self._use_gpu_check.setChecked(prefs["use_gpu"])
        if "worker_threads" in prefs:
            self._threads_spin.setValue(prefs["worker_threads"])
