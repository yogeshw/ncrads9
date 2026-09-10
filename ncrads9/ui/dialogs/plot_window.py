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
DS9's Plot Tool window.

The menus follow DS9's (`ds9/library/plotdialog.tcl:51`): File for loading
and saving data, exporting, printing and DS9's Backup/Restore of the plot
itself; Edit for the pointer mode; Graph for the axes and the legend; Data
for the appearance of whichever dataset is current.

Zooming is a drag with the Zoom pointer, and each drag pushes the view it
left onto a stack, so zooming out retraces the way in one step at a time --
which is what DS9 gets from BLT's zoom stack and what makes exploring a
noisy profile possible at all.

The state lives in `analysis/plot/`, not here, so a plot can be built and
saved without a window.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FormatStrFormatter, ScalarFormatter
from matplotlib.widgets import RectangleSelector
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLineEdit,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...analysis.plot import (
    Axis,
    AxisFormat,
    DataFormat,
    Dataset,
    LegendPosition,
    PlotDataError,
    PlotState,
    PlotStyle,
    ZoomStack,
)
from ...analysis.plot.dataset import COLORS, SHAPES, SIZES, WIDTHS

#: How big a plot window opens, in pixels.
WINDOW_SIZE = (720, 520)

#: The file filters the File menu offers.
DATA_FILTER = "Data Files (*.dat *.txt *.csv);;All Files (*)"
PLOT_FILTER = "Plot Files (*.plot *.json);;All Files (*)"
IMAGE_FILTER = "PNG (*.png);;PDF (*.pdf);;SVG (*.svg);;EPS (*.eps)"

#: Bar plots need a width; without one every bar is a hairline.
BAR_WIDTH_FRACTION = 0.8


class PlotWindow(QDialog):
    """A plot window with DS9's menus.

    Args:
        state: The plot to show. A new empty one when not given.
        parent: Optional parent widget.
    """

    def __init__(self, state: PlotState | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state or PlotState()
        self.zoom_stack = ZoomStack()
        self.current_dataset = 0
        self._selector: RectangleSelector | None = None

        self.setWindowTitle(self.state.title or "Plot Tool")
        self.resize(*WINDOW_SIZE)

        layout = QVBoxLayout(self)
        layout.setMenuBar(self._menus())

        self.figure = Figure(figsize=(7, 5), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.draw()

    # -- menus ---------------------------------------------------------------

    def _menus(self) -> QMenuBar:
        """DS9's four plot menus."""
        bar = QMenuBar(self)
        self.actions_by_name: dict[str, QAction] = {}

        file_menu = bar.addMenu("&File")
        self._add(file_menu, "load_data", "&Load Data...", self.load_data)
        self._add(file_menu, "save_data", "&Save Data...", self.save_data)
        self._add(file_menu, "list_data", "L&ist Data", self.list_data)
        file_menu.addSeparator()
        self._add(file_menu, "export", "&Export...", self.export_image)
        self._add(file_menu, "statistics", "Statis&tics", self.show_statistics)
        file_menu.addSeparator()
        self._add(file_menu, "backup", "&Backup...", self.backup)
        self._add(file_menu, "restore", "&Restore...", self.restore)
        file_menu.addSeparator()
        self._add(file_menu, "print", "&Print...", self.print_plot)
        file_menu.addSeparator()
        self._add(file_menu, "close", "&Close", self.reject)

        edit_menu = bar.addMenu("&Edit")
        pointer_group = QActionGroup(self)
        for name, label in (("pointer", "&Pointer"), ("zoom", "&Zoom")):
            action = self._add(edit_menu, f"mode_{name}", label, None, checkable=True)
            pointer_group.addAction(action)
            action.triggered.connect(lambda _c=False, key=name: self.set_pointer_mode(key))
        self.actions_by_name["mode_pointer"].setChecked(True)
        self.pointer_mode = "pointer"

        graph_menu = bar.addMenu("&Graph")
        style_group = QActionGroup(self)
        for style in PlotStyle:
            action = self._add(graph_menu, f"style_{style.value}", style.value.title(), None, checkable=True)
            style_group.addAction(action)
            action.setChecked(style is self.state.style)
            action.triggered.connect(lambda _c=False, key=style: self.set_style(key))
        graph_menu.addSeparator()

        for axis_name, axis_label in (("x", "&X Axis"), ("y", "&Y Axis")):
            axis_menu = graph_menu.addMenu(axis_label)
            for flag, flag_label in (("log", "&Log"), ("flip", "&Flip"), ("grid", "&Grid")):
                action = self._add(axis_menu, f"{axis_name}_{flag}", flag_label, None, checkable=True)
                action.setChecked(getattr(self._axis(axis_name), flag))
                action.triggered.connect(lambda state, a=axis_name, f=flag: self.set_axis_flag(a, f, state))
            axis_menu.addSeparator()
            format_group = QActionGroup(self)
            for choice in AxisFormat:
                action = self._add(
                    axis_menu,
                    f"{axis_name}_format_{choice.value}",
                    choice.value.title(),
                    None,
                    checkable=True,
                )
                format_group.addAction(action)
                action.setChecked(choice is self._axis(axis_name).number_format)
                action.triggered.connect(lambda _c=False, a=axis_name, f=choice: self.set_axis_format(a, f))

        graph_menu.addSeparator()
        self._add(graph_menu, "range", "Axes &Range...", self.edit_range)
        self._add(graph_menu, "titles", "&Titles...", self.edit_titles)
        graph_menu.addSeparator()
        self._add(graph_menu, "zoom_out", "Zoom &Out", self.zoom_out)
        self._add(graph_menu, "zoom_reset", "Zoom &Fit", self.zoom_reset)

        legend_menu = graph_menu.addMenu("&Legend")
        show = self._add(legend_menu, "legend_show", "&Show", None, checkable=True)
        show.setChecked(self.state.show_legend)
        show.triggered.connect(self.set_legend_shown)
        legend_menu.addSeparator()
        position_group = QActionGroup(self)
        for position in LegendPosition:
            action = self._add(
                legend_menu,
                f"legend_{position.value}",
                position.value.replace("plotarea", "plot area").title(),
                None,
                checkable=True,
            )
            position_group.addAction(action)
            action.setChecked(position is self.state.legend_position)
            action.triggered.connect(lambda _c=False, key=position: self.set_legend_position(key))

        self.data_menu = bar.addMenu("&Data")
        self._build_data_menu()
        return bar

    def _add(
        self,
        menu,
        name: str,
        label: str,
        handler,
        checkable: bool = False,
    ) -> QAction:
        """Add one action, remembering it by name so a test can reach it."""
        action = QAction(label, self)
        action.setCheckable(checkable)
        if handler is not None:
            action.triggered.connect(lambda _checked=False: handler())
        menu.addAction(action)
        self.actions_by_name[name] = action
        return action

    def _build_data_menu(self) -> None:
        """The Data menu, which acts on whichever dataset is current."""
        self.data_menu.clear()
        if not self.state.datasets:
            empty = QAction("(no data)", self)
            empty.setEnabled(False)
            self.data_menu.addAction(empty)
            return

        select = self.data_menu.addMenu("&Select Dataset")
        group = QActionGroup(self)
        for index, dataset in enumerate(self.state.datasets):
            action = QAction(dataset.name, self)
            action.setCheckable(True)
            action.setChecked(index == self.current_dataset)
            group.addAction(action)
            action.triggered.connect(lambda _c=False, key=index: self.select_dataset(key))
            select.addAction(action)

        self.data_menu.addSeparator()
        show = QAction("&Show", self)
        show.setCheckable(True)
        show.setChecked(self._dataset().show)
        show.triggered.connect(self.set_dataset_shown)
        self.data_menu.addAction(show)
        self.actions_by_name["data_show"] = show

        for label, values, attribute in (
            ("&Color", COLORS, "color"),
            ("&Width", WIDTHS, "width"),
            ("Sha&pe", tuple(SHAPES), "shape"),
            ("Si&ze", SIZES, "size"),
        ):
            submenu = self.data_menu.addMenu(label)
            group = QActionGroup(self)
            for value in values:
                action = QAction(str(value), self)
                action.setCheckable(True)
                action.setChecked(getattr(self._dataset(), attribute) == value)
                group.addAction(action)
                action.triggered.connect(
                    lambda _c=False, a=attribute, v=value: self.set_dataset_property(a, v)
                )
                submenu.addAction(action)

        self.data_menu.addSeparator()
        self.actions_by_name["data_rename"] = self._data_action("&Rename...", self.rename_dataset)
        self.actions_by_name["data_duplicate"] = self._data_action(
            "&Duplicate Dataset", self.duplicate_dataset
        )
        self.actions_by_name["data_delete"] = self._data_action("De&lete Dataset", self.delete_dataset)

    def _data_action(self, label: str, handler) -> QAction:
        """One plain command on the Data menu."""
        action = QAction(label, self)
        action.triggered.connect(lambda _checked=False: handler())
        self.data_menu.addAction(action)
        return action

    # -- state -----------------------------------------------------------------

    def _axis(self, name: str) -> Axis:
        """The named axis."""
        return self.state.x_axis if name == "x" else self.state.y_axis

    def _dataset(self) -> Dataset:
        """The current dataset.

        Falls back to the first: the current index can outlive a deletion,
        and a Data menu acting on nothing would be a crash.
        """
        if not self.state.datasets:
            raise IndexError("no datasets")
        self.current_dataset = min(self.current_dataset, len(self.state.datasets) - 1)
        return self.state.datasets[self.current_dataset]

    def add_dataset(self, dataset: Dataset) -> Dataset:
        """Put another curve on the plot and redraw."""
        added = self.state.add(dataset)
        self.zoom_stack.reset()
        self._build_data_menu()
        self.draw()
        return added

    def select_dataset(self, index: int) -> None:
        """Make one dataset current, so the Data menu acts on it."""
        self.current_dataset = index
        self._build_data_menu()

    def set_style(self, style: PlotStyle) -> None:
        """Line, bar or scatter."""
        self.state.style = style
        self.draw()

    def set_axis_flag(self, axis: str, flag: str, value: bool) -> None:
        """Set Log, Flip or Grid on one axis."""
        setattr(self._axis(axis), flag, bool(value))
        self.draw()

    def set_axis_format(self, axis: str, choice: AxisFormat) -> None:
        """Set how one axis's numbers are written."""
        self._axis(axis).number_format = choice
        self.draw()

    def set_legend_shown(self, shown: bool) -> None:
        """Show or hide the key."""
        self.state.show_legend = bool(shown)
        self.draw()

    def set_legend_position(self, position: LegendPosition) -> None:
        """Move the key."""
        self.state.legend_position = position
        self.draw()

    def set_dataset_shown(self, shown: bool) -> None:
        """Show or hide the current dataset."""
        self._dataset().show = bool(shown)
        self.draw()

    def set_dataset_property(self, attribute: str, value) -> None:
        """Set the current dataset's colour, width, shape or size."""
        setattr(self._dataset(), attribute, value)
        self.draw()

    def rename_dataset(self) -> None:
        """Rename the current dataset, which is what the legend shows."""
        dataset = self._dataset()
        name, accepted = QInputDialog.getText(self, "Rename", "Name:", text=dataset.name)
        if accepted and name.strip():
            dataset.name = name.strip()
            self._build_data_menu()
            self.draw()

    def duplicate_dataset(self) -> None:
        """Copy the current dataset."""
        self.state.duplicate(self.current_dataset)
        self._build_data_menu()
        self.draw()

    def delete_dataset(self) -> None:
        """Delete the current dataset."""
        self.state.remove(self.current_dataset)
        self.current_dataset = max(0, self.current_dataset - 1)
        self._build_data_menu()
        self.draw()

    # -- zooming ----------------------------------------------------------------

    def set_pointer_mode(self, mode: str) -> None:
        """Switch between the pointer and the zoom rubber band."""
        self.pointer_mode = mode
        self._install_selector()

    def _install_selector(self) -> None:
        """Attach or detach the rubber band, per the pointer mode."""
        if self._selector is not None:
            self._selector.set_active(False)
            self._selector = None
        if self.pointer_mode != "zoom" or not self.figure.axes:
            return
        self._selector = RectangleSelector(
            self.figure.axes[0],
            self._on_zoom_box,
            useblit=False,
            button=[1],
            interactive=False,
        )

    def _on_zoom_box(self, press, release) -> None:
        """Zoom to a dragged rectangle, remembering the view being left."""
        if press is None or release is None:
            return
        self.zoom_to(press.xdata, release.xdata, press.ydata, release.ydata)

    def zoom_to(self, x0, x1, y0, y1) -> None:
        """Zoom to a rectangle, pushing the current view onto the stack."""
        if None in (x0, x1, y0, y1) or x0 == x1 or y0 == y1:
            return
        self.zoom_stack.push(
            (
                self.state.x_axis.minimum,
                self.state.x_axis.maximum,
                self.state.y_axis.minimum,
                self.state.y_axis.maximum,
            )
        )
        self.state.x_axis.set_range(x0, x1)
        self.state.y_axis.set_range(y0, y1)
        self.draw()

    def zoom_out(self) -> None:
        """Go back one step, to the view the last zoom left."""
        view = self.zoom_stack.pop()
        if view is None:
            self.zoom_reset()
            return
        x0, x1, y0, y1 = view
        self.state.x_axis.set_range(x0, x1)
        self.state.y_axis.set_range(y0, y1)
        self.draw()

    def zoom_reset(self) -> None:
        """Fit the data again, and forget the way in."""
        self.zoom_stack.reset()
        self.state.x_axis.clear_range()
        self.state.y_axis.clear_range()
        self.draw()

    # -- the File menu ------------------------------------------------------------

    def load_data(self) -> None:
        """Read a column file as another dataset."""
        path, _filter = QFileDialog.getOpenFileName(self, "Load Data", "", DATA_FILTER)
        if not path:
            return
        formats = [choice.value for choice in DataFormat]
        chosen, accepted = QInputDialog.getItem(self, "Data Format", "Columns:", formats, 0, False)
        if not accepted:
            return
        try:
            text = Path(path).read_text()
            dataset = self.state.load_data(text, chosen, name=Path(path).stem)
        except (OSError, PlotDataError) as exc:
            QMessageBox.warning(self, "Load Data", str(exc))
            return
        self.current_dataset = self.state.datasets.index(dataset)
        self.zoom_stack.reset()
        self._build_data_menu()
        self.draw()

    def save_data(self) -> None:
        """Write the current dataset back out as columns."""
        if not self.state.datasets:
            return
        path, _filter = QFileDialog.getSaveFileName(self, "Save Data", "", DATA_FILTER)
        if not path:
            return
        try:
            Path(path).write_text(self._dataset().to_text() + "\n")
        except OSError as exc:
            QMessageBox.warning(self, "Save Data", str(exc))

    def list_data(self) -> None:
        """Show every dataset as text, DS9's List Data."""
        _show_text(self, "List Data", self.state.list_data() or "(no data)")

    def show_statistics(self) -> None:
        """Show the usual summary of each dataset."""
        import statistics as stats

        lines = []
        for dataset in self.state.datasets:
            if not len(dataset):
                continue
            lines.append(f"{dataset.name}: {len(dataset)} points")
            for label, values in (("x", dataset.x), ("y", dataset.y)):
                spread = stats.pstdev(values) if len(values) > 1 else 0.0
                lines.append(
                    f"  {label}: min {min(values):g} max {max(values):g} "
                    f"mean {stats.fmean(values):g} median {stats.median(values):g} "
                    f"stddev {spread:g}"
                )
        _show_text(self, "Statistics", "\n".join(lines) or "(no data)")

    def export_image(self) -> None:
        """Save the plot as a picture."""
        path, _filter = QFileDialog.getSaveFileName(self, "Export Plot", "", IMAGE_FILTER)
        if not path:
            return
        try:
            self.figure.savefig(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Export Plot", str(exc))

    def backup(self) -> None:
        """Save the plot itself, DS9's Backup."""
        path, _filter = QFileDialog.getSaveFileName(self, "Backup Plot", "", PLOT_FILTER)
        if not path:
            return
        try:
            self.state.save(path)
        except OSError as exc:
            QMessageBox.warning(self, "Backup Plot", str(exc))

    def restore(self) -> None:
        """Read a saved plot back, DS9's Restore."""
        path, _filter = QFileDialog.getOpenFileName(self, "Restore Plot", "", PLOT_FILTER)
        if not path:
            return
        try:
            self.state = PlotState.load(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Restore Plot", str(exc))
            return
        self.current_dataset = 0
        self.zoom_stack.reset()
        self._build_data_menu()
        self.draw()

    def print_plot(self) -> None:
        """Print the plot."""
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if not dialog.exec():
            return
        self.render_to_printer(printer)

    def render_to_printer(self, printer: QPrinter) -> None:
        """Paint the canvas onto a printer, at the printer's resolution."""
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QPainter

        painter = QPainter(printer)
        try:
            page = printer.pageRect(QPrinter.Unit.DevicePixel)
            picture = self.canvas.grab()
            target = QRectF(picture.rect())
            target.moveCenter(page.center())
            painter.drawPixmap(target.topLeft(), picture)
        finally:
            painter.end()

    # -- dialogs -----------------------------------------------------------------

    def edit_range(self) -> None:
        """DS9's Axes Range dialog: both axes, or automatic."""
        dialog = AxisRangeDialog(self.state.x_axis, self.state.y_axis, self)
        if dialog.exec():
            dialog.apply()
            self.zoom_stack.reset()
            self.draw()

    def edit_titles(self) -> None:
        """DS9's Titles dialog: the plot's title and the axis labels."""
        dialog = PlotTitlesDialog(self.state, self)
        if dialog.exec():
            dialog.apply()
            self.setWindowTitle(self.state.title or "Plot Tool")
            self.draw()

    # -- drawing --------------------------------------------------------------------

    def draw(self) -> None:
        """Redraw everything from the state."""
        self.figure.clear()
        axes = self.figure.add_subplot(111)

        for dataset in self.state.visible:
            self._draw_dataset(axes, dataset)

        axes.set_title(self.state.title)
        axes.set_xlabel(self.state.x_axis.label)
        axes.set_ylabel(self.state.y_axis.label)
        self._apply_axis(axes, "x", self.state.x_axis)
        self._apply_axis(axes, "y", self.state.y_axis)

        if self.state.show_legend and self.state.visible:
            axes.legend(
                loc=self.state.legend_position.matplotlib,
                title=self.state.legend_title or None,
                fontsize="small",
            )

        self._install_selector()
        self.canvas.draw_idle()

    def _draw_dataset(self, axes, dataset: Dataset) -> None:
        """Draw one curve in whichever style the plot is in."""
        if self.state.style is PlotStyle.BAR:
            width = _bar_width(dataset.x)
            axes.bar(
                dataset.x,
                dataset.y,
                width=width,
                label=dataset.name,
                color=dataset.color if dataset.fill else "none",
                edgecolor=dataset.color,
                linewidth=max(1, dataset.width),
                yerr=dataset.y_error or None,
            )
            return

        line_style = "none" if self.state.style is PlotStyle.SCATTER else "-"
        if dataset.x_error or dataset.y_error:
            axes.errorbar(
                dataset.x,
                dataset.y,
                xerr=dataset.x_error or None,
                yerr=dataset.y_error or None,
                label=dataset.name,
                color=dataset.color,
                linewidth=dataset.width,
                linestyle=line_style,
                marker=dataset.marker,
                markersize=dataset.size,
                capsize=3,
            )
            return

        axes.plot(
            dataset.x,
            dataset.y,
            label=dataset.name,
            color=dataset.color,
            linewidth=dataset.width,
            linestyle=line_style,
            marker=dataset.marker,
            markersize=dataset.size,
        )

    def _apply_axis(self, axes, name: str, axis: Axis) -> None:
        """Put one axis's settings onto the drawn axes."""
        if axis.log:
            # A log axis needs positive data; matplotlib would draw nothing
            # and say nothing, so fall back rather than show an empty plot.
            values = [
                value for dataset in self.state.visible for value in (dataset.x if name == "x" else dataset.y)
            ]
            if values and min(values) > 0:
                getattr(axes, f"set_{name}scale")("log")

        limits = axis.range
        if limits is not None:
            getattr(axes, f"set_{name}lim")(*limits)
        if axis.flip:
            getattr(axes, f"invert_{name}axis")()

        axis_object = axes.xaxis if name == "x" else axes.yaxis
        if axis.number_format is AxisFormat.DECIMAL:
            axis_object.set_major_formatter(FormatStrFormatter("%g"))
        elif axis.number_format is AxisFormat.EXPONENTIAL:
            formatter = ScalarFormatter(useMathText=False)
            formatter.set_scientific(True)
            formatter.set_powerlimits((0, 0))
            axis_object.set_major_formatter(formatter)

        axes.grid(self.state.x_axis.grid or self.state.y_axis.grid, alpha=0.3)


def _bar_width(x: list[float]) -> float:
    """A sensible bar width: the smallest gap between neighbours.

    Without this every bar is a hairline, because matplotlib's default width
    of 0.8 assumes data spaced about one apart.
    """
    if len(x) < 2:
        return BAR_WIDTH_FRACTION
    gaps = [abs(b - a) for a, b in zip(sorted(x), sorted(x)[1:], strict=False) if b != a]
    return (min(gaps) * BAR_WIDTH_FRACTION) if gaps else BAR_WIDTH_FRACTION


def _show_text(parent: QWidget, title: str, body: str) -> None:
    """Show some text in a plain modeless window."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(560, 420)
    layout = QVBoxLayout(dialog)
    view = QPlainTextEdit(body)
    view.setReadOnly(True)
    layout.addWidget(view)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()


class AxisRangeDialog(QDialog):
    """DS9's Axes Range dialog.

    Args:
        x_axis: The x axis to edit.
        y_axis: The y axis.
        parent: Optional parent widget.
    """

    #: The widest range the spin boxes offer.
    LIMIT = 1e12

    def __init__(self, x_axis: Axis, y_axis: Axis, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Axes Range")
        self._x_axis = x_axis
        self._y_axis = y_axis

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._boxes: dict[str, QDoubleSpinBox] = {}
        bounds = {
            "x minimum": x_axis.minimum,
            "x maximum": x_axis.maximum,
            "y minimum": y_axis.minimum,
            "y maximum": y_axis.maximum,
        }
        for label, value in bounds.items():
            box = QDoubleSpinBox()
            box.setRange(-self.LIMIT, self.LIMIT)
            box.setDecimals(6)
            box.setValue(float(value) if value is not None else 0.0)
            form.addRow(f"{label}:", box)
            self._boxes[label] = box

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Reset
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        # Reset means "go back to fitting the data", which is what an
        # automatic range is, so it accepts rather than closing empty-handed.
        buttons.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self._reset)
        layout.addWidget(buttons)
        self._automatic = False

    def _reset(self) -> None:
        """Ask for an automatic range and close."""
        self._automatic = True
        self.accept()

    def apply(self) -> None:
        """Write the chosen ranges onto the axes."""
        if self._automatic:
            self._x_axis.clear_range()
            self._y_axis.clear_range()
            return
        self._x_axis.set_range(self._boxes["x minimum"].value(), self._boxes["x maximum"].value())
        self._y_axis.set_range(self._boxes["y minimum"].value(), self._boxes["y maximum"].value())


class PlotTitlesDialog(QDialog):
    """DS9's Titles dialog: the plot's title, the axis labels, the legend's.

    Args:
        state: The plot to retitle.
        parent: Optional parent widget.
    """

    def __init__(self, state: PlotState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Titles")
        self._state = state

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._title = QLineEdit(state.title)
        form.addRow("Title:", self._title)
        self._x_label = QLineEdit(state.x_axis.label)
        form.addRow("X axis:", self._x_label)
        self._y_label = QLineEdit(state.y_axis.label)
        form.addRow("Y axis:", self._y_label)
        self._legend = QLineEdit(state.legend_title)
        form.addRow("Legend:", self._legend)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply(self) -> None:
        """Write the chosen titles onto the plot."""
        self._state.title = self._title.text()
        self._state.x_axis.label = self._x_label.text()
        self._state.y_axis.label = self._y_label.text()
        self._state.legend_title = self._legend.text()
