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
DS9's coordinate menu button: the system, sky frame and sky format of a
row of position entries (`CoordMenuButton` in `menu.tcl`).

Every DS9 dialog that takes a position puts one of these beside it, and
the button's text says what the numbers mean: the sky frame when the
system is a celestial WCS, the system's name otherwise. A dialog asks it
which entries make sense for its frame (`set_available`) so that a WCS
the file lacks cannot be chosen, as DS9's `CoordMenuEnable` does.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import string
from collections.abc import Callable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QMenu, QToolButton, QWidget

#: The label each system has in DS9's menu.
SYSTEM_LABELS: dict[str, str] = {
    "wcs": "WCS",
    "image": "Image",
    "physical": "Physical",
    "amplifier": "Amplifier",
    "detector": "Detector",
    **{f"wcs{letter}": f"WCS {letter}" for letter in string.ascii_lowercase},
}

#: DS9's sky frames, in its menu's order, with their labels.
SKY_LABELS: dict[str, str] = {
    "fk4": "FK4",
    "fk5": "FK5",
    "icrs": "ICRS",
    "galactic": "Galactic",
    "ecliptic": "Ecliptic",
}

#: DS9's sky formats and their labels.
FORMAT_LABELS: dict[str, str] = {"degrees": "Degrees", "sexagesimal": "Sexagesimal"}


class CoordMenuButton(QToolButton):
    """A button whose menu picks a coordinate system, sky frame and format."""

    #: Emitted with (system, sky, format) whenever any of them is chosen.
    changed = pyqtSignal(str, str, str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        system: str = "wcs",
        sky: str = "fk5",
        sky_format: str = "degrees",
    ) -> None:
        super().__init__(parent)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._system = system
        self._sky = sky
        self._format = sky_format
        self._celestial = True

        menu = QMenu(self)
        #: value -> action, for each of the three radio groups.
        self.system_actions: dict[str, QAction] = {}
        self.sky_actions: dict[str, QAction] = {}
        self.format_actions: dict[str, QAction] = {}

        systems = QActionGroup(self)

        def radio(target: QMenu, group: QActionGroup, label: str, slot: Callable[[], None]) -> QAction:
            action = QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False: slot())
            group.addAction(action)
            target.addAction(action)
            return action

        self.system_actions["wcs"] = radio(menu, systems, "WCS", lambda: self.set_system("wcs", emit=True))
        self.multiple_wcs_menu = menu.addMenu("Multiple WCS")
        for letter in string.ascii_lowercase:
            key = f"wcs{letter}"
            self.system_actions[key] = radio(
                self.multiple_wcs_menu, systems, f"WCS {letter}", lambda k=key: self.set_system(k, emit=True)
            )
        menu.addSeparator()
        for key in ("image", "physical", "amplifier", "detector"):
            self.system_actions[key] = radio(
                menu, systems, SYSTEM_LABELS[key], lambda k=key: self.set_system(k, emit=True)
            )

        menu.addSeparator()
        skies = QActionGroup(self)
        for key, label in SKY_LABELS.items():
            self.sky_actions[key] = radio(menu, skies, label, lambda k=key: self.set_sky(k, emit=True))

        menu.addSeparator()
        formats = QActionGroup(self)
        for key, label in FORMAT_LABELS.items():
            self.format_actions[key] = radio(menu, formats, label, lambda k=key: self.set_format(k, emit=True))

        self.setMenu(menu)
        self._show()

    # -- state ---------------------------------------------------------------

    @property
    def system(self) -> str:
        """The chosen coordinate system: wcs, wcsa..wcsz, image, ..."""
        return self._system

    @property
    def sky(self) -> str:
        """The chosen sky frame."""
        return self._sky

    @property
    def sky_format(self) -> str:
        """The chosen sky format: degrees or sexagesimal."""
        return self._format

    def set_system(self, system: str, emit: bool = False) -> None:
        """Choose a system."""
        self._system = system.lower()
        self._show(emit)

    def set_sky(self, sky: str, emit: bool = False) -> None:
        """Choose a sky frame."""
        self._sky = sky.lower()
        self._show(emit)

    def set_format(self, sky_format: str, emit: bool = False) -> None:
        """Choose a sky format."""
        self._format = sky_format.lower()
        self._show(emit)

    def set_available(self, available: Callable[[str], bool]) -> None:
        """Enable only the systems a frame has, as DS9's `CoordMenuEnable`.

        Sky frames and formats mean something only for a celestial
        system, so they are disabled while one is not chosen.

        Args:
            available: Whether the frame can express a given system.
        """
        for key, action in self.system_actions.items():
            action.setEnabled(bool(available(key)))
        self._celestial = self._system.startswith("wcs") and bool(available(self._system))
        for action in (*self.sky_actions.values(), *self.format_actions.values()):
            action.setEnabled(self._celestial)
        self._show()

    def _show(self, emit: bool = False) -> None:
        """Tick the chosen entries and label the button as DS9 does."""
        for key, action in self.system_actions.items():
            action.setChecked(key == self._system)
        for key, action in self.sky_actions.items():
            action.setChecked(key == self._sky)
        for key, action in self.format_actions.items():
            action.setChecked(key == self._format)
        celestial = self._system.startswith("wcs") and self._celestial
        self.setText(SKY_LABELS.get(self._sky, self._sky) if celestial else SYSTEM_LABELS.get(self._system, self._system))
        if emit:
            self.changed.emit(self._system, self._sky, self._format)
