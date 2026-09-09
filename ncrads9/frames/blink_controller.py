# NCRADS9 - NCRA DS9 Viewer
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
Frame sequencing for DS9's Blink and Fade modes.

This decides *which frame comes next*; it does not own a timer. The UI drives
it from a QTimer, so the sequencing logic stays free of Qt and is directly
unit-testable.

Only the frames the user has left visible take part -- DS9's Show/Hide Frames
removes a frame from the blink cycle without deleting it -- so the caller
passes the active frame indices on every step rather than the controller
caching a stale list.

Before M1 this was a `BlinkController` that polled a wall-clock `update()` and
modelled frame ranges, and was never used; the sequencing actually driving the
UI was inline in `MainWindow._update_blink`.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

#: DS9's blink intervals, in milliseconds (Frame Parameters -> Blink Interval).
BLINK_INTERVALS_MS: tuple[int, ...] = (125, 250, 500, 1000, 2000, 4000, 8000, 16000)

#: DS9's fade intervals, in milliseconds.
FADE_INTERVALS_MS: tuple[int, ...] = (1000, 2000, 4000, 8000)

#: DS9's default blink and fade intervals.
DEFAULT_BLINK_INTERVAL_MS = 500
DEFAULT_FADE_INTERVAL_MS = 1000


class BlinkOrder(Enum):
    """Direction the cycle runs in."""

    FORWARD = "forward"
    REVERSE = "reverse"
    PINGPONG = "pingpong"


@dataclass
class BlinkController:
    """Chooses the next frame in a blink or fade cycle.

    Attributes:
        order: Direction of travel through the active frames.
        interval_ms: Milliseconds between steps; the caller applies this to its
            timer.
    """

    order: BlinkOrder = BlinkOrder.FORWARD
    interval_ms: int = DEFAULT_BLINK_INTERVAL_MS

    #: Only meaningful for PINGPONG: which way the cycle is currently going.
    _descending: bool = False

    def set_interval(self, interval_ms: int) -> int:
        """Set the step interval, clamped to at least 1 ms. Returns the value."""
        self.interval_ms = max(1, int(interval_ms))
        return self.interval_ms

    def reset(self) -> None:
        """Forget any ping-pong direction state."""
        self._descending = False

    def next_index(self, active: Sequence[int], current: int) -> int | None:
        """Return the next frame index to show, or None if there is nothing to do.

        Args:
            active: Indices of the frames taking part, in display order.
            current: The frame index showing now. It need not be in `active`;
                if it is not -- the user just hid the visible frame -- the
                cycle restarts at the first active frame.

        Returns:
            The next index, or None when fewer than two frames are active
            (a one-frame blink has nothing to alternate between).
        """
        if len(active) < 2:
            return None

        if current not in active:
            return active[0]

        position = active.index(current)

        if self.order is BlinkOrder.FORWARD:
            return active[(position + 1) % len(active)]

        if self.order is BlinkOrder.REVERSE:
            return active[(position - 1) % len(active)]

        # Ping-pong: walk to one end, turn around, walk back.
        if self._descending:
            if position == 0:
                self._descending = False
                return active[1]
            return active[position - 1]
        if position == len(active) - 1:
            self._descending = True
            return active[position - 1]
        return active[position + 1]
