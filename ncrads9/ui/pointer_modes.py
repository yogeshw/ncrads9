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
What a drag on the image does: DS9's pointer modes.

DS9's Edit menu chooses between them -- pointer, region, crosshair,
colorbar, pan, zoom, rotate, crop, catalog, footprint, examine, 3d,
illustrate -- and the whole of the mouse's meaning changes with the choice.
Only `region` and `colorbar` did anything here before; the rest reported the
milestone they were waiting for.

Each mode is a small handler with press, move and release, acting on a
target it is given rather than on a window it reaches into. That is what
lets them be tested against a recording target instead of against a
displayed image, and it is why the geometry below is arithmetic rather than
Qt.

Two of them draw while dragging -- crop and zoom rubber-band a rectangle --
and `rubber_band` is how the overlay knows to paint it.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math
from typing import Protocol

#: DS9's examine zoom factor (`pexamine(zoom)` in `examine.tcl:12`).
EXAMINE_ZOOM = 4.0

#: How much one click of DS9's zoom mode zooms.
ZOOM_STEP = 2.0

#: How far a drag must travel to count as a drag rather than a click, in
#: image pixels. Below it, a crop or zoom box is treated as a click.
MINIMUM_DRAG = 3.0

#: How many pixels of horizontal drag make a full turn in rotate mode.
ROTATE_PIXELS_PER_TURN = 400.0


class PointerTarget(Protocol):
    """What a pointer mode can ask the application to do.

    A protocol rather than the controller itself, so a handler can be
    driven by a recording double in a test -- which is the only way to
    check that a drag means what it should without a display.
    """

    def pan_to(self, x: float, y: float) -> None:
        """Centre the view on an image position."""

    def pan_by(self, dx: float, dy: float) -> None:
        """Shift the view by an offset in image pixels."""

    def zoom_by(self, factor: float, x: float, y: float) -> None:
        """Zoom about an image position."""

    def rotate_by(self, degrees: float) -> None:
        """Turn the view."""

    def crop_to(self, x0: float, y0: float, x1: float, y1: float) -> None:
        """Display only an image rectangle, as DS9's crop does."""

    def zoom_to(self, x0: float, y0: float, x1: float, y1: float) -> None:
        """Zoom and pan so an image rectangle fills the viewport."""

    def examine_at(self, x: float, y: float, zoom: float) -> None:
        """Open a zoomed view of one position."""

    def move_crosshair(self, x: float, y: float) -> None:
        """Put the crosshair at an image position."""

    def pick_at(self, x: float, y: float) -> bool:
        """Select whatever overlay symbol is at a position."""


class PointerHandler:
    """One pointer mode.

    Args:
        target: What to act on.
    """

    #: The mode's name, as the Edit menu spells it.
    name = "none"

    #: Whether a drag in this mode draws a rectangle.
    draws_band = False

    def __init__(self, target: PointerTarget) -> None:
        self.target = target
        self._start: tuple[float, float] | None = None
        self._last: tuple[float, float] | None = None

    @property
    def dragging(self) -> bool:
        """Whether a drag is in progress."""
        return self._start is not None

    @property
    def rubber_band(self) -> tuple[float, float, float, float] | None:
        """The rectangle being dragged, in image pixels, or None."""
        if not self.draws_band or self._start is None or self._last is None:
            return None
        return (*self._start, *self._last)

    def press(self, x: float, y: float, button: str = "left") -> bool:
        """Handle a press. Returns whether the mode used it."""
        self._start = (x, y)
        self._last = (x, y)
        return True

    def move(self, x: float, y: float) -> bool:
        """Handle a drag. Returns whether the mode used it."""
        if self._start is None:
            return False
        self._last = (x, y)
        return True

    def release(self, x: float, y: float) -> bool:
        """Handle a release. Returns whether the mode used it."""
        used = self._start is not None
        self._start = None
        self._last = None
        return used

    def _travelled(self, x: float, y: float) -> float:
        """How far the drag has gone from where it started."""
        if self._start is None:
            return 0.0
        return math.hypot(x - self._start[0], y - self._start[1])


class PanHandler(PointerHandler):
    """DS9's pan mode: a click centres the view, a drag shifts it."""

    name = "pan"

    def move(self, x: float, y: float) -> bool:
        """Shift the view by however far the cursor moved."""
        if self._last is None:
            return False
        # The image moves with the cursor, so the *view* moves the other
        # way -- getting this backwards is the classic reversed-pan bug.
        self.target.pan_by(self._last[0] - x, self._last[1] - y)
        self._last = (x, y)
        return True

    def release(self, x: float, y: float) -> bool:
        """A click with no drag centres the view on the point."""
        if self._start is None:
            return False
        if self._travelled(x, y) < MINIMUM_DRAG:
            self.target.pan_to(x, y)
        self._start = None
        self._last = None
        return True


class ZoomHandler(PointerHandler):
    """DS9's zoom mode: left zooms in, right zooms out, a drag boxes a view."""

    name = "zoom"
    draws_band = True

    def __init__(self, target: PointerTarget) -> None:
        super().__init__(target)
        self._button = "left"

    def press(self, x: float, y: float, button: str = "left") -> bool:
        self._button = button
        return super().press(x, y, button)

    def release(self, x: float, y: float) -> bool:
        """Zoom to the dragged box, or by a step about the clicked point."""
        if self._start is None:
            return False
        start = self._start
        travelled = self._travelled(x, y)
        self._start = None
        self._last = None

        if travelled >= MINIMUM_DRAG:
            # A box means "show me this": centre it and zoom to fit it.
            # A zoom box zooms; it does not crop. DS9 keeps the two apart,
            # and cropping from the zoom mode would leave no way back to the
            # rest of the data.
            self.target.zoom_to(start[0], start[1], x, y)
            return True

        factor = ZOOM_STEP if self._button == "left" else 1.0 / ZOOM_STEP
        self.target.zoom_by(factor, x, y)
        return True


class RotateHandler(PointerHandler):
    """DS9's rotate mode: a horizontal drag turns the view."""

    name = "rotate"

    def move(self, x: float, y: float) -> bool:
        """Turn by however far the cursor moved sideways."""
        if self._last is None:
            return False
        degrees = (x - self._last[0]) / ROTATE_PIXELS_PER_TURN * 360.0
        self.target.rotate_by(degrees)
        self._last = (x, y)
        return True


class CropHandler(PointerHandler):
    """DS9's crop mode: rubber-band a rectangle and crop to it."""

    name = "crop"
    draws_band = True

    def release(self, x: float, y: float) -> bool:
        """Crop to the box, ignoring a box too small to be meant."""
        if self._start is None:
            return False
        start = self._start
        travelled = self._travelled(x, y)
        self._start = None
        self._last = None
        if travelled < MINIMUM_DRAG:
            # A click is not a crop; cropping to nothing leaves no way back.
            return True
        self.target.crop_to(start[0], start[1], x, y)
        return True


class ExamineHandler(PointerHandler):
    """DS9's examine mode: a click opens a zoomed view of that spot."""

    name = "examine"

    def __init__(self, target: PointerTarget, zoom: float = EXAMINE_ZOOM) -> None:
        super().__init__(target)
        self.zoom = zoom

    def release(self, x: float, y: float) -> bool:
        if self._start is None:
            return False
        self._start = None
        self._last = None
        self.target.examine_at(x, y, self.zoom)
        return True


class CrosshairHandler(PointerHandler):
    """DS9's crosshair mode: a click or drag moves the crosshair."""

    name = "crosshair"

    def press(self, x: float, y: float, button: str = "left") -> bool:
        super().press(x, y, button)
        self.target.move_crosshair(x, y)
        return True

    def move(self, x: float, y: float) -> bool:
        if self._start is None:
            return False
        self.target.move_crosshair(x, y)
        self._last = (x, y)
        return True


class PickHandler(PointerHandler):
    """DS9's catalog and footprint modes: a click selects a symbol's row."""

    def __init__(self, target: PointerTarget, name: str = "catalog") -> None:
        super().__init__(target)
        self.name = name

    def press(self, x: float, y: float, button: str = "left") -> bool:
        super().press(x, y, button)
        # Whether a symbol was under the cursor decides if the click is
        # ours; a miss should still reach whatever is underneath.
        return self.target.pick_at(x, y)


#: The handler each mode uses. `none`, `region`, `colorbar`, `3d` and
#: `illustrate` are not here: the first three are handled elsewhere and the
#: last two arrive with their own milestones.
HANDLERS: dict[str, type[PointerHandler]] = {
    "pan": PanHandler,
    "zoom": ZoomHandler,
    "rotate": RotateHandler,
    "crop": CropHandler,
    "examine": ExamineHandler,
    "crosshair": CrosshairHandler,
}


def handler_for(mode: str, target: PointerTarget) -> PointerHandler | None:
    """The handler one mode needs, or None if it has none.

    Args:
        mode: The mode's name, as the Edit menu spells it.
        target: What the handler acts on.
    """
    if mode in ("catalog", "footprint"):
        return PickHandler(target, mode)
    kind = HANDLERS.get(mode)
    return kind(target) if kind is not None else None
