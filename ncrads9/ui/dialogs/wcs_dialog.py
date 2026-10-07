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
DS9's WCS Parameters window: read, edit and replace a frame's WCS.

A copy of `WCSDialog` in DS9's `wcs.tcl`. One field per FITS keyword, on
seven tabs -- the basic keywords, the two halves of the `PVi_m` projection
parameters and the four SIP distortion polynomials -- under DS9's own File,
Edit, WCS and Extension menus.

The window edits every WCS description in the header at once. Its `WCS`
menu only chooses which one the fields show, `WCS` for the primary or
`WCS a`..`WCS z` for an alternate, relabelling them `CTYPE1A` and so on as
DS9's `ConfigWCSDialog` does; Apply then replaces the frame's whole WCS with
everything typed, as DS9's `wcs replace` does. Reset puts back the WCS the
file came with. Open fills the fields from a `.wcs` keyword file without
applying it; Save writes the frame's current WCS, as DS9's does.

Modeless, like every parameters window (`modeless.py`): the readout and
the grid it changes are on the image behind it.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from PyQt6.QtGui import QAction, QActionGroup, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core import wcs_keywords
from .modeless import make_modeless

#: The file filter for Open and Save.
FILE_FILTER = "WCS files (*.wcs);;All files (*)"

#: Character width of one field, DS9's `-width 14`.
FIELD_WIDTH = 14

#: Fields that describe the observation rather than one WCS description, so
#: carry no alternate letter. DS9 relabels the first two on its dialog but
#: reads and writes them unsuffixed; they are simply unsuffixed here.
_GLOBAL_FIELDS = ("MJD-OBS", "DATE-OBS", "EPOCH")


#: The (p, q) pairs DS9 lays out for each SIP polynomial: p + q <= 9.
SIP_TERMS: tuple[tuple[int, int], ...] = tuple(
    (p, q) for p in range(10) for q in range(10) if p + q <= 9 and (p, q) != (0, 0)
)


class WCSDialog(QDialog):
    """The WCS Parameters window."""

    def __init__(self, controller, parent=None) -> None:
        """
        Args:
            controller: The `WCSController`, which owns the frame's WCS.
            parent: The main window.
        """
        super().__init__(parent)
        make_modeless(self)
        self._controller = controller
        #: Every keyword typed or loaded, for every description at once:
        #: upper-case keyword -> its text. The fields show one letter's.
        self._values: dict[str, str] = {}
        #: Which description the fields show: "" or "a".."z".
        self._letter = ""
        #: Field base name (e.g. `CTYPE1`) -> its entry and its label.
        self.fields: dict[str, QLineEdit] = {}
        self._labels: dict[str, QLabel] = {}
        #: Base names that take the alternate letter.
        self._per_system: set[str] = set()

        self.setWindowTitle("WCS Parameters")
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        layout.setMenuBar(self._menus())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._scrolled(self._keyword_page()), "Keyword")
        self.tabs.addTab(self._scrolled(self._pv_page(0, 18)), "PVi_00")
        self.tabs.addTab(self._scrolled(self._pv_page(18, 36)), "PVi_18")
        self.tabs.addTab(self._scrolled(self._sip_page("A", dmax=True)), "A_p_q")
        self.tabs.addTab(self._scrolled(self._sip_page("B", dmax=True)), "B_p_q")
        self.tabs.addTab(self._scrolled(self._sip_page("AP", dmax=False)), "AP_p_q")
        self.tabs.addTab(self._scrolled(self._sip_page("BP", dmax=False)), "BP_p_q")
        layout.addWidget(self.tabs)

        buttons = QHBoxLayout()
        for label, slot in (("Apply", self.apply), ("Reset", self.reset), ("Close", self.close)):
            button = QPushButton(label)
            button.setAutoDefault(False)
            button.clicked.connect(lambda _checked=False, s=slot: s())
            buttons.addWidget(button)
        layout.addLayout(buttons)

    # -- construction --------------------------------------------------------

    def _menus(self) -> QMenuBar:
        """DS9's File, Edit, WCS and Extension menus."""
        bar = QMenuBar(self)
        #: Action name -> the action, so a test can trigger one.
        self.actions_by_name: dict[str, QAction] = {}

        file_menu = bar.addMenu("&File")
        self._add(file_menu, "open", "&Open...", self.open_file, "Ctrl+O")
        self._add(file_menu, "save", "&Save...", self.save_file, "Ctrl+S")
        file_menu.addSeparator()
        self._add(file_menu, "apply", "&Apply", self.apply)
        self._add(file_menu, "reset", "&Reset", self.reset)
        file_menu.addSeparator()
        self._add(file_menu, "close", "&Close", self.close, "Ctrl+W")

        edit_menu = bar.addMenu("&Edit")
        self._add(edit_menu, "cut", "Cu&t", lambda: self._on_entry("cut"), "Ctrl+X")
        self._add(edit_menu, "copy", "&Copy", lambda: self._on_entry("copy"), "Ctrl+C")
        self._add(edit_menu, "paste", "&Paste", lambda: self._on_entry("paste"), "Ctrl+V")

        wcs_menu = bar.addMenu("&WCS")
        group = QActionGroup(self)
        group.setExclusive(True)
        #: DS9's system token -> its entry on this window's WCS menu.
        self.system_actions: dict[str, QAction] = {}
        for system in ("wcs", *(f"wcs{letter}" for letter in wcs_keywords.ALTERNATE_LETTERS)):
            label = "WCS" if system == "wcs" else f"WCS {system[3]}"
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(system == "wcs")
            action.triggered.connect(lambda _checked=False, s=system: self.set_system(s))
            group.addAction(action)
            wcs_menu.addAction(action)
            if system == "wcs":
                wcs_menu.addSeparator()
            self.system_actions[system] = action

        # DS9 lists a mosaic's segments here, and disables the menu for a
        # frame of one; a frame here always holds one.
        self.extension_menu = bar.addMenu("E&xtension")
        self.extension_menu.setEnabled(False)
        return bar

    def _add(self, menu, name: str, label: str, slot, shortcut: str | None = None) -> QAction:
        """One menu entry, remembered by name."""
        action = QAction(label, self)
        action.triggered.connect(lambda _checked=False: slot())
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        menu.addAction(action)
        self.actions_by_name[name] = action
        return action

    @staticmethod
    def _scrolled(page: QWidget) -> QScrollArea:
        """A tab's page in a scroll area: the Keyword tab alone is 70 fields."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(page)
        return area

    def _field(self, grid: QGridLayout, name: str, row: int, column: int, per_system: bool = True) -> None:
        """One labelled entry, at a grid position counted in label+entry pairs."""
        label = QLabel(name)
        entry = QLineEdit()
        entry.setMinimumWidth(entry.fontMetrics().averageCharWidth() * FIELD_WIDTH)
        grid.addWidget(label, row, column * 2)
        grid.addWidget(entry, row, column * 2 + 1)
        self.fields[name] = entry
        self._labels[name] = label
        if per_system:
            self._per_system.add(name)

    def _keyword_page(self) -> QWidget:
        """DS9's `Keyword` tab, laid out as DS9 grids it."""
        page = QWidget()
        grid = QGridLayout(page)
        row = 0
        for name in ("WCSNAME", "WCSAXES", "RADESYS"):
            self._field(grid, name, row, 0)
            row += 1
        self._field(grid, "EQUINOX", row, 0)
        self._field(grid, "EPOCH", row, 1, per_system=False)
        row += 1
        self._field(grid, "MJD-OBS", row, 0, per_system=False)
        self._field(grid, "DATE-OBS", row, 1, per_system=False)
        row += 1
        for stem in ("CTYPE", "CRPIX", "CRVAL", "CUNIT", "CDELT"):
            for axis in range(1, 5):
                self._field(grid, f"{stem}{axis}", row, axis - 1)
            row += 1
        for stem in ("CD", "PC"):
            for j in range(1, 5):
                for i in range(1, 5):
                    self._field(grid, f"{stem}{i}_{j}", row, i - 1)
                row += 1
        for m in range(2):
            for i in range(1, 5):
                self._field(grid, f"PS{i}_{m}", row, i - 1)
            row += 1
        self._field(grid, "LATPOLE", row, 0)
        self._field(grid, "LONPOLE", row, 1)
        grid.setRowStretch(row + 1, 1)
        return page

    def _pv_page(self, first: int, last: int) -> QWidget:
        """One of DS9's two `PVi_m` tabs: m from `first` up to `last`."""
        page = QWidget()
        grid = QGridLayout(page)
        for row, m in enumerate(range(first, last)):
            for i in range(1, 5):
                self._field(grid, f"PV{i}_{m}", row, i - 1)
        grid.setRowStretch(last - first, 1)
        return page

    def _sip_page(self, prefix: str, dmax: bool) -> QWidget:
        """One of DS9's SIP tabs: the order, then the coefficients p + q <= 9.

        SIP describes the primary WCS only, so these carry no letter.
        """
        page = QWidget()
        grid = QGridLayout(page)
        self._field(grid, f"{prefix}_ORDER", 0, 0, per_system=False)
        if dmax:
            self._field(grid, f"{prefix}_DMAX", 0, 1, per_system=False)
        for index, (p, q) in enumerate(SIP_TERMS):
            self._field(grid, f"{prefix}_{p}_{q}", 1 + index // 4, index % 4, per_system=False)
        grid.setRowStretch(2 + len(SIP_TERMS) // 4, 1)
        return page

    # -- the values ----------------------------------------------------------

    def _key(self, name: str) -> str:
        """The keyword one field edits for the description shown."""
        return f"{name}{self._letter.upper()}" if name in self._per_system else name

    def _store(self) -> None:
        """Copy what the fields show back into `_values`."""
        for name, entry in self.fields.items():
            key = self._key(name)
            text = entry.text().strip()
            if text:
                self._values[key] = text
            else:
                self._values.pop(key, None)

    def _show(self) -> None:
        """Fill the fields, and their labels, for the description chosen."""
        for name, entry in self.fields.items():
            key = self._key(name)
            self._labels[name].setText(key)
            entry.setText(self._values.get(key, ""))

    @property
    def system(self) -> str:
        """Which description the fields show: `wcs` or `wcsa`..`wcsz`."""
        return f"wcs{self._letter}"

    def set_system(self, system: str) -> None:
        """Show another description's keywords, keeping what was typed."""
        token = system.strip().lower()
        if token not in self.system_actions:
            return
        self._store()
        self._letter = token[3:]
        self.system_actions[token].setChecked(True)
        self._show()

    def load_values(self, values: Mapping[str, str]) -> None:
        """Replace everything on the window with these keywords."""
        self._values = {str(key).upper(): str(value) for key, value in values.items() if str(value).strip()}
        self._show()

    def values(self) -> dict[str, str]:
        """Every keyword on the window, for every description."""
        self._store()
        return dict(self._values)

    def wcs_text(self) -> str:
        """What is on the window, as `.wcs` text (DS9's `WCSFromVar`)."""
        return wcs_keywords.format_wcs_text(wcs_keywords.values_to_header(self.values()))

    # -- File menu -----------------------------------------------------------

    def apply(self) -> bool:
        """Make what is typed the frame's WCS, DS9's `WCSApplyDialog`."""
        problem = self._controller.replace_wcs(self.values())
        if problem:
            QMessageBox.warning(self, "WCS Parameters", f"Unable to apply the WCS: {problem}")
            return False
        return True

    def reset(self) -> bool:
        """Put back the file's own WCS and show it, DS9's `WCSResetDialog`."""
        problem = self._controller.reset_wcs()
        self.load_values(self._controller.current_wcs_values())
        return problem is None

    def open_file(self, path: str | None = None) -> bool:
        """Fill the fields from a `.wcs` file. Apply makes them the WCS."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Open WCS", "", FILE_FILTER)
        if not path:
            return False
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            QMessageBox.warning(self, "WCS Parameters", f"Unable to open {Path(path).name}:\n{exc}")
            return False
        self.load_values(wcs_keywords.parse_wcs_text(text))
        return True

    def save_file(self, path: str | None = None) -> bool:
        """Write the frame's current WCS to a `.wcs` file."""
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Save WCS", "", FILE_FILTER)
        if not path:
            return False
        problem = self._controller.save_wcs_file(path)
        if problem:
            QMessageBox.warning(self, "WCS Parameters", problem)
            return False
        return True

    # -- Edit menu -----------------------------------------------------------

    def _on_entry(self, operation: str) -> None:
        """Cut, copy or paste in whichever field has the focus."""
        widget = QApplication.focusWidget()
        if isinstance(widget, QLineEdit) and widget in self.fields.values():
            getattr(widget, operation)()
