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

Positions take DS9's `CoordMenuButton` choices -- `wcs` and any alternate
`wcsa`..`wcsz` the header carries, image or physical, a sky frame and a
format -- and lengths its `DistMenuButton` ones: image, physical, or
degrees, arcminutes or arcseconds through a WCS. An annulus or a panda gets
DS9's radii list with Inner, Outer, Annuli and Generate
(`markerbaseannulus.tcl`). The region controller reloads an open dialog
whenever its region is dragged or reshaped on the canvas, so Apply never
snaps a moved region back to where the dialog last saw it.

What replaced what: this module used to hold a dialog that edited a plain
`dict` of nine hardcoded shape names and could not describe an annulus, a
panda or a segment, and nothing opened it (`test_no_orphan_modules` listed it
against M6-7). It edits `BaseRegion` now.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenuBar,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...coordinates import positions
from ...coordinates.sexagesimal import parse_sexagesimal
from ...regions.base_region import BaseRegion
from ...regions.shapes.annulus import Annulus, generate_radii
from ...regions.shapes.point import Point
from ..widgets.coord_menu_button import WCS_LETTERS, CoordMenuButton, DistMenuButton

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
    "radii": "Radii",
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

#: DS9's Analysis menu, in its order: name and label.
ANALYSIS_COMMANDS: tuple[tuple[str, str], ...] = (
    ("statistics", "&Statistics"),
    ("histogram", "&Histogram"),
    ("radial", "&Radial Profile"),
    ("plot2d", "Plot &2D"),
    ("plot3d", "Plot &3D"),
)

#: Shapes with annuli, which are the ones a radial profile means anything for.
ANNULAR_NAMES: frozenset[str] = frozenset(
    {"annulus", "ellipseannulus", "boxannulus", "panda", "epanda", "bpanda"}
)

#: Shapes that are a line, which are the ones a 2D cut can be taken along.
LINEAR_NAMES: frozenset[str] = frozenset({"line", "ruler", "projection", "vector", "segment"})

#: Shapes with no interior, so nothing to sum: no statistics, no histogram.
HOLLOW_NAMES: frozenset[str] = frozenset(
    {"text", "point", "compass", "line", "ruler", "projection", "vector", "segment"}
)


def analysis_commands_for(region: BaseRegion) -> tuple[str, ...]:
    """Which Analysis entries a shape gets."""
    name = type(region).__name__.lower()
    offered: list[str] = []
    if name not in HOLLOW_NAMES:
        offered.extend(("statistics", "histogram"))
    if name in ANNULAR_NAMES:
        offered.append("radial")
    if name in LINEAR_NAMES:
        offered.append("plot2d")
    if name not in HOLLOW_NAMES:
        offered.append("plot3d")
    return tuple(offered)


#: The pixel systems. The WCS systems the frame has -- `wcs`, and `wcsa`..
#: `wcsz` when its header carries them -- come first, as in DS9's menu.
PIXEL_SYSTEMS: tuple[str, ...] = ("image", "physical")

#: Where DS9's marker dialogs start: `marker(dialog,system)` is physical
#: (`marker.tcl`), which is image for a file with no LTV/LTM keywords.
DIALOG_SYSTEM = "physical"

#: Significant digits a dialog writes a number with, so a value shown and
#: applied unchanged lands back on the same pixel.
DIALOG_DIGITS = 10

#: The entry at the foot of the colour list that opens a colour chooser.
OTHER_COLOR = "Other..."

#: DS9's font weights and slants.
FONT_WEIGHTS: tuple[str, ...] = ("normal", "bold")
FONT_SLANTS: tuple[str, ...] = ("roman", "italic")

#: The radii Generate methods (`markerbaseannulus.tcl` Method menu).
GENERATE_METHODS: tuple[tuple[str, str], ...] = (("dist", "Equal Distance"), ("area", "Equal Area"))

#: Shapes whose radii are edited as a list with Generate: the attributes
#: holding the inner and outer radius and the ring count, when there is one.
RADII_SHAPES: dict[str, tuple[str, str, str | None]] = {
    "annulus": ("inner_radius", "outer_radius", None),
    "panda": ("inner_radius", "outer_radius", "num_radii"),
    "epanda": ("inner_major", "outer_major", "num_radii"),
    "bpanda": ("inner_major", "outer_major", "num_radii"),
}


@dataclass(frozen=True)
class Field:
    """One geometry parameter of a shape, and how to edit it.

    Attributes:
        name: The attribute on the region.
        label: What the dialog calls it.
        kind: One of "position", "path", "length", "radii", "angle",
            "count", "flag", "choice" or "text" -- which decides both the
            widget and whether a coordinate conversion applies.
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
    if name == "radii":
        return "radii"
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


def parse_numbers(text: str) -> list[float] | None:
    """Every number in a list typed one per line, or None if any is not."""
    try:
        values = [float(token) for token in text.replace(",", " ").split()]
    except ValueError:
        return None
    return values


class RegionDialog(QDialog):
    """DS9's Get Information dialog for one region.

    Args:
        region: The region to show. Its own parameters decide the fields.
        wcs_handler: The frame's WCS, used to offer sky coordinate systems
            and to convert into them. Without one only the pixel systems
            are offered, which is what DS9 does for an image with no WCS.
        parent: Optional parent widget.
        frame: The frame the region is on. When given, its header supplies
            the physical transform and any alternate WCS (`wcsa`..`wcsz`).
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
        frame: Any = None,
    ) -> None:
        super().__init__(parent)
        self.region = region
        if frame is None:
            frame = SimpleNamespace(wcs_handler=wcs_handler, header=None)
        elif wcs_handler is None:
            wcs_handler = getattr(frame, "wcs_handler", None)
        self.frame = frame
        self.wcs_handler = wcs_handler
        self.setWindowTitle(type(region).__name__)

        self._fields = geometry_fields(region)
        self._editors: dict[str, QWidget] = {}
        self._property_boxes: dict[str, QCheckBox] = {}
        #: What the radii list showed when last loaded, so Apply can tell
        #: an edit of the list from an edit of the inner and outer radius.
        self._loaded_radii = ""

        self._build()
        self.load()

    # -- construction --------------------------------------------------------

    @property
    def has_wcs(self) -> bool:
        """Whether a sky coordinate system can be offered."""
        return bool(self.wcs_systems())

    def _has(self, system: str) -> bool:
        """Whether the frame carries a celestial WCS of that name."""
        try:
            handler = positions.wcs_handler(self.frame, system)
        except Exception:
            return False
        return bool(getattr(handler, "is_valid", False))

    def wcs_systems(self) -> tuple[str, ...]:
        """The frame's WCS systems: `wcs`, then `wcsa`..`wcsz`."""
        names = ("wcs", *(f"wcs{letter}" for letter in WCS_LETTERS))
        header = getattr(self.frame, "header", None)
        found = []
        for name in names:
            if name != "wcs":
                try:
                    if header is None or f"CTYPE1{name[3:].upper()}" not in header:
                        continue
                except TypeError:
                    continue
            if self._has(name):
                found.append(name)
        return tuple(found)

    def systems(self) -> tuple[str, ...]:
        """The coordinate systems this region's frame can offer."""
        return self.wcs_systems() + PIXEL_SYSTEMS

    def _build(self) -> None:
        """Lay the dialog out: coordinates, geometry, style, properties."""
        layout = QVBoxLayout(self)
        layout.setMenuBar(self._menu_bar())
        layout.addWidget(QLabel(f"<b>{type(self.region).__name__}</b>"))

        text_row = QFormLayout()
        self._text = QLineEdit()
        text_row.addRow("Id:", self._text)
        layout.addLayout(text_row)

        layout.addWidget(self._coordinate_group())
        layout.addWidget(self._geometry_group())
        if self._radii_spec() is not None:
            layout.addWidget(self._radii_group())
        layout.addWidget(self._style_group())
        layout.addWidget(self._property_group())
        layout.addWidget(self._buttons())

    def _menu_bar(self) -> QMenuBar:
        """The Analysis menu DS9 puts on every region dialog.

        Which entries a shape gets is DS9's rule, not a uniform list: a
        radial profile needs annuli (`annulus.tcl:47`), a 2D cut needs a
        line (`line.tcl:36`), a 3D plot needs an area to sum over
        (`circle.tcl:39`). An entry that could only ever report "this shape
        cannot do that" is not offered at all.
        """
        bar = QMenuBar(self)
        menu = bar.addMenu("&Analysis")

        #: Analysis command name -> its action, for the controller to wire.
        self.analysis_actions: dict[str, QAction] = {}
        for name, label in ANALYSIS_COMMANDS:
            if name not in analysis_commands_for(self.region):
                continue
            action = QAction(label, self)
            menu.addAction(action)
            self.analysis_actions[name] = action

        menu.setEnabled(bool(self.analysis_actions))
        return bar

    def _coordinate_group(self) -> QGroupBox:
        """DS9's `CoordMenuButton` and `DistMenuButton`, the shared widgets.

        Positions take a system, a sky frame and a format; distances take a
        system and, through a WCS, a unit -- degrees, arcmin or arcsec.
        """
        group = QGroupBox("Coordinates")
        form = QFormLayout(group)

        self._coord = CoordMenuButton(self, other=1, system=DIALOG_SYSTEM)
        self._coord.set_sky_format("sexagesimal")
        self._coord.adjust(self._has, DIALOG_SYSTEM, self._has)
        self._coord.changed.connect(self._on_system_changed)
        form.addRow("Position:", self._coord)

        self._dist = DistMenuButton(self, other=True, system=DIALOG_SYSTEM)
        self._dist.set_distance_format("arcsec")
        self._dist.adjust(self._has, DIALOG_SYSTEM, self._has)
        self._dist.changed.connect(self._on_system_changed)
        form.addRow("Distance:", self._dist)
        return group

    @staticmethod
    def _holder(row: QHBoxLayout) -> QWidget:
        row.setContentsMargins(0, 0, 0, 0)
        holder = QWidget()
        holder.setLayout(row)
        return holder

    def _geometry_group(self) -> QGroupBox:
        """One row per parameter the shape declares."""
        group = QGroupBox("Parameters")
        form = QFormLayout(group)
        for field in self._fields:
            editor = self._editor_for(field)
            self._editors[field.name] = editor
            if field.kind != "radii":
                form.addRow(f"{field.label}:", editor)
        return group

    def _editor_for(self, field: Field) -> QWidget:
        """The widget one field is edited through."""
        if field.kind == "path":
            editor = QPlainTextEdit()
            editor.setPlaceholderText("one x y per line")
            return editor
        if field.kind == "radii":
            return self._radii_text()
        if field.kind == "flag":
            return QCheckBox()
        if field.kind == "choice":
            box = QComboBox()
            box.addItems(field.choices)
            return box
        return QLineEdit()

    def _radii_spec(self) -> tuple[str, str, str | None] | None:
        """The inner, outer and count attributes, for a shape with radii."""
        return RADII_SHAPES.get(type(self.region).__name__.lower())

    def _radii_text(self) -> QPlainTextEdit:
        """The one radii list, made on first asking."""
        if getattr(self, "_radii", None) is None:
            self._radii = QPlainTextEdit()
            self._radii.setPlaceholderText("one radius per line")
        return self._radii

    def _radii_group(self) -> QGroupBox:
        """DS9's annulus dialog: Inner, Outer, Annuli, Generate and the list.

        Generate fills the list from the three numbers
        (`MarkerBaseAnnulusGenerateCircle`), in the distance unit shown.
        """
        group = QGroupBox("Radii")
        form = QFormLayout(group)
        self._generate_inner = QLineEdit()
        self._generate_outer = QLineEdit()
        self._generate_count = QSpinBox()
        self._generate_count.setRange(1, 999)
        self._generate_method = QComboBox()
        for value, label in GENERATE_METHODS:
            self._generate_method.addItem(label, value)
        generate = QPushButton("Generate")
        generate.clicked.connect(self.generate)

        form.addRow("Inner:", self._generate_inner)
        form.addRow("Outer:", self._generate_outer)
        form.addRow("Annuli:", self._generate_count)
        form.addRow("Method:", self._generate_method)
        form.addRow("", generate)
        form.addRow("Radii:", self._radii_text())
        return group

    def _style_group(self) -> QGroupBox:
        """Colour, width and font: the same choices the Region menu offers."""
        group = QGroupBox("Style")
        form = QFormLayout(group)

        self._color = QComboBox()
        self._color.addItems(DIALOG_COLORS)
        self._color.addItem(OTHER_COLOR)
        self._color.activated.connect(self._on_color_activated)
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
        self._font_weight = QComboBox()
        self._font_weight.addItems(FONT_WEIGHTS)
        fonts.addWidget(self._font_weight)
        self._font_slant = QComboBox()
        self._font_slant.addItems(FONT_SLANTS)
        fonts.addWidget(self._font_slant)
        form.addRow("Font:", self._holder(fonts))
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

    # -- colour --------------------------------------------------------------

    def _set_color(self, name: str) -> None:
        """Show a colour, adding it above Other... if the list lacks it."""
        if self._color.findText(name) < 0:
            self._color.insertItem(self._color.count() - 1, name)
        self._color.setCurrentText(name)

    def _on_color_activated(self, index: int) -> None:
        """Other... opens a colour chooser, as DS9's colour menu does."""
        if self._color.itemText(index) != OTHER_COLOR:
            return
        chosen = QColorDialog.getColor(QColor(str(self.region.color)), self, "Color")
        if chosen.isValid():
            self._set_color(chosen.name())
        else:
            self._set_color(str(self.region.color))

    # -- coordinates ---------------------------------------------------------

    def _on_system_changed(self) -> None:
        """Restate every field in the systems now chosen.

        The menus are adjusted again first, so the sky frame and unit
        entries are live exactly when a WCS is chosen.
        """
        self._coord.adjust(self._has, DIALOG_SYSTEM, self._has)
        self._dist.adjust(self._has, DIALOG_SYSTEM, self._has)
        self.load_geometry()

    def format_position(self, x: float, y: float) -> str:
        """Write one image position in the chosen system and format."""
        coord = self._coord
        return positions.from_image(
            self.frame, x, y, coord.system, coord.sky, coord.sky_format, digits=DIALOG_DIGITS
        )

    def read_position(self, text: str) -> tuple[float, float] | None:
        """Read a position back, converting from the chosen system.

        Returns None when the text is not a position, which leaves the
        region's own value alone.
        """
        words = text.replace(",", " ").split()
        if len(words) == 6:
            words = [":".join(words[:3]), ":".join(words[3:])]
        if len(words) != 2:
            return None
        try:
            return positions.to_image(self.frame, words[0], words[1], self._coord.system, self._coord.sky)
        except Exception:
            return None

    def format_length(self, value: float) -> str:
        """Write a length in image pixels in the chosen distance system."""
        shown, _ = positions.distance_from_image(
            self.frame, value, value, self._dist.system, self._dist.distance_format
        )
        return f"{shown:.{DIALOG_DIGITS}g}"

    def read_length(self, text: str) -> float | None:
        """Read a length back into image pixels, or None if it is not one."""
        try:
            value = float(text)
            pixels, _ = positions.distance_to_image(
                self.frame, value, value, self._dist.system, self._dist.distance_format
            )
        except (TypeError, ValueError):
            return None
        return pixels

    # -- radii -----------------------------------------------------------------

    def region_radii(self) -> list[float]:
        """The region's radii in image pixels, smallest first."""
        if isinstance(self.region, Annulus):
            return self.region.radii
        inner_name, outer_name, count_name = self._radii_spec()
        inner = float(getattr(self.region, inner_name))
        outer = float(getattr(self.region, outer_name))
        count = int(getattr(self.region, count_name)) if count_name else 1
        return generate_radii(inner, outer, count)

    def generate(self) -> None:
        """Fill the radii list from Inner, Outer and Annuli: DS9's Generate."""
        try:
            inner = float(self._generate_inner.text())
            outer = float(self._generate_outer.text())
        except ValueError:
            return
        radii = generate_radii(
            inner, outer, self._generate_count.value(), self._generate_method.currentData()
        )
        self._radii_text().setPlainText("\n".join(f"{radius:.8g}" for radius in radii))

    def _load_radii(self) -> None:
        if self._radii_spec() is None:
            return
        radii = self.region_radii()
        self._generate_inner.setText(self.format_length(radii[0]))
        self._generate_outer.setText(self.format_length(radii[-1]))
        self._generate_count.setValue(max(1, len(radii) - 1))
        self._loaded_radii = "\n".join(self.format_length(radius) for radius in radii)
        self._radii_text().setPlainText(self._loaded_radii)

    def _apply_radii(self) -> None:
        """Write an edited radii list back, if it was edited.

        An annulus keeps any list. A panda's radii are evenly spaced by
        definition (`panda(x,y,a1,a2,na,r1,r2,nr)`), so a list sets its ends
        and its count; an elliptical or box panda keeps its axis ratio.
        """
        if self._radii_spec() is None:
            return
        text = self._radii_text().toPlainText()
        if text.strip() == self._loaded_radii.strip():
            return
        values = parse_numbers(text)
        if values is None or len(values) < 2:
            return
        radii = [self.read_length(str(value)) for value in values]
        if any(radius is None for radius in radii):
            return
        radii = sorted(radii)
        if isinstance(self.region, Annulus):
            self.region.radii = radii
            return
        inner_name, outer_name, count_name = self._radii_spec()
        if inner_name == "inner_major":
            for major, minor in (("inner_major", "inner_minor"), ("outer_major", "outer_minor")):
                old = float(getattr(self.region, major)) or 1.0
                new = radii[0] if major == "inner_major" else radii[-1]
                setattr(self.region, minor, float(getattr(self.region, minor)) * new / old)
        setattr(self.region, inner_name, radii[0])
        setattr(self.region, outer_name, radii[-1])
        if count_name:
            setattr(self.region, count_name, len(radii) - 1)

    # -- loading and applying ------------------------------------------------

    def load(self) -> None:
        """Fill every field from the region."""
        self._text.setText(self.region.text or "")
        self._set_color(str(self.region.color))
        self._width.setCurrentText(str(self.region.width))
        family, size, weight, slant = self._font_of(self.region)
        self._font.setCurrentText(family)
        self._font_size.setCurrentText(str(size))
        self._font_weight.setCurrentText(weight)
        self._font_slant.setCurrentText(slant)
        for attribute, box in self._property_boxes.items():
            box.setChecked(bool(getattr(self.region, attribute, False)))
        self.load_geometry()

    @staticmethod
    def _font_of(region: BaseRegion) -> tuple[str, int, str, str]:
        """Split a DS9 font string, e.g. "helvetica 10 bold italic"."""
        parts = str(region.font).split()
        family = parts[0] if parts else DIALOG_FONTS[0]
        try:
            size = int(parts[1])
        except (IndexError, ValueError):
            size = DIALOG_FONT_SIZES[1]
        weight = next((part for part in parts[2:] if part in FONT_WEIGHTS), FONT_WEIGHTS[0])
        slant = next((part for part in parts[2:] if part in FONT_SLANTS), FONT_SLANTS[0])
        return family, size, weight, slant

    def load_geometry(self) -> None:
        """Restate every geometry field, in the current coordinate system."""
        for field in self._fields:
            editor = self._editors[field.name]
            value = getattr(self.region, field.name)
            if field.kind == "position":
                editor.setText(self.format_position(*value))
            elif field.kind == "path":
                editor.setPlainText("\n".join(self.format_position(x, y) for x, y in value))
            elif field.kind == "radii":
                continue
            elif field.kind == "flag":
                editor.setChecked(bool(value))
            elif field.kind == "choice":
                editor.setCurrentText(str(value))
            elif field.kind == "text":
                editor.setText(str(value))
            elif field.kind == "count":
                editor.setText(str(int(value)))
            elif field.kind == "length":
                editor.setText(self.format_length(float(value)))
            else:
                editor.setText(f"{float(value):g}")
        self._load_radii()

    def apply(self) -> None:
        """Write every field back onto the region and announce the change."""
        self.region.text = self._text.text()
        color = self._color.currentText()
        if color != OTHER_COLOR:
            self.region.color = color
        self.region.width = int(self._width.currentText())
        self.region.font = (
            f"{self._font.currentText()} {self._font_size.currentText()} "
            f"{self._font_weight.currentText()} {self._font_slant.currentText()}"
        )
        for attribute, box in self._property_boxes.items():
            if hasattr(self.region, attribute):
                setattr(self.region, attribute, box.isChecked())
        self.apply_geometry()
        self.region_changed.emit(self.region)
        # Show what the region now holds, in the systems chosen: a value
        # the region refused is put back rather than left looking applied.
        self.load_geometry()

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
            elif field.kind == "radii":
                continue
            elif field.kind == "flag":
                setattr(self.region, field.name, editor.isChecked())
            elif field.kind == "choice":
                setattr(self.region, field.name, editor.currentText())
            elif field.kind == "text":
                setattr(self.region, field.name, editor.text())
            elif field.kind == "count":
                self._set_number(field.name, editor.text(), int)
            elif field.kind == "length":
                length = self.read_length(editor.text())
                if length is not None:
                    setattr(self.region, field.name, length)
            else:
                self._set_number(field.name, editor.text(), float)
        self._apply_radii()

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
