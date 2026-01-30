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

"""Spectral line identification utilities.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple


@dataclass
class SpectralLine:
    """Represents a spectral line."""

    name: str
    wavelength: float  # Rest wavelength in Angstroms
    element: str = ""
    ionization: str = ""
    transition: str = ""

    @property
    def label(self) -> str:
        """Get a display label for the line."""
        if self.element and self.ionization:
            return f"{self.element} {self.ionization}"
        return self.name


# Common spectral lines database
COMMON_LINES: List[SpectralLine] = [
    SpectralLine("Lyman-alpha", 1215.67, "H", "I", "2-1"),
    SpectralLine("C IV", 1549.06, "C", "IV", ""),
    SpectralLine("Mg II", 2798.75, "Mg", "II", ""),
    SpectralLine("O II", 3727.09, "O", "II", ""),
    SpectralLine("H-delta", 4101.74, "H", "I", "6-2"),
    SpectralLine("H-gamma", 4340.47, "H", "I", "5-2"),
    SpectralLine("H-beta", 4861.33, "H", "I", "4-2"),
    SpectralLine("O III", 4958.91, "O", "III", ""),
    SpectralLine("O III", 5006.84, "O", "III", ""),
    SpectralLine("Na D", 5892.94, "Na", "I", ""),
    SpectralLine("H-alpha", 6562.82, "H", "I", "3-2"),
    SpectralLine("N II", 6583.41, "N", "II", ""),
    SpectralLine("S II", 6716.47, "S", "II", ""),
    SpectralLine("S II", 6730.85, "S", "II", ""),
]


class LineIdentifier:
    """Identifies spectral lines in observed spectra."""

    def __init__(
        self,
        line_database: Optional[List[SpectralLine]] = None,
    ) -> None:
        """Initialize the line identifier.

        Args:
            line_database: Custom line database, or use COMMON_LINES.
        """
        self._database: List[SpectralLine] = line_database or COMMON_LINES.copy()
        self._redshift: float = 0.0
        self._tolerance: float = 5.0  # Angstroms

    @property
    def redshift(self) -> float:
        """Get the current redshift."""
        return self._redshift

    @redshift.setter
    def redshift(self, value: float) -> None:
        """Set the redshift for line matching."""
        self._redshift = value

    @property
    def tolerance(self) -> float:
        """Get the wavelength matching tolerance."""
        return self._tolerance

    @tolerance.setter
    def tolerance(self, value: float) -> None:
        """Set the wavelength matching tolerance in Angstroms."""
        self._tolerance = value

    def add_line(self, line: SpectralLine) -> None:
        """Add a line to the database.

        Args:
            line: Spectral line to add.
        """
        self._database.append(line)

    def remove_line(self, name: str) -> bool:
        """Remove a line from the database by name.

        Args:
            name: Name of the line to remove.

        Returns:
            True if a line was removed.
        """
        for i, line in enumerate(self._database):
            if line.name == name:
                del self._database[i]
                return True
        return False

    def observed_wavelength(self, rest_wavelength: float) -> float:
        """Calculate observed wavelength at current redshift.

        Args:
            rest_wavelength: Rest wavelength in Angstroms.

        Returns:
            Observed wavelength in Angstroms.
        """
        return rest_wavelength * (1.0 + self._redshift)

    def rest_wavelength(self, observed_wavelength: float) -> float:
        """Calculate rest wavelength from observed wavelength.

        Args:
            observed_wavelength: Observed wavelength in Angstroms.

        Returns:
            Rest wavelength in Angstroms.
        """
        return observed_wavelength / (1.0 + self._redshift)

    def identify(
        self,
        observed_wavelength: float,
    ) -> List[Tuple[SpectralLine, float]]:
        """Identify possible lines at an observed wavelength.

        Args:
            observed_wavelength: Observed wavelength in Angstroms.

        Returns:
            List of (line, offset) tuples sorted by offset.
        """
        matches: List[Tuple[SpectralLine, float]] = []

        for line in self._database:
            expected = self.observed_wavelength(line.wavelength)
            offset = abs(observed_wavelength - expected)
            if offset <= self._tolerance:
                matches.append((line, offset))

        matches.sort(key=lambda x: x[1])
        return matches

    def find_lines_in_range(
        self,
        wavelength_min: float,
        wavelength_max: float,
    ) -> List[Tuple[SpectralLine, float]]:
        """Find all lines expected in a wavelength range.

        Args:
            wavelength_min: Minimum wavelength in Angstroms.
            wavelength_max: Maximum wavelength in Angstroms.

        Returns:
            List of (line, observed_wavelength) tuples.
        """
        result: List[Tuple[SpectralLine, float]] = []

        for line in self._database:
            obs_wave = self.observed_wavelength(line.wavelength)
            if wavelength_min <= obs_wave <= wavelength_max:
                result.append((line, obs_wave))

        result.sort(key=lambda x: x[1])
        return result

    def estimate_redshift(
        self,
        observed_wavelength: float,
        line: SpectralLine,
    ) -> float:
        """Estimate redshift given an observed line identification.

        Args:
            observed_wavelength: Observed wavelength in Angstroms.
            line: Identified spectral line.

        Returns:
            Estimated redshift.
        """
        return (observed_wavelength / line.wavelength) - 1.0
