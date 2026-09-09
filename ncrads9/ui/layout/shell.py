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
The fixed window layout: header row, buttonbar, canvas, colorbar.

NCRADS9 used to arrange these as free-floating `QDockWidget`s, which let the
user drag the panner out of the window and gave every panel its own title bar
(the panner and magnifier each ended up with two, being docks nested inside
docks). DS9 has no floating panels: `ds9(main)` is one Tk grid, and its
`LayoutViewHorz` / `LayoutViewVert` / `LayoutViewBasic` / `LayoutViewAdvanced`
procedures in `ds9/library/layout.tcl` re-grid the same widgets into fixed
positions. `WindowShell` is that grid.

The shell owns no state of its own: it reads a `ViewState` and arranges
whatever widgets it was handed. Nothing here touches image data, so the whole
class is testable by constructing it with stub widgets.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from .view_state import ViewLayout, ViewState

#: DS9's `canvas(gap)` -- the padding between the panels and the canvas.
GAP = 4


def _separator(orientation: Qt.Orientation) -> QFrame:
    """A one-pixel rule, matching DS9's `ttk::separator`."""
    frame = QFrame()
    frame.setFrameShape(
        QFrame.Shape.HLine if orientation == Qt.Orientation.Horizontal else QFrame.Shape.VLine
    )
    frame.setFrameShadow(QFrame.Shadow.Sunken)
    return frame


class WindowShell(QWidget):
    """The fixed arrangement of the main window's panels.

    Args:
        info_panel: The information panel.
        panner: The panner.
        magnifier: The magnifier.
        button_bar: The two-row category buttonbar.
        image_area: The scrollable canvas holding the image viewer.
        colorbar: The colorbar.
        graph_horizontal: The horizontal cut graph.
        graph_vertical: The vertical cut graph.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        *,
        info_panel: QWidget,
        panner: QWidget,
        magnifier: QWidget,
        button_bar: QWidget,
        image_area: QWidget,
        colorbar: QWidget,
        graph_horizontal: QWidget,
        graph_vertical: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.info_panel = info_panel
        self.panner = panner
        self.magnifier = magnifier
        self.button_bar = button_bar
        self.image_area = image_area
        self.colorbar = colorbar
        self.graph_horizontal = graph_horizontal
        self.graph_vertical = graph_vertical

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(0)

        self._header = self._build_header()
        self._header_separator = _separator(Qt.Orientation.Horizontal)
        self._buttons_separator = _separator(Qt.Orientation.Horizontal)
        self._canvas = self._build_canvas()

        #: Everything the grid manages. Anything not placed by `relayout` is
        #: hidden, which is what Tk's `grid forget` amounts to.
        self._managed: tuple[QWidget, ...] = (
            self._header,
            self._header_separator,
            self.button_bar,
            self._buttons_separator,
            self._canvas,
        )

        self.relayout(ViewState())

    # -- construction --------------------------------------------------------

    def _build_header(self) -> QWidget:
        """The row holding the information panel, magnifier and panner.

        DS9 packs the info panel to the left and the magnifier and panner to
        the right, in that order (`LayoutViewHorz`). The box direction is
        swapped per layout by `relayout`.
        """
        header = QWidget()
        self._header_box = QHBoxLayout(header)
        self._header_box.setContentsMargins(GAP, GAP, GAP, GAP)
        self._header_box.setSpacing(GAP)
        return header

    def _build_canvas(self) -> QWidget:
        """The canvas, its cut graphs and the colorbar.

        DS9's `LayoutFrames` builds the same nest: the graphs sit against the
        canvas edges and the colorbar below or beside the pair.
        """
        canvas = QWidget()
        outer = QVBoxLayout(canvas)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(GAP)

        plot_row = QWidget()
        self._plot_box = QHBoxLayout(plot_row)
        self._plot_box.setContentsMargins(0, 0, 0, 0)
        self._plot_box.setSpacing(GAP)
        self._plot_box.addWidget(self.image_area, 1)
        self._plot_box.addWidget(self.graph_vertical)

        self._canvas_box = outer
        outer.addWidget(plot_row, 1)
        outer.addWidget(self.graph_horizontal)
        outer.addWidget(self.colorbar)
        return canvas

    # -- layout --------------------------------------------------------------

    def relayout(self, state: ViewState) -> None:
        """Re-grid every panel to match `state`.

        Mirrors DS9's `LayoutView`: reset the grid, then place the widgets the
        chosen layout calls for.
        """
        self._clear()

        if state.layout == ViewLayout.VERTICAL:
            self._layout_vertical(state)
        elif state.layout == ViewLayout.BASIC:
            self._layout_basic()
        elif state.layout == ViewLayout.ADVANCED:
            self._layout_advanced(state)
        else:
            self._layout_horizontal(state)

        self._layout_header(state)
        self._layout_canvas(state)
        self._orient_button_bar(state)

    def _clear(self) -> None:
        """Empty the grid and hide everything it managed."""
        while self._grid.count():
            self._grid.takeAt(0)
        for index in range(5):
            self._grid.setRowStretch(index, 0)
            self._grid.setColumnStretch(index, 0)
        for widget in self._managed:
            widget.hide()

    def _place(self, widget: QWidget, row: int, column: int, *, span: int = 1) -> None:
        """Add one widget to the grid and show it."""
        self._grid.addWidget(widget, row, column, 1, span)
        widget.show()

    def _layout_horizontal(self, state: ViewState) -> None:
        """Header above the buttonbar, both above the canvas (DS9 default)."""
        self._grid.setRowStretch(4, 1)
        self._grid.setColumnStretch(0, 1)

        if state.header_visible:
            self._place(self._header, 0, 0)
            self._orient_separator(self._header_separator, Qt.Orientation.Horizontal)
            self._place(self._header_separator, 1, 0)

        if state.buttons:
            self._place(self.button_bar, 2, 0)
            self._orient_separator(self._buttons_separator, Qt.Orientation.Horizontal)
            self._place(self._buttons_separator, 3, 0)

        self._place(self._canvas, 4, 0)

    def _layout_vertical(self, state: ViewState) -> None:
        """Header and buttonbar down the left, canvas to their right."""
        self._grid.setRowStretch(0, 1)
        self._grid.setColumnStretch(4, 1)

        if state.header_visible:
            self._place(self._header, 0, 0)
            self._orient_separator(self._header_separator, Qt.Orientation.Vertical)
            self._place(self._header_separator, 0, 1)

        if state.buttons:
            self._place(self.button_bar, 0, 2)
            self._orient_separator(self._buttons_separator, Qt.Orientation.Vertical)
            self._place(self._buttons_separator, 0, 3)

        self._place(self._canvas, 0, 4)

    def _layout_basic(self) -> None:
        """Canvas only. DS9 shows no panels at all in Basic."""
        self._grid.setRowStretch(0, 1)
        self._grid.setColumnStretch(0, 1)
        self._place(self._canvas, 0, 0)

    def _layout_advanced(self, state: ViewState) -> None:
        """Canvas on the left, then the header, then the buttonbar."""
        self._grid.setRowStretch(2, 1)
        self._grid.setColumnStretch(2, 1)

        self._place(self._canvas, 2, 2)

        if state.header_visible:
            self._orient_separator(self._header_separator, Qt.Orientation.Vertical)
            self._place(self._header_separator, 2, 3)
            self._place(self._header, 2, 4)

        if state.buttons:
            self._orient_separator(self._buttons_separator, Qt.Orientation.Vertical)
            self._place(self._buttons_separator, 2, 5)
            self._place(self.button_bar, 2, 6)

    @staticmethod
    def _orient_separator(separator: QFrame, orientation: Qt.Orientation) -> None:
        """Turn a separator on its side, as DS9's `configure -orient` does."""
        separator.setFrameShape(
            QFrame.Shape.HLine if orientation == Qt.Orientation.Horizontal else QFrame.Shape.VLine
        )

    def _layout_header(self, state: ViewState) -> None:
        """Fill the header row, in the order the current layout wants.

        Horizontal runs left to right -- info, then magnifier, then panner.
        Vertical and Advanced stack them: magnifier, info, panner.
        """
        while self._header_box.count():
            self._header_box.takeAt(0)
        for widget in (self.info_panel, self.magnifier, self.panner):
            widget.hide()

        # Basic grids nothing but the canvas, so there is no header to fill
        # and its three panels stay hidden.
        if state.layout is ViewLayout.BASIC or not state.header_visible:
            return

        stacked = state.layout in (ViewLayout.VERTICAL, ViewLayout.ADVANCED)
        self._header_box.setDirection(
            QVBoxLayout.Direction.TopToBottom if stacked else QHBoxLayout.Direction.LeftToRight
        )

        if stacked:
            order: tuple[tuple[QWidget, bool], ...] = (
                (self.magnifier, state.magnifier),
                (self.info_panel, state.info),
                (self.panner, state.panner),
            )
        else:
            order = (
                (self.info_panel, state.info),
                (self.magnifier, state.magnifier),
                (self.panner, state.panner),
            )

        for widget, visible in order:
            if widget is self.info_panel and not visible:
                # Take the info panel's slack, so the panner and magnifier
                # stay against the far edge instead of drifting to the middle.
                self._header_box.addStretch(1)
                continue
            if not visible:
                continue
            # The info panel expands; the panner and magnifier are
            # fixed-size, as in DS9.
            self._header_box.addWidget(widget, 1 if widget is self.info_panel else 0)
            widget.show()

    def _orient_button_bar(self, state: ViewState) -> None:
        """Run the buttonbar down a column in the side-by-side layouts.

        A no-op for a bar that does not offer it, so the shell can still be
        built over stand-in widgets.
        """
        orient = getattr(self.button_bar, "set_orientation", None)
        if orient is not None:
            orient(state.layout in (ViewLayout.VERTICAL, ViewLayout.ADVANCED))

    def _layout_canvas(self, state: ViewState) -> None:
        """Show or hide the colorbar and the two cut graphs."""
        self.graph_horizontal.setVisible(state.graph_horizontal)
        self.graph_vertical.setVisible(state.graph_vertical)
        self.colorbar.setVisible(state.colorbar)
