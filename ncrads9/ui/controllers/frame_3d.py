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
The 3D frame: what it is seen from, and what is drawn over it.

The ray trace is in `frames/frame_3d.py`; this holds the view each frame is
seen from, puts the rendered cube where the display can find it, and turns
DS9's drag-to-rotate into azimuth and elevation.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from ...frames.frame_3d import (
    BACKGROUNDS,
    METHODS,
    View3D,
    corners,
    edges,
    extent,
    render,
    slice_outline,
)
from .base import Controller

#: How far a drag turns the cube: DS9 turns it a degree a pixel, which is
#: what makes a small drag useful and a big one a full turn.
DEGREES_PER_PIXEL = 1.0

#: What the 3D dialog's decorations look like to begin with (`3d.tcl:16`).
DEFAULTS: dict[str, object] = {
    "method": "mip",
    "background": "none",
    "highlite": True,
    "highlite_color": "cyan",
    "border": True,
    "border_color": "blue",
    "compass": False,
    "compass_color": "green",
}


class Frame3DController(Controller):
    """Owns each 3D frame's view and its decorations."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: Where each frame is seen from, by frame id. A frame that has
        #: never been turned is not in here and is seen face-on.
        self.views: dict[int, View3D] = {}
        #: How each is rendered and decorated, by frame id.
        self.settings: dict[int, dict] = {}
        #: Whether turning one 3D frame turns them all.
        self.locked = False
        self._dialog = None

    def connect(self) -> None:
        """Wire Frame -> 3D and Frame -> Match/Lock -> 3D."""
        self.menu.action_frame_3d_dialog.triggered.connect(lambda _checked=False: self.show_dialog())
        self.menu.action_match_3d.triggered.connect(lambda _checked=False: self.match())

    # -- which frames are 3D -----------------------------------------------------

    def is_three_d(self, frame=None) -> bool:
        """Whether a frame is a 3D frame holding a cube."""
        target = frame if frame is not None else self.frame
        if target is None or getattr(target, "frame_type", "base") != "3d":
            return False
        data = getattr(target, "image", None)
        return data is not None and getattr(data, "data", None) is not None and data.data.ndim == 3

    def cube(self, frame=None):
        """A 3D frame's whole cube, or None if it has none.

        The cube as it came off disk, not `image_data`, which by then holds
        one slice.
        """
        target = frame if frame is not None else self.frame
        if not self.is_three_d(target):
            return None
        return np.asarray(target.image.data)

    # -- the view ----------------------------------------------------------------

    def view(self, frame=None) -> View3D:
        """Where one frame is seen from."""
        target = frame if frame is not None else self.frame
        if target is None:
            return View3D()
        return self.views.get(target.frame_id, View3D())

    def setting(self, name: str, frame=None):
        """One of a frame's 3D settings."""
        target = frame if frame is not None else self.frame
        if target is None:
            return DEFAULTS.get(name)
        return self.settings.get(target.frame_id, {}).get(name, DEFAULTS.get(name))

    def set_setting(self, name: str, value, frame=None) -> None:
        """Change one of a frame's 3D settings and redraw."""
        target = frame if frame is not None else self.frame
        if target is None:
            return
        self.settings.setdefault(target.frame_id, {})[name] = value
        self.refresh()

    def set_view(
        self,
        azimuth: float | None = None,
        elevation: float | None = None,
        scale: float | None = None,
        propagate: bool = True,
    ) -> View3D:
        """Turn the current frame, and redraw it.

        Args:
            azimuth: Degrees, clamped to DS9's -180 to 180.
            elevation: Degrees, clamped to -90 to 90.
            scale: How much to stretch the third axis.
            propagate: Whether the lock may copy this to the other frames.

        Returns:
            The view now in force.
        """
        frame = self.frame
        if frame is None:
            return View3D()

        current = self.view(frame)
        wanted = View3D(
            azimuth=_wrap(current.azimuth if azimuth is None else azimuth),
            elevation=max(-90.0, min(90.0, current.elevation if elevation is None else elevation)),
            scale=max(0.01, current.scale if scale is None else scale),
        )
        self.views[frame.frame_id] = wanted
        self.refresh()
        if propagate and self.locked:
            self.propagate(wanted)
        return wanted

    def rotate_by(self, dx: float, dy: float) -> View3D:
        """Turn the cube by a drag, as DS9's 3D pointer mode does.

        Sideways is azimuth and up-and-down is elevation, which is the way
        round that makes a cube feel like an object rather than a dial.
        """
        current = self.view()
        return self.set_view(
            azimuth=current.azimuth + dx * DEGREES_PER_PIXEL,
            elevation=current.elevation - dy * DEGREES_PER_PIXEL,
        )

    def reset(self) -> View3D:
        """Back to face-on at the cube's own scale, DS9's Reset."""
        return self.set_view(azimuth=0.0, elevation=0.0, scale=1.0)

    # -- rendering ---------------------------------------------------------------

    def rendered(self, frame=None):
        """One frame's cube as the ray trace leaves it, or None.

        Returns data rather than a picture: the scale, the clip and the
        colormap follow, exactly as they do for a slice.
        """
        target = frame if frame is not None else self.frame
        cube = self.cube(target)
        if cube is None:
            return None
        method = str(self.setting("method", target))
        try:
            return render(cube, self.view(target), method)
        except ValueError:
            return None

    def refresh(self) -> None:
        """Redraw the frame, its decorations and the dialog."""
        if self.window.image_data is not None or self.frame is not None:
            self.window.display.display()
        self.draw_decorations()
        if self._dialog is not None:
            self._dialog.reload()

    # -- the border, the highlighted slice and the compass -----------------------------

    def decorations(self, frame=None) -> list:
        """The lines drawn over a 3D frame, in the rendered image's pixels.

        The border says where the cube is when most of it is transparent;
        the highlight says which slice the regions, the crosshair and the
        contours are on; the compass says which way the data axes point.

        Returns:
            `(points, colour, width)` for each polyline, empty for a frame
            that is not 3D.
        """
        target = frame if frame is not None else self.frame
        cube = self.cube(target)
        if cube is None:
            return []

        view = self.view(target)
        height, width = extent(cube.shape, view)

        # The ray trace centres the cube in the rendered image, so screen
        # coordinates about the centre become image coordinates by adding
        # the middle -- and y is flipped, images counting rows downwards.
        def to_image(point) -> tuple[float, float]:
            return ((width - 1) / 2.0 + point[0], (height - 1) / 2.0 - point[1])

        lines: list = []
        if self.setting("border", target):
            projected = corners(cube.shape, view)
            colour = str(self.setting("border_color", target))
            for first, second in edges():
                lines.append(([to_image(projected[first]), to_image(projected[second])], colour, 1))

        if self.setting("highlite", target):
            outline = slice_outline(cube.shape, view, int(getattr(target, "slice_index", 0)))
            points = [to_image(point) for point in outline]
            lines.append((points + points[:1], str(self.setting("highlite_color", target)), 2))

        if self.setting("compass", target):
            depth, rows, columns = cube.shape
            length = max(columns, rows, depth) / 3.0
            origin = np.array([-columns / 2.0, -rows / 2.0, -depth * view.scale / 2.0])
            colour = str(self.setting("compass_color", target))
            matrix = view.matrix.T
            for axis in range(3):
                arm = np.zeros(3)
                arm[axis] = length
                start = to_image(origin @ matrix)
                end = to_image((origin + arm) @ matrix)
                lines.append(([start, end], colour, 2))
        return lines

    def draw_decorations(self) -> None:
        """Put the decorations on the overlay, or clear them."""
        overlay = getattr(self.viewer, "contour_overlay", None)
        if overlay is None or not hasattr(overlay, "set_cube_lines"):
            return
        overlay.set_cube_lines(self.decorations())

    # -- across frames -------------------------------------------------------------

    def propagate(self, view: View3D) -> int:
        """Copy a view to every other 3D frame.

        Returns:
            How many were turned.
        """
        source = self.frame
        changed = 0
        for frame in self.frames.frames:
            if frame is source or not self.is_three_d(frame):
                continue
            self.views[frame.frame_id] = view
            changed += 1
        return changed

    def match(self) -> None:
        """Frame -> Match -> 3D: see every 3D frame from here."""
        if not self.is_three_d():
            self.status("The current frame is not a 3D frame", 2500)
            return
        changed = self.propagate(self.view())
        self.window.display.display()
        self.status(f"Matched {changed} 3D frame(s)", 2000)

    def set_locked(self, locked: bool) -> None:
        """Frame -> Lock -> 3D: keep the 3D frames' views together."""
        self.locked = bool(locked)
        if self.locked and self.is_three_d():
            self.propagate(self.view())
            self.window.display.display()
        self.status(f"3D lock: {'on' if locked else 'off'}")

    # -- the dialog ------------------------------------------------------------------

    def show_dialog(self):
        """DS9's 3D dialog."""
        from ..dialogs.frame_3d_dialog import Frame3DDialog

        if self._dialog is not None:
            self._dialog.reload()
            self._dialog.raise_()
            self._dialog.activateWindow()
            return self._dialog

        dialog = Frame3DDialog(self, self.window)
        dialog.finished.connect(lambda _result: setattr(self, "_dialog", None))
        self._dialog = dialog
        dialog.show()
        return dialog

    def sync(self) -> None:
        """Follow a frame change, since the view is per frame."""
        if self._dialog is not None:
            self._dialog.reload()

    # -- what XPA sets ------------------------------------------------------------------

    def set_method(self, method: str) -> bool:
        """`3d method mip|aip`."""
        if method not in METHODS:
            return False
        self.set_setting("method", method)
        return True

    def set_background(self, kind: str) -> bool:
        """`3d background none|azimuth|elevation`."""
        if kind not in BACKGROUNDS:
            return False
        self.set_setting("background", kind)
        return True

    def describe(self) -> str:
        """What `xpaget 3d` answers: the view, one value a line."""
        view = self.view()
        return "\n".join(
            [
                f"view {view.azimuth:g} {view.elevation:g}",
                f"scale {view.scale:g}",
                f"method {self.setting('method')}",
                f"background {self.setting('background')}",
            ]
        )

    def state(self, frame=None) -> dict:
        """A frame's whole 3D state, for the backup."""
        view = self.view(frame)
        settings = dict(DEFAULTS)
        target = frame if frame is not None else self.frame
        if target is not None:
            settings.update(self.settings.get(target.frame_id, {}))
        return {
            "azimuth": view.azimuth,
            "elevation": view.elevation,
            "scale": view.scale,
            **settings,
        }

    def apply_state(self, state: dict, frame=None) -> None:
        """Put a frame's 3D state back, as a restore does."""
        target = frame if frame is not None else self.frame
        if target is None or not isinstance(state, dict):
            return
        self.views[target.frame_id] = View3D(
            azimuth=float(state.get("azimuth", 0.0)),
            elevation=float(state.get("elevation", 0.0)),
            scale=float(state.get("scale", 1.0)),
        )
        kept = {name: state[name] for name in DEFAULTS if name in state}
        self.settings[target.frame_id] = kept


def _wrap(degrees: float) -> float:
    """An azimuth in DS9's -180 to 180, however far it was dragged."""
    turned = (float(degrees) + 180.0) % 360.0 - 180.0
    return -180.0 if turned == 180.0 else turned


def replace_view(view: View3D, **changes) -> View3D:
    """One view with some of its angles changed."""
    return replace(view, **changes)
