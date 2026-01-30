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
CoordinateEntry Widget - RA/Dec coordinate input widget.

Author: Yogesh Wadadekar
"""

import re
from typing import Optional, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLineEdit,
    QLabel,
    QComboBox,
)


class CoordinateEntry(QWidget):
    """A widget for entering astronomical coordinates (RA/Dec)."""

    coordinatesChanged = pyqtSignal(float, float)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initialize the CoordinateEntry widget.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)

        self._ra: float = 0.0
        self._dec: float = 0.0
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Format selector
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self._format_combo = QComboBox()
        self._format_combo.addItems(["Sexagesimal", "Decimal"])
        format_layout.addWidget(self._format_combo)
        format_layout.addStretch()
        layout.addLayout(format_layout)

        # RA entry
        ra_layout = QHBoxLayout()
        ra_layout.addWidget(QLabel("RA:"))
        self._ra_entry = QLineEdit()
        self._ra_entry.setPlaceholderText("HH:MM:SS.ss or degrees")
        ra_layout.addWidget(self._ra_entry)
        layout.addLayout(ra_layout)

        # Dec entry
        dec_layout = QHBoxLayout()
        dec_layout.addWidget(QLabel("Dec:"))
        self._dec_entry = QLineEdit()
        self._dec_entry.setPlaceholderText("DD:MM:SS.ss or degrees")
        dec_layout.addWidget(self._dec_entry)
        layout.addLayout(dec_layout)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._ra_entry.editingFinished.connect(self._on_coordinates_changed)
        self._dec_entry.editingFinished.connect(self._on_coordinates_changed)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)

    def _on_coordinates_changed(self) -> None:
        """Handle coordinate input change."""
        try:
            ra = self._parse_ra(self._ra_entry.text())
            dec = self._parse_dec(self._dec_entry.text())
            if ra is not None and dec is not None:
                self._ra = ra
                self._dec = dec
                self.coordinatesChanged.emit(ra, dec)
        except ValueError:
            pass

    def _on_format_changed(self, index: int) -> None:
        """Handle format change."""
        if index == 0:  # Sexagesimal
            self._ra_entry.setPlaceholderText("HH:MM:SS.ss")
            self._dec_entry.setPlaceholderText("DD:MM:SS.ss")
        else:  # Decimal
            self._ra_entry.setPlaceholderText("degrees")
            self._dec_entry.setPlaceholderText("degrees")

    def _parse_ra(self, text: str) -> Optional[float]:
        """Parse RA from text."""
        text = text.strip()
        if not text:
            return None

        if self._format_combo.currentIndex() == 0:  # Sexagesimal
            return self._sexagesimal_to_degrees(text, is_ra=True)
        else:  # Decimal
            return float(text)

    def _parse_dec(self, text: str) -> Optional[float]:
        """Parse Dec from text."""
        text = text.strip()
        if not text:
            return None

        if self._format_combo.currentIndex() == 0:  # Sexagesimal
            return self._sexagesimal_to_degrees(text, is_ra=False)
        else:  # Decimal
            return float(text)

    def _sexagesimal_to_degrees(self, text: str, is_ra: bool = False) -> float:
        """Convert sexagesimal string to degrees."""
        pattern = r"([+-]?\d+)[:\s]+(\d+)[:\s]+(\d+\.?\d*)"
        match = re.match(pattern, text)
        if not match:
            raise ValueError(f"Invalid sexagesimal format: {text}")

        d = float(match.group(1))
        m = float(match.group(2))
        s = float(match.group(3))

        sign = -1 if d < 0 or text.startswith("-") else 1
        degrees = abs(d) + m / 60.0 + s / 3600.0
        degrees *= sign

        if is_ra:
            degrees *= 15.0  # Convert hours to degrees

        return degrees

    def coordinates(self) -> Tuple[float, float]:
        """Get the current coordinates as (RA, Dec) in degrees."""
        return (self._ra, self._dec)

    def setCoordinates(self, ra: float, dec: float) -> None:
        """Set the coordinates in degrees."""
        self._ra = ra
        self._dec = dec

        if self._format_combo.currentIndex() == 0:  # Sexagesimal
            self._ra_entry.setText(self._degrees_to_sexagesimal(ra / 15.0))
            self._dec_entry.setText(self._degrees_to_sexagesimal(dec))
        else:  # Decimal
            self._ra_entry.setText(f"{ra:.6f}")
            self._dec_entry.setText(f"{dec:.6f}")

    def _degrees_to_sexagesimal(self, degrees: float) -> str:
        """Convert degrees to sexagesimal string."""
        sign = "-" if degrees < 0 else ""
        degrees = abs(degrees)
        d = int(degrees)
        m = int((degrees - d) * 60)
        s = (degrees - d - m / 60.0) * 3600
        return f"{sign}{d:02d}:{m:02d}:{s:05.2f}"
