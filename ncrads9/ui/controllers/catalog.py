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

from ...catalogs import (
    catalog_file,
    catalog_match,
    catalog_query,
    catalog_search,
    footprints,
    servers,
)
from ...catalogs.catalog_set import CatalogSet, LoadedCatalog
from ..dialogs.catalog_search_dialog import CatalogSearchDialog
from ..dialogs.catalog_window import CatalogWindow
from ..dialogs.symbol_editor_dialog import SymbolEditorDialog
from .base import Controller

#: The radius a menu query uses, in arcseconds. DS9's `pcat(loc)`.
DEFAULT_RADIUS_ARCSEC = 500.0

#: The colour footprint outlines are drawn in.
FOOTPRINT_COLOR = "yellow"

#: The tag every footprint outline carries, so Clear All can find them.
FOOTPRINT_TAG = "footprint"


def _footprint_tag(name: str) -> str:
    """The tag outlines from one server carry."""
    return f"{FOOTPRINT_TAG}:{name}"


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
        #: How the catalogue *search* fetches. Replaced in tests, like
        #: `transport`; `None` means the real client.
        self.search_fetcher = None
        #: How footprint queries fetch, likewise.
        self.footprint_fetcher = None
        #: The search dialog, kept so it is not collected while shown.
        self._search_dialog = None
        #: DS9's `catalog` settings that have no control of their own here
        #: -- the match parameters, the row limit, the coordinate system a
        #: listing is written in. XPA sets them; the tool reads them back.
        self.settings: dict[str, str] = {
            "maxrows": "5000",
            "match_error": "2 arcsec",
            "match_function": "1and2",
            "match_return": "1and2",
            "match_unique": "yes",
        }

    def connect(self) -> None:
        """Wire every catalogue on the menu, plus load and clear."""
        menu = self.menu
        for name, action in menu.catalog_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.query(key))

        menu.action_catalog_load.triggered.connect(lambda _checked=False: self.load_file())
        menu.action_catalog_clear_all.triggered.connect(lambda _checked=False: self.clear_all())
        menu.action_catalog_search.triggered.connect(lambda _checked=False: self.search())
        menu.action_catalog_match.triggered.connect(lambda _checked=False: self.show_match_dialog())
        menu.action_catalog_tool.triggered.connect(lambda _checked=False: self.show_tool())

        for name, action in menu.footprint_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.query_footprints(key))
        menu.action_footprint_clear_all.triggered.connect(lambda _checked=False: self.clear_footprints())

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
        """Open DS9's Search for Catalogs dialog (M8-10)."""
        existing = getattr(self, "_search_dialog", None)
        if existing is not None:
            existing.raise_()
            existing.activateWindow()
            return

        dialog = CatalogSearchDialog(self.mirror, self.window)
        dialog.search_requested.connect(
            lambda request, d=dialog: d.show_result(
                catalog_search.search(request, fetcher=self.search_fetcher)
            )
        )
        dialog.catalog_chosen.connect(self.query_identifier)
        dialog.finished.connect(lambda _result: setattr(self, "_search_dialog", None))
        self._search_dialog = dialog
        dialog.show()

    def query_identifier(self, identifier: str) -> LoadedCatalog | None:
        """Query a VizieR catalogue by identifier, from the search results.

        Not on DS9's menu, so it has no `catXXX` name; a server entry is
        made for it on the spot.
        """
        center = self.frame_center()
        if center is None:
            self.status("This frame has no WCS, so there is nothing to search around", 4000)
            return None

        server = servers.CatalogServer(
            label=identifier,
            name=f"cat:{identifier}",
            service=servers.Service.CDS,
            identifier=identifier,
            section="",
        )
        request = catalog_query.QueryRequest(
            server=server,
            center=center,
            radius=DEFAULT_RADIUS_ARCSEC * u.arcsec,
            mirror=self.mirror,
        )
        self.status(f"Querying {identifier}...")
        result = catalog_query.run(request, transport=self.transport)
        self.status(result.message, 4000)
        if result.table is None:
            return None
        return self.add(LoadedCatalog(name=identifier, table=result.table, source=f"cds:{identifier}"))

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
        """Open DS9's symbol editor on one catalogue (M8-3)."""
        dialog = SymbolEditorDialog(catalog.symbols, catalog.columns, self.window)
        dialog.symbols_changed.connect(lambda symbols, target=catalog: self._apply_symbols(target, symbols))
        dialog.exec()

    def _apply_symbols(self, catalog: LoadedCatalog, symbols) -> None:
        """Take the edited rules and redraw."""
        catalog.symbols = list(symbols)
        self.refresh_overlay()
        self.status(f"{catalog.name}: {len(symbols)} symbol rule{'s' if len(symbols) != 1 else ''}")

    # -- matching two catalogues (M8-6) -----------------------------------------

    def match(
        self,
        first: str,
        second: str,
        radius_arcsec: float = catalog_match.DEFAULT_RADIUS_ARCSEC,
        function: str = "1and2",
        columns: str = "1and2",
        unique: bool = True,
    ) -> LoadedCatalog | None:
        """Match two loaded catalogues, DS9's Catalog Match.

        Args:
            first: The first catalogue's name.
            second: The second's.
            radius_arcsec: How close two rows must be.
            function: `1and2`, `1not2` or `2not1`.
            columns: For `1and2`, `1and2` for both catalogues' columns or
                `1only` for the first's.
            unique: Whether each row may appear once only.

        Returns:
            The match, loaded as a catalogue of its own, or None.
        """
        left = self.catalogs.by_name(first)
        right = self.catalogs.by_name(second)
        if left is None or right is None:
            self.status("Two loaded catalogs are needed to match", 3000)
            return None

        try:
            matched = catalog_match.match(left.table, right.table, radius_arcsec, function, columns, unique)
        except catalog_match.MatchError as exc:
            self.status(str(exc), 4000)
            return None

        if not len(matched):
            self.status(f"No matches between {first} and {second}", 4000)
            return None

        return self.add(
            LoadedCatalog(
                name=f"{first} {function} {second}",
                table=matched,
                source=f"match:{radius_arcsec:g}arcsec",
            )
        )

    def show_match_dialog(self) -> None:
        """Ask which two catalogues to match, and with what radius."""
        names = [entry.name for entry in self.catalogs]
        if len(names) < 2:
            self.status("Load two catalogs to match them", 3000)
            return

        first, accepted = QInputDialog.getItem(
            self.window, "Catalog Match", "First catalog:", names, 0, False
        )
        if not accepted:
            return
        second, accepted = QInputDialog.getItem(
            self.window, "Catalog Match", "Second catalog:", names, 1, False
        )
        if not accepted:
            return
        radius, accepted = QInputDialog.getDouble(
            self.window,
            "Catalog Match",
            "Radius (arcsec):",
            catalog_match.DEFAULT_RADIUS_ARCSEC,
            0.01,
            3600.0,
            2,
        )
        if not accepted:
            return
        functions = [choice.value for choice in catalog_match.MatchFunction]
        function, accepted = QInputDialog.getItem(
            self.window, "Catalog Match", "Function:", functions, 0, False
        )
        if not accepted:
            return
        self.match(first, second, radius, function)

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

    # -- footprint servers (M8-20) ---------------------------------------------

    def query_footprints(
        self,
        name: str,
        radius_arcmin: float = footprints.DEFAULT_RADIUS_ARCMIN,
    ) -> LoadedCatalog | None:
        """Ask a footprint server what covers the frame's centre.

        The observations load as a catalogue -- filterable and listable
        like any other -- and their outlines are drawn as polygon regions,
        which is what DS9's `fpreg.tcl` does with them.
        """
        server = footprints.by_name(name)
        if server is None:
            self.status(f"No such footprint server: {name}", 3000)
            return None

        center = self.frame_center()
        if center is None:
            self.status("This frame has no WCS, so there is nothing to search around", 4000)
            return None

        request = footprints.FootprintRequest(
            server=server,
            longitude=float(center.ra.deg),
            latitude=float(center.dec.deg),
            radius_arcmin=radius_arcmin,
        )
        self.status(f"Asking {server.label}...")
        result = footprints.query(request, fetcher=self.footprint_fetcher)
        self.status(result.message, 5000)
        if result.table is None:
            return None

        loaded = self.add(
            LoadedCatalog(name=server.label, table=result.table, source=f"footprint:{server.name}")
        )
        self.draw_footprints(server.name, result.polygons)
        return loaded

    def draw_footprints(self, name: str, polygons) -> int:
        """Draw footprint outlines as polygon regions.

        Tagged with the server's name, so Clear All can find them again --
        an outline is a region once drawn, and there is no other way to
        tell it from one the user made.

        Returns:
            How many were drawn.
        """
        frame = self.frame
        handler = getattr(frame, "wcs_handler", None) if frame else None
        if frame is None or handler is None or not getattr(handler, "is_valid", False):
            return 0

        from ...regions.shapes.polygon import Polygon

        drawn = 0
        for outline in polygons:
            vertices = []
            for longitude, latitude in outline:
                try:
                    x, y = handler.world_to_pixel(longitude, latitude)
                except Exception:
                    continue
                vertices.append((float(x), float(y)))
            if len(vertices) < 3:
                continue
            frame.regions.append(
                Polygon(vertices=vertices, color=FOOTPRINT_COLOR, tags=[_footprint_tag(name)])
            )
            drawn += 1

        self.window.region.refresh_overlay()
        return drawn

    def clear_footprints(self) -> None:
        """Remove every footprint outline and catalogue, DS9's Clear All."""
        frame = self.frame
        removed = 0
        if frame is not None:
            before = len(frame.regions)
            frame.regions = [
                region
                for region in frame.regions
                if not any(tag.startswith(FOOTPRINT_TAG) for tag in region.tags)
            ]
            removed = before - len(frame.regions)
            self.window.region.refresh_overlay()

        names = [entry.name for entry in self.catalogs if entry.source.startswith("footprint:")]
        for entry_name in names:
            entry = self.catalogs.by_name(entry_name)
            if entry is not None:
                self.clear(entry)

        self.status(f"Cleared {removed} footprint outline{'s' if removed != 1 else ''}")

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
