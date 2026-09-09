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

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
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
            action.setChecked(float(factor) == settings.factor)
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

    def show_dialog(self) -> None:
        """Show DS9's Binning Parameters dialog."""
        columns = self.available_columns()
        if not columns:
            self.status("The current frame is not a binned table", 3000)
            return

        dialog = BinDialog(columns, self.columns, self.settings, self.window)
        if not dialog.exec():
            return
        self.window.bin_spec = dialog.bin_spec()
        self.window.bin_settings = dialog.settings()
        self.sync()
        self.rebin()


class BinDialog(QDialog):
    """DS9's Binning Parameters dialog.

    Args:
        columns: The table's column names, to choose the axes from.
        spec: The columns currently binned on.
        settings: The current function, factor, buffer size, depth and filter.
        parent: Optional parent widget.
    """

    #: The label standing for "no third column: count the rows".
    NO_DEPTH_COLUMN = "(count rows)"

    def __init__(self, columns, spec: BinSpec, settings: BinSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Binning Parameters")
        self._columns = tuple(columns)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._x = self._column_box(spec.columns[0] if spec.columns else "")
        form.addRow("X column:", self._x)
        self._y = self._column_box(spec.columns[1] if len(spec.columns) > 1 else "")
        form.addRow("Y column:", self._y)

        self._depth_column = QComboBox()
        self._depth_column.addItem(self.NO_DEPTH_COLUMN)
        self._depth_column.addItems(self._columns)
        if len(spec.columns) > 2:
            self._depth_column.setCurrentText(spec.columns[2].upper())
        form.addRow("Bin values of:", self._depth_column)

        self._function = QComboBox()
        self._function.addItems([function.value for function in BinFunction])
        self._function.setCurrentText(settings.function.value)
        form.addRow("Function:", self._function)

        self._factor = QComboBox()
        self._factor.addItems([f"{factor:g}" for factor in BIN_FACTORS])
        self._factor.setCurrentText(f"{settings.factor:g}")
        form.addRow("Bin factor:", self._factor)

        self._buffer = QComboBox()
        self._buffer.addItems([str(size) for size in BUFFER_SIZES])
        self._buffer.setCurrentText(str(settings.buffer_size))
        form.addRow("Buffer size:", self._buffer)

        self._depth = QSpinBox()
        self._depth.setRange(1, MAX_DEPTH)
        self._depth.setValue(max(1, settings.depth))
        form.addRow("Depth:", self._depth)

        self._filter = QLineEdit(settings.filter)
        self._filter.setPlaceholderText("pha>5&&ccd_id==3")
        form.addRow("Filter:", self._filter)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _column_box(self, current: str) -> QComboBox:
        """A combo listing the table's columns, `current` selected."""
        box = QComboBox()
        box.addItems(self._columns)
        wanted = current.strip().upper()
        if wanted in self._columns:
            box.setCurrentText(wanted)
        return box

    def bin_spec(self) -> BinSpec:
        """The columns the user chose."""
        columns = [self._x.currentText(), self._y.currentText()]
        depth = self._depth_column.currentText()
        if depth != self.NO_DEPTH_COLUMN:
            columns.append(depth)
        return BinSpec(columns=tuple(columns))

    def settings(self) -> BinSettings:
        """The parameters the user chose."""
        return BinSettings(
            function=BinFunction(self._function.currentText()),
            factor=float(self._factor.currentText()),
            buffer_size=int(self._buffer.currentText()),
            depth=int(self._depth.value()),
            filter=self._filter.text().strip(),
        )
