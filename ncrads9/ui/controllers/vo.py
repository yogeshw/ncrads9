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
The VO menu: virtual-observatory queries and SAMP.

Not a DS9 menu. DS9 reaches all of this from Analysis -- Image Servers,
Archives, Catalogs, Footprint Servers, Catalog Tool, Virtual Observatory --
and NCRADS9 substitutes a `VO` menu where DS9 has `Illustrate`
(PLAN.md §1, §7). M8 builds the real catalog and image-server subsystems and
folds these entries back under Analysis where a DS9 user will look for them.

What works today: a 2MASS SIAP image query, a VizieR catalog overlay, and a
SAMP client that can receive `table.load.votable` and `image.load.fits` and
draw the result as markers. SAMP tables arrive on a worker thread, so they are
handed to the GUI thread through the window's `samp_table_received` signal
rather than touched directly.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import tempfile
from urllib.parse import unquote, urlparse

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table
from PyQt6.QtWidgets import QColorDialog, QDialog, QInputDialog

from ...catalogs.vizier import VizierCatalog
from ...communication.samp import SAMPClient
from ...frames.frame import Frame
from ...image_servers.sia_client import SIAClient
from ...regions.base_region import BaseRegion
from ...regions.shapes.box import Box
from ...regions.shapes.circle import Circle
from ...regions.shapes.ellipse import Ellipse
from ...regions.shapes.point import Point
from ..dialogs.vo_query_dialog import VOQueryDialog
from .base import Controller


class VOController(Controller):
    """Owns the VO menu."""

    def connect(self) -> None:
        """Wire the VO menu, and the Analysis entries that duplicate it."""
        menu = self.menu
        menu.action_siap_2mass.triggered.connect(self.query_2mass_image)
        menu.action_catalog_vizier.triggered.connect(self.query_vizier_catalog)
        menu.action_samp_connect.triggered.connect(self.samp_connect)
        menu.action_samp_disconnect.triggered.connect(self.samp_disconnect)
        menu.action_samp_marker_color.triggered.connect(self.choose_marker_color)
        menu.action_samp_marker_shape.triggered.connect(self.choose_marker_shape)
        menu.action_samp_marker_size.triggered.connect(self.choose_marker_size)

        # DS9 puts these under Analysis; both routes reach the same method.
        menu.action_analysis_2mass.triggered.connect(self.query_2mass_image)
        menu.action_analysis_vizier.triggered.connect(self.query_vizier_catalog)
        menu.action_catalog_tool.triggered.connect(self.query_vizier_catalog)
        menu.action_virtual_observatory.triggered.connect(self.query_vizier_catalog)

    def query_2mass_image(self) -> None:
        """Query 2MASS via SIAP and load image into new frame."""
        ra, dec = self.query_coordinates()
        dialog = VOQueryDialog(self.window, ra, dec, radius_deg=0.1, title="2MASS SIAP Query")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        ra, dec, radius = dialog.values()

        client = SIAClient(SIAClient.get_known_services()["2MASS"])
        table = client.query(ra, dec, size=radius, format="image/fits")
        if table is None or len(table) == 0:
            self.status("No SIAP images found", 3000)
            return

        access_url = self.pick_access_url(table)
        if not access_url:
            self.status("No SIAP access URL found", 3000)
            return

        try:
            data = client.get_image(access_url)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".fits") as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            self.window.frame_controller.new_frame()
            self.window.display.load_fits(tmp_path)
            self.status("Loaded SIAP image into new frame", 3000)
        except Exception as e:
            self.status(f"SIAP load error: {e}", 3000)

    def query_vizier_catalog(self) -> None:
        """Query VizieR and overlay catalog sources."""
        ra, dec = self.query_coordinates()
        dialog = VOQueryDialog(self.window, ra, dec, radius_deg=0.05, title="VizieR Catalog Query")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        ra, dec, radius = dialog.values()

        catalog = VizierCatalog(catalog="II/246/out")
        coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
        table = catalog.query_region(coord, radius=radius * u.deg)
        if table is None or len(table) == 0:
            self.status("No VizieR sources found", 3000)
            return
        coords = catalog.get_coordinates(table)
        if not coords:
            self.status("Catalog has no usable coordinates", 3000)
            return
        if not self.window.wcs_handler or not self.window.wcs_handler.is_valid:
            self.status("Current frame has no WCS for overlay", 3000)
            return

        for coord in coords:
            pixel = self.window.region.world_to_pixel(coord.ra.deg, coord.dec.deg)
            if pixel is None:
                continue
            x, y = pixel
            region = Point(center=(x, y), origin="vizier_catalog")
            self.window.region.on_created(region)
            self.viewer.add_region(region)

        self.status(f"Overlayed {len(coords)} catalog sources", 3000)

    def init_samp(self) -> None:
        """Initialize SAMP client and callbacks."""
        self.window._samp_client = SAMPClient()
        self.window._samp_client.register_callback("table.load.votable", self.on_samp_votable)
        self.window._samp_client.register_callback("table.load.fits", self.on_samp_fits)

    def sync_samp_menu(self) -> None:
        """Update SAMP menu action enabled states."""
        self.menu.action_samp_connect.setEnabled(not self.window._samp_connected)
        self.menu.action_samp_disconnect.setEnabled(self.window._samp_connected)

    def samp_connect(self) -> None:
        """Connect to a SAMP hub."""
        if self.window._samp_client is None:
            self.init_samp()
        if self.window._samp_client is None:
            self.status("SAMP client unavailable", 3000)
            return
        if self.window._samp_client.connect():
            self.window._samp_connected = True
            self.status("Connected to SAMP hub", 3000)
        else:
            self.window._samp_connected = False
            self.status("Failed to connect to SAMP hub", 3000)
        self.sync_samp_menu()

    def samp_disconnect(self) -> None:
        """Disconnect from SAMP hub."""
        if self.window._samp_client is not None:
            self.window._samp_client.disconnect()
        self.window._samp_connected = False
        self.sync_samp_menu()
        self.status("Disconnected from SAMP hub", 3000)

    def on_samp_votable(self, sender_id: str, params: dict) -> None:
        """Queue incoming table.load.votable message on UI thread."""
        self.queue_samp_table(params, "votable")

    def on_samp_fits(self, sender_id: str, params: dict) -> None:
        """Queue incoming table.load.fits message on UI thread."""
        self.queue_samp_table(params, "fits")

    def queue_samp_table(self, params: dict, table_format: str) -> None:
        """Queue incoming SAMP table message for UI-thread handling."""
        url = str(params.get("url", "")).strip()
        if not url:
            return
        table_id = str(params.get("table-id") or params.get("name") or "samp-catalog")
        self.window.samp_table_received.emit(url, table_id, table_format)

    def handle_samp_table(self, url: str, table_id: str, table_format: str) -> None:
        """Handle incoming SAMP catalog message."""
        frame = self.frames.current_frame
        if not frame or frame.image_data is None:
            self.status("No image loaded for SAMP catalog overlay", 3000)
            return
        if not self.window.wcs_handler or not self.window.wcs_handler.is_valid:
            self.status("Current frame has no WCS for SAMP catalog overlay", 3000)
            return

        table = self.read_samp_table(url, table_format)
        if table is None or len(table) == 0:
            self.status(f"Failed to load SAMP catalog: {table_id}", 3000)
            return

        coords = self.catalog_coordinates(table)
        if not coords:
            self.status("SAMP catalog has no usable RA/Dec columns", 3000)
            return

        sources: list[tuple[float, float]] = []
        for coord in coords:
            pixel = self.window.region.world_to_pixel(coord.ra.deg, coord.dec.deg)
            if pixel is not None:
                sources.append(pixel)

        if not sources:
            self.status("No plottable sources in SAMP catalog", 3000)
            return

        self.window._samp_catalog_sources[frame.frame_id] = sources
        self.rebuild_markers(frame)
        self.window.region.show_frame_regions(frame)
        self.status(f"Loaded SAMP catalog {table_id}: {len(sources)} sources", 4000)

    def read_samp_table(self, url: str, table_format: str) -> Table | None:
        """Read SAMP table from URL/path."""
        target = url
        parsed = urlparse(url)
        if parsed.scheme == "file":
            target = unquote(parsed.path)

        try:
            return Table.read(target, format=table_format)
        except Exception:
            try:
                return Table.read(target)
            except Exception:
                return None

    def catalog_coordinates(self, table: Table) -> list[SkyCoord] | None:
        """Extract ICRS coordinates from a table."""
        ra_col: str | None = None
        dec_col: str | None = None
        for col in table.colnames:
            col_lower = col.lower()
            if col_lower in ("ra", "_ra", "raj2000", "ra_icrs", "ra_j2000"):
                ra_col = col
            elif col_lower in ("dec", "_dec", "dej2000", "de", "dec_icrs", "dec_j2000"):
                dec_col = col
        if ra_col is None or dec_col is None:
            return None

        coords: list[SkyCoord] = []
        for row in table:
            try:
                coord = SkyCoord(
                    ra=float(row[ra_col]),
                    dec=float(row[dec_col]),
                    unit=(u.deg, u.deg),
                    frame="icrs",
                )
                coords.append(coord)
            except Exception:
                continue
        return coords if coords else None

    def build_marker(self, x: float, y: float) -> BaseRegion:
        """Create a region marking a SAMP catalog source.

        Tagged with origin="samp_catalog" so `_rebuild_samp_regions_for_frame`
        can replace exactly these regions when the marker style changes,
        without disturbing anything the user drew.
        """
        size = max(1.0, float(self.window._samp_marker_size))
        shape = self.window._samp_marker_shape
        common = {"color": self.window._samp_marker_color, "origin": "samp_catalog"}

        if shape == "circle":
            return Circle(center=(x, y), radius=size, **common)
        if shape == "box":
            return Box(center=(x, y), width_box=size * 2, height_box=size * 2, **common)
        if shape == "ellipse":
            return Ellipse(center=(x, y), semi_major=size, semi_minor=size, **common)
        return Point(center=(x, y), size=int(round(size * 2)), **common)

    def rebuild_markers(self, frame: Frame) -> None:
        """Rebuild SAMP regions for a frame from stored source positions."""
        frame.regions = [
            region for region in frame.regions if getattr(region, "origin", "user") != "samp_catalog"
        ]
        for x, y in self.window._samp_catalog_sources.get(frame.frame_id, []):
            frame.regions.append(self.build_marker(x, y))

    def refresh_markers(self) -> None:
        """Refresh SAMP catalog marker rendering with current style."""
        for frame in self.frames.frames:
            if frame.frame_id in self.window._samp_catalog_sources:
                self.rebuild_markers(frame)
        self.window.region.show_frame_regions(self.frames.current_frame)

    def choose_marker_color(self) -> None:
        """Change SAMP catalog marker color."""
        color = QColorDialog.getColor(self.window._samp_marker_color, self.window, "SAMP Marker Color")
        if not color.isValid():
            return
        self.window._samp_marker_color = color
        self.refresh_markers()
        self.status("Updated SAMP marker color", 2000)

    def choose_marker_shape(self) -> None:
        """Change SAMP catalog marker shape."""
        shape_map = {
            "Point": "point",
            "Circle": "circle",
            "Box": "box",
            "Ellipse": "ellipse",
        }
        labels = list(shape_map.keys())
        current_label = next(
            (label for label, value in shape_map.items() if value == self.window._samp_marker_shape), "Point"
        )
        current_index = labels.index(current_label)
        selected, ok = QInputDialog.getItem(
            self.window,
            "SAMP Marker Shape",
            "Shape:",
            labels,
            current_index,
            False,
        )
        if not ok:
            return
        self.window._samp_marker_shape = shape_map[selected]
        self.refresh_markers()
        self.status(f"SAMP marker shape: {selected}", 2000)

    def choose_marker_size(self) -> None:
        """Change SAMP catalog marker size."""
        size, ok = QInputDialog.getDouble(
            self.window,
            "SAMP Marker Size",
            "Size (pixels):",
            float(self.window._samp_marker_size),
            1.0,
            100.0,
            1,
        )
        if not ok:
            return
        self.window._samp_marker_size = float(size)
        self.refresh_markers()
        self.status(f"SAMP marker size: {self.window._samp_marker_size:.1f}", 2000)

    def query_coordinates(self) -> tuple[float, float]:
        """Get query coordinates from cursor WCS or image center."""
        if (
            self.window._last_mouse_pos is not None
            and self.window.wcs_handler
            and self.window.wcs_handler.is_valid
        ):
            x, y = self.window._last_mouse_pos
            ra, dec = self.window.wcs_handler.pixel_to_world(x, y)
            return ra, dec
        if (
            self.window.image_data is not None
            and self.window.wcs_handler
            and self.window.wcs_handler.is_valid
        ):
            cx = self.window.image_data.shape[1] / 2
            cy = self.window.image_data.shape[0] / 2
            ra, dec = self.window.wcs_handler.pixel_to_world(cx, cy)
            return ra, dec
        return (0.0, 0.0)

    def pick_access_url(self, table: Table) -> str:
        """Pick access URL from SIAP table."""
        for col in ("access_url", "download", "url", "accessURL", "AccessURL"):
            if col in table.colnames:
                return str(table[col][0])
        return ""
