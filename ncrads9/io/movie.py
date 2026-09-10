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
DS9's Create Movie: a run of rendered images, written as one file.

DS9 offers an animated GIF or an MPEG, over the frames or over a cube's
slices, with a hard cut between them or a fade (`movie.tcl`). The GIF is
written by Pillow, which is already a dependency; the MPEG needs ffmpeg,
which is not, so its absence is reported rather than assumed.

The fade is made here rather than by the writer: it is extra images, blended
between each pair, and both formats then treat them as ordinary frames.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .gif_writer import GIFWriter
from .mpeg_writer import MPEGWriter

#: The two kinds of file DS9's dialog offers.
TYPES: tuple[str, ...] = ("gif", "mpeg")

#: What the movie runs over. `3d` needs the 3D frame of M9-21.
ACTIONS: tuple[str, ...] = ("frame", "slice", "3d")

#: How one image gives way to the next.
TRANSITIONS: tuple[str, ...] = ("blink", "fade")

#: DS9's default delay, in hundredths of a second (`movie.tcl`).
DEFAULT_DELAY = 10

#: How many blended images a fade puts between two frames.
FADE_STEPS = 8


class MovieError(Exception):
    """A movie that cannot be written, for the reason given."""


def fade_between(
    first: NDArray[np.uint8],
    second: NDArray[np.uint8],
    steps: int = FADE_STEPS,
) -> list[NDArray[np.uint8]]:
    """The images that carry one frame into the next.

    Args:
        first: Where the fade starts.
        second: Where it ends.
        steps: How many images to put between them, the last being the
            second frame itself.

    Returns:
        The blended images. Empty if the two are not the same shape, since
        there is nothing sensible to blend.
    """
    if first.shape != second.shape:
        return []
    blended = []
    for step in range(1, max(1, steps) + 1):
        weight = step / max(1, steps)
        mixed = first.astype(np.float32) * (1.0 - weight) + second.astype(np.float32) * weight
        blended.append(mixed.astype(np.uint8))
    return blended


def sequence(
    images: Sequence[NDArray[np.uint8]],
    transition: str = "blink",
) -> list[NDArray[np.uint8]]:
    """The whole run of images a movie is made of.

    Args:
        images: One rendered image per frame or slice.
        transition: `blink` for a hard cut, `fade` to blend between them.

    Returns:
        The images in order.
    """
    frames = [np.asarray(image, dtype=np.uint8) for image in images]
    if transition != "fade" or len(frames) < 2:
        return frames

    run = [frames[0]]
    for index in range(len(frames) - 1):
        run.extend(fade_between(frames[index], frames[index + 1]))
    # Back to the first, so the loop does not jump.
    run.extend(fade_between(frames[-1], frames[0]))
    return run


def have_ffmpeg() -> bool:
    """Whether an MPEG can be written at all."""
    return shutil.which("ffmpeg") is not None


def write(
    path: str | Path,
    images: Sequence[NDArray[np.uint8]],
    movie_type: str = "gif",
    transition: str = "blink",
    delay: int = DEFAULT_DELAY,
) -> Path:
    """Write a movie.

    Args:
        path: The file to write.
        images: One rendered image per frame or slice, in order.
        movie_type: `gif` or `mpeg`.
        transition: `blink` or `fade`.
        delay: How long each image is shown, in hundredths of a second, as
            DS9's dialog asks. The MPEG's frame rate comes from the same
            number, since an MPEG has no per-frame delay.

    Returns:
        The path written.

    Raises:
        MovieError: If there is nothing to write, the type is not one of
            DS9's two, or an MPEG is asked for without ffmpeg.
    """
    if movie_type not in TYPES:
        raise MovieError(f"{movie_type} is not a kind of movie DS9 makes")

    run = sequence(images, transition)
    if not run:
        raise MovieError("there is nothing to make a movie of")

    hundredths = max(1, int(delay))
    target = Path(path)

    if movie_type == "gif":
        writer = GIFWriter(target)
        writer.add_frames(run, normalize=False)
        writer.write(duration=hundredths * 10)
        return target

    if not have_ffmpeg():
        raise MovieError("an MPEG needs ffmpeg on the path; an animated GIF does not")
    writer_mpeg = MPEGWriter(target)
    writer_mpeg.add_frames(run, normalize=False)
    writer_mpeg.write(fps=max(1, int(round(100 / hundredths))))
    return target


def frames_of(rendered: Sequence[NDArray[Any]]) -> list[NDArray[np.uint8]]:
    """Rendered images made the same size, so a writer will take them.

    Two frames of different files are different sizes, and neither writer
    will accept a run that changes shape; each is padded into the largest
    with black rather than the movie being refused.
    """
    images = [np.asarray(image) for image in rendered if image is not None]
    if not images:
        return []
    height = max(image.shape[0] for image in images)
    width = max(image.shape[1] for image in images)

    padded = []
    for image in images:
        if image.ndim == 2:
            image = np.repeat(image[:, :, None], 3, axis=2)
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        canvas[: image.shape[0], : image.shape[1]] = image[:, :, :3]
        padded.append(canvas)
    return padded
