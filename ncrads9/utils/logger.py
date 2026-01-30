# NCRA DS9 - Astronomical Image Viewer
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
Logging configuration and utilities.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TextIO


def setup_logging(
    level: int | str = logging.INFO,
    log_file: Path | str | None = None,
    log_format: str | None = None,
    stream: TextIO | None = None,
) -> logging.Logger:
    """
    Configure application logging.

    Args:
        level: Logging level (e.g., logging.DEBUG, "INFO").
        log_file: Optional path to log file.
        log_format: Custom log format string.
        stream: Output stream (defaults to stderr).

    Returns:
        Configured root logger for the application.
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logger = logging.getLogger("ncrads9")
    logger.setLevel(level)
    logger.handlers.clear()

    formatter = logging.Formatter(log_format)

    # Console handler
    console_handler = logging.StreamHandler(stream or sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler if specified
    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger for a module.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Logger instance.
    """
    return logging.getLogger(f"ncrads9.{name}")


class LogContext:
    """Context manager for temporary log level changes."""

    def __init__(self, logger: logging.Logger, level: int) -> None:
        """
        Initialize log context.

        Args:
            logger: Logger to modify.
            level: Temporary log level.
        """
        self._logger = logger
        self._new_level = level
        self._old_level: int | None = None

    def __enter__(self) -> logging.Logger:
        """Enter context and set temporary level."""
        self._old_level = self._logger.level
        self._logger.setLevel(self._new_level)
        return self._logger

    def __exit__(self, *args: object) -> None:
        """Exit context and restore original level."""
        if self._old_level is not None:
            self._logger.setLevel(self._old_level)
