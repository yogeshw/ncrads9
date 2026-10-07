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
DS9's Name Resolution dialog, `NRESDialog` in `nameres.tcl`.

An Object entry, a Name Server menu (NED, SIMBAD or VizieR, at SAO or CDS),
the resolved position read out in the sky frame and format chosen, and
File -> Pan To and Crosshair To to take the image there. Retrieve resolves;
it does not move anything, which is DS9's order of things -- the position
is read first and then used.

The window resolves nothing itself: it asks, through `retrieve_requested`,
and the controller answers with `set_result` or `set_status`.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from astropy.coordinates import SkyCoord
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QActionGroup
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenuBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...catalogs import name_server, sky_position
from .modeless import make_modeless


class NameResolutionDialog(QDialog):
    """Resolve an object name and take the image to it.

    Args:
        server: The name server to start with, e.g. `simbad-cds`.
        parent: Optional parent widget.
    """

    #: Emitted with (name, server) when Retrieve is pressed.
    retrieve_requested = pyqtSignal(str, str)
    #: Emitted with `pan` or `crosshair` when File -> Pan To or Crosshair To is chosen.
    command_requested = pyqtSignal(str)

    def __init__(self, server: str = name_server.DEFAULT_SERVER, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        make_modeless(self)
        self.setWindowTitle("Name Resolution")
        #: The name server chosen.
        self.server = server
        #: The last position resolved, or None.
        self.coord: SkyCoord | None = None

        layout = QVBoxLayout(self)
        layout.setMenuBar(self._menus())

        grid = QGridLayout()
        layout.addLayout(grid)
        grid.addWidget(QLabel("Object"), 0, 0)
        self._name = QLineEdit()
        self._name.returnPressed.connect(self.retrieve)
        grid.addWidget(self._name, 0, 1, 1, 4)

        self._sky = QComboBox()
        self._sky.addItems(sky_position.SKY_FRAMES)
        self._sky.setCurrentText("fk5")
        self._sky.currentTextChanged.connect(lambda _text: self._show())
        grid.addWidget(self._sky, 1, 0)
        self._x = QLineEdit()
        self._x.setReadOnly(True)
        grid.addWidget(self._x, 1, 1)
        self._y = QLineEdit()
        self._y.setReadOnly(True)
        grid.addWidget(self._y, 1, 2)
        self._format = QComboBox()
        self._format.addItems(sky_position.SKY_FORMATS)
        self._format.currentTextChanged.connect(lambda _text: self._show())
        grid.addWidget(self._format, 1, 3)

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Status:"))
        self._status = QLabel()
        self._status.setWordWrap(True)
        status_row.addWidget(self._status, 1)
        layout.addLayout(status_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        retrieve = QPushButton("Retrieve")
        retrieve.clicked.connect(self.retrieve)
        buttons.addButton(retrieve, QDialogButtonBox.ButtonRole.ActionRole)
        self.pan_button = QPushButton("Pan To")
        self.pan_button.clicked.connect(lambda: self.command_requested.emit("pan"))
        buttons.addButton(self.pan_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.crosshair_button = QPushButton("Crosshair To")
        self.crosshair_button.clicked.connect(lambda: self.command_requested.emit("crosshair"))
        buttons.addButton(self.crosshair_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._enable()

    def _menus(self) -> QMenuBar:
        bar = QMenuBar(self)
        file_menu = bar.addMenu("&File")
        file_menu.addAction("&Retrieve").triggered.connect(lambda _checked=False: self.retrieve())
        file_menu.addSeparator()
        self.action_pan = file_menu.addAction("&Pan To")
        self.action_pan.triggered.connect(lambda _checked=False: self.command_requested.emit("pan"))
        self.action_crosshair = file_menu.addAction("&Crosshair To")
        self.action_crosshair.triggered.connect(
            lambda _checked=False: self.command_requested.emit("crosshair")
        )
        file_menu.addSeparator()
        file_menu.addAction("&Close").triggered.connect(lambda _checked=False: self.close())

        names_menu = bar.addMenu("&Name Server")
        group = QActionGroup(self)
        #: Server value -> its action.
        self.server_actions = {}
        for label, value in name_server.SERVERS:
            action = names_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == self.server)
            group.addAction(action)
            action.triggered.connect(lambda _checked=False, key=value: self.set_server(key))
            self.server_actions[value] = action
        return bar

    def set_server(self, server: str) -> None:
        """Choose the name server."""
        self.server = server
        action = self.server_actions.get(server)
        if action is not None:
            action.setChecked(True)

    def object_name(self) -> str:
        return self._name.text().strip()

    def set_object_name(self, name: str) -> None:
        self._name.setText(str(name))

    def set_sky(self, sky: str, skyformat: str | None = None) -> None:
        """Choose the frame and format the position is read out in."""
        if sky in sky_position.SKY_FRAMES:
            self._sky.setCurrentText(sky)
        if skyformat in sky_position.SKY_FORMATS:
            self._format.setCurrentText(skyformat)

    def position_text(self) -> tuple[str, str]:
        """The position read out, as shown."""
        return (self._x.text(), self._y.text())

    def retrieve(self) -> None:
        """Ask for the name to be resolved."""
        name = self.object_name()
        if not name:
            self.set_status("Please specify an Object Name")
            return
        self.set_status(f"Resolving {name} with {name_server.label_for(self.server)}...")
        self.retrieve_requested.emit(name, self.server)

    def set_result(self, coord: SkyCoord | None) -> None:
        """Show a resolved position, or clear it."""
        self.coord = coord
        self._show()
        self._enable()
        if coord is not None:
            self.set_status("Done")

    def set_status(self, text: str) -> None:
        self._status.setText(str(text))

    def status_text(self) -> str:
        return self._status.text()

    def _show(self) -> None:
        if self.coord is None:
            self._x.clear()
            self._y.clear()
            return
        x, y = sky_position.format_position(self.coord, self._sky.currentText(), self._format.currentText())
        self._x.setText(x)
        self._y.setText(y)

    def _enable(self) -> None:
        has = self.coord is not None
        for widget in (self.pan_button, self.crosshair_button, self.action_pan, self.action_crosshair):
            widget.setEnabled(has)
