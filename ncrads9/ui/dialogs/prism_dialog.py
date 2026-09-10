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
DS9's Prism window: a FITS file's extensions, headers and rows.

Three panes as DS9 has them (`prism.tcl:178`) -- the extension list, the
header, and the selected extension's data -- with DS9's three menus and its
six buttons under them.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from astropy.table import Table
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QGuiApplication, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...analysis.plot.dataset import Dataset
from ...analysis.plot.plot_state import PlotState, PlotStyle
from ...catalogs import catalog_file
from ...prism.browser import BLOCK, MIN_COLS, MIN_ROWS, PrismBrowser, format_value

#: How big the window opens.
WINDOW_SIZE = (900, 700)

#: What DS9's Prism reads and writes besides FITS, and by which format.
IMPORTS: tuple[tuple[str, str, catalog_file.CatalogFormat], ...] = (
    ("votable", "&VOTable", catalog_file.CatalogFormat.VOTABLE),
    ("starbase", "&Starbase", catalog_file.CatalogFormat.STARBASE),
    ("tsv", "&Tab-Separated-Value", catalog_file.CatalogFormat.TSV),
)

#: How many bins a new histogram has (`var(bar,num)`, `prism.tcl:83`).
DEFAULT_BINS = 10


class PrismDialog(QDialog):
    """Browses one file: its extensions, their headers, their rows."""

    def __init__(self, parent=None, window=None) -> None:
        """
        Args:
            parent: The widget to sit over.
            window: The main window, for `Image` to load into a frame.
                None makes that button report that there is nowhere to load.
        """
        super().__init__(parent)
        self._window = window if window is not None else parent
        #: The FITS file being browsed.
        self.browser = PrismBrowser()
        #: An imported table, when the file is not FITS. DS9 calls this its
        #: `ascii` type and turns the extension list off for it.
        self.table: Table | None = None
        self._table_name = ""
        self._last_search = ""
        self._plots: list[QDialog] = []
        self._plot_mode = "newplot"

        self.setWindowTitle("Prism")
        self.resize(*WINDOW_SIZE)
        self._build()
        self.update_state()

    # -- the window -----------------------------------------------------------

    def _build(self) -> None:
        """Lay out the three panes, the menus and the buttons."""
        layout = QVBoxLayout(self)
        layout.setMenuBar(self._menus())

        top = QSplitter(Qt.Orientation.Horizontal)

        self.extensions = QTreeWidget()
        self.extensions.setHeaderLabels(["Extension", "Type", "Dimensions"])
        self.extensions.setRootIsDecorated(False)
        self.extensions.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.extensions.currentItemChanged.connect(lambda *_: self.on_extension_changed())
        top.addWidget(self._framed("Extensions", self.extensions))

        self.header = QPlainTextEdit()
        self.header.setReadOnly(True)
        self.header.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        top.addWidget(self._framed("Header", self.header))
        top.setSizes([320, 580])

        self.data = QTableWidget(MIN_ROWS, MIN_COLS)
        self.data.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.data.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(top)
        split.addWidget(self._framed("Extension Data", self.data))
        split.setSizes([300, 400])
        layout.addWidget(split)

        self._rows_label = QLabel()
        layout.addWidget(self._rows_label)

        buttons = QHBoxLayout()
        #: Button name -> the button, so a test can press one.
        self.buttons: dict[str, QPushButton] = {}
        for name, label, slot in (
            ("open", "Open", self.open_file),
            ("clear", "Clear", self.clear),
            ("image", "Image", self.load_image),
            ("plot", "Plot", self.plot),
            ("histogram", "Histogram", self.histogram),
            ("close", "Close", self.close),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
            self.buttons[name] = button
        layout.addLayout(buttons)

    @staticmethod
    def _framed(title: str, inner: QWidget) -> QWidget:
        """One pane with DS9's label over it."""
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(2, 2, 2, 2)
        column.addWidget(QLabel(title))
        column.addWidget(inner)
        return holder

    def _menus(self) -> QMenuBar:
        """DS9's File, Edit and Table menus (`prism.tcl:106`)."""
        bar = QMenuBar(self)
        #: Action name -> the action, so a test can trigger one.
        self.actions_by_name: dict[str, QAction] = {}

        file_menu = bar.addMenu("&File")
        self._add(file_menu, "open", "&Open...", self.open_file)
        import_menu = file_menu.addMenu("&Import")
        export_menu = file_menu.addMenu("&Export")
        for name, label, chosen in IMPORTS:
            self._add(
                import_menu,
                f"import_{name}",
                label,
                lambda _checked=False, fmt=chosen: self.import_table(fmt),
            )
            self._add(
                export_menu,
                f"export_{name}",
                label,
                lambda _checked=False, fmt=chosen: self.export_table(fmt),
            )
        file_menu.addSeparator()
        self._add(file_menu, "image", "&Image", self.load_image)
        self._add(file_menu, "clear", "&Clear", self.clear)
        file_menu.addSeparator()
        self._add(file_menu, "close", "Cl&ose", self.close)

        edit_menu = bar.addMenu("&Edit")
        # Cut and Paste are disabled in DS9's Prism too: it browses a file,
        # so there is nothing to cut from and nowhere to paste to.
        for name, label, key in (("cut", "Cu&t", "Ctrl+X"), ("paste", "&Paste", "Ctrl+V")):
            action = self._add(edit_menu, name, label, None)
            action.setShortcut(QKeySequence(key))
            action.setEnabled(False)
        copy = self._add(edit_menu, "copy", "&Copy", self.copy)
        copy.setShortcut(QKeySequence("Ctrl+C"))
        edit_menu.addSeparator()
        self._add(edit_menu, "select_all", "Select &All", self.select_all)
        self._add(edit_menu, "select_none", "Select &None", self.select_none)
        edit_menu.addSeparator()
        find = self._add(edit_menu, "find", "&Find...", self.find)
        find.setShortcut(QKeySequence("Ctrl+F"))
        find_next = self._add(edit_menu, "find_next", "Find Ne&xt", self.find_next)
        find_next.setShortcut(QKeySequence("Ctrl+G"))

        table_menu = bar.addMenu("&Table")
        self._add(table_menu, "plot", "&Plot...", self.plot)
        self._add(table_menu, "histogram", "&Histogram...", self.histogram)
        table_menu.addSeparator()
        for name, label, slot in (
            ("first_block", "&First Block", self.first_block),
            ("next_block", "&Next Block", self.next_block),
            ("previous_block", "&Previous Block", self.previous_block),
            ("last_block", "&Last Block", self.last_block),
        ):
            self._add(table_menu, name, label, slot)
        table_menu.addSeparator()
        self._add(table_menu, "goto_row", "&Goto Row...", self.goto_row)
        return bar

    def _add(self, menu, name: str, label: str, slot) -> QAction:
        """One menu entry, remembered by name."""
        action = QAction(label, self)
        if slot is not None:
            action.triggered.connect(slot)
        menu.addAction(action)
        self.actions_by_name[name] = action
        return action

    # -- what is enabled ---------------------------------------------------------

    def update_state(self) -> None:
        """Enable what the loaded file supports, as DS9 does.

        A FITS image extension can be loaded into a frame but not plotted; a
        table can be plotted and paged; an imported ASCII table can be
        plotted but has no extension to load (`PrismDialogUpdate`).
        """
        is_fits = self.browser.is_open
        has_table = self.browser.is_table if is_fits else self.table is not None

        for name in ("clear", "goto_row"):
            self._enable(name, is_fits or self.table is not None)
        self._enable("image", is_fits)
        for name in ("plot", "histogram"):
            self._enable(name, has_table)
        for name in ("first_block", "next_block", "previous_block", "last_block"):
            self._enable(name, is_fits and self.browser.is_table)
        for name in ("clear", "image", "plot", "histogram"):
            if name in self.buttons:
                self.buttons[name].setEnabled(self.actions_by_name[name].isEnabled())

        self._rows_label.setText(self._describe())

    def _enable(self, name: str, enabled: bool) -> None:
        """Enable one action by name."""
        action = self.actions_by_name.get(name)
        if action is not None:
            action.setEnabled(enabled)

    def _describe(self) -> str:
        """The line under the table saying where in the file we are."""
        if self.table is not None:
            return f"{self._table_name}: {len(self.table)} rows x {len(self.table.colnames)} columns"
        if not self.browser.is_open:
            return "No file loaded."
        info = self.browser.current
        where = f"{self.browser.path.name if self.browser.path else ''} [{self.browser.index}]"
        if info is not None and not self.browser.is_table:
            return f"{where} {info.kind.value} {info.dimensions}".strip()
        rows = self.browser.rows
        start = self.browser.start
        stop = min(start + len(self.data_rows), rows)
        return f"{where} rows {start + 1}-{stop} of {rows}"

    @property
    def data_rows(self) -> list[list[str]]:
        """The rows on screen, as strings."""
        return self._rows

    # -- opening ---------------------------------------------------------------------

    def open_file(self, path: str | None = None) -> bool:
        """Open a FITS file, as the Open button and File -> Open do."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Open FITS File", "", "FITS files (*.fits *.fit *.fts *.gz);;All files (*)"
            )
        if not path:
            return False
        try:
            extensions = self.browser.open(path)
        except Exception as exc:
            QMessageBox.warning(self, "Prism", f"Unable to load FITS file:\n{exc}")
            return False

        self.table = None
        self._table_name = ""
        self.setWindowTitle(f"Prism: {Path(path).name}")
        self._fill_extensions(extensions)
        return True

    def _fill_extensions(self, extensions) -> None:
        """Put the extension list in the tree and select DS9's default one."""
        self.extensions.blockSignals(True)
        self.extensions.clear()
        for info in extensions:
            QTreeWidgetItem(self.extensions, [info.name or "-", info.kind.value, info.dimensions])
        self.extensions.blockSignals(False)

        wanted = self.browser.index
        if 0 <= wanted < self.extensions.topLevelItemCount():
            self.extensions.setCurrentItem(self.extensions.topLevelItem(wanted))
        else:
            self.show_extension()

    def on_extension_changed(self) -> None:
        """Follow a click in the extension list."""
        index = self.extensions.indexOfTopLevelItem(self.extensions.currentItem())
        if index < 0:
            return
        self.browser.select(index)
        self.show_extension()

    def show_extension(self) -> None:
        """Fill the header and the data panes from the shown extension."""
        self.header.setPlainText(self.browser.header_text())
        self.fill_table()
        self.update_state()

    def clear(self) -> None:
        """Forget the file, as DS9's Clear does."""
        self.browser.clear()
        self.table = None
        self._table_name = ""
        self.extensions.clear()
        self.header.clear()
        self.data.clear()
        self.data.setRowCount(MIN_ROWS)
        self.data.setColumnCount(MIN_COLS)
        self._rows = []
        self.setWindowTitle("Prism")
        self.update_state()

    # -- the data pane -----------------------------------------------------------------

    def fill_table(self) -> None:
        """Put the block of rows on screen."""
        if self.table is not None:
            names = list(self.table.colnames)
            # The same formatter as the FITS path, so an integer read from a
            # text file does not turn into "1.0" on the way to the cell.
            rows = [[format_value(value) for value in row] for row in self.table[:BLOCK]]
        else:
            names, rows = self.browser.block()
        self._rows = rows

        self.data.clear()
        self.data.setColumnCount(max(len(names), MIN_COLS))
        self.data.setRowCount(max(len(rows), MIN_ROWS))
        self.data.setHorizontalHeaderLabels(names + [""] * (self.data.columnCount() - len(names)))

        offset = self.browser.start if self.table is None else 0
        self.data.setVerticalHeaderLabels(
            [str(offset + number + 1) for number in range(self.data.rowCount())]
        )
        for row_number, row in enumerate(rows):
            for column_number, value in enumerate(row):
                self.data.setItem(row_number, column_number, QTableWidgetItem(value))
        self._rows_label.setText(self._describe())

    # -- paging --------------------------------------------------------------------------

    def first_block(self) -> None:
        """Show the first block of rows."""
        self.browser.first_block()
        self.fill_table()

    def next_block(self) -> None:
        """Show the next block."""
        self.browser.next_block()
        self.fill_table()

    def previous_block(self) -> None:
        """Show the previous block."""
        self.browser.previous_block()
        self.fill_table()

    def last_block(self) -> None:
        """Show the last block."""
        self.browser.last_block()
        self.fill_table()

    def goto_row(self, row: int | None = None) -> None:
        """Show the block one row is in, and select that row."""
        rows = len(self.table) if self.table is not None else self.browser.rows
        if rows <= 0:
            return
        if row is None:
            row, ok = QInputDialog.getInt(self, "Goto Row", "Row:", 1, 1, rows)
            if not ok:
                return
        if self.table is not None:
            offset = max(1, min(int(row), rows)) - 1
        else:
            offset = self.browser.goto_row(int(row))
            self.fill_table()
        self.data.setCurrentCell(offset, 0)
        self.data.scrollToItem(self.data.item(offset, 0))

    # -- the Edit menu ---------------------------------------------------------------------

    def copy(self) -> str:
        """Copy whichever pane has focus, as DS9's Prism does.

        Returns:
            What was copied, so a test need not read the clipboard.
        """
        if self.header.hasFocus():
            text = self.header.textCursor().selectedText() or self.header.toPlainText()
        else:
            selected = self.data.selectedItems()
            text = "\n".join(item.text() for item in selected)
        QGuiApplication.clipboard().setText(text)
        return text

    def select_all(self) -> None:
        """Select the whole header, which is DS9's text pane here."""
        self.header.selectAll()

    def select_none(self) -> None:
        """Select nothing."""
        cursor = self.header.textCursor()
        cursor.clearSelection()
        self.header.setTextCursor(cursor)
        self.data.clearSelection()

    def find(self, text: str | None = None) -> bool:
        """Search the header, as DS9 binds Find to its text pane."""
        if text is None:
            text, ok = QInputDialog.getText(self, "Find", "Find:", text=self._last_search)
            if not ok or not text:
                return False
        self._last_search = text
        cursor = self.header.textCursor()
        cursor.setPosition(0)
        self.header.setTextCursor(cursor)
        return self.header.find(text)

    def find_next(self) -> bool:
        """Find the next occurrence of the last search."""
        if not self._last_search:
            return self.find()
        return self.header.find(self._last_search)

    # -- Import and Export -------------------------------------------------------------------

    def import_table(
        self,
        chosen: catalog_file.CatalogFormat,
        path: str | None = None,
    ) -> bool:
        """Read a table that is not FITS, DS9's `ascii` type."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, f"Import {chosen.value}", "", catalog_file.FILE_FILTER
            )
        if not path:
            return False
        try:
            table = catalog_file.load(path, chosen)
        except Exception as exc:
            QMessageBox.warning(self, "Prism", f"Unable to import:\n{exc}")
            return False

        self.browser.clear()
        self.extensions.clear()
        self.table = table
        self._table_name = Path(path).name
        self.header.setPlainText("\n".join(f"{name}" for name in table.colnames))
        self.setWindowTitle(f"Prism: {self._table_name}")
        self.fill_table()
        self.update_state()
        return True

    def export_table(
        self,
        chosen: catalog_file.CatalogFormat,
        path: str | None = None,
    ) -> bool:
        """Write the loaded table out in one of DS9's three formats."""
        table = self._as_table()
        if table is None:
            QMessageBox.warning(self, "Prism", "There is no table to export.")
            return False
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, f"Export {chosen.value}", "", catalog_file.FILE_FILTER
            )
        if not path:
            return False
        try:
            catalog_file.save(path, table, chosen)
        except Exception as exc:
            QMessageBox.warning(self, "Prism", f"Unable to export:\n{exc}")
            return False
        return True

    def _as_table(self) -> Table | None:
        """The loaded rows as a table, whichever kind of file they came from."""
        if self.table is not None:
            return self.table
        if not self.browser.is_table:
            return None
        columns = {}
        for name in self.browser.columns:
            try:
                columns[name] = self.browser.column(name)
            except (KeyError, TypeError, ValueError):
                continue
        return Table(columns) if columns else None

    # -- Image, Plot and Histogram --------------------------------------------------------

    def load_image(self) -> bool:
        """Load the shown extension into a new frame, as DS9's Image does."""
        if not self.browser.is_open or self.browser.path is None:
            QMessageBox.warning(self, "Prism", "No file loaded.")
            return False
        window = self._window
        if window is None or not hasattr(window, "display"):
            return False
        window.frame_controller.new_frame()
        window.display.load_fits(f"{self.browser.path}[{self.browser.index}]")
        return True

    def _numeric_columns(self) -> list[str]:
        """The columns worth plotting: the ones that are numbers."""
        table = self._as_table()
        if table is None:
            return []
        return [name for name in table.colnames if np.issubdtype(table[name].dtype, np.number)]

    def plot(
        self,
        x_name: str | None = None,
        y_name: str | None = None,
        x_error: str | None = None,
        y_error: str | None = None,
    ) -> QDialog | None:
        """Plot one column against another, as DS9's Plot does.

        Args:
            x_name: The column along the bottom, or None to ask.
            y_name: The column up the side, or None to ask.
            x_error: A column of x error bars, as XPA's `xyex` asks for.
            y_error: A column of y error bars.

        Returns:
            The plot window, or None if there was nothing to plot.
        """
        names = self._numeric_columns()
        if len(names) < 2:
            QMessageBox.warning(self, "Prism", "Plotting needs two numeric columns.")
            return None
        if x_name is None or y_name is None:
            chosen = ColumnChooser(names, self, histogram=False).choose()
            if chosen is None:
                return None
            x_name, y_name = chosen["x"], chosen["y"]

        table = self._as_table()
        if table is None:
            return None
        if x_name not in table.colnames or y_name not in table.colnames:
            QMessageBox.warning(self, "Prism", "No such column.")
            return None

        dataset = Dataset(
            name=f"{y_name} vs {x_name}",
            x=[float(value) for value in table[x_name]],
            y=[float(value) for value in table[y_name]],
        )
        for column, attribute in ((x_error, "x_error"), (y_error, "y_error")):
            if column and column in table.colnames:
                setattr(dataset, attribute, [float(value) for value in table[column]])

        state = PlotState(title=f"{y_name} vs {x_name}")
        state.x_axis.title = x_name
        state.y_axis.title = y_name
        state.add(dataset)
        return self._open_plot(state)

    def histogram(
        self,
        name: str | None = None,
        bins: int | None = None,
        low: float | None = None,
        high: float | None = None,
    ) -> QDialog | None:
        """Histogram one column, as DS9's Histogram does.

        Args:
            name: The column, or None to ask.
            bins: How many bins.
            low: The lowest value counted, or None for the column's own
                minimum -- DS9's `bar,minmax`.
            high: The highest.

        Returns:
            The plot window, or None if there was nothing to plot.
        """
        names = self._numeric_columns()
        if not names:
            QMessageBox.warning(self, "Prism", "A histogram needs a numeric column.")
            return None
        if name is None:
            chosen = ColumnChooser(names, self, histogram=True).choose()
            if chosen is None:
                return None
            name, bins = chosen["x"], chosen["bins"]

        table = self._as_table()
        if table is None:
            return None
        if name not in table.colnames:
            QMessageBox.warning(self, "Prism", "No such column.")
            return None
        values = np.asarray(table[name], dtype=np.float64)
        values = values[np.isfinite(values)]
        if values.size == 0:
            QMessageBox.warning(self, "Prism", f"{name} has no finite values.")
            return None

        limits = None if low is None or high is None else (float(low), float(high))
        counts, edges = np.histogram(values, bins=max(1, int(bins or DEFAULT_BINS)), range=limits)
        centres = (edges[:-1] + edges[1:]) / 2.0
        state = PlotState(title=f"{name} histogram", style=PlotStyle.BAR)
        state.x_axis.title = name
        state.y_axis.title = "Count"
        state.add(
            Dataset(
                name=name,
                x=[float(value) for value in centres],
                y=[float(value) for value in counts],
            )
        )
        return self._open_plot(state)

    def _open_plot(self, state: PlotState) -> QDialog:
        """Show a plot, keeping a reference so it is not collected.

        DS9's plot mode decides whether that is a new window or another
        curve on the one already open (`prism mode overplot`).
        """
        from .plot_window import PlotWindow

        if self.plot_mode == "overplot" and self._plots:
            plot = self._plots[-1]
            for dataset in state.datasets:
                plot.add_dataset(dataset)
            plot.raise_()
            return plot

        plot = PlotWindow(state, self)
        self._plots.append(plot)
        plot.show()
        return plot

    @property
    def plot_mode(self) -> str:
        """Whether a plot opens a window or joins the last one.

        DS9 keeps this per Prism window and offers `newplot`, `newgraph`
        and `overplot`; ours has one plot window per graph, so `newgraph`
        and `newplot` are the same thing.
        """
        return self._plot_mode

    @plot_mode.setter
    def plot_mode(self, mode: str) -> None:
        """Set the plot mode."""
        self._plot_mode = mode if mode in ("newplot", "newgraph", "overplot") else "newplot"

    def select_extension(self, which: int | str) -> bool:
        """Show one extension by index or by `EXTNAME`, as XPA's `ext` does.

        Returns:
            Whether there was such an extension.
        """
        index: int | None = None
        if isinstance(which, int) or str(which).lstrip("-").isdigit():
            index = int(which)
        else:
            wanted = str(which).strip().upper()
            for info in self.browser.extensions:
                if (info.name or "").upper() == wanted:
                    index = info.index
                    break
        if index is None or not 0 <= index < self.extensions.topLevelItemCount():
            return False
        self.extensions.setCurrentItem(self.extensions.topLevelItem(index))
        return True


class ColumnChooser(QDialog):
    """Which columns to plot, and how many bins to put them in."""

    def __init__(self, names: list[str], parent=None, histogram: bool = False) -> None:
        """
        Args:
            names: The columns worth plotting.
            parent: The Prism window.
            histogram: Whether to ask for bins rather than a second column.
        """
        super().__init__(parent)
        self.setWindowTitle("Histogram" if histogram else "Plot")
        self._histogram = histogram

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._x = QComboBox()
        self._x.addItems(names)
        form.addRow("Column:" if histogram else "X:", self._x)

        self._y = QComboBox()
        self._y.addItems(names)
        if len(names) > 1:
            self._y.setCurrentIndex(1)
        if not histogram:
            form.addRow("Y:", self._y)

        self._bins = QSpinBox()
        self._bins.setRange(1, 1000)
        self._bins.setValue(DEFAULT_BINS)
        if histogram:
            form.addRow("Bins:", self._bins)

        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose(self) -> dict | None:
        """Ask, and say what was chosen, or None if it was cancelled."""
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        return {
            "x": self._x.currentText(),
            "y": self._y.currentText(),
            "bins": self._bins.value(),
        }
