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
The small dialogs DS9 shows after a region file name is chosen.

`MarkerSaveDialog` and `MarkerLoadDialog` in `ds9/library/markerdialog.tcl`:
Save asks for the format and the coordinate system -- system, sky frame and
sky format -- the file is written in; Open asks for the format, the system
an X Y file's numbers are in, and whether to load into the current frame or
into every frame.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ...regions.region_formats import RegionFormat
from ..widgets.coord_menu_button import CoordMenuButton

#: DS9's Format menu, in its order, as (value, label). XML and SAOtng are
#: not written by this application, so they are not offered.
FORMAT_LABELS: tuple[tuple[RegionFormat, str], ...] = (
    (RegionFormat.DS9, "DS9/Funtools"),
    (RegionFormat.CIAO, "CIAO"),
    (RegionFormat.SAOIMAGE, "SAOimage"),
    (RegionFormat.PROS, "IRAF PROS"),
    (RegionFormat.FUNTOOLS, "Funtools"),
    (RegionFormat.XY, "X Y"),
)


@dataclass(frozen=True)
class RegionFileOptions:
    """What the dialog chose.

    Attributes:
        region_format: The file format.
        system: image, physical, wcs or wcsa..wcsz.
        sky: The sky frame, for a WCS system.
        sky_format: degrees or sexagesimal, for a WCS system.
        all_frames: Open only: load into every frame.
    """

    region_format: RegionFormat = RegionFormat.DS9
    system: str = "image"
    sky: str = "fk5"
    sky_format: str = "degrees"
    all_frames: bool = False


class RegionFileDialog(QDialog):
    """DS9's region Save or Open options.

    Args:
        mode: "save" or "load".
        wcs_systems: The WCS systems the current frame has.
        initial: What to show first -- the last choice, as DS9 remembers it.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        mode: str = "save",
        wcs_systems: tuple[str, ...] = (),
        initial: RegionFileOptions | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.mode = mode
        initial = initial or RegionFileOptions(system="wcs" if wcs_systems else "image")
        self.setWindowTitle("Save Regions" if mode == "save" else "Load Regions")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._format = QComboBox()
        for value, label in FORMAT_LABELS:
            self._format.addItem(label, value)
        self._format.setCurrentIndex(max(0, self._format.findData(initial.region_format)))
        self._format.currentIndexChanged.connect(self._sync)
        form.addRow("Format:", self._format)

        # DS9's own CoordMenuButton: system, sky frame and sky format.
        self._coord = CoordMenuButton(self, other=1, system=initial.system)
        self._coord.set_sky(initial.sky)
        self._coord.set_sky_format(initial.sky_format)
        available = tuple(wcs_systems)
        self._coord.adjust(lambda name: name in available, "physical", lambda name: name in available)
        form.addRow("Coordinate System:", self._coord)

        self._current = QRadioButton("Load into Current")
        self._all = QRadioButton("Load into All")
        group = QButtonGroup(self)
        group.addButton(self._current)
        group.addButton(self._all)
        (self._all if initial.all_frames else self._current).setChecked(True)
        if mode != "save":
            form.addRow("Frames:", self._current)
            form.addRow("", self._all)
        else:
            self._current.hide()
            self._all.hide()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._sync()

    def _sync(self, *_args) -> None:
        """Enable what applies, as `UpdateMarkerLoadDialog` does.

        Opening, the system only matters for an X Y file: every other format
        says its own.
        """
        xy = self._format.currentData() is RegionFormat.XY
        self._coord.setEnabled(self.mode == "save" or xy)

    def options(self) -> RegionFileOptions:
        """What is chosen now."""
        return RegionFileOptions(
            region_format=self._format.currentData(),
            system=self._coord.system,
            sky=self._coord.sky,
            sky_format=self._coord.sky_format,
            all_frames=self._all.isChecked(),
        )
