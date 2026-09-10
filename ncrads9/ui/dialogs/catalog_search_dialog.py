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
DS9's Search for Catalogs dialog.

Title or identifier, free text, and three keyword menus -- wavelength,
mission and object type -- then a list of what VizieR has, from which one
can be loaded. The keyword lists are DS9's, offered as menus rather than as
text because VizieR matches them exactly and `xray` for `X-ray` returns
nothing with no hint why.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...catalogs.catalog_search import (
    ASTRONOMY,
    MISSIONS,
    NO_KEYWORD,
    WAVELENGTHS,
    SearchRequest,
    SearchResult,
)
from ...catalogs.servers import MIRRORS

#: How big the dialog opens.
WINDOW_SIZE = (760, 520)


class CatalogSearchDialog(QDialog):
    """Search VizieR's index and choose a catalogue to load.

    Args:
        mirror: Which VizieR site to search.
        parent: Optional parent widget.
    """

    #: Emitted with a `SearchRequest` when Search is pressed.
    search_requested = pyqtSignal(object)
    #: Emitted with a VizieR identifier when one is chosen.
    catalog_chosen = pyqtSignal(str)

    def __init__(self, mirror: str = "cds", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Search for Catalogs")
        self.resize(*WINDOW_SIZE)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._source = QLineEdit()
        self._source.setPlaceholderText("e.g. I/345 or gaia")
        self._source.returnPressed.connect(self.request)
        form.addRow("Catalog:", self._source)

        self._words = QLineEdit()
        self._words.setPlaceholderText("words in the title or description")
        self._words.returnPressed.connect(self.request)
        form.addRow("Keywords:", self._words)

        self._wavelength = _keywords(WAVELENGTHS)
        form.addRow("Wavelength:", self._wavelength)
        self._mission = _keywords(MISSIONS)
        form.addRow("Mission:", self._mission)
        self._astronomy = _keywords(ASTRONOMY)
        form.addRow("Object type:", self._astronomy)

        self._mirror = QComboBox()
        for label, name in MIRRORS:
            self._mirror.addItem(label, name)
        index = self._mirror.findData(mirror)
        if index >= 0:
            self._mirror.setCurrentIndex(index)
        form.addRow("Server:", self._mirror)

        self._results = QTableWidget(0, 2)
        self._results.setHorizontalHeaderLabels(["Catalog", "Title"])
        self._results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._results.itemDoubleClicked.connect(lambda _item: self.choose())
        layout.addWidget(self._results)

        self._message = QLabel()
        layout.addWidget(self._message)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.request)
        buttons.addButton(search_button, QDialogButtonBox.ButtonRole.ActionRole)
        self._load_button = QPushButton("Load")
        self._load_button.clicked.connect(self.choose)
        self._load_button.setEnabled(False)
        buttons.addButton(self._load_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- searching ----------------------------------------------------------

    def build_request(self) -> SearchRequest:
        """What the fields are asking for."""
        return SearchRequest(
            source=self._source.text(),
            words=self._words.text(),
            wavelength=self._wavelength.currentText(),
            mission=self._mission.currentText(),
            astronomy=self._astronomy.currentText(),
            mirror=str(self._mirror.currentData() or "cds"),
        )

    def request(self) -> None:
        """Ask the controller to run the search."""
        self._message.setText("Searching...")
        self.search_requested.emit(self.build_request())

    def show_result(self, result: SearchResult) -> None:
        """Show what the search found."""
        self._message.setText(result.message)
        self._results.setRowCount(len(result.found))
        for row, (identifier, title) in enumerate(result.found):
            self._results.setItem(row, 0, QTableWidgetItem(identifier))
            self._results.setItem(row, 1, QTableWidgetItem(title))
        self._results.resizeColumnToContents(0)
        self._load_button.setEnabled(bool(result.found))

    def chosen(self) -> str:
        """The identifier of the highlighted row, or "" if none is."""
        row = self._results.currentRow()
        if row < 0:
            return ""
        item = self._results.item(row, 0)
        return item.text() if item is not None else ""

    def choose(self) -> None:
        """Load the highlighted catalogue."""
        identifier = self.chosen()
        if identifier:
            self.catalog_chosen.emit(identifier)


def _keywords(choices) -> QComboBox:
    """A keyword menu, opening on "none" -- do not filter on this."""
    combo = QComboBox()
    combo.addItem(NO_KEYWORD)
    combo.addItems(list(choices))
    return combo
