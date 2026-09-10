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
DS9's advanced symbol editor.

A list of rules, each with a condition and an appearance, and "for the first
expression to evaluate true, a given symbol is displayed"
(`ds9/doc/ref/catalog.html`). So the order of the rules is the whole point,
and the editor is a table you can reorder rather than a form.

The columns are DS9's own (`catsym.tcl`): condition, shape, colour, width,
size, size2, angle, text and font. Size, size2 and angle take expressions
over the catalogue's columns; text is text unless it uses `$` or
`[expr ...]`; and the condition decides which rows get the symbol at all.

Rule sets load and save, which is DS9's "These symbol expressions can be
saved for future use".

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...catalogs.catalog_set import COLORS, SHAPES, Symbol, load_symbols, save_symbols

#: How big the editor opens.
WINDOW_SIZE = (900, 420)

#: The columns, in DS9's order, and which kind of editor each takes.
COLUMNS: tuple[tuple[str, str], ...] = (
    ("Condition", "text"),
    ("Shape", "shape"),
    ("Colour", "color"),
    ("Width", "width"),
    ("Size", "text"),
    ("Size2", "text"),
    ("Angle", "text"),
    ("Text", "text"),
)

#: The line widths offered.
WIDTHS: tuple[int, ...] = (1, 2, 3, 4)

#: The filter its Load and Save offer.
SYMBOL_FILTER = "Symbol Files (*.sym *.json);;All Files (*)"


class SymbolEditorDialog(QDialog):
    """Edit one catalogue's symbol rules.

    Args:
        symbols: The rules to edit. A copy is edited, so Cancel cancels.
        columns: The catalogue's column names, shown as a reminder of what
            the expressions may refer to.
        parent: Optional parent widget.
    """

    #: Emitted with the edited rules when Apply or OK is pressed.
    symbols_changed = pyqtSignal(object)

    def __init__(
        self,
        symbols: list[Symbol] | None = None,
        columns: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Symbol Editor")
        self.resize(*WINDOW_SIZE)
        self.symbols = [Symbol(**vars(symbol)) for symbol in (symbols or [Symbol()])]

        layout = QVBoxLayout(self)
        if columns:
            hint = QLabel("Expressions may use <b>$column</b>: " + ", ".join(f"${name}" for name in columns))
            hint.setWordWrap(True)
            layout.addWidget(hint)

        self._table = QTableWidget()
        self._table.setColumnCount(len(COLUMNS))
        self._table.setHorizontalHeaderLabels([label for label, _kind in COLUMNS])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        layout.addWidget(self._table)

        layout.addLayout(self._buttons())

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self._accept)
        box.rejected.connect(self.reject)
        box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        layout.addWidget(box)

        self.reload()

    def _buttons(self) -> QHBoxLayout:
        """Add, remove, reorder, load and save."""
        row = QHBoxLayout()
        #: Button name -> the button, so a test can press one.
        self.buttons: dict[str, QPushButton] = {}
        for name, label, handler in (
            ("add", "Add", self.add_rule),
            ("remove", "Remove", self.remove_rule),
            ("up", "Move Up", lambda: self.move_rule(-1)),
            ("down", "Move Down", lambda: self.move_rule(1)),
            ("load", "Load...", self.load),
            ("save", "Save...", self.save),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, call=handler: call())
            row.addWidget(button)
            self.buttons[name] = button
        row.addStretch()
        return row

    # -- the table -------------------------------------------------------------

    def reload(self) -> None:
        """Rebuild the table from the rules."""
        self._table.setRowCount(len(self.symbols))
        for row, symbol in enumerate(self.symbols):
            self._fill_row(row, symbol)
        self._table.resizeColumnsToContents()

    def _fill_row(self, row: int, symbol: Symbol) -> None:
        """Put one rule's editors in one table row."""
        values = (
            symbol.condition,
            symbol.shape,
            symbol.color,
            symbol.width,
            symbol.size,
            symbol.size2,
            symbol.angle,
            symbol.text,
        )
        for column, ((_label, kind), value) in enumerate(zip(COLUMNS, values, strict=True)):
            if kind == "shape":
                self._table.setCellWidget(row, column, _combo(SHAPES, str(value)))
            elif kind == "color":
                self._table.setCellWidget(row, column, _combo(COLORS, str(value)))
            elif kind == "width":
                box = QSpinBox()
                box.setRange(min(WIDTHS), max(WIDTHS))
                box.setValue(int(value))
                self._table.setCellWidget(row, column, box)
            else:
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row, column, item)

    def gather(self) -> list[Symbol]:
        """Read the table back into the rules."""
        gathered: list[Symbol] = []
        for row in range(self._table.rowCount()):
            existing = self.symbols[row] if row < len(self.symbols) else Symbol()
            gathered.append(
                Symbol(
                    condition=self._text(row, 0),
                    shape=self._choice(row, 1, existing.shape),
                    color=self._choice(row, 2, existing.color),
                    width=self._number(row, 3, existing.width),
                    size=self._text(row, 4) or existing.size,
                    size2=self._text(row, 5) or existing.size2,
                    angle=self._text(row, 6) or existing.angle,
                    text=self._text(row, 7),
                    font=existing.font,
                    font_size=existing.font_size,
                    units=existing.units,
                )
            )
        self.symbols = gathered
        return gathered

    def _text(self, row: int, column: int) -> str:
        """One text cell."""
        item = self._table.item(row, column)
        return item.text().strip() if item is not None else ""

    def _choice(self, row: int, column: int, default: str) -> str:
        """One combo cell."""
        widget = self._table.cellWidget(row, column)
        return widget.currentText() if isinstance(widget, QComboBox) else default

    def _number(self, row: int, column: int, default: int) -> int:
        """One spin cell."""
        widget = self._table.cellWidget(row, column)
        return widget.value() if isinstance(widget, QSpinBox) else default

    # -- editing the list --------------------------------------------------------

    def add_rule(self) -> None:
        """Add a rule at the end."""
        self.gather()
        self.symbols.append(Symbol())
        self.reload()

    def remove_rule(self) -> None:
        """Remove the selected rule, keeping at least one.

        A catalogue with no rules draws nothing and offers no way back, so
        the last rule cannot be removed -- it is reset instead.
        """
        row = self._table.currentRow()
        self.gather()
        if row < 0 or row >= len(self.symbols):
            return
        if len(self.symbols) == 1:
            self.symbols = [Symbol()]
        else:
            del self.symbols[row]
        self.reload()

    def move_rule(self, direction: int) -> None:
        """Move the selected rule up or down, which changes which one wins."""
        row = self._table.currentRow()
        self.gather()
        target = row + direction
        if row < 0 or target < 0 or target >= len(self.symbols):
            return
        self.symbols[row], self.symbols[target] = self.symbols[target], self.symbols[row]
        self.reload()
        self._table.selectRow(target)

    # -- files --------------------------------------------------------------------

    def load(self) -> None:
        """Read a saved rule set."""
        path, _filter = QFileDialog.getOpenFileName(self, "Load Symbols", "", SYMBOL_FILTER)
        if not path:
            return
        try:
            self.symbols = load_symbols(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Load Symbols", str(exc))
            return
        self.reload()

    def save(self) -> None:
        """Write the rule set out."""
        path, _filter = QFileDialog.getSaveFileName(self, "Save Symbols", "", SYMBOL_FILTER)
        if not path:
            return
        if not Path(path).suffix:
            path = f"{path}.sym"
        try:
            save_symbols(path, self.gather())
        except OSError as exc:
            QMessageBox.warning(self, "Save Symbols", str(exc))

    def apply(self) -> None:
        """Announce the rules without closing."""
        self.symbols_changed.emit(self.gather())

    def _accept(self) -> None:
        """Announce them and close."""
        self.apply()
        self.accept()


def _combo(choices, current: str) -> QComboBox:
    """A combo of `choices` with `current` selected."""
    combo = QComboBox()
    combo.addItems(list(choices))
    combo.setCurrentText(current)
    return combo
