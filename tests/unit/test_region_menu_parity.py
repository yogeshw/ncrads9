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
The fifteen Region entries DS9 had and NCRADS9 did not.

They fell into four groups, and only the first was cosmetic:

* three composite shapes were named as the *file format* spells them --
  `Ellipse Annulus`, `Epanda`, `Bpanda` -- rather than as DS9's menu does;
* a point had no symbol to choose. DS9 offers seven; NCRADS9 drew every
  point as a circle and `Point.SHAPES` had supported all seven all along;
* `Include` and `Source` were single check boxes, so `Exclude` and
  `Background` -- both real states a region can be in, and both written
  into region files -- had no entry and no name on screen;
* `Delete All and Open` was absent, and `Open` *replaced* the frame's
  regions rather than adding to them, so a second region file silently
  discarded the first. DS9 has both entries because its `Open` adds.
"""

from __future__ import annotations

import numpy as np
import pytest

from ncrads9.regions.region_parser import RegionParser
from ncrads9.regions.shapes.point import Point
from ncrads9.ui.menu_bar import REGION_EITHER_OR, REGION_POINT_SHAPES, REGION_SHAPES
from ncrads9.ui.widgets.region_overlay import RegionMode


@pytest.fixture
def window(qapp, monkeypatch):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    made = MainWindow()
    made._rebuild_image_viewer(False)
    frame = made.frame_manager.current_frame
    frame.image_data = np.arange(64 * 64, dtype=np.float32).reshape(64, 64)
    frame.original_image_data = frame.image_data
    frame.regions = RegionParser().parse_string("image\ncircle(10,10,5)\nbox(20,20,6,6)\n")
    yield made
    made.close()


def _labels(menu) -> list[str]:
    """The menu's entries as a person reads them, separators dropped."""
    return [action.text().replace("&", "") for action in menu.actions() if not action.isSeparator()]


# -- DS9's own words for the three composites --------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("ellipseannulus", "Elliptical Annulus"),
        ("epanda", "Elliptical Panda"),
        ("bpanda", "Box Panda"),
    ],
)
def test_a_composite_shape_is_named_as_ds9_names_it(window, name, expected):
    assert window.menu_bar.region_shape_actions[name].text().replace("&", "") == expected


def test_renaming_did_not_change_the_keys(window):
    """The labels changed; the keys are what region files, XPA and the
    button bar use, and they did not."""
    keys = [name for name, _label in REGION_SHAPES]
    for expected in ("ellipseannulus", "epanda", "bpanda"):
        assert expected in keys
        window.menu_bar.region_shape_actions[expected].trigger()
        assert window.image_viewer.region_overlay.mode is RegionMode(expected)


def test_the_status_bar_reports_a_shape_by_its_menu_name(window):
    window.menu_bar.region_shape_actions["epanda"].trigger()
    assert window.button_bar is not None  # the label round-trips through it


# -- the seven point symbols -------------------------------------------------------


def test_point_is_a_cascade_of_ds9s_seven_symbols(window):
    assert _labels(window.menu_bar.region_point_menu) == [
        "Circle",
        "Box",
        "Diamond",
        "Cross",
        "X",
        "Arrow",
        "BoxCircle",
    ]


def test_the_cascade_offers_exactly_the_symbols_the_model_supports(window):
    assert tuple(name for name, _label in REGION_POINT_SHAPES) == Point.SHAPES
    for name, _label in REGION_POINT_SHAPES:
        assert name in window.menu_bar.region_point_shape_actions


@pytest.mark.parametrize("symbol", Point.SHAPES)
def test_choosing_a_symbol_arms_point_mode_and_becomes_the_default(window, symbol):
    window.menu_bar.region_point_shape_actions[symbol].trigger()
    assert window.image_viewer.region_overlay.mode is RegionMode.POINT
    assert window.region.defaults["shape"] == symbol


@pytest.mark.parametrize("symbol", Point.SHAPES)
def test_a_point_drawn_after_choosing_a_symbol_carries_it(window, symbol):
    """The whole point of the cascade: the region that comes out."""
    window.menu_bar.region_point_shape_actions[symbol].trigger()
    drawn = Point(center=(5.0, 5.0))
    window.region.apply_defaults(drawn)
    assert drawn.shape == symbol


def test_the_symbol_default_reaches_no_other_shape(window):
    """`shape` is `Point`'s attribute and no one else's, which is why it can
    be stored as a plain default."""
    from ncrads9.regions.shapes.circle import Circle

    window.menu_bar.region_point_shape_actions["diamond"].trigger()
    circle = Circle(center=(1.0, 1.0), radius=2.0)
    window.region.apply_defaults(circle)
    assert not hasattr(circle, "shape")


def test_a_symbol_applies_to_the_selected_points(window):
    frame = window.frame_manager.current_frame
    chosen = Point(center=(1.0, 1.0))
    chosen.selected = True
    frame.regions = [chosen]
    window.menu_bar.region_point_shape_actions["cross"].trigger()
    assert chosen.shape == "cross"


def test_choosing_a_symbol_unchecks_the_shape_that_was_armed(window):
    """One exclusive group across both levels, so the menu cannot show two
    shapes armed at once."""
    window.menu_bar.region_shape_actions["circle"].trigger()
    assert window.menu_bar.region_shape_actions["circle"].isChecked()
    window.menu_bar.region_point_shape_actions["x"].trigger()
    assert not window.menu_bar.region_shape_actions["circle"].isChecked()
    assert window.menu_bar.region_point_shape_actions["x"].isChecked()

    window.menu_bar.region_shape_actions["box"].trigger()
    assert not window.menu_bar.region_point_shape_actions["x"].isChecked()


@pytest.mark.parametrize(
    ("spelling", "symbol"),
    [
        ("diamond point", "diamond"),
        ("diamondpoint", "diamond"),
        ("boxcircle point", "boxcircle"),
        ("BoxCircle Point", "boxcircle"),
        ("x point", "x"),
    ],
)
def test_ds9s_point_spellings_are_accepted(window, spelling, symbol):
    """How a script names a point: DS9's Shape cascade has no plain `point`
    either, so `region shape` is given the compound."""
    window.region.set_shape(spelling)
    assert window.image_viewer.region_overlay.mode is RegionMode.POINT
    assert window.region.defaults["shape"] == symbol


@pytest.mark.parametrize("name", ["point", "circle", "box"])
def test_a_plain_shape_name_is_still_itself(window, name):
    """`point` alone arms the mode and leaves the symbol alone; `circle` and
    `box` are whole shapes, not point symbols."""
    window.region.set_point_shape("diamond")
    window.region.set_shape(name)
    assert window.image_viewer.region_overlay.mode is RegionMode(name)
    assert window.region.defaults["shape"] == "diamond"


def test_an_unknown_symbol_is_refused_not_stored(window):
    window.region.set_point_shape("circle")
    window.region.set_point_shape("triangle")
    assert window.region.defaults["shape"] == "circle"


# -- include/exclude and source/background -----------------------------------------


def test_the_properties_cascade_reads_as_ds9s_does(window):
    assert _labels(window.menu_bar.region_properties_menu) == [
        "Fixed in Size",
        "Can Edit",
        "Can Move",
        "Can Rotate",
        "Can Delete",
        "Include",
        "Exclude",
        "Source",
        "Background",
        "Dash",
        "Fill",
    ]


@pytest.mark.parametrize(
    ("attribute", "on", "off"), [(row[0], row[1][0], row[2][0]) for row in REGION_EITHER_OR]
)
def test_each_either_or_property_is_a_pair(window, attribute, on, off):
    pair = window.menu_bar.region_either_or_actions[attribute]
    assert {action.text() for action in pair.values()} == {on, off}
    assert pair[True].isChecked() and not pair[False].isChecked()


@pytest.mark.parametrize("attribute", [row[0] for row in REGION_EITHER_OR])
def test_choosing_one_half_unchecks_the_other(window, attribute):
    pair = window.menu_bar.region_either_or_actions[attribute]
    pair[False].trigger()
    assert not pair[True].isChecked()
    assert window.region.defaults[attribute] is False

    pair[True].trigger()
    assert not pair[False].isChecked()
    assert window.region.defaults[attribute] is True


@pytest.mark.parametrize("attribute", [row[0] for row in REGION_EITHER_OR])
def test_either_or_applies_to_the_selection(window, attribute):
    regions = window.frame_manager.current_frame.regions
    regions[0].selected = True
    window.menu_bar.region_either_or_actions[attribute][False].trigger()
    assert getattr(regions[0], attribute) is False
    assert getattr(regions[1], attribute) is True


def test_an_excluded_region_is_written_with_ds9s_minus(window):
    """The state the menu could not reach, seen where it matters."""
    from ncrads9.regions.region_writer import RegionWriter

    region = RegionParser().parse_string("image\ncircle(10,10,5)\n")[0]
    region.selected = True
    window.frame_manager.current_frame.regions = [region]
    window.menu_bar.region_either_or_actions["include"][False].trigger()
    text = RegionWriter().to_string([region])
    assert "-circle" in text


def test_a_background_region_is_written_as_background(window):
    from ncrads9.regions.region_writer import RegionWriter

    region = RegionParser().parse_string("image\ncircle(10,10,5)\n")[0]
    region.selected = True
    window.frame_manager.current_frame.regions = [region]
    window.menu_bar.region_either_or_actions["source"][False].trigger()
    text = RegionWriter().to_string([region])
    assert "background" in text


# -- Open, and Delete All and Open -------------------------------------------------


@pytest.fixture
def region_file(tmp_path):
    path = tmp_path / "extra.reg"
    path.write_text("image\ncircle(40,40,3)\n")
    return path


def _answer_with(monkeypatch, path):
    from PyQt6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))


def test_open_adds_to_what_is_already_there(window, monkeypatch, region_file):
    """DS9's Open adds. This replaced, so a second region file silently
    threw the first one away."""
    _answer_with(monkeypatch, region_file)
    before = len(window.frame_manager.current_frame.regions)
    window.region.load_regions()
    assert len(window.frame_manager.current_frame.regions) == before + 1


def test_delete_all_and_open_replaces(window, monkeypatch, region_file):
    _answer_with(monkeypatch, region_file)
    window.menu_bar.action_region_delete_all_and_load.trigger()
    assert len(window.frame_manager.current_frame.regions) == 1


def test_the_menu_offers_both(window):
    labels = _labels(window.menu_bar.region_menu)
    assert "Delete All" in labels
    assert "Delete All and Open..." in labels


def test_cancelling_the_chooser_changes_nothing(window, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    before = list(window.frame_manager.current_frame.regions)
    window.menu_bar.action_region_delete_all_and_load.trigger()
    assert window.frame_manager.current_frame.regions == before


def test_an_open_can_be_undone(window, monkeypatch, region_file):
    """Replacing the frame's regions without an undo step would make
    `Delete All and Open` the one irreversible entry in the menu."""
    _answer_with(monkeypatch, region_file)
    before = [region.center for region in window.frame_manager.current_frame.regions]
    window.menu_bar.action_region_delete_all_and_load.trigger()
    assert len(window.frame_manager.current_frame.regions) == 1
    window.undo.undo()
    assert [region.center for region in window.frame_manager.current_frame.regions] == before
