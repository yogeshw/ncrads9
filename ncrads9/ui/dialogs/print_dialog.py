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
DS9's Print dialog: where it goes, and what PostScript to make.

Two groups as DS9 has them (`print.tcl:280`): Print To, with a printer and
its command or a file and its name, and Postscript, with the colour model,
the level and the resolution.

The one addition is PDF beside PostScript in the format list. DS9 has no
PDF; a modern desktop would rather have one, and the page comes out with
the same geometry either way.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from ...printing.page_setup import PageSetup
from ...printing.postscript import COLOR_MODELS, LEVELS, RESOLUTIONS
from ...printing.print_engine import Destination, OutputFormat, PrintSettings

#: What each colour model is called on the dialog.
COLOR_LABELS: dict[str, str] = {"rgb": "RGB", "cmyk": "CMYK", "gray": "Grayscale"}

#: What each output format is called.
FORMAT_LABELS: tuple[tuple[OutputFormat, str], ...] = (
    (OutputFormat.POSTSCRIPT, "PostScript"),
    (OutputFormat.EPS, "Encapsulated PostScript"),
    (OutputFormat.PDF, "PDF"),
)


class PrintDialog(QDialog):
    """Asks where the print goes and what it is made of."""

    def __init__(self, settings: PrintSettings | None = None, parent=None) -> None:
        """
        Args:
            settings: What to start from.
            parent: The main window.
        """
        super().__init__(parent)
        self.setWindowTitle("Print")
        self.setMinimumWidth(420)
        self._page: PageSetup = (settings or PrintSettings()).page

        layout = QVBoxLayout(self)

        destination = QGroupBox("Print To")
        destination_form = QFormLayout(destination)
        # One group, explicitly: the two buttons sit in different rows, and
        # Qt only makes radio buttons exclusive within one parent widget --
        # so without this, choosing File left Printer chosen as well.
        self._destination_group = QButtonGroup(self)
        self._printer = QRadioButton("Printer")
        self._command = QLineEdit()
        printer_row = QHBoxLayout()
        printer_row.addWidget(self._printer)
        printer_row.addWidget(self._command)
        destination_form.addRow("Command:", self._wrap(printer_row))

        self._file = QRadioButton("File")
        self._destination_group.addButton(self._printer)
        self._destination_group.addButton(self._file)
        self._filename = QLineEdit()
        browse = QPushButton("Browse...")
        browse.clicked.connect(self.browse)
        file_row = QHBoxLayout()
        file_row.addWidget(self._file)
        file_row.addWidget(self._filename)
        file_row.addWidget(browse)
        destination_form.addRow("Name:", self._wrap(file_row))
        layout.addWidget(destination)

        options = QGroupBox("Postscript")
        options_form = QFormLayout(options)
        self._color = QComboBox()
        for model in COLOR_MODELS:
            self._color.addItem(COLOR_LABELS[model], model)
        options_form.addRow("Color:", self._color)

        self._level = QComboBox()
        for level in LEVELS:
            self._level.addItem(f"Level {level}", level)
        options_form.addRow("Level:", self._level)

        self._resolution = QComboBox()
        for value in RESOLUTIONS:
            self._resolution.addItem(str(value), value)
        options_form.addRow("DPI:", self._resolution)

        self._format = QComboBox()
        for chosen, label in FORMAT_LABELS:
            self._format.addItem(label, chosen)
        self._format.currentIndexChanged.connect(lambda _index: self.update_state())
        options_form.addRow("Format:", self._format)
        layout.addWidget(options)

        for button in (self._printer, self._file):
            button.toggled.connect(lambda _checked=False: self.update_state())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.load(settings or PrintSettings())

    @staticmethod
    def _wrap(inner) -> QGroupBox:
        """One row of controls as a single widget for the form."""
        holder = QGroupBox()
        holder.setFlat(True)
        holder.setLayout(inner)
        return holder

    # -- what it shows -----------------------------------------------------------

    def load(self, settings: PrintSettings) -> None:
        """Fill the dialog in."""
        self._printer.setChecked(settings.destination is Destination.PRINTER)
        self._file.setChecked(settings.destination is Destination.FILE)
        self._command.setText(settings.command)
        self._filename.setText(settings.filename)
        self._color.setCurrentIndex(max(0, self._color.findData(settings.color_model)))
        self._level.setCurrentIndex(max(0, self._level.findData(settings.level)))
        self._resolution.setCurrentIndex(max(0, self._resolution.findData(settings.resolution)))
        self._format.setCurrentIndex(max(0, self._format.findData(settings.output_format)))
        self._page = settings.page
        self.update_state()

    def update_state(self) -> None:
        """Turn off what the chosen combination has no use for."""
        to_printer = self._printer.isChecked()
        self._command.setEnabled(to_printer)
        self._filename.setEnabled(not to_printer)

        # A PDF is not PostScript: it has no level and no colour model of
        # DS9's kind, and it cannot be piped to `lp` as text.
        is_pdf = self._format.currentData() is OutputFormat.PDF
        self._level.setEnabled(not is_pdf)
        self._color.setEnabled(not is_pdf)
        if is_pdf and to_printer:
            self._file.setChecked(True)

    def browse(self) -> None:
        """Choose the file to print to."""
        chosen, _ = QFileDialog.getSaveFileName(
            self,
            "Print to File",
            self._filename.text(),
            "PostScript (*.ps *.eps);;PDF (*.pdf);;All files (*)",
        )
        if chosen:
            self._filename.setText(chosen)
            self._file.setChecked(True)

    def settings(self) -> PrintSettings:
        """What the dialog says to print."""
        return PrintSettings(
            destination=Destination.PRINTER if self._printer.isChecked() else Destination.FILE,
            command=self._command.text(),
            filename=self._filename.text(),
            level=int(self._level.currentData()),
            color_model=str(self._color.currentData()),
            resolution=int(self._resolution.currentData()),
            output_format=self._format.currentData(),
            page=self._page,
        )

    def choose(self) -> PrintSettings | None:
        """Ask, and say what was chosen, or None if it was cancelled."""
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        return self.settings()
