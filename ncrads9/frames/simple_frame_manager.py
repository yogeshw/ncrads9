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
Simple frame management for multiple images.

Author: Yogesh Wadadekar
"""

from typing import Optional, List
from dataclasses import dataclass
import numpy as np
from pathlib import Path


@dataclass
class Frame:
    """Container for a single frame (image + metadata)."""
    
    frame_id: int
    filepath: Optional[Path] = None
    image_data: Optional[np.ndarray] = None
    header: Optional[dict] = None
    wcs_handler: Optional[object] = None
    regions: List = None
    
    def __post_init__(self):
        if self.regions is None:
            self.regions = []
    
    @property
    def has_data(self) -> bool:
        """Check if frame has image data."""
        return self.image_data is not None
    
    @property
    def filename(self) -> str:
        """Get filename or 'Empty'."""
        if self.filepath:
            return self.filepath.name
        return f"Frame {self.frame_id}"


class FrameManager:
    """Manages multiple image frames."""
    
    def __init__(self):
        self._frames: List[Frame] = []
        self._current_index: int = -1
        self._next_id: int = 1
        
        # Create initial empty frame
        self.new_frame()
    
    @property
    def current_frame(self) -> Optional[Frame]:
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
    
    def new_frame(self) -> Frame:
        """Create a new empty frame."""
        frame = Frame(frame_id=self._next_id)
        self._frames.append(frame)
        self._current_index = len(self._frames) - 1
        self._next_id += 1
        return frame
    
    def delete_frame(self, index: Optional[int] = None) -> bool:
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
    
    def next_frame(self) -> Optional[Frame]:
        """Go to next frame."""
        if len(self._frames) > 0:
            self._current_index = (self._current_index + 1) % len(self._frames)
            return self.current_frame
        return None
    
    def prev_frame(self) -> Optional[Frame]:
        """Go to previous frame."""
        if len(self._frames) > 0:
            self._current_index = (self._current_index - 1) % len(self._frames)
            return self.current_frame
        return None
    
    def first_frame(self) -> Optional[Frame]:
        """Go to first frame."""
        if len(self._frames) > 0:
            self._current_index = 0
            return self.current_frame
        return None
    
    def last_frame(self) -> Optional[Frame]:
        """Go to last frame."""
        if len(self._frames) > 0:
            self._current_index = len(self._frames) - 1
            return self.current_frame
        return None
    
    def goto_frame(self, index: int) -> Optional[Frame]:
        """Go to specific frame by index."""
        if 0 <= index < len(self._frames):
            self._current_index = index
            return self.current_frame
        return None
    
    def get_frame_list(self) -> List[str]:
        """Get list of frame descriptions."""
        return [f"{i+1}: {frame.filename}" for i, frame in enumerate(self._frames)]
