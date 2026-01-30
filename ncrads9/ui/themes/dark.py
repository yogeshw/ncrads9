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
Dark Theme - Dark mode stylesheet.

Author: Yogesh Wadadekar
"""

from typing import Optional

from PyQt6.QtWidgets import QApplication


class DarkTheme:
    """Dark theme for the application."""

    NAME = "Dark"

    STYLESHEET = """
    QMainWindow {
        background-color: #1e1e1e;
    }

    QWidget {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 13px;
        color: #d4d4d4;
    }

    QMenuBar {
        background-color: #252526;
        border-bottom: 1px solid #3c3c3c;
        padding: 2px;
    }

    QMenuBar::item {
        padding: 4px 8px;
        background-color: transparent;
        color: #d4d4d4;
    }

    QMenuBar::item:selected {
        background-color: #3c3c3c;
        border-radius: 4px;
    }

    QMenu {
        background-color: #252526;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        padding: 4px;
    }

    QMenu::item {
        padding: 6px 24px;
        border-radius: 2px;
        color: #d4d4d4;
    }

    QMenu::item:selected {
        background-color: #094771;
        color: white;
    }

    QToolBar {
        background-color: #252526;
        border-bottom: 1px solid #3c3c3c;
        spacing: 4px;
        padding: 4px;
    }

    QToolButton {
        background-color: transparent;
        border: none;
        border-radius: 4px;
        padding: 4px;
        color: #d4d4d4;
    }

    QToolButton:hover {
        background-color: #3c3c3c;
    }

    QToolButton:pressed {
        background-color: #4c4c4c;
    }

    QPushButton {
        background-color: #3c3c3c;
        border: 1px solid #5c5c5c;
        border-radius: 4px;
        padding: 6px 16px;
        min-width: 60px;
        color: #d4d4d4;
    }

    QPushButton:hover {
        background-color: #4c4c4c;
        border-color: #6c6c6c;
    }

    QPushButton:pressed {
        background-color: #5c5c5c;
    }

    QPushButton:disabled {
        background-color: #2d2d2d;
        color: #6c6c6c;
    }

    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background-color: #3c3c3c;
        border: 1px solid #5c5c5c;
        border-radius: 4px;
        padding: 4px 8px;
        color: #d4d4d4;
    }

    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
        border-color: #0078d4;
    }

    QComboBox::drop-down {
        border: none;
    }

    QComboBox QAbstractItemView {
        background-color: #252526;
        border: 1px solid #3c3c3c;
        selection-background-color: #094771;
    }

    QListWidget, QTreeWidget, QTableWidget {
        background-color: #252526;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        color: #d4d4d4;
    }

    QListWidget::item:selected, QTreeWidget::item:selected {
        background-color: #094771;
        color: white;
    }

    QListWidget::item:hover, QTreeWidget::item:hover {
        background-color: #2a2d2e;
    }

    QGroupBox {
        font-weight: bold;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
        color: #d4d4d4;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 4px;
        color: #d4d4d4;
    }

    QSlider::groove:horizontal {
        height: 4px;
        background-color: #3c3c3c;
        border-radius: 2px;
    }

    QSlider::handle:horizontal {
        width: 16px;
        height: 16px;
        margin: -6px 0;
        background-color: #0078d4;
        border-radius: 8px;
    }

    QSlider::handle:horizontal:hover {
        background-color: #1a8cff;
    }

    QStatusBar {
        background-color: #007acc;
        border-top: none;
        color: white;
    }

    QScrollBar:vertical {
        background-color: #1e1e1e;
        width: 12px;
        border-radius: 6px;
    }

    QScrollBar::handle:vertical {
        background-color: #5c5c5c;
        border-radius: 6px;
        min-height: 20px;
    }

    QScrollBar::handle:vertical:hover {
        background-color: #7c7c7c;
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }

    QLabel {
        color: #d4d4d4;
    }

    QTabWidget::pane {
        border: 1px solid #3c3c3c;
        background-color: #1e1e1e;
    }

    QTabBar::tab {
        background-color: #2d2d2d;
        border: 1px solid #3c3c3c;
        padding: 6px 12px;
        color: #d4d4d4;
    }

    QTabBar::tab:selected {
        background-color: #1e1e1e;
        border-bottom-color: #1e1e1e;
    }

    QTabBar::tab:hover:!selected {
        background-color: #3c3c3c;
    }
    """

    @classmethod
    def apply(cls, app: Optional[QApplication] = None) -> None:
        """
        Apply the theme to the application.

        Args:
            app: QApplication instance. If None, uses the current instance.
        """
        if app is None:
            app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(cls.STYLESHEET)

    @classmethod
    def stylesheet(cls) -> str:
        """Get the theme stylesheet."""
        return cls.STYLESHEET
