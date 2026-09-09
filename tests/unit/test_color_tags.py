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


"""Colour tags, the Colorbar pointer mode, and several colorbars at once."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.colormaps.color_tags import (
    DEFAULT_TAG_COLOR,
    TAG_COLORS,
    ColorTag,
    ColorTagError,
    ColorTagSet,
    parse_color,
)
from ncrads9.ui.widgets.colorbar_widget import MAX_BARS, ColorbarEntry, ColorbarWidget

#: A grey ramp, as the widget and the tag set both expect.
GREY = np.tile(np.linspace(0.0, 1.0, 256)[:, None], (1, 3))


# -- the tag model (M5-11) ---------------------------------------------------


def test_a_tag_is_ordered_and_clamped():
    assert (ColorTag(0.9, 0.2).start, ColorTag(0.9, 0.2).stop) == (0.2, 0.9)
    assert (ColorTag(-5.0, 99.0).start, ColorTag(-5.0, 99.0).stop) == (0.0, 1.0)


def test_ds9s_tag_colours_are_offered():
    assert set(TAG_COLORS) == {
        "black",
        "white",
        "red",
        "green",
        "blue",
        "cyan",
        "magenta",
        "yellow",
    }


@pytest.mark.parametrize(
    ("name", "rgb"),
    [("red", (1.0, 0.0, 0.0)), ("#00ff00", (0.0, 1.0, 0.0)), ("0000ff", (0.0, 0.0, 1.0))],
)
def test_colours_parse_by_name_and_by_hex(name, rgb):
    assert parse_color(name) == pytest.approx(rgb)


@pytest.mark.parametrize("name", ["chartreuse", "#12345", "", "#gggggg"])
def test_an_unknown_colour_is_refused(name):
    with pytest.raises(ColorTagError):
        parse_color(name)


def test_a_tag_covers_its_range():
    tag = ColorTag(0.25, 0.75)
    assert tag.contains(0.25) and tag.contains(0.5) and tag.contains(0.75)
    assert not tag.contains(0.2) and not tag.contains(0.8)


def test_tags_paint_a_flat_colour_over_their_range():
    tags = ColorTagSet([ColorTag(0.0, 0.1, "blue"), ColorTag(0.9, 1.0, "red")])
    painted = tags.apply(GREY)
    assert painted[0].tolist() == pytest.approx([0.0, 0.0, 1.0])
    assert painted[-1].tolist() == pytest.approx([1.0, 0.0, 0.0])
    # The middle is untouched.
    assert painted[128].tolist() == pytest.approx(GREY[128].tolist())


def test_an_untagged_set_does_not_copy_the_table():
    assert ColorTagSet().apply(GREY) is GREY


def test_applying_leaves_the_input_alone():
    original = GREY.copy()
    ColorTagSet([ColorTag(0.0, 1.0, "red")]).apply(GREY)
    assert np.array_equal(GREY, original)


def test_the_newest_tag_wins_an_overlap():
    tags = ColorTagSet([ColorTag(0.0, 1.0, "blue"), ColorTag(0.4, 0.6, "red")])
    assert tags.index_at(0.5) == 1
    assert tags.apply(GREY)[128].tolist() == pytest.approx([1.0, 0.0, 0.0])


def test_index_at_finds_nothing_outside_every_tag():
    assert ColorTagSet([ColorTag(0.0, 0.1)]).index_at(0.5) is None


def test_tags_can_be_replaced_and_removed():
    tags = ColorTagSet([ColorTag(0.0, 0.1), ColorTag(0.9, 1.0)])
    tags.replace(0, ColorTag(0.2, 0.3, "green"))
    assert tags.tags[0].color == "green"
    tags.remove(0)
    assert len(tags) == 1
    tags.clear()
    assert not tags


def test_replacing_or_removing_a_missing_tag_raises():
    tags = ColorTagSet()
    with pytest.raises(IndexError):
        tags.remove(0)
    with pytest.raises(IndexError):
        tags.replace(3, ColorTag(0.0, 1.0))


# -- DS9's tag files ---------------------------------------------------------


def test_the_file_format_is_start_stop_colour():
    text = ColorTagSet([ColorTag(0.2, 0.8, "green")]).to_text()
    assert text.strip() == "0.2 0.8 green"


def test_tag_files_round_trip():
    tags = ColorTagSet([ColorTag(0.0, 0.1, "blue"), ColorTag(0.85, 1.0, "#ff8800")])
    reloaded = ColorTagSet.from_text(tags.to_text())
    assert [str(tag) for tag in reloaded] == [str(tag) for tag in tags]


def test_comments_and_blank_lines_are_ignored():
    tags = ColorTagSet.from_text("# a comment\n\n0.1 0.2 red   # trailing\n")
    assert len(tags) == 1
    assert tags.tags[0].color == "red"


def test_a_missing_colour_takes_the_default():
    assert ColorTagSet.from_text("0.1 0.2\n").tags[0].color == DEFAULT_TAG_COLOR


@pytest.mark.parametrize("text", ["nonsense\n", "0.1\n", "low high red\n"])
def test_a_bad_tag_file_line_is_reported(text):
    with pytest.raises(ColorTagError):
        ColorTagSet.from_text(text)


def test_tags_save_and_load_through_a_file(tmp_path):
    path = tmp_path / "tags.tag"
    ColorTagSet([ColorTag(0.3, 0.4, "cyan")]).save(path)
    assert ColorTagSet.load(path).tags[0].color == "cyan"


# -- the colorbar widget (M5-12) --------------------------------------------


@pytest.fixture
def colorbar(qapp):
    widget = ColorbarWidget()
    widget.resize(400, 90)
    yield widget
    widget.deleteLater()


def test_one_colormap_is_one_bar(colorbar):
    colorbar.set_colormap(GREY, 0.0, 10.0, "grey")
    assert colorbar.bar_count == 1
    assert colorbar.colorbar_label.pixmap() is not None


def test_several_entries_are_several_bars(colorbar):
    colorbar.set_colorbars([ColorbarEntry(GREY, 0.0, 1.0, "a"), ColorbarEntry(GREY, 0.0, 2.0, "b")])
    assert colorbar.bar_count == 2
    assert colorbar.name_label.text() == "a · b"


def test_the_single_bar_attributes_still_read(colorbar):
    """XPA and the Colormap Parameters dialog read them."""
    colorbar.set_colorbars([ColorbarEntry(GREY, 3.0, 7.0, "first"), ColorbarEntry(GREY, 0.0, 1.0)])
    assert (colorbar.vmin, colorbar.vmax) == (3.0, 7.0)
    assert colorbar.colormap_name == "first"


def test_too_many_bars_are_capped(colorbar):
    colorbar.set_colorbars([ColorbarEntry(GREY, 0.0, 1.0, str(i)) for i in range(50)])
    assert colorbar.bar_count == MAX_BARS


def test_no_entries_clears_the_bar(colorbar):
    colorbar.set_colormap(GREY, 0.0, 1.0, "grey")
    colorbar.set_colorbars([])
    pixmap = colorbar.colorbar_label.pixmap()
    assert pixmap is None or pixmap.isNull()


def test_both_orientations_draw(colorbar):
    for orientation in ("horizontal", "vertical"):
        colorbar.set_orientation(orientation)
        colorbar.set_colorbars([ColorbarEntry(GREY, 0.0, 1.0, "a"), ColorbarEntry(GREY, 0.0, 1.0, "b")])
        assert not colorbar.colorbar_label.pixmap().isNull(), orientation


def test_clicking_reports_a_position_along_the_bar(colorbar):
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QMouseEvent

    colorbar.set_colormap(GREY, 0.0, 1.0, "grey")
    colorbar.show()
    seen: list[float] = []
    colorbar.clicked.connect(seen.append)

    label = colorbar.colorbar_label
    pixmap = label.pixmap()
    middle = label.mapTo(colorbar, QPoint(pixmap.width() // 2, pixmap.height() // 2))
    colorbar.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(middle),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert seen and 0.0 <= seen[0] <= 1.0
    assert seen[0] == pytest.approx(0.5, abs=0.1)


# -- in a window -------------------------------------------------------------


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
    window.resize(700, 600)
    window.display.load_fits("ncrads9/sampleimages/SDSS9_M51_r.fits")
    yield window
    window.close()


def test_tags_are_held_per_frame(main_window):
    main_window.color.add_tag(0.9, 1.0, "red")
    first = main_window.frame_manager.current_frame

    main_window.frame_controller.new_frame()
    main_window.display.load_fits("ncrads9/sampleimages/SDSS9_M51_g.fits")
    assert len(main_window.color.tags()) == 0
    assert len(main_window.color.tags(first)) == 1


def test_a_tag_reaches_the_rendered_colormap(main_window):
    from ncrads9.colormaps.colormap import Colormap

    plain = main_window.color.colormap("grey")
    assert main_window.color.apply_tags(plain) is plain

    main_window.color.add_tag(0.0, 1.0, "red")
    tagged = main_window.color.apply_tags(plain)
    assert isinstance(tagged, Colormap)
    assert tagged.colors[128].tolist() == pytest.approx([1.0, 0.0, 0.0])


def test_a_tag_reaches_the_colorbar(main_window):
    main_window.color.add_tag(0.0, 1.0, "blue")
    shown = main_window.colorbar_widget.colormap_data
    assert shown[128].tolist() == pytest.approx([0.0, 0.0, 1.0])


def test_tags_survive_a_colormap_change(main_window):
    """A tag marks a place in the table, not a colour of its own."""
    main_window.color.add_tag(0.9, 1.0, "red")
    main_window.color.set_colormap("heat")
    assert len(main_window.color.tags()) == 1
    assert main_window.colorbar_widget.colormap_data[-1].tolist() == pytest.approx([1.0, 0.0, 0.0])


def test_deleting_tags_restores_the_table(main_window):
    main_window.color.add_tag(0.0, 1.0, "red")
    main_window.color.delete_tags()
    assert len(main_window.color.tags()) == 0
    assert "Deleted 1 colour tag" in main_window.status_bar.currentMessage()


def test_deleting_with_no_tags_says_so(main_window):
    main_window.color.delete_tags()
    assert "No colour tags to delete" in main_window.status_bar.currentMessage()


def test_an_impossible_tag_colour_is_reported(main_window):
    main_window.color.add_tag(0.0, 1.0, "chartreuse")
    assert "not a colour" in main_window.status_bar.currentMessage()
    assert len(main_window.color.tags()) == 0


def test_tags_round_trip_through_a_file(main_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    path = tmp_path / "frame.tag"
    main_window.color.add_tag(0.2, 0.3, "cyan")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))
    main_window.color.save_tags()

    main_window.color.delete_tags()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
    main_window.color.load_tags()
    assert [str(tag) for tag in main_window.color.tags()] == ["0.2 0.3 cyan"]


def test_a_bad_tag_file_is_reported(main_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    path = tmp_path / "bad.tag"
    path.write_text("nonsense\n")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
    main_window.color.load_tags()
    assert "Error loading colour tags" in main_window.status_bar.currentMessage()


# -- the Colorbar pointer mode (M5-13) --------------------------------------


def test_ds9s_pointer_modes_are_all_offered(main_window):
    from ncrads9.ui.menu_bar import EDIT_MODES

    names = [name for name, _label in EDIT_MODES]
    assert names[:5] == ["none", "region", "crosshair", "colorbar", "pan"]
    assert set(main_window.menu_bar.edit_mode_actions) == set(names)


def test_choosing_a_mode_records_and_ticks_it(main_window):
    main_window.menu_bar.edit_mode_actions["colorbar"].trigger()
    assert main_window.edit_mode == "colorbar"
    assert main_window.menu_bar.edit_mode_actions["colorbar"].isChecked()


def test_a_deferred_mode_says_its_milestone(main_window):
    from ncrads9.ui.controllers.edit import DEFERRED_MODES

    main_window.edit.set_mode("crop")
    assert DEFERRED_MODES["crop"] in main_window.status_bar.currentMessage()


def test_an_unknown_mode_is_reported(main_window):
    main_window.edit.set_mode("teleport")
    assert "Unknown edit mode" in main_window.status_bar.currentMessage()


def test_clicking_the_colorbar_does_nothing_outside_colorbar_mode(main_window):
    main_window.edit.set_mode("none")
    main_window.color.on_colorbar_clicked(0.5)
    assert len(main_window.color.tags()) == 0


def test_clicking_the_colorbar_in_colorbar_mode_makes_a_tag(main_window, monkeypatch):
    from ncrads9.ui.dialogs import color_tag_dialog

    monkeypatch.setattr(color_tag_dialog.ColorTagDialog, "exec", lambda self: 0)
    main_window.edit.set_mode("colorbar")
    main_window.color.on_colorbar_clicked(0.5)
    assert len(main_window.color.tags()) == 1
    assert main_window.color.tags().tags[0].contains(0.5)


def test_clicking_an_existing_tag_edits_rather_than_adds(main_window, monkeypatch):
    from ncrads9.ui.dialogs import color_tag_dialog

    monkeypatch.setattr(color_tag_dialog.ColorTagDialog, "exec", lambda self: 0)
    main_window.color.add_tag(0.4, 0.6, "red")
    main_window.edit.set_mode("colorbar")
    main_window.color.on_colorbar_clicked(0.5)
    assert len(main_window.color.tags()) == 1


def test_the_dialog_can_delete_the_tag_it_opened(main_window, monkeypatch):
    from ncrads9.ui.dialogs.color_tag_dialog import ColorTagDialog

    monkeypatch.setattr(ColorTagDialog, "exec", lambda self: ColorTagDialog.DELETED)
    main_window.color.add_tag(0.4, 0.6, "red")
    main_window.color.show_tag_dialog(0)
    assert len(main_window.color.tags()) == 0


def test_resetting_contrast_and_bias(main_window):
    main_window.image_viewer.image_viewer.set_contrast_brightness(2.5, 0.4)
    main_window.color.reset_contrast_bias()
    contrast, brightness = main_window.image_viewer.get_contrast_brightness()
    assert contrast == pytest.approx(1.0)
    assert brightness == pytest.approx(0.0)
    assert "reset" in main_window.status_bar.currentMessage()


# -- several colorbars (M5-12) ----------------------------------------------


def test_a_colour_frame_shows_one_bar_per_channel(main_window):
    main_window.frame_controller.new_frame_of_type("rgb")
    frame = main_window.frame_manager.current_frame
    for channel, band in (("red", "i"), ("green", "r"), ("blue", "g")):
        frame.rgb_channels[channel] = fits.getdata(f"ncrads9/sampleimages/SDSS9_M51_{band}.fits").astype(
            np.float32
        )
    frame.rgb_current_channel = "red"
    main_window.display.sync_rgb_scalar_view(frame)
    main_window.display.display()

    assert main_window.colorbar_widget.bar_count == 3
    assert main_window.colorbar_widget.name_label.text() == "red · green · blue"


def test_tiled_frames_show_one_bar_each(main_window):
    for band in ("g", "i"):
        main_window.frame_controller.new_frame()
        main_window.display.load_fits(f"ncrads9/sampleimages/SDSS9_M51_{band}.fits")
    main_window.frame_controller.set_tile(True)
    assert main_window.colorbar_widget.bar_count == 3


def test_turning_multiple_colorbars_off_leaves_one(main_window):
    for band in ("g", "i"):
        main_window.frame_controller.new_frame()
        main_window.display.load_fits(f"ncrads9/sampleimages/SDSS9_M51_{band}.fits")
    main_window.frame_controller.set_tile(True)
    main_window.menu_bar.action_view_multi_colorbar.setChecked(False)
    main_window.display.display()
    assert main_window.colorbar_widget.bar_count == 1


def test_a_single_frame_shows_one_bar_however_multi_is_set(main_window):
    assert main_window.view_state.multi
    assert main_window.colorbar_widget.bar_count == 1


def test_multiple_colorbars_no_longer_announces_itself_as_deferred(main_window):
    """It said "has no effect until M5" until M5-12 gave it an effect."""
    from ncrads9.ui.controllers.view import UNIMPLEMENTED_PANELS

    assert "multi" not in UNIMPLEMENTED_PANELS
    main_window.menu_bar.action_view_multi_colorbar.setChecked(False)
    assert "no effect" not in main_window.status_bar.currentMessage()


def test_each_tiled_bar_carries_its_own_limits(main_window):
    for band in ("g", "i"):
        main_window.frame_controller.new_frame()
        main_window.display.load_fits(f"ncrads9/sampleimages/SDSS9_M51_{band}.fits")
    frames = main_window.frame_manager.frames
    frames[0].z1, frames[0].z2 = 0.0, 1.0
    frames[1].z1, frames[1].z2 = 10.0, 20.0
    main_window.frame_controller.set_tile(True)

    entries = main_window.display.colorbar_entries(
        main_window.frame_manager.current_frame,
        main_window.color.colormap("grey"),
        0.0,
        1.0,
    )
    assert (entries[0].vmin, entries[0].vmax) == (0.0, 1.0)
    assert (entries[1].vmin, entries[1].vmax) == (10.0, 20.0)
