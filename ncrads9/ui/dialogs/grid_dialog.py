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
DS9's Coordinate Grid Parameters dialog.

A tab per element -- Grid, Axes, Numerics, Labels, Tickmarks, Title, Border
-- because that is how DS9 divides it, with a menu per element carrying
Show, Colour and either a Line or a Font (`ds9/library/grid.tcl:581`). A
menu bar of eleven cascades does not translate into a Qt dialog; a notebook
of the same settings does.

What this replaced: a dialog of one colour, one line width, a label toggle
and two spacings, which could not express six of the seven elements.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...grid.grid_config import (
    COLORS,
    ELEMENTS,
    FONT_SIZES,
    FONT_SLANTS,
    FONT_WEIGHTS,
    FONTS,
    LINE_ELEMENTS,
    LINE_STYLES,
    LINE_WIDTHS,
    GridConfig,
    GridType,
    Placement,
)

#: The coordinate systems the Coordinate tab offers.
SYSTEMS: tuple[str, ...] = ("wcs", "image", "physical")

#: The sky frames it offers, when the system is wcs.
SKY_FRAMES: tuple[str, ...] = ("fk4", "fk5", "icrs", "galactic", "ecliptic")

#: And the two formats.
SKY_FORMATS: tuple[str, ...] = ("sexagesimal", "degrees")

#: The filter Load and Save offer.
GRID_FILTER = "Grid Files (*.grd *.json);;All Files (*)"

#: The widest spacing the dialog offers, in degrees.
MAX_SPACING = 180.0


class GridDialog(QDialog):
    """Everything a coordinate grid's appearance is set from.

    Args:
        config: The grid settings to edit. A copy is edited, so Cancel
            really cancels.
        parent: Optional parent widget.
    """

    #: Emitted with the edited `GridConfig` when Apply or OK is pressed.
    grid_changed = pyqtSignal(object)

    def __init__(self, config: GridConfig | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Coordinate Grid Parameters")
        self.config = (config or GridConfig()).copy()
        self._widgets: dict[str, QWidget] = {}

        layout = QVBoxLayout(self)
        self._show = QCheckBox("Show coordinate grid")
        self._show.setChecked(self.config.visible)
        layout.addWidget(self._show)

        notebook = QTabWidget()
        notebook.addTab(self._general_tab(), "General")
        notebook.addTab(self._coordinate_tab(), "Coordinate")
        for name in ELEMENTS:
            notebook.addTab(self._element_tab(name), name.title())
        layout.addWidget(notebook)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Open
            | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        buttons.button(QDialogButtonBox.StandardButton.Open).setText("Load...")
        buttons.button(QDialogButtonBox.StandardButton.Open).clicked.connect(self.load)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Save...")
        buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self.save)
        layout.addWidget(buttons)

    # -- tabs ----------------------------------------------------------------

    def _general_tab(self) -> QWidget:
        """DS9's Type menu, the titles, and the spacing."""
        page = QWidget()
        layout = QVBoxLayout(page)

        type_group = QGroupBox("Type")
        form = QFormLayout(type_group)
        self._widgets["grid_type"] = self._combo(
            [choice.value for choice in GridType], self.config.grid_type.value
        )
        form.addRow("Grid:", self._widgets["grid_type"])
        self._widgets["axes_placement"] = self._combo(
            [choice.value for choice in Placement], self.config.axes_placement.value
        )
        form.addRow("Axes:", self._widgets["axes_placement"])
        self._widgets["numerics_placement"] = self._combo(
            [choice.value for choice in Placement], self.config.numerics_placement.value
        )
        form.addRow("Numerics:", self._widgets["numerics_placement"])
        vertical = QCheckBox()
        vertical.setChecked(self.config.vertical_text)
        self._widgets["vertical_text"] = vertical
        form.addRow("Vertical text:", vertical)
        layout.addWidget(type_group)

        titles = QGroupBox("Titles")
        form = QFormLayout(titles)
        for key, label, value in (
            ("title", "Title", self.config.title),
            ("x_title", "X axis", self.config.x_title),
            ("y_title", "Y axis", self.config.y_title),
        ):
            field = QLineEdit(value)
            field.setPlaceholderText("(from the coordinate system)")
            self._widgets[key] = field
            form.addRow(f"{label}:", field)
        layout.addWidget(titles)

        spacing = QGroupBox("Spacing")
        form = QFormLayout(spacing)
        automatic = QCheckBox("Choose from the image")
        automatic.setChecked(self.config.auto_spacing)
        self._widgets["auto_spacing"] = automatic
        form.addRow("", automatic)

        target = QSpinBox()
        target.setRange(2, 40)
        target.setValue(self.config.target_lines)
        self._widgets["target_lines"] = target
        form.addRow("Lines per axis:", target)

        for key, label, value in (
            ("x_spacing", "X interval (deg)", self.config.x_spacing),
            ("y_spacing", "Y interval (deg)", self.config.y_spacing),
        ):
            box = QDoubleSpinBox()
            box.setRange(0.0, MAX_SPACING)
            box.setDecimals(6)
            box.setValue(float(value) if value else 0.0)
            box.setSpecialValueText("automatic")
            self._widgets[key] = box
            form.addRow(f"{label}:", box)
        layout.addWidget(spacing)

        layout.addStretch()
        return page

    def _coordinate_tab(self) -> QWidget:
        """The system, the sky frame, the format, and the numeric formats."""
        page = QWidget()
        layout = QVBoxLayout(page)

        group = QGroupBox("Coordinate system")
        form = QFormLayout(group)
        self._widgets["system"] = self._combo(SYSTEMS, self.config.system)
        form.addRow("System:", self._widgets["system"])
        self._widgets["sky"] = self._combo(SKY_FRAMES, self.config.sky)
        form.addRow("Sky frame:", self._widgets["sky"])
        self._widgets["sky_format"] = self._combo(SKY_FORMATS, self.config.sky_format)
        form.addRow("Format:", self._widgets["sky_format"])
        layout.addWidget(group)

        formats = QGroupBox("Numeric format")
        form = QFormLayout(formats)
        for key, label, value in (
            ("x_format", "X axis", self.config.x_format),
            ("y_format", "Y axis", self.config.y_format),
        ):
            field = QLineEdit(value)
            field.setPlaceholderText("e.g. hms.1, +dms.2, d.3, %1.7G")
            self._widgets[key] = field
            form.addRow(f"{label}:", field)
        form.addRow(
            "",
            _hint(
                "DS9's format characters: <b>+</b> plus sign, <b>z</b> leading zeros, "
                "<b>i</b>/<b>b</b>/<b>l</b> colon, blank or letter separators, "
                "<b>d</b>/<b>h</b> degrees or hours, <b>m</b>/<b>s</b> minutes and "
                "seconds, <b>.N</b> decimal places. Blank uses the default for the "
                "system."
            ),
        )
        layout.addWidget(formats)

        layout.addStretch()
        return page

    def _element_tab(self, name: str) -> QWidget:
        """One element: Show, colour, and either a line or a font."""
        element = self.config.element(name)
        page = QWidget()
        form = QFormLayout(page)

        show = QCheckBox()
        show.setChecked(element.show)
        self._widgets[f"{name}.show"] = show
        form.addRow("Show:", show)

        self._widgets[f"{name}.color"] = self._combo(COLORS, element.color)
        form.addRow("Colour:", self._widgets[f"{name}.color"])

        if name in LINE_ELEMENTS:
            self._widgets[f"{name}.width"] = self._combo(
                [str(width) for width in LINE_WIDTHS], str(element.width)
            )
            form.addRow("Width:", self._widgets[f"{name}.width"])
            self._widgets[f"{name}.style"] = self._combo(LINE_STYLES, element.style)
            form.addRow("Style:", self._widgets[f"{name}.style"])
        else:
            self._widgets[f"{name}.font"] = self._combo(FONTS, element.font)
            form.addRow("Font:", self._widgets[f"{name}.font"])
            self._widgets[f"{name}.font_size"] = self._combo(
                [str(size) for size in FONT_SIZES], str(element.font_size)
            )
            form.addRow("Size:", self._widgets[f"{name}.font_size"])
            self._widgets[f"{name}.font_weight"] = self._combo(FONT_WEIGHTS, element.font_weight)
            form.addRow("Weight:", self._widgets[f"{name}.font_weight"])
            self._widgets[f"{name}.font_slant"] = self._combo(FONT_SLANTS, element.font_slant)
            form.addRow("Slant:", self._widgets[f"{name}.font_slant"])

        return page

    @staticmethod
    def _combo(choices, current: str) -> QComboBox:
        """A combo of `choices` with `current` selected."""
        combo = QComboBox()
        combo.addItems([str(choice) for choice in choices])
        combo.setCurrentText(str(current))
        return combo

    # -- reading the dialog back ------------------------------------------------

    def gather(self) -> GridConfig:
        """Read every field back into the configuration."""
        config = self.config
        config.visible = self._show.isChecked()
        config.grid_type = GridType(self._widgets["grid_type"].currentText())
        config.axes_placement = Placement(self._widgets["axes_placement"].currentText())
        config.numerics_placement = Placement(self._widgets["numerics_placement"].currentText())
        config.vertical_text = self._widgets["vertical_text"].isChecked()

        config.title = self._widgets["title"].text()
        config.x_title = self._widgets["x_title"].text()
        config.y_title = self._widgets["y_title"].text()

        config.auto_spacing = self._widgets["auto_spacing"].isChecked()
        config.target_lines = self._widgets["target_lines"].value()
        # Zero is the spin box's "automatic": a grid line every nought
        # degrees is not a setting, it is an infinite loop.
        config.x_spacing = self._widgets["x_spacing"].value() or None
        config.y_spacing = self._widgets["y_spacing"].value() or None

        config.system = self._widgets["system"].currentText()
        config.sky = self._widgets["sky"].currentText()
        config.sky_format = self._widgets["sky_format"].currentText()
        config.x_format = self._widgets["x_format"].text()
        config.y_format = self._widgets["y_format"].text()

        for name in ELEMENTS:
            element = config.element(name)
            element.show = self._widgets[f"{name}.show"].isChecked()
            element.color = self._widgets[f"{name}.color"].currentText()
            if name in LINE_ELEMENTS:
                element.width = int(self._widgets[f"{name}.width"].currentText())
                element.style = self._widgets[f"{name}.style"].currentText()
            else:
                element.font = self._widgets[f"{name}.font"].currentText()
                element.font_size = int(self._widgets[f"{name}.font_size"].currentText())
                element.font_weight = self._widgets[f"{name}.font_weight"].currentText()
                element.font_slant = self._widgets[f"{name}.font_slant"].currentText()
        return config

    def apply(self) -> None:
        """Announce the settings without closing."""
        self.grid_changed.emit(self.gather().copy())

    def _accept(self) -> None:
        """Announce them and close."""
        self.apply()
        self.accept()

    # -- load and save (M7-13) ---------------------------------------------------

    def save(self) -> None:
        """Write the settings to a file."""
        path, _filter = QFileDialog.getSaveFileName(self, "Save Grid", "", GRID_FILTER)
        if not path:
            return
        try:
            self.gather().save(path)
        except OSError as exc:
            QMessageBox.warning(self, "Save Grid", str(exc))

    def load(self) -> None:
        """Read settings back from a file and show them.

        The dialog is rebuilt rather than updated field by field: there are
        fifty of them, and one missed would silently keep an old value.
        """
        path, _filter = QFileDialog.getOpenFileName(self, "Load Grid", "", GRID_FILTER)
        if not path:
            return
        try:
            loaded = GridConfig.load(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Load Grid", str(exc))
            return

        replacement = GridDialog(loaded, self.parentWidget())
        replacement.grid_changed.connect(self.grid_changed.emit)
        self.accept()
        replacement.show()
        self.grid_changed.emit(loaded.copy())
        self.status_path = Path(path)


def _hint(text: str) -> QWidget:
    """A wrapped italic note under a form row."""
    from PyQt6.QtWidgets import QLabel

    label = QLabel(text)
    label.setWordWrap(True)
    return label
