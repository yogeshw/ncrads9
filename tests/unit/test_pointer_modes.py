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

"""DS9's pointer modes (M9-1 ... M9-5)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.ui.pointer_modes import (
    EXAMINE_ZOOM,
    HANDLERS,
    MINIMUM_DRAG,
    ZOOM_STEP,
    handler_for,
)

SIZE = 200


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


class Recorder:
    """A pointer target that writes down what it was asked to do."""

    def __init__(self, picks: bool = True) -> None:
        self.calls: list[tuple] = []
        self.picks = picks

    def _record(self, name):
        def call(*args):
            self.calls.append((name, args))
            return self.picks if name == "pick_at" else None

        return call

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._record(name)

    @property
    def names(self) -> list[str]:
        return [name for name, _args in self.calls]


# -- the handlers ------------------------------------------------------------


def test_every_mode_ds9_offers_has_a_handler():
    for mode in ("pan", "zoom", "rotate", "crop", "examine", "crosshair"):
        assert handler_for(mode, Recorder()) is not None
    for mode in ("catalog", "footprint"):
        assert handler_for(mode, Recorder()) is not None


def test_the_modes_with_no_handler_have_none():
    """These four are handled elsewhere: pointer, region and illustrate by
    the overlay's own gestures, and colorbar by the colorbar widget."""
    for mode in ("none", "region", "colorbar", "illustrate"):
        assert handler_for(mode, Recorder()) is None


def test_the_3d_mode_turns_the_cube():
    target = Recorder()
    handler = handler_for("3d", target)
    handler.press(10.0, 10.0)
    handler.move(40.0, 30.0)
    assert target.calls == [("turn_cube", (30.0, 20.0))]


def test_a_pan_drag_moves_the_view_the_other_way():
    """The image follows the cursor, so the view goes the opposite way --
    getting this backwards is the classic reversed-pan bug."""
    target = Recorder()
    handler = handler_for("pan", target)
    handler.press(100.0, 100.0)
    handler.move(110.0, 100.0)
    assert target.calls == [("pan_by", (-10.0, 0.0))]


def test_a_pan_click_centres_the_view():
    target = Recorder()
    handler = handler_for("pan", target)
    handler.press(50.0, 60.0)
    handler.release(50.0, 60.0)
    assert target.calls == [("pan_to", (50.0, 60.0))]


def test_a_pan_drag_does_not_also_centre():
    target = Recorder()
    handler = handler_for("pan", target)
    handler.press(50.0, 60.0)
    handler.move(150.0, 60.0)
    handler.release(150.0, 60.0)
    assert target.names == ["pan_by"]


def test_a_zoom_click_zooms_in_and_a_right_click_out():
    target = Recorder()
    handler = handler_for("zoom", target)
    handler.press(50.0, 50.0, "left")
    handler.release(50.0, 50.0)
    handler.press(50.0, 50.0, "right")
    handler.release(50.0, 50.0)
    assert target.calls == [
        ("zoom_by", (ZOOM_STEP, 50.0, 50.0)),
        ("zoom_by", (1.0 / ZOOM_STEP, 50.0, 50.0)),
    ]


def test_a_zoom_box_zooms_to_that_rectangle_and_does_not_crop():
    """Zoom and crop are different modes: a zoom box must not throw away the
    rest of the data, which is what cropping from here used to do."""
    target = Recorder()
    handler = handler_for("zoom", target)
    handler.press(10.0, 10.0)
    handler.move(60.0, 40.0)
    handler.release(60.0, 40.0)
    assert target.calls == [("zoom_to", (10.0, 10.0, 60.0, 40.0))]


def test_a_rotate_drag_turns_the_view():
    target = Recorder()
    handler = handler_for("rotate", target)
    handler.press(0.0, 0.0)
    handler.move(100.0, 0.0)
    assert target.names == ["rotate_by"]
    assert target.calls[0][1][0] > 0


def test_a_rotate_drag_the_other_way_turns_the_other_way():
    target = Recorder()
    handler = handler_for("rotate", target)
    handler.press(100.0, 0.0)
    handler.move(0.0, 0.0)
    assert target.calls[0][1][0] < 0


def test_a_crop_box_crops():
    target = Recorder()
    handler = handler_for("crop", target)
    handler.press(20.0, 30.0)
    handler.move(80.0, 90.0)
    handler.release(80.0, 90.0)
    assert target.calls == [("crop_to", (20.0, 30.0, 80.0, 90.0))]


def test_a_crop_click_crops_nothing():
    """Cropping to a click leaves no way back."""
    target = Recorder()
    handler = handler_for("crop", target)
    handler.press(20.0, 30.0)
    handler.release(20.0 + MINIMUM_DRAG / 2, 30.0)
    assert target.calls == []


def test_crop_and_zoom_draw_a_band_and_the_others_do_not():
    assert handler_for("crop", Recorder()).draws_band is True
    assert handler_for("zoom", Recorder()).draws_band is True
    for mode in ("pan", "rotate", "examine", "crosshair"):
        assert handler_for(mode, Recorder()).draws_band is False


def test_the_band_is_the_rectangle_being_dragged():
    handler = handler_for("crop", Recorder())
    assert handler.rubber_band is None
    handler.press(10.0, 20.0)
    handler.move(30.0, 40.0)
    assert handler.rubber_band == (10.0, 20.0, 30.0, 40.0)
    handler.release(30.0, 40.0)
    assert handler.rubber_band is None


def test_examine_opens_a_zoomed_view_at_ds9s_factor():
    """`pexamine(zoom)` is 4 (`examine.tcl:12`)."""
    target = Recorder()
    handler = handler_for("examine", target)
    handler.press(70.0, 80.0)
    handler.release(70.0, 80.0)
    assert target.calls == [("examine_at", (70.0, 80.0, EXAMINE_ZOOM))]


def test_crosshair_mode_places_on_press_and_follows_the_drag():
    target = Recorder()
    handler = handler_for("crosshair", target)
    handler.press(10.0, 10.0)
    handler.move(20.0, 30.0)
    assert target.calls == [
        ("move_crosshair", (10.0, 10.0)),
        ("move_crosshair", (20.0, 30.0)),
    ]


def test_a_pick_that_hits_is_used_and_a_miss_is_not():
    """A miss must reach whatever is underneath."""
    assert handler_for("catalog", Recorder(picks=True)).press(1.0, 1.0) is True
    assert handler_for("catalog", Recorder(picks=False)).press(1.0, 1.0) is False


def test_a_move_with_no_press_is_not_used():
    """A drag that began outside the image is not this mode's business."""
    for mode in HANDLERS:
        assert handler_for(mode, Recorder()).move(1.0, 1.0) is False


# -- the controller carrying them out --------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    rows, columns = np.indices((SIZE, SIZE))
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32), header=_header()).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    yield window
    window.close()


@pytest.mark.parametrize(
    "mode", ["pan", "zoom", "rotate", "crop", "examine", "crosshair", "catalog", "footprint"]
)
def test_choosing_a_mode_arms_its_handler(main_window, mode):
    """Every one of these used to answer with the milestone it was waiting
    for."""
    main_window.menu_bar.edit_mode_actions[mode].trigger()
    assert main_window.pointer.handler is not None
    assert main_window.pointer.handler.name == mode
    assert main_window.image_viewer.region_overlay.pointer_handler is main_window.pointer.handler


def test_pointer_mode_disarms_the_handler(main_window):
    main_window.menu_bar.edit_mode_actions["pan"].trigger()
    main_window.menu_bar.edit_mode_actions["none"].trigger()
    assert main_window.pointer.handler is None
    assert main_window.image_viewer.region_overlay.pointer_handler is None


def test_region_mode_leaves_the_overlay_to_its_own_gestures(main_window):
    main_window.menu_bar.edit_mode_actions["region"].trigger()
    assert main_window.image_viewer.region_overlay.pointer_handler is None


def test_a_zoom_click_changes_the_zoom(main_window):
    before = main_window.image_viewer.get_zoom()
    main_window.pointer.zoom_by(2.0, 100.0, 100.0)
    assert main_window.image_viewer.get_zoom() == pytest.approx(before * 2.0)


def test_zooming_is_bounded(main_window):
    from ncrads9.ui.controllers.pointer import MAX_ZOOM, MIN_ZOOM

    for _ in range(20):
        main_window.pointer.zoom_by(4.0, 100.0, 100.0)
    assert main_window.image_viewer.get_zoom() <= MAX_ZOOM
    for _ in range(40):
        main_window.pointer.zoom_by(0.25, 100.0, 100.0)
    assert main_window.image_viewer.get_zoom() >= MIN_ZOOM


def test_a_rotate_drag_is_relative_to_the_current_angle(main_window):
    main_window.zoom.set_rotation(30.0)
    main_window.pointer.rotate_by(15.0)
    assert main_window.frame_manager.current_frame.rotation == pytest.approx(45.0)


def test_zooming_to_a_box_fits_it(main_window):
    before = main_window.image_viewer.get_zoom()
    main_window.pointer.zoom_to(80.0, 80.0, 120.0, 120.0)
    # A forty-pixel box in a viewport hundreds wide is a zoom in.
    assert main_window.image_viewer.get_zoom() > before


def test_a_box_too_small_to_zoom_to_is_refused(main_window):
    main_window.pointer.zoom_to(50.0, 50.0, 50.5, 50.5)
    assert "too small" in main_window.status_bar.currentMessage()


def test_a_crop_drag_crops_and_leaves_the_view_alone(main_window):
    """DS9's crop chooses the data displayed; it is not a zoom."""
    zoom_before = main_window.image_viewer.get_zoom()
    main_window.pointer.crop_to(80.0, 80.0, 120.0, 120.0)
    assert main_window.frame_manager.current_frame.crop is not None
    assert main_window.image_viewer.get_zoom() == pytest.approx(zoom_before)


def test_examine_opens_a_second_frame_and_leaves_the_first(main_window):
    before = main_window.frame_manager.num_frames
    main_window.pointer.examine_at(60.0, 60.0, 4.0)
    assert main_window.frame_manager.num_frames == before + 1
    assert main_window.image_viewer.get_zoom() == pytest.approx(4.0)


def test_examine_needs_a_file_behind_the_frame(main_window):
    main_window.frame_manager.current_frame.filepath = None
    before = main_window.frame_manager.num_frames
    main_window.pointer.examine_at(60.0, 60.0, 4.0)
    assert main_window.frame_manager.num_frames == before
    assert "needs a frame with a file" in main_window.status_bar.currentMessage()


# -- the crosshair (M9-1) ------------------------------------------------------------


def test_the_crosshair_starts_unplaced(main_window):
    assert main_window.crosshair.position() is None


def test_placing_the_crosshair(main_window):
    main_window.crosshair.move_to(60.0, 70.0)
    assert main_window.crosshair.position() == (60.0, 70.0)
    assert main_window.crosshair.enabled is True


def test_the_crosshair_is_per_frame(main_window):
    """DS9's is; the lock is what ties them together."""
    main_window.crosshair.move_to(60.0, 70.0)
    main_window.frame_controller.new_frame()
    assert main_window.crosshair.position() is None


def test_turning_it_on_places_it_in_the_middle(main_window):
    """So the mode does something the moment it is chosen."""
    main_window.crosshair.set_enabled(True)
    assert main_window.crosshair.position() == (SIZE / 2.0, SIZE / 2.0)


def test_the_crosshair_reads_the_pixel_under_it(main_window):
    # The fixture's data is row + column, zero-based.
    assert main_window.crosshair.value_at(11.0, 21.0) == pytest.approx(30.0)


def test_a_crosshair_off_the_image_reads_nothing(main_window):
    assert main_window.crosshair.value_at(-5.0, -5.0) is None
    assert main_window.crosshair.value_at(1e6, 1e6) is None


def test_the_crosshair_drives_the_readout(main_window):
    main_window.crosshair.move_to(31.0, 41.0)
    # The status bar's pixel readout follows it, through the same path the
    # pointer uses.
    assert main_window._last_mouse_pos == (30, 40)


def test_moving_the_crosshair_reaches_the_overlay(main_window):
    main_window.crosshair.move_to(60.0, 70.0)
    overlay = main_window.image_viewer.contour_overlay
    assert overlay._crosshair_visible is True
    assert overlay._crosshair_position == (60.0, 70.0)


def test_the_lock_moves_every_other_frame(main_window):
    main_window.crosshair.move_to(60.0, 70.0)
    main_window.frame_controller.new_frame()
    main_window.crosshair.move_to(90.0, 90.0)

    main_window.crosshair.set_locked(True)
    first = main_window.frame_manager.frames[0]
    assert first.crosshair is not None


def test_the_lock_matches_through_the_sky_not_the_pixels(main_window, tmp_path):
    """Two frames of the same field at different scales have the same object
    at different pixels."""
    coarse = _header()
    coarse["CDELT1"] = -0.002
    coarse["CDELT2"] = 0.002
    path = tmp_path / "coarse.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32), header=coarse).writeto(path)

    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(path))
    main_window.frame_controller.first()

    main_window.crosshair.locked = True
    main_window.crosshair.move_to(150.0, 150.0)

    other = main_window.frame_manager.frames[1]
    assert other.crosshair is not None
    # Half the scale, so the same sky offset is half the pixel offset.
    assert other.crosshair[0] == pytest.approx(125.0, abs=1.0)


def test_the_lock_falls_back_to_pixels_without_a_wcs(main_window, tmp_path):
    path = tmp_path / "plain.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32)).writeto(path)
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(path))
    main_window.frame_controller.first()

    main_window.crosshair.locked = True
    main_window.crosshair.move_to(60.0, 70.0)
    assert main_window.frame_manager.frames[1].crosshair == (60.0, 70.0)


def test_crosshair_mode_places_it_by_clicking(main_window):
    main_window.menu_bar.edit_mode_actions["crosshair"].trigger()
    handler = main_window.pointer.handler
    handler.press(45.0, 55.0)
    assert main_window.crosshair.position() == (45.0, 55.0)


def test_leaving_crosshair_mode_hides_it(main_window):
    main_window.menu_bar.edit_mode_actions["crosshair"].trigger()
    main_window.menu_bar.edit_mode_actions["pan"].trigger()
    assert main_window.crosshair.enabled is False


# -- the dialog ----------------------------------------------------------------------


@pytest.fixture
def dialog(main_window):
    from ncrads9.ui.dialogs.crosshair_dialog import CrosshairDialog

    made = CrosshairDialog(main_window.crosshair, main_window)
    yield made
    made.close()


def test_the_dialog_can_place_the_crosshair(dialog, main_window):
    """Typing a coordinate is how you place it exactly."""
    dialog._x.setValue(33.0)
    dialog._y.setValue(44.0)
    dialog.apply_position()
    assert main_window.crosshair.position() == (33.0, 44.0)


def test_the_dialog_shows_the_sky_position_and_value(dialog, main_window):
    main_window.crosshair.move_to(100.0, 100.0)
    dialog.reload()
    assert ":" not in dialog._sky.text()
    assert dialog._sky.text().startswith("149.9")
    assert dialog._value.text() not in ("", "--")


def test_the_dialog_says_when_it_is_not_placed(dialog):
    assert "not placed" in dialog._sky.text()


def test_reloading_does_not_move_the_crosshair(dialog, main_window):
    """`setValue` emits, and a reload that emitted would move what it reports."""
    main_window.crosshair.move_to(70.0, 80.0)
    dialog.reload()
    dialog.reload()
    assert main_window.crosshair.position() == (70.0, 80.0)


def test_the_dialog_changes_the_colour_and_size(dialog, main_window):
    dialog._color.setCurrentText("cyan")
    dialog._size.setValue(50)
    assert main_window.crosshair.color == "cyan"
    assert main_window.crosshair.size == 50


def test_the_dialog_toggles_the_lock(dialog, main_window):
    dialog._lock.setChecked(True)
    assert main_window.crosshair.locked is True


# -- the overlay stack the modes depend on ---------------------------------------------


def test_the_region_overlay_is_the_only_layer_taking_the_mouse(main_window):
    """A Qt event a child ignores goes to the parent, not to a sibling, so
    two overlays taking clicks means the lower one never sees any."""
    from PyQt6.QtCore import Qt

    viewer = main_window.image_viewer
    assert not viewer.region_overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    for overlay in (viewer.contour_overlay, viewer.catalog_overlay):
        assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_the_region_overlay_is_on_top(main_window):
    children = [
        child for child in main_window.image_viewer.image_viewer.children() if hasattr(child, "testAttribute")
    ]
    assert type(children[-1]).__name__ == "RegionOverlay"


def test_a_click_on_no_region_offers_it_to_the_catalogue_layer(main_window):
    from PyQt6.QtCore import QPointF

    asked = []
    main_window.image_viewer.region_overlay.pick_handler = lambda point: asked.append(point) or False
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QMouseEvent

    overlay = main_window.image_viewer.region_overlay
    point = QPointF(20.0, 20.0)
    overlay.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            point,
            point,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert asked == [point]


def test_match_crosshair_copies_it_to_the_other_frames(main_window):
    """DS9's Frame -> Match -> Crosshair. It used to match the frames' views,
    which is what Match -> Frame is for."""
    main_window.crosshair.move_to(60.0, 70.0)
    before = main_window.frame_manager.current_frame.pan_x
    main_window.frame_controller.new_frame()
    main_window.frame_controller.first()

    main_window.menu_bar.action_match_crosshair_image.trigger()
    assert main_window.frame_manager.frames[1].crosshair == (60.0, 70.0)
    assert main_window.frame_manager.frames[0].pan_x == before


def test_match_crosshair_says_when_there_is_none(main_window):
    main_window.menu_bar.action_match_crosshair_wcs.trigger()
    assert "place one first" in main_window.status_bar.currentMessage()


def test_lock_crosshair_turns_the_lock_on_and_off(main_window):
    main_window.menu_bar.action_lock_crosshair_wcs.trigger()
    assert main_window.crosshair.locked is True
    assert main_window.crosshair.lock_system == "wcs"
    main_window.menu_bar.action_lock_crosshair_none.trigger()
    assert main_window.crosshair.locked is False


def test_the_crosshair_dialog_has_one_owner(main_window, monkeypatch):
    """Two controllers were connected to Crosshair Parameters, so choosing it
    opened a question box and then the dialog."""
    from PyQt6.QtWidgets import QInputDialog

    def refuse(*args, **kwargs):
        raise AssertionError("the old crosshair prompt is still connected")

    monkeypatch.setattr(QInputDialog, "getItem", refuse)
    main_window.menu_bar.action_crosshair_params.trigger()
    assert main_window.crosshair._dialog is not None
    main_window.crosshair._dialog.close()
