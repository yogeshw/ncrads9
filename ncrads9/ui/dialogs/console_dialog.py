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
A Python console, where DS9 has a TCL one.

DS9's File menu offers `Open TCL Console` and `Source TCL`, because DS9 is
written in TCL and its console is its own interpreter. Ours is written in
Python, so the console is a Python one and the script it sources is a
Python script -- the same feature, in the language the application is
actually made of.

What the console can reach is deliberately wide: `window` is the main
window, and everything a controller can do is a method on it. That is the
point. It is not a sandbox and does not pretend to be one: anyone who can
type in this window is already running the application.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import codeop
import contextlib
import io
import sys
import traceback

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QDialog,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

#: How big the console opens.
WINDOW_SIZE = (760, 460)

#: What it says when it opens.
BANNER = (
    "NCRADS9 Python console. `window` is the main window; "
    "`window.zoom`, `window.region`, `window.crop` and the rest are its "
    "controllers.\n"
    "Try: window.zoom.set_zoom(2)\n"
)

#: How many lines of history are remembered.
HISTORY = 200


class ConsoleDialog(QDialog):
    """A Python prompt with the application in scope."""

    def __init__(self, window=None, parent=None) -> None:
        """
        Args:
            window: The main window, put in the console's namespace.
            parent: The widget to sit over.
        """
        super().__init__(parent)
        self.setWindowTitle("Python Console")
        self.resize(*WINDOW_SIZE)

        #: What the console can see.
        self.namespace: dict = {"window": window, "ncrads9": _package()}
        #: Lines typed, for the up and down arrows.
        self.history: list[str] = []
        self._history_index = 0
        #: A statement being continued over several lines.
        self._pending: list[str] = []

        layout = QVBoxLayout(self)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("monospace"))
        self.output.setPlainText(BANNER)
        layout.addWidget(self.output)

        self.prompt = QLineEdit()
        self.prompt.setFont(QFont("monospace"))
        self.prompt.setPlaceholderText(">>>")
        self.prompt.returnPressed.connect(self.run_prompt)
        self.prompt.installEventFilter(self)
        layout.addWidget(self.prompt)

        close = QPushButton("Close")
        close.clicked.connect(self.close)
        layout.addWidget(close)

    # -- running things ----------------------------------------------------------

    def run_prompt(self) -> None:
        """Run whatever is typed, and show what it said."""
        text = self.prompt.text()
        self.prompt.clear()
        if not text.strip() and not self._pending:
            return

        self.history.append(text)
        del self.history[: max(0, len(self.history) - HISTORY)]
        self._history_index = len(self.history)
        self.echo(("... " if self._pending else ">>> ") + text)
        self.run(text)

    def run(self, text: str) -> str:
        """Run one line, continuing a statement if one is open.

        Args:
            text: The line.

        Returns:
            Whatever it printed or raised, which is also shown.
        """
        self._pending.append(text)
        source = "\n".join(self._pending)

        # Compiled and run here rather than through
        # `InteractiveInterpreter.runsource`, which reports an error by
        # calling `sys.excepthook` when something has replaced it -- so the
        # traceback would go to the application's handler instead of to
        # this window, which is the one place it is any use.
        try:
            compiled = codeop.compile_command(source, "<console>", "single")
        except (SyntaxError, OverflowError, ValueError):
            self._pending = []
            self.prompt.setPlaceholderText(">>>")
            output = "".join(traceback.format_exception_only(*sys.exc_info()[:2]))
            self.echo(output.rstrip())
            return output

        if compiled is None:
            # More lines wanted: keep them and change the prompt.
            self.prompt.setPlaceholderText("...")
            return ""

        self._pending = []
        self.prompt.setPlaceholderText(">>>")
        captured = io.StringIO()
        try:
            with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                exec(compiled, self.namespace)
        except SystemExit:
            # `exit()` in a console should close the console, not the
            # application it is meant to be driving.
            self.echo("(use the Close button)")
            return ""
        except BaseException:
            output = captured.getvalue() + traceback.format_exc()
            self.echo(output.rstrip())
            return output

        output = captured.getvalue()
        if output.strip():
            self.echo(output.rstrip())
        return output

    def run_script(self, path: str) -> str:
        """Run a whole file, as DS9's Source TCL does for TCL.

        Args:
            path: The script.

        Returns:
            Whatever it printed or raised.
        """
        from pathlib import Path

        try:
            source = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            message = f"Could not read {Path(path).name}: {exc}"
            self.echo(message)
            return message

        self.echo(f">>> # {path}")
        captured = io.StringIO()
        try:
            with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                exec(compile(source, str(path), "exec"), self.namespace)
        except BaseException:
            output = captured.getvalue() + traceback.format_exc()
            self.echo(output.rstrip())
            return output

        output = captured.getvalue()
        if output.strip():
            self.echo(output.rstrip())
        return output

    def echo(self, text: str) -> None:
        """Put something in the output pane."""
        self.output.appendPlainText(text)
        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())

    # -- the history ---------------------------------------------------------------

    def eventFilter(self, watched, event):
        """Walk the history with the up and down arrows."""
        if watched is self.prompt and isinstance(event, QKeyEvent):
            if event.type() == QKeyEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Up:
                    self.recall(-1)
                    return True
                if event.key() == Qt.Key.Key_Down:
                    self.recall(1)
                    return True
        return super().eventFilter(watched, event)

    def recall(self, step: int) -> None:
        """Show an earlier or later line from the history."""
        if not self.history:
            return
        self._history_index = max(0, min(len(self.history), self._history_index + step))
        if self._history_index >= len(self.history):
            self.prompt.clear()
            return
        self.prompt.setText(self.history[self._history_index])


def _package():
    """The `ncrads9` package, so the console can import from it easily."""
    import ncrads9

    return ncrads9
