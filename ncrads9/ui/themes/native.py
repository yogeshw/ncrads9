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
Native Theme - Platform native theme.

Author: Yogesh Wadadekar
"""

import sys
from typing import Optional

from PyQt6.QtWidgets import QApplication, QStyleFactory


class NativeTheme:
    """Native platform theme for the application."""

    NAME = "Native"

    # Minimal stylesheet that preserves native look while adding minor tweaks
    STYLESHEET = """
    QWidget {
        font-size: 13px;
    }

    QGroupBox {
        font-weight: bold;
        margin-top: 8px;
        padding-top: 8px;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 4px;
    }
    """

    @classmethod
    def get_platform_style(cls) -> str:
        """
        Get the appropriate native style for the current platform.

        Returns:
            Style name for the current platform.
        """
        available_styles = QStyleFactory.keys()

        if sys.platform == "darwin":
            # macOS
            preferred = ["macOS", "Fusion"]
        elif sys.platform == "win32":
            # Windows
            preferred = ["Windows", "WindowsVista", "Fusion"]
        else:
            # Linux and others
            preferred = ["Fusion", "Breeze", "Oxygen", "GTK+"]

        for style in preferred:
            if style in available_styles:
                return style

        # Fallback to first available
        return available_styles[0] if available_styles else "Fusion"

    @classmethod
    def apply(cls, app: Optional[QApplication] = None) -> None:
        """
        Apply the native theme to the application.

        Args:
            app: QApplication instance. If None, uses the current instance.
        """
        if app is None:
            app = QApplication.instance()
        if app is not None:
            style_name = cls.get_platform_style()
            app.setStyle(style_name)
            app.setStyleSheet(cls.STYLESHEET)

    @classmethod
    def stylesheet(cls) -> str:
        """Get the theme stylesheet."""
        return cls.STYLESHEET

    @classmethod
    def available_styles(cls) -> list[str]:
        """
        Get list of available platform styles.

        Returns:
            List of available style names.
        """
        return QStyleFactory.keys()
