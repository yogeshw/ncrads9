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


"""Region properties, rendering and the Region menu's selection operations."""

from __future__ import annotations

import numpy as np
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QImage, QPainter, QPixmap

from ncrads9.regions.region_parser import RegionParser
from ncrads9.regions.region_renderer import FILL_ALPHA, RegionRenderer
from ncrads9.ui.menu_bar import (
    REGION_COLORS,
    REGION_FONT_SIZES,
    REGION_FONTS,
    REGION_PROPERTIES,
    REGION_SELECTION_COMMANDS,
    REGION_SHAPES,
    REGION_WIDTHS,
)

#: Identity transform: image coordinates are widget coordinates.
IDENTITY = QPointF


def _parse(text: str):
    return RegionParser().parse_string(f"image\n{text}\n")[0]


#: How dark a channel has to be to count as painted, out of 255.
INK = 250


def _render(regions, zoom: float = 1.0, size: int = 400):
    """Draw regions onto a white canvas and hand back an RGB array.

    Read out through numpy rather than `QImage.pixelColor`: a per-pixel call
    on a 400-square canvas is 160,000 round trips into Qt, which took these
    tests from a second to minutes.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill()
    painter = QPainter(pixmap)
    RegionRenderer().render(
        painter,
        regions,
        lambda x, y: QPointF(size / 2 + (x - 50) * zoom, size / 2 - (y - 50) * zoom),
    )
    painter.end()

    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
    buffer = image.constBits()
    buffer.setsize(image.height() * image.bytesPerLine())
    rows = np.frombuffer(buffer, dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
    # `.copy()` is not a nicety: the frombuffer view borrows the QImage's
    # own memory, which Qt frees when `image` goes out of scope here. Reading
    # it afterwards is undefined -- it segfaulted outright in a script and
    # silently handed back stale pixels in a test.
    return rows[:, : image.width() * 3].reshape(image.height(), image.width(), 3).copy()


def _ink(canvas) -> np.ndarray:
    """A mask of the pixels something was drawn on."""
    return canvas.min(axis=2) < INK


def _painted_width(region, zoom: float) -> int:
    """How many columns of the canvas the region covers."""
    columns = np.nonzero(_ink(_render([region], zoom=zoom)).any(axis=0))[0]
    return int(columns.max() - columns.min()) if columns.size else 0


# -- every shape draws (M6-9) ------------------------------------------------


ALL_SHAPES = (
    "circle(50,50,20)",
    "ellipse(50,50,20,10,30)",
    "box(50,50,20,10,15)",
    "polygon(40,40,60,40,60,60)",
    "segment(40,40,50,60,60,40)",
    "point(50,50)",
    "line(40,40,60,60)",
    "vector(40,40,20,45)",
    "ruler(40,40,60,60)",
    "compass(50,50,15)",
    "projection(40,40,60,60,8)",
    "annulus(50,50,8,18)",
    "ellipse(50,50,6,4,16,10)",
    "box(50,50,6,4,16,10)",
    "panda(50,50,0,360,4,8,18,2)",
    "epanda(50,50,0,270,3,6,4,16,10,2,20)",
    "bpanda(50,50,0,360,4,6,4,16,10,2)",
    "text(50,50) # text={label}",
)


@pytest.mark.parametrize("text", ALL_SHAPES)
def test_every_shape_puts_ink_on_the_canvas(qapp, text):
    """Eleven of these used to draw a four-pixel tick and nothing else."""
    assert int(_ink(_render([_parse(text)])).sum()) > 10, text


def test_a_composite_shows_a_centre_cross(qapp):
    assert int(_ink(_render([_parse("# composite(50,50,0)")])).sum()) > 4


def test_a_text_region_draws_its_label_once(qapp):
    """It was drawn twice: once as the shape, once as the label."""
    rows = np.nonzero(_ink(_render([_parse("text(50,50) # text={ABC}")])).any(axis=1))[0]
    # One line of text occupies one band of rows, not two.
    bands = 1 + int((np.diff(rows) > 3).sum()) if rows.size else 0
    assert bands == 1


# -- fill and dash (M6-9) ----------------------------------------------------


def test_fill_paints_the_interior(qapp):
    plain = _render([_parse("circle(50,50,20)")])
    filled = _render([_parse("circle(50,50,20) # fill=1")])
    assert not _ink(plain)[200, 200]
    assert _ink(filled)[200, 200]


def test_a_fill_is_translucent(qapp):
    """The data underneath has to stay readable."""
    assert 0 < FILL_ALPHA < 255


def test_dash_reaches_the_pen(qapp):
    from PyQt6.QtCore import Qt

    renderer = RegionRenderer()
    assert renderer.pen_for(_parse("circle(1,2,3)")).style() != Qt.PenStyle.DashLine
    assert renderer.pen_for(_parse("circle(1,2,3) # dash=1")).style() == Qt.PenStyle.DashLine


def test_an_excluded_region_is_struck_through(qapp):
    """DS9 marks an exclusion so it can be told apart at a glance."""
    included = _render([_parse("circle(50,50,20)")])
    excluded = _render([_parse("-circle(50,50,20)")])

    def red_pixels(canvas) -> int:
        # Redder than it is green, rather than an absolute threshold: the
        # strike is a 45-degree line, so antialiasing covers each pixel
        # about half and pure red arrives as (255, 127, 127).
        return int((canvas[:, :, 0].astype(int) - canvas[:, :, 1] > 50).sum())

    assert red_pixels(excluded) > red_pixels(included)


# -- fixed in size (M6-8) ----------------------------------------------------


def test_a_plain_region_scales_with_the_zoom(qapp):
    region = _parse("circle(50,50,20)")
    assert _painted_width(region, 2.0) == pytest.approx(_painted_width(region, 1.0) * 2, abs=4)


def test_a_fixed_region_keeps_its_screen_size(qapp):
    """DS9's "fixed in size": legible however far the image is zoomed."""
    region = _parse("circle(50,50,20) # fixed=1")
    at_one = _painted_width(region, 1.0)
    for zoom in (2.0, 4.0, 8.0):
        assert _painted_width(region, zoom) == pytest.approx(at_one, abs=2), zoom


# -- the Region menu ---------------------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    window._rebuild_image_viewer(False)
    frame = window.frame_manager.current_frame
    frame.image_data = np.arange(64 * 64, dtype=np.float32).reshape(64, 64)
    frame.original_image_data = frame.image_data
    frame.regions = RegionParser().parse_string("image\ncircle(10,10,5)\nbox(20,20,6,6)\ncircle(30,30,5)\n")
    yield window
    window.close()


def test_the_shape_cascade_offers_every_drawable_shape(main_window):
    assert len(REGION_SHAPES) == 18
    for name, _label in REGION_SHAPES:
        assert name in main_window.menu_bar.region_shape_actions


@pytest.mark.parametrize("name", [name for name, _label in REGION_SHAPES])
def test_choosing_a_shape_arms_that_drawing_mode(main_window, name):
    """Thirteen of the eighteen used to answer "arrives in M6-4"."""
    from ncrads9.ui.widgets.region_overlay import RegionMode

    main_window.menu_bar.region_shape_actions[name].trigger()
    assert main_window.image_viewer.region_overlay.mode is RegionMode(name)


def test_choosing_a_drawable_shape_sets_the_mode(main_window):
    from ncrads9.ui.widgets.region_overlay import RegionMode

    main_window.menu_bar.region_shape_actions["ellipse"].trigger()
    assert main_window.image_viewer.region_overlay.mode is RegionMode.ELLIPSE


@pytest.mark.parametrize("color", REGION_COLORS)
def test_every_colour_is_offered_and_becomes_the_default(main_window, color):
    main_window.menu_bar.region_color_actions[color].trigger()
    assert main_window.region.defaults["color"] == color


@pytest.mark.parametrize("width", REGION_WIDTHS)
def test_every_width_is_offered(main_window, width):
    main_window.menu_bar.region_width_actions[width].trigger()
    assert main_window.region.defaults["width"] == width


def test_a_colour_change_applies_to_the_selection(main_window):
    regions = main_window.frame_manager.current_frame.regions
    regions[0].selected = True
    main_window.region.set_color("red")
    assert regions[0].color == "red"
    # Unselected regions are left alone.
    assert regions[1].color == "green"


def test_a_colour_change_with_no_selection_only_sets_the_default(main_window):
    main_window.region.set_color("cyan")
    assert all(region.color == "green" for region in main_window.frame_manager.current_frame.regions)
    assert main_window.region.defaults["color"] == "cyan"


def test_the_defaults_reach_a_newly_drawn_region(main_window):
    main_window.region.set_color("magenta")
    main_window.region.set_width(3)
    drawn = _parse("circle(1,2,3)")
    main_window.region.apply_defaults(drawn)
    assert drawn.color == "magenta"
    assert drawn.width == 3


@pytest.mark.parametrize(("name", "_label", "_default"), REGION_PROPERTIES)
def test_every_property_flag_is_offered(main_window, name, _label, _default):
    action = main_window.menu_bar.region_property_actions[name]
    action.setChecked(not action.isChecked())
    assert name in main_window.region.defaults


def test_a_property_change_applies_to_the_selection(main_window):
    regions = main_window.frame_manager.current_frame.regions
    regions[0].selected = True
    main_window.menu_bar.region_property_actions["dash"].setChecked(True)
    assert regions[0].dash
    assert not regions[1].dash


def test_the_font_cascade_sets_family_and_size(main_window):
    main_window.menu_bar.region_font_actions["times"].trigger()
    main_window.menu_bar.region_font_size_actions[14].trigger()
    assert main_window.region.defaults["font"] == "times 14 normal roman"


def test_ds9s_font_choices_are_offered(main_window):
    assert set(REGION_FONTS) == set(main_window.menu_bar.region_font_actions)
    assert set(REGION_FONT_SIZES) == set(main_window.menu_bar.region_font_size_actions)


# -- selection operations (M6-14, M6-15) -------------------------------------


def test_every_selection_command_is_wired(main_window, monkeypatch):
    """Trigger each one, with the two that open dialogs stubbed.

    Save Selection opens a file dialog and List Selection a message box;
    triggering them for real blocks the run forever under the offscreen
    platform, which is how this test first hung.
    """
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)

    names = [name for name, _label in REGION_SELECTION_COMMANDS if name]
    assert set(names) == set(main_window.menu_bar.region_selection_actions)
    for name in names:
        main_window.region.select_all()
        main_window.menu_bar.region_selection_actions[name].trigger()


def test_select_all_and_none(main_window):
    main_window.region.select_all()
    assert len(main_window.region.selection()) == 3
    main_window.region.select_none()
    assert main_window.region.selection() == []


def test_invert_swaps_the_selection(main_window):
    regions = main_window.frame_manager.current_frame.regions
    regions[0].selected = True
    main_window.region.select_invert()
    assert not regions[0].selected
    assert regions[1].selected and regions[2].selected


def test_front_and_back_select_the_ends(main_window):
    regions = main_window.frame_manager.current_frame.regions
    main_window.region.bring_front()
    assert regions[-1].selected and not regions[0].selected
    main_window.region.send_back()
    assert regions[0].selected and not regions[-1].selected


def test_move_to_front_reorders_the_drawing_list(main_window):
    frame = main_window.frame_manager.current_frame
    first = frame.regions[0]
    first.selected = True
    main_window.region.move_front()
    assert frame.regions[-1] is first


def test_move_to_back_reorders_the_drawing_list(main_window):
    frame = main_window.frame_manager.current_frame
    last = frame.regions[-1]
    last.selected = True
    main_window.region.move_back()
    assert frame.regions[0] is last


def test_moving_with_no_selection_says_so(main_window):
    main_window.region.move_front()
    assert "No regions selected" in main_window.status_bar.currentMessage()


def test_delete_selection_removes_only_what_is_selected(main_window):
    frame = main_window.frame_manager.current_frame
    frame.regions[1].selected = True
    main_window.region.delete_selection()
    assert len(frame.regions) == 2


def test_delete_respects_the_delete_property(main_window):
    """DS9's `delete=0` marks a region that must not be deleted."""
    frame = main_window.frame_manager.current_frame
    frame.regions[0].can_delete = False
    for region in frame.regions:
        region.selected = True

    main_window.region.delete_selection()
    assert len(frame.regions) == 1
    assert "delete=0" in main_window.status_bar.currentMessage()


def test_delete_all_respects_the_delete_property(main_window):
    frame = main_window.frame_manager.current_frame
    frame.regions[2].can_delete = False
    main_window.region.clear_regions()
    assert len(frame.regions) == 1
    assert "delete=0" in main_window.status_bar.currentMessage()


def test_delete_all_clears_an_unprotected_frame(main_window):
    frame = main_window.frame_manager.current_frame
    main_window.region.clear_regions()
    assert frame.regions == []


def test_moving_respects_the_move_property(main_window):
    """`move=0` is enforced in the overlay's drag handler."""
    from PyQt6.QtCore import QPointF as Point

    overlay = main_window.image_viewer.region_overlay
    region = main_window.frame_manager.current_frame.regions[0]
    region.can_move = False
    overlay.regions = [region]
    overlay.selected_region = region
    overlay.drag_start = Point(0.0, 0.0)
    before = region.center

    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QMouseEvent

    overlay.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            Point(50.0, 50.0),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert region.center == before


# -- listing and saving ------------------------------------------------------


def test_saving_a_selection_needs_one(main_window):
    main_window.region.save_selection()
    assert "No regions selected" in main_window.status_bar.currentMessage()


def test_listing_with_no_regions_says_so(main_window):
    main_window.frame_manager.current_frame.regions = []
    main_window.region.list_regions()
    assert "No regions to list" in main_window.status_bar.currentMessage()


def test_listing_shows_every_region(main_window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    shown: dict[str, str] = {}
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.update(text=self.detailedText()) or 0)
    main_window.region.list_regions()
    assert shown["text"].count("circle") == 2
    assert "box(" in shown["text"]


def test_listing_a_selection_shows_only_it(main_window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    shown: dict[str, str] = {}
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.update(text=self.detailedText()) or 0)
    main_window.frame_manager.current_frame.regions[1].selected = True
    main_window.region.list_selection()
    assert "box(" in shown["text"]
    assert "circle" not in shown["text"]


def test_saving_reports_what_a_format_cannot_hold(main_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    frame = main_window.frame_manager.current_frame
    frame.regions = RegionParser().parse_string("image\ncircle(1,2,3)\nline(0,0,1,1)\n")
    path = tmp_path / "out.reg"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(path), "CIAO region files (*.reg)")),
    )
    main_window.region.save_regions()
    assert "cannot hold line" in main_window.status_bar.currentMessage()
    assert "line(" not in path.read_text()


# -- Get Information, from the menu (M6-7) -----------------------------------


def test_get_information_with_nothing_selected_says_so(main_window):
    main_window.region.select_none()
    main_window.menu_bar.action_region_info.trigger()
    assert "Select a region first" in main_window.status_bar.currentMessage()


def test_get_information_opens_one_dialog_per_selected_region(main_window):
    """DS9 opens a dialog for each, rather than making you pick one."""
    main_window.region.select_all()
    main_window.menu_bar.action_region_info.trigger()
    assert len(main_window.region._dialogs) == 3
    for dialog in list(main_window.region._dialogs.values()):
        dialog.close()


def test_asking_twice_reuses_the_same_dialog(main_window):
    region = main_window.frame_manager.current_frame.regions[0]
    main_window.region.show_information(region)
    first = next(iter(main_window.region._dialogs.values()))
    main_window.region.show_information(region)
    assert list(main_window.region._dialogs.values()) == [first]
    first.close()


def test_closing_a_dialog_forgets_it(main_window):
    region = main_window.frame_manager.current_frame.regions[0]
    main_window.region.show_information(region)
    next(iter(main_window.region._dialogs.values())).close()
    assert main_window.region._dialogs == {}


def test_deleting_from_the_dialog_removes_the_region(main_window):
    frame = main_window.frame_manager.current_frame
    region = frame.regions[0]
    main_window.region.show_information(region)
    dialog = main_window.region._dialogs[id(region)]
    dialog._delete()
    assert region not in frame.regions
    assert len(frame.regions) == 2


# -- groups, from the menu (M6-16) --------------------------------------------


def test_new_group_with_nothing_selected_says_so(main_window):
    """Grouping every region because none was chosen is not what anyone meant."""
    main_window.region.select_none()
    main_window.menu_bar.action_region_new_group.trigger()
    assert "Select the regions to group first" in main_window.status_bar.currentMessage()


def test_new_group_tags_the_selection(main_window, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("bright", True)))
    regions = main_window.frame_manager.current_frame.regions
    regions[0].selected = True
    main_window.menu_bar.action_region_new_group.trigger()
    assert regions[0].tags == ["bright"]
    assert regions[1].tags == []


def test_new_group_suggests_the_first_unused_name(main_window, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog

    offered = {}

    def prompt(_parent, _title, _label, text=""):
        offered["text"] = text
        return ("", False)

    monkeypatch.setattr(QInputDialog, "getText", staticmethod(prompt))
    regions = main_window.frame_manager.current_frame.regions
    regions[0].tags = ["Group 1"]
    regions[0].selected = True
    main_window.menu_bar.action_region_new_group.trigger()
    assert offered["text"] == "Group 2"


def test_the_groups_dialog_opens_and_is_kept(main_window):
    main_window.menu_bar.action_region_groups.trigger()
    assert main_window.region._group_dialog is not None
    main_window.region._group_dialog.close()
    assert main_window.region._group_dialog is None


# -- point glyphs (M6-5) ------------------------------------------------------


def test_every_ds9_point_glyph_draws_something(qapp):
    from ncrads9.regions.shapes.point import Point

    assert len(Point.SHAPES) == 7
    for glyph in Point.SHAPES:
        assert int(_ink(_render([_parse(f"point(50,50) # point={glyph}")])).sum()) > 10, glyph


def test_the_seven_glyphs_are_seven_different_marks(qapp):
    """Seven names that all drew a circle would be one glyph with seven names."""
    from ncrads9.regions.shapes.point import Point

    drawn = {glyph: _render([_parse(f"point(50,50) # point={glyph}")]).tobytes() for glyph in Point.SHAPES}
    assert len(set(drawn.values())) == len(Point.SHAPES)


def test_a_points_size_is_honoured(qapp):
    small = _ink(_render([_parse("point(50,50) # point=circle 5")])).sum()
    large = _ink(_render([_parse("point(50,50) # point=circle 30")])).sum()
    assert large > small * 2
