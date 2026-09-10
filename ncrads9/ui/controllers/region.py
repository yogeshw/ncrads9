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

from pathlib import Path

import numpy as np
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from ...analysis.centroid import DEFAULT_ITERATIONS, DEFAULT_RADIUS, centroid_at
from ...regions import group_manager, region_analysis, region_template
from ...regions.base_region import BaseRegion
from ...regions.region_formats import RegionFormat, dropped_shapes
from ...regions.region_parser import RegionParser
from ...regions.region_writer import RegionWriter
from ...regions.shapes.composite import Composite
from ..dialogs.centroid_dialog import CentroidDialog
from ..dialogs.group_dialog import GroupDialog
from ..dialogs.region_analysis_dialog import RegionPlotDialog, RegionStatisticsDialog
from ..dialogs.region_dialog import RegionDialog, analysis_commands_for
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

#: The filter DS9's template chooser uses.
TEMPLATE_FILTER = "Template Files (*.tpl);;All Files (*)"


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

        #: DS9's centroid settings, from `ds9/library/marker.tcl:28`.
        self.centroid_radius: float = DEFAULT_RADIUS
        self.centroid_iterations: int = DEFAULT_ITERATIONS
        #: Whether a newly drawn region is centroided at once.
        self.auto_centroid: bool = False

        #: Open analysis windows, keyed by (region id, command).
        self._analysis: dict[tuple[int, str], object] = {}
        #: Which of DS9's Auto Plot toggles are on.
        self._auto: set[str] = set()

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

        menu.action_composite_create.triggered.connect(lambda _checked=False: self.create_composite())
        menu.action_composite_dissolve.triggered.connect(lambda _checked=False: self.dissolve_composite())

        menu.action_region_centroid.triggered.connect(lambda _checked=False: self.centroid())
        menu.action_region_centroid_params.triggered.connect(
            lambda _checked=False: self.show_centroid_parameters()
        )
        menu.action_region_auto_centroid.toggled.connect(self.set_auto_centroid)
        menu.action_region_show.toggled.connect(self.set_show_regions)
        menu.action_region_show_text.toggled.connect(self.set_show_text)

        for name, action in menu.region_auto_actions.items():
            action.toggled.connect(lambda state, key=name: self.set_auto_analysis(key, state))

        menu.action_template_open.triggered.connect(lambda _checked=False: self.load_template())
        menu.action_template_save.triggered.connect(lambda _checked=False: self.save_template())
        for path, action in menu.region_fov_actions.items():
            action.triggered.connect(lambda _checked=False, key=path: self.load_fov(key))

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

    # -- region analysis (M6-22 ... M6-26) -------------------------------------

    def open_analysis(self, region: BaseRegion, name: str) -> None:
        """Open one of a region's Analysis windows, or raise the open one.

        Args:
            region: The region measured.
            name: One of `ANALYSIS_COMMANDS`.
        """
        key = (id(region), name)
        existing = self._analysis.get(key)
        if existing is not None:
            existing.refresh()
            existing.raise_()
            existing.activateWindow()
            return

        window = self._analysis_window(region, name)
        if window is None:
            self.status(f"Unknown analysis: {name}", 3000)
            return
        window.finished.connect(lambda _result, k=key: self._analysis.pop(k, None))
        self._analysis[key] = window
        window.show()

    def _analysis_window(self, region: BaseRegion, name: str):
        """Build the window one analysis command wants."""
        if name == "statistics":
            return RegionStatisticsDialog(region, self._statistics_text, self.window)

        plots = {
            "histogram": (self._histogram_of, "Histogram", ("Value", "Pixels"), "bar"),
            "radial": (self._radial_of, "Radial Profile", ("Radius (pixels)", "Surface brightness"), "line"),
            "plot2d": (self._cut_of, "Plot 2D", ("Distance (pixels)", "Value"), "line"),
            "plot3d": (self._depth_of, "Plot 3D", ("Slice", "Sum in region"), "line"),
        }
        if name not in plots:
            return None
        provider, title, labels, style = plots[name]
        return RegionPlotDialog(region, provider, title, labels, style, self.window)

    # -- what the windows ask for ------------------------------------------------

    def _image(self):
        """The current frame's image, or None."""
        frame = self.frame
        return None if frame is None else frame.image_data

    def _statistics_text(self, region: BaseRegion) -> str:
        return region_analysis.describe(region, self._image())

    def _histogram_of(self, region: BaseRegion):
        centres, counts = region_analysis.histogram(region, self._image())
        return (centres, counts, None)

    def _radial_of(self, region: BaseRegion):
        return region_analysis.radial_profile(region, self._image())

    def _cut_of(self, region: BaseRegion):
        distances, values = region_analysis.cut(region, self._image())
        return (distances, values, None)

    def _depth_of(self, region: BaseRegion):
        frame = self.frame
        cube = None if frame is None else getattr(getattr(frame, "image", None), "data", None)
        slices, totals = region_analysis.depth_profile(region, cube)
        return (slices, totals, None)

    # -- the Auto toggles (M6-26) -------------------------------------------------

    def set_auto_analysis(self, name: str, enabled: bool) -> None:
        """Turn one of DS9's Auto Plot toggles on or off.

        With one on, every region drawn or changed opens -- and keeps up to
        date -- that window. That is what makes them worth having: DS9's
        point is that you drag a projection across a source and watch the
        cut change, rather than reopening a dialog each time.
        """
        if enabled:
            self._auto.add(name)
        else:
            self._auto.discard(name)
        self.status(f"Auto {name}: {'on' if enabled else 'off'}")
        if enabled:
            for region in self.selection_only():
                self._auto_open(region)

    def _auto_open(self, region: BaseRegion) -> None:
        """Open the automatic windows a region qualifies for."""
        offered = analysis_commands_for(region)
        for name in self._auto:
            if name in offered:
                self.open_analysis(region, name)

    def refresh_analysis(self, region: BaseRegion | None = None) -> None:
        """Measure again in every open analysis window.

        Called after anything that moves a region, so a window never shows
        an answer for where the region used to be.
        """
        for (region_id, _name), window in list(self._analysis.items()):
            if region is None or region_id == id(region):
                window.refresh()

    # -- templates and instrument FOVs (M6-18, M6-19) --------------------------

    def load_template(self, path: str | None = None) -> None:
        """Load a template onto the current frame at its WCS centre.

        Args:
            path: The template file. Asked for when not given.
        """
        frame = self.frame
        if frame is None:
            self.status("No frame", 3000)
            return

        if path is None:
            path, _filter = QFileDialog.getOpenFileName(self.window, "Open Template", "", TEMPLATE_FILTER)
            if not path:
                return

        try:
            placed = region_template.load(path, getattr(frame, "wcs_handler", None))
        except region_template.TemplateError as exc:
            self.status(str(exc), 5000)
            return
        except OSError as exc:
            self.status(f"Cannot read {Path(path).name}: {exc}", 5000)
            return

        for region in placed:
            frame.regions.append(region)
        self.refresh_overlay()
        self.status(f"Loaded {Path(path).name}: {len(placed)} region{'s' if len(placed) != 1 else ''}")

    def load_fov(self, name: str) -> None:
        """Load one of DS9's bundled instrument fields of view.

        Args:
            name: A key of `bundled_templates`, e.g. "chandra/acis/acis-i".
        """
        path = region_template.bundled_templates().get(name)
        if path is None:
            self.status(f"No such instrument template: {name}", 3000)
            return
        self.load_template(str(path))

    def save_template(self) -> None:
        """Save the regions as a template, relative to the WCS centre.

        DS9 saves everything on the frame, not the selection: a template is
        an instrument, and half an instrument is not one.
        """
        frame = self.frame
        if frame is None or not frame.regions:
            self.status("No regions to save", 3000)
            return

        path, _filter = QFileDialog.getSaveFileName(self.window, "Save Template", "", TEMPLATE_FILTER)
        if not path:
            return
        if not Path(path).suffix:
            path = f"{path}{region_template.TEMPLATE_SUFFIX}"

        try:
            region_template.save(path, frame.regions, getattr(frame, "wcs_handler", None))
        except region_template.TemplateError as exc:
            self.status(str(exc), 5000)
            return
        except OSError as exc:
            self.status(f"Cannot write {Path(path).name}: {exc}", 5000)
            return
        self.status(f"Saved {len(frame.regions)} regions to {Path(path).name}")

    # -- centroid (M6-20) -------------------------------------------------------

    def centroid(self, regions: list[BaseRegion] | None = None) -> None:
        """Walk each chosen region onto the flux under it, DS9's Centroid.

        Args:
            regions: What to centroid. Defaults to the selection; with
                nothing selected DS9 centroids nothing, since moving every
                region on the frame is not a thing anyone asks for by
                accident.
        """
        frame = self.frame
        chosen = regions if regions is not None else self.selection_only()
        if frame is None or frame.image_data is None:
            self.status("No image to centroid on", 3000)
            return
        if not chosen:
            self.status("Select a region to centroid", 3000)
            return

        moved = 0
        for region in chosen:
            if not region.can_move:
                continue
            x, y = region.center
            found = centroid_at(
                frame.image_data,
                x,
                y,
                radius=self.centroid_radius,
                iterations=self.centroid_iterations,
            )
            if found != (x, y):
                region.center = found
                moved += 1

        self.refresh_overlay()
        self.status(f"Centroided {moved} region{'s' if moved != 1 else ''}")

    def show_centroid_parameters(self) -> None:
        """Ask for the centroid radius and iteration count."""
        dialog = CentroidDialog(self.centroid_radius, self.centroid_iterations, self.window)
        if not dialog.exec():
            return
        self.centroid_radius, self.centroid_iterations = dialog.values()
        self.status(f"Centroid: radius {self.centroid_radius:g}, {self.centroid_iterations} iterations")

    def set_auto_centroid(self, enabled: bool) -> None:
        """Centroid each region as it is drawn, DS9's Auto Centroid."""
        self.auto_centroid = bool(enabled)
        self.status(f"Auto centroid: {'on' if enabled else 'off'}")

    # -- what is drawn ------------------------------------------------------------

    def set_show_regions(self, shown: bool) -> None:
        """Show or hide every region, DS9's Region Parameters -> Show."""
        overlay = getattr(self.viewer, "region_overlay", None)
        if overlay is not None:
            overlay.setVisible(bool(shown))
        self.status(f"Regions: {'shown' if shown else 'hidden'}")

    def set_show_text(self, shown: bool) -> None:
        """Show or hide region labels, DS9's Show Text."""
        overlay = getattr(self.viewer, "region_overlay", None)
        if overlay is not None:
            overlay.renderer.show_labels = bool(shown)
        self.refresh_overlay()
        self.status(f"Region text: {'shown' if shown else 'hidden'}")

    # -- composites (M6-17) ----------------------------------------------------

    def create_composite(self) -> None:
        """Fold the selection into one composite region, DS9's Create.

        The members leave the frame's region list and live inside the
        composite from then on, which is what makes the whole thing move,
        rotate and delete as one.
        """
        frame = self.frame
        chosen = self.selection_only()
        if frame is None or len(chosen) < 2:
            self.status("Select two or more regions to make a composite", 3000)
            return

        composite = Composite(regions=list(chosen))
        self.apply_defaults(composite)
        # Put the composite where the first member was, so folding regions
        # up does not also bring them to the front.
        position = min(frame.regions.index(region) for region in chosen)
        frame.regions = [region for region in frame.regions if region not in chosen]
        frame.regions.insert(position, composite)

        for member in chosen:
            member.selected = False
        composite.selected = True

        self.refresh_overlay()
        self.status(f"Composite of {len(chosen)} regions")

    def dissolve_composite(self) -> None:
        """Break the selected composites back into their members."""
        frame = self.frame
        if frame is None:
            return
        composites = [region for region in self.selection_only() if isinstance(region, Composite)]
        if not composites:
            self.status("Select a composite region to dissolve", 3000)
            return

        released = 0
        for composite in composites:
            position = frame.regions.index(composite)
            members = list(composite.regions)
            frame.regions[position : position + 1] = members
            for member in members:
                member.selected = True
            released += len(members)

        self.refresh_overlay()
        self.status(f"Dissolved {len(composites)} composite{'s' if len(composites) != 1 else ''}")

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
        dialog.region_changed.connect(self._on_region_changed)
        for name, action in dialog.analysis_actions.items():
            action.triggered.connect(lambda _checked=False, r=region, key=name: self.open_analysis(r, key))
        dialog.region_deleted.connect(self._delete_one)
        dialog.finished.connect(lambda _result, key=id(region): self._dialogs.pop(key, None))
        self._dialogs[id(region)] = dialog
        dialog.show()

    def _on_region_changed(self, region: BaseRegion) -> None:
        """Redraw, and re-measure anything watching this region."""
        self.refresh_overlay()
        self.refresh_analysis(region)

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

        with self.window.undo.regions("Reorder Regions"):
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
        with self.window.undo.regions("Delete Regions"):
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
            with self.window.undo.regions("Delete All Regions"):
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
            with self.window.undo.regions(f"Create {describe(region)}"):
                frame.regions.append(self.apply_defaults(region))
        self.status(f"Created {describe(region)} region")
        if self.auto_centroid:
            # DS9's Auto Centroid: a region dropped near a source snaps onto
            # it, so it need not be placed precisely by hand.
            self.centroid([region])
        if self._auto:
            self._auto_open(region)

    def on_edit(self, phase: str) -> None:
        """Record a region drag, which spans a press and a release.

        A context manager cannot hold a snapshot across two mouse events,
        so the two ends are taken here: `begin` opens one and `finish`
        closes it, and a drag that changed nothing records nothing.
        """
        undo = self.window.undo
        if phase == "begin":
            self._edit = undo.regions("Move Region")
            self._edit.__enter__()
            return
        pending = getattr(self, "_edit", None)
        if pending is not None:
            self._edit = None
            pending.__exit__(None, None, None)

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
