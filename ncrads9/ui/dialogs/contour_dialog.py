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
DS9's Contour Parameters dialog (`ContourDialog` in `contour.tcl`).

The levels are a text list the reader owns: Generate fills it from the
number of levels, the scale and the limits; it may then be edited by hand;
and Apply draws exactly the levels it holds. An empty list is generated
first, as DS9's `UpdateContour` does.

Author: Yogesh Wadadekar
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QColor, QKeySequence
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...analysis.contour import (
    CONTOUR_LIMIT_MODES,
    CONTOUR_SCALES,
    DEFAULT_LOG_EXPONENT,
    DEFAULT_NUM_LEVELS,
    contour_limits,
    ds9_levels,
    format_levels,
    normalize_mode,
    normalize_scale,
    parse_levels,
    parse_levels_file,
)
from ..menu_bar import REGION_COLORS
from .modeless import make_modeless

#: DS9's default smoothness (`ContourDef`).
DS9_SMOOTHNESS = 4

#: The filter DS9's Load and Save Contour Levels offer.
LEVELS_FILTER = "Contour Levels (*.lev);;All Files (*)"

#: Supplies the pixels Generate and the Limits menu measure: the analysis
#: array and, for Global scope, the whole extension (or None).
DataSource = Callable[[], tuple[Any, Any] | None]


def _number(text: str) -> float | None:
    """A typed limit, or None if it is not a number."""
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


class ContourDialog(QDialog):
    """DS9's Contour Parameters window."""

    #: Apply: the settings, with `levels` exactly as the Levels box holds.
    contours_changed = pyqtSignal(dict)
    #: Kept for older callers; the File menu's Save replaces it.
    contours_export_requested = pyqtSignal(dict)
    #: The File menu's commands the controller runs: open, save, copy,
    #: paste and polygons (Convert to Polygons).
    contours_file_requested = pyqtSignal(str)
    #: Clear: take the contours off the frame.
    contours_cleared = pyqtSignal()

    def __init__(self, parent: QWidget | None = None, data_source: DataSource | None = None) -> None:
        """Initialize the contour dialog.

        Args:
            parent: Parent widget.
            data_source: Where Generate and the Limits menu get the pixels.
        """
        super().__init__(parent)
        self.setWindowTitle("Contour Parameters")
        # A parameters window: read and adjusted while looking at the
        # image behind it, so it must not block or cover what it changes.
        make_modeless(self)
        self._data_source = data_source

        self._color = "green"
        self._width = 1
        self._dash = False
        self._scale = "linear"
        self._log_exp = DEFAULT_LOG_EXPONENT
        self._mode = "minmax"
        self._scope = "local"
        self._method = "smooth"

        self._setup_ui()

    # -- building ------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Lay the window out as DS9 does: menus, parameters, levels, buttons."""
        layout = QVBoxLayout(self)
        self.menu_bar = QMenuBar(self)
        layout.setMenuBar(self.menu_bar)
        #: Menu title -> its menu, so a test can walk one.
        self.menus: dict[str, QMenu] = {}
        #: (menu, value) -> the radio or command action, for tests.
        self.menu_actions: dict[tuple[str, str], QAction] = {}

        body = QHBoxLayout()

        param = QGroupBox("Contour")
        grid = QGridLayout(param)
        self._levels_slider, self._num_levels_spin = self._slider(0, 50, DEFAULT_NUM_LEVELS)
        grid.addWidget(QLabel("Levels"), 0, 0)
        grid.addWidget(self._levels_slider, 0, 1, 1, 3)
        grid.addWidget(self._num_levels_spin, 0, 4)
        self._smooth_slider, self._smoothness_spin = self._slider(0, 32, DS9_SMOOTHNESS)
        grid.addWidget(QLabel("Smoothness"), 1, 0)
        grid.addWidget(self._smooth_slider, 1, 1, 1, 3)
        grid.addWidget(self._smoothness_spin, 1, 4)
        grid.addWidget(QLabel("Limits"), 2, 0)
        grid.addWidget(QLabel("Low"), 2, 1)
        self._low_edit = QLineEdit()
        self._low_edit.setMaximumWidth(110)
        grid.addWidget(self._low_edit, 2, 2)
        grid.addWidget(QLabel("High"), 2, 3)
        self._high_edit = QLineEdit()
        self._high_edit.setMaximumWidth(110)
        grid.addWidget(self._high_edit, 2, 4)
        # Typing a limit is DS9's User mode in all but name.
        self._low_edit.textEdited.connect(lambda _text: self._set_mode("user", recompute=False))
        self._high_edit.textEdited.connect(lambda _text: self._set_mode("user", recompute=False))
        body.addWidget(param)

        levels = QGroupBox("Levels")
        levels_layout = QVBoxLayout(levels)
        self._levels_text = QPlainTextEdit()
        self._levels_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._levels_text.setMinimumWidth(140)
        levels_layout.addWidget(self._levels_text)
        body.addWidget(levels, 1)
        layout.addLayout(body, 1)

        buttons = QHBoxLayout()
        #: Button label -> button, so a test can press one.
        self.buttons: dict[str, QPushButton] = {}
        for label, slot in (
            ("Apply", self.apply),
            ("Generate", self.generate),
            ("Clear", self.clear),
            ("Close", self.close),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, run=slot: run())
            buttons.addWidget(button)
            self.buttons[label] = button
        layout.addLayout(buttons)

        self._build_menus()

    def _slider(self, low: int, high: int, value: int) -> tuple[QSlider, QSpinBox]:
        """DS9's `slider`: a scale with an entry beside it, kept in step."""
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(low, high)
        spin = QSpinBox()
        spin.setRange(low, high)
        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        spin.setValue(value)
        slider.setValue(value)
        return slider, spin

    def _command(self, menu: QMenu, key: str, label: str, slot, shortcut=None) -> QAction:
        action = menu.addAction(label)
        action.triggered.connect(lambda _checked=False: slot())
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        self.menu_actions[(menu.title(), key)] = action
        return action

    def _radio(self, menu: QMenu, group: QActionGroup, key: str, label: str, slot) -> QAction:
        action = menu.addAction(label)
        action.setCheckable(True)
        group.addAction(action)
        action.triggered.connect(lambda _checked=False: slot(key))
        self.menu_actions[(menu.title(), key)] = action
        return action

    def _build_menus(self) -> None:
        """File, Edit, Color, Width, Scale, Limits, Scope and Method."""
        for title in ("File", "Edit", "Color", "Width", "Scale", "Limits", "Scope", "Method"):
            self.menus[title] = self.menu_bar.addMenu(title)

        menu = self.menus["File"]
        self._command(
            menu, "open", "Open...", lambda: self._file_command("open"), QKeySequence.StandardKey.Open
        )
        self._command(
            menu, "save", "Save...", lambda: self._file_command("save"), QKeySequence.StandardKey.Save
        )
        menu.addSeparator()
        self._command(menu, "apply", "Apply", self.apply)
        self._command(menu, "generate", "Generate", self.generate)
        self._command(menu, "clear", "Clear", self.clear)
        menu.addSeparator()
        self._command(menu, "copy", "Copy Contours", lambda: self._file_command("copy"))
        self._command(menu, "paste", "Paste Contours", lambda: self._file_command("paste"))
        menu.addSeparator()
        self._command(menu, "load_levels", "Load Contour Levels...", self.load_levels)
        self._command(menu, "save_levels", "Save Contour Levels...", self.save_levels)
        menu.addSeparator()
        self._command(menu, "polygons", "Convert to Polygons", lambda: self._file_command("polygons"))
        menu.addSeparator()
        self._command(menu, "close", "Close", self.close, QKeySequence.StandardKey.Close)

        menu = self.menus["Edit"]
        self._command(menu, "cut", "Cut", lambda: self._edit("cut"), QKeySequence.StandardKey.Cut)
        self._command(menu, "copy", "Copy", lambda: self._edit("copy"), QKeySequence.StandardKey.Copy)
        self._command(menu, "paste", "Paste", lambda: self._edit("paste"), QKeySequence.StandardKey.Paste)

        menu = self.menus["Color"]
        group = QActionGroup(self)
        for name in REGION_COLORS:
            self._radio(menu, group, name, name.capitalize(), self.set_color)
        menu.addSeparator()
        self._command(menu, "other", "Other Color...", self._choose_color)

        menu = self.menus["Width"]
        group = QActionGroup(self)
        for width in (1, 2, 3, 4):
            self._radio(menu, group, str(width), str(width), lambda key: self.set_width(int(key)))
        menu.addSeparator()
        dash = menu.addAction("Dash")
        dash.setCheckable(True)
        dash.toggled.connect(self.set_dash)
        self.menu_actions[("Width", "dash")] = dash

        menu = self.menus["Scale"]
        group = QActionGroup(self)
        for value, label in CONTOUR_SCALES:
            self._radio(menu, group, value, label, self.set_scale)
        menu.addSeparator()
        self._command(menu, "log_exponent", "Log Exponent...", self._ask_log_exponent)

        menu = self.menus["Limits"]
        group = QActionGroup(self)
        for entry in CONTOUR_LIMIT_MODES:
            if entry is None:
                menu.addSeparator()
                continue
            self._radio(menu, group, entry[0], entry[1], self._set_mode)

        menu = self.menus["Scope"]
        group = QActionGroup(self)
        self._radio(menu, group, "global", "Global", self.set_scope)
        self._radio(menu, group, "local", "Local", self.set_scope)

        menu = self.menus["Method"]
        group = QActionGroup(self)
        self._radio(menu, group, "block", "Block", self.set_method)
        self._radio(menu, group, "smooth", "Smooth", self.set_method)

        self._sync_menus()

    def _sync_menus(self) -> None:
        """Tick the radio entries that match the settings."""
        for (menu, key), action in self.menu_actions.items():
            if not action.isCheckable():
                continue
            if menu == "Color":
                action.setChecked(key == self._color)
            elif menu == "Width":
                if key == "dash":
                    action.blockSignals(True)
                    action.setChecked(self._dash)
                    action.blockSignals(False)
                else:
                    action.setChecked(int(key) == self._width)
            elif menu == "Scale":
                action.setChecked(key == self._scale)
            elif menu == "Limits":
                action.setChecked(key == self._mode)
            elif menu == "Scope":
                action.setChecked(key == self._scope)
            elif menu == "Method":
                action.setChecked(key == self._method)

    # -- the parameters ------------------------------------------------------

    def set_data_source(self, source: DataSource | None) -> None:
        """Say where Generate and the Limits menu get their pixels."""
        self._data_source = source

    def _data(self) -> tuple[Any, Any]:
        if self._data_source is None:
            return None, None
        found = self._data_source()
        return found if found is not None else (None, None)

    def set_color(self, color: str) -> None:
        """DS9's Color menu."""
        self._color = str(color)
        self._sync_menus()

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Contour Color")
        if color.isValid():
            self.set_color(color.name())

    def set_width(self, width: int) -> None:
        """DS9's Width menu."""
        self._width = max(1, int(width))
        self._sync_menus()

    def set_dash(self, dash: bool) -> None:
        """The Width menu's Dash."""
        self._dash = bool(dash)
        self._sync_menus()

    def set_scale(self, scale: str) -> None:
        """DS9's Scale menu."""
        self._scale = normalize_scale(scale)
        self._sync_menus()

    def set_log_exponent(self, exponent: float) -> None:
        """The Scale menu's Log Exponent."""
        self._log_exp = float(exponent)

    def _ask_log_exponent(self) -> None:
        value, ok = QInputDialog.getDouble(self, "Scale", "Log Exponent", self._log_exp, 1.0, 1e10, 2)
        if ok:
            self.set_log_exponent(value)

    def set_limit_mode(self, mode: str) -> None:
        """DS9's Limits menu: pick a mode and fill Low and High from it."""
        self._set_mode(mode)

    def _set_mode(self, mode: str, recompute: bool = True) -> None:
        self._mode = normalize_mode(mode)
        self._sync_menus()
        if recompute:
            self._update_limits()

    def set_scope(self, scope: str) -> None:
        """DS9's Scope menu, which recomputes the limits as Limits does."""
        self._scope = "global" if str(scope).lower() == "global" else "local"
        self._sync_menus()
        self._update_limits()

    def set_method(self, method: str) -> None:
        """DS9's Method menu: Block or Smooth."""
        self._method = "block" if str(method).lower() == "block" else "smooth"
        self._sync_menus()

    def set_limits(self, low: float, high: float) -> None:
        """Put numbers in Low and High."""
        self._low_edit.setText(f"{float(low):.10g}")
        self._high_edit.setText(f"{float(high):.10g}")

    def limits(self) -> tuple[float, float] | None:
        """Low and High, or None if either is not a number."""
        low, high = _number(self._low_edit.text()), _number(self._high_edit.text())
        if low is None or high is None:
            return None
        return low, high

    def _update_limits(self) -> None:
        """DS9's `ContourModeDialog`: Low and High from the Limits mode."""
        data, whole = self._data()
        found = contour_limits(data, self._mode, self._scope, whole)
        if found is not None:
            self.set_limits(*found)

    # -- the levels ----------------------------------------------------------

    def levels_text(self) -> str:
        """What the Levels box holds."""
        return self._levels_text.toPlainText()

    def set_levels_text(self, text: str) -> None:
        """Replace what the Levels box holds."""
        self._levels_text.setPlainText(text)

    def levels(self) -> list[float]:
        """The levels in the box, as numbers."""
        return parse_levels(self.levels_text())

    def set_levels(self, levels) -> None:
        """Fill the Levels box, one level per line."""
        self.set_levels_text(format_levels(levels))

    def generate(self) -> list[float]:
        """DS9's Generate: fill the Levels box from the parameters."""
        self._levels_text.clear()
        limits = self.limits()
        if limits is None:
            self._update_limits()
            limits = self.limits()
        if limits is None:
            return []
        data, _whole = self._data()
        levels = ds9_levels(
            max(1, self._num_levels_spin.value()),
            limits[0],
            limits[1],
            self._scale,
            self._log_exp,
            data=data,
        )
        self.set_levels(levels)
        return levels

    def apply(self) -> None:
        """DS9's Apply: draw exactly the levels in the box.

        An empty box is generated first, as DS9's `UpdateContour` does.
        """
        if not self.levels():
            self.generate()
        self.contours_changed.emit(self.settings())

    def clear(self) -> None:
        """DS9's Clear: contours off, the box regenerated."""
        self.contours_cleared.emit()
        self.generate()

    def load_levels(self) -> None:
        """File > Load Contour Levels."""
        path, _filter = QFileDialog.getOpenFileName(self, "Load Contour Levels", "", LEVELS_FILTER)
        if path:
            self.load_levels_file(path)

    def load_levels_file(self, path: str) -> list[float]:
        """Read a levels file into the box, DS9's `ContourLoadLevelsNow`."""
        text = Path(path).read_text()
        if Path(path).suffix.lower() == ".lev":
            self.set_levels_text(text)
            return self.levels()
        levels = parse_levels_file(text)
        self.set_levels(levels)
        return levels

    def save_levels(self) -> None:
        """File > Save Contour Levels."""
        path, _filter = QFileDialog.getSaveFileName(self, "Save Contour Levels", "", LEVELS_FILTER)
        if path:
            self.save_levels_file(path)

    def save_levels_file(self, path: str) -> None:
        """Write the box as it stands, DS9's `ContourSaveLevelsNow`."""
        text = self.levels_text()
        Path(path).write_text(text if text.endswith("\n") else text + "\n")

    # -- commands ------------------------------------------------------------

    def _file_command(self, name: str) -> None:
        """Ask the controller for one of DS9's contour file commands."""
        self.contours_file_requested.emit(name)

    def _edit(self, what: str) -> None:
        """The Edit menu: on whichever text field has the focus."""
        widget = self.focusWidget()
        if isinstance(widget, (QLineEdit, QPlainTextEdit)):
            getattr(widget, what)()

    # -- settings ------------------------------------------------------------

    def settings(self) -> dict:
        """The settings Apply hands the controller."""
        limits = self.limits()
        return {
            "color": self._color,
            "line_width": float(self._width),
            "line_style": "Dashed" if self._dash else "Solid",
            "contour_method": self._method,
            "smoothness": max(1, self._smoothness_spin.value()),
            "num_levels": max(1, self._num_levels_spin.value()),
            "scale": self._scale,
            "log_exp": self._log_exp,
            "mode": self._mode,
            "scope": self._scope,
            "limits": limits,
            "levels": self.levels(),
        }

    def _get_settings(self) -> dict:
        """Older name for `settings`."""
        return self.settings()

    def load_settings(self, settings: dict[str, Any], levels=None) -> None:
        """Seed the dialog from the contours in force, DS9's `UpdateContourDialog`.

        Args:
            settings: The current contour settings.
            levels: The levels on screen; generated when there are none.
        """
        if "color" in settings:
            self._color = str(settings["color"])
        if "line_width" in settings:
            self._width = max(1, int(float(settings["line_width"]) or 1))
        if "line_style" in settings:
            self._dash = str(settings["line_style"]).lower() != "solid"
        if "contour_method" in settings:
            self._method = "block" if str(settings["contour_method"]).lower() == "block" else "smooth"
        if "smoothness" in settings:
            self._smoothness_spin.setValue(max(1, int(settings["smoothness"])))
        if "num_levels" in settings:
            self._num_levels_spin.setValue(max(1, int(settings["num_levels"])))
        if "scale" in settings:
            self._scale = normalize_scale(settings["scale"])
        if settings.get("log_exp"):
            self._log_exp = float(settings["log_exp"])
        if "scope" in settings:
            self._scope = "global" if str(settings["scope"]).lower() == "global" else "local"
        if "mode" in settings:
            self._mode = normalize_mode(settings["mode"])
        self._sync_menus()

        limits = settings.get("limits")
        if limits is not None and len(limits) == 2:
            self.set_limits(*limits)
        else:
            self._update_limits()

        chosen = levels if levels else settings.get("levels")
        if chosen:
            self.set_levels(chosen)
        else:
            self.generate()
