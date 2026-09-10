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
The windows a region's Analysis menu opens.

Two of them: a text window for Statistics, which is what DS9 shows (its
`SimpleTextDialog`), and a plot window for the histogram, the radial profile
and the two cuts. Both are modeless and both can be told to measure again,
because the region under them moves -- that is what DS9's Auto Plot toggles
are for, and a window that showed a stale answer after the region moved
would be worse than no window.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...regions.base_region import BaseRegion
from ...regions.region_analysis import AnalysisError

#: How big the statistics window opens, in pixels. DS9's is 80 columns.
STATISTICS_SIZE = (760, 460)

#: How big a plot window opens.
PLOT_SIZE = (640, 460)


class RegionStatisticsDialog(QDialog):
    """DS9's Statistics window for one region.

    Args:
        region: The region measured. Held so `refresh` can measure it again
            after it has been moved or resized.
        provider: Called with the region and asked for the text to show.
            The controller supplies it, so this window need not know where
            the image data lives.
        parent: Optional parent widget.
    """

    def __init__(self, region: BaseRegion, provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.region = region
        self._provider = provider
        self.setWindowTitle(f"Statistics: {type(region).__name__}")
        self.resize(*STATISTICS_SIZE)

        layout = QVBoxLayout(self)
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        # The tables are laid out with tabs and only line up in a fixed pitch.
        self._text.setFont(QFont("monospace"))
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.refresh()

    def refresh(self) -> None:
        """Measure the region again and show the result."""
        try:
            self._text.setPlainText(self._provider(self.region))
        except AnalysisError as exc:
            self._text.setPlainText(str(exc))


class RegionPlotDialog(QDialog):
    """A plot of something measured along or inside a region.

    Args:
        region: The region plotted, kept so `refresh` can measure again.
        provider: Called with the region, returning
            `(x, y, errors_or_None)`.
        title: The window's title and the plot's.
        labels: The x and y axis labels.
        style: "line" for a profile or a cut, "bar" for a histogram.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        region: BaseRegion,
        provider,
        title: str,
        labels: tuple[str, str],
        style: str = "line",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.region = region
        self._provider = provider
        self._labels = labels
        self._style = style
        self._title = title
        self.setWindowTitle(f"{title}: {type(region).__name__}")
        self.resize(*PLOT_SIZE)

        layout = QVBoxLayout(self)
        self._figure = Figure(figsize=(6, 4), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._figure)
        layout.addWidget(self._canvas)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.refresh()

    def refresh(self) -> None:
        """Measure the region again and redraw."""
        self._figure.clear()
        axes = self._figure.add_subplot(111)
        try:
            x, y, errors = self._provider(self.region)
        except AnalysisError as exc:
            axes.text(0.5, 0.5, str(exc), ha="center", va="center", transform=axes.transAxes)
            self._canvas.draw_idle()
            return

        self._draw(axes, x, y, errors)
        axes.set_xlabel(self._labels[0])
        axes.set_ylabel(self._labels[1])
        axes.set_title(self._title)
        axes.grid(True, alpha=0.3)
        self._canvas.draw_idle()

    def _draw(self, axes, x: Sequence[float], y: Sequence[float], errors) -> None:
        """Put the data on the axes in whichever style was asked for."""
        if self._style == "bar" and len(x) > 1:
            width = float(np.diff(np.asarray(x, dtype=float)).mean())
            axes.bar(x, y, width=width, align="center")
            return
        if errors is not None and len(errors) == len(x):
            axes.errorbar(x, y, yerr=errors, fmt="o-", capsize=3)
            return
        axes.plot(x, y, "-")
