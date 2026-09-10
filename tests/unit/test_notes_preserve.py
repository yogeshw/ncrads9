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

"""DS9's Notes and Preserve During Load (M9-16, M9-17)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

SIZE = 32


@pytest.fixture
def image(tmp_path):
    rows, columns = np.indices((SIZE, SIZE))
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32)).writeto(path)
    return path


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path, image):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(image))
    yield window
    window.close()


# -- Notes ---------------------------------------------------------------------------


def test_the_file_menu_has_notes_and_header(main_window):
    """DS9 keeps Header on File, not on Analysis where ours used to be."""
    labels = [
        action.text().replace("&", "")
        for action in main_window.menu_bar.file_menu.actions()
        if not action.isSeparator()
    ]
    assert "Notes..." in labels
    assert "Header..." in labels

    analysis = [
        action.text().replace("&", "")
        for action in main_window.menu_bar.analysis_menu.actions()
        if not action.isSeparator()
    ]
    assert "FITS Header" not in analysis


def test_the_notes_window_opens_empty(main_window):
    dialog = main_window.notes.show_dialog()
    assert dialog.text.toPlainText() == ""
    dialog.close()


def test_typing_reaches_the_controller(main_window):
    """The controller's copy is what the backup writes, so it must not lag
    behind the window."""
    dialog = main_window.notes.show_dialog()
    dialog.text.setPlainText("seeing was poor")
    assert main_window.notes.text == "seeing was poor"
    dialog.close()


def test_the_text_survives_the_window_being_closed(main_window):
    dialog = main_window.notes.show_dialog()
    dialog.text.setPlainText("kept")
    dialog.close()
    dialog.reject()

    again = main_window.notes.show_dialog()
    assert again.text.toPlainText() == "kept"
    again.close()


def test_asking_for_the_window_twice_reuses_it(main_window):
    first = main_window.notes.show_dialog()
    assert main_window.notes.show_dialog() is first
    first.close()


def test_append_insert_and_clear(main_window):
    main_window.notes.append("second")
    main_window.notes.insert("first")
    assert main_window.notes.text == "first\nsecond\n"
    main_window.notes.clear()
    assert main_window.notes.text == ""


def test_the_window_follows_the_controller(main_window):
    dialog = main_window.notes.show_dialog()
    main_window.notes.append("from xpa")
    assert "from xpa" in dialog.text.toPlainText()
    dialog.close()


def test_notes_round_trip_through_a_file(main_window, tmp_path):
    main_window.notes.append("a line")
    path = tmp_path / "notes.txt"
    assert main_window.notes.save(path) is True

    main_window.notes.clear()
    assert main_window.notes.load(path) is True
    assert "a line" in main_window.notes.text


def test_loading_notes_that_are_not_there_is_reported(main_window, tmp_path):
    assert main_window.notes.load(tmp_path / "nope.txt") is False
    assert "Could not read" in main_window.status_bar.currentMessage()


def test_saving_notes_where_they_cannot_go_is_reported(main_window, tmp_path):
    blocked = tmp_path / "afile"
    blocked.write_text("in the way")
    assert main_window.notes.save(blocked / "notes.txt") is False
    assert "Could not write" in main_window.status_bar.currentMessage()


def test_the_windows_own_file_menu_reads_and_writes(main_window, tmp_path):
    dialog = main_window.notes.show_dialog()
    dialog.text.setPlainText("written from the window")
    path = tmp_path / "w.txt"
    assert dialog.save_file(str(path)) is True

    dialog.clear()
    assert dialog.open_file(str(path)) is True
    assert dialog.text.toPlainText() == "written from the window"
    dialog.close()


def test_the_windows_menus_are_ds9s(main_window):
    dialog = main_window.notes.show_dialog()
    for name in (
        "open",
        "save",
        "close",
        "cut",
        "copy",
        "paste",
        "clear",
        "select_all",
        "select_none",
        "find",
        "find_next",
    ):
        assert name in dialog.actions_by_name
    dialog.close()


def test_find_and_find_next(main_window):
    dialog = main_window.notes.show_dialog()
    dialog.text.setPlainText("alpha beta alpha")
    assert dialog.find("alpha") is True
    assert dialog.find_next() is True
    assert dialog.find("gamma") is False
    dialog.close()


def test_the_notes_go_into_the_backup(main_window, tmp_path):
    """Which is the whole reason for having notes here rather than in a
    text editor beside the application."""
    main_window.notes.append("worth keeping")
    path = tmp_path / "s.bck"
    main_window.session.backup(str(path))

    main_window.notes.clear()
    main_window.session.restore(str(path))
    assert "worth keeping" in main_window.notes.text


# -- Preserve During Load ---------------------------------------------------------------


def test_the_menu_has_ds9s_two_entries(main_window):
    labels = [action.text().replace("&", "") for action in main_window.menu_bar.preserve_menu.actions()]
    assert labels == ["Pan", "Region"]


def test_both_are_off_by_default(main_window):
    """As DS9 has them: new data in a frame refits the view and clears the
    regions, which were drawn around things in the old data."""
    assert main_window.file.preserving("pan") is False
    assert main_window.file.preserving("regions") is False


def test_the_menu_turns_them_on(main_window):
    main_window.menu_bar.preserve_actions["pan"].setChecked(True)
    assert main_window.file.preserving("pan") is True
    assert "Preserve pan during load: on" in main_window.status_bar.currentMessage()


def test_without_preserve_pan_a_load_refits(main_window, image):
    main_window.zoom.set_zoom(8.0)
    main_window.display.load_fits(str(image))
    assert main_window.frame_manager.current_frame.zoom != pytest.approx(8.0)


def test_with_preserve_pan_a_load_keeps_the_view(main_window, image):
    """Which is the point of the setting: stepping through a series of
    images of the same field without losing your place."""
    main_window.file.set_preserve("pan", True)
    main_window.zoom.set_zoom(8.0)
    main_window.zoom.on_panner_pan(10.0, 12.0)
    frame = main_window.frame_manager.current_frame
    # Where the pan actually ended up: a small viewport clamps it, and what
    # matters is that the load leaves it there rather than refitting.
    was = (frame.pan_x, frame.pan_y)

    main_window.display.load_fits(str(image))
    frame = main_window.frame_manager.current_frame
    assert frame.zoom == pytest.approx(8.0)
    assert (frame.pan_x, frame.pan_y) == pytest.approx(was)


def test_without_preserve_regions_a_load_clears_them(main_window, image):
    from ncrads9.regions.shapes.circle import Circle

    frame = main_window.frame_manager.current_frame
    frame.regions = [Circle(center=(10.0, 10.0), radius=3.0)]
    main_window.display.load_fits(str(image))
    assert main_window.frame_manager.current_frame.regions == []


def test_with_preserve_regions_a_load_keeps_them(main_window, image):
    from ncrads9.regions.shapes.circle import Circle

    main_window.file.set_preserve("regions", True)
    frame = main_window.frame_manager.current_frame
    frame.regions = [Circle(center=(10.0, 10.0), radius=3.0)]

    main_window.display.load_fits(str(image))
    assert len(main_window.frame_manager.current_frame.regions) == 1


def test_the_settings_go_into_the_backup(main_window, tmp_path):
    main_window.file.set_preserve("pan", True)
    path = tmp_path / "s.bck"
    main_window.session.backup(str(path))

    main_window.file.set_preserve("pan", False)
    main_window.session.restore(str(path))
    assert main_window.file.preserving("pan") is True
    assert main_window.menu_bar.preserve_actions["pan"].isChecked() is True
