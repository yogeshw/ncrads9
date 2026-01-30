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
#
# Author: Yogesh Wadadekar

"""BlinkController class for frame blinking animation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional

from .frame import Frame
from .frame_manager import FrameManager


class BlinkMode(Enum):
    """Blinking modes."""

    FORWARD = auto()
    BACKWARD = auto()
    BOUNCE = auto()


class BlinkState(Enum):
    """Blinking states."""

    STOPPED = auto()
    RUNNING = auto()
    PAUSED = auto()


@dataclass
class BlinkSettings:
    """Settings for frame blinking."""

    interval: float = 0.5  # seconds between frames
    mode: BlinkMode = BlinkMode.FORWARD
    loop: bool = True
    start_frame: int = 0
    end_frame: Optional[int] = None


class BlinkController:
    """Controls frame blinking animation."""

    def __init__(self, frame_manager: FrameManager) -> None:
        """Initialize a BlinkController.

        Args:
            frame_manager: The frame manager to control.
        """
        self._frame_manager = frame_manager
        self._settings = BlinkSettings()
        self._state = BlinkState.STOPPED
        self._current_index: int = 0
        self._direction: int = 1  # 1 for forward, -1 for backward
        self._frame_order: list[int] = []
        self._last_update_time: float = 0.0
        self._callbacks: list[Callable[[Frame], None]] = []

    @property
    def settings(self) -> BlinkSettings:
        """Return the blink settings."""
        return self._settings

    @property
    def state(self) -> BlinkState:
        """Return the current blink state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Return whether blinking is running."""
        return self._state == BlinkState.RUNNING

    @property
    def is_paused(self) -> bool:
        """Return whether blinking is paused."""
        return self._state == BlinkState.PAUSED

    @property
    def current_frame_index(self) -> int:
        """Return the current frame index in the blink sequence."""
        return self._current_index

    @property
    def frame_count(self) -> int:
        """Return the number of frames in the blink sequence."""
        return len(self._frame_order)

    def set_interval(self, interval: float) -> None:
        """Set the blink interval.

        Args:
            interval: Time between frames in seconds.
        """
        self._settings.interval = max(0.01, interval)

    def set_mode(self, mode: BlinkMode) -> None:
        """Set the blink mode.

        Args:
            mode: The blinking mode.
        """
        self._settings.mode = mode

    def set_loop(self, loop: bool) -> None:
        """Set whether blinking loops.

        Args:
            loop: Whether to loop.
        """
        self._settings.loop = loop

    def set_frame_range(
        self, start: Optional[int] = None, end: Optional[int] = None
    ) -> None:
        """Set the frame range for blinking.

        Args:
            start: Start frame index.
            end: End frame index.
        """
        if start is not None:
            self._settings.start_frame = max(0, start)
        if end is not None:
            self._settings.end_frame = end

    def _build_frame_order(self) -> None:
        """Build the list of frame IDs in blink order."""
        frame_ids = sorted(self._frame_manager.frames.keys())

        if not frame_ids:
            self._frame_order = []
            return

        start = min(self._settings.start_frame, len(frame_ids) - 1)
        end = (
            self._settings.end_frame
            if self._settings.end_frame is not None
            else len(frame_ids) - 1
        )
        end = min(end, len(frame_ids) - 1)

        self._frame_order = frame_ids[start : end + 1]

    def start(self) -> bool:
        """Start blinking.

        Returns:
            True if blinking started, False if no frames.
        """
        self._build_frame_order()

        if not self._frame_order:
            return False

        self._current_index = 0
        self._direction = 1
        self._last_update_time = time.time()
        self._state = BlinkState.RUNNING

        # Set first frame
        self._frame_manager.set_active_frame(self._frame_order[0])

        return True

    def stop(self) -> None:
        """Stop blinking."""
        self._state = BlinkState.STOPPED
        self._current_index = 0
        self._direction = 1

    def pause(self) -> None:
        """Pause blinking."""
        if self._state == BlinkState.RUNNING:
            self._state = BlinkState.PAUSED

    def resume(self) -> None:
        """Resume blinking."""
        if self._state == BlinkState.PAUSED:
            self._state = BlinkState.RUNNING
            self._last_update_time = time.time()

    def toggle(self) -> None:
        """Toggle between running and paused states."""
        if self._state == BlinkState.RUNNING:
            self.pause()
        elif self._state == BlinkState.PAUSED:
            self.resume()
        else:
            self.start()

    def update(self) -> bool:
        """Update the blink animation.

        Returns:
            True if the frame changed, False otherwise.
        """
        if self._state != BlinkState.RUNNING:
            return False

        if not self._frame_order:
            return False

        current_time = time.time()
        elapsed = current_time - self._last_update_time

        if elapsed < self._settings.interval:
            return False

        self._last_update_time = current_time

        # Calculate next frame
        next_index = self._current_index + self._direction

        if self._settings.mode == BlinkMode.FORWARD:
            if next_index >= len(self._frame_order):
                if self._settings.loop:
                    next_index = 0
                else:
                    self.stop()
                    return False
        elif self._settings.mode == BlinkMode.BACKWARD:
            if next_index < 0:
                if self._settings.loop:
                    next_index = len(self._frame_order) - 1
                else:
                    self.stop()
                    return False
        elif self._settings.mode == BlinkMode.BOUNCE:
            if next_index >= len(self._frame_order):
                self._direction = -1
                next_index = len(self._frame_order) - 2
                if next_index < 0:
                    next_index = 0
            elif next_index < 0:
                self._direction = 1
                next_index = 1
                if next_index >= len(self._frame_order):
                    next_index = 0

        self._current_index = next_index
        frame_id = self._frame_order[self._current_index]
        self._frame_manager.set_active_frame(frame_id)

        # Notify callbacks
        frame = self._frame_manager.get_frame(frame_id)
        if frame is not None:
            for callback in self._callbacks:
                callback(frame)

        return True

    def next_frame(self) -> Optional[Frame]:
        """Manually advance to the next frame.

        Returns:
            The new active frame, or None.
        """
        if not self._frame_order:
            return None

        self._current_index = (self._current_index + 1) % len(self._frame_order)
        frame_id = self._frame_order[self._current_index]
        self._frame_manager.set_active_frame(frame_id)
        return self._frame_manager.get_frame(frame_id)

    def previous_frame(self) -> Optional[Frame]:
        """Manually go to the previous frame.

        Returns:
            The new active frame, or None.
        """
        if not self._frame_order:
            return None

        self._current_index = (self._current_index - 1) % len(self._frame_order)
        frame_id = self._frame_order[self._current_index]
        self._frame_manager.set_active_frame(frame_id)
        return self._frame_manager.get_frame(frame_id)

    def goto_frame(self, index: int) -> Optional[Frame]:
        """Go to a specific frame in the blink sequence.

        Args:
            index: Frame index in the blink sequence.

        Returns:
            The frame, or None if index is invalid.
        """
        if not self._frame_order:
            return None

        if 0 <= index < len(self._frame_order):
            self._current_index = index
            frame_id = self._frame_order[self._current_index]
            self._frame_manager.set_active_frame(frame_id)
            return self._frame_manager.get_frame(frame_id)
        return None

    def add_callback(self, callback: Callable[[Frame], None]) -> None:
        """Add a callback for frame change events.

        Args:
            callback: Callback function that receives the new frame.
        """
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[Frame], None]) -> None:
        """Remove a frame change callback.

        Args:
            callback: The callback to remove.
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def reset(self) -> None:
        """Reset the blink controller."""
        self.stop()
        self._settings = BlinkSettings()
        self._callbacks.clear()
