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
DS9's catalog list window.

"Along with the overlay display, a catalog list is provided in a separate
window. It displays the column values for each catalog object. The catalog
list can be sorted and filtered, and the catalog display will be
automatically updated" (`ds9/doc/ref/catalog.html`).

The two-way selection is the part worth stating: selecting rows here
highlights the symbols on the image, and clicking a symbol highlights the
row here. Both directions go through `selection_changed`, and the guard
against the two chasing each other is `_syncing` -- without it, setting the
selection to answer a symbol click emits a change, which moves the symbols,
which... which is why it is there.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...catalogs.catalog_set import LoadedCatalog

#: How big the window opens.
WINDOW_SIZE = (860, 520)

#: How many rows are put in the table at most. A million-row catalogue in a
#: QTableWidget is minutes of widget construction; the filter is the way to
#: narrow it, and the count label says what is not shown.
MAX_DISPLAYED_ROWS = 20000


class CatalogWindow(QDialog):
    """One catalogue's rows, sortable, filterable, and linked to the image.

    Args:
        catalog: The catalogue to show. Held, not copied, so the filter and
            the selection set here are the ones the overlay reads.
        parent: Optional parent widget.
    """

    #: Emitted when the rows selected here change, with the row indices.
    selection_changed = pyqtSignal(object)
    #: Emitted when the filter changes and the overlay should be redrawn.
    filter_changed = pyqtSignal(str)
    #: Emitted when the user asks for one of the window's commands.
    command_requested = pyqtSignal(str)

    def __init__(self, catalog: LoadedCatalog, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.setWindowTitle(f"Catalog: {catalog.name}")
        self.resize(*WINDOW_SIZE)

        #: True while a selection is being set programmatically, so the two
        #: directions of the sync cannot chase each other.
        self._syncing = False
        #: Table row -> catalogue row, since the table shows the filtered
        #: rows and may be sorted.
        self._rows: list[int] = []

        layout = QVBoxLayout(self)
        layout.setMenuBar(self._menus())

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._filter = QLineEdit(catalog.filter_expression)
        self._filter.setPlaceholderText("$Jmag>11 && $_RAJ2000>180")
        self._filter.returnPressed.connect(self.apply_filter)
        filter_row.addWidget(self._filter)
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self.apply_filter)
        filter_row.addWidget(apply_button)
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_filter)
        filter_row.addWidget(clear_button)
        layout.addLayout(filter_row)

        self._table = QTableWidget()
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.itemDoubleClicked.connect(lambda _item: self.pan_to_row())
        layout.addWidget(self._table)

        self._count = QLabel()
        layout.addWidget(self._count)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.reload()

    # -- menus -----------------------------------------------------------------

    def _menus(self) -> QMenuBar:
        """The window's own commands, as DS9's catalog window has them."""
        bar = QMenuBar(self)
        #: Command name -> its action, so a test can trigger one.
        self.actions_by_name = {}

        file_menu = bar.addMenu("&File")
        for name, label in (
            ("save", "&Save Catalog..."),
            ("header", "&Header"),
            ("print", "&Print..."),
            ("plot", "P&lot..."),
            ("regions", "Copy to &Regions"),
            ("clear", "&Clear Catalog"),
        ):
            action = file_menu.addAction(label)
            action.triggered.connect(lambda _checked=False, key=name: self._request(key))
            self.actions_by_name[name] = action

        edit_menu = bar.addMenu("&Edit")
        for name, label in (("select_all", "Select &All"), ("select_none", "Select &None")):
            action = edit_menu.addAction(label)
            action.triggered.connect(lambda _checked=False, key=name: self._request(key))
            self.actions_by_name[name] = action

        symbol_menu = bar.addMenu("&Symbol")
        action = symbol_menu.addAction("&Edit Symbols...")
        action.triggered.connect(lambda _checked=False: self._request("symbols"))
        self.actions_by_name["symbols"] = action

        return bar

    def _request(self, name: str) -> None:
        """Handle a command, either here or by asking the controller."""
        if name == "select_all":
            self.select_rows(self.catalog.rows())
            return
        if name == "select_none":
            self.select_rows([])
            return
        if name == "header":
            self.show_header()
            return
        if name == "print":
            self.print_list()
            return
        self.command_requested.emit(name)

    # -- the table -------------------------------------------------------------

    def reload(self) -> None:
        """Rebuild the table from the catalogue and its filter."""
        rows = self.catalog.rows()
        shown = rows[:MAX_DISPLAYED_ROWS]
        self._rows = shown
        columns = self.catalog.columns

        # Sorting must be off while filling, or every insertion re-sorts and
        # the rows end up in an order the row map no longer describes.
        self._table.setSortingEnabled(False)
        self._table.clear()
        self._table.setColumnCount(len(columns))
        self._table.setRowCount(len(shown))
        self._table.setHorizontalHeaderLabels(columns)

        table = self.catalog.table
        for position, row in enumerate(shown):
            for column, name in enumerate(columns):
                item = _cell(table[name][row])
                # The catalogue row travels with the cell, so a sort does
                # not break the link back to the data.
                item.setData(Qt.ItemDataRole.UserRole, int(row))
                self._table.setItem(position, column, item)
        self._table.setSortingEnabled(True)
        self._table.resizeColumnsToContents()

        self._update_count(len(rows), len(shown))
        self.sync_selection()

    def _update_count(self, total: int, shown: int) -> None:
        """Say how many rows there are, and how many are not shown."""
        whole = len(self.catalog.table)
        parts = [f"{total} of {whole} rows"]
        if shown < total:
            parts.append(f"showing the first {shown}")
        if self.catalog.filter_error:
            parts.append(f"filter ignored: {self.catalog.filter_error}")
        self._count.setText("    ".join(parts))

    def _table_row_for(self, catalog_row: int) -> int | None:
        """Which table row shows a catalogue row, after any sort."""
        for position in range(self._table.rowCount()):
            item = self._table.item(position, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == catalog_row:
                return position
        return None

    # -- the row under the cursor ---------------------------------------------

    def _current_row(self) -> int | None:
        """The catalogue row the cursor is on, or None."""
        item = self._table.currentItem()
        if item is None:
            return None
        row = self._table.item(item.row(), 0)
        return None if row is None else int(row.data(Qt.ItemDataRole.UserRole))

    def _show_context_menu(self, position) -> None:
        """Copy a cell or a row, or pan the image to the row's position.

        Carried over from `catalogs/catalog_table.py`, a table widget this
        window replaced; these three were the parts of it worth keeping.
        """
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.addAction("Copy Cell").triggered.connect(self.copy_cell)
        menu.addAction("Copy Row").triggered.connect(self.copy_row)
        menu.addSeparator()
        menu.addAction("Pan to Position").triggered.connect(self.pan_to_row)
        menu.exec(self._table.viewport().mapToGlobal(position))

    def copy_cell(self) -> None:
        """Put the cell under the cursor on the clipboard."""
        from PyQt6.QtGui import QGuiApplication

        item = self._table.currentItem()
        if item is not None:
            QGuiApplication.clipboard().setText(item.text())

    def copy_row(self) -> None:
        """Put the whole row on the clipboard, tab-separated."""
        from PyQt6.QtGui import QGuiApplication

        row = self._current_row()
        if row is None:
            return
        table = self.catalog.table
        QGuiApplication.clipboard().setText(
            "\t".join(_text(table[name][row]) for name in self.catalog.columns)
        )

    def pan_to_row(self) -> None:
        """Ask for the image to be centred on this row's position."""
        row = self._current_row()
        if row is None:
            return
        self.select_rows([row])
        self.command_requested.emit(f"pan:{row}")

    # -- selection (M8-2) --------------------------------------------------------

    def _on_selection_changed(self) -> None:
        """The user changed the selection here; tell the overlay."""
        if self._syncing:
            return
        rows = {
            item.data(Qt.ItemDataRole.UserRole) for item in self._table.selectedItems() if item.column() == 0
        }
        self.catalog.select(rows)
        self.selection_changed.emit(sorted(self.catalog.selected))

    def select_rows(self, rows) -> None:
        """Set the selection from catalogue row indices, and announce it."""
        self.catalog.select(rows)
        self.sync_selection()
        self.selection_changed.emit(sorted(self.catalog.selected))

    def sync_selection(self) -> None:
        """Make the table's highlight match the catalogue's selection.

        Announces nothing: this is the answering half of the sync, and
        emitting here is what makes the two directions chase each other.
        """
        self._syncing = True
        try:
            self._table.clearSelection()
            for row in self.catalog.selected:
                position = self._table_row_for(row)
                if position is not None:
                    self._table.selectRow(position)
        finally:
            self._syncing = False

    # -- filtering (M8-4) ---------------------------------------------------------

    def apply_filter(self) -> None:
        """Apply the filter as typed, and redraw."""
        self.catalog.filter_expression = self._filter.text().strip()
        self.reload()
        self.filter_changed.emit(self.catalog.filter_expression)
        if self.catalog.filter_error:
            # Said in the count line as well, but a filter that silently
            # did nothing is the complaint this avoids.
            QMessageBox.information(self, "Filter", self.catalog.filter_error)

    def clear_filter(self) -> None:
        """Show every row again."""
        self._filter.clear()
        self.catalog.filter_expression = ""
        self.reload()
        self.filter_changed.emit("")

    # -- the window's own commands -------------------------------------------------

    def show_header(self) -> None:
        """Show the catalogue's header, as DS9's Header view does."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Header: {self.catalog.name}")
        dialog.resize(520, 400)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit(self.catalog.header())
        view.setReadOnly(True)
        view.setFont(QFont("monospace"))
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def print_list(self) -> None:
        """Print the list, separately from the image as DS9 does."""
        from PyQt6.QtGui import QPainter, QTextDocument
        from PyQt6.QtPrintSupport import QPrintDialog, QPrinter

        printer = QPrinter()
        if not QPrintDialog(printer, self).exec():
            return
        document = QTextDocument()
        document.setDefaultFont(QFont("monospace", 8))
        document.setPlainText(self.as_text())
        painter = QPainter()
        if painter.begin(printer):
            try:
                document.drawContents(painter)
            finally:
                painter.end()

    def as_text(self) -> str:
        """The visible rows as plain text, for printing."""
        columns = self.catalog.columns
        lines = ["\t".join(columns)]
        table = self.catalog.table
        for row in self._rows:
            lines.append("\t".join(_text(table[name][row]) for name in columns))
        return "\n".join(lines)


def _text(value) -> str:
    """One cell as text."""
    if value is None or value is np.ma.masked:
        return ""
    if isinstance(value, (float, np.floating)):
        return "" if np.isnan(value) else f"{value:g}"
    return str(value)


class _NumericItem(QTableWidgetItem):
    """A cell that sorts by its number rather than by its text.

    `QTableWidgetItem` compares its display text, so a magnitude column
    sorts 10 before 9. Setting `EditRole` to a float does not help: Qt
    aliases EditRole to DisplayRole inside the item, so the number replaces
    the formatted text and the comparison is still textual. Comparing here
    is the way that works.
    """

    def __init__(self, text: str, value: float) -> None:
        super().__init__(text)
        self.value = float(value)
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other) -> bool:
        if isinstance(other, _NumericItem):
            return self.value < other.value
        return super().__lt__(other)


def _cell(value) -> QTableWidgetItem:
    """One table cell, sorting numerically where the value is a number."""
    text = _text(value)
    numeric = isinstance(value, (float, np.floating, int, np.integer)) and not (
        isinstance(value, (float, np.floating)) and np.isnan(value)
    )
    return _NumericItem(text, float(value)) if numeric else QTableWidgetItem(text)
