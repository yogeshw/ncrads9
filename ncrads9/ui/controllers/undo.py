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
Edit -> Undo and Redo, and the snapshots behind them.

A command here is a *before* and an *after* of some small piece of state,
taken around the thing that changed it:

    with self.window.undo.regions("Delete Region"):
        frame.regions = [...]

That is deliberately not the command pattern's usual shape, where every
operation grows an undo method of its own. A snapshot of a frame's regions
is a few hundred bytes, and taking one around the change costs one line at
the call site rather than a parallel implementation of every edit -- which
is the sort of thing that goes out of date the first time an edit gains a
field.

What is covered is regions, the view, the colours and the illustrate layer.
What is not is anything with data behind it: loading a file, binning a
table, deleting a frame. Those are not snapshots, they are megabytes, and
DS9 does not undo them either.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import copy
from contextlib import contextmanager

from ...utils.undo import UndoStack
from .base import Controller

#: The view fields a "view change" is a change to.
VIEW_FIELDS: tuple[str, ...] = (
    "zoom",
    "pan_x",
    "pan_y",
    "rotation",
    "flip_x",
    "flip_y",
    "align_wcs",
)

#: The colour fields a "colour change" is a change to.
COLOR_FIELDS: tuple[str, ...] = (
    "colormap",
    "invert_colormap",
    "contrast",
    "brightness",
    "color_tags",
)


class UndoController(Controller):
    """Owns the undo stack and the two menu entries over it."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: What has been done and what has been undone.
        self.stack = UndoStack()

    def connect(self) -> None:
        """Wire Edit -> Undo and Redo."""
        self.menu.action_undo.triggered.connect(lambda _checked=False: self.undo())
        self.menu.action_redo.triggered.connect(lambda _checked=False: self.redo())
        self.sync()

    def sync(self) -> None:
        """Say on the menu what would be undone, as every editor does."""
        undo = self.menu.action_undo
        redo = self.menu.action_redo
        undo.setEnabled(self.stack.can_undo)
        redo.setEnabled(self.stack.can_redo)
        undo.setText(f"&Undo {self.stack.undo_label}".rstrip())
        redo.setText(f"&Redo {self.stack.redo_label}".rstrip())

    # -- doing and undoing ------------------------------------------------------------

    def undo(self) -> str | None:
        """Take back the last command."""
        label = self.stack.undo()
        if label is None:
            self.status("Nothing to undo", 2000)
            return None
        self.sync()
        self.status(f"Undid {label}", 2500)
        return label

    def redo(self) -> str | None:
        """Do the last undone command again."""
        label = self.stack.redo()
        if label is None:
            self.status("Nothing to redo", 2000)
            return None
        self.sync()
        self.status(f"Redid {label}", 2500)
        return label

    def clear(self) -> None:
        """Forget the history, as loading a new file does."""
        self.stack.clear()
        self.sync()

    # -- recording a change ------------------------------------------------------------

    @contextmanager
    def snapshot(self, label: str, read, write, key=None):
        """Record whatever one block of code does to one piece of state.

        Args:
            label: What to call it on the menu.
            read: Called to take a snapshot.
            write: Called with a snapshot to put it back.
            key: Called with a snapshot to get something comparable, for
                state whose snapshots cannot be compared directly. A
                region has no equality of its own, so two snapshots of an
                untouched list would look different and every click would
                fill the history.

        Yields:
            Nothing; the block does the work.
        """
        if self.stack.applying:
            # An undo or a redo is putting state back; that is not a new
            # command, and recording it would make undo un-undoable.
            yield
            return

        compare = key if key is not None else (lambda snapshot: snapshot)
        before = read()
        yield
        after = read()
        if compare(before) == compare(after):
            # Nothing changed, so nothing to undo -- a click that moved a
            # region by nothing should not fill the history.
            return
        self.stack.record(
            label,
            undo=lambda: (write(before), self.after_apply()),
            redo=lambda: (write(after), self.after_apply()),
        )
        self.sync()

    def after_apply(self) -> None:
        """Put the frame back on the screen after a snapshot went back on it.

        The viewer holds the zoom and the pan itself, so writing them back
        onto the frame is not enough: the frame's view has to be applied to
        the viewer, exactly as switching to the frame does. Without this an
        undone zoom is undone on the frame and still on the screen -- and
        the next thing that persists the view writes the screen's value
        back over it.
        """
        window = self.window
        frame = self.frame
        if frame is not None:
            window.frame_controller.apply_view_state(frame)
            if hasattr(window.zoom, "set_zoom_display"):
                window.zoom.set_zoom_display(frame.zoom)
            elif hasattr(window.image_viewer, "zoom_to"):
                window.image_viewer.zoom_to(frame.zoom)
        window.region.show_frame_regions(frame)
        window.display.display()
        if hasattr(window.zoom, "update_panner_rect"):
            window.zoom.update_panner_rect()

    # -- the pieces of state it knows about ---------------------------------------------

    @contextmanager
    def regions(self, label: str = "Region Edit"):
        """Record a change to the current frame's regions.

        The snapshot is the list itself, deep-copied, so a restore is
        exact; what decides whether anything changed is the regions written
        out as DS9's text, because a region has no equality of its own and
        two copies of an untouched list would look different.
        """
        frame = self.frame
        if frame is None:
            yield
            return

        def read():
            return copy.deepcopy(list(frame.regions or []))

        def write(snapshot) -> None:
            frame.regions = copy.deepcopy(snapshot)

        with self.snapshot(label, read, write, key=self._region_text):
            yield

    @staticmethod
    def _region_text(regions) -> str:
        """A region list as DS9 would write it, for comparing two of them."""
        from ...regions.region_writer import RegionWriter

        if not regions:
            return ""
        try:
            return RegionWriter(coordinate_system="image").to_string(list(regions))
        except Exception:
            # A region the writer cannot express is still a change; saying
            # so is better than dropping the command.
            return repr([id(region) for region in regions])

    @contextmanager
    def view(self, label: str = "View Change"):
        """Record a change to the current frame's pan, zoom or orientation."""
        yield from self._fields(label, VIEW_FIELDS)

    @contextmanager
    def colors(self, label: str = "Colour Change"):
        """Record a change to the current frame's colours."""
        yield from self._fields(label, COLOR_FIELDS)

    def _fields(self, label: str, names: tuple[str, ...]):
        """Record a change to some of the current frame's fields."""
        frame = self.frame
        if frame is None:
            yield
            return

        def read():
            return {name: copy.deepcopy(getattr(frame, name, None)) for name in names}

        def write(snapshot) -> None:
            for name, value in snapshot.items():
                setattr(frame, name, copy.deepcopy(value))

        with self.snapshot(label, read, write):
            yield

    @contextmanager
    def illustrations(self, label: str = "Illustrate Edit"):
        """Record a change to the illustrate layer.

        DS9 undoes illustrate edits too, and separately from regions
        (`UpdateEditMenu`'s illustrate branch).
        """
        from ...illustrate import illustrate_file

        layer = self.window.illustrate.layer

        def read():
            return illustrate_file.serialise(layer.elements)

        def write(snapshot) -> None:
            layer.clear()
            for element in illustrate_file.parse(snapshot):
                layer.add(element)
            self.window.illustrate.refresh()

        with self.snapshot(label, read, write):
            yield
