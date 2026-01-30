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
User preferences storage and management.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Preferences:
    """User preferences storage with JSON persistence."""

    DEFAULT_PREFS: dict[str, Any] = {
        "colormap": "gray",
        "scale": "linear",
        "zoom_level": 1.0,
        "recent_files": [],
        "max_recent_files": 10,
        "window_geometry": None,
        "show_toolbar": True,
        "show_statusbar": True,
    }

    def __init__(self, prefs_path: Path | str | None = None) -> None:
        """
        Initialize preferences.

        Args:
            prefs_path: Path to preferences JSON file.
        """
        self._prefs: dict[str, Any] = self.DEFAULT_PREFS.copy()
        self._prefs_path: Path | None = None

        if prefs_path is not None:
            self._prefs_path = Path(prefs_path)
            self.load()

    def load(self) -> None:
        """Load preferences from file if it exists."""
        if self._prefs_path is None or not self._prefs_path.exists():
            return

        try:
            with open(self._prefs_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                self._prefs.update(loaded)
        except (json.JSONDecodeError, OSError):
            pass

    def save(self) -> None:
        """Save preferences to file."""
        if self._prefs_path is None:
            return

        self._prefs_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._prefs_path, "w", encoding="utf-8") as f:
            json.dump(self._prefs, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a preference value.

        Args:
            key: Preference key.
            default: Default value if not found.

        Returns:
            The preference value.
        """
        return self._prefs.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        """
        Set a preference value.

        Args:
            key: Preference key.
            value: Value to set.
            save: Whether to save immediately.
        """
        self._prefs[key] = value
        if save:
            self.save()

    def add_recent_file(self, filepath: Path | str) -> None:
        """
        Add a file to recent files list.

        Args:
            filepath: Path to the file.
        """
        filepath = str(filepath)
        recent = self._prefs.get("recent_files", [])
        if filepath in recent:
            recent.remove(filepath)
        recent.insert(0, filepath)

        max_recent = self._prefs.get("max_recent_files", 10)
        self._prefs["recent_files"] = recent[:max_recent]
        self.save()

    def get_recent_files(self) -> list[str]:
        """Return list of recent files."""
        return self._prefs.get("recent_files", [])

    def reset(self) -> None:
        """Reset preferences to defaults."""
        self._prefs = self.DEFAULT_PREFS.copy()
        self.save()

    def __repr__(self) -> str:
        """Return string representation."""
        return f"Preferences(path={self._prefs_path})"
