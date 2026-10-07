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
DS9's coordinate and distance menu buttons (`menu.tcl:310`, `menu.tcl:468`).

Every DS9 dialog that takes a position puts a small menu button beside the
entries -- WCS, the twenty-six alternate WCSs, image, physical, amplifier,
detector, then the sky frame and format -- and every one that takes a size
puts a distance button -- the same systems, then degrees, arcmin, arcsec.
The button's face reads what the numbers are in: the system, or the sky
frame (or angular unit) when the system is a celestial WCS.

These are those two buttons, plus `CoordEntry`, the text box DS9 types a
coordinate into, which has to take `13:29:52.7` as well as a number.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import string
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QLineEdit, QMenu, QToolButton, QWidget

#: The alternate WCS letters, as DS9's `Multiple WCS` submenu lists them.
WCS_LETTERS: tuple[str, ...] = tuple(string.ascii_lowercase)

#: The pixel systems DS9 offers when a menu's `other` is 1.
PIXEL_SYSTEMS: tuple[str, ...] = ("image", "physical", "amplifier", "detector")

#: The sky frames, with their menu labels.
SKY_FRAMES: tuple[tuple[str, str], ...] = (
    ("fk4", "FK4"),
    ("fk5", "FK5"),
    ("icrs", "ICRS"),
    ("galactic", "Galactic"),
    ("ecliptic", "Ecliptic"),
)

#: The sky formats.
SKY_FORMATS: tuple[tuple[str, str], ...] = (("degrees", "Degrees"), ("sexagesimal", "Sexagesimal"))

#: The angular units a distance can be in.
DISTANCE_FORMATS: tuple[tuple[str, str], ...] = (
    ("degrees", "Degrees"),
    ("arcmin", "ArcMin"),
    ("arcsec", "ArcSec"),
)


def is_wcs(system: str) -> bool:
    """Whether a system is the primary WCS or one of `wcsa`..`wcsz`."""
    return system.startswith("wcs")


def frame_has_wcs(frame: Any, system: str) -> bool:
    """Whether a frame carries a usable (celestial) WCS of that name."""
    if frame is None:
        return False
    if not is_wcs(system):
        return True
    getter = getattr(frame, "wcs_for", None)
    if callable(getter):
        handler = getter(system)
    else:
        handler = getattr(frame, "wcs_handler", None) if system == "wcs" else None
    return bool(getattr(handler, "is_valid", False))


class CoordEntry(QLineEdit):
    """A coordinate box: free text, because sexagesimal is not a number.

    `value` and `setValue` read and write it as a number, so it can stand in
    for the spin box it replaced.
    """

    def value(self) -> float:
        """The text as a number.

        Raises:
            ValueError: If it is not one.
        """
        return float(self.text().strip())

    def setValue(self, value: float) -> None:
        """Show a number, without trailing zeros."""
        self.setText(f"{float(value):.10g}")


class _SystemMenuButton(QToolButton):
    """What the coordinate and distance buttons share: the system choice."""

    #: Emitted when anything on the menu is chosen.
    changed: pyqtSignal = pyqtSignal()

    def __init__(self, parent: QWidget | None, other: int, system: str) -> None:
        super().__init__(parent)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._menu = QMenu(self)
        self.setMenu(self._menu)
        #: Menu value -> its action: `wcs`, `wcsa`.., `image`, `fk5`, `arcsec` ...
        self.actions_by_value: dict[str, QAction] = {}
        self._system = system
        self._celestial: Callable[[str], bool] = lambda _name: False

        self._systems = QActionGroup(self)
        self._add(self._menu, self._systems, "wcs", "WCS")
        self._multiple = self._menu.addMenu("Multiple WCS")
        for letter in WCS_LETTERS:
            self._add(self._multiple, self._systems, f"wcs{letter}", f"WCS {letter}")
        if other == 1:
            self._menu.addSeparator()
            for name in PIXEL_SYSTEMS:
                self._add(self._menu, self._systems, name, name.capitalize())
        elif other == 2:
            self._menu.addSeparator()
            self._add(self._menu, self._systems, "image", "Image")

    def _add(self, menu: QMenu, group: QActionGroup, value: str, label: str) -> QAction:
        action = QAction(label, self)
        action.setCheckable(True)
        action.setData(value)
        group.addAction(action)
        menu.addAction(action)
        action.triggered.connect(lambda _checked=False, item=action: self._chosen(item))
        self.actions_by_value[value] = action
        return action

    def _chosen(self, action: QAction) -> None:
        """A menu entry was picked."""
        group = action.actionGroup()
        self._set_from_group(group, str(action.data()))
        self._refresh()
        self.changed.emit()

    def _set_from_group(self, group: QActionGroup | None, value: str) -> None:
        if group is self._systems:
            self._system = value

    # -- state -----------------------------------------------------------------

    @property
    def system(self) -> str:
        """The chosen coordinate system: `wcs`, `wcsa`.., `image` ..."""
        return self._system

    def set_system(self, system: str, notify: bool = False) -> None:
        """Choose a system.

        Args:
            system: Any value the menu offers.
            notify: Emit `changed`.
        """
        system = system.lower()
        if system not in self.actions_by_value:
            raise ValueError(f"no coordinate system {system!r} on this menu")
        self._system = system
        self._refresh()
        if notify:
            self.changed.emit()

    def _is_celestial(self) -> bool:
        return is_wcs(self._system) and self._celestial(self._system)

    def _face(self) -> str:
        return self._system

    def _refresh(self) -> None:
        """Tick the chosen entries and write the button's face."""
        for value, action in self.actions_by_value.items():
            group = action.actionGroup()
            action.setChecked(self._selected(group) == value)
        self.setText(self._face())

    def _selected(self, group: QActionGroup | None) -> str:
        return self._system if group is self._systems else ""

    # -- what the frame offers ------------------------------------------------

    def adjust(
        self,
        available: Callable[[str], bool],
        fallback: str = "physical",
        celestial: Callable[[str], bool] | None = None,
    ) -> None:
        """DS9's `AdjustCoordSystem` and `CoordMenuEnable` together.

        Greys out the WCSs the frame does not carry and, when the chosen one
        is among them, falls back -- to physical for a position, to image for
        a slice -- as DS9 does.

        Args:
            available: Whether a system can be used on the frame.
            fallback: What to choose when the current system cannot.
            celestial: Whether a WCS is a sky one; one that is not shows
                its own name on the face, not a sky frame.
        """
        if celestial is not None:
            self._celestial = celestial
        for value, action in self.actions_by_value.items():
            if action.actionGroup() is self._systems and is_wcs(value):
                action.setEnabled(bool(available(value)))
        if is_wcs(self._system) and not available(self._system):
            self._system = fallback if fallback in self.actions_by_value else "image"
        self._enable_extras(self._is_celestial())
        self._refresh()

    def adjust_to_frame(self, frame: Any, fallback: str = "physical") -> None:
        """`adjust` for a 2D position on a frame: its own WCSs decide."""
        self.adjust(
            lambda name: frame_has_wcs(frame, name), fallback, lambda name: frame_has_wcs(frame, name)
        )

    def reset(self) -> None:
        """DS9's `CoordMenuReset`: everything enabled again, for no frame."""
        for action in self.actions_by_value.values():
            action.setEnabled(True)
        self._refresh()

    def _enable_extras(self, celestial: bool) -> None:
        """Enable the sky/format entries only for a sky system."""


class CoordMenuButton(_SystemMenuButton):
    """DS9's `CoordMenuButton`: system, sky frame and sky format.

    Args:
        parent: Optional parent widget.
        other: 1 to offer image, physical, amplifier and detector; 2 to offer
            image alone, as the 3D and cube menus do; 0 for WCS only.
        sky: Offer the sky frames.
        sky_format: Offer degrees and sexagesimal.
        system: The initial system; DS9 starts its dialogs on `wcs`.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        other: int = 1,
        sky: bool = True,
        sky_format: bool = True,
        system: str = "wcs",
    ) -> None:
        super().__init__(parent, other, system)
        self._sky = "fk5"
        self._sky_format = "degrees"
        self._skies = QActionGroup(self) if sky else None
        self._formats = QActionGroup(self) if sky_format else None
        if self._skies is not None:
            self._menu.addSeparator()
            for value, label in SKY_FRAMES:
                self._add(self._menu, self._skies, value, label)
        if self._formats is not None:
            self._menu.addSeparator()
            for value, label in SKY_FORMATS:
                self._add(self._menu, self._formats, value, label)
        self._refresh()

    @property
    def sky(self) -> str:
        """The sky frame, `fk5` by default."""
        return self._sky

    @property
    def sky_format(self) -> str:
        """`degrees` or `sexagesimal`."""
        return self._sky_format

    def set_sky(self, sky: str, notify: bool = False) -> None:
        """Choose a sky frame."""
        self._sky = sky.lower()
        self._refresh()
        if notify:
            self.changed.emit()

    def set_sky_format(self, sky_format: str, notify: bool = False) -> None:
        """Choose degrees or sexagesimal."""
        self._sky_format = sky_format.lower()
        self._refresh()
        if notify:
            self.changed.emit()

    def _set_from_group(self, group: QActionGroup | None, value: str) -> None:
        if group is not None and group is self._skies:
            self._sky = value
        elif group is not None and group is self._formats:
            self._sky_format = value
        else:
            super()._set_from_group(group, value)

    def _selected(self, group: QActionGroup | None) -> str:
        if group is not None and group is self._skies:
            return self._sky
        if group is not None and group is self._formats:
            return self._sky_format
        return super()._selected(group)

    def _face(self) -> str:
        # DS9's CoordMenuButtonCmd: a celestial WCS reads as its sky frame.
        if self._skies is not None and self._is_celestial():
            return self._sky
        return self._system

    def _enable_extras(self, celestial: bool) -> None:
        for group in (self._skies, self._formats):
            if group is None:
                continue
            for action in group.actions():
                action.setEnabled(celestial)


class DistMenuButton(_SystemMenuButton):
    """DS9's `DistMenuButton`: system, and the angular unit of a WCS size.

    Args:
        parent: Optional parent widget.
        other: Offer image, physical, amplifier and detector too.
        distance_format: Offer degrees, arcmin and arcsec.
        system: The initial system.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        other: bool = True,
        distance_format: bool = True,
        system: str = "wcs",
    ) -> None:
        super().__init__(parent, 1 if other else 0, system)
        self._format = "degrees"
        self._formats = QActionGroup(self) if distance_format else None
        if self._formats is not None:
            self._menu.addSeparator()
            for value, label in DISTANCE_FORMATS:
                self._add(self._menu, self._formats, value, label)
        self._refresh()

    @property
    def distance_format(self) -> str:
        """`degrees`, `arcmin` or `arcsec`."""
        return self._format

    def set_distance_format(self, distance_format: str, notify: bool = False) -> None:
        """Choose the angular unit."""
        self._format = distance_format.lower()
        self._refresh()
        if notify:
            self.changed.emit()

    def _set_from_group(self, group: QActionGroup | None, value: str) -> None:
        if group is not None and group is self._formats:
            self._format = value
        else:
            super()._set_from_group(group, value)

    def _selected(self, group: QActionGroup | None) -> str:
        if group is not None and group is self._formats:
            return self._format
        return super()._selected(group)

    def _face(self) -> str:
        if self._formats is not None and self._is_celestial():
            return self._format
        return self._system

    def _enable_extras(self, celestial: bool) -> None:
        if self._formats is not None:
            for action in self._formats.actions():
                action.setEnabled(celestial)
