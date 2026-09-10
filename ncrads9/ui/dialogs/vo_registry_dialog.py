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
The VO registry browser: find a service, then query it.

Two halves in one window, because that is how it is used. The top finds
services of a chosen kind; the bottom queries whichever one is highlighted
about a position. A TAP service is listed but cannot be queried from here:
it answers ADQL, which needs a query and a schema to write one against.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...catalogs.vo_registry import DiscoveryResult, Service, ServiceKind

#: How big the window opens.
WINDOW_SIZE = (860, 560)

#: The cone radius it opens at, in degrees.
DEFAULT_RADIUS = 0.1


class VORegistryDialog(QDialog):
    """Discover VO services and query one of them.

    Args:
        center: The frame's centre as (longitude, latitude) in degrees.
        parent: Optional parent widget.
    """

    #: Emitted with (kind, words) when Search is pressed.
    discovery_requested = pyqtSignal(object, str)
    #: Emitted with (service, longitude, latitude, radius) on Query.
    query_requested = pyqtSignal(object, float, float, float)

    def __init__(
        self,
        center: tuple[float, float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("VO Registry")
        self.resize(*WINDOW_SIZE)
        self._services: list[Service] = []

        layout = QVBoxLayout(self)

        find = QGroupBox("Find services")
        form = QFormLayout(find)
        self._kind = QComboBox()
        for kind in ServiceKind:
            self._kind.addItem(kind.label, kind)
        form.addRow("Kind:", self._kind)

        self._words = QLineEdit()
        self._words.setPlaceholderText("words in the title or description")
        self._words.returnPressed.connect(self.discover)
        form.addRow("Keywords:", self._words)

        search = QPushButton("Search")
        search.clicked.connect(self.discover)
        form.addRow("", search)
        layout.addWidget(find)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Service", "Publisher", "URL"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.itemSelectionChanged.connect(self._on_selected)
        layout.addWidget(self._table)

        ask = QGroupBox("Query the selected service")
        form = QFormLayout(ask)
        self._longitude = QDoubleSpinBox()
        self._longitude.setRange(0.0, 360.0)
        self._longitude.setDecimals(6)
        form.addRow("RA (degrees):", self._longitude)
        self._latitude = QDoubleSpinBox()
        self._latitude.setRange(-90.0, 90.0)
        self._latitude.setDecimals(6)
        form.addRow("Dec (degrees):", self._latitude)
        if center is not None:
            self._longitude.setValue(float(center[0]))
            self._latitude.setValue(float(center[1]))

        self._radius = QDoubleSpinBox()
        self._radius.setRange(0.0001, 10.0)
        self._radius.setDecimals(4)
        self._radius.setValue(DEFAULT_RADIUS)
        form.addRow("Radius (degrees):", self._radius)

        self._query_button = QPushButton("Query")
        self._query_button.setEnabled(False)
        self._query_button.clicked.connect(self.query)
        form.addRow("", self._query_button)
        layout.addWidget(ask)

        self._message = QLabel()
        self._message.setWordWrap(True)
        layout.addWidget(self._message)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- discovery ------------------------------------------------------------

    def kind(self) -> ServiceKind:
        """Which service kind is chosen."""
        return self._kind.currentData()

    def discover(self) -> None:
        """Ask the controller to search the registry."""
        self._message.setText("Searching the registry...")
        self.discovery_requested.emit(self.kind(), self._words.text().strip())

    def show_result(self, result: DiscoveryResult) -> None:
        """Show what the registry returned."""
        self._services = list(result.services)
        self._message.setText(result.message)
        self._table.setRowCount(len(self._services))
        for row, service in enumerate(self._services):
            self._table.setItem(row, 0, QTableWidgetItem(service.title))
            self._table.setItem(row, 1, QTableWidgetItem(service.publisher))
            self._table.setItem(row, 2, QTableWidgetItem(service.url))
        self._query_button.setEnabled(False)

    def selected(self) -> Service | None:
        """The highlighted service, or None."""
        row = self._table.currentRow()
        if 0 <= row < len(self._services):
            return self._services[row]
        return None

    def _on_selected(self) -> None:
        """Enable Query for a service that can answer one."""
        service = self.selected()
        if service is None:
            self._query_button.setEnabled(False)
            return
        # TAP is listed but cannot be asked about a position.
        self._query_button.setEnabled(service.kind is not ServiceKind.TAP)
        if service.description:
            self._message.setText(service.description[:400])

    # -- querying --------------------------------------------------------------

    def query(self) -> None:
        """Ask the controller to query the highlighted service."""
        service = self.selected()
        if service is None:
            return
        self._message.setText(f"Querying {service.title}...")
        self.query_requested.emit(
            service,
            self._longitude.value(),
            self._latitude.value(),
            self._radius.value(),
        )

    def set_message(self, text: str) -> None:
        """Say what happened."""
        self._message.setText(text)
