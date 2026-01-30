# NCRA DS9 - Astronomical Image Viewer
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
Threading utilities for background operations.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass
class TaskResult(Generic[T]):
    """Result of a background task."""

    success: bool
    value: T | None = None
    error: Exception | None = None


@dataclass
class BackgroundTask(Generic[T]):
    """A background task with progress tracking."""

    func: Callable[..., T]
    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    on_complete: Callable[[TaskResult[T]], None] | None = None
    on_progress: Callable[[float, str], None] | None = None
    name: str = "task"

    _cancelled: bool = field(default=False, init=False)
    _progress: float = field(default=0.0, init=False)
    _status: str = field(default="pending", init=False)

    def cancel(self) -> None:
        """Request task cancellation."""
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._cancelled

    def report_progress(self, progress: float, message: str = "") -> None:
        """
        Report task progress.

        Args:
            progress: Progress value between 0 and 1.
            message: Optional status message.
        """
        self._progress = min(max(progress, 0.0), 1.0)
        self._status = message
        if self.on_progress is not None:
            self.on_progress(self._progress, message)

    @property
    def progress(self) -> float:
        """Return current progress."""
        return self._progress

    @property
    def status(self) -> str:
        """Return current status message."""
        return self._status


class TaskRunner:
    """Thread pool executor for running background tasks."""

    def __init__(self, max_workers: int = 4) -> None:
        """
        Initialize task runner.

        Args:
            max_workers: Maximum number of worker threads.
        """
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[str, Future[Any]] = {}
        self._lock = threading.Lock()

    def submit(self, task: BackgroundTask[T]) -> Future[TaskResult[T]]:
        """
        Submit a task for background execution.

        Args:
            task: BackgroundTask to execute.

        Returns:
            Future containing the TaskResult.
        """

        def run_task() -> TaskResult[T]:
            try:
                result = task.func(*task.args, **task.kwargs)
                task_result = TaskResult(success=True, value=result)
            except Exception as e:
                task_result = TaskResult(success=False, error=e)

            if task.on_complete is not None:
                task.on_complete(task_result)

            return task_result

        future = self._executor.submit(run_task)

        with self._lock:
            self._tasks[task.name] = future

        return future

    def run_in_thread(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> Future[T]:
        """
        Run a function in a background thread.

        Args:
            func: Function to run.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Future containing the result.
        """
        return self._executor.submit(func, *args, **kwargs)

    def cancel_task(self, name: str) -> bool:
        """
        Attempt to cancel a task by name.

        Args:
            name: Task name.

        Returns:
            True if cancellation was successful.
        """
        with self._lock:
            if name in self._tasks:
                return self._tasks[name].cancel()
        return False

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the task runner.

        Args:
            wait: Whether to wait for pending tasks.
        """
        self._executor.shutdown(wait=wait)

    def __enter__(self) -> TaskRunner:
        """Enter context manager."""
        return self

    def __exit__(self, *args: object) -> None:
        """Exit context manager and shutdown."""
        self.shutdown(wait=True)
