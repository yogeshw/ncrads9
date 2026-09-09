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
Frame collection and navigation.

Owns the ordered list of frames and the notion of a current frame, and
provides DS9's navigation verbs: new/delete, first/prev/next/last, goto and
move.

Author: Yogesh Wadadekar
"""

from .frame import Frame


class FrameManager:
    """Manages multiple image frames."""

    def __init__(self):
        self._frames: list[Frame] = []
        self._current_index: int = -1
        self._next_id: int = 1

        # Create initial empty frame
        self.new_frame()

    @property
    def current_frame(self) -> Frame | None:
        """Get current active frame."""
        if 0 <= self._current_index < len(self._frames):
            return self._frames[self._current_index]
        return None

    @property
    def current_index(self) -> int:
        """Get current frame index."""
        return self._current_index

    @property
    def num_frames(self) -> int:
        """Get total number of frames."""
        return len(self._frames)

    @property
    def frames(self) -> list[Frame]:
        """Get list of frames."""
        return self._frames

    def new_frame(self, frame_type: str = "base") -> Frame:
        """Create a new empty frame."""
        frame = Frame(frame_id=self._next_id, frame_type=frame_type)
        self._frames.append(frame)
        self._current_index = len(self._frames) - 1
        self._next_id += 1
        return frame

    def delete_frame(self, index: int | None = None) -> bool:
        """
        Delete a frame.

        Args:
            index: Frame index to delete. If None, deletes current frame.

        Returns:
            True if deleted, False if only one frame left.
        """
        if len(self._frames) <= 1:
            return False  # Always keep at least one frame

        if index is None:
            index = self._current_index

        if 0 <= index < len(self._frames):
            del self._frames[index]

            # Adjust current index
            if self._current_index >= len(self._frames):
                self._current_index = len(self._frames) - 1

            return True
        return False

    def next_frame(self) -> Frame | None:
        """Go to next frame."""
        if len(self._frames) > 0:
            self._current_index = (self._current_index + 1) % len(self._frames)
            return self.current_frame
        return None

    def prev_frame(self) -> Frame | None:
        """Go to previous frame."""
        if len(self._frames) > 0:
            self._current_index = (self._current_index - 1) % len(self._frames)
            return self.current_frame
        return None

    def first_frame(self) -> Frame | None:
        """Go to first frame."""
        if len(self._frames) > 0:
            self._current_index = 0
            return self.current_frame
        return None

    def last_frame(self) -> Frame | None:
        """Go to last frame."""
        if len(self._frames) > 0:
            self._current_index = len(self._frames) - 1
            return self.current_frame
        return None

    def goto_frame(self, index: int) -> Frame | None:
        """Go to specific frame by index."""
        if 0 <= index < len(self._frames):
            self._current_index = index
            return self.current_frame
        return None

    def get_frame_list(self) -> list[str]:
        """Get list of frame descriptions."""
        return [f"{i+1}: {frame.filename}" for i, frame in enumerate(self._frames)]

    def move_frame(self, index: int, target_index: int) -> bool:
        """Move a frame to a new position."""
        if not (0 <= index < len(self._frames)):
            return False
        target_index = max(0, min(target_index, len(self._frames) - 1))
        frame = self._frames.pop(index)
        self._frames.insert(target_index, frame)
        if self._current_index == index:
            self._current_index = target_index
        elif index < self._current_index <= target_index:
            self._current_index -= 1
        elif target_index <= self._current_index < index:
            self._current_index += 1
        return True

    def reset_to_single_frame(self) -> Frame:
        """Delete all frames and create one empty frame."""
        self._frames = []
        self._current_index = -1
        self._next_id = 1
        return self.new_frame()
