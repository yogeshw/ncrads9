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
The Bin menu: turning a FITS table into an image.

DS9's Bin applies to a table, not to an image. A change to any of its
settings -- the function, the bin factor, the buffer size, the columns or the
filter -- means re-binning the table the frame was loaded from and replacing
the image on screen, which is why this controller reads the frame's own
`fits_handler` rather than its pixels.

The menu belonged to the Analysis controller before M5, where it
block-averaged the displayed image: the same operation as Block under a
different name, and wrong for both (PLAN.md §3.4). Block stayed on Analysis
and this is the real Bin.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenuBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ...core.bin_table import (
    BIN_FACTORS,
    BUFFER_SIZES,
    BinFunction,
    BinSettings,
    BinTableError,
    bin_table,
    column_extent,
    column_names,
)
from ...core.file_spec import BinSpec
from ...core.fits_handler import HDUKind, classify
from ...core.wcs_handler import WCSHandler
from .base import Controller

#: The largest depth the parameters dialog offers along a third column.
MAX_DEPTH = 4096


class BinController(Controller):
    """Owns the Bin menu."""

    def connect(self) -> None:
        """Wire the Bin menu."""
        menu = self.menu

        for name, action in menu.bin_function_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.set_function(key))

        menu.action_bin_in.triggered.connect(self.bin_in)
        menu.action_bin_out.triggered.connect(self.bin_out)
        menu.action_bin_fit.triggered.connect(self.bin_fit)

        for factor, action in menu.bin_factor_actions.items():
            action.triggered.connect(lambda _checked=False, value=factor: self.set_factor(value))
        for size, action in menu.bin_buffer_actions.items():
            action.triggered.connect(lambda _checked=False, value=size: self.set_buffer_size(value))

        menu.action_bin_params.triggered.connect(self.show_dialog)

    def sync(self) -> None:
        """Tick every Bin entry to match the current settings."""
        settings = self.settings
        for name, action in self.menu.bin_function_actions.items():
            action.setChecked(settings.function.value == name)
        for factor, action in self.menu.bin_factor_actions.items():
            action.setChecked(settings.factors == (float(factor), float(factor)))
        for size, action in self.menu.bin_buffer_actions.items():
            action.setChecked(size == settings.buffer_size)

    # -- settings ------------------------------------------------------------

    @property
    def settings(self) -> BinSettings:
        """The window's bin settings."""
        return self.window.bin_settings

    @property
    def columns(self) -> BinSpec:
        """Which columns to bin on."""
        return self.window.bin_spec

    def update(self, **changes) -> None:
        """Replace one or more settings and re-bin."""
        self.window.bin_settings = replace(self.window.bin_settings, **changes)
        self.sync()
        self.rebin()

    def set_function(self, function: str) -> None:
        """Sum the rows in a bin, or average them.

        Args:
            function: "sum" or "average".
        """
        try:
            value = BinFunction(function)
        except ValueError:
            self.status(f"Unknown bin function: {function}", 3000)
            return
        self.update(function=value)
        self.status(f"Bin function: {value.value}")

    def set_factor(self, factor: float) -> None:
        """Set how many column units go into one image pixel."""
        try:
            settings = self.settings.with_factor(factor)
        except BinTableError as exc:
            self.status(str(exc), 3000)
            return
        self.window.bin_settings = settings
        self.sync()
        self.rebin()
        self.status(f"Bin factor: {settings.factor:g}")

    def set_factors(self, x: float, y: float) -> str | None:
        """Bin x and y by different factors, DS9's `bin factor 4 2`."""
        try:
            settings = self.settings.with_factors(x, y)
        except BinTableError as exc:
            self.status(str(exc), 3000)
            return str(exc)
        self.window.bin_settings = settings
        self.sync()
        self.rebin()
        self.status(f"Bin factor: {x:g} x {y:g}")
        return None

    def set_buffer_size(self, size: int) -> None:
        """Cap the binned image's dimensions."""
        if size not in BUFFER_SIZES:
            self.status(f"Buffer size must be one of {', '.join(map(str, BUFFER_SIZES))}", 3000)
            return
        self.update(buffer_size=int(size))
        self.status(f"Bin buffer: {size}x{size}")

    def bin_in(self) -> None:
        """Halve the bin factor: finer bins, a bigger image."""
        self.set_factor(self._step(-1))

    def bin_out(self) -> None:
        """Double the bin factor: coarser bins, a smaller image."""
        self.set_factor(self._step(1))

    def _step(self, direction: int) -> float:
        """The preset one step from the current factor."""
        current = self.settings.factor
        nearest = min(BIN_FACTORS, key=lambda value: abs(value - current))
        index = BIN_FACTORS.index(nearest) + direction
        return float(BIN_FACTORS[max(0, min(len(BIN_FACTORS) - 1, index))])

    def bin_fit(self) -> None:
        """Choose the finest factor whose image fits the viewport."""
        table = self.table_hdu()
        if table is None:
            self.status("The current frame is not a binned table", 3000)
            return

        from ...core.bin_table import bin_edges, column_extent

        viewport = self.window._effective_viewport_size()
        wanted = max(1, min(viewport.width(), viewport.height()))
        extents = [column_extent(table, name) for name in self.columns.columns[:2]]
        widest = max(high - low + 1.0 for low, high in extents)

        for factor in BIN_FACTORS:
            probe = replace(self.settings, factor=float(factor))
            if len(bin_edges((0.0, widest - 1.0), probe)) - 1 <= wanted:
                self.set_factor(factor)
                return
        self.set_factor(BIN_FACTORS[-1])

    # -- re-binning ----------------------------------------------------------

    def table_hdu(self):
        """The table the current frame was binned from, or None.

        Returns None for an ordinary image frame, which is what makes every
        Bin entry a no-op there rather than an error.
        """
        frame = self.frame
        if frame is None or frame.fits_handler is None or frame.hdu_index is None:
            return None
        hdu_list = getattr(frame.fits_handler, "hdu_list", None)
        if hdu_list is None or frame.hdu_index >= len(hdu_list):
            return None
        hdu = hdu_list[frame.hdu_index]
        if classify(hdu, frame.hdu_index).kind is not HDUKind.EVENTS:
            return None
        return hdu

    def available_columns(self) -> tuple[str, ...]:
        """The current frame's table columns, or () if it has none."""
        table = self.table_hdu()
        return () if table is None else column_names(table)

    def rebin(self) -> None:
        """Re-bin the current frame's table and put the result on screen.

        A frame that is not a binned table is left alone, so changing a Bin
        setting while an image is displayed is remembered for the next table
        rather than reported as an error.
        """
        table = self.table_hdu()
        if table is None:
            return

        try:
            image = bin_table(table, self.columns, self.settings)
        except BinTableError as exc:
            self.status(str(exc), 5000)
            return

        frame = self.frame
        if frame is None:
            return
        frame.image = image
        frame.image_data = image.data
        frame.original_image_data = image.data
        frame.header = image.header
        frame.wcs_handler = WCSHandler(image.header)
        # A different grid is a different distribution, so the limits go.
        frame.z1 = None
        frame.z2 = None
        self.window.z1 = None
        self.window.z2 = None

        self.window.display.display()
        self.window.zoom.zoom_fit()
        height, width = image.data.shape[:2]
        self.status_bar.update_image_info(width, height)
        self.status(f"Binned {width}x{height}: {self.settings.describe()}", 3000)

    # -- parameters dialog ---------------------------------------------------

    def centre(self) -> tuple[float, float] | None:
        """Where the binned image is centred, in column units.

        The Bin Center if one was given, otherwise the middle of the data,
        which is what DS9 reports for "or center of data".
        """
        if self.settings.center is not None:
            return self.settings.center
        table = self.table_hdu()
        if table is None:
            return None
        try:
            extents = [column_extent(table, name) for name in self.columns.columns[:2]]
        except Exception:
            return None
        return tuple((low + high) / 2.0 for low, high in extents)

    def column_ranges(self) -> dict[str, tuple[float, float]]:
        """Each column's extent, for the dialog's Min and Max."""
        table = self.table_hdu()
        if table is None:
            return {}
        ranges = {}
        for name in self.available_columns():
            try:
                ranges[name] = column_extent(table, name)
            except Exception:
                continue
        return ranges

    # -- parameters dialog ---------------------------------------------------

    def show_dialog(self) -> None:
        """Show DS9's Binning Parameters window, modeless."""
        columns = self.available_columns()
        if not columns:
            self.status("The current frame is not a binned table", 3000)
            return

        dialog = BinDialog(columns, self.columns, self.settings, self.window, ranges=self.column_ranges())
        dialog.set_centre(self.centre(), self.settings.center is None)
        dialog.applied.connect(self.apply_dialog)
        self.show_window(dialog)

    def apply_dialog(self, spec: BinSpec, settings: BinSettings) -> None:
        """Bin with what the dialog holds."""
        self.window.bin_spec = spec
        self.window.bin_settings = settings
        self.sync()
        self.rebin()


class BinDialog(QDialog):
    """DS9's Binning Parameters window (`BinDialog`, `bin.tcl`).

    File (Apply, Clear Filter, Close), Method, Bin and Buffer menus -- the
    last three the main window's own actions -- over Bin Columns with each
    column's Min and Max, Bin Center with "or center of data", Bin Filter
    and Bin 3rd Column, and Apply, Clear Filter and Close. Modeless, as
    DS9's is: it used to be OK/Cancel and block the image it binned.

    Args:
        columns: The table's column names, to choose the axes from.
        spec: The columns currently binned on.
        settings: The current function, factor, buffer size, depth, filter
            and centre.
        parent: The main window, or nothing.
        ranges: Each column's extent, shown as its Min and Max.
    """

    #: Apply: the columns and settings to bin with.
    applied = pyqtSignal(object, object)

    #: The label standing for "no third column: count the rows".
    NO_DEPTH_COLUMN = "(count rows)"

    def __init__(self, columns, spec: BinSpec, settings: BinSettings, parent=None, ranges=None) -> None:
        from ..dialogs.modeless import make_modeless

        super().__init__(parent)
        self.setWindowTitle("Binning Parameters")
        make_modeless(self)
        self._columns = tuple(columns)
        self._ranges = dict(ranges or {})
        self._settings = settings

        layout = QVBoxLayout(self)
        layout.setMenuBar(self._build_menus(getattr(parent, "menu_bar", None)))

        cols = QGroupBox("Bin Columns")
        grid = QGridLayout(cols)
        for column, title in enumerate(("Column", "Bin", "Min", "Max")):
            grid.addWidget(QLabel(title), 0, column + 1)
        self._x = self._column_box(spec.columns[0] if spec.columns else "")
        self._y = self._column_box(spec.columns[1] if len(spec.columns) > 1 else "")
        self._factor_x = QLineEdit(f"{settings.factors[0]:g}")
        self._factor_y = QLineEdit(f"{settings.factors[1]:g}")
        self._range_labels = {}
        for row, (label, box, factor) in enumerate((("x", self._x, self._factor_x), ("y", self._y, self._factor_y)), 1):
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(box, row, 1)
            grid.addWidget(factor, row, 2)
            low, high = QLabel(), QLabel()
            grid.addWidget(low, row, 3)
            grid.addWidget(high, row, 4)
            self._range_labels[box] = (low, high)
            box.currentTextChanged.connect(lambda _text, b=box: self._show_range(b))
            self._show_range(box)
        layout.addWidget(cols)

        centre = QGroupBox("Bin Center")
        centre_row = QHBoxLayout(centre)
        self._centre_x = QLineEdit()
        self._centre_y = QLineEdit()
        self._auto_centre = QCheckBox("or center of data")
        self._auto_centre.toggled.connect(lambda on: (self._centre_x.setEnabled(not on), self._centre_y.setEnabled(not on)))
        for widget in (self._centre_x, self._centre_y, self._auto_centre):
            centre_row.addWidget(widget)
        layout.addWidget(centre)
        self.set_centre(settings.center, settings.center is None)

        filter_group = QGroupBox("Bin Filter")
        filter_row = QHBoxLayout(filter_group)
        self._filter = QLineEdit(settings.filter)
        self._filter.setPlaceholderText("pha>5&&ccd_id==3")
        filter_row.addWidget(self._filter)
        layout.addWidget(filter_group)

        third = QGroupBox("Bin 3rd Column")
        third_grid = QGridLayout(third)
        third_grid.addWidget(QLabel("Column"), 0, 0)
        third_grid.addWidget(QLabel("Depth"), 0, 1)
        self._depth_column = QComboBox()
        self._depth_column.addItem(self.NO_DEPTH_COLUMN)
        self._depth_column.addItems(self._columns)
        if len(spec.columns) > 2:
            self._depth_column.setCurrentText(spec.columns[2].upper())
        self._depth = QSpinBox()
        self._depth.setRange(1, MAX_DEPTH)
        self._depth.setValue(max(1, settings.depth))
        third_grid.addWidget(self._depth_column, 1, 0)
        third_grid.addWidget(self._depth, 1, 1)
        layout.addWidget(third)

        self.message = QLabel()
        layout.addWidget(self.message)

        buttons = QHBoxLayout()
        for label, slot in (("Apply", self.apply), ("Clear Filter", self.clear_filter), ("Close", self.close)):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, s=slot: s())
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def _build_menus(self, menu) -> QMenuBar:
        bar = QMenuBar(self)
        file_menu = bar.addMenu("&File")
        for label, slot in (("Apply", self.apply), ("Clear Filter", self.clear_filter), (None, None), ("Close", self.close)):
            if label is None:
                file_menu.addSeparator()
                continue
            action = QAction(label, self)
            if label == "Close":
                action.setShortcut(QKeySequence(QKeySequence.StandardKey.Close))
            action.triggered.connect(lambda _checked=False, s=slot: s())
            file_menu.addAction(action)
        if menu is not None:
            # The main window's own Bin actions, shared rather than copied.
            method = bar.addMenu("&Method")
            for action in getattr(menu, "bin_function_actions", {}).values():
                method.addAction(action)
            bin_menu = bar.addMenu("&Bin")
            for name in ("action_bin_in", "action_bin_out", "action_bin_fit"):
                if hasattr(menu, name):
                    bin_menu.addAction(getattr(menu, name))
            bin_menu.addSeparator()
            for action in getattr(menu, "bin_factor_actions", {}).values():
                bin_menu.addAction(action)
            buffer = bar.addMenu("B&uffer")
            for action in getattr(menu, "bin_buffer_actions", {}).values():
                buffer.addAction(action)
        return bar

    def _column_box(self, current: str) -> QComboBox:
        """A combo listing the table's columns, `current` selected."""
        box = QComboBox()
        box.addItems(self._columns)
        wanted = current.strip().upper()
        if wanted in self._columns:
            box.setCurrentText(wanted)
        return box

    def _show_range(self, box: QComboBox) -> None:
        low, high = self._ranges.get(box.currentText(), (None, None))
        labels = self._range_labels.get(box)
        if labels is None:
            return
        labels[0].setText("" if low is None else f"{low:g}")
        labels[1].setText("" if high is None else f"{high:g}")

    def set_centre(self, centre: tuple[float, float] | None, automatic: bool) -> None:
        """Show the Bin Center, and whether it is the middle of the data."""
        if centre is not None:
            self._centre_x.setText(f"{centre[0]:g}")
            self._centre_y.setText(f"{centre[1]:g}")
        self._auto_centre.setChecked(automatic)
        self._centre_x.setEnabled(not automatic)
        self._centre_y.setEnabled(not automatic)

    def bin_spec(self) -> BinSpec:
        """The columns the user chose."""
        columns = [self._x.currentText(), self._y.currentText()]
        depth = self._depth_column.currentText()
        if depth != self.NO_DEPTH_COLUMN:
            columns.append(depth)
        return BinSpec(columns=tuple(columns))

    def settings(self) -> BinSettings | None:
        """The parameters the user chose, or None (and a message) if unusable."""
        try:
            fx, fy = float(self._factor_x.text()), float(self._factor_y.text())
        except ValueError:
            self.message.setText("The bin factors are numbers.")
            return None
        if fx <= 0 or fy <= 0:
            self.message.setText("A bin factor is positive.")
            return None
        centre = None
        if not self._auto_centre.isChecked():
            try:
                centre = (float(self._centre_x.text()), float(self._centre_y.text()))
            except ValueError:
                self.message.setText("The bin center is two numbers, or the center of data.")
                return None
        self.message.clear()
        # The Method and Buffer menus are the main window's and change its
        # settings directly, so those are the ones to build on.
        base = getattr(self.parent(), "bin_settings", None) or self._settings
        return replace(
            base,
            factor=fx,
            factor_y=None if fx == fy else fy,
            depth=int(self._depth.value()),
            filter=self._filter.text().strip(),
            center=centre,
        )

    def apply(self) -> None:
        """DS9's Apply."""
        settings = self.settings()
        if settings is not None:
            self._settings = settings
            self.applied.emit(self.bin_spec(), settings)

    def clear_filter(self) -> None:
        """DS9's Clear Filter: bin every row again."""
        self._filter.clear()
        self.apply()
