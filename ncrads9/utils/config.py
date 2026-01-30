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
Configuration management using TOML files.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


class Config:
    """Application configuration manager using TOML files."""

    def __init__(self, config_path: Path | str | None = None) -> None:
        """
        Initialize configuration.

        Args:
            config_path: Path to TOML configuration file.
        """
        self._config: dict[str, Any] = {}
        self._config_path: Path | None = None

        if config_path is not None:
            self.load(config_path)

    def load(self, config_path: Path | str) -> None:
        """
        Load configuration from a TOML file.

        Args:
            config_path: Path to the TOML configuration file.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            tomllib.TOMLDecodeError: If the TOML is invalid.
        """
        self._config_path = Path(config_path)
        with open(self._config_path, "rb") as f:
            self._config = tomllib.load(f)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "display.colormap").
            default: Default value if key not found.

        Returns:
            The configuration value or default.
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_section(self, section: str) -> dict[str, Any]:
        """
        Get an entire configuration section.

        Args:
            section: Section name.

        Returns:
            Dictionary containing the section's configuration.
        """
        return self._config.get(section, {})

    @property
    def config_path(self) -> Path | None:
        """Return the current configuration file path."""
        return self._config_path

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in configuration."""
        return self.get(key) is not None

    def __repr__(self) -> str:
        """Return string representation."""
        return f"Config(path={self._config_path})"
