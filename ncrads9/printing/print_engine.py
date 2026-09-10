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
Where a print goes: a file, or a command's standard input.

DS9's Print dialog offers a printer with a command (`lp` by default) or a
file with a name (`print.tcl:292`). The PostScript is the same either way,
which is why this is a small module over `postscript.py` rather than part
of it.

PDF is ours rather than DS9's: DS9 prints PostScript, and a modern desktop
would rather have a PDF. It is written by the same driver's page geometry
through Pillow, so the page is laid out identically.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from .page_setup import POINTS_PER_INCH, PageSetup
from .postscript import PostScriptDocument, PostScriptError


class Destination(Enum):
    """Where the print goes."""

    PRINTER = "printer"
    FILE = "file"


class OutputFormat(Enum):
    """What is written."""

    POSTSCRIPT = "ps"
    EPS = "eps"
    PDF = "pdf"


#: What DS9 pipes a print into by default (`ps(cmd)`, `print.tcl:18`).
DEFAULT_COMMAND = "lp"

#: What DS9 calls the file (`ps(filename)`).
DEFAULT_FILENAME = "ncrads9.ps"

#: How long to give the print command before giving up, in seconds.
COMMAND_TIMEOUT = 60


@dataclass
class PrintSettings:
    """Everything DS9's Print dialog holds.

    Attributes:
        destination: A printer or a file.
        command: The command a printer print is piped into.
        filename: The file a file print is written to.
        level: PostScript level 1, 2 or 3.
        color_model: `rgb`, `cmyk` or `gray`.
        resolution: Pixels per inch.
        output_format: PostScript, EPS or PDF.
        page: The page geometry, from Page Setup.
    """

    destination: Destination = Destination.PRINTER
    command: str = DEFAULT_COMMAND
    filename: str = DEFAULT_FILENAME
    level: int = 2
    color_model: str = "rgb"
    resolution: int = 150
    output_format: OutputFormat = OutputFormat.POSTSCRIPT
    page: PageSetup = field(default_factory=PageSetup)


class PrintError(Exception):
    """A print that did not happen, for the reason given."""


def document(settings: PrintSettings, title: str = "NCRADS9") -> PostScriptDocument:
    """The PostScript document one set of settings describes."""
    return PostScriptDocument(
        page=settings.page,
        level=settings.level,
        color_model=settings.color_model,
        resolution=settings.resolution,
        title=title,
        encapsulated=settings.output_format is OutputFormat.EPS,
    )


def to_file(
    path: str | Path,
    rgb: NDArray[np.uint8],
    settings: PrintSettings,
    title: str = "NCRADS9",
) -> Path:
    """Write a print to a file.

    Args:
        path: Where to write it.
        rgb: The rendered image.
        settings: What to write.
        title: The document's title.

    Returns:
        The path written.

    Raises:
        PrintError: If it cannot be written.
    """
    target = Path(path)
    try:
        if settings.output_format is OutputFormat.PDF:
            _write_pdf(target, rgb, settings)
        else:
            document(settings, title).write(target, rgb)
    except (OSError, PostScriptError, ValueError) as exc:
        raise PrintError(str(exc)) from exc
    return target


def to_command(
    rgb: NDArray[np.uint8],
    settings: PrintSettings,
    title: str = "NCRADS9",
    runner=None,
) -> None:
    """Send a print to a command's standard input, as DS9's `lp` does.

    Args:
        rgb: The rendered image.
        settings: What to print, and what command to print it with.
        title: The document's title.
        runner: What to run the command with. Defaults to
            `subprocess.run`; a test passes its own and never spawns
            anything.

    Raises:
        PrintError: If there is no command, or it fails.
    """
    command = (settings.command or "").strip()
    if not command:
        raise PrintError("no print command is set")

    text = document(settings, title).render(rgb)
    run = runner if runner is not None else subprocess.run
    try:
        result = run(
            command.split(),
            input=text.encode("ascii"),
            capture_output=True,
            timeout=COMMAND_TIMEOUT,
        )
    except FileNotFoundError as exc:
        raise PrintError(f"{command.split()[0]} is not on the path") from exc
    except OSError as exc:
        raise PrintError(str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise PrintError(f"{command} did not finish within {COMMAND_TIMEOUT}s") from exc

    code = getattr(result, "returncode", 0)
    if code:
        stderr = getattr(result, "stderr", b"") or b""
        detail = stderr.decode("utf-8", "replace").strip() if isinstance(stderr, bytes) else str(stderr)
        raise PrintError(f"{command} failed: {detail or f'exit {code}'}")


def _write_pdf(path: Path, rgb: NDArray[np.uint8], settings: PrintSettings) -> None:
    """Write a PDF page with the image where the PostScript would put it."""
    from PIL import Image

    from ..io.pdf_writer import PDFWriter

    array = np.asarray(rgb, dtype=np.uint8)
    if array.ndim == 2:
        array = np.repeat(array[:, :, None], 3, axis=2)
    height, width = array.shape[:2]

    # The page in pixels at the print resolution, so the PDF has the same
    # geometry as the PostScript rather than its own idea of one.
    scale = settings.resolution / POINTS_PER_INCH
    page_width, page_height = settings.page.size_points
    canvas = Image.new("RGB", (max(1, int(page_width * scale)), max(1, int(page_height * scale))), "white")

    x, y, box_width, box_height = settings.page.place(width, height)
    placed = Image.fromarray(array[:, :, :3]).resize(
        (max(1, int(box_width * scale)), max(1, int(box_height * scale))), Image.Resampling.NEAREST
    )
    # PostScript counts y from the bottom and a picture from the top.
    top = canvas.height - int((y + box_height) * scale)
    canvas.paste(placed, (int(x * scale), top))

    writer = PDFWriter(path)
    # The page is already laid out and already bytes, so nothing is
    # normalised on the way through.
    writer.add_page(np.asarray(canvas), normalize=False)
    writer.write(dpi=settings.resolution, title="NCRADS9")
