# NCRADS9 - NCRA DS9-like FITS Viewer
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
One axis of a plot: its label, its range, and how it is drawn.

DS9's per-axis menu offers Log, Flip and Grid, with the range set from a
separate Axes Range dialog that can also leave it automatic
(`ds9/library/plotdialog.tcl:234`). "Automatic" is a range of None here
rather than a computed pair, so a dataset added later re-fits the axis
instead of being cropped to what the old data happened to span.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AxisFormat(Enum):
    """How an axis's numbers are written."""

    #: Whatever matplotlib would choose.
    AUTOMATIC = "automatic"
    #: Plain decimal, e.g. 1234.5.
    DECIMAL = "decimal"
    #: Exponential, e.g. 1.2345e+03.
    EXPONENTIAL = "exponential"


@dataclass
class Axis:
    """One axis.

    Attributes:
        label: The axis title.
        log: Logarithmic rather than linear.
        flip: Increasing the other way.
        grid: Draw grid lines at the ticks.
        minimum, maximum: The range. None on either means "fit the data",
            so a dataset added later is not cropped to the old extent.
        number_format: How the tick numbers are written.
    """

    label: str = ""
    log: bool = False
    flip: bool = False
    grid: bool = True
    minimum: float | None = None
    maximum: float | None = None
    number_format: AxisFormat = AxisFormat.AUTOMATIC

    @property
    def automatic(self) -> bool:
        """Whether the range is left to the data."""
        return self.minimum is None or self.maximum is None

    @property
    def range(self) -> tuple[float, float] | None:
        """The range, or None when it is automatic."""
        if self.automatic:
            return None
        return (float(self.minimum), float(self.maximum))  # type: ignore[arg-type]

    def set_range(self, low: float | None, high: float | None) -> None:
        """Set the range, or clear it by passing None.

        A reversed pair is swapped rather than refused: dragging a zoom box
        right to left means the same rectangle.
        """
        if low is None or high is None:
            self.minimum = self.maximum = None
            return
        self.minimum, self.maximum = (float(low), float(high)) if low <= high else (float(high), float(low))

    def clear_range(self) -> None:
        """Go back to fitting the data."""
        self.minimum = self.maximum = None

    def to_dict(self) -> dict:
        """The axis as plain data, for saving."""
        return {
            "label": self.label,
            "log": self.log,
            "flip": self.flip,
            "grid": self.grid,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "number_format": self.number_format.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Axis:
        """Read an axis back from saved data."""
        return cls(
            label=str(data.get("label", "")),
            log=bool(data.get("log", False)),
            flip=bool(data.get("flip", False)),
            grid=bool(data.get("grid", True)),
            minimum=data.get("minimum"),
            maximum=data.get("maximum"),
            number_format=AxisFormat(data.get("number_format", AxisFormat.AUTOMATIC.value)),
        )
