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
The View menu: the window's layout, and what it shows.

DS9's View menu is one four-valued layout radio group, five panel toggles,
four frame-decoration toggles, and one toggle per information-panel field
(`ViewMainMenu` in `ds9/library/mview.tcl`). Every entry writes a flag into
the `view(...)` array and calls `LayoutView`, `LayoutFrames` or
`LayoutInfoPanel`. This controller is that: it owns the window's `ViewState`,
and every setter writes a flag and re-lays out.

It also feeds the information panel, since the panel's contents are part of
what View shows: the file and object rows on a load, the coordinate and value
rows on every mouse move.

Still missing against DS9 (PLAN.md §5.3): Multiple Colorbars is a flag with
no per-frame colorbar behind it yet (M5), and the Amplifier and Detector rows
read the same values as Physical because NCRADS9 does not parse `ATM*`/`DTM*`
(M4). Both are wired and both say so in the status bar.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ...coordinates.physical_coords import PhysicalTransform
from ...core.wcs_handler import WCSHandler, available_alternates
from ..layout.view_state import INFO_FIELDS, PANEL_NAMES, ViewLayout
from .base import Controller

if TYPE_CHECKING:
    from ..main_window import MainWindow

#: Menu attribute -> the layout it selects.
LAYOUT_ACTIONS: dict[str, ViewLayout] = {
    "action_view_horizontal": ViewLayout.HORIZONTAL,
    "action_view_vertical": ViewLayout.VERTICAL,
    "action_view_basic": ViewLayout.BASIC,
    "action_view_advanced": ViewLayout.ADVANCED,
}

#: Panel flag -> its menu attribute.
PANEL_ACTIONS: dict[str, str] = {
    "info": "action_view_info",
    "panner": "action_view_panner",
    "magnifier": "action_view_magnifier",
    "buttons": "action_view_buttons",
    "icons": "action_view_icons",
    "colorbar": "action_view_colorbar",
    "multi": "action_view_multi_colorbar",
    "graph_horizontal": "action_view_graph_horizontal",
    "graph_vertical": "action_view_graph_vertical",
}

#: Flags that are recorded and reported but have nothing behind them yet,
#: with the milestone that gives them an effect. Empty since M5-12 gave
#: Multiple Colorbars its behaviour; kept because the mechanism is how a
#: half-built toggle should announce itself.
UNIMPLEMENTED_PANELS: dict[str, str] = {}


class ViewController(Controller):
    """Owns the View menu, the window's layout, and the information panel."""

    def __init__(self, window: MainWindow) -> None:
        """
        Args:
            window: The main window, as for every controller.
        """
        super().__init__(window)
        #: Alternate WCS handlers for the current frame, and which frame they
        #: belong to. See `_alternate_handlers`.
        self._alternates: dict[str, WCSHandler] = {}
        self._alternates_frame_id: int | None = None

    def connect(self) -> None:
        """Wire the View menu."""
        for attribute, layout in LAYOUT_ACTIONS.items():
            action = getattr(self.menu, attribute)
            action.triggered.connect(lambda _checked=False, value=layout: self.set_layout(value))

        for name, attribute in PANEL_ACTIONS.items():
            action = getattr(self.menu, attribute)
            action.toggled.connect(lambda visible, key=name: self.set_panel(key, visible))

        for name, action in self.menu.info_field_actions.items():
            action.toggled.connect(lambda visible, key=name: self.set_info_field(key, visible))

        self.menu.action_fullscreen.triggered.connect(self.set_fullscreen)
        self.menu.action_show_statusbar.triggered.connect(self.set_statusbar_visible)

    def sync(self) -> None:
        """Bring the menu's tick marks in step with the state."""
        state = self.state
        for attribute, layout in LAYOUT_ACTIONS.items():
            getattr(self.menu, attribute).setChecked(state.layout is layout)
        for name, attribute in PANEL_ACTIONS.items():
            getattr(self.menu, attribute).setChecked(getattr(state, name))
        for name, action in self.menu.info_field_actions.items():
            action.setChecked(state.field_visible(name))

    # -- state ---------------------------------------------------------------

    @property
    def state(self):
        """The window's `ViewState`."""
        return self.window.view_state

    @property
    def info_panel(self):
        """The information panel."""
        return self.window.info_panel

    def set_layout(self, layout: ViewLayout | str) -> None:
        """Switch between the horizontal, vertical, basic and advanced layouts.

        Args:
            layout: A `ViewLayout`, or one of its values as a string.
        """
        value = ViewLayout(layout) if isinstance(layout, str) else layout
        self.state.layout = value
        self.apply()
        self.status(f"Layout: {value.value}")

    def set_panel(self, name: str, visible: bool) -> None:
        """Show or hide one panel.

        Args:
            name: One of `PANEL_NAMES`.
            visible: Whether to show it.
        """
        if name not in PANEL_NAMES:
            self.status(f"Unknown panel: {name}")
            return
        setattr(self.state, name, bool(visible))
        self.apply()

        milestone = UNIMPLEMENTED_PANELS.get(name)
        if milestone is not None:
            self.status(f"{name.replace('_', ' ')} has no effect until {milestone}")

    def set_info_field(self, name: str, visible: bool) -> None:
        """Show or hide one information-panel field.

        Args:
            name: One of `INFO_FIELDS`.
            visible: Whether to show it.
        """
        if name not in INFO_FIELDS:
            self.status(f"Unknown info-panel field: {name}")
            return
        self.state.set_field_visible(name, visible)
        self.info_panel.apply_state(self.state)

    def apply(self) -> None:
        """Re-lay out the window from the current state.

        DS9's `LayoutView`: re-grid the shell, re-grid the information panel,
        and show or hide the icon bars.
        """
        self.window.shell.relayout(self.state)
        self.info_panel.apply_state(self.state)
        self.window.main_toolbar.setVisible(self.state.icons)
        self.refresh_info()

    # -- NCRADS9 additions ---------------------------------------------------

    def set_fullscreen(self, fullscreen: bool) -> None:
        """Show the window full screen, or return it to normal."""
        if fullscreen:
            self.window.showFullScreen()
        else:
            self.window.showNormal()

    def set_toolbar_visible(self, visible: bool) -> None:
        """Show or hide the toolbar. DS9 calls this Icons."""
        self.set_panel("icons", visible)

    def set_statusbar_visible(self, visible: bool) -> None:
        """Show or hide the status bar."""
        self.window.statusBar().setVisible(visible)

    def set_colorbar_visible(self, visible: bool) -> None:
        """Show or hide the colorbar."""
        self.set_panel("colorbar", visible)

    def set_graph_visible(self, axis: str, visible: bool) -> None:
        """Show or hide one of the cut graphs.

        Args:
            axis: "horizontal" or "vertical".
            visible: Whether to show it.
        """
        self.set_panel(f"graph_{axis}", visible)

    # -- feeding the information panel ---------------------------------------

    def refresh_info(self) -> None:
        """Refill the rows that describe the loaded image.

        Cheap enough to call on every load, frame change and scale change:
        it reads the header and the cached scale limits, not the pixels --
        except for min/max, which is only computed when that row is shown.
        """
        panel = self.info_panel
        frame = self.frame
        if frame is None:
            panel.clear()
            return

        panel.set_filename(str(frame.filepath) if frame.filepath else "")
        header = self._header()
        panel.set_object(str(header.get("OBJECT", "")) if header else "")
        panel.set_units(str(header.get("BUNIT", "")) if header else "")

        index = self.frames.current_index + 1
        panel.set_frame(
            f"Frame {index}",
            f"{self._zoom():.4g}",
            f"{getattr(frame, 'rotation', 0.0):.4g}",
        )

        low, high = self.window.z1, self.window.z2
        panel.set_lowhigh("" if low is None else f"{low:.6g}", "" if high is None else f"{high:.6g}")

        if self.state.field_visible("minmax"):
            self._refresh_minmax()

    def _refresh_minmax(self) -> None:
        """Fill the Min and Max rows, with the position of each extreme."""
        data = self.window.image_data
        panel = self.info_panel
        if data is None or data.size == 0:
            panel.set_minmax("", "")
            return
        if np.all(np.isnan(data)):
            panel.set_minmax("nan", "nan")
            return

        rows = data.shape[0]
        low_index = np.unravel_index(int(np.nanargmin(data)), data.shape)
        high_index = np.unravel_index(int(np.nanargmax(data)), data.shape)
        panel.set_minmax(
            f"{float(np.nanmin(data)):.6g}",
            f"{float(np.nanmax(data)):.6g}",
            # The panel reports image coordinates, which count from the
            # bottom-left; numpy row zero is the top.
            (f"{int(low_index[1])}", f"{rows - 1 - int(low_index[0])}"),
            (f"{int(high_index[1])}", f"{rows - 1 - int(high_index[0])}"),
        )

    def update_cursor(self, x: int, y: int) -> None:
        """Fill the rows that track the pointer.

        Args:
            x: Image column under the pointer, counting from zero.
            y: Image row under the pointer, counting from the bottom.
        """
        panel = self.info_panel
        data = self.window.image_data
        if data is None:
            panel.clear_cursor()
            return

        # DS9 numbers image pixels from one, and its y axis runs upwards.
        panel.set_coords("image", f"{x + 1}", f"{y + 1}")

        transform = self._physical()
        px, py = transform.image_to_physical(x + 1, y + 1)
        for system in ("physical", "amplifier", "detector"):
            panel.set_coords(system, f"{px:.4g}", f"{py:.4g}")

        row = data.shape[0] - 1 - y
        if 0 <= row < data.shape[0] and 0 <= x < data.shape[1]:
            panel.set_value(f"{data[row, x]:.6g}")
        else:
            panel.set_value("")

        handler = self.window.wcs_handler
        if handler is not None and handler.is_valid:
            ra, dec = handler.pixel_to_world(x, y)
            lon, lat = self.coords.format_sky(ra, dec)
            panel.set_wcs(self.coords.sky.value, lon, lat)
        else:
            panel.set_wcs("", "", "")

        self._update_alternate_wcs(x, y)

        if self.state.field_visible("keyword"):
            self._refresh_keyword()

    def _update_alternate_wcs(self, x: int, y: int) -> None:
        """Fill whichever of the `wcs_a`..`wcs_z` rows are shown.

        A FITS header may carry several WCS descriptions, suffixed A..Z, and
        DS9 lists all twenty-six on `View -> Multiple WCS`. Only the rows the
        user has turned on are computed, and only for the letters this header
        actually declares -- the rest are blanked so a stale reading from a
        previous frame cannot linger.
        """
        panel = self.info_panel
        wanted = [
            suffix
            for suffix in available_alternates(self._header())
            if self.state.field_visible(f"wcs_{suffix}")
        ]
        for suffix, handler in self._alternate_handlers().items():
            if suffix not in wanted:
                panel.set_wcs("", "", "", suffix=suffix)
                continue
            lon, lat = handler.pixel_to_world(x, y)
            panel.set_wcs(
                f"wcs{suffix}",
                *self.coords.format_pair(float(lon), float(lat)),
                suffix=suffix,
            )

    def _alternate_handlers(self) -> dict[str, WCSHandler]:
        """The current frame's alternate WCS handlers, built once per frame.

        Building an `astropy.wcs.WCS` is far too slow to do on every mouse
        move, so they are cached against the frame they came from.
        """
        frame = self.frame
        if frame is None:
            return {}
        if self._alternates_frame_id == frame.frame_id:
            return self._alternates
        header = self._header()
        self._alternates = {suffix: WCSHandler(header, key=suffix) for suffix in available_alternates(header)}
        self._alternates_frame_id = frame.frame_id
        return self._alternates

    def _refresh_keyword(self) -> None:
        """Show the value of whichever FITS card the user typed."""
        keyword = self.info_panel.keyword_entry.text().strip().upper()
        header = self._header()
        if not keyword or header is None:
            self.info_panel.set_keyword("")
            return
        self.info_panel.set_keyword(str(header.get(keyword, "")))

    # -- helpers -------------------------------------------------------------

    def _header(self):
        """The current frame's header, or None.

        Reads only what is already in memory. `MainWindow.fits_handler` would
        re-open the file when a frame carries a path but no handler, and this
        runs on every redisplay -- the panel is a readout, not a loader.
        """
        frame = self.frame
        if frame is None:
            return None
        if frame.header is not None:
            return frame.header
        return getattr(frame.fits_handler, "header", None)

    def _physical(self) -> PhysicalTransform:
        """The current frame's image-to-physical mapping."""
        header = self._header()
        return PhysicalTransform() if header is None else PhysicalTransform.from_header(header)

    def _zoom(self) -> float:
        """The viewer's current zoom, or 1.0 if it does not report one."""
        return float(getattr(self.viewer, "zoom_factor", 1.0) or 1.0)
