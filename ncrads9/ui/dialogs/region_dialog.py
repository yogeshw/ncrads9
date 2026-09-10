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
DS9's per-region Get Information dialog.

Double-clicking a region in DS9, or choosing Region -> Get Information, opens
a dialog showing that region's own parameters -- a circle's centre and radius,
a panda's angles and its two sets of radii -- with menus for the coordinate
system the positions are shown in and the format they are written in, plus
the region's colour, width, font and property flags.

The fields are read off each shape's constructor rather than listed here, so
a shape cannot gain a parameter the dialog does not show. That is the whole
reason this is one dialog and not nineteen: the shapes already declare what
they are made of, and `geometry_fields` just asks them.

What replaced what: this module used to hold a dialog that edited a plain
`dict` of nine hardcoded shape names and could not describe an annulus, a
panda or a segment, and nothing opened it (`test_no_orphan_modules` listed it
against M6-7). It edits `BaseRegion` now.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...coordinates.coord_system import CoordFrame, CoordinateContext, SkyFormat, SkyFrame
from ...coordinates.sexagesimal import parse_sexagesimal
from ...regions.base_region import BaseRegion
from ...regions.shapes.point import Point

#: Constructor parameters every shape shares; they are edited by the style
#: and property rows rather than as geometry.
COMMON_PARAMETERS: frozenset[str] = frozenset({"self", "color", "width", "font", "text", "tags", "kwargs"})

#: Geometry parameters holding one position, which the coordinate menus act on.
POSITION_PARAMETERS: frozenset[str] = frozenset({"center", "start", "end"})

#: Geometry parameters holding a list of positions.
PATH_PARAMETERS: frozenset[str] = frozenset({"vertices", "points"})

#: Parameters counted rather than measured, so no unit conversion applies.
COUNT_PARAMETERS: frozenset[str] = frozenset({"size"})

#: Labels DS9 uses where a bare attribute name would read badly.
FIELD_LABELS: dict[str, str] = {
    "center": "Center",
    "start": "Start",
    "end": "End",
    "radius": "Radius",
    "semi_major": "Semi-major",
    "semi_minor": "Semi-minor",
    "width_box": "Width",
    "height_box": "Height",
    "projection_width": "Thickness",
    "num_angles": "Angles",
    "num_radii": "Annuli",
    "label": "Text",
    "shape": "Point",
    "size": "Size",
}

#: The colours the Region -> Color cascade offers. Kept here rather than
#: imported from the menu so the dialog does not depend on the menu bar.
DIALOG_COLORS: tuple[str, ...] = (
    "black",
    "white",
    "red",
    "green",
    "blue",
    "cyan",
    "magenta",
    "yellow",
)

#: The line widths the Width cascade offers.
DIALOG_WIDTHS: tuple[int, ...] = (1, 2, 3, 4)

#: The fonts and sizes the Font cascade offers.
DIALOG_FONTS: tuple[str, ...] = ("helvetica", "times", "courier")
DIALOG_FONT_SIZES: tuple[int, ...] = (9, 10, 12, 14, 16, 18, 24)

#: DS9's region property flags: the attribute, and the label the menu uses.
DIALOG_PROPERTIES: tuple[tuple[str, str], ...] = (
    ("fixed", "Fixed in Size"),
    ("can_edit", "Edit"),
    ("can_move", "Move"),
    ("can_rotate", "Rotate"),
    ("can_delete", "Delete"),
    ("include", "Include"),
    ("source", "Source"),
    ("dash", "Dash"),
    ("fill", "Fill"),
)

#: The pixel systems, then the sky frames. A sky frame is only offered when
#: the frame has a WCS to convert through.
PIXEL_SYSTEMS: tuple[str, ...] = ("image", "physical")


@dataclass(frozen=True)
class Field:
    """One geometry parameter of a shape, and how to edit it.

    Attributes:
        name: The attribute on the region.
        label: What the dialog calls it.
        kind: One of "position", "path", "length", "angle", "count",
            "flag", "choice" or "text" -- which decides both the widget and
            whether a coordinate conversion applies.
        choices: The allowed values, for a "choice" field.
    """

    name: str
    label: str
    kind: str
    choices: tuple[str, ...] = ()


def field_kind(name: str, value: Any) -> str:
    """Classify one constructor parameter by its name and current value."""
    if name in POSITION_PARAMETERS:
        return "position"
    if name in PATH_PARAMETERS:
        return "path"
    if isinstance(value, bool):
        return "flag"
    if name == "shape":
        return "choice"
    if isinstance(value, str):
        return "text"
    if name.endswith("angle"):
        return "angle"
    if name.startswith("num_") or name in COUNT_PARAMETERS:
        return "count"
    return "length"


def geometry_fields(region: BaseRegion) -> list[Field]:
    """The parameters that make one shape what it is, in declaration order.

    Read off the shape's own `__init__` rather than from a table per shape:
    a table would let a shape gain a parameter the dialog never shows, which
    is the failure this dialog exists to avoid.
    """
    fields: list[Field] = []
    for name in inspect.signature(type(region).__init__).parameters:
        if name in COMMON_PARAMETERS:
            continue
        value = getattr(region, name, None)
        if value is None:
            continue
        label = FIELD_LABELS.get(name, name.replace("_", " ").capitalize())
        choices = tuple(Point.SHAPES) if name == "shape" else ()
        fields.append(Field(name, label, field_kind(name, value), choices))
    return fields


def parse_pair(text: str) -> tuple[float, float] | None:
    """Read a position back from the dialog.

    Accepts the two forms the dialog can show: plain numbers, and the
    sexagesimal pair a sky frame is written in. Returns None rather than
    raising, so a half-typed field leaves the region alone instead of
    throwing a dialog in the user's face on every keystroke.
    """
    tokens = text.replace(",", " ").split()
    if len(tokens) == 2:
        try:
            return (parse_sexagesimal(tokens[0])[0], parse_sexagesimal(tokens[1])[0])
        except ValueError:
            return None
    if len(tokens) == 6:
        # "hh mm ss dd mm ss", which is how a sexagesimal pair looks when it
        # is typed with spaces instead of colons.
        first, second = " ".join(tokens[:3]), " ".join(tokens[3:])
        try:
            return (parse_sexagesimal(first)[0], parse_sexagesimal(second)[0])
        except ValueError:
            return None
    return None


class RegionDialog(QDialog):
    """DS9's Get Information dialog for one region.

    Args:
        region: The region to show. Its own parameters decide the fields.
        wcs_handler: The frame's WCS, used to offer sky coordinate systems
            and to convert into them. Without one only the pixel systems
            are offered, which is what DS9 does for an image with no WCS.
        parent: Optional parent widget.
    """

    #: Emitted with the region after Apply, so the overlay can redraw.
    region_changed = pyqtSignal(object)
    #: Emitted with the region when Delete is pressed.
    region_deleted = pyqtSignal(object)

    def __init__(
        self,
        region: BaseRegion,
        wcs_handler: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.region = region
        self.wcs_handler = wcs_handler
        self.setWindowTitle(type(region).__name__)

        self._fields = geometry_fields(region)
        self._editors: dict[str, QWidget] = {}
        self._property_boxes: dict[str, QCheckBox] = {}
        self._context = CoordinateContext.from_names(frame="image")

        self._build()
        self.load()

    # -- construction --------------------------------------------------------

    @property
    def has_wcs(self) -> bool:
        """Whether a sky coordinate system can be offered."""
        return bool(self.wcs_handler is not None and getattr(self.wcs_handler, "is_valid", False))

    def systems(self) -> tuple[str, ...]:
        """The coordinate systems this region's frame can offer."""
        if not self.has_wcs:
            return PIXEL_SYSTEMS
        return PIXEL_SYSTEMS + tuple(frame.value for frame in SkyFrame)

    def _build(self) -> None:
        """Lay the dialog out: coordinates, geometry, style, properties."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{type(self.region).__name__}</b>"))

        text_row = QFormLayout()
        self._text = QLineEdit()
        text_row.addRow("Id:", self._text)
        layout.addLayout(text_row)

        layout.addWidget(self._coordinate_group())
        layout.addWidget(self._geometry_group())
        layout.addWidget(self._style_group())
        layout.addWidget(self._property_group())
        layout.addWidget(self._buttons())

    def _coordinate_group(self) -> QGroupBox:
        """The system and format menus, which restate every position."""
        group = QGroupBox("Coordinates")
        form = QFormLayout(group)

        self._system = QComboBox()
        self._system.addItems(self.systems())
        self._system.currentTextChanged.connect(self._on_system_changed)
        form.addRow("System:", self._system)

        self._format = QComboBox()
        self._format.addItems([choice.value for choice in SkyFormat])
        self._format.setCurrentText(SkyFormat.SEXAGESIMAL.value)
        self._format.setEnabled(False)
        self._format.currentTextChanged.connect(lambda _text: self.load_geometry())
        form.addRow("Format:", self._format)
        return group

    def _geometry_group(self) -> QGroupBox:
        """One row per parameter the shape declares."""
        group = QGroupBox("Parameters")
        form = QFormLayout(group)
        for field in self._fields:
            editor = self._editor_for(field)
            self._editors[field.name] = editor
            form.addRow(f"{field.label}:", editor)
        return group

    def _editor_for(self, field: Field) -> QWidget:
        """The widget one field is edited through."""
        if field.kind == "path":
            editor = QPlainTextEdit()
            editor.setPlaceholderText("one x y per line")
            return editor
        if field.kind == "flag":
            return QCheckBox()
        if field.kind == "choice":
            box = QComboBox()
            box.addItems(field.choices)
            return box
        return QLineEdit()

    def _style_group(self) -> QGroupBox:
        """Colour, width and font: the same choices the Region menu offers."""
        group = QGroupBox("Style")
        form = QFormLayout(group)

        self._color = QComboBox()
        self._color.addItems(DIALOG_COLORS)
        form.addRow("Color:", self._color)

        self._width = QComboBox()
        self._width.addItems([str(width) for width in DIALOG_WIDTHS])
        form.addRow("Width:", self._width)

        fonts = QHBoxLayout()
        self._font = QComboBox()
        self._font.addItems(DIALOG_FONTS)
        fonts.addWidget(self._font)
        self._font_size = QComboBox()
        self._font_size.addItems([str(size) for size in DIALOG_FONT_SIZES])
        fonts.addWidget(self._font_size)
        holder = QWidget()
        holder.setLayout(fonts)
        form.addRow("Font:", holder)
        return group

    def _property_group(self) -> QGroupBox:
        """DS9's nine property flags, as checkboxes."""
        group = QGroupBox("Properties")
        form = QFormLayout(group)
        for attribute, label in DIALOG_PROPERTIES:
            box = QCheckBox(label)
            self._property_boxes[attribute] = box
            form.addRow("", box)
        return group

    def _buttons(self) -> QWidget:
        """Apply, Close and Delete, as DS9's region dialogs have."""
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)

        delete = QPushButton("Delete")
        delete.clicked.connect(self._delete)
        buttons.addButton(delete, QDialogButtonBox.ButtonRole.DestructiveRole)
        return buttons

    # -- coordinates ---------------------------------------------------------

    def _on_system_changed(self, name: str) -> None:
        """Switch the system the positions are shown in."""
        if name in PIXEL_SYSTEMS:
            self._context = CoordinateContext.from_names(frame=name)
            self._format.setEnabled(False)
        else:
            self._context = CoordinateContext.from_names(
                frame="wcs", sky=name, sky_format=self._format.currentText()
            )
            self._format.setEnabled(True)
        self.load_geometry()

    def format_position(self, x: float, y: float) -> str:
        """Write one image position in the chosen system and format."""
        if self._context.frame is not CoordFrame.WCS:
            return f"{x:g} {y:g}"
        context = self._context.with_format(self._format.currentText())
        lon, lat = self.wcs_handler.pixel_to_world(x, y)
        first, second = context.format_pair(*context.transform(lon, lat))
        return f"{first} {second}"

    def read_position(self, text: str) -> tuple[float, float] | None:
        """Read a position back, converting from the chosen system.

        Returns None when the text is not a position, which leaves the
        region's own value alone.
        """
        pair = parse_pair(text)
        if pair is None:
            return None
        if self._context.frame is not CoordFrame.WCS:
            return pair
        x, y = self.wcs_handler.world_to_pixel(*pair)
        return (float(x), float(y))

    # -- loading and applying ------------------------------------------------

    def load(self) -> None:
        """Fill every field from the region."""
        self._text.setText(self.region.text or "")
        self._color.setCurrentText(self.region.color)
        self._width.setCurrentText(str(self.region.width))
        family, size = self._font_of(self.region)
        self._font.setCurrentText(family)
        self._font_size.setCurrentText(str(size))
        for attribute, box in self._property_boxes.items():
            box.setChecked(bool(getattr(self.region, attribute, False)))
        self.load_geometry()

    @staticmethod
    def _font_of(region: BaseRegion) -> tuple[str, int]:
        """Split a DS9 font string, e.g. "helvetica 10 normal roman"."""
        parts = str(region.font).split()
        family = parts[0] if parts else DIALOG_FONTS[0]
        try:
            size = int(parts[1])
        except (IndexError, ValueError):
            size = DIALOG_FONT_SIZES[1]
        return family, size

    def load_geometry(self) -> None:
        """Restate every geometry field, in the current coordinate system."""
        for field in self._fields:
            editor = self._editors[field.name]
            value = getattr(self.region, field.name)
            if field.kind == "position":
                editor.setText(self.format_position(*value))
            elif field.kind == "path":
                editor.setPlainText("\n".join(self.format_position(x, y) for x, y in value))
            elif field.kind == "flag":
                editor.setChecked(bool(value))
            elif field.kind == "choice":
                editor.setCurrentText(str(value))
            elif field.kind == "text":
                editor.setText(str(value))
            elif field.kind == "count":
                editor.setText(str(int(value)))
            else:
                editor.setText(f"{float(value):g}")

    def apply(self) -> None:
        """Write every field back onto the region and announce the change."""
        self.region.text = self._text.text()
        self.region.color = self._color.currentText()
        self.region.width = int(self._width.currentText())
        self.region.font = f"{self._font.currentText()} {self._font_size.currentText()} normal roman"
        for attribute, box in self._property_boxes.items():
            if hasattr(self.region, attribute):
                setattr(self.region, attribute, box.isChecked())
        self.apply_geometry()
        self.region_changed.emit(self.region)

    def apply_geometry(self) -> None:
        """Write the geometry fields back, skipping any that will not parse.

        A field that cannot be read is left as the region already has it:
        an unparseable radius must not silently become zero.
        """
        for field in self._fields:
            editor = self._editors[field.name]
            if field.kind == "position":
                position = self.read_position(editor.text())
                if position is not None:
                    setattr(self.region, field.name, position)
            elif field.kind == "path":
                path = [
                    point
                    for point in (self.read_position(line) for line in editor.toPlainText().splitlines())
                    if point is not None
                ]
                if len(path) >= 2:
                    setattr(self.region, field.name, path)
            elif field.kind == "flag":
                setattr(self.region, field.name, editor.isChecked())
            elif field.kind == "choice":
                setattr(self.region, field.name, editor.currentText())
            elif field.kind == "text":
                setattr(self.region, field.name, editor.text())
            elif field.kind == "count":
                self._set_number(field.name, editor.text(), int)
            else:
                self._set_number(field.name, editor.text(), float)

    def _set_number(self, name: str, text: str, cast) -> None:
        """Set one numeric attribute, ignoring text that is not a number."""
        try:
            setattr(self.region, name, cast(float(text)))
        except (TypeError, ValueError):
            return

    def _delete(self) -> None:
        """Ask for the region to be deleted, if it allows it."""
        if not self.region.can_delete:
            return
        self.region_deleted.emit(self.region)
        self.accept()
