# NCRADS9 - NCRA DS9 Visualization Tool
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
DS9 backup file reader for NCRADS9.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Any, Optional, Union


class BackupReader:
    """Reader for DS9 backup files."""

    def __init__(self, filepath: Union[str, Path]) -> None:
        """
        Initialize backup reader.

        Args:
            filepath: Path to the DS9 backup file.
        """
        self.filepath = Path(filepath)
        self._content: str = ""
        self._parsed: dict[str, Any] = {}

    def read(self) -> dict[str, Any]:
        """
        Read and parse the backup file.

        Returns:
            Parsed backup data.
        """
        with open(self.filepath, "r") as f:
            self._content = f.read()

        self._parse()
        return self._parsed

    def _parse(self) -> None:
        """Parse the backup file content."""
        self._parsed = {
            "version": None,
            "frames": [],
            "regions": [],
            "colormaps": [],
            "scales": [],
            "commands": [],
        }

        lines = self._content.split("\n")
        current_section: Optional[str] = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("global"):
                self._parse_global(line)
            elif line.startswith("frame"):
                current_section = "frames"
                self._parsed["frames"].append(self._parse_frame(line))
            elif line.startswith("regions"):
                current_section = "regions"
            elif line.startswith("colormap"):
                self._parse_colormap(line)
            elif line.startswith("scale"):
                self._parse_scale(line)
            elif current_section == "regions":
                self._parsed["regions"].append(self._parse_region(line))
            else:
                self._parsed["commands"].append(line)

    def _parse_global(self, line: str) -> None:
        """Parse global settings line."""
        parts = line.split()
        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                self._parsed[key] = value

    def _parse_frame(self, line: str) -> dict[str, Any]:
        """Parse frame definition."""
        frame: dict[str, Any] = {"id": None, "file": None, "options": {}}
        parts = line.split()

        for i, part in enumerate(parts):
            if part == "frame" and i + 1 < len(parts):
                frame["id"] = parts[i + 1]
            elif "=" in part:
                key, value = part.split("=", 1)
                frame["options"][key] = value

        return frame

    def _parse_region(self, line: str) -> dict[str, Any]:
        """Parse region definition."""
        region: dict[str, Any] = {
            "type": None,
            "coords": [],
            "properties": {},
        }

        if "(" in line:
            type_end = line.index("(")
            region["type"] = line[:type_end].strip()
            coords_str = line[type_end + 1 : line.index(")")]
            region["coords"] = [c.strip() for c in coords_str.split(",")]

        return region

    def _parse_colormap(self, line: str) -> None:
        """Parse colormap settings."""
        parts = line.split()
        if len(parts) >= 2:
            self._parsed["colormaps"].append(parts[1])

    def _parse_scale(self, line: str) -> None:
        """Parse scale settings."""
        parts = line.split()
        if len(parts) >= 2:
            self._parsed["scales"].append({
                "type": parts[1],
                "params": parts[2:] if len(parts) > 2 else [],
            })

    def get_frames(self) -> list[dict[str, Any]]:
        """
        Get frame definitions.

        Returns:
            List of frame dictionaries.
        """
        return self._parsed.get("frames", [])

    def get_regions(self) -> list[dict[str, Any]]:
        """
        Get region definitions.

        Returns:
            List of region dictionaries.
        """
        return self._parsed.get("regions", [])

    def get_commands(self) -> list[str]:
        """
        Get DS9 commands.

        Returns:
            List of command strings.
        """
        return self._parsed.get("commands", [])