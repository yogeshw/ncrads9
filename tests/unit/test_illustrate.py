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

"""DS9's Illustrate layer (M9-6, M9-7, M9-8)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits
from PyQt6.QtCore import QPointF

from ncrads9.illustrate import illustrate_file
from ncrads9.illustrate.elements import (
    DEFAULT_COLOR,
    SHAPES,
    Box,
    Circle,
    Image,
    Line,
    Polygon,
    Style,
    Text,
)
from ncrads9.illustrate.layer import IllustrateLayer

SIZE = 100


# -- the elements -------------------------------------------------------------------


def test_every_shape_the_menu_offers_can_be_made():
    layer = IllustrateLayer()
    for shape in SHAPES:
        assert layer.create(shape, 50.0, 50.0).kind == shape


def test_a_circle_knows_its_extent_and_its_middle():
    circle = Circle(x=50.0, y=60.0, radius=10.0)
    assert circle.bounds() == (40.0, 50.0, 60.0, 70.0)
    assert circle.center == (50.0, 60.0)


def test_moving_an_element_moves_all_of_it():
    polygon = Polygon(points=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])
    polygon.move(5.0, -5.0)
    assert polygon.points == [(5.0, -5.0), (15.0, -5.0), (15.0, 5.0)]


def test_an_outline_shape_is_picked_on_its_edge_not_its_middle():
    """Clicking through an unfilled circle should reach what is behind it."""
    circle = Circle(x=50.0, y=50.0, radius=20.0)
    assert circle.contains(70.0, 50.0)
    assert not circle.contains(50.0, 50.0)


def test_a_filled_shape_is_picked_anywhere_inside_it():
    circle = Circle(style=Style(fill=True), x=50.0, y=50.0, radius=20.0)
    assert circle.contains(50.0, 50.0)
    assert not circle.contains(90.0, 50.0)


def test_a_line_is_picked_along_its_length():
    line = Line(points=[(0.0, 0.0), (100.0, 0.0)])
    assert line.contains(50.0, 1.0)
    assert not line.contains(50.0, 40.0)
    # And not past its end, where its extent alone would have caught it.
    assert not line.contains(150.0, 0.0)


def test_a_polygon_that_is_filled_is_picked_inside_it():
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert Polygon(style=Style(fill=True), points=square).contains(5.0, 5.0)
    assert not Polygon(style=Style(fill=True), points=square).contains(20.0, 5.0)


def test_a_polygons_handles_are_its_own_points():
    """So a polygon is reshaped vertex by vertex, not by its bounding box."""
    polygon = Polygon(points=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])
    assert polygon.handles() == polygon.points
    polygon.resize(1, 20.0, 5.0)
    assert polygon.points[1] == (20.0, 5.0)


def test_a_box_is_reshaped_about_its_centre():
    box = Box(x=50.0, y=50.0, radius1=10.0, radius2=10.0)
    box.resize(0, 80.0, 60.0)
    assert (box.radius1, box.radius2) == (30.0, 10.0)
    assert box.center == (50.0, 50.0)


def test_an_image_keeps_its_aspect_ratio_when_resized():
    """As DS9's does (`IllustrateImageEdit`)."""
    image = Image(x=50.0, y=50.0, path="", width=40.0, height=20.0)
    image.resize(0, 90.0, 50.0)
    assert image.width == pytest.approx(80.0)
    assert image.height == pytest.approx(40.0)


def test_a_copy_is_independent_and_unselected():
    polygon = Polygon(points=[(0.0, 0.0), (10.0, 10.0)])
    polygon.selected = True
    clone = polygon.copy()
    clone.move(5.0, 5.0)
    assert polygon.points == [(0.0, 0.0), (10.0, 10.0)]
    assert clone.selected is False
    assert clone.style is not polygon.style


# -- the file format -----------------------------------------------------------------


def test_the_header_is_the_one_ds9_writes():
    text = illustrate_file.serialise([])
    assert text.startswith("# Illustrate file format: DS9 version 1.0\n")
    assert "global color = cyan fill = no width = 1 dash = no" in text
    assert "global font = helvetica fontsize = 12" in text


def test_only_what_differs_from_the_default_is_written():
    """Which is what makes a saved file readable."""
    assert Circle(x=1.0, y=2.0, radius=3.0).to_line() == "circle 1 2 3"
    assert (
        Circle(style=Style(color="red", width=2), x=1.0, y=2.0, radius=3.0).to_line()
        == "circle 1 2 3 # color = red width = 2"
    )


@pytest.mark.parametrize(
    "line",
    [
        "circle 100 200 20",
        "circle 100 200 20 # color = red fill = yes width = 3 dash = yes",
        "ellipse 10 20 30 40",
        "box 1 2 3 4 # fill = yes",
        "polygon 0 0 10 0 10 10",
        "line 0 0 50 50 # line = 1 0",
        "line 0 0 50 50 # color = magenta width = 4 dash = yes line = 1 1",
        'text 5 6 "hello"',
        'text 5 6 "hello" # font = times fontsize = 20 fontweight = bold fontslant = italic',
        'text 5 6 "hello" # angle = 45 justify = center',
        'image 1 2 "/tmp/sun.png" 30 40',
    ],
)
def test_every_line_round_trips(line):
    elements = illustrate_file.parse(line)
    assert len(elements) == 1
    assert elements[0].to_line() == line


def test_a_multi_line_caption_survives_the_round_trip():
    text = Text(x=1.0, y=2.0, text="two\nlines")
    parsed = illustrate_file.parse(text.to_line())
    assert parsed[0].text == "two\nlines"


def test_a_path_with_a_space_in_it_survives():
    image = Image(x=1.0, y=2.0, path="/tmp/a folder/sun.png", width=3.0, height=4.0)
    assert illustrate_file.parse(image.to_line())[0].path == "/tmp/a folder/sun.png"


def test_ds9s_own_stray_bracket_is_read_anyway():
    """DS9's line writer emits `width = 3)` (`illustrateline.tcl:127`). A
    file that is mostly good is worth reading."""
    parsed = illustrate_file.parse("line 0 0 10 10 # width = 3) line = 0 1")
    assert parsed[0].style.width == 3
    assert parsed[0].arrow_last is True


def test_the_globals_set_the_defaults_for_what_follows():
    text = "global color = red width = 2\ncircle 1 2 3\n"
    circle = illustrate_file.parse(text)[0]
    assert circle.style.color == "red"
    assert circle.style.width == 2


def test_a_lines_own_properties_beat_the_globals():
    text = "global color = red\ncircle 1 2 3 # color = blue\n"
    assert illustrate_file.parse(text)[0].style.color == "blue"


def test_a_line_that_makes_no_sense_is_skipped_not_raised():
    parsed = illustrate_file.parse("circle 1 2 3\nbanana 4 5\nline 1\nbox 9 9 9 9\n")
    assert [element.kind for element in parsed] == ["circle", "box"]


def test_comments_and_blank_lines_are_ignored():
    assert illustrate_file.parse("# a note\n\n   \n") == []


def test_a_file_round_trips_through_the_disk(tmp_path):
    elements = [
        Circle(style=Style(color="red"), x=1.0, y=2.0, radius=3.0),
        Text(x=4.0, y=5.0, text="caption"),
    ]
    path = tmp_path / "figure.ill"
    illustrate_file.save(path, elements)
    assert [element.to_line() for element in illustrate_file.load(path)] == [
        element.to_line() for element in elements
    ]


# -- the layer -------------------------------------------------------------------------


@pytest.fixture
def layer():
    made = IllustrateLayer()
    made.create("circle", 20.0, 20.0)
    made.create("box", 60.0, 60.0)
    made.create("text", 90.0, 90.0)
    return made


def test_the_last_added_is_on_top(layer):
    assert layer.elements[-1].kind == "text"


def test_a_click_finds_the_topmost_element_under_it(layer):
    """Front to back: the one drawn last is the one you can see."""
    over = layer.create("circle", 20.0, 20.0, radius=20.0)
    over.style.fill = True
    layer.elements[0].style.fill = True
    assert layer.at(20.0, 20.0) is over


def test_a_click_on_nothing_finds_nothing(layer):
    assert layer.at(5.0, 95.0) is None


def test_selecting_one_element_unselects_the_others(layer):
    layer.select_all()
    layer.select_only(layer.elements[0])
    assert layer.selection() == [layer.elements[0]]


def test_all_none_and_invert(layer):
    assert layer.select_all() == 3
    layer.select_none()
    assert layer.selection() == []
    assert layer.invert_selection() == 3
    assert layer.invert_selection() == 0


def test_front_and_back_select_one_each(layer):
    assert layer.select_front() is layer.elements[-1]
    assert layer.selection() == [layer.elements[-1]]
    assert layer.select_back() is layer.elements[0]


def test_front_and_back_on_an_empty_layer_do_nothing():
    empty = IllustrateLayer()
    assert empty.select_front() is None
    assert empty.select_back() is None


def test_moving_to_the_front_keeps_the_selections_own_order(layer):
    first, second = layer.elements[0], layer.elements[1]
    first.selected = second.selected = True
    layer.move_to_front()
    assert layer.elements[-2:] == [first, second]


def test_moving_to_the_back_keeps_the_selections_own_order(layer):
    last = layer.elements[-1]
    last.selected = True
    layer.move_to_back()
    assert layer.elements[0] is last


def test_moving_nothing_moves_nothing(layer):
    before = list(layer.elements)
    assert layer.move_to_front() == 0
    assert layer.elements == before


def test_only_the_selection_has_handles(layer):
    circle = layer.elements[0]
    x, y = circle.handles()[0]
    assert layer.handle_at(x, y) is None
    circle.selected = True
    assert layer.handle_at(x, y) == (circle, 0)


def test_deleting_the_selection_and_deleting_everything(layer):
    layer.elements[0].selected = True
    assert layer.delete_selection() == 1
    assert len(layer) == 2
    assert layer.clear() == 2
    assert len(layer) == 0


def test_copy_and_paste_leaves_the_original_alone(layer):
    layer.elements[0].selected = True
    assert layer.copy_selection() == 1
    pasted = layer.paste(offset=10.0)
    assert len(layer) == 4
    assert pasted[0].center == (30.0, 30.0)
    assert layer.elements[0].center == (20.0, 20.0)


def test_cut_takes_it_away_and_keeps_it(layer):
    layer.elements[0].selected = True
    assert layer.cut_selection() == 1
    assert len(layer) == 2
    layer.paste()
    assert len(layer) == 3


def test_what_is_pasted_becomes_the_selection(layer):
    layer.elements[0].selected = True
    layer.copy_selection()
    pasted = layer.paste()
    assert layer.selection() == pasted


def test_a_new_element_takes_the_layers_style(layer):
    layer.style.color = "magenta"
    layer.style.width = 3
    made = layer.create("circle", 1.0, 1.0)
    assert made.style.color == "magenta"
    assert made.style.width == 3
    # Its own copy, so changing one element does not change the next.
    made.style.color = "red"
    assert layer.style.color == "magenta"


# -- the menu over it ----------------------------------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32)).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    yield window
    window.close()


def test_the_menu_is_ds9s(main_window):
    labels = [
        action.text().replace("&", "")
        for action in main_window.menu_bar.illustrate_menu.actions()
        if not action.isSeparator()
    ]
    assert labels == [
        "Get Information",
        "Shape",
        "Color",
        "Width",
        "All",
        "None",
        "Invert",
        "Front",
        "Back",
        "Move to Front",
        "Move to Back",
        "Save Selection...",
        "List Selection",
        "Delete Selection",
        "Open...",
        "Save...",
        "List",
        "Delete All",
        "Show",
    ]


def test_the_shape_menu_chooses_what_a_drag_draws(main_window):
    main_window.menu_bar.illustrate_shape_actions["ellipse"].trigger()
    assert main_window.illustrate.layer.shape == "ellipse"


def test_the_colour_and_width_menus_set_the_style(main_window):
    main_window.menu_bar.illustrate_color_actions["magenta"].trigger()
    main_window.menu_bar.illustrate_width_actions[3].trigger()
    assert main_window.illustrate.layer.style.color == "magenta"
    assert main_window.illustrate.layer.style.width == 3


def test_the_colour_menu_recolours_the_selection(main_window):
    element = main_window.illustrate.layer.create("circle", 10.0, 10.0)
    element.selected = True
    main_window.menu_bar.illustrate_color_actions["red"].trigger()
    assert element.style.color == "red"


def test_show_hides_the_layer_without_losing_it(main_window):
    main_window.illustrate.layer.create("circle", 10.0, 10.0)
    main_window.menu_bar.action_illustrate_show.setChecked(False)
    assert main_window.illustrate.layer.visible is False
    assert len(main_window.illustrate.layer) == 1


def test_the_selection_commands(main_window):
    layer = main_window.illustrate.layer
    layer.create("circle", 10.0, 10.0)
    layer.create("box", 50.0, 50.0)

    main_window.menu_bar.illustrate_actions["all"].trigger()
    assert len(layer.selection()) == 2
    main_window.menu_bar.illustrate_actions["none"].trigger()
    assert layer.selection() == []
    main_window.menu_bar.illustrate_actions["invert"].trigger()
    assert len(layer.selection()) == 2
    main_window.menu_bar.illustrate_actions["front"].trigger()
    assert layer.selection() == [layer.elements[-1]]
    main_window.menu_bar.illustrate_actions["back"].trigger()
    assert layer.selection() == [layer.elements[0]]


def test_the_order_commands(main_window):
    layer = main_window.illustrate.layer
    first = layer.create("circle", 10.0, 10.0)
    layer.create("box", 50.0, 50.0)
    first.selected = True

    main_window.menu_bar.illustrate_actions["move_front"].trigger()
    assert layer.elements[-1] is first
    main_window.menu_bar.illustrate_actions["move_back"].trigger()
    assert layer.elements[0] is first


def test_delete_selection_and_delete_all(main_window):
    layer = main_window.illustrate.layer
    layer.create("circle", 10.0, 10.0)
    layer.create("box", 50.0, 50.0).selected = True

    main_window.menu_bar.illustrate_actions["delete_selection"].trigger()
    assert len(layer) == 1
    main_window.menu_bar.illustrate_actions["delete_all"].trigger()
    assert len(layer) == 0


def test_delete_all_with_nothing_there_says_so(main_window):
    main_window.menu_bar.illustrate_actions["delete_all"].trigger()
    assert "Nothing to delete" in main_window.status_bar.currentMessage()


def test_open_and_save_go_through_a_file(main_window, tmp_path):
    layer = main_window.illustrate.layer
    layer.create("circle", 20.0, 30.0, radius=10.0)
    path = tmp_path / "figure.ill"

    assert main_window.illustrate.save(str(path)) is True
    layer.clear()
    assert main_window.illustrate.load(str(path)) == 1
    assert layer.elements[0].center == (20.0, 30.0)


def test_loading_adds_to_what_is_already_drawn(main_window, tmp_path):
    """As DS9 does: an illustrate file is not a replacement for the layer."""
    layer = main_window.illustrate.layer
    layer.create("circle", 20.0, 30.0)
    path = tmp_path / "figure.ill"
    main_window.illustrate.save(str(path))
    main_window.illustrate.load(str(path))
    assert len(layer) == 2


def test_saving_the_selection_writes_only_it(main_window, tmp_path):
    layer = main_window.illustrate.layer
    layer.create("circle", 20.0, 30.0)
    layer.create("box", 60.0, 60.0).selected = True
    path = tmp_path / "some.ill"

    assert main_window.illustrate.save_selection(str(path)) is True
    written = illustrate_file.load(path)
    assert [element.kind for element in written] == ["box"]


def test_saving_the_selection_with_nothing_selected_says_so(main_window, tmp_path):
    main_window.illustrate.layer.create("circle", 20.0, 30.0)
    assert main_window.illustrate.save_selection(str(tmp_path / "x.ill")) is False
    assert "Nothing selected" in main_window.status_bar.currentMessage()


def test_saving_an_empty_layer_writes_nothing(main_window, tmp_path):
    path = tmp_path / "empty.ill"
    assert main_window.illustrate.save(str(path)) is False
    assert not path.exists()


def test_loading_a_file_that_is_not_there_is_reported(main_window, tmp_path):
    assert main_window.illustrate.load(str(tmp_path / "missing.ill")) == 0
    assert "Could not read" in main_window.status_bar.currentMessage()


def test_listing_shows_what_would_be_written(main_window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    shown = {}
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.update(text=self.detailedText()))
    main_window.illustrate.layer.create("circle", 20.0, 30.0, radius=5.0)
    main_window.menu_bar.illustrate_actions["list"].trigger()
    assert "circle 20 30 5" in shown["text"]


def test_listing_nothing_says_so(main_window):
    main_window.menu_bar.illustrate_actions["list"].trigger()
    assert "No illustrations to list" in main_window.status_bar.currentMessage()


# -- the mode and the overlay -------------------------------------------------------------


def test_illustrate_mode_is_no_longer_deferred(main_window):
    main_window.menu_bar.edit_mode_actions["illustrate"].trigger()
    assert "arrives in" not in main_window.status_bar.currentMessage()
    assert main_window.image_viewer.illustrate_overlay.editing is True


def test_leaving_the_mode_stops_the_layer_taking_clicks(main_window):
    """Or an invisible drawing would catch a click meant for the image."""
    main_window.menu_bar.edit_mode_actions["illustrate"].trigger()
    main_window.menu_bar.edit_mode_actions["pan"].trigger()
    assert main_window.image_viewer.illustrate_overlay.editing is False


def test_leaving_the_mode_clears_the_selection(main_window):
    main_window.menu_bar.edit_mode_actions["illustrate"].trigger()
    main_window.illustrate.layer.create("circle", 10.0, 10.0).selected = True
    main_window.menu_bar.edit_mode_actions["pan"].trigger()
    assert main_window.illustrate.layer.selection() == []


def test_the_overlay_draws_the_controllers_layer(main_window):
    assert main_window.image_viewer.illustrate_overlay.layer is main_window.illustrate.layer


def test_the_layer_survives_the_viewer_being_rebuilt(main_window):
    """Switching the GPU preference replaces the widget; the illustrations
    are on the canvas, not on the widget."""
    main_window.illustrate.layer.create("circle", 10.0, 10.0)
    main_window._rebuild_image_viewer(False)
    assert len(main_window.illustrate.layer) == 1
    assert main_window.image_viewer.illustrate_overlay.layer is main_window.illustrate.layer


def test_the_overlay_is_transparent_to_the_mouse(main_window):
    """Only the region overlay takes mouse events; this one is handed them."""
    from PyQt6.QtCore import Qt

    overlay = main_window.image_viewer.illustrate_overlay
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert main_window.image_viewer.region_overlay.illustrate_handler == overlay.handle_event


def test_a_drag_draws_the_chosen_shape(main_window):
    overlay = main_window.image_viewer.illustrate_overlay
    overlay.editing = True
    overlay.layer.shape = "box"

    overlay.handle_event("press", QPointF(10.0, 10.0))
    overlay.handle_event("move", QPointF(50.0, 30.0))
    overlay.handle_event("release", QPointF(50.0, 30.0))

    assert len(overlay.layer) == 1
    box = overlay.layer.elements[0]
    assert box.kind == "box"
    assert box.center == (30.0, 20.0)
    assert (box.radius1, box.radius2) == (20.0, 10.0)


def test_a_click_places_a_default_sized_shape(main_window):
    overlay = main_window.image_viewer.illustrate_overlay
    overlay.editing = True
    overlay.handle_event("press", QPointF(40.0, 40.0))
    overlay.handle_event("release", QPointF(40.0, 40.0))

    circle = overlay.layer.elements[0]
    assert circle.center == (40.0, 40.0)
    assert circle.radius == 20.0


def test_a_click_on_an_element_selects_it_instead_of_drawing(main_window):
    overlay = main_window.image_viewer.illustrate_overlay
    overlay.editing = True
    circle = overlay.layer.create("circle", 40.0, 40.0, radius=20.0)

    overlay.handle_event("press", QPointF(60.0, 40.0))
    overlay.handle_event("release", QPointF(60.0, 40.0))
    assert overlay.layer.selection() == [circle]
    assert len(overlay.layer) == 1


def test_dragging_a_selected_element_moves_it(main_window):
    overlay = main_window.image_viewer.illustrate_overlay
    overlay.editing = True
    circle = overlay.layer.create("circle", 40.0, 40.0, radius=20.0)

    overlay.handle_event("press", QPointF(60.0, 40.0))
    overlay.handle_event("move", QPointF(70.0, 50.0))
    overlay.handle_event("release", QPointF(70.0, 50.0))
    assert circle.center == (50.0, 50.0)


def test_dragging_a_handle_reshapes_rather_than_moves(main_window):
    overlay = main_window.image_viewer.illustrate_overlay
    overlay.editing = True
    box = overlay.layer.create("box", 50.0, 50.0, radius1=10.0, radius2=10.0)
    box.selected = True
    corner = box.handles()[0]

    overlay.handle_event("press", QPointF(*corner))
    overlay.handle_event("move", QPointF(20.0, 30.0))
    overlay.handle_event("release", QPointF(20.0, 30.0))
    assert box.center == (50.0, 50.0)
    assert box.radius1 == pytest.approx(30.0)


def test_the_overlay_ignores_the_mouse_outside_the_mode(main_window):
    overlay = main_window.image_viewer.illustrate_overlay
    overlay.editing = False
    assert overlay.handle_event("press", QPointF(10.0, 10.0)) is False
    assert len(overlay.layer) == 0


def test_a_right_click_is_not_the_layers_business(main_window):
    overlay = main_window.image_viewer.illustrate_overlay
    overlay.editing = True
    assert overlay.handle_event("press", QPointF(10.0, 10.0), "right") is False


def test_the_layer_draws_without_raising(main_window):
    """Every shape through the painter once, since a paint error is silent."""
    overlay = main_window.image_viewer.illustrate_overlay
    for shape in SHAPES:
        element = overlay.layer.create(shape, 50.0, 50.0)
        element.selected = True
        if shape == "text":
            element.text = "two\nlines"
            element.angle = 30.0
    overlay.resize(200, 200)
    painted = overlay.grab().toImage()
    assert not painted.isNull()
    # Something was actually drawn, or this would pass with a broken painter.
    colours = {painted.pixel(x, y) for x in range(0, 200, 4) for y in range(0, 200, 4)}
    assert len(colours) > 1


# -- the Get Information dialog -------------------------------------------------------------


@pytest.fixture
def dialog(main_window):
    main_window.menu_bar.action_illustrate_info.trigger()
    made = main_window.illustrate._dialog
    assert made is not None
    yield made
    made.close()


def test_the_dialog_says_when_nothing_is_selected(dialog):
    assert "No illustration selected" in dialog._what.text()


def test_the_dialog_shows_the_selected_shapes_own_rows(dialog, main_window):
    circle = main_window.illustrate.layer.create("circle", 20.0, 30.0, radius=5.0)
    circle.selected = True
    dialog.reload()

    assert "Circle" in dialog._what.text()
    assert dialog._radius.value() == pytest.approx(5.0)
    assert dialog._rows["radius"].isVisibleTo(dialog)
    # An ellipse's second radius has no meaning for a circle.
    assert not dialog._rows["radii"].isVisibleTo(dialog)


def test_the_dialog_edits_the_selected_shape(dialog, main_window):
    circle = main_window.illustrate.layer.create("circle", 20.0, 30.0, radius=5.0)
    circle.selected = True
    dialog.reload()

    dialog._x.setValue(60.0)
    dialog._radius.setValue(15.0)
    dialog._color.setCurrentText("red")
    dialog._fill.setChecked(True)
    dialog.apply_changes()

    assert circle.x == 60.0
    assert circle.radius == 15.0
    assert circle.style.color == "red"
    assert circle.style.fill is True


def test_the_dialog_edits_a_caption(dialog, main_window):
    text = main_window.illustrate.layer.create("text", 20.0, 30.0)
    text.selected = True
    dialog.reload()

    dialog._text.setPlainText("a caption")
    dialog._font_size.setValue(24)
    dialog._angle.setValue(45.0)
    dialog._justify.setCurrentText("center")
    dialog.apply_changes()

    assert text.text == "a caption"
    assert text.font_size == 24
    assert text.angle == 45.0
    assert text.justify == "center"


def test_the_dialog_sets_a_lines_arrowheads(dialog, main_window):
    line = main_window.illustrate.layer.create("line", 20.0, 30.0)
    line.selected = True
    dialog.reload()

    dialog._arrow_last.setChecked(True)
    dialog.apply_changes()
    assert line.arrow_last is True
    assert line.arrow_first is False


def test_the_dialog_deletes_what_it_is_showing(dialog, main_window):
    main_window.illustrate.layer.create("circle", 20.0, 30.0).selected = True
    dialog.buttons["delete"].click()
    assert len(main_window.illustrate.layer) == 0
    assert "No illustration selected" in dialog._what.text()


def test_the_dialog_shows_the_one_that_was_just_clicked(dialog, main_window):
    """A click selects one element alone, and the dialog follows it."""
    overlay = main_window.image_viewer.illustrate_overlay
    overlay.editing = True
    circle = overlay.layer.create("circle", 40.0, 40.0, radius=20.0)
    overlay.handle_event("press", QPointF(60.0, 40.0))
    overlay.handle_event("release", QPointF(60.0, 40.0))

    assert main_window.illustrate.selected() is circle
    assert "Circle" in dialog._what.text()


def test_asking_for_the_dialog_twice_reuses_it(main_window):
    main_window.illustrate.show_dialog()
    first = main_window.illustrate._dialog
    main_window.illustrate.show_dialog()
    assert main_window.illustrate._dialog is first
    first.close()


def test_applying_with_nothing_selected_does_nothing(dialog):
    dialog.apply_changes()
    dialog.delete_element()


def test_the_default_colour_is_ds9s_cyan(main_window):
    assert main_window.illustrate.layer.style.color == DEFAULT_COLOR
    assert main_window.menu_bar.illustrate_color_actions["cyan"].isChecked()


def test_an_ellipse_and_a_box_share_the_two_radius_rows(dialog, main_window):
    for shape in ("ellipse", "box"):
        main_window.illustrate.layer.clear()
        element = main_window.illustrate.layer.create(shape, 20.0, 30.0)
        element.selected = True
        dialog.reload()
        assert dialog._rows["radii"].isVisibleTo(dialog)
        dialog._radius1.setValue(11.0)
        dialog._radius2.setValue(22.0)
        dialog.apply_changes()
        assert (element.radius1, element.radius2) == (11.0, 22.0)


def test_an_images_rows_are_its_file_and_its_size(dialog, main_window):
    image = main_window.illustrate.layer.create("image", 20.0, 30.0, path="/tmp/a.png")
    image.width = image.height = 10.0
    image.selected = True
    dialog.reload()

    assert "/tmp/a.png" in dialog._path.text()
    dialog._size_w.setValue(40.0)
    dialog._size_h.setValue(20.0)
    dialog.apply_changes()
    assert (image.width, image.height) == (40.0, 20.0)
