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
DS9's Scale Parameters window (`ScaleDialog`, `scale.tcl`).

A menubar -- File, Edit, Scale, Limits, Scope, Min Max, Parameters, Graph --
over a plot of the pixel distribution, the Low and High limits, and Apply
and Close. Two vertical lines on the plot, red for Low and green for High,
mark the limits in force; dragging either one sets User limits when the
mouse is let go, exactly as DS9's `ScaleMotionDialog`/`ScaleReleaseDialog`
do.

Everything but Graph acts at once, as it does in DS9, and is the main
window's own Scale-menu actions rather than copies: one QAction may sit in
any number of menus with one shared check mark, so the dialog can never
disagree with the menu. Only Apply needs the Low and High fields; it always
means "these numbers, as User limits", which is why the fields open on the
limits in force rather than on zero -- an Apply straight after opening the
window changes nothing.

Built without a main window -- as the tests and the translation survey do
-- the menus are the dialog's own actions, and choosing one emits
`scale_changed` with what was chosen.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import Any

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from numpy.typing import NDArray
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QPushButton,
    QVBoxLayout,
)

from ..menu_bar import MINMAX_METHODS, SCALE_FUNCTIONS, SCALE_LIMIT_MODES
from .modeless import make_modeless

#: DS9's `scale(bins)`.
HISTOGRAM_BINS = 512

#: More pixels than this are sampled with a stride before binning. The plot
#: is a picture of a distribution, and a 16-million-pixel image binned in
#: full on every redisplay makes dragging a limit line stutter.
MAX_HISTOGRAM_SAMPLES = 2_000_000

#: How close, in screen pixels, a press must be to a limit line to take it.
GRAB_TOLERANCE = 8

#: DS9's `ScaleXAxisDialog` margin for the Current Range view.
CURRENT_RANGE_MARGIN = 0.10

#: DS9 colours the two cut lines thus.
LOW_COLOUR = "red"
HIGH_COLOUR = "green"

#: Limit keys DS9 groups with separators between them in its Limits menu.
_LIMIT_GROUPS: tuple[tuple[str, ...], ...] = (
    ("minmax",),
    ("99.5", "99", "98", "97", "96", "95", "92.5", "90"),
    ("zscale", "zmax", "user"),
)


def pixel_distribution(
    data: NDArray[np.floating] | None,
    bins: int = HISTOGRAM_BINS,
) -> tuple[NDArray[np.float64], NDArray[np.float64], float, float] | None:
    """The histogram DS9 draws: counts over the whole data range.

    Args:
        data: The displayed array.
        bins: How many bins.

    Returns:
        (bin centres, counts, data minimum, data maximum), or None when
        there is nothing finite to bin.
    """
    if data is None:
        return None
    flat = np.asarray(data).ravel()
    if flat.size > MAX_HISTOGRAM_SAMPLES:
        flat = flat[:: int(np.ceil(flat.size / MAX_HISTOGRAM_SAMPLES))]
    flat = flat[np.isfinite(flat)]
    if flat.size == 0:
        return None
    low, high = float(flat.min()), float(flat.max())
    if high <= low:
        high = low + 1.0
    counts, edges = np.histogram(flat, bins=bins, range=(low, high))
    centres = 0.5 * (edges[:-1] + edges[1:])
    return centres, counts.astype(np.float64), low, high


class ScaleDialog(QDialog):
    """The Scale Parameters window.

    Args:
        parent: The main window, whose Scale menu and scale controller the
            dialog works through. Without one it stands alone and reports
            every choice through `scale_changed`.
    """

    #: Apply, or the release of a dragged limit line, emits
    #: `{"limit_mode": "user", "low": ..., "high": ...}`. A standalone
    #: dialog also emits one key for each menu choice -- `scale_function`,
    #: `limit_mode`, `scope`, `minmax_method` or `use_datasec`.
    scale_changed = pyqtSignal(dict)

    def __init__(self, parent: Any | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Scale Parameters")
        # A parameters window: the point of it is to watch the image change
        # behind it, so it must neither block nor cover the main window.
        make_modeless(self)
        self.setMinimumWidth(520)
        self._window = parent if hasattr(parent, "scale") and hasattr(parent, "menu_bar") else None

        #: The limits shown, DS9's `dscale(min)`/`dscale(max)`.
        self.low: float | None = None
        self.high: float | None = None
        #: DS9's `scale(yaxis)` and `scale(xaxis)`, its defaults.
        self.y_axis = "log"
        self.x_axis = "full"

        self._distribution: tuple[NDArray[np.float64], NDArray[np.float64], float, float] | None = None
        self._data_key: tuple | None = None
        self._dragging: str | None = None

        self._setup_ui()
        self.sync()

    # -- construction --------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setMenuBar(self._build_menus())

        self.figure = Figure(figsize=(5.0, 2.0), tight_layout=True)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(200)
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        layout.addWidget(self.canvas, 1)

        row = QHBoxLayout()
        row.addWidget(QLabel("Limits"))
        row.addWidget(QLabel("Low"))
        self.low_entry = QLineEdit()
        self.low_entry.setMinimumWidth(110)
        row.addWidget(self.low_entry)
        row.addWidget(QLabel("High"))
        self.high_entry = QLineEdit()
        self.high_entry.setMinimumWidth(110)
        row.addWidget(self.high_entry)
        row.addStretch()
        layout.addLayout(row)

        buttons = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def _build_menus(self) -> QMenuBar:
        bar = QMenuBar(self)
        main = getattr(self._window, "menu_bar", None)

        def command(menu: QMenu, label: str, slot, shortcut=None) -> QAction:
            action = QAction(label, self)
            if shortcut is not None:
                action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda _checked=False: slot())
            menu.addAction(action)
            return action

        file_menu = bar.addMenu("&File")
        self.action_apply = command(file_menu, "Apply", self.apply)
        file_menu.addSeparator()
        self.action_close = command(file_menu, "Close", self.close, QKeySequence.StandardKey.Close)

        # DS9's `EditMenu`: cut, copy and paste in whichever field has focus.
        edit_menu = bar.addMenu("&Edit")
        command(edit_menu, "Cut", lambda: self._edit("cut"), QKeySequence.StandardKey.Cut)
        command(edit_menu, "Copy", lambda: self._edit("copy"), QKeySequence.StandardKey.Copy)
        command(edit_menu, "Paste", lambda: self._edit("paste"), QKeySequence.StandardKey.Paste)

        if main is not None:
            self.function_actions = dict(main.scale_function_actions)
            self.limit_actions = dict(main.scale_limit_actions)
            self.scope_actions = dict(main.scale_scope_actions)
            self.method_actions = dict(main.minmax_method_actions)
            self.action_use_datasec = main.action_use_datasec
            log_exponent: QAction | QMenu = main.log_exponent_menu
            other_limits: QAction = main.action_scale_user_limits
            sample_parameters: QAction = main.action_sample_parameters
            zscale_parameters: QAction = main.action_zscale_parameters
        else:
            self.function_actions = self._local_group(SCALE_FUNCTIONS, "scale_function", "linear")
            self.limit_actions = self._local_group(SCALE_LIMIT_MODES, "limit_mode", "minmax")
            self.scope_actions = self._local_group(
                (("global", "&Global"), ("local", "&Local")), "scope", "local"
            )
            self.method_actions = self._local_group(MINMAX_METHODS, "minmax_method", "scan")
            self.action_use_datasec = QAction("Use &DATASEC", self)
            self.action_use_datasec.setCheckable(True)
            self.action_use_datasec.setChecked(True)
            self.action_use_datasec.toggled.connect(
                lambda on: self.scale_changed.emit({"use_datasec": bool(on)})
            )
            log_exponent = QAction("Log Exponent...", self)
            other_limits = QAction("Other...", self)
            sample_parameters = QAction("Sample Parameters...", self)
            zscale_parameters = QAction("ZScale...", self)

        self.scale_menu = bar.addMenu("&Scale")
        for action in self.function_actions.values():
            self.scale_menu.addAction(action)
        self.scale_menu.addSeparator()
        if isinstance(log_exponent, QMenu):
            self.scale_menu.addMenu(log_exponent)
        else:
            self.scale_menu.addAction(log_exponent)

        self.limits_menu = bar.addMenu("&Limits")
        for group in _LIMIT_GROUPS:
            for key in group:
                if key in self.limit_actions:
                    self.limits_menu.addAction(self.limit_actions[key])
            self.limits_menu.addSeparator()
        self.limits_menu.addAction(other_limits)

        self.scope_menu = bar.addMenu("S&cope")
        for key in ("global", "local"):
            self.scope_menu.addAction(self.scope_actions[key])

        self.minmax_menu = bar.addMenu("&Min Max")
        for action in self.method_actions.values():
            self.minmax_menu.addAction(action)
        self.minmax_menu.addSeparator()
        self.minmax_menu.addAction(sample_parameters)

        self.parameters_menu = bar.addMenu("&Parameters")
        self.parameters_menu.addAction(self.action_use_datasec)
        self.parameters_menu.addSeparator()
        self.parameters_menu.addAction(zscale_parameters)

        # Graph is the dialog's own: how the plot is drawn, not the image.
        self.graph_menu = bar.addMenu("&Graph")
        self.y_axis_actions = self._graph_group(
            (("linear", "Linear"), ("log", "Log")), self.set_y_axis, "log"
        )
        self.graph_menu.addSeparator()
        self.x_axis_actions = self._graph_group(
            (("full", "Full Range"), ("current", "Current Range")), self.set_x_axis, "full"
        )
        return bar

    def _local_group(self, entries, key: str, checked: str) -> dict[str, QAction]:
        """Radio actions for a standalone dialog, reported via `scale_changed`."""
        group = QActionGroup(self)
        group.setExclusive(True)
        actions: dict[str, QAction] = {}
        for name, label in entries:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(name == checked)
            group.addAction(action)
            action.triggered.connect(lambda _checked=False, k=key, n=name: self.scale_changed.emit({k: n}))
            actions[name] = action
        return actions

    def _graph_group(self, entries, slot, checked: str) -> dict[str, QAction]:
        group = QActionGroup(self)
        group.setExclusive(True)
        actions: dict[str, QAction] = {}
        for name, label in entries:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(name == checked)
            group.addAction(action)
            action.triggered.connect(lambda _checked=False, n=name: slot(n))
            self.graph_menu.addAction(action)
            actions[name] = action
        return actions

    def _edit(self, operation: str) -> None:
        widget = QApplication.focusWidget()
        if isinstance(widget, QLineEdit) and self.isAncestorOf(widget):
            getattr(widget, operation)()

    # -- state ---------------------------------------------------------------

    def sync(self) -> None:
        """Show the current frame's data and limits (DS9's `UpdateScaleDialog`).

        Called when the window opens and whenever the image is redisplayed
        while it is up, so a new frame, a new limit mode or a new file is
        reflected without reopening it.
        """
        window = self._window
        if window is None:
            self._redraw()
            return
        data = getattr(window, "image_data", None)
        if data is None:
            self.set_state(None, None, None)
            return
        low, high = window.scale.current_limits()
        self.set_state(data, low, high)

    def set_state(
        self,
        data: NDArray[np.floating] | None,
        low: float | None,
        high: float | None,
    ) -> None:
        """Show one array's distribution and a pair of limits.

        The histogram is only rebinned when the array itself changes, since
        this runs on every redisplay and a limit change leaves it alone.
        """
        key = None if data is None else (id(data), data.shape, data.dtype.str)
        if key != self._data_key:
            self._data_key = key
            self._distribution = pixel_distribution(data)
        if self._dragging is None:
            self.low = None if low is None else float(low)
            self.high = None if high is None else float(high)
            self._show_entries()
        self._redraw()

    def _show_entries(self) -> None:
        self.low_entry.setText("" if self.low is None else f"{self.low:.6g}")
        self.high_entry.setText("" if self.high is None else f"{self.high:.6g}")

    def entered_limits(self) -> tuple[float, float] | None:
        """The Low and High fields as numbers, or None if either is not one."""
        try:
            low = float(self.low_entry.text())
            high = float(self.high_entry.text())
        except ValueError:
            return None
        if not (np.isfinite(low) and np.isfinite(high)):
            return None
        return low, high

    # -- the plot ------------------------------------------------------------

    def _redraw(self) -> None:
        axes = self.axes
        axes.clear()
        axes.set_title("Pixel Distribution", fontsize=9)
        axes.tick_params(labelsize=7)
        self._low_line = self._high_line = None
        if self._distribution is None:
            axes.set_xticks([])
            axes.set_yticks([])
            self.canvas.draw_idle()
            return

        centres, counts, _dmin, _dmax = self._distribution
        axes.fill_between(centres, counts, step="mid", color="0.25", linewidth=0)
        axes.step(centres, counts, where="mid", color="0.25", linewidth=0.8)
        if self.y_axis == "log":
            axes.set_yscale("log")
            axes.set_ylim(bottom=1, top=max(float(counts.max()), 1.0) * 1.5)
        else:
            axes.set_ylim(bottom=0, top=max(float(counts.max()), 1.0) * 1.05)
        axes.grid(True, axis="y", linewidth=0.3)
        if self.low is not None and self.high is not None:
            self._low_line = axes.axvline(self.low, color=LOW_COLOUR, linewidth=1.5)
            self._high_line = axes.axvline(self.high, color=HIGH_COLOUR, linewidth=1.5)
        axes.set_xlim(*self.x_range())
        self.canvas.draw_idle()

    def x_range(self) -> tuple[float, float]:
        """The plot's x extent (DS9's `ScaleXAxisDialog`).

        Full Range spans the data with one bin's margin; Current Range spans
        the limits with a tenth of their width either side.
        """
        if self._distribution is None:
            return 0.0, 1.0
        centres, _counts, dmin, dmax = self._distribution
        if self.x_axis == "current" and self.low is not None and self.high is not None:
            diff = self.high - self.low
            if abs(diff) > 0:
                return self.low - diff * CURRENT_RANGE_MARGIN, self.high + diff * CURRENT_RANGE_MARGIN
        diff = (dmax - dmin) / max(len(centres), 1)
        return dmin - diff, dmax + diff

    def set_y_axis(self, mode: str) -> None:
        """Graph -> Linear or Log: how the counts are drawn."""
        self.y_axis = "log" if mode == "log" else "linear"
        self.y_axis_actions[self.y_axis].setChecked(True)
        self._redraw()

    def set_x_axis(self, mode: str) -> None:
        """Graph -> Full Range or Current Range: what the plot spans."""
        self.x_axis = "current" if mode == "current" else "full"
        self.x_axis_actions[self.x_axis].setChecked(True)
        self._redraw()

    # -- dragging the limit lines -------------------------------------------

    def _on_press(self, event) -> None:
        if event.button != 1 or event.inaxes is not self.axes or self.low is None or self.high is None:
            return
        to_screen = self.axes.transData.transform
        distances = {
            "low": abs(to_screen((self.low, 1.0))[0] - event.x),
            "high": abs(to_screen((self.high, 1.0))[0] - event.x),
        }
        which = min(distances, key=distances.get)
        if distances[which] <= GRAB_TOLERANCE:
            self._dragging = which

    def _on_motion(self, event) -> None:
        if self._dragging is not None and event.xdata is not None:
            self.drag_limit(self._dragging, float(event.xdata))

    def _on_release(self, _event) -> None:
        if self._dragging is not None:
            self._dragging = None
            self.release_limit()

    def drag_limit(self, which: str, value: float) -> None:
        """Move one limit line (DS9's `ScaleMotionDialog`).

        A line is not allowed past the other one: it stops where the other
        line is, so Low can never end up above High.

        Args:
            which: "low" or "high".
            value: Where the line has been dragged to, in data units.
        """
        if self.low is None or self.high is None:
            return
        if which == "low":
            self.low = min(float(value), self.high)
        else:
            self.high = max(float(value), self.low)
        self._show_entries()
        if self._low_line is not None and self._high_line is not None:
            self._low_line.set_xdata([self.low, self.low])
            self._high_line.set_xdata([self.high, self.high])
            self.canvas.draw_idle()

    def release_limit(self) -> None:
        """Let go of a dragged line (DS9's `ScaleReleaseDialog`).

        The limits under the lines become User limits at once, as in DS9;
        no Apply is needed.
        """
        if self.low is None or self.high is None:
            return
        self.scale_changed.emit({"limit_mode": "user", "low": self.low, "high": self.high})
        self._redraw()

    # -- buttons -------------------------------------------------------------

    def apply(self) -> None:
        """Apply the Low and High fields as User limits (DS9's `ScaleApplyDialog`)."""
        limits = self.entered_limits()
        if limits is None:
            self._show_entries()
            return
        self.low, self.high = limits
        self.scale_changed.emit({"limit_mode": "user", "low": self.low, "high": self.high})
        self._redraw()


__all__ = ["HISTOGRAM_BINS", "ScaleDialog", "pixel_distribution"]
