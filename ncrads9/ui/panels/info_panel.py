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
The information panel: DS9's readout of the file, the pixel and the cursor.

DS9 grids this in `LayoutInfoPanelHorz` (`ds9/library/info.tcl`) as a seven
column table, one row per field, in a fixed order: File, Object, Keyword,
Min, Max, Low/High, Value, Units, WCS (and each of the alternate systems
`wcsa`..`wcsz`), Detector, Amplifier, Physical, Image, and finally the frame
number with its zoom and rotation. Each row is shown or hidden by its own
entry in the View menu, so the panel's height changes as the user turns fields
on and off. This is a direct port of that table.

The panel that stood here before was NCRADS9's own invention -- four labelled
group boxes carrying pixel x/y, one value, RA/Dec, Galactic l/b and whole
image statistics -- and it was never shown: nothing in the window ever
constructed it. The DS9 fields it lacked (filename, object, units, min/max
with their positions, low/high cut limits, physical and amplifier and detector
coordinates, frame/zoom/angle) are exactly what a DS9 user looks at, so the
rows below replace it rather than extend it. Whole-image statistics have a
dialog of their own (`Analysis -> Statistics`) and are not part of DS9's panel.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QGridLayout, QLabel, QLineEdit, QSizePolicy, QWidget

from ..layout.view_state import INFO_FIELDS, WCS_SUFFIXES, ViewLayout, ViewState

#: DS9's `ww` -- the character width of a value cell.
VALUE_WIDTH = 12
#: DS9's `xx` -- the character width of the filename and object cells.
WIDE_WIDTH = 42
#: DS9's `ww` in `LayoutInfoPanelVert` -- every cell, wide ones included,
#: narrows when the panel sits in a column beside the canvas.
COMPACT_WIDTH = 13
#: The placeholder DS9 shows for a field with nothing in it.
BLANK = ""
#: Qt's "no maximum", for undoing a compact cap.
MAX_CELL_WIDTH = 16777215
#: The column the grid lets take up the slack, as DS9 does for column 7.
STRETCH_COLUMN = 7


@dataclass
class _Row:
    """One field of the panel: its widgets, and where they sit in the grid."""

    name: str
    #: (widget, column, column span) triples.
    cells: list[tuple[QWidget, int, int]] = field(default_factory=list)


class InfoPanel(QWidget):
    """DS9's information panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Initialize the information panel.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("InfoPanel")

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(2, 2, 2, 2)
        self._grid.setHorizontalSpacing(4)
        self._grid.setVerticalSpacing(1)
        self._grid.setColumnStretch(STRETCH_COLUMN, 1)

        #: Value widgets, by the name the update methods use.
        self._values: dict[str, QLabel] = {}
        #: Rows in DS9's grid order.
        self._rows: list[_Row] = []
        #: Which rows are shown. Starts at DS9's defaults.
        self._visible: dict[str, bool] = {}
        #: Cells wider than one value column -> their full width, so
        #: `set_compact` can put them back.
        self._wide_cells: dict[str, int] = {}
        self._compact = False

        self._build_rows()
        self.apply_state(ViewState())

    # -- construction --------------------------------------------------------

    def set_compact(self, compact: bool) -> None:
        """Narrow the wide cells for a panel laid out in a column.

        DS9's `LayoutInfoPanelVert` drops every cell to thirteen characters
        when the panel stands beside the canvas rather than above it,
        otherwise the filename row alone sets the whole window's width. DS9
        also splits each title and value onto separate rows there; this keeps
        one row per field and only narrows the cells.
        """
        if compact == self._compact:
            return
        self._compact = compact
        for key, full_width in self._wide_cells.items():
            label = self._values[key]
            digit = label.fontMetrics().horizontalAdvance("0")
            if compact:
                label.setMinimumWidth(COMPACT_WIDTH * digit)
                # Cap it too, or a long filename would widen the whole column
                # regardless of the minimum. Tk clips its entries the same way.
                label.setMaximumWidth(COMPACT_WIDTH * digit)
            else:
                label.setMinimumWidth(full_width * digit)
                label.setMaximumWidth(MAX_CELL_WIDTH)

    def _value(self, key: str, *, width: int = VALUE_WIDTH) -> QLabel:
        """A right-aligned monospaced cell, registered under `key`.

        Monospaced because the readout updates on every mouse move; a
        proportional font makes the columns jitter as the digits change.
        """
        label = QLabel(BLANK)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        label.setFont(font)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setMinimumWidth(width * label.fontMetrics().horizontalAdvance("0"))
        # Minimum, not Ignored: an Ignored policy lets Qt shrink the cell
        # below its own minimum, and the columns then print over each other.
        label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._values[key] = label
        if width != VALUE_WIDTH:
            self._wide_cells[key] = width
        return label

    @staticmethod
    def _title(text: str) -> QLabel:
        """A left-aligned row title."""
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _add_row(self, name: str, cells: list[tuple[QWidget, int, int]]) -> None:
        """Register one field's row."""
        self._rows.append(_Row(name, cells))

    def _xy_row(self, name: str, title: str) -> None:
        """A row of the form `Title  x <value>  y <value>`.

        DS9 uses this shape for the image, physical, amplifier and detector
        coordinate systems, and for the WCS systems.
        """
        self._add_row(
            name,
            [
                (self._title(title), 0, 1),
                (self._title("x"), 1, 1),
                (self._value(f"{name}_x"), 2, 1),
                (self._title("y"), 3, 1),
                (self._value(f"{name}_y"), 4, 1),
            ],
        )

    def _build_rows(self) -> None:
        """Create every row, in DS9's `LayoutInfoPanelHorz` order."""
        self._add_row(
            "filename",
            [(self._title("File"), 0, 1), (self._value("filename", width=WIDE_WIDTH), 2, 6)],
        )
        self._add_row(
            "object",
            [(self._title("Object"), 0, 1), (self._value("object", width=WIDE_WIDTH), 2, 6)],
        )

        # DS9's keyword row is an editable entry: the user types a FITS
        # keyword and the panel shows that card's value for the current frame.
        self.keyword_entry = QLineEdit()
        self.keyword_entry.setMaximumWidth(
            VALUE_WIDTH * self.keyword_entry.fontMetrics().horizontalAdvance("0")
        )
        self.keyword_entry.setPlaceholderText("KEYWORD")
        self._add_row(
            "keyword",
            [
                (self.keyword_entry, 0, 1),
                (self._value("keyword", width=WIDE_WIDTH), 2, 6),
            ],
        )

        for name, title in (("min", "Min"), ("max", "Max")):
            self._add_row(
                "minmax",
                [
                    (self._title(title), 0, 1),
                    (self._title("x"), 1, 1),
                    (self._value(f"{name}_x"), 2, 1),
                    (self._title("y"), 3, 1),
                    (self._value(f"{name}_y"), 4, 1),
                    (self._value(name), 6, 1),
                ],
            )

        self._add_row(
            "lowhigh",
            [
                (self._title("Low High"), 0, 1),
                (self._value("low"), 2, 1),
                (self._value("high"), 4, 1),
            ],
        )
        self._add_row(
            "value",
            [(self._title("Value"), 0, 1), (self._value("value", width=WIDE_WIDTH), 2, 6)],
        )
        self._add_row(
            "bunit",
            [(self._title("Units"), 0, 1), (self._value("bunit"), 2, 1)],
        )

        # The primary WCS, then DS9's twenty-six alternates. The row title is
        # the sky frame in use ("fk5", "galactic", ...), which the WCS menu
        # changes, so it is a value cell rather than a fixed title.
        for suffix in ("", *WCS_SUFFIXES):
            name = "wcs" if not suffix else f"wcs_{suffix}"
            self._add_row(
                name,
                [
                    (self._value(f"{name}_label"), 0, 1),
                    (self._title("α"), 1, 1),
                    (self._value(f"{name}_x"), 2, 1),
                    (self._title("δ"), 3, 1),
                    (self._value(f"{name}_y"), 4, 1),
                ],
            )

        self._xy_row("detector", "Detector")
        self._xy_row("amplifier", "Amplifier")
        self._xy_row("physical", "Physical")
        self._xy_row("image", "Image")

        self._add_row(
            "frame",
            [
                (self._value("frame", width=8), 0, 1),
                (self._title("Zoom"), 1, 1),
                (self._value("zoom"), 2, 1),
                (self._value("angle"), 4, 1),
                (self._title("Angle"), 5, 1),
            ],
        )

    # -- visibility ----------------------------------------------------------

    def apply_state(self, state: ViewState) -> None:
        """Show the fields `state` asks for, in DS9's order and widths."""
        self.set_compact(state.layout in (ViewLayout.VERTICAL, ViewLayout.ADVANCED))
        self._visible = {name: state.field_visible(name) for name in INFO_FIELDS}
        self._relayout()

    def set_field_visible(self, name: str, visible: bool) -> None:
        """Show or hide one field.

        Args:
            name: An entry of `INFO_FIELDS`.
            visible: Whether to show it.

        Raises:
            KeyError: If `name` is not a field of the panel.
        """
        if name not in self._visible:
            raise KeyError(f"not an info-panel field: {name}")
        self._visible[name] = bool(visible)
        self._relayout()

    def field_visible(self, name: str) -> bool:
        """Whether one field is currently shown."""
        return self._visible.get(name, False)

    def visible_fields(self) -> tuple[str, ...]:
        """Every shown field, in grid order."""
        return tuple(name for name in INFO_FIELDS if self._visible.get(name))

    def _relayout(self) -> None:
        """Re-grid the shown rows, packed from row zero with no gaps."""
        while self._grid.count():
            self._grid.takeAt(0)
        for row in self._rows:
            for widget, _column, _span in row.cells:
                widget.hide()

        index = 0
        for row in self._rows:
            if not self._visible.get(row.name, False):
                continue
            for widget, column, span in row.cells:
                self._grid.addWidget(widget, index, column, 1, span)
                widget.show()
            self._grid.setRowStretch(index, 0)
            index += 1

        # Pack the rows against the top. Without this the vertical layout,
        # where the panel has a whole column of height to fill, spreads them
        # evenly down it.
        self._grid.setRowStretch(index, 1)

    # -- readout -------------------------------------------------------------

    def set_text(self, key: str, text: str) -> None:
        """Write one value cell.

        Unknown keys are ignored, so a caller can offer a field the panel does
        not have (an alternate WCS that this file lacks, say) without guarding.
        """
        label = self._values.get(key)
        if label is not None:
            label.setText(text)

    def set_filename(self, filename: str) -> None:
        """Show the loaded file's name."""
        self.set_text("filename", filename)

    def set_object(self, name: str) -> None:
        """Show the OBJECT card."""
        self.set_text("object", name)

    def set_keyword(self, value: str) -> None:
        """Show the value of the keyword the user typed."""
        self.set_text("keyword", value)

    def set_value(self, text: str) -> None:
        """Show the pixel value under the cursor."""
        self.set_text("value", text)

    def set_units(self, units: str) -> None:
        """Show the BUNIT card."""
        self.set_text("bunit", units)

    def set_minmax(
        self,
        minimum: str,
        maximum: str,
        min_pos: tuple[str, str] = (BLANK, BLANK),
        max_pos: tuple[str, str] = (BLANK, BLANK),
    ) -> None:
        """Show the data range, and where each extreme is.

        Args:
            minimum: The lowest pixel value, formatted.
            maximum: The highest pixel value, formatted.
            min_pos: Image (x, y) of the lowest pixel.
            max_pos: Image (x, y) of the highest pixel.
        """
        self.set_text("min", minimum)
        self.set_text("max", maximum)
        self.set_text("min_x", min_pos[0])
        self.set_text("min_y", min_pos[1])
        self.set_text("max_x", max_pos[0])
        self.set_text("max_y", max_pos[1])

    def set_lowhigh(self, low: str, high: str) -> None:
        """Show the current scale limits."""
        self.set_text("low", low)
        self.set_text("high", high)

    def set_coords(self, system: str, x: str, y: str) -> None:
        """Show a cursor position in one coordinate system.

        Args:
            system: "image", "physical", "amplifier" or "detector".
            x: The formatted x coordinate.
            y: The formatted y coordinate.
        """
        self.set_text(f"{system}_x", x)
        self.set_text(f"{system}_y", y)

    def set_wcs(self, label: str, x: str, y: str, suffix: str = "") -> None:
        """Show a cursor position in a WCS.

        Args:
            label: The sky frame's name, e.g. "fk5".
            x: The formatted longitude.
            y: The formatted latitude.
            suffix: "" for the primary WCS, or one of "a".."z".
        """
        name = "wcs" if not suffix else f"wcs_{suffix}"
        self.set_text(f"{name}_label", label)
        self.set_text(f"{name}_x", x)
        self.set_text(f"{name}_y", y)

    def set_frame(self, frame: str, zoom: str = BLANK, angle: str = BLANK) -> None:
        """Show the current frame's number, zoom and rotation."""
        self.set_text("frame", frame)
        self.set_text("zoom", zoom)
        self.set_text("angle", angle)

    def clear_cursor(self) -> None:
        """Blank every field that tracks the cursor.

        The file, object, units and frame rows are left alone: they describe
        the loaded image, not the pointer, and DS9 keeps them on screen when
        the pointer leaves the canvas.
        """
        for key, label in self._values.items():
            if key.endswith(("_x", "_y")) or key == "value":
                label.setText(BLANK)

    def clear(self) -> None:
        """Blank every field."""
        for label in self._values.values():
            label.setText(BLANK)
