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
The Region menu: drawing mode, properties, selection and region files.

Two things live here. The *defaults* -- colour, width, font and the property
flags -- are what a newly drawn region takes and what the menu applies to
whatever is selected, which is how DS9's Color, Width, Properties and Font
cascades behave: they act on the selection when there is one and set the
default when there is not.

The *selection* operations are DS9's All, None, Invert, Front, Back, Move to
Front and Move to Back, plus Save, List and Delete for the selection alone.
Front and Back are the drawing order, so they are a reordering of the frame's
region list -- the last drawn is on top.

Still missing against DS9 (PLAN.md §5.9): creating the shapes that need more
than a drag (M6-4), resize and rotate handles (M6-6), the per-shape
information dialog (M6-7), groups (M6-16), composites (M6-17), templates and
instrument FOVs (M6-18, M6-19) and centroiding (M6-20).

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from ...regions import group_manager
from ...regions.base_region import BaseRegion
from ...regions.region_formats import RegionFormat, dropped_shapes
from ...regions.region_parser import RegionParser
from ...regions.region_writer import RegionWriter
from ..dialogs.group_dialog import GroupDialog
from ..dialogs.region_dialog import RegionDialog
from ..menu_bar import (
    DEFAULT_REGION_COLOR,
    DEFAULT_REGION_FONT,
    DEFAULT_REGION_FONT_SIZE,
    REGION_SHAPES,
)
from ..widgets.region_overlay import RegionMode
from .base import Controller

#: Mode -> the name the status bar and button bar show. Read off the Shape
#: cascade so a shape cannot be offered under one name and reported under
#: another; the ampersands are the menu's accelerator marks.
MODE_LABELS: dict[RegionMode, str] = {RegionMode.NONE: "None"} | {
    RegionMode(name): label.replace("&", "") for name, label in REGION_SHAPES
}

#: Button-bar label -> region mode. The button bar has no Point button.
LABEL_MODES: dict[str, RegionMode] = {label: mode for mode, label in MODE_LABELS.items()}

REGION_FILTER = "Region Files (*.reg);;All Files (*)"


def describe(region: BaseRegion) -> str:
    """Name a region for the status bar, e.g. "circle".

    Takes the name from the shape's class rather than from a mode attribute.
    The overlay's old `Region` dataclass carried a `RegionMode`, and the two
    handlers below still read `region.mode.value` after M1 replaced it with
    `BaseRegion` subclasses -- so drawing anything raised AttributeError.
    Nothing caught it, because the M1 tests connected their own listener to
    the overlay's signal and never went through the window's handler.
    """
    return type(region).__name__.lower()


class RegionController(Controller):
    """Owns the Region menu."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as for every controller.
        """
        super().__init__(window)
        #: What a newly drawn region takes, and what the Color, Width,
        #: Properties and Font cascades set when nothing is selected. Kept
        #: here rather than on the window, which M2-16 caps at 600 lines.
        self.region_defaults: dict = {
            "color": DEFAULT_REGION_COLOR,
            "width": 1,
            "font_family": DEFAULT_REGION_FONT,
            "font_size": DEFAULT_REGION_FONT_SIZE,
        }

        #: Open Get Information dialogs, keyed by the region's id. A
        #: modeless dialog nothing holds a reference to is collected the
        #: moment it is shown, so it must be kept somewhere.
        self._dialogs: dict[int, RegionDialog] = {}

        #: The Groups dialog, kept for the same reason.
        self._group_dialog: GroupDialog | None = None

    def connect(self) -> None:
        """Wire the Region menu."""
        menu = self.menu

        for name, action in menu.region_shape_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.set_shape(key))
        menu.action_region_none.triggered.connect(lambda: self.set_mode(RegionMode.NONE))

        for name, action in menu.region_color_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.set_color(key))
        for value, action in menu.region_width_actions.items():
            action.triggered.connect(lambda _checked=False, key=value: self.set_width(key))
        for name, action in menu.region_property_actions.items():
            action.toggled.connect(lambda state, key=name: self.set_property(key, state))
        for family, action in menu.region_font_actions.items():
            action.triggered.connect(lambda _checked=False, key=family: self.set_font_family(key))
        for size, action in menu.region_font_size_actions.items():
            action.triggered.connect(lambda _checked=False, key=size: self.set_font_size(key))

        for name, action in menu.region_selection_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.selection_command(key))

        menu.action_region_load.triggered.connect(self.load_regions)
        menu.action_region_save.triggered.connect(self.save_regions)
        menu.action_region_list.triggered.connect(self.list_regions)
        menu.action_region_delete_all.triggered.connect(self.clear_regions)

        # Through a lambda: `triggered` hands its `checked` bool to the
        # first argument, which would arrive as the region to show.
        menu.action_region_info.triggered.connect(lambda _checked=False: self.show_information())

        menu.action_region_new_group.triggered.connect(lambda _checked=False: self.new_group())
        menu.action_region_groups.triggered.connect(lambda _checked=False: self.show_groups())

        for action, milestone in (
            (menu.action_region_composite, "M6-17"),
            (menu.action_region_template, "M6-18"),
            (menu.action_region_centroid, "M6-20"),
        ):
            action.triggered.connect(
                lambda _checked=False, a=action, m=milestone: self.status(
                    f"{a.text().replace('&', '')} arrives in {m}", 3000
                )
            )

    # -- drawing mode --------------------------------------------------------

    def set_shape(self, name: str) -> None:
        """Choose the shape the next drag draws.

        Args:
            name: A key of `MenuBar.region_shape_actions`.
        """
        try:
            self.set_mode(RegionMode(name))
        except ValueError:
            self.status(f"Unknown region shape: {name}", 3000)

    def set_mode(self, mode: RegionMode) -> None:
        """Set the shape the next drag will draw."""
        self.viewer.set_region_mode(mode)
        label = MODE_LABELS.get(mode, "None")
        self.window.button_bar.set_region_mode(label)
        self.status(f"Region mode: {label}")

    def on_button_bar_mode(self, label: str) -> None:
        """Set the drawing mode from a button-bar label."""
        self.set_mode(LABEL_MODES.get(label, RegionMode.NONE))

    # -- defaults, and the selection they apply to ---------------------------

    @property
    def defaults(self) -> dict:
        """What a newly drawn region takes for its colour, width and flags."""
        return self.region_defaults

    def selection(self) -> list[BaseRegion]:
        """The selected regions, or every region when none is selected.

        DS9's Color, Width, Properties and Font cascades act on what is
        selected; with nothing selected they set the default for what comes
        next, which `_apply` does by writing to `defaults` as well.
        """
        frame = self.frame
        if frame is None:
            return []
        return [region for region in frame.regions if getattr(region, "selected", False)]

    def _apply(self, attribute: str, value: object, message: str) -> None:
        """Set a default, and apply it to the selection if there is one."""
        self.defaults[attribute] = value
        chosen = self.selection()
        for region in chosen:
            setattr(region, attribute, value)
        if chosen:
            self.refresh_overlay()
            self.status(f"{message} for {len(chosen)} selected")
        else:
            self.status(f"{message} for new regions")

    def set_color(self, color: str) -> None:
        """Set the region colour."""
        self._apply("color", color, f"Region colour: {color}")

    def set_width(self, width: int) -> None:
        """Set the region line width."""
        self._apply("width", int(width), f"Region width: {width}")

    def set_property(self, name: str, enabled: bool) -> None:
        """Set one of DS9's region property flags.

        Args:
            name: A key of `MenuBar.region_property_actions`.
            enabled: Whether the flag is on.
        """
        self._apply(name, bool(enabled), f"Region {name.replace('_', ' ')}: {'on' if enabled else 'off'}")

    def set_font_family(self, family: str) -> None:
        """Set the region font family, keeping the current size."""
        size = self.defaults.get("font_size", 10)
        self.defaults["font_family"] = family
        self._apply("font", f"{family} {size} normal roman", f"Region font: {family}")

    def set_font_size(self, size: int) -> None:
        """Set the region font size, keeping the current family."""
        family = self.defaults.get("font_family", "helvetica")
        self.defaults["font_size"] = int(size)
        self._apply("font", f"{family} {size} normal roman", f"Region font size: {size}")

    def apply_defaults(self, region: BaseRegion) -> BaseRegion:
        """Give a newly drawn region the current defaults."""
        for attribute, value in self.defaults.items():
            if attribute in ("font_family", "font_size"):
                continue
            if hasattr(region, attribute):
                setattr(region, attribute, value)
        return region

    # -- groups (M6-16) -------------------------------------------------------

    def new_group(self) -> None:
        """Tag the selection as a new group, DS9's New Group.

        A group in DS9 is a tag, so this is exactly "put a name on these
        regions" -- and because it is a tag, it survives being written to a
        region file and read back.
        """
        chosen = self.selection_only()
        if not chosen:
            self.status("Select the regions to group first", 3000)
            return

        frame = self.frame
        suggestion = group_manager.default_name(frame.regions if frame else [])
        name, accepted = QInputDialog.getText(self.window, "New Group", "Enter group name:", text=suggestion)
        name = name.strip()
        if not accepted or not name:
            return

        added = group_manager.create(chosen, name)
        self.refresh_overlay()
        self.status(f"Group {name}: {added} region{'s' if added != 1 else ''}")

    def selection_only(self) -> list[BaseRegion]:
        """The selected regions, and nothing when none is selected.

        `selection` falls back to every region, which is right for the Color
        and Width cascades -- they set a default -- and wrong here: grouping
        every region because none was chosen is not what anyone meant.
        """
        frame = self.frame
        if frame is None:
            return []
        return [region for region in frame.regions if getattr(region, "selected", False)]

    def show_groups(self) -> None:
        """Open DS9's Groups dialog on the current frame."""
        frame = self.frame
        if frame is None:
            self.status("No frame", 3000)
            return

        existing = getattr(self, "_group_dialog", None)
        if existing is not None:
            existing.regions = frame.regions
            existing.refresh()
            existing.raise_()
            existing.activateWindow()
            return

        dialog = GroupDialog(frame.regions, self.window)
        dialog.groups_changed.connect(self._on_groups_changed)
        dialog.finished.connect(lambda _result: setattr(self, "_group_dialog", None))
        self._group_dialog = dialog
        dialog.show()

    def _on_groups_changed(self, message: str) -> None:
        """Redraw and report, after the Groups dialog changes something."""
        self.refresh_overlay()
        self.status(message)

    # -- Get Information (M6-7) ----------------------------------------------

    def show_information(self, region: BaseRegion | None = None) -> None:
        """Open DS9's Get Information dialog on one region.

        Args:
            region: The region to show. Defaults to the selection -- and to
                the whole selection, since DS9 opens one dialog per selected
                region rather than making the user pick one.
        """
        chosen = [region] if region is not None else self.selection()
        if not chosen:
            self.status("Select a region first", 3000)
            return
        for target in chosen:
            self._open_information(target)

    def _open_information(self, region: BaseRegion) -> None:
        """Open, remember and show one region's dialog.

        The dialog is kept in `self._dialogs` because a modeless dialog with
        no reference is garbage collected the moment this returns, which
        shows as a window that flashes and vanishes.
        """
        existing = self._dialogs.get(id(region))
        if existing is not None:
            existing.load()
            existing.raise_()
            existing.activateWindow()
            return

        frame = self.frame
        dialog = RegionDialog(region, getattr(frame, "wcs_handler", None), self.window)
        dialog.region_changed.connect(lambda _region: self.refresh_overlay())
        dialog.region_deleted.connect(self._delete_one)
        dialog.finished.connect(lambda _result, key=id(region): self._dialogs.pop(key, None))
        self._dialogs[id(region)] = dialog
        dialog.show()

    def _delete_one(self, region: BaseRegion) -> None:
        """Delete one region, from its own dialog."""
        frame = self.frame
        if frame is None or region not in frame.regions:
            return
        frame.regions.remove(region)
        self.refresh_overlay()
        self.status(f"Deleted {describe(region)}")

    # -- selection operations (M6-14, M6-15) ---------------------------------

    def selection_command(self, name: str) -> None:
        """Run one of DS9's selection or ordering commands."""
        handler = {
            "all": self.select_all,
            "none": self.select_none,
            "invert": self.select_invert,
            "front": self.bring_front,
            "back": self.send_back,
            "move_front": self.move_front,
            "move_back": self.move_back,
            "save_selection": self.save_selection,
            "list_selection": self.list_selection,
            "delete_selection": self.delete_selection,
        }.get(name)
        if handler is None:
            self.status(f"Unknown region command: {name}", 3000)
            return
        handler()

    def _regions(self) -> list[BaseRegion]:
        """The current frame's regions, or an empty list."""
        frame = self.frame
        return frame.regions if frame is not None and frame.regions is not None else []

    def _set_selected(self, regions, selected: bool) -> None:
        """Mark a run of regions selected or not, and redraw."""
        for region in regions:
            region.selected = selected
        self.refresh_overlay()

    def select_all(self) -> None:
        """Select every region on the frame."""
        regions = self._regions()
        self._set_selected(regions, True)
        self.status(f"Selected {len(regions)} regions")

    def select_none(self) -> None:
        """Deselect everything."""
        self._set_selected(self._regions(), False)
        self.status("Selection cleared")

    def select_invert(self) -> None:
        """Select what was not selected, and deselect what was."""
        for region in self._regions():
            region.selected = not getattr(region, "selected", False)
        self.refresh_overlay()
        self.status(f"Selected {len(self.selection())} regions")

    def bring_front(self) -> None:
        """Select the frontmost region, which is the last drawn."""
        regions = self._regions()
        self._set_selected(regions, False)
        if regions:
            regions[-1].selected = True
            self.refresh_overlay()
        self.status("Selected the front region")

    def send_back(self) -> None:
        """Select the backmost region, which is the first drawn."""
        regions = self._regions()
        self._set_selected(regions, False)
        if regions:
            regions[0].selected = True
            self.refresh_overlay()
        self.status("Selected the back region")

    def move_front(self) -> None:
        """Move the selection to the end of the list, so it draws on top."""
        self._reorder(to_front=True)

    def move_back(self) -> None:
        """Move the selection to the start, so everything draws over it."""
        self._reorder(to_front=False)

    def _reorder(self, to_front: bool) -> None:
        """Move the selected regions to one end of the drawing order."""
        frame = self.frame
        chosen = self.selection()
        if frame is None or not chosen:
            self.status("No regions selected")
            return

        rest = [region for region in frame.regions if region not in chosen]
        frame.regions = (rest + chosen) if to_front else (chosen + rest)
        self.refresh_overlay()
        self.status(f"Moved {len(chosen)} regions to the {'front' if to_front else 'back'}")

    def delete_selection(self) -> None:
        """Delete the selected regions, honouring DS9's delete property."""
        frame = self.frame
        chosen = self.selection()
        if frame is None or not chosen:
            self.status("No regions selected")
            return

        protected = [region for region in chosen if not getattr(region, "can_delete", True)]
        deletable = [region for region in chosen if getattr(region, "can_delete", True)]
        frame.regions = [region for region in frame.regions if region not in deletable]
        self.refresh_overlay()

        message = f"Deleted {len(deletable)} regions"
        if protected:
            message += f"; {len(protected)} are marked delete=0"
        self.status(message, 3000)

    def list_selection(self) -> None:
        """Show the selected regions as DS9 would write them."""
        self._show_listing(self.selection(), "Selected Regions")

    def list_regions(self) -> None:
        """Show every region as DS9 would write them."""
        self._show_listing(self._regions(), "Regions")

    def _show_listing(self, regions: list[BaseRegion], title: str) -> None:
        """Put a region listing in a scrollable message box."""
        if not regions:
            self.status("No regions to list")
            return
        text = RegionWriter(coordinate_system=self.window.coord_context.frame.value).to_string(regions)
        box = QMessageBox(self.window)
        box.setWindowTitle(title)
        box.setText(f"{len(regions)} regions")
        box.setDetailedText(text)
        box.exec()

    def save_selection(self) -> None:
        """Write the selected regions to a file."""
        chosen = self.selection()
        if not chosen:
            self.status("No regions selected")
            return
        self._write(chosen)

    # -- file operations -----------------------------------------------------

    def load_regions(self) -> None:
        """Load a DS9 region file into the current frame."""
        filepath, _ = QFileDialog.getOpenFileName(self.window, "Load Region File", "", REGION_FILTER)
        if not filepath:
            return
        try:
            regions = RegionParser().parse_file(filepath)
        except Exception as exc:
            self.status(f"Error loading regions: {exc}", 3000)
            return

        frame = self.frame
        if frame is not None:
            frame.regions = regions
            self.show_frame_regions(frame)
        self.status(f"Loaded {len(regions)} regions from {filepath}", 3000)

    def save_regions(self) -> None:
        """Write the current frame's regions to a DS9 region file."""
        regions = self._regions()
        if not regions:
            self.status("No regions to save")
            return
        self._write(regions)

    def _write(self, regions: list[BaseRegion]) -> None:
        """Prompt for a path and a format, then write.

        The format is taken from the chosen filter, so DS9's File Format menu
        is the file dialog's own -- one fewer dialog for the same choice.
        """
        filters = ";;".join(f"{value.value.upper()} region files (*.reg)" for value in RegionFormat)
        filepath, chosen = QFileDialog.getSaveFileName(
            self.window, "Save Region File", "", f"{REGION_FILTER};;{filters}"
        )
        if not filepath:
            return

        region_format = RegionFormat.DS9
        for value in RegionFormat:
            if chosen.lower().startswith(value.value):
                region_format = value
                break

        lost = dropped_shapes(regions, region_format)
        try:
            RegionWriter(
                coordinate_system=self.window.coord_context.frame.value,
                region_format=region_format,
            ).write_file(regions, filepath)
        except OSError as exc:
            self.status(f"Error saving regions: {exc}", 5000)
            return

        message = f"Saved {len(regions)} regions to {filepath}"
        if lost:
            message += f"; {region_format.value} cannot hold {', '.join(lost)}"
        self.status(message, 4000)

    def clear_regions(self) -> None:
        """Delete every region on the current frame."""
        frame = self.frame
        if frame is not None:
            protected = [r for r in frame.regions if not getattr(r, "can_delete", True)]
            frame.regions = list(protected)
            # SAMP markers are regenerated from stored positions, so drop
            # those too or they would reappear on the next refresh.
            self.window._samp_catalog_sources.pop(frame.frame_id, None)
            if protected:
                self.show_frame_regions(frame)
                self.set_mode(RegionMode.NONE)
                self.status(f"Cleared all but {len(protected)} regions marked delete=0", 3000)
                return
        if hasattr(self.viewer, "clear_regions"):
            self.viewer.clear_regions()
        self.set_mode(RegionMode.NONE)
        self.status("Cleared all regions")

    # -- overlay signals -----------------------------------------------------

    def on_created(self, region: BaseRegion) -> None:
        """Record a region the user just drew on the current frame."""
        frame = self.frame
        if frame is not None:
            frame.regions.append(self.apply_defaults(region))
        self.status(f"Created {describe(region)} region")

    def on_selected(self, region: BaseRegion) -> None:
        """Report the region the user just clicked."""
        self.status(f"Selected {describe(region)} region")

    # -- frame synchronisation -----------------------------------------------

    def show_frame_regions(self, frame) -> None:
        """Replace the overlay's regions with the given frame's."""
        if not hasattr(self.viewer, "clear_regions"):
            return
        self.viewer.clear_regions()
        if frame is None:
            return
        for region in frame.regions:
            self.viewer.add_region(region)

    def refresh_overlay(self) -> None:
        """Redraw the overlay after a change to the regions themselves."""
        self.show_frame_regions(self.frame)

    # -- coordinates ---------------------------------------------------------

    def world_to_pixel(self, ra_deg: float, dec_deg: float) -> tuple[float, float] | None:
        """Convert a sky position to image pixels for overlaying a catalog.

        Returns None when there is no usable WCS, or when the position falls
        outside the projection and comes back non-finite.
        """
        handler = self.window.wcs_handler
        if handler is None or not handler.is_valid or self.window.image_data is None:
            return None
        try:
            x, y = handler.world_to_pixel(ra_deg, dec_deg)
        except Exception:
            return None
        if not np.isfinite(x) or not np.isfinite(y):
            return None
        return float(x), float(y)

    def ask_text(self) -> str:
        """Prompt for a region's text label."""
        text, ok = QInputDialog.getText(self.window, "Region Text", "Text:")
        return text if ok else ""
