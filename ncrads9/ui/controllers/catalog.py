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
The Catalogs menu: querying servers, loading files, drawing symbols.

Forty-odd catalogues on DS9's menu, a local file loader, and one list window
per loaded catalogue, with the symbols on a layer of their own over the
image. The queries run through `catalogs.catalog_query`, whose transport is
injectable -- so this controller can be tested without a network, which for
a feature that is nothing but network calls is the difference between having
tests and not.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from PyQt6.QtWidgets import QFileDialog, QInputDialog

from ...catalogs import catalog_file, catalog_query, servers
from ...catalogs.catalog_set import CatalogSet, LoadedCatalog
from ..dialogs.catalog_window import CatalogWindow
from .base import Controller

#: The radius a menu query uses, in arcseconds. DS9's `pcat(loc)`.
DEFAULT_RADIUS_ARCSEC = 500.0


class CatalogController(Controller):
    """Owns the Catalogs menu and the catalogues loaded on the frame."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: The catalogues loaded, and their symbols.
        self.catalogs = CatalogSet()
        #: One list window per catalogue, by name.
        self._windows: dict[str, CatalogWindow] = {}
        #: How queries are made. Replaced in tests; `None` means the real
        #: network client.
        self.transport = None
        #: Which VizieR mirror to ask.
        self.mirror = servers.DEFAULT_MIRROR

    def connect(self) -> None:
        """Wire every catalogue on the menu, plus load and clear."""
        menu = self.menu
        for name, action in menu.catalog_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.query(key))

        menu.action_catalog_load.triggered.connect(lambda _checked=False: self.load_file())
        menu.action_catalog_clear_all.triggered.connect(lambda _checked=False: self.clear_all())
        menu.action_catalog_search.triggered.connect(lambda _checked=False: self.search())
        menu.action_catalog_tool.triggered.connect(lambda _checked=False: self.show_tool())

    def attach(self, viewer) -> None:
        """Hook up a newly built viewer's catalogue layer.

        Lives here rather than in `MainWindow._connect_viewer`, which the
        M2 guard caps at 600 lines -- and which this pushed over it.
        """
        overlay = getattr(viewer, "catalog_overlay", None)
        if overlay is None:
            return
        overlay.symbol_picked.connect(self.on_symbol_picked)
        # No redraw here: this runs while the window is still being built,
        # before `image_viewer` is set, and there is nothing loaded yet.
        # `sync` redraws on every frame change from then on.

    # -- querying ---------------------------------------------------------------

    def frame_center(self) -> SkyCoord | None:
        """The middle of the current frame, in sky coordinates.

        None when the frame has no WCS: a cone search needs a position, and
        an image with no WCS has none to offer.
        """
        frame = self.frame
        handler = getattr(frame, "wcs_handler", None) if frame else None
        if handler is None or not getattr(handler, "is_valid", False):
            return None

        data = getattr(frame, "image_data", None)
        if data is None:
            return None
        try:
            longitude, latitude = handler.pixel_to_world(data.shape[1] / 2.0, data.shape[0] / 2.0)
        except Exception:
            return None
        return SkyCoord(float(longitude) * u.deg, float(latitude) * u.deg)

    def query(self, name: str, radius_arcsec: float = DEFAULT_RADIUS_ARCSEC) -> LoadedCatalog | None:
        """Query one of DS9's catalogues around the frame's centre.

        Args:
            name: DS9's catalogue name, e.g. `catgaia`.
            radius_arcsec: The cone radius.

        Returns:
            The catalogue loaded, or None if the query found nothing.
        """
        center = self.frame_center()
        if center is None:
            self.status("This frame has no WCS, so there is nothing to search around", 4000)
            return None

        try:
            request = catalog_query.request_for(name, center, radius_arcsec * u.arcsec, mirror=self.mirror)
        except catalog_query.CatalogQueryError as exc:
            self.status(str(exc), 3000)
            return None

        self.status(f"Querying {request.server.label}...")
        result = catalog_query.run(request, transport=self.transport)
        self.status(result.message, 4000)
        if result.table is None:
            return None

        return self.add(
            LoadedCatalog(
                name=request.server.label,
                table=result.table,
                source=f"{request.server.service.value}:{request.server.identifier or name}",
            )
        )

    def load_file(self, path: str | None = None) -> LoadedCatalog | None:
        """Load a local catalogue file, DS9's Load Catalog."""
        if path is None:
            path, _filter = QFileDialog.getOpenFileName(
                self.window, "Load Catalog", "", catalog_file.FILE_FILTER
            )
            if not path:
                return None

        try:
            table = catalog_file.load(path)
        except catalog_file.CatalogFileError as exc:
            self.status(f"{Path(path).name}: {exc}", 5000)
            return None
        except OSError as exc:
            self.status(f"Cannot read {Path(path).name}: {exc}", 5000)
            return None

        loaded = self.add(LoadedCatalog(name=Path(path).stem, table=table, source=str(path)))
        self.status(f"Loaded {len(table)} rows from {Path(path).name}")
        return loaded

    def search(self) -> None:
        """DS9's Search for Catalogs, which M8-10 implements."""
        self.status("Searching for catalogs arrives in M8-10", 3000)

    # -- the catalogues on the frame ----------------------------------------------

    def add(self, catalog: LoadedCatalog) -> LoadedCatalog:
        """Take a catalogue, open its window and draw its symbols."""
        added = self.catalogs.add(catalog)
        self.show_window(added)
        self.refresh_overlay()
        return added

    def show_tool(self) -> None:
        """Open the list window of the catalogue most recently loaded."""
        if not self.catalogs:
            self.status("No catalogs are loaded", 3000)
            return
        self.show_window(self.catalogs.catalogs[-1])

    def show_window(self, catalog: LoadedCatalog) -> CatalogWindow:
        """Open, or raise, one catalogue's list window."""
        existing = self._windows.get(catalog.name)
        if existing is not None:
            existing.reload()
            existing.raise_()
            existing.activateWindow()
            return existing

        window = CatalogWindow(catalog, self.window)
        window.selection_changed.connect(lambda _rows: self.refresh_overlay())
        window.filter_changed.connect(lambda _text: self.refresh_overlay())
        window.command_requested.connect(
            lambda command, name=catalog.name: self.window_command(name, command)
        )
        window.finished.connect(lambda _result, name=catalog.name: self._windows.pop(name, None))
        self._windows[catalog.name] = window
        window.show()
        return window

    def window_command(self, name: str, command: str) -> None:
        """Run one of the list window's commands."""
        catalog = self.catalogs.by_name(name)
        if catalog is None:
            return
        if command.startswith("pan:"):
            self.pan_to(catalog, int(command.split(":", 1)[1]))
            return

        handler = {
            "save": self.save_file,
            "plot": self.plot,
            "regions": self.to_regions,
            "clear": self.clear,
            "symbols": self.edit_symbols,
        }.get(command)
        if handler is None:
            self.status(f"Unknown catalog command: {command}", 3000)
            return
        handler(catalog)

    def pan_to(self, catalog: LoadedCatalog, row: int) -> None:
        """Centre the image on one catalogue row's position."""
        coordinates = catalog.positions()
        if coordinates is None or row >= len(coordinates):
            self.status(f"{catalog.name} has no position for that row", 3000)
            return

        frame = self.frame
        handler = getattr(frame, "wcs_handler", None) if frame else None
        if handler is None or not getattr(handler, "is_valid", False):
            self.status("This frame has no WCS to pan through", 3000)
            return

        position = coordinates[row]
        try:
            x, y = handler.world_to_pixel(position.ra.deg, position.dec.deg)
        except Exception:
            self.status("That row is not on this image", 3000)
            return
        self.window.zoom.on_panner_pan(float(x), float(y))
        self.status(f"{catalog.name}: panned to row {row + 1}")

    def save_file(self, catalog: LoadedCatalog) -> None:
        """Save a catalogue as a local file, DS9's Save."""
        path, _filter = QFileDialog.getSaveFileName(self.window, "Save Catalog", "", catalog_file.FILE_FILTER)
        if not path:
            return
        try:
            catalog_file.save(path, catalog.filtered())
        except (catalog_file.CatalogFileError, OSError) as exc:
            self.status(f"Cannot write {Path(path).name}: {exc}", 5000)
            return
        self.status(f"Saved {catalog.name} to {Path(path).name}")

    def plot(self, catalog: LoadedCatalog) -> None:
        """Plot two of a catalogue's columns, DS9's Catalog Plot (M8-7)."""
        from ...analysis.plot import Dataset, PlotState

        numeric = [
            name
            for name in catalog.columns
            if getattr(catalog.table[name], "dtype", None) is not None
            and catalog.table[name].dtype.kind in "fiu"
        ]
        if len(numeric) < 2:
            self.status(f"{catalog.name} has no two numeric columns to plot", 4000)
            return

        x_name, accepted = QInputDialog.getItem(self.window, "Catalog Plot", "X axis:", numeric, 0, False)
        if not accepted:
            return
        y_name, accepted = QInputDialog.getItem(
            self.window, "Catalog Plot", "Y axis:", numeric, min(1, len(numeric) - 1), False
        )
        if not accepted:
            return

        rows = catalog.filtered()
        state = PlotState(title=catalog.name)
        state.x_axis.label = x_name
        state.y_axis.label = y_name
        state.add(
            Dataset(
                name=catalog.name,
                x=[float(value) for value in rows[x_name]],
                y=[float(value) for value in rows[y_name]],
            )
        )
        # Points, not a line: a catalogue's rows are in no particular order,
        # and joining them draws a scribble.
        from ...analysis.plot import PlotStyle

        state.style = PlotStyle.SCATTER
        self.window.analysis.show_plot(state)

    def to_regions(self, catalog: LoadedCatalog) -> None:
        """Turn a catalogue's symbols into regions, DS9's Copy to Regions.

        The selection if there is one, otherwise everything the filter
        keeps -- which is what DS9 does, and what makes it useful for
        feeding an analysis task a handful of sources.
        """
        frame = self.frame
        handler = getattr(frame, "wcs_handler", None) if frame else None
        if frame is None or handler is None or not getattr(handler, "is_valid", False):
            self.status("This frame has no WCS, so a catalogue cannot become regions", 4000)
            return

        from ...regions.shapes.circle import Circle

        symbols = catalog.draw()
        chosen = [symbol for symbol in symbols if symbol.selected] or symbols
        if not chosen:
            self.status(f"{catalog.name} has nothing to copy", 3000)
            return

        made = 0
        for symbol in chosen:
            try:
                x, y = handler.world_to_pixel(symbol.longitude, symbol.latitude)
            except Exception:
                continue
            frame.regions.append(
                Circle(
                    center=(float(x), float(y)),
                    radius=max(1.0, symbol.size / 2.0),
                    color=symbol.color,
                    text=symbol.text,
                )
            )
            made += 1

        self.window.region.refresh_overlay()
        self.status(f"Copied {made} catalog symbol{'s' if made != 1 else ''} to regions")

    def edit_symbols(self, catalog: LoadedCatalog) -> None:
        """DS9's symbol editor, which M8-3 implements."""
        self.status("The symbol editor arrives in M8-3", 3000)

    def clear(self, catalog: LoadedCatalog) -> None:
        """Remove one catalogue."""
        window = self._windows.pop(catalog.name, None)
        if window is not None:
            window.close()
        self.catalogs.remove(catalog.name)
        self.refresh_overlay()
        self.status(f"Cleared {catalog.name}")

    def clear_all(self) -> None:
        """Remove every catalogue, DS9's Clear All."""
        if not self.catalogs:
            self.status("No catalogs are loaded", 2500)
            return
        for window in list(self._windows.values()):
            window.close()
        self._windows.clear()
        count = self.catalogs.clear()
        self.refresh_overlay()
        self.status(f"Cleared {count} catalog{'s' if count != 1 else ''}")

    # -- the overlay -----------------------------------------------------------------

    def overlay(self):
        """The catalogue symbol layer on the current viewer, if there is one."""
        return getattr(self.viewer, "catalog_overlay", None)

    def refresh_overlay(self) -> None:
        """Redraw the symbols of every visible catalogue."""
        overlay = self.overlay()
        if overlay is None:
            return

        frame = self.frame
        handler = getattr(frame, "wcs_handler", None) if frame else None
        if handler is None or not getattr(handler, "is_valid", False):
            # Nowhere to put them: a catalogue is sky positions, and this
            # frame has no sky.
            overlay.set_projection(None)
            overlay.clear()
            return

        def to_image(longitude: float, latitude: float):
            try:
                x, y = handler.world_to_pixel(longitude, latitude)
            except Exception:
                return None
            return (float(x), float(y))

        overlay.set_projection(to_image)
        owner = self.catalogs.catalogs[-1].name if self.catalogs else ""
        overlay.set_symbols(self.catalogs.draw(), owner)

    def on_symbol_picked(self, owner: str, row: int) -> None:
        """A symbol was clicked: select its row and show it in the window."""
        catalog = self.catalogs.by_name(owner)
        if catalog is None:
            return
        catalog.select([row])
        window = self._windows.get(owner)
        if window is not None:
            window.sync_selection()
        self.refresh_overlay()
        self.status(f"{catalog.name}: row {row + 1}")

    def sync(self) -> None:
        """Redraw after a frame change, since the WCS may be different."""
        self.refresh_overlay()
