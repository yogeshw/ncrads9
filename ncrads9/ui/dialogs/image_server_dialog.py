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
The dialog every image server shares, as DS9's `imgsvr.tcl` is shared.

Object name or coordinates, a size, and a survey where the server offers a
choice. One dialog for all nine, because the only thing that differs between
them is the survey list and the unit the size is in -- and both come off the
server's own description.

The size unit is shown rather than assumed: asking for "10" from SkyView and
from STScI means ten degrees at one and ten arcminutes at the other, and a
dialog that did not say so would hand back a field 36 times too big.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...image_servers.servers import ImageServer, SizeUnit

#: The default cutout size in each unit -- a sensible field, not a survey.
DEFAULT_SIZE = {SizeUnit.DEGREES: 0.25, SizeUnit.ARCMIN: 15.0, SizeUnit.PIXELS: 512.0}

#: SkyView's output image size, and the largest it will make.
DEFAULT_PIXELS = 512
MAX_PIXELS = 4096

#: What one of DS9's size units is in degrees.
_TO_DEGREES = {"degrees": 1.0, "arcmins": 1.0 / 60.0, "arcsecs": 1.0 / 3600.0}

#: The largest size the dialog offers, per unit.
MAX_SIZE = {SizeUnit.DEGREES: 10.0, SizeUnit.ARCMIN: 600.0, SizeUnit.PIXELS: 4096.0}


class ImageServerDialog(QDialog):
    """Ask where and how big a cutout to fetch.

    Args:
        server: Which server. Its survey list and size unit shape the
            dialog.
        center: The current frame's centre as (longitude, latitude) in
            degrees, offered as the default position.
        parent: Optional parent widget.
    """

    #: Emitted with (longitude, latitude, width, height, survey) on Retrieve.
    #: The pixel size, which only SkyView has, is read off the dialog by
    #: the controller rather than carried here -- a signal that most
    #: servers would fill with a placeholder is worse than a lookup.
    retrieve_requested = pyqtSignal(float, float, float, float, str)
    #: Emitted with an object name to resolve, when one was typed.
    name_requested = pyqtSignal(str)

    def __init__(
        self,
        server: ImageServer,
        center: tuple[float, float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.server = server
        self.setWindowTitle(server.label)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._by_name = QRadioButton("Object name")
        self._by_coordinates = QRadioButton("Coordinates")
        self._by_coordinates.setChecked(center is not None)
        self._by_name.setChecked(center is None)
        form.addRow(self._by_name, self._by_coordinates)

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. M51")
        self._name.returnPressed.connect(self.resolve)
        form.addRow("Name:", self._name)

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

        unit = server.size_unit
        self._width = QDoubleSpinBox()
        self._width.setRange(0.001, MAX_SIZE[unit])
        self._width.setDecimals(4)
        self._width.setValue(DEFAULT_SIZE[unit])
        form.addRow(f"Width ({unit.value}):", self._width)

        self._height = QDoubleSpinBox()
        self._height.setRange(0.001, MAX_SIZE[unit])
        self._height.setDecimals(4)
        self._height.setValue(DEFAULT_SIZE[unit])
        form.addRow(f"Height ({unit.value}):", self._height)

        # SkyView asks for the sky size in degrees and the image size in
        # pixels separately; the other servers derive one from the other.
        self._pixels: tuple[QSpinBox, QSpinBox] | None = None
        if server.takes_pixels:
            across = QSpinBox()
            across.setRange(1, MAX_PIXELS)
            across.setValue(DEFAULT_PIXELS)
            down = QSpinBox()
            down.setRange(1, MAX_PIXELS)
            down.setValue(DEFAULT_PIXELS)
            pixel_row = QHBoxLayout()
            pixel_row.addWidget(across)
            pixel_row.addWidget(down)
            form.addRow("Pixels:", pixel_row)
            self._pixels = (across, down)

        self._survey: QComboBox | None = None
        if server.surveys:
            self._survey = QComboBox()
            # Editable for SkyView, which has over a hundred and sixty
            # surveys and only a score of them on the list.
            self._survey.setEditable(server.name == "skyview")
            for entry in server.surveys:
                self._survey.addItem(entry.label, entry.value)
            form.addRow("Survey:", self._survey)

        self._message = QLabel()
        self._message.setWordWrap(True)
        layout.addWidget(self._message)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        resolve = QPushButton("Resolve Name")
        resolve.clicked.connect(self.resolve)
        buttons.addButton(resolve, QDialogButtonBox.ButtonRole.ActionRole)
        get = QPushButton("Retrieve")
        get.clicked.connect(self.request)
        buttons.addButton(get, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def survey(self) -> str:
        """Which survey is chosen, or "" when the server offers no choice."""
        if self._survey is None:
            return ""
        # An editable combo may hold a survey name that is not on the list,
        # in which case the text *is* the value.
        data = self._survey.currentData()
        text = self._survey.currentText()
        return str(data) if data and text == self._survey.itemText(self._survey.currentIndex()) else text

    def center(self) -> tuple[float, float]:
        """The position it is pointed at, in degrees."""
        return (self._longitude.value(), self._latitude.value())

    def object_name(self) -> str:
        """The object name typed in, or ""."""
        return self._name.text().strip()

    def size(self) -> tuple[float, float]:
        """The cutout size, in the server's own unit."""
        return (self._width.value(), self._height.value())

    def set_size(self, width: float, height: float, unit: str = "degrees") -> None:
        """Set the cutout size, converting into the server's unit.

        DS9's `xpaset ds9 dss size 30 30 arcmin` names its unit, which need
        not be the one the server wants; pixels are not convertible, so a
        size given in the other unit is taken as-is.

        Args:
            width: How wide.
            height: How tall.
            unit: `degrees`, `arcmin` or `arcsec`, as DS9's grammar takes.
        """
        factor = _TO_DEGREES.get(unit.lower().rstrip("s") + "s", 1.0)
        wanted = self.server.size_unit
        if wanted is SizeUnit.ARCMIN:
            scale = factor * 60.0
        elif wanted is SizeUnit.DEGREES:
            scale = factor
        else:
            # Pixels: nothing to convert to, so take the number given.
            scale = 1.0
        self._width.setValue(max(self._width.minimum(), float(width) * scale))
        self._height.setValue(max(self._height.minimum(), float(height) * scale))

    def pixels(self) -> tuple[int, int] | None:
        """The output image size, or None for a server that has no such setting."""
        if self._pixels is None:
            return None
        return (self._pixels[0].value(), self._pixels[1].value())

    def set_pixels(self, width: int, height: int) -> bool:
        """Set the output image size, DS9's `skyview pixels <w> <h>`.

        Returns:
            Whether this server has such a setting at all.
        """
        if self._pixels is None:
            return False
        self._pixels[0].setValue(max(1, min(MAX_PIXELS, int(width))))
        self._pixels[1].setValue(max(1, min(MAX_PIXELS, int(height))))
        return True

    def set_survey(self, name: str) -> bool:
        """Choose a survey by its value or its label.

        Returns:
            Whether the server offers it. An editable list (SkyView's)
            takes anything, since it offers far more than it lists.
        """
        if self._survey is None:
            return False
        # Case-insensitive: DS9's own grammar tokenises `dss1` and maps it
        # to the server's `DSS1`, so a script need not know the casing.
        wanted = name.strip().lower()
        for index in range(self._survey.count()):
            known = (str(self._survey.itemData(index) or ""), self._survey.itemText(index))
            if wanted in (text.lower() for text in known):
                self._survey.setCurrentIndex(index)
                return True
        if self._survey.isEditable():
            self._survey.setCurrentText(name)
            return True
        return False

    def set_name(self, name: str) -> None:
        """Fill in an object name without resolving it yet."""
        self._name.setText(str(name))
        self._by_name.setChecked(True)

    def set_center(self, longitude: float, latitude: float) -> None:
        """Fill in a resolved position and switch to coordinates."""
        self._longitude.setValue(float(longitude))
        self._latitude.setValue(float(latitude))
        self._by_coordinates.setChecked(True)

    def set_message(self, text: str) -> None:
        """Say what happened."""
        self._message.setText(text)

    def resolve(self) -> None:
        """Ask for the typed name to be resolved to coordinates."""
        name = self._name.text().strip()
        if not name:
            self.set_message("Type an object name to resolve")
            return
        self._by_name.setChecked(True)
        self.name_requested.emit(name)

    def request(self) -> None:
        """Ask for the cutout."""
        if self._by_name.isChecked() and self._name.text().strip():
            # Resolve first: the controller fills the coordinates in and
            # the user presses Retrieve again, which is what DS9 does.
            self.resolve()
            return

        self.set_message("Retrieving...")
        self.retrieve_requested.emit(
            self._longitude.value(),
            self._latitude.value(),
            self._width.value(),
            self._height.value(),
            self.survey(),
        )
