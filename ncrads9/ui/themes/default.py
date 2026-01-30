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
Default Theme - Light theme stylesheet.

Author: Yogesh Wadadekar
"""

from typing import Optional

from PyQt6.QtWidgets import QApplication


class DefaultTheme:
    """Default light theme for the application."""

    NAME = "Default"

    STYLESHEET = """
    QMainWindow {
        background-color: #f5f5f5;
    }

    QWidget {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 13px;
    }

    QMenuBar {
        background-color: #ffffff;
        border-bottom: 1px solid #e0e0e0;
        padding: 2px;
    }

    QMenuBar::item {
        padding: 4px 8px;
        background-color: transparent;
    }

    QMenuBar::item:selected {
        background-color: #e8e8e8;
        border-radius: 4px;
    }

    QMenu {
        background-color: #ffffff;
        border: 1px solid #d0d0d0;
        border-radius: 4px;
        padding: 4px;
    }

    QMenu::item {
        padding: 6px 24px;
        border-radius: 2px;
    }

    QMenu::item:selected {
        background-color: #0078d4;
        color: white;
    }

    QToolBar {
        background-color: #fafafa;
        border-bottom: 1px solid #e0e0e0;
        spacing: 4px;
        padding: 4px;
    }

    QToolButton {
        background-color: transparent;
        border: none;
        border-radius: 4px;
        padding: 4px;
    }

    QToolButton:hover {
        background-color: #e8e8e8;
    }

    QToolButton:pressed {
        background-color: #d8d8d8;
    }

    QPushButton {
        background-color: #ffffff;
        border: 1px solid #d0d0d0;
        border-radius: 4px;
        padding: 6px 16px;
        min-width: 60px;
    }

    QPushButton:hover {
        background-color: #f8f8f8;
        border-color: #b0b0b0;
    }

    QPushButton:pressed {
        background-color: #e8e8e8;
    }

    QPushButton:disabled {
        background-color: #f0f0f0;
        color: #a0a0a0;
    }

    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background-color: #ffffff;
        border: 1px solid #d0d0d0;
        border-radius: 4px;
        padding: 4px 8px;
    }

    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
        border-color: #0078d4;
    }

    QListWidget, QTreeWidget, QTableWidget {
        background-color: #ffffff;
        border: 1px solid #d0d0d0;
        border-radius: 4px;
    }

    QListWidget::item:selected, QTreeWidget::item:selected {
        background-color: #0078d4;
        color: white;
    }

    QGroupBox {
        font-weight: bold;
        border: 1px solid #d0d0d0;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 4px;
        color: #404040;
    }

    QSlider::groove:horizontal {
        height: 4px;
        background-color: #d0d0d0;
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
        background-color: #106ebe;
    }

    QStatusBar {
        background-color: #f5f5f5;
        border-top: 1px solid #e0e0e0;
    }

    QScrollBar:vertical {
        background-color: #f5f5f5;
        width: 12px;
        border-radius: 6px;
    }

    QScrollBar::handle:vertical {
        background-color: #c0c0c0;
        border-radius: 6px;
        min-height: 20px;
    }

    QScrollBar::handle:vertical:hover {
        background-color: #a0a0a0;
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
