# NCRADS9 - NCRA DS9 Visualization Tool
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
MPEG video writer for NCRADS9.

Author: Yogesh Wadadekar
"""

import subprocess
from pathlib import Path
from typing import Any, Optional, Sequence, Union

import numpy as np
from numpy.typing import NDArray


class MPEGWriter:
    """Writer for MPEG video files using ffmpeg."""

    def __init__(self, filepath: Union[str, Path]) -> None:
        """
        Initialize MPEG writer.

        Args:
            filepath: Path for the output video file.
        """
        self.filepath = Path(filepath)
        self._frames: list[NDArray[Any]] = []
        self._width: Optional[int] = None
        self._height: Optional[int] = None

    def add_frame(
        self,
        data: NDArray[Any],
        normalize: bool = True,
    ) -> None:
        """
        Add a frame to the video.

        Args:
            data: Image data as numpy array (H, W) or (H, W, 3).
            normalize: Whether to normalize data to 0-255 range.
        """
        if normalize:
            data = self._normalize(data)

        if data.ndim == 2:
            data = np.stack([data, data, data], axis=-1)

        data = data.astype(np.uint8)

        if self._width is None:
            self._height, self._width = data.shape[:2]

        self._frames.append(data)

    def add_frames(
        self,
        frames: Sequence[NDArray[Any]],
        normalize: bool = True,
    ) -> None:
        """
        Add multiple frames at once.

        Args:
            frames: Sequence of image arrays.
            normalize: Whether to normalize data.
        """
        for frame in frames:
            self.add_frame(frame, normalize=normalize)

    def write(
        self,
        fps: int = 30,
        codec: str = "libx264",
        crf: int = 23,
        preset: str = "medium",
    ) -> None:
        """
        Write the video to disk using ffmpeg.

        Args:
            fps: Frames per second.
            codec: Video codec.
            crf: Constant Rate Factor (quality, lower = better).
            preset: Encoding speed preset.
        """
        if not self._frames:
            raise ValueError("No frames to write")

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{self._width}x{self._height}",
            "-pix_fmt", "rgb24",
            "-r", str(fps),
            "-i", "-",
            "-c:v", codec,
            "-crf", str(crf),
            "-preset", preset,
            "-pix_fmt", "yuv420p",
            str(self.filepath),
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        for frame in self._frames:
            proc.stdin.write(frame.tobytes())  # type: ignore

        proc.stdin.close()  # type: ignore
        proc.wait()

        if proc.returncode != 0:
            stderr = proc.stderr.read().decode()  # type: ignore
            raise RuntimeError(f"ffmpeg failed: {stderr}")

    def clear(self) -> None:
        """Clear all frames."""
        self._frames.clear()
        self._width = None
        self._height = None

    def _normalize(self, data: NDArray[Any]) -> NDArray[Any]:
        """Normalize data to 0-255 range."""
        data = np.asarray(data, dtype=np.float64)
        data_min = np.nanmin(data)
        data_max = np.nanmax(data)
        if data_max > data_min:
            data = (data - data_min) / (data_max - data_min) * 255
        return data
