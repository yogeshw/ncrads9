# This file is part of ncrads9.
#
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
Catalog table widget for displaying query results.

Author: Yogesh Wadadekar
"""

from typing import Optional, List, Any, Callable, Dict
from dataclasses import dataclass

from astropy.table import Table
from astropy.coordinates import SkyCoord
import astropy.units as u

try:
    from PyQt6.QtWidgets import (
        QTableWidget,
        QTableWidgetItem,
        QHeaderView,
        QAbstractItemView,
        QMenu,
        QAction,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QPushButton,
        QLabel,
        QLineEdit,
        QComboBox,
    )
    from PyQt6.QtCore import Qt, pyqtSignal

    HAS_QT = True
except ImportError:
    HAS_QT = False
    QWidget = object  # type: ignore
    pyqtSignal = None  # type: ignore


@dataclass
class ColumnConfig:
    """Configuration for a table column."""

    name: str
    display_name: Optional[str] = None
    width: int = 100
    visible: bool = True
    format_func: Optional[Callable[[Any], str]] = None


class CatalogTable(QWidget if HAS_QT else object):
    """Widget for displaying catalog query results in a table."""

    if HAS_QT:
        row_selected = pyqtSignal(int)
        row_double_clicked = pyqtSignal(int)
        coord_selected = pyqtSignal(object)

    def __init__(
        self,
        parent: Optional[Any] = None,
        table: Optional[Table] = None,
    ) -> None:
        """
        Initialize catalog table widget.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget.
        table : Table, optional
            Astropy table to display.
        """
        if not HAS_QT:
            raise ImportError("PyQt6 is required for CatalogTable widget")

        super().__init__(parent)

        self._table: Optional[Table] = None
        self._column_configs: Dict[str, ColumnConfig] = {}
        self._selected_row: int = -1
        self._sort_column: int = -1
        self._sort_order: Qt.SortOrder = Qt.AscendingOrder

        self._setup_ui()

        if table is not None:
            self.set_table(table)

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()

        self._filter_label = QLabel("Filter:")
        toolbar.addWidget(self._filter_label)

        self._filter_column = QComboBox()
        toolbar.addWidget(self._filter_column)

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Enter filter value...")
        self._filter_input.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._filter_input)

        self._clear_filter_btn = QPushButton("Clear")
        self._clear_filter_btn.clicked.connect(self._clear_filter)
        toolbar.addWidget(self._clear_filter_btn)

        toolbar.addStretch()

        self._row_count_label = QLabel("0 rows")
        toolbar.addWidget(self._row_count_label)

        layout.addLayout(toolbar)

        # Table widget
        self._table_widget = QTableWidget()
        self._table_widget.setAlternatingRowColors(True)
        self._table_widget.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        self._table_widget.setSelectionMode(
            QAbstractItemView.SingleSelection
        )
        self._table_widget.setSortingEnabled(True)
        self._table_widget.setContextMenuPolicy(Qt.CustomContextMenu)

        self._table_widget.itemSelectionChanged.connect(
            self._on_selection_changed
        )
        self._table_widget.itemDoubleClicked.connect(
            self._on_double_click
        )
        self._table_widget.customContextMenuRequested.connect(
            self._show_context_menu
        )

        layout.addWidget(self._table_widget)

    def set_table(self, table: Table) -> None:
        """
        Set the table data to display.

        Parameters
        ----------
        table : Table
            Astropy table to display.
        """
        self._table = table
        self._populate_table()
        self._update_filter_columns()
        self._update_row_count()

    def _populate_table(self) -> None:
        """Populate the table widget with data."""
        if self._table is None:
            return

        self._table_widget.clear()
        self._table_widget.setSortingEnabled(False)

        # Set up columns
        columns = self._table.colnames
        self._table_widget.setColumnCount(len(columns))
        self._table_widget.setHorizontalHeaderLabels(columns)

        # Set up rows
        self._table_widget.setRowCount(len(self._table))

        for row_idx, row in enumerate(self._table):
            for col_idx, col_name in enumerate(columns):
                value = row[col_name]
                display_value = self._format_value(col_name, value)
                item = QTableWidgetItem(display_value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self._table_widget.setItem(row_idx, col_idx, item)

        self._table_widget.setSortingEnabled(True)
        self._table_widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )

    def _format_value(self, column: str, value: Any) -> str:
        """Format a cell value for display."""
        if column in self._column_configs:
            config = self._column_configs[column]
            if config.format_func:
                return config.format_func(value)

        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    def _update_filter_columns(self) -> None:
        """Update the filter column dropdown."""
        self._filter_column.clear()
        if self._table is not None:
            self._filter_column.addItems(self._table.colnames)

    def _apply_filter(self, text: str) -> None:
        """Apply filter to table rows."""
        if not text:
            self._show_all_rows()
            return

        column = self._filter_column.currentText()
        col_idx = self._filter_column.currentIndex()

        for row in range(self._table_widget.rowCount()):
            item = self._table_widget.item(row, col_idx)
            if item is None:
                continue
            match = text.lower() in item.text().lower()
            self._table_widget.setRowHidden(row, not match)

        self._update_row_count()

    def _clear_filter(self) -> None:
        """Clear the filter."""
        self._filter_input.clear()
        self._show_all_rows()

    def _show_all_rows(self) -> None:
        """Show all rows."""
        for row in range(self._table_widget.rowCount()):
            self._table_widget.setRowHidden(row, False)
        self._update_row_count()

    def _update_row_count(self) -> None:
        """Update the row count label."""
        total = self._table_widget.rowCount()
        visible = sum(
            1
            for row in range(total)
            if not self._table_widget.isRowHidden(row)
        )
        if visible == total:
            self._row_count_label.setText(f"{total} rows")
        else:
            self._row_count_label.setText(f"{visible}/{total} rows")

    def _on_selection_changed(self) -> None:
        """Handle row selection change."""
        selected = self._table_widget.selectedItems()
        if selected:
            row = selected[0].row()
            self._selected_row = row
            self.row_selected.emit(row)

            coord = self._get_row_coordinate(row)
            if coord is not None:
                self.coord_selected.emit(coord)

    def _on_double_click(self, item: QTableWidgetItem) -> None:
        """Handle row double-click."""
        self.row_double_clicked.emit(item.row())

    def _show_context_menu(self, pos: Any) -> None:
        """Show context menu."""
        menu = QMenu(self)

        copy_action = QAction("Copy Cell", self)
        copy_action.triggered.connect(self._copy_cell)
        menu.addAction(copy_action)

        copy_row_action = QAction("Copy Row", self)
        copy_row_action.triggered.connect(self._copy_row)
        menu.addAction(copy_row_action)

        menu.addSeparator()

        goto_action = QAction("Go to Position", self)
        goto_action.triggered.connect(self._goto_position)
        menu.addAction(goto_action)

        menu.exec_(self._table_widget.mapToGlobal(pos))

    def _copy_cell(self) -> None:
        """Copy selected cell to clipboard."""
        selected = self._table_widget.selectedItems()
        if selected:
            from PyQt6.QtWidgets import QApplication

            QApplication.clipboard().setText(selected[0].text())

    def _copy_row(self) -> None:
        """Copy selected row to clipboard."""
        if self._selected_row < 0:
            return

        values = []
        for col in range(self._table_widget.columnCount()):
            item = self._table_widget.item(self._selected_row, col)
            if item:
                values.append(item.text())

        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText("\t".join(values))

    def _goto_position(self) -> None:
        """Emit signal to go to selected row's position."""
        if self._selected_row >= 0:
            coord = self._get_row_coordinate(self._selected_row)
            if coord is not None:
                self.coord_selected.emit(coord)

    def _get_row_coordinate(self, row: int) -> Optional[SkyCoord]:
        """Get coordinate for a table row."""
        if self._table is None:
            return None

        ra_col: Optional[str] = None
        dec_col: Optional[str] = None

        for col in self._table.colnames:
            col_lower = col.lower()
            if col_lower in ("ra", "_ra", "raj2000", "ra_icrs"):
                ra_col = col
            elif col_lower in ("dec", "_dec", "dej2000", "de", "dec_icrs"):
                dec_col = col

        if ra_col is None or dec_col is None:
            return None

        try:
            ra = float(self._table[row][ra_col])
            dec = float(self._table[row][dec_col])
            return SkyCoord(ra=ra, dec=dec, unit=(u.deg, u.deg), frame="icrs")
        except Exception:
            return None

    def get_selected_row(self) -> int:
        """Return the currently selected row index."""
        return self._selected_row

    def get_selected_data(self) -> Optional[Dict[str, Any]]:
        """Return data from the selected row as a dictionary."""
        if self._table is None or self._selected_row < 0:
            return None

        return {
            col: self._table[self._selected_row][col]
            for col in self._table.colnames
        }

    def set_column_config(self, column: str, config: ColumnConfig) -> None:
        """Set configuration for a column."""
        self._column_configs[column] = config

    def get_table(self) -> Optional[Table]:
        """Return the underlying astropy Table."""
        return self._table

    def clear(self) -> None:
        """Clear the table display."""
        self._table = None
        self._table_widget.clear()
        self._table_widget.setRowCount(0)
        self._table_widget.setColumnCount(0)
        self._filter_column.clear()
        self._row_count_label.setText("0 rows")
