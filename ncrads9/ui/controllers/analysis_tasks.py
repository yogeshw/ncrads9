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
External analysis tasks: loading them, offering them, running them.

This is the other end of `analysis/task_file.py`, `analysis/macros.py` and
`analysis/task_runner.py`. It builds the Analysis menu from what a `.ds9.ans`
file declares -- nested cascades, help entries, key bindings, buttons --
supplies the macros with everything they need to know about the current
frame, and puts each task's output wherever its sinks said.

What it replaced: a loader that read a homegrown `label|command` format and
"executed" a command by printing it to the status bar unless it happened to
start with `url:`, `open:` or `message:`. No DS9 analysis file would have
worked with it, and none of DS9's four task types, thirty-odd macros or four
output sinks existed.

Tasks whose file templates do not match what is loaded are greyed rather
than hidden, as DS9 does: a menu that changed shape with every file would be
impossible to learn.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QAction, QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMenu, QMessageBox

from ...analysis.macros import Expansion, MacroContext, expand
from ...analysis.plot import PlotDataError, PlotState, parse_data, parse_stdin
from ...analysis.task_file import (
    AnalysisFile,
    MenuNode,
    Task,
    TaskFileError,
    TaskType,
    parse_file,
)
from ...analysis.task_runner import TaskResult, TaskRunner
from ...regions.region_formats import RegionFormat
from ...regions.region_writer import RegionWriter
from ..dialogs.analysis_param_dialog import AnalysisParamDialog
from ..dialogs.analysis_text_dialog import AnalysisTextDialog
from .base import Controller

#: The filter the Load Analysis Commands dialog offers.
ANALYSIS_FILTER = "Analysis Files (*.ans *.analysis *.ds9);;All Files (*)"

#: The files DS9 loads at startup from the working directory and $HOME
#: (`ds9/doc/ref/analysis.html`).
STARTUP_NAMES: tuple[str, ...] = ("ds9.ans", "ds9.analysis")

#: And every `*.ds9` in these, in this order.
STARTUP_DIRECTORIES: tuple[str, ...] = (
    ".",
    "$HOME/bin",
    "/usr/local/bin",
    "/opt/local/bin",
    "/soft/saord/bin",
)

#: How the `$message` kinds map onto question buttons.
MESSAGE_BUTTONS = {"ok": ("ok",), "okcancel": ("ok", "cancel"), "yesno": ("yes", "no")}


class AnalysisTaskController(Controller):
    """Owns the external analysis tasks and the menu they build."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: The files loaded, in the order loaded.
        self.files: list[AnalysisFile] = []
        #: The actions added to the Analysis menu, so they can be removed.
        self._actions: list[QAction] = []
        #: The submenus added, likewise.
        self._menus: list[QMenu] = []
        #: The key bindings, which live as long as the file that declared them.
        self._shortcuts: list[QShortcut] = []
        #: Runners for tasks in flight, keyed by the task they run.
        self._runners: dict[int, TaskRunner] = {}
        #: One text window per task, so a second run appends to the first.
        self._windows: dict[str, AnalysisTextDialog] = {}
        #: Parameter values the user last entered, per parameter set.
        self._remembered: dict[str, dict[str, str]] = {}

    def connect(self) -> None:
        """Wire Load and Clear Analysis Commands."""
        self.menu.action_load_analysis_commands.triggered.connect(lambda _checked=False: self.load_commands())
        self.menu.action_clear_analysis_commands.triggered.connect(
            lambda _checked=False: self.clear_commands()
        )

    def sync(self) -> None:
        """Grey the tasks that do not apply to what is now loaded."""
        filename = self._filename()
        for action in self._actions:
            task = action.data()
            if isinstance(task, Task) and task.task_type is not TaskType.HELP:
                action.setEnabled(task.applies_to(filename))

    # -- loading ---------------------------------------------------------------

    def load_commands(self, path: str | None = None) -> bool:
        """Load an analysis file, DS9's Load Analysis Commands.

        Args:
            path: The file. Asked for when not given.

        Returns:
            Whether anything was loaded.
        """
        if path is None:
            path, _filter = QFileDialog.getOpenFileName(
                self.window, "Load Analysis Commands", "", ANALYSIS_FILTER
            )
            if not path:
                return False

        try:
            loaded = parse_file(path)
        except TaskFileError as exc:
            self.status(f"{Path(path).name}: {exc}", 5000)
            return False
        except OSError as exc:
            self.status(f"Cannot read {Path(path).name}: {exc}", 5000)
            return False

        self.files.append(loaded)
        self._install(loaded)
        count = len(loaded.tasks())
        self.status(f"Loaded {count} analysis task{'s' if count != 1 else ''} from {Path(path).name}")
        return True

    def autoload(self) -> int:
        """Load the analysis files DS9 loads at startup.

        DS9 looks for `ds9.ans` and `ds9.analysis` in the working directory
        and in `$HOME`, then for every `*.ds9` in a short list of
        directories. A file that will not parse is reported and skipped
        rather than stopping the others -- one bad file in `/usr/local/bin`
        should not cost the user the rest of their tasks.

        Returns:
            How many files were loaded.
        """
        loaded = 0
        for path in self.startup_files():
            try:
                found = parse_file(path)
            except (TaskFileError, OSError) as exc:
                self.status(f"Skipped {path.name}: {exc}", 4000)
                continue
            self.files.append(found)
            self._install(found)
            loaded += 1
        return loaded

    @staticmethod
    def startup_files() -> list[Path]:
        """Every analysis file DS9 would load at startup, in its order."""
        found: list[Path] = []
        home = Path(os.path.expanduser("~"))

        for directory in (Path.cwd(), home):
            for name in STARTUP_NAMES:
                candidate = directory / name
                if candidate.is_file():
                    found.append(candidate)

        for raw in STARTUP_DIRECTORIES:
            directory = Path(os.path.expandvars(raw)).expanduser()
            if not directory.is_dir():
                continue
            found.extend(sorted(path for path in directory.glob("*.ds9") if path.is_file()))

        # The same file named twice -- `.` and the working directory -- is
        # one file, and loading it twice would double every menu entry.
        unique: list[Path] = []
        seen: set[Path] = set()
        for path in found:
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                unique.append(path)
        return unique

    def clear_commands(self) -> None:
        """Remove every loaded task, DS9's Clear Analysis Commands."""
        if not self.files:
            self.status("No analysis commands are loaded", 2500)
            return

        for action in self._actions:
            self.menu.analysis_menu.removeAction(action)
        for submenu in self._menus:
            self.menu.analysis_menu.removeAction(submenu.menuAction())
        for shortcut in self._shortcuts:
            shortcut.setEnabled(False)
            shortcut.deleteLater()

        bar = getattr(self.window, "button_bar", None)
        if bar is not None and hasattr(bar, "clear_analysis_buttons"):
            bar.clear_analysis_buttons()

        count = sum(len(found.tasks()) for found in self.files)
        self._actions.clear()
        self._menus.clear()
        self._shortcuts.clear()
        self.files.clear()
        self.status(f"Cleared {count} analysis task{'s' if count != 1 else ''}")

    # -- building the menu -------------------------------------------------------

    def _install(self, loaded: AnalysisFile) -> None:
        """Put one file's tasks on the menu and bind its keys."""
        before = self.menu.action_load_analysis_commands
        separator = self.menu.analysis_menu.insertSeparator(before)
        self._actions.append(separator)
        self._add_entries(self.menu.analysis_menu, loaded.menu, before)

        for task in loaded.binds:
            self._bind(task)
        for bar in loaded.buttonbars:
            for task in bar:
                self._add_button(task)
        self.sync()

    def _add_entries(self, menu: QMenu, node: MenuNode, before: QAction | None) -> None:
        """Add one menu node's entries, in file order."""
        for entry in node.entries:
            if entry is None:
                action = menu.insertSeparator(before) if before else menu.addSeparator()
                self._actions.append(action)
            elif isinstance(entry, MenuNode):
                submenu = QMenu(entry.label, menu)
                if before:
                    menu.insertMenu(before, submenu)
                else:
                    menu.addMenu(submenu)
                self._menus.append(submenu)
                self._add_entries(submenu, entry, None)
            else:
                self._add_task(menu, entry, before)

    def _add_task(self, menu: QMenu, task: Task, before: QAction | None) -> None:
        """Add one task as a menu entry."""
        action = QAction(task.label, self.window)
        action.setData(task)
        action.triggered.connect(lambda _checked=False, t=task: self.run(t))
        if before:
            menu.insertAction(before, action)
        else:
            menu.addAction(action)
        self._actions.append(action)

    def _add_button(self, task: Task) -> None:
        """Add one task to the button bar, if there is one to add it to."""
        bar = getattr(self.window, "button_bar", None)
        adder = getattr(bar, "add_analysis_button", None)
        if adder is None:
            # No button bar to put it on; the task is still runnable from
            # XPA and is not silently lost, because it stays in `files`.
            return
        adder(task.label, lambda t=task: self.run(t))

    def _bind(self, task: Task) -> None:
        """Bind a task to a keystroke, DS9's `bind <key>`."""
        sequence = QKeySequence(task.event)
        if sequence.isEmpty():
            self.status(f"Cannot bind {task.label!r} to {task.event!r}", 3000)
            return
        shortcut = QShortcut(sequence, self.window)
        shortcut.activated.connect(lambda t=task: self.run(t))
        self._shortcuts.append(shortcut)

    # -- running -------------------------------------------------------------------

    def run(self, task: Task, sync: bool = False) -> TaskResult | None:
        """Run one task: expand its command line, then do what it says.

        Args:
            task: The task.
            sync: Wait for it and return the result. For XPA, where a
                caller is waiting; the menu never does this.

        Returns:
            The result when `sync`, otherwise None -- the output arrives at
            the sinks later.
        """
        if task.task_type is TaskType.HELP:
            self._show_text(task.label, task.command, append=False)
            return None

        if task.task_type is TaskType.WEB:
            QDesktopServices.openUrl(QUrl(task.command))
            self.status(f"Opened {task.label}")
            return None

        expanded = expand(task.command, self.context(task))
        if expanded.cancelled:
            self.status(f"{task.label}: cancelled", 2000)
            return None

        if sync:
            from ...analysis.task_runner import run_sync

            result = run_sync(expanded, task.label, task.directory)
            self._deliver(result, expanded)
            return result

        runner = TaskRunner(self.window)
        runner.finished.connect(lambda result, e=expanded: self._on_finished(result, e))
        self._runners[id(task)] = runner
        if not runner.start(expanded, task.label, task.directory):
            self._runners.pop(id(task), None)
            return None
        self.status(f"Running {task.label}...")
        return None

    def cancel_all(self) -> int:
        """Stop every running task.

        Returns:
            How many were stopped.
        """
        running = [runner for runner in self._runners.values() if runner.running]
        for runner in running:
            runner.cancel()
        return len(running)

    def _on_finished(self, result: TaskResult, expansion: Expansion) -> None:
        """A task ended; put its output where the sinks said."""
        for key, runner in list(self._runners.items()):
            if not runner.running:
                self._runners.pop(key, None)
        self._deliver(result, expansion)

    def _deliver(self, result: TaskResult, expansion: Expansion) -> None:
        """Route one task's output to its sinks (M7-4)."""
        if result.cancelled:
            self.status(f"{result.label}: cancelled", 2500)
            return

        sinks = expansion.sinks
        if sinks.null:
            # `$null` expects nothing, and DS9 does not even report failure.
            return

        if result.failure:
            self._show_text(result.label or "Analysis", result.failure)
            return

        if sinks.plot is not None:
            self._deliver_plot(result, expansion)
        if sinks.image is not None:
            self._deliver_image(result, expansion)
        if sinks.text or not sinks.any:
            # No sink named is DS9's default of showing the text: silence
            # would leave the user unsure the task ran at all.
            self._show_text(result.label or "Analysis", result.text(sinks.include_stderr))

        if result.status not in (0, None) and not sinks.text:
            self.status(f"{result.label} exited {result.status}", 4000)

    def _deliver_plot(self, result: TaskResult, expansion: Expansion) -> None:
        """Show a task's output as a plot."""
        sink = expansion.sinks.plot
        if sink is None:
            return
        try:
            if sink.from_stdin:
                parsed = parse_stdin(result.output, name=result.label or "Data")
                if parsed.message:
                    self._show_text(result.label or "Analysis", parsed.message)
                if parsed.dataset is None:
                    return
                state = PlotState(title=parsed.title)
                state.x_axis.label = parsed.x_label
                state.y_axis.label = parsed.y_label
                state.add(parsed.dataset)
            else:
                state = PlotState(title=sink.title)
                state.x_axis.label = sink.x_label
                state.y_axis.label = sink.y_label
                state.add(parse_data(result.output, sink.dimension, name=result.label or "Data"))
        except PlotDataError as exc:
            self._show_text(result.label or "Analysis", f"{exc}\n\n{result.output}")
            return
        self.window.analysis.show_plot(state)

    def _deliver_image(self, result: TaskResult, expansion: Expansion) -> None:
        """Load a task's output into a frame, DS9's `$image`."""
        import tempfile

        sink = expansion.sinks.image
        if sink is None or not result.output:
            return

        # The output is FITS, and FITS is binary, so it goes through a file
        # rather than through the text the other sinks want.
        with tempfile.NamedTemporaryFile(suffix=".fits", delete=False) as handle:
            handle.write(result.output.encode("latin-1", errors="replace"))
            path = handle.name

        if sink.target in ("new", "rgb", "3d"):
            self.window.frame_controller.new_frame()
        try:
            self.window.display.load_fits(path)
        except Exception as exc:
            self._show_text(result.label or "Analysis", f"Could not load the result: {exc}")

    def _show_text(self, title: str, body: str, append: bool = True) -> AnalysisTextDialog:
        """Show text in the window belonging to this task.

        One window per task: running a task twice appends, so two runs can
        be compared, which is DS9's behaviour and the reason its text window
        has a Clear button.
        """
        window = self._windows.get(title)
        if window is None:
            window = AnalysisTextDialog(title, body, self.window)
            window.finished.connect(lambda _result, key=title: self._windows.pop(key, None))
            self._windows[title] = window
            window.show()
            return window

        if append:
            window.append(body)
        else:
            window.set_text(body)
        window.raise_()
        window.activateWindow()
        return window

    # -- the macros' view of the application ---------------------------------------

    def context(self, task: Task, x: float | None = None, y: float | None = None) -> MacroContext:
        """Everything the macros need, gathered from the current frame.

        Args:
            task: The task, whose directory `$dir` reports.
            x: The event x position, for a `bind` task's `$x`.
            y: Its y position.
        """
        frame = self.frame
        data = None if frame is None else frame.image_data
        height, width = (data.shape[0], data.shape[1]) if data is not None else (0, 0)

        return MacroContext(
            filename=str(getattr(frame, "file_spec", None) or self._filename() or ""),
            filename_root=Path(self._filename() or "").name,
            filename_full=str(getattr(frame, "filepath", "") or ""),
            width=width,
            height=height,
            depth=self._depth(),
            bitpix=self._bitpix(),
            directory=task.directory,
            regions=self._regions,
            coordinate=lambda axis, system, sky, fmt: self._coordinate(axis, system, sky, fmt, x, y),
            value=lambda: self._value(x, y),
            pan=self._pan,
            data_file=self._data_file,
            entry=self._entry,
            message=self._message,
            message_ok=self._message_ok,
            file_dialog=self._file_dialog,
            parameters=self._parameters,
        )

    def _filename(self) -> str | None:
        """The current frame's file, or None."""
        frame = self.frame
        path = getattr(frame, "filepath", None) if frame else None
        return str(path) if path else None

    def _depth(self) -> int:
        """How many slices the current frame's data has."""
        frame = self.frame
        image = getattr(frame, "image", None) if frame else None
        data = getattr(image, "data", None)
        return int(data.shape[0]) if data is not None and data.ndim == 3 else 1

    def _bitpix(self) -> int:
        """The current frame's BITPIX, from its header or its dtype."""
        frame = self.frame
        header = getattr(frame, "header", None) if frame else None
        if header is not None and "BITPIX" in header:
            return int(header["BITPIX"])
        data = getattr(frame, "image_data", None) if frame else None
        if data is None:
            return 0
        import numpy as np

        return {
            np.dtype("uint8"): 8,
            np.dtype("int16"): 16,
            np.dtype("int32"): 32,
            np.dtype("float32"): -32,
            np.dtype("float64"): -64,
        }.get(data.dtype, -32)

    def _regions(self, options: str) -> str:
        """`$regions` -- the frame's regions, in the format asked for."""
        frame = self.frame
        regions = list(getattr(frame, "regions", ()) or ()) if frame else []
        if not regions:
            return ""

        wanted = [part.strip().lower() for part in options.split(",") if part.strip()]
        region_format = RegionFormat.DS9
        for word in wanted:
            try:
                region_format = RegionFormat(word if word != "saotng" else "saoimage")
                break
            except ValueError:
                continue

        # The property filters: only the regions with all of them.
        if "include" in wanted:
            regions = [region for region in regions if region.include]
        if "exclude" in wanted:
            regions = [region for region in regions if not region.include]
        if "source" in wanted:
            regions = [region for region in regions if getattr(region, "source", True)]
        if "background" in wanted:
            regions = [region for region in regions if not getattr(region, "source", True)]

        writer = RegionWriter(region_format=region_format)
        return writer.to_string(regions, include_header=False).strip()

    def _coordinate(
        self,
        axis: str,
        system: str,
        sky: str,
        sky_format: str,
        x: float | None,
        y: float | None,
    ) -> str:
        """`$x`, `$y` and `$z` -- where the event was, in the system asked for."""
        if axis == "z":
            frame = self.frame
            return str(int(getattr(frame, "slice_index", 0) or 0) + 1)
        if x is None or y is None:
            return ""

        if system in ("image", "physical", "amplifier", "detector"):
            return f"{x:g}" if axis == "x" else f"{y:g}"

        frame = self.frame
        handler = getattr(frame, "wcs_handler", None) if frame else None
        if handler is None or not getattr(handler, "is_valid", False):
            return f"{x:g}" if axis == "x" else f"{y:g}"

        from ...coordinates.coord_system import CoordinateContext

        context = CoordinateContext.from_names(frame="wcs", sky=sky, sky_format=sky_format)
        longitude, latitude = handler.pixel_to_world(x, y)
        first, second = context.format_pair(*context.transform(longitude, latitude))
        return first if axis == "x" else second

    def _value(self, x: float | None, y: float | None) -> str:
        """`$value` -- the pixel under a bind event."""
        frame = self.frame
        data = getattr(frame, "image_data", None) if frame else None
        if data is None or x is None or y is None:
            return ""
        column, row = int(round(x)) - 1, int(round(y)) - 1
        if 0 <= row < data.shape[0] and 0 <= column < data.shape[1]:
            return f"{float(data[row, column]):g}"
        return ""

    def _pan(self, system: str, sky: str, sky_format: str) -> str:
        """`$pan` -- where the frame is centred."""
        frame = self.frame
        data = getattr(frame, "image_data", None) if frame else None
        if data is None:
            return ""
        centre_x = data.shape[1] / 2.0
        centre_y = data.shape[0] / 2.0
        if system in ("image", "physical", "amplifier", "detector"):
            return f"{centre_x:g} {centre_y:g}"
        first = self._coordinate("x", system, sky, sky_format, centre_x, centre_y)
        second = self._coordinate("y", system, sky, sky_format, centre_x, centre_y)
        return f"{first} {second}"

    def _data_file(self) -> str | None:
        """`$data` -- the current frame written out as FITS, for stdin."""
        import tempfile

        frame = self.frame
        data = getattr(frame, "image_data", None) if frame else None
        if data is None:
            return None

        from astropy.io import fits

        header = getattr(frame, "header", None)
        with tempfile.NamedTemporaryFile(suffix=".fits", delete=False) as handle:
            path = handle.name
        try:
            fits.PrimaryHDU(data=data, header=header).writeto(path, overwrite=True)
        except Exception:
            return None
        return path

    # -- the prompts -------------------------------------------------------------------

    def _entry(self, message: str) -> str | None:
        """`$entry(msg)` -- ask for a string."""
        text, accepted = QInputDialog.getText(self.window, "Analysis", message)
        return text if accepted else None

    def _message(self, kind: str, body: str) -> bool:
        """`$message([kind,]msg)` -- show a message; False cancels the task."""
        if kind == "ok":
            QMessageBox.information(self.window, "Analysis", body)
            return True
        if kind == "yesno":
            answer = QMessageBox.question(self.window, "Analysis", body)
            return answer == QMessageBox.StandardButton.Yes
        answer = QMessageBox.warning(
            self.window,
            "Analysis",
            body,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Ok

    def _message_ok(self, kind: str, body: str) -> str | None:
        """`$messageok(...)` -- show one and substitute the button pressed."""
        if kind == "ok":
            QMessageBox.information(self.window, "Analysis", body)
            return "ok"
        if kind == "yesno":
            answer = QMessageBox.question(self.window, "Analysis", body)
            return "yes" if answer == QMessageBox.StandardButton.Yes else "no"
        answer = QMessageBox.warning(
            self.window,
            "Analysis",
            body,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        return "ok" if answer == QMessageBox.StandardButton.Ok else "cancel"

    def _file_dialog(self, kind: str) -> str | None:
        """`$filedialog(open|save)` -- ask for a path."""
        if kind == "save":
            path, _filter = QFileDialog.getSaveFileName(self.window, "Analysis: Save")
        else:
            path, _filter = QFileDialog.getOpenFileName(self.window, "Analysis: Open")
        return path or None

    def _parameters(self, name: str) -> dict[str, str] | None:
        """`$param(name)` -- run the named parameter dialog.

        The values are remembered per set, so running a task twice offers
        what was typed last time rather than starting over.
        """
        parameters = None
        for loaded in self.files:
            if name in loaded.parameters:
                parameters = loaded.parameters[name]
                break
        if parameters is None:
            self.status(f"No such parameter set: {name}", 3000)
            return None

        dialog = AnalysisParamDialog(parameters, self._expand_default, self.window)
        remembered = self._remembered.get(name, {})
        for variable, value in remembered.items():
            widget = dialog._widgets.get(variable)
            if widget is not None and hasattr(widget, "setText"):
                widget.setText(value)

        if not dialog.exec():
            return None
        values = dialog.values()
        self._remembered[name] = values
        return values

    def _expand_default(self, value: str) -> str:
        """Expand the macros a parameter default may contain.

        DS9's own sample has `{$filename}` and `{$width}` as defaults, so a
        dialog that showed them literally would be showing the wrong thing.
        """
        if "$" not in value:
            return value
        task = Task("", ("*",), TaskType.MENU, "", directory="")
        return expand(value, self.context(task)).command
