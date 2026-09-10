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

"""DS9's Backup, Restore and automatic backup (M9-11, M9-12)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.io.session import autosave, backup

SIZE = 40


def _header() -> fits.Header:
    return fits.Header(
        {
            "NAXIS": 2,
            "NAXIS1": SIZE,
            "NAXIS2": SIZE,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CRPIX1": SIZE / 2,
            "CRPIX2": SIZE / 2,
            "CRVAL1": 150.0,
            "CRVAL2": 2.0,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
        }
    )


# -- the file format -------------------------------------------------------------------


def test_a_backup_round_trips(tmp_path):
    state = {"frames": [{"zoom": 2.0, "colormap": "heat"}], "current": 0}
    backup.save(tmp_path / "s.bck", state)
    read, arrays = backup.load(tmp_path / "s.bck")
    assert read["frames"] == state["frames"]
    assert arrays == {}


def test_a_backup_is_json_not_a_script(tmp_path):
    """DS9's backup is a Tcl script it `eval`s on restore. A data file that
    is executed on being opened is not something to reproduce."""
    backup.save(tmp_path / "s.bck", {"frames": []})
    document = json.loads((tmp_path / "s.bck").read_text())
    assert document["format"] == "ncrads9-backup"
    assert document["version"] == backup.VERSION


def test_arrays_go_in_the_sidecar_as_fits(tmp_path):
    """Readable by anything, which a pickle or a blob would not be."""
    data = np.arange(9.0).reshape(3, 3)
    backup.save(tmp_path / "s.bck", {"frames": []}, {"frame_1": data})

    written = tmp_path / "s.bck.dir" / "frame_1.fits"
    assert written.is_file()
    _state, arrays = backup.load(tmp_path / "s.bck")
    assert np.array_equal(arrays["frame_1"], data)


def test_saving_again_replaces_the_sidecar(tmp_path):
    backup.save(tmp_path / "s.bck", {}, {"old": np.zeros((2, 2))})
    backup.save(tmp_path / "s.bck", {}, {"new": np.zeros((2, 2))})
    _state, arrays = backup.load(tmp_path / "s.bck")
    assert list(arrays) == ["new"]


def test_a_file_that_is_not_a_backup_is_refused(tmp_path):
    path = tmp_path / "other.json"
    path.write_text('{"hello": 1}')
    with pytest.raises(backup.BackupError, match="not an NCRADS9 backup"):
        backup.load(path)


def test_something_that_is_not_json_is_refused(tmp_path):
    path = tmp_path / "junk.bck"
    path.write_text("not json at all")
    with pytest.raises(backup.BackupError, match="not a backup file"):
        backup.load(path)


def test_a_missing_backup_is_refused(tmp_path):
    with pytest.raises(backup.BackupError, match="cannot read"):
        backup.load(tmp_path / "nope.bck")


def test_a_newer_backup_is_refused_as_ds9_refuses_one(tmp_path):
    path = tmp_path / "future.bck"
    path.write_text(json.dumps({"format": backup.FORMAT, "version": backup.VERSION + 5}))
    with pytest.raises(backup.BackupError, match="newer version"):
        backup.load(path)


def test_numpy_scalars_and_paths_are_written_as_plain_json(tmp_path):
    """A capture picks these up from numpy arrays and Path fields, and json
    refuses them without help."""
    from pathlib import Path

    backup.save(
        tmp_path / "s.bck",
        {"zoom": np.float32(2.5), "rows": np.int64(7), "flag": np.bool_(True), "file": Path("/x")},
    )
    state, _arrays = backup.load(tmp_path / "s.bck")
    assert state["zoom"] == 2.5
    assert state["rows"] == 7
    assert state["flag"] is True
    assert state["file"] == "/x"


def test_removing_a_backup_takes_its_sidecar_too(tmp_path):
    backup.save(tmp_path / "s.bck", {}, {"a": np.zeros((2, 2))})
    backup.remove(tmp_path / "s.bck")
    assert not (tmp_path / "s.bck").exists()
    assert not (tmp_path / "s.bck.dir").exists()


def test_removing_one_that_is_not_there_is_quiet(tmp_path):
    backup.remove(tmp_path / "never.bck")


# -- where the automatic backup lives -----------------------------------------------------


def test_the_automatic_backup_is_in_the_home_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert autosave.path() == tmp_path / ".ncrads9.auto"


def test_it_only_counts_as_recoverable_with_its_sidecar(tmp_path, monkeypatch):
    """A file with no directory is a backup whose write did not finish."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert autosave.exists() is False

    autosave.path().write_text("{}")
    assert autosave.exists() is False

    backup.sidecar(autosave.path()).mkdir()
    assert autosave.exists() is True


def test_the_interval_is_ds9s_five_minutes():
    assert autosave.interval_ms() == 5 * 60_000
    assert autosave.interval_ms(0.5) == 30_000
    # Never zero, which would be a timer that fires forever.
    assert autosave.interval_ms(0) == 1


# -- capturing and restoring a session ------------------------------------------------------


@pytest.fixture
def image(tmp_path):
    rows, columns = np.indices((SIZE, SIZE))
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32), header=_header()).writeto(path)
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


def test_a_capture_is_json_able(main_window):
    state, _arrays = main_window.session.capture()
    json.dumps(state, default=str)


def test_a_frame_with_a_file_is_captured_by_its_name_not_its_pixels(main_window, image):
    """Which is what keeps a backup of a night's work small."""
    state, arrays = main_window.session.capture()
    assert arrays == {}
    assert state["frames"][0]["file_spec"].startswith(str(image))


def test_a_frame_with_no_file_has_its_pixels_written_out(main_window):
    main_window.frame_controller.new_frame()
    frame = main_window.frame_manager.current_frame
    frame.image_data = np.ones((4, 4), dtype=np.float32)

    state, arrays = main_window.session.capture()
    key = state["frames"][1]["data"]
    assert key in arrays
    assert arrays[key].shape == (4, 4)


def test_the_view_comes_back(main_window):
    main_window.zoom.set_zoom(4.0)
    main_window.zoom.set_rotation(90.0)
    state, arrays = main_window.session.capture()

    main_window.zoom.set_zoom(1.0)
    main_window.zoom.set_rotation(0.0)
    main_window.session.apply(state, arrays)

    frame = main_window.frame_manager.current_frame
    assert frame.zoom == pytest.approx(4.0)
    assert frame.rotation == pytest.approx(90.0)


def test_the_colours_come_back(main_window):
    main_window.color.set_colormap("heat")
    main_window.scale.set_limit_mode("zscale")
    state, arrays = main_window.session.capture()

    main_window.color.set_colormap("grey")
    main_window.session.apply(state, arrays)
    assert main_window.frame_manager.current_frame.colormap == "heat"
    assert main_window.scale_limits.mode.value == "zscale"


def test_the_regions_come_back(main_window):
    from ncrads9.regions.shapes.circle import Circle

    frame = main_window.frame_manager.current_frame
    frame.regions = [Circle(center=(20.0, 20.0), radius=5.0)]
    state, arrays = main_window.session.capture()

    frame.regions = []
    main_window.session.apply(state, arrays)
    restored = main_window.frame_manager.current_frame.regions
    assert len(restored) == 1
    assert restored[0].center[0] == pytest.approx(20.0)


def test_the_crop_and_the_crosshair_come_back(main_window):
    main_window.crop.crop_to(10.0, 10.0, 30.0, 30.0)
    main_window.crosshair.move_to(15.0, 16.0)
    state, arrays = main_window.session.capture()

    main_window.crop.reset()
    main_window.session.apply(state, arrays)

    frame = main_window.frame_manager.current_frame
    assert frame.crop is not None
    assert (frame.crop.x0, frame.crop.y0) == (10.0, 10.0)
    assert frame.crosshair == (15.0, 16.0)
    assert main_window.crosshair.enabled is True


def test_the_colour_tags_come_back(main_window):
    from ncrads9.colormaps.color_tags import ColorTag, ColorTagSet

    frame = main_window.frame_manager.current_frame
    frame.color_tags = ColorTagSet([ColorTag(start=0.1, stop=0.2, color="red")])
    state, arrays = main_window.session.capture()

    frame.color_tags = None
    main_window.session.apply(state, arrays)
    tags = main_window.frame_manager.current_frame.color_tags
    assert tags is not None and len(tags) == 1


def test_the_illustrate_layer_comes_back(main_window):
    main_window.illustrate.layer.create("circle", 20.0, 30.0, radius=8.0)
    state, arrays = main_window.session.capture()

    main_window.illustrate.layer.clear()
    main_window.session.apply(state, arrays)
    assert len(main_window.illustrate.layer) == 1
    assert main_window.illustrate.layer.elements[0].center == (20.0, 30.0)


def test_the_grid_and_contour_settings_come_back(main_window):
    main_window.analysis.grid_config.visible = True
    from ncrads9.grid.grid_config import GridType

    main_window.analysis.grid_config.grid_type = GridType.PUBLICATION
    main_window.analysis.apply_contours({"method": "Linear", "num_levels": 7, "color": "#ff0000"})
    state, arrays = main_window.session.capture()

    main_window.analysis.grid_config.visible = False
    main_window._contour_settings = None
    main_window.session.apply(state, arrays)

    assert main_window.analysis.grid_config.visible is True
    assert main_window.analysis.grid_config.grid_type is GridType.PUBLICATION
    assert main_window._contour_settings["num_levels"] == 7


def test_more_than_one_frame_comes_back(main_window, image):
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(image))
    main_window.zoom.set_zoom(8.0)
    state, arrays = main_window.session.capture()

    assert main_window.session.apply(state, arrays) == 2
    assert main_window.frame_manager.num_frames == 2
    assert main_window.frame_manager.frames[1].zoom == pytest.approx(8.0)


def test_the_current_frame_comes_back(main_window, image):
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(image))
    main_window.frame_controller.first()
    state, arrays = main_window.session.capture()

    main_window.session.apply(state, arrays)
    assert main_window.frame_manager.current_index == 0


def test_the_edit_mode_comes_back(main_window):
    main_window.menu_bar.edit_mode_actions["pan"].trigger()
    state, arrays = main_window.session.capture()
    main_window.menu_bar.edit_mode_actions["none"].trigger()

    main_window.session.apply(state, arrays)
    assert main_window.edit_mode == "pan"


def test_a_file_that_has_gone_is_reported_not_fatal(main_window, tmp_path):
    """A backup names files; the files can move."""
    gone = tmp_path / "gone.fits"
    fits.PrimaryHDU(data=np.zeros((4, 4), dtype=np.float32)).writeto(gone)
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(gone))
    state, arrays = main_window.session.capture()
    gone.unlink()

    restored = main_window.session.apply(state, arrays)
    assert restored == 1
    assert any("no longer there" in problem for problem in main_window.session.problems)
    # And the frame is still there, empty, rather than the restore stopping.
    assert main_window.frame_manager.num_frames == 2


# -- the menu entries -----------------------------------------------------------------------


def test_backup_and_restore_through_a_file(main_window, tmp_path):
    main_window.zoom.set_zoom(4.0)
    path = tmp_path / "session.bck"
    assert main_window.session.backup(str(path)) is True
    assert path.is_file()

    main_window.zoom.set_zoom(1.0)
    assert main_window.session.restore(str(path)) is True
    assert main_window.frame_manager.current_frame.zoom == pytest.approx(4.0)


def test_restoring_something_that_is_not_a_backup_is_reported(main_window, tmp_path):
    path = tmp_path / "junk.bck"
    path.write_text("nonsense")
    assert main_window.session.restore(str(path)) is False
    assert "Restore failed" in main_window.status_bar.currentMessage()


def test_backing_up_where_it_cannot_be_written_is_reported(main_window, tmp_path):
    # A missing parent directory is created; a parent that is a *file*
    # cannot be.
    blocked = tmp_path / "afile"
    blocked.write_text("in the way")
    assert main_window.session.backup(str(blocked / "s.bck")) is False
    assert "Backup failed" in main_window.status_bar.currentMessage()


def test_backing_up_creates_the_directory_it_is_asked_for(main_window, tmp_path):
    """Saving into a folder that is not there yet is a courtesy, not an
    error: the folder is part of what was asked for."""
    path = tmp_path / "sessions" / "tonight.bck"
    assert main_window.session.backup(str(path)) is True
    assert path.is_file()


def test_cancelling_the_file_dialog_does_nothing(main_window, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    assert main_window.session.backup() is False
    assert main_window.session.restore() is False


def test_the_file_menu_has_backup_and_restore(main_window):
    labels = [
        action.text().replace("&", "")
        for action in main_window.menu_bar.file_menu.actions()
        if not action.isSeparator()
    ]
    assert "Backup..." in labels
    assert "Restore..." in labels


# -- the automatic backup ---------------------------------------------------------------------


def test_the_automatic_backup_is_written_on_the_timer(main_window):
    assert main_window.session.write_autosave() is True
    assert autosave.exists() is True


def test_the_timer_starts_when_the_preference_allows_it(main_window, monkeypatch):
    assert main_window.session.start_autosave() is True
    assert main_window.session.timer is not None
    assert main_window.session.timer.interval() == 5 * 60_000

    monkeypatch.setattr(
        type(main_window.preferences),
        "get",
        lambda self, key, default=None: False if key in ("use_gpu", "autosave") else default,
    )
    assert main_window.session.start_autosave() is False
    assert main_window.session.timer is None


def test_the_interval_follows_the_preference(main_window, monkeypatch):
    monkeypatch.setattr(
        type(main_window.preferences),
        "get",
        lambda self, key, default=None: (
            False if key == "use_gpu" else (1 if key == "autosave_interval" else default)
        ),
    )
    assert main_window.session.interval() == 60_000


def test_a_clean_exit_removes_the_automatic_backup(main_window):
    """Which is what makes one still being there a crash."""
    main_window.session.write_autosave()
    main_window.session.clean_exit()
    assert autosave.exists() is False
    assert main_window.session.timer is None


def test_recovery_restores_what_a_crash_left(main_window):
    main_window.zoom.set_zoom(4.0)
    main_window.session.write_autosave()
    main_window.zoom.set_zoom(1.0)

    assert main_window.session.offer_recovery(ask=False) is True
    assert main_window.frame_manager.current_frame.zoom == pytest.approx(4.0)
    # And it is cleared afterwards, so it is offered once.
    assert autosave.exists() is False


def test_recovery_with_nothing_to_recover_does_nothing(main_window):
    assert main_window.session.offer_recovery(ask=False) is False


def test_declining_recovery_throws_it_away(main_window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    main_window.session.write_autosave()
    assert main_window.session.offer_recovery() is False
    assert autosave.exists() is False


def test_accepting_recovery_restores_it(main_window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    main_window.zoom.set_zoom(4.0)
    main_window.session.write_autosave()
    main_window.zoom.set_zoom(1.0)
    assert main_window.session.offer_recovery() is True
    assert main_window.frame_manager.current_frame.zoom == pytest.approx(4.0)


def test_a_region_that_no_longer_parses_does_not_stop_the_restore(main_window):
    """One bad line in a saved region list must not cost the whole session."""
    state, arrays = main_window.session.capture()
    state["frames"][0]["regions"] = "image\ncircle(10,20,5"

    assert main_window.session.apply(state, arrays) == 1
    assert main_window.frame_manager.current_frame.image_data is not None
