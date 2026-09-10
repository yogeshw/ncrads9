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
The backup file: a whole session, saved and read back.

DS9's backup is a Tcl script that rebuilds the session by `eval`ing itself
(`backup.tcl`). We cannot eval Tcl, and would not want to execute a data
file as code even if we could -- a backup arrives by email as readily as any
other file. So ours is JSON, beside a directory of the same name plus
`.dir`, which is where DS9 puts a backup's auxiliary files too:

    session.bck        the state, as JSON
    session.bck.dir/   the data of any frame with no file behind it

A frame loaded from a file is stored as the file's name and the extension
on screen; only a frame whose data came from somewhere else -- an array
over XPA, a mosaic assembled in memory -- has its pixels written out. That
is what keeps a backup of a night's work small.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray

#: What the file says it is, so a JSON file that is not one of ours is
#: refused rather than half-read.
FORMAT = "ncrads9-backup"

#: The format's version. Read a file of this version or older; refuse a
#: newer one, as DS9 refuses a newer backup than itself.
VERSION = 1

#: What the auxiliary directory is called, DS9's `${fn}.dir`.
SIDECAR_SUFFIX = ".dir"

#: What DS9 calls a backup on disk, and what ours are called.
FILE_FILTER = "Backup files (*.bck);;All files (*)"


class BackupError(Exception):
    """A backup that cannot be read, for the reason given."""


def sidecar(path: str | Path) -> Path:
    """Where a backup's auxiliary files live."""
    return Path(str(path) + SIDECAR_SUFFIX)


def save(
    path: str | Path,
    state: dict[str, Any],
    arrays: dict[str, NDArray[np.floating]] | None = None,
) -> Path:
    """Write a session out.

    Args:
        path: The backup file. Its `.dir` is replaced if it exists, and any
            parent directory that does not exist yet is created -- saving
            into a folder that is not there is part of what was asked for.
        state: The session, as plain JSON-able data.
        arrays: Data with no file behind it, by the key the state refers to
            it by. Each is written as a single-image FITS file in the
            `.dir`, which is what makes it readable by anything else.

    Returns:
        The path written.

    Raises:
        BackupError: If the file or its directory cannot be written.
    """
    target = Path(path)
    directory = sidecar(target)
    document = {"format": FORMAT, "version": VERSION, **state}

    try:
        # The directory is made whether or not anything goes in it, as DS9
        # makes its own (`BackupPreamble`): a backup missing its directory is
        # a backup whose write did not finish, and the automatic-backup
        # recovery reads it that way.
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for key, data in (arrays or {}).items():
            fits.PrimaryHDU(data=np.asarray(data)).writeto(directory / f"{key}.fits", overwrite=True)
        target.write_text(json.dumps(document, indent=2, default=_plain), encoding="utf-8")
    except OSError as exc:
        raise BackupError(f"cannot write {target.name}: {exc}") from exc
    return target


def load(path: str | Path) -> tuple[dict[str, Any], dict[str, NDArray[np.floating]]]:
    """Read a session back.

    Args:
        path: The backup file.

    Returns:
        (state, arrays), the arrays keyed as the state refers to them.

    Raises:
        BackupError: If the file is missing, is not a backup, or was
            written by a newer version than this one understands.
    """
    target = Path(path)
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BackupError(f"cannot read {target.name}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BackupError(f"{target.name} is not a backup file: {exc}") from exc

    if not isinstance(document, dict) or document.get("format") != FORMAT:
        raise BackupError(f"{target.name} is not an NCRADS9 backup file")
    version = int(document.get("version", 0))
    if version > VERSION:
        raise BackupError(
            f"{target.name} was written by a newer version (backup {version}, this reads {VERSION})"
        )

    arrays: dict[str, NDArray[np.floating]] = {}
    directory = sidecar(target)
    if directory.is_dir():
        for saved in sorted(directory.glob("*.fits")):
            try:
                with fits.open(saved, memmap=False) as hdus:
                    data = hdus[0].data
            except OSError:
                continue
            if data is not None:
                arrays[saved.stem] = np.asarray(data)

    state = {key: value for key, value in document.items() if key not in ("format", "version")}
    state["version"] = version
    return (state, arrays)


def remove(path: str | Path) -> None:
    """Delete a backup and its directory, as DS9's autosave does."""
    target = Path(path)
    target.unlink(missing_ok=True)
    shutil.rmtree(sidecar(target), ignore_errors=True)


def _plain(value):
    """Anything JSON cannot write by itself: numpy scalars, paths, enums."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    return str(value)
