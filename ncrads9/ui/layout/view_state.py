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
What the window shows, and how it is arranged.

DS9 keeps this in one global array, `view(...)`, set up by `ViewDef` in
`ds9/library/layout.tcl`: a four-valued layout, a visibility flag per panel,
and a flag per information-panel field. Every menu entry in DS9's View menu
writes one of those flags and then calls `LayoutView`, `LayoutFrames` or
`LayoutInfoPanel`. `ViewState` below is that array, with DS9's own defaults.

Keeping it a plain dataclass -- no Qt -- means the layout rules can be tested
without building a window, and it gives the XPA `view` access point (M8) a
single object to read and write.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

#: The suffixes DS9 uses for the alternate WCS systems, `wcsa` .. `wcsz`.
WCS_SUFFIXES: tuple[str, ...] = tuple("abcdefghijklmnopqrstuvwxyz")


class ViewLayout(str, Enum):
    """The four arrangements DS9 offers in `View`.

    DS9 treats these as one radio group, not as two independent settings:
    Basic and Advanced are alternative *layouts*, so choosing Basic replaces
    Horizontal rather than modifying it. TODO.md M3-4/M3-5 describe them as a
    layout switch plus a pair of modes; this follows DS9.
    """

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    BASIC = "basic"
    ADVANCED = "advanced"


#: Information-panel fields, in the order `LayoutInfoPanelHorz` grids them.
#: The `wcs` entry stands for the primary WCS; the alternates are appended
#: below as `wcs_a` .. `wcs_z`.
INFO_FIELDS: tuple[str, ...] = (
    "filename",
    "object",
    "keyword",
    "minmax",
    "lowhigh",
    "value",
    "bunit",
    "wcs",
    *(f"wcs_{suffix}" for suffix in WCS_SUFFIXES),
    "detector",
    "amplifier",
    "physical",
    "image",
    "frame",
)

#: Fields DS9 shows by default (`ViewDef`). `value` is not in DS9's list
#: because DS9 grids it unconditionally -- it has no menu toggle.
DEFAULT_INFO_FIELDS: frozenset[str] = frozenset(
    {"filename", "object", "value", "wcs", "physical", "image", "frame"}
)


#: The panel flags, in the order DS9's View menu lists them.
PANEL_NAMES: tuple[str, ...] = (
    "info",
    "panner",
    "magnifier",
    "buttons",
    "icons",
    "colorbar",
    "multi",
    "graph_horizontal",
    "graph_vertical",
)


def _default_info() -> dict[str, bool]:
    """Every information-panel field, at DS9's default visibility."""
    return {name: name in DEFAULT_INFO_FIELDS for name in INFO_FIELDS}


@dataclass
class ViewState:
    """Which parts of the window are shown, and in what arrangement."""

    layout: ViewLayout = ViewLayout.HORIZONTAL

    # Panels. DS9: view(info), view(panner), ...
    info: bool = True
    panner: bool = True
    magnifier: bool = True
    buttons: bool = True
    icons: bool = True
    colorbar: bool = True
    #: One colorbar per frame rather than one shared. DS9: view(multi).
    multi: bool = True
    graph_horizontal: bool = False
    graph_vertical: bool = False

    #: Field name -> shown. Keys are exactly `INFO_FIELDS`.
    info_fields: dict[str, bool] = field(default_factory=_default_info)

    #: True when the header row has anything in it to show.
    @property
    def header_visible(self) -> bool:
        """DS9 grids the header if any of info, panner or magnifier is on."""
        return self.info or self.panner or self.magnifier

    def field_visible(self, name: str) -> bool:
        """Whether one information-panel field is shown.

        `value` is always shown, matching DS9, which grids it with no toggle.
        """
        if name == "value":
            return True
        return self.info_fields.get(name, False)

    def set_field_visible(self, name: str, visible: bool) -> None:
        """Show or hide one information-panel field.

        Raises:
            KeyError: If `name` is not an information-panel field.
        """
        if name not in self.info_fields:
            raise KeyError(f"not an info-panel field: {name}")
        self.info_fields[name] = bool(visible)
