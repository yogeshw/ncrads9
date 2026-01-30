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

"""FrameManager class for managing multiple frames."""

from __future__ import annotations

from enum import Enum, auto
from typing import Callable, Optional

from .frame import Frame


class MatchMode(Enum):
    """Frame matching modes."""

    NONE = auto()
    WCS = auto()
    IMAGE = auto()
    PHYSICAL = auto()
    AMPLIFIER = auto()
    DETECTOR = auto()


class LockMode(Enum):
    """Frame locking modes."""

    NONE = auto()
    FRAME = auto()
    CROSSHAIR = auto()
    CROP = auto()
    SLICE = auto()
    BIN = auto()
    AXES = auto()
    SCALE = auto()
    SCALE_LIMITS = auto()
    COLORBAR = auto()
    BLOCK = auto()
    SMOOTH = auto()


class FrameManager:
    """Manages multiple frames, active frame, frame matching and locking."""

    def __init__(self) -> None:
        """Initialize the FrameManager."""
        self._frames: dict[int, Frame] = {}
        self._active_frame_id: Optional[int] = None
        self._next_frame_id: int = 1
        self._match_mode: MatchMode = MatchMode.NONE
        self._lock_modes: set[LockMode] = set()
        self._frame_change_callbacks: list[Callable[[Optional[Frame]], None]] = []

    @property
    def frames(self) -> dict[int, Frame]:
        """Return all frames."""
        return self._frames

    @property
    def frame_count(self) -> int:
        """Return the number of frames."""
        return len(self._frames)

    @property
    def active_frame(self) -> Optional[Frame]:
        """Return the active frame."""
        if self._active_frame_id is not None:
            return self._frames.get(self._active_frame_id)
        return None

    @property
    def active_frame_id(self) -> Optional[int]:
        """Return the active frame ID."""
        return self._active_frame_id

    @property
    def match_mode(self) -> MatchMode:
        """Return the current match mode."""
        return self._match_mode

    @match_mode.setter
    def match_mode(self, mode: MatchMode) -> None:
        """Set the match mode."""
        self._match_mode = mode

    @property
    def lock_modes(self) -> set[LockMode]:
        """Return the current lock modes."""
        return self._lock_modes

    def create_frame(self, name: str = "") -> Frame:
        """Create a new frame.

        Args:
            name: Optional name for the frame.

        Returns:
            The newly created frame.
        """
        frame = Frame(self._next_frame_id, name)
        self._frames[self._next_frame_id] = frame
        self._next_frame_id += 1

        if self._active_frame_id is None:
            self.set_active_frame(frame.frame_id)

        return frame

    def delete_frame(self, frame_id: int) -> bool:
        """Delete a frame.

        Args:
            frame_id: ID of the frame to delete.

        Returns:
            True if the frame was deleted, False otherwise.
        """
        if frame_id not in self._frames:
            return False

        del self._frames[frame_id]

        if self._active_frame_id == frame_id:
            if self._frames:
                self.set_active_frame(next(iter(self._frames.keys())))
            else:
                self._active_frame_id = None
                self._notify_frame_change()

        return True

    def get_frame(self, frame_id: int) -> Optional[Frame]:
        """Get a frame by ID.

        Args:
            frame_id: ID of the frame to get.

        Returns:
            The frame, or None if not found.
        """
        return self._frames.get(frame_id)

    def set_active_frame(self, frame_id: int) -> bool:
        """Set the active frame.

        Args:
            frame_id: ID of the frame to make active.

        Returns:
            True if the frame was set as active, False otherwise.
        """
        if frame_id not in self._frames:
            return False

        self._active_frame_id = frame_id
        self._notify_frame_change()
        return True

    def next_frame(self) -> Optional[Frame]:
        """Switch to the next frame.

        Returns:
            The new active frame, or None if no frames exist.
        """
        if not self._frames:
            return None

        frame_ids = sorted(self._frames.keys())
        if self._active_frame_id is None:
            self.set_active_frame(frame_ids[0])
        else:
            current_index = frame_ids.index(self._active_frame_id)
            next_index = (current_index + 1) % len(frame_ids)
            self.set_active_frame(frame_ids[next_index])

        return self.active_frame

    def previous_frame(self) -> Optional[Frame]:
        """Switch to the previous frame.

        Returns:
            The new active frame, or None if no frames exist.
        """
        if not self._frames:
            return None

        frame_ids = sorted(self._frames.keys())
        if self._active_frame_id is None:
            self.set_active_frame(frame_ids[-1])
        else:
            current_index = frame_ids.index(self._active_frame_id)
            prev_index = (current_index - 1) % len(frame_ids)
            self.set_active_frame(frame_ids[prev_index])

        return self.active_frame

    def first_frame(self) -> Optional[Frame]:
        """Switch to the first frame.

        Returns:
            The first frame, or None if no frames exist.
        """
        if not self._frames:
            return None

        frame_ids = sorted(self._frames.keys())
        self.set_active_frame(frame_ids[0])
        return self.active_frame

    def last_frame(self) -> Optional[Frame]:
        """Switch to the last frame.

        Returns:
            The last frame, or None if no frames exist.
        """
        if not self._frames:
            return None

        frame_ids = sorted(self._frames.keys())
        self.set_active_frame(frame_ids[-1])
        return self.active_frame

    def add_lock_mode(self, mode: LockMode) -> None:
        """Add a lock mode.

        Args:
            mode: The lock mode to add.
        """
        self._lock_modes.add(mode)

    def remove_lock_mode(self, mode: LockMode) -> None:
        """Remove a lock mode.

        Args:
            mode: The lock mode to remove.
        """
        self._lock_modes.discard(mode)

    def is_locked(self, mode: LockMode) -> bool:
        """Check if a lock mode is active.

        Args:
            mode: The lock mode to check.

        Returns:
            True if the lock mode is active.
        """
        return mode in self._lock_modes

    def clear_locks(self) -> None:
        """Clear all lock modes."""
        self._lock_modes.clear()

    def match_frames(self) -> None:
        """Match all frames based on the current match mode."""
        if self._match_mode == MatchMode.NONE:
            return

        active = self.active_frame
        if active is None:
            return

        for frame in self._frames.values():
            if frame.frame_id != self._active_frame_id:
                self._apply_match(active, frame)

    def _apply_match(self, source: Frame, target: Frame) -> None:
        """Apply matching from source to target frame.

        Args:
            source: The source frame.
            target: The target frame.
        """
        if self._match_mode == MatchMode.IMAGE:
            target.settings.zoom = source.settings.zoom
            target.settings.pan_x = source.settings.pan_x
            target.settings.pan_y = source.settings.pan_y
        elif self._match_mode == MatchMode.WCS:
            # WCS matching would require coordinate transformation
            pass

    def add_frame_change_callback(
        self, callback: Callable[[Optional[Frame]], None]
    ) -> None:
        """Add a callback for frame change events.

        Args:
            callback: Callback function that receives the new active frame.
        """
        self._frame_change_callbacks.append(callback)

    def remove_frame_change_callback(
        self, callback: Callable[[Optional[Frame]], None]
    ) -> None:
        """Remove a frame change callback.

        Args:
            callback: The callback to remove.
        """
        if callback in self._frame_change_callbacks:
            self._frame_change_callbacks.remove(callback)

    def _notify_frame_change(self) -> None:
        """Notify all callbacks of a frame change."""
        active = self.active_frame
        for callback in self._frame_change_callbacks:
            callback(active)

    def clear_all(self) -> None:
        """Clear all frames."""
        self._frames.clear()
        self._active_frame_id = None
        self._next_frame_id = 1
        self._notify_frame_change()
