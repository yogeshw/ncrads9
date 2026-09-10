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
Where the automatic backup lives and when it is written.

DS9 writes a full backup to `~/.ds9.auto` every five minutes, deletes it
when it exits cleanly, and offers to restore it on the next start if it is
still there -- which it only is after a crash (`autosave.tcl`). Ours does
the same, with the interval and the switch as preferences.

The timer belongs to the controller; what is here is the paths and the
policy, so both can be tested without waiting five minutes.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import os
from pathlib import Path

from . import backup

#: What DS9 calls it, adjusted for this application's name.
FILENAME = ".ncrads9.auto"

#: How often DS9 writes one, in minutes (`pds9(autosave,interval)`).
DEFAULT_INTERVAL_MINUTES = 5

#: Whether it is on unless a preference says otherwise (`pds9(autosave)`).
DEFAULT_ENABLED = True


def home() -> Path:
    """Where the automatic backup goes.

    `$HOME`, as DS9's `GetEnvHome` has it, so a test can put it somewhere
    else without writing to the real one.
    """
    return Path(os.environ.get("HOME", str(Path.home())))


def path() -> Path:
    """The automatic backup's file."""
    return home() / FILENAME


def exists() -> bool:
    """Whether there is one to recover.

    Both the file and its directory, as DS9 checks: a file without its
    directory is a backup whose write did not finish.
    """
    target = path()
    return target.is_file() and backup.sidecar(target).is_dir()


def remove() -> None:
    """Delete it, which is what a clean exit does."""
    backup.remove(path())


def interval_ms(minutes: float | None = None) -> int:
    """The timer's interval in milliseconds."""
    chosen = DEFAULT_INTERVAL_MINUTES if minutes is None else float(minutes)
    return max(1, int(chosen * 60_000))
