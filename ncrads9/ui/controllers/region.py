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
The Region menu: drawing mode, and region file load/save.

DS9's Region menu is the second largest in the application and NCRADS9 has
about a seventh of it (PLAN.md §5.9). Six of DS9's twenty shapes can be drawn;
the properties submenu, selection operations, groups, composites, templates,
instrument FOVs, centroiding and the per-shape information dialog are all
absent. M6 is the milestone that closes this, and the region *model* is already
ready for it after M1 -- `BaseRegion` carries the full DS9 property set.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import QFileDialog

from ...regions.base_region import BaseRegion
from ...regions.region_parser import RegionParser
from ...regions.region_writer import RegionWriter
from ..widgets.region_overlay import RegionMode
from .base import Controller

#: Region mode -> the label the menu and button bar show.
MODE_LABELS: dict[RegionMode, str] = {
    RegionMode.NONE: "None",
    RegionMode.CIRCLE: "Circle",
    RegionMode.ELLIPSE: "Ellipse",
    RegionMode.BOX: "Box",
    RegionMode.POLYGON: "Polygon",
    RegionMode.LINE: "Line",
    RegionMode.POINT: "Point",
}

#: Button-bar label -> region mode. The button bar has no Point button.
LABEL_MODES: dict[str, RegionMode] = {label: mode for mode, label in MODE_LABELS.items()}

REGION_FILTER = "Region Files (*.reg);;All Files (*)"


def describe(region: BaseRegion) -> str:
    """Name a region for the status bar, e.g. "circle".

    Takes the name from the shape's class rather than from a mode attribute.
    The overlay's old `Region` dataclass carried a `RegionMode`, and the two
    handlers below still read `region.mode.value` after M1 replaced it with
    `BaseRegion` subclasses -- so drawing anything raised AttributeError.
    Nothing caught it, because the M1 tests connected their own listener to
    the overlay's signal and never went through the window's handler.
    """
    return type(region).__name__.lower()


class RegionController(Controller):
    """Owns the Region menu."""

    def connect(self) -> None:
        """Wire the Region menu."""
        self.menu.action_region_none.triggered.connect(lambda: self.set_mode(RegionMode.NONE))
        self.menu.action_region_circle.triggered.connect(lambda: self.set_mode(RegionMode.CIRCLE))
        self.menu.action_region_ellipse.triggered.connect(lambda: self.set_mode(RegionMode.ELLIPSE))
        self.menu.action_region_box.triggered.connect(lambda: self.set_mode(RegionMode.BOX))
        self.menu.action_region_polygon.triggered.connect(lambda: self.set_mode(RegionMode.POLYGON))
        self.menu.action_region_line.triggered.connect(lambda: self.set_mode(RegionMode.LINE))
        self.menu.action_region_point.triggered.connect(lambda: self.set_mode(RegionMode.POINT))

        self.menu.action_region_load.triggered.connect(self.load_regions)
        self.menu.action_region_save.triggered.connect(self.save_regions)
        self.menu.action_region_delete_all.triggered.connect(self.clear_regions)

    # -- drawing mode --------------------------------------------------------

    def set_mode(self, mode: RegionMode) -> None:
        """Set the shape the next drag will draw."""
        self.viewer.set_region_mode(mode)
        label = MODE_LABELS.get(mode, "None")
        self.window.button_bar.set_region_mode(label)
        self.status(f"Region mode: {label}")

    def on_button_bar_mode(self, label: str) -> None:
        """Set the drawing mode from a button-bar label."""
        self.set_mode(LABEL_MODES.get(label, RegionMode.NONE))

    # -- overlay signals -----------------------------------------------------

    def on_created(self, region: BaseRegion) -> None:
        """Record a region the user just drew on the current frame."""
        frame = self.frame
        if frame is not None:
            frame.regions.append(region)
        self.status(f"Created {describe(region)} region")

    def on_selected(self, region: BaseRegion) -> None:
        """Report the region the user just clicked."""
        self.status(f"Selected {describe(region)} region")

    # -- frame synchronisation -----------------------------------------------

    def show_frame_regions(self, frame) -> None:
        """Replace the overlay's regions with the given frame's."""
        if not hasattr(self.viewer, "clear_regions"):
            return
        self.viewer.clear_regions()
        if frame is None:
            return
        for region in frame.regions:
            self.viewer.add_region(region)

    # -- file operations -----------------------------------------------------

    def load_regions(self) -> None:
        """Load a DS9 region file into the current frame."""
        filepath, _ = QFileDialog.getOpenFileName(self.window, "Load Region File", "", REGION_FILTER)
        if not filepath:
            return
        try:
            regions = RegionParser().parse_file(filepath)
        except Exception as exc:
            self.status(f"Error loading regions: {exc}", 3000)
            return

        frame = self.frame
        if frame is not None:
            frame.regions = regions
            self.show_frame_regions(frame)
        self.status(f"Loaded {len(regions)} regions from {filepath}", 3000)

    def save_regions(self) -> None:
        """Write the current frame's regions to a DS9 region file."""
        frame = self.frame
        if frame is None or not frame.regions:
            self.status("No regions to save")
            return

        filepath, _ = QFileDialog.getSaveFileName(self.window, "Save Region File", "", REGION_FILTER)
        if not filepath:
            return
        RegionWriter().write_file(frame.regions, filepath)
        self.status(f"Saved regions to {filepath}", 3000)

    def clear_regions(self) -> None:
        """Delete every region on the current frame."""
        frame = self.frame
        if frame is not None:
            frame.regions.clear()
            # SAMP markers are regenerated from stored positions, so drop
            # those too or they would reappear on the next refresh.
            self.window._samp_catalog_sources.pop(frame.frame_id, None)
        if hasattr(self.viewer, "clear_regions"):
            self.viewer.clear_regions()
        self.set_mode(RegionMode.NONE)
        self.status("Cleared all regions")

    # -- coordinates ---------------------------------------------------------

    def world_to_pixel(self, ra_deg: float, dec_deg: float) -> tuple[float, float] | None:
        """Convert a sky position to image pixels for overlaying a catalog.

        Returns None when there is no usable WCS, or when the position falls
        outside the projection and comes back non-finite.
        """
        handler = self.window.wcs_handler
        if handler is None or not handler.is_valid or self.window.image_data is None:
            return None
        try:
            x, y = handler.world_to_pixel(ra_deg, dec_deg)
        except Exception:
            return None
        if not np.isfinite(x) or not np.isfinite(y):
            return None
        return float(x), float(y)
