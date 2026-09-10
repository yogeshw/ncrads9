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
The Illustrate menu (`millustrate.tcl`).

The layer it drives is not a region layer: an illustration is drawn on the
canvas and stays where it is put, which is what makes it useful for a figure
-- an arrow pointing at something, a caption, a logo -- and what makes it
wrong for marking a star. See `illustrate/elements.py`.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ...illustrate import illustrate_file
from ...illustrate.layer import IllustrateLayer
from .base import Controller

#: The file dialog's filter, as DS9's illustrate file box has it.
FILE_FILTER = "Illustrate files (*.ill *.txt);;All files (*)"

#: How far a pasted illustration is shifted, so it does not hide the one it
#: was copied from.
PASTE_OFFSET = 10.0


class IllustrateController(Controller):
    """Owns the illustrate layer and the menu over it."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: The one layer, shared by every frame -- DS9's illustrations are on
        #: the canvas, and the canvas does not change with the frame.
        self.layer = IllustrateLayer()
        self._dialog = None

    def connect(self) -> None:
        """Wire the whole Illustrate menu."""
        menu = self.menu
        menu.action_illustrate_info.triggered.connect(lambda _checked=False: self.show_dialog())
        menu.action_illustrate_show.toggled.connect(self.set_visible)

        for name, action in menu.illustrate_shape_actions.items():
            action.triggered.connect(lambda _checked=False, shape=name: self.set_shape(shape))
        for name, action in menu.illustrate_color_actions.items():
            action.triggered.connect(lambda _checked=False, color=name: self.set_color(color))
        for value, action in menu.illustrate_width_actions.items():
            action.triggered.connect(lambda _checked=False, width=value: self.set_width(width))

        commands = {
            "all": self.select_all,
            "none": self.select_none,
            "invert": self.invert_selection,
            "front": self.select_front,
            "back": self.select_back,
            "move_front": self.move_to_front,
            "move_back": self.move_to_back,
            "save_selection": self.save_selection,
            "list_selection": self.list_selection,
            "delete_selection": self.delete_selection,
            "open": self.load,
            "save": self.save,
            "list": self.list_all,
            "delete_all": self.delete_all,
        }
        for name, slot in commands.items():
            menu.illustrate_actions[name].triggered.connect(lambda _checked=False, run=slot: run())

    # -- the overlay -------------------------------------------------------------

    @property
    def overlay(self):
        """The overlay drawing the layer, or None before there is a viewer."""
        return getattr(self.viewer, "illustrate_overlay", None)

    def attach(self) -> None:
        """Point the viewer's overlay at this layer.

        Called whenever the viewer is rebuilt, which happens when the GPU
        preference changes and replaces the widget.
        """
        overlay = self.overlay
        if overlay is None:
            return
        overlay.layer = self.layer
        overlay.editing = self.window.edit_mode == "illustrate"
        overlay.on_selected = self._on_selected
        region_overlay = getattr(self.viewer, "region_overlay", None)
        if region_overlay is not None:
            region_overlay.illustrate_handler = overlay.handle_event
        overlay.update()

    def set_editing(self, editing: bool) -> None:
        """Let the mouse reach the layer, or stop it, as the mode changes."""
        overlay = self.overlay
        if overlay is not None:
            overlay.editing = bool(editing)
            if not editing:
                self.layer.select_none()
            overlay.update()

    def refresh(self) -> None:
        """Redraw the layer."""
        overlay = self.overlay
        if overlay is not None:
            overlay.update()
        if self._dialog is not None:
            self._dialog.reload()

    def _on_selected(self, element) -> None:
        """Follow a click on the canvas, so the dialog shows what was picked."""
        if self._dialog is not None:
            self._dialog.reload()

    # -- the style a new element gets ------------------------------------------------

    def set_shape(self, shape: str) -> None:
        """Choose what the next drag draws."""
        self.layer.shape = shape
        self.status(f"Illustrate shape: {shape}", 2000)

    def set_color(self, color: str) -> None:
        """Set the colour, for the selection if there is one."""
        self.layer.style.color = color
        for element in self.layer.selection():
            element.style.color = color
        self.refresh()
        self.status(f"Illustrate color: {color}", 2000)

    def set_width(self, width: int) -> None:
        """Set the line width, for the selection if there is one."""
        self.layer.style.width = int(width)
        for element in self.layer.selection():
            element.style.width = int(width)
        self.refresh()
        self.status(f"Illustrate width: {width}", 2000)

    def set_visible(self, visible: bool) -> None:
        """DS9's Show: draw the layer or hide it, keeping it either way."""
        self.layer.visible = bool(visible)
        self.refresh()
        self.status(f"Illustrations {'shown' if visible else 'hidden'}", 2000)

    # -- the selection ----------------------------------------------------------------

    def select_all(self) -> None:
        """Select every illustration."""
        count = self.layer.select_all()
        self.refresh()
        self.status(f"Selected {count} illustration(s)", 2000)

    def select_none(self) -> None:
        """Select none."""
        self.layer.select_none()
        self.refresh()
        self.status("Selection cleared", 2000)

    def invert_selection(self) -> None:
        """Swap what is selected for what is not."""
        count = self.layer.invert_selection()
        self.refresh()
        self.status(f"Selected {count} illustration(s)", 2000)

    def select_front(self) -> None:
        """Select the topmost illustration alone."""
        found = self.layer.select_front()
        self.refresh()
        self.status("Selected the front illustration" if found else "Nothing to select", 2000)

    def select_back(self) -> None:
        """Select the bottom illustration alone."""
        found = self.layer.select_back()
        self.refresh()
        self.status("Selected the back illustration" if found else "Nothing to select", 2000)

    # -- the order they are drawn in ---------------------------------------------------

    def move_to_front(self) -> None:
        """Draw the selection over everything else."""
        count = self.layer.move_to_front()
        self.refresh()
        self.status(f"Moved {count} illustration(s) to the front" if count else "Nothing selected", 2000)

    def move_to_back(self) -> None:
        """Draw the selection under everything else."""
        count = self.layer.move_to_back()
        self.refresh()
        self.status(f"Moved {count} illustration(s) to the back" if count else "Nothing selected", 2000)

    # -- deleting ------------------------------------------------------------------------

    def delete_selection(self) -> None:
        """Remove the selected illustrations."""
        count = self.layer.delete_selection()
        self.refresh()
        self.status(f"Deleted {count} illustration(s)" if count else "Nothing selected", 2000)

    def delete_all(self) -> None:
        """Remove every illustration."""
        count = self.layer.clear()
        self.refresh()
        self.status(f"Deleted {count} illustration(s)" if count else "Nothing to delete", 2000)

    # -- the clipboard --------------------------------------------------------------------

    def copy_selection(self) -> int:
        """Copy the selection, for Edit -> Paste."""
        return self.layer.copy_selection()

    def cut_selection(self) -> int:
        """Cut the selection, for Edit -> Cut."""
        count = self.layer.cut_selection()
        self.refresh()
        return count

    def paste(self) -> int:
        """Paste what was cut or copied, shifted so it can be seen."""
        pasted = self.layer.paste(PASTE_OFFSET)
        self.refresh()
        return len(pasted)

    # -- files -----------------------------------------------------------------------------

    def load(self, path: str | None = None) -> int:
        """Read an illustrate file onto the layer, adding to what is there.

        Args:
            path: The file, or None to ask for one.

        Returns:
            How many illustrations were read.
        """
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self.window, "Open Illustrate File", "", FILE_FILTER)
        if not path:
            return 0
        try:
            elements = illustrate_file.load(path)
        except OSError as exc:
            self.status(f"Could not read {Path(path).name}: {exc}", 4000)
            return 0

        for element in elements:
            self.layer.add(element)
        self.refresh()
        self.status(f"Loaded {len(elements)} illustration(s) from {Path(path).name}", 3000)
        return len(elements)

    def save(self, path: str | None = None) -> bool:
        """Write every illustration to a file."""
        return self._write(self.layer.elements, path, "illustrations")

    def save_selection(self, path: str | None = None) -> bool:
        """Write the selected illustrations to a file."""
        chosen = self.layer.selection()
        if not chosen:
            self.status("Nothing selected", 2000)
            return False
        return self._write(chosen, path, "selected illustrations")

    def _write(self, elements, path: str | None, what: str) -> bool:
        """Write some illustrations out."""
        if not elements:
            self.status("No illustrations to save", 2000)
            return False
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self.window, "Save Illustrate File", "", FILE_FILTER)
        if not path:
            return False
        try:
            illustrate_file.save(path, list(elements))
        except OSError as exc:
            self.status(f"Could not write {Path(path).name}: {exc}", 4000)
            return False
        self.status(f"Saved {len(elements)} {what} to {Path(path).name}", 3000)
        return True

    # -- listing -------------------------------------------------------------------------

    def list_all(self) -> None:
        """Show every illustration as DS9 would write it."""
        self._show(self.layer.elements, "Illustrate")

    def list_selection(self) -> None:
        """Show the selected illustrations as DS9 would write them."""
        chosen = self.layer.selection()
        if not chosen:
            self.status("Nothing selected", 2000)
            return
        self._show(chosen, "Illustrate Selection")

    def _show(self, elements, title: str) -> None:
        """Put a listing in a scrollable box, as the region listing does."""
        if not elements:
            self.status("No illustrations to list", 2000)
            return
        box = QMessageBox(self.window)
        box.setWindowTitle(title)
        box.setText(f"{len(elements)} illustration(s)")
        box.setDetailedText(illustrate_file.serialise(list(elements)))
        box.exec()

    # -- the dialog -----------------------------------------------------------------------

    def show_dialog(self) -> None:
        """DS9's Get Information: the selected illustration's parameters."""
        from ..dialogs.illustrate_dialog import IllustrateDialog

        if self._dialog is not None:
            self._dialog.reload()
            self._dialog.raise_()
            self._dialog.activateWindow()
            return

        dialog = IllustrateDialog(self, self.window)
        dialog.finished.connect(lambda _result: setattr(self, "_dialog", None))
        self._dialog = dialog
        dialog.show()

    def selected(self):
        """The one illustration the dialog edits, or None.

        The last of the selection, which is the topmost -- and the one just
        clicked, since a click selects it alone.
        """
        chosen = self.layer.selection()
        return chosen[-1] if chosen else None
