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
Running an analysis task, and being able to stop it.

An analysis command is a shell pipeline -- `$data | funcnts | $text` becomes
`funcnts` with a FITS file on its stdin -- so it runs through a shell rather
than being split into arguments. That is what the format is: a command line
the user wrote for their own shell.

It runs asynchronously, because the point of an external task is that it may
take a while, and a task that froze the window until `funcnts` finished
would be worse than no task at all. `run_sync` exists for XPA, where the
caller is waiting on an answer and there is no window to freeze.

`$geturl` is the exception DS9 carved out for platforms with no subprocess
support: it fetches a URL and hands the body to the sink, with no shell
involved. It is honoured here for the same reason it is documented -- an
analysis file written for it should work.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import urlopen

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from .macros import Expansion

#: How long `run_sync` waits before giving up, in seconds.
SYNC_TIMEOUT = 60.0

#: How long a URL fetch waits, in seconds.
URL_TIMEOUT = 30.0

#: How long a cancelled process is given to die politely before it is killed.
TERMINATE_GRACE_MS = 2000


@dataclass
class TaskResult:
    """What a task produced.

    Attributes:
        label: The task's menu label, for titling whatever shows the output.
        output: Its standard output, which is what the sinks display.
        errors: Its standard error.
        status: The exit status, or None if it never ran.
        cancelled: True if the user stopped it.
        failure: Why it could not be run at all, if it could not.
    """

    label: str = ""
    output: str = ""
    errors: str = ""
    status: int | None = None
    cancelled: bool = False
    failure: str = ""

    @property
    def ok(self) -> bool:
        """Whether the task ran and said it succeeded."""
        return not self.cancelled and not self.failure and self.status == 0

    def text(self, include_errors: bool = False) -> str:
        """What to show in a text window.

        DS9's `|` shows stdout and `|&` shows both. A task that failed
        shows its errors regardless -- silence would be the worst answer.
        """
        if self.failure:
            return self.failure
        if include_errors or (self.status not in (0, None) and self.errors):
            return "\n".join(part for part in (self.output, self.errors) if part)
        return self.output


def shell() -> list[str]:
    """The shell to run a command line through.

    `|&` for stdout-and-stderr is bash's spelling, and analysis files use
    it, so bash is preferred where there is one.
    """
    for candidate in ("bash", "sh"):
        found = shutil.which(candidate)
        if found:
            return [found, "-c"]
    return ["/bin/sh", "-c"]


def environment(directory: str) -> dict[str, str]:
    """The environment a task runs in.

    DS9 puts the analysis file's own directory on PATH
    (`analysis.tcl:206`), so a task can name a script sitting beside it.
    """
    result = dict(os.environ)
    if directory:
        result["PATH"] = f"{directory}{os.pathsep}{result.get('PATH', '')}"
    return result


def fetch(url: str, timeout: float = URL_TIMEOUT) -> TaskResult:
    """Retrieve a URL, for `$geturl`.

    Only http and https: DS9 says "Only HTTP is supported", and a `file:`
    URL reaching a fetcher is a way to read a file the user did not mean to
    share.
    """
    if not url.lower().startswith(("http://", "https://")):
        return TaskResult(failure=f"$geturl supports http and https only, not {url!r}")
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read()
    except (URLError, OSError, ValueError) as exc:
        return TaskResult(failure=f"Could not fetch {url}: {exc}")
    return TaskResult(output=body.decode("utf-8", errors="replace"), status=0)


def run_sync(
    expansion: Expansion,
    label: str = "",
    directory: str = "",
    timeout: float = SYNC_TIMEOUT,
) -> TaskResult:
    """Run a task and wait for it. For XPA, where someone is waiting.

    Raises nothing: a task that cannot be run comes back as a result with
    `failure` set, because the caller wants an answer either way.
    """
    if expansion.geturl:
        return TaskResult(label=label, **_fields(fetch(expansion.geturl)))
    if not expansion.command:
        return TaskResult(label=label, failure="Nothing to run")

    stdin = _open_stdin(expansion)
    try:
        completed = subprocess.run(
            [*shell(), expansion.command],
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=stdin,
            env=environment(directory),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return TaskResult(label=label, failure=f"{label or 'Task'} timed out after {timeout:g}s")
    except OSError as exc:
        return TaskResult(label=label, failure=f"Could not run {label or 'task'}: {exc}")
    finally:
        if stdin is not None:
            stdin.close()

    return TaskResult(
        label=label,
        output=completed.stdout or "",
        errors=completed.stderr or "",
        status=completed.returncode,
    )


def _fields(result: TaskResult) -> dict:
    """A result's fields, minus its label, for relabelling one."""
    return {
        "output": result.output,
        "errors": result.errors,
        "status": result.status,
        "cancelled": result.cancelled,
        "failure": result.failure,
    }


def _open_stdin(expansion: Expansion):
    """The file `$data` asked to be fed in, opened, or None."""
    if not expansion.stdin_file:
        return None
    try:
        return open(expansion.stdin_file, "rb")
    except OSError:
        return None


class TaskRunner(QObject):
    """Runs one analysis task at a time, and can be told to stop.

    One runner per task rather than one shared: two tasks started together
    are two processes, and a Cancel button that stopped whichever happened
    to be last would be a trap.
    """

    #: Emitted with a `TaskResult` when the task ends, however it ends.
    finished = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._label = ""
        self._cancelled = False
        self._stdin: bytes | None = None

    @property
    def running(self) -> bool:
        """Whether a task is in flight."""
        return self._process is not None

    def start(self, expansion: Expansion, label: str = "", directory: str = "") -> bool:
        """Begin a task.

        Args:
            expansion: The expanded command and its sinks.
            label: The task's name, carried through to the result.
            directory: The analysis file's directory, put on PATH.

        Returns:
            False when there was nothing to run, or a task already is; the
            caller then knows no `finished` will arrive for this call.
        """
        if self.running:
            return False

        self._label = label
        self._cancelled = False

        if expansion.geturl:
            # No subprocess, which is the whole point of `$geturl`.
            result = fetch(expansion.geturl)
            result.label = label
            self.finished.emit(result)
            return True

        if not expansion.command:
            self.finished.emit(TaskResult(label=label, failure="Nothing to run"))
            return False

        self._stdin = _read(expansion.stdin_file)

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        qt_environment = process.processEnvironment()
        for name, value in environment(directory).items():
            qt_environment.insert(name, value)
        process.setProcessEnvironment(qt_environment)
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)
        self._process = process

        command = shell()
        process.start(command[0], [*command[1:], expansion.command])
        if self._stdin is not None:
            process.write(self._stdin)
        process.closeWriteChannel()
        return True

    def cancel(self) -> None:
        """Stop the running task, politely and then not."""
        process = self._process
        if process is None:
            return
        self._cancelled = True
        process.terminate()
        if not process.waitForFinished(TERMINATE_GRACE_MS):
            process.kill()
            process.waitForFinished(TERMINATE_GRACE_MS)

    # -- process callbacks ---------------------------------------------------

    def _on_finished(self, status: int, _exit_status) -> None:
        """Gather the output and report."""
        process = self._process
        if process is None:
            return
        result = TaskResult(
            label=self._label,
            output=bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace"),
            errors=bytes(process.readAllStandardError()).decode("utf-8", errors="replace"),
            status=int(status),
            cancelled=self._cancelled,
        )
        self._release()
        self.finished.emit(result)

    def _on_error(self, error) -> None:
        """Report a task that could not be started at all."""
        if self._process is None:
            return
        if error == QProcess.ProcessError.Crashed and self._cancelled:
            # Cancelling shows up as a crash; `_on_finished` reports it.
            return
        self._release()
        self.finished.emit(TaskResult(label=self._label, failure=f"Could not run {self._label or 'task'}"))

    def _release(self) -> None:
        """Let go of the finished process."""
        if self._process is not None:
            self._process.deleteLater()
        self._process = None
        self._stdin = None


def _read(path: str | None) -> bytes | None:
    """The bytes of the `$data` file, or None if there is none to read."""
    if not path:
        return None
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None
