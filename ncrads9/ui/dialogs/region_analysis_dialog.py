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

Both can save what they show, as DS9's do: the Statistics window's Save
writes the table, and a plot's File -> Save Data... writes its columns, one
point per line. Plot 2D and Plot 3D carry DS9's Method menu -- Average, Sum
or Median -- which re-measures with the method chosen.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtGui import QAction, QActionGroup, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMenuBar,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...regions.base_region import BaseRegion
from ...regions.region_analysis import AnalysisError
from .. import plot_theme

#: How big the statistics window opens, in pixels. DS9's is 80 columns.
STATISTICS_SIZE = (760, 460)

#: How big a plot window opens.
PLOT_SIZE = (640, 460)

#: The file choosers' filters.
TEXT_FILTER = "Text Files (*.txt);;All Files (*)"
DATA_FILTER = "Data Files (*.dat *.txt);;All Files (*)"


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

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(lambda: self.save())
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.refresh()

    def refresh(self) -> None:
        """Measure the region again and show the result."""
        try:
            self._text.setPlainText(self._provider(self.region))
        except AnalysisError as exc:
            self._text.setPlainText(str(exc))

    def text(self) -> str:
        """What the window shows."""
        return self._text.toPlainText()

    def save(self, path: str | None = None) -> bool:
        """Write the statistics to a text file, DS9's Statistics Save.

        Args:
            path: Where to write. Asked for when not given.

        Returns:
            Whether a file was written.
        """
        if path is None:
            path, _filter = QFileDialog.getSaveFileName(self, "Save Statistics", "", TEXT_FILTER)
            if not path:
                return False
        Path(path).write_text(self.text() + "\n", encoding="utf-8")
        return True


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
        methods: DS9's Method menu, when the plot has one. The provider is
            then called with the region and the chosen method.
        method: Which method to start with.
    """

    def __init__(
        self,
        region: BaseRegion,
        provider,
        title: str,
        labels: tuple[str, str],
        style: str = "line",
        parent: QWidget | None = None,
        methods: Sequence[str] = (),
        method: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.region = region
        self._provider = provider
        self._labels = labels
        self._style = style
        self._title = title
        self._methods = tuple(methods)
        self.method = method or (self._methods[0] if self._methods else None)
        #: The last thing measured, as (x, y, errors), for Save Data.
        self.data: tuple | None = None
        self.setWindowTitle(f"{title}: {type(region).__name__}")
        self.resize(*PLOT_SIZE)

        layout = QVBoxLayout(self)
        layout.setMenuBar(self._menu_bar())
        self._figure = Figure(figsize=(6, 4), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._figure)
        layout.addWidget(self._canvas)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.refresh()

    def _menu_bar(self) -> QMenuBar:
        """File -> Save Data..., and the Method menu where DS9 has one."""
        bar = QMenuBar(self)
        file_menu = bar.addMenu("&File")
        self.action_save_data = QAction("Save &Data...", self)
        self.action_save_data.triggered.connect(lambda _checked=False: self.save_data())
        file_menu.addAction(self.action_save_data)
        file_menu.addSeparator()
        close = QAction("&Close", self)
        close.triggered.connect(lambda _checked=False: self.reject())
        file_menu.addAction(close)

        #: Method name -> its radio action.
        self.method_actions: dict[str, QAction] = {}
        if self._methods:
            menu = bar.addMenu("&Method")
            group = QActionGroup(self)
            for name in self._methods:
                action = QAction(name.capitalize(), self, checkable=True)
                action.setChecked(name == self.method)
                action.triggered.connect(lambda _checked=False, key=name: self.set_method(key))
                group.addAction(action)
                menu.addAction(action)
                self.method_actions[name] = action
        return bar

    def set_method(self, method: str) -> None:
        """Choose Average, Sum or Median, and measure again."""
        self.method = method
        action = self.method_actions.get(method)
        if action is not None:
            action.setChecked(True)
        self.refresh()

    def _measure(self):
        if self._methods:
            return self._provider(self.region, self.method)
        return self._provider(self.region)

    def save_data(self, path: str | None = None) -> bool:
        """Write the plotted points to a text file, DS9's Save Data.

        One point per line: x, y and, where the plot has them, the error.

        Returns:
            Whether a file was written.
        """
        if self.data is None:
            return False
        if path is None:
            path, _filter = QFileDialog.getSaveFileName(self, "Save Data", "", DATA_FILTER)
            if not path:
                return False
        x, y, errors = self.data
        columns = [x, y] if errors is None or len(errors) != len(x) else [x, y, errors]
        lines = [" ".join(f"{float(value):.10g}" for value in row) for row in zip(*columns, strict=False)]
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    def refresh(self) -> None:
        """Measure the region again and redraw."""
        self._figure.clear()
        axes = self._figure.add_subplot(111)
        try:
            x, y, errors = self._measure()
        except AnalysisError as exc:
            self.data = None
            axes.text(0.5, 0.5, str(exc), ha="center", va="center", transform=axes.transAxes)
            plot_theme.style_figure(self._figure, self)
            self._canvas.draw_idle()
            return

        self.data = (list(x), list(y), None if errors is None else list(errors))
        self._draw(axes, x, y, errors)
        axes.set_xlabel(self._labels[0])
        ylabel = self._labels[1]
        if self.method:
            ylabel = f"{ylabel} ({self.method.capitalize()})"
        axes.set_ylabel(ylabel)
        axes.set_title(self._title)
        axes.grid(True, alpha=0.3)
        plot_theme.style_figure(self._figure, self)
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
