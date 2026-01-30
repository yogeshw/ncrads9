# NCRADS9 - A Python/Qt6 Clone of SAOImageDS9
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
NCRADS9 Application Setup

This module initializes the Qt application and main window.

Author: Yogesh Wadadekar
"""

from typing import List

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ncrads9 import __version__
from ncrads9.ui.main_window import MainWindow
from ncrads9.utils.config import Config
from ncrads9.utils.logger import setup_logging


def run_application(argv: List[str]) -> int:
    """
    Initialize and run the NCRADS9 application.

    Args:
        argv: Command line arguments.

    Returns:
        Exit code.
    """
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application
    app = QApplication(argv)
    app.setApplicationName("NCRADS9")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("NCRA")

    # Setup logging
    setup_logging()

    # Load configuration
    config = Config()

    # Create main window
    main_window = MainWindow(config)
    main_window.show()

    # Process command line arguments for files to open
    files_to_open = [arg for arg in argv[1:] if not arg.startswith("-")]
    for filepath in files_to_open:
        main_window.open_file(filepath)

    return app.exec()
