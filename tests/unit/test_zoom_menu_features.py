import os

import numpy as np
import pytest
from astropy.wcs import WCS
from PyQt6.QtWidgets import QApplication, QWidget

from ncrads9.ui.main_window import MainWindow
from ncrads9.core.wcs_handler import WCSHandler
from ncrads9.utils.preferences import Preferences


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def main_window(qapp, monkeypatch):
    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    yield window
    window.close()


def _load_test_image(window: MainWindow, width: int = 256, height: int = 256) -> None:
    frame = window.frame_manager.current_frame
    assert frame is not None
    image = np.arange(width * height, dtype=np.float32).reshape(height, width)
    frame.image_data = image.copy()
    frame.original_image_data = image.copy()
    window.z1 = None
    window.z2 = None
    window._update_frame_display()


def _make_test_wcs(width: int, height: int) -> WCSHandler:
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [width / 2.0, height / 2.0]
    wcs.wcs.cdelt = [-0.0002777778, 0.0002777778]
    wcs.wcs.crval = [180.0, 45.0]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    return WCSHandler(wcs=wcs)


def test_zoom_menu_exposes_ds9_style_actions(main_window: MainWindow):
    assert main_window.menu_bar.action_zoom_center is not None
    assert main_window.menu_bar.action_zoom_align.isCheckable()
    assert sorted(main_window.menu_bar.zoom_preset_actions) == [
        0.03125,
        0.0625,
        0.125,
        0.25,
        0.5,
        1.0,
        2.0,
        4.0,
        8.0,
        16.0,
        32.0,
    ]
    assert set(main_window.menu_bar.zoom_orientation_actions) == {"none", "x", "y", "xy"}
    assert sorted(main_window.menu_bar.zoom_rotation_actions) == [0, 90, 180, 270]
    assert main_window.menu_bar.action_crop_parameters is not None
    assert main_window.menu_bar.action_pan_zoom_rotate_parameters is not None


def test_zoom_menu_state_tracks_frame_view(main_window: MainWindow):
    _load_test_image(main_window)
    frame1 = main_window.frame_manager.current_frame
    assert frame1 is not None

    main_window._set_zoom_level(4.0)
    main_window._set_orientation("x")
    main_window._set_rotation(90)
    main_window._set_align_wcs(True)

    assert frame1.zoom == pytest.approx(4.0)
    assert frame1.flip_x is True and frame1.flip_y is False
    assert frame1.rotation == pytest.approx(90.0)
    assert frame1.align_wcs is True
    assert main_window.menu_bar.zoom_preset_actions[4.0].isChecked()
    assert main_window.menu_bar.zoom_orientation_actions["x"].isChecked()
    assert main_window.menu_bar.zoom_rotation_actions[90].isChecked()
    assert main_window.menu_bar.action_zoom_align.isChecked()

    frame2 = main_window.frame_manager.new_frame()
    frame2.image_data = np.ones((32, 32), dtype=np.float32)
    frame2.original_image_data = frame2.image_data.copy()
    frame2.zoom = 2.0
    frame2.flip_y = True
    frame2.rotation = 180.0
    main_window._goto_frame_index(1)

    assert main_window.menu_bar.zoom_preset_actions[2.0].isChecked()
    assert main_window.menu_bar.zoom_orientation_actions["y"].isChecked()
    assert main_window.menu_bar.zoom_rotation_actions[180].isChecked()


def test_center_image_recenters_scrollbars(main_window: MainWindow):
    _load_test_image(main_window, width=1200, height=900)
    main_window._set_zoom_level(3.0)
    main_window.scroll_area.horizontalScrollBar().setValue(0)
    main_window.scroll_area.verticalScrollBar().setValue(0)

    main_window._center_image()

    assert main_window.scroll_area.horizontalScrollBar().value() > 0
    assert main_window.scroll_area.verticalScrollBar().value() > 0


def test_crop_and_pan_zoom_rotate_parameters_apply_to_frame(main_window: MainWindow):
    _load_test_image(main_window, width=400, height=300)
    frame = main_window.frame_manager.current_frame
    assert frame is not None

    main_window._apply_crop_parameters(
        {"center_x": 120.0, "center_y": 80.0, "width": 40.0, "height": 20.0}
    )
    assert frame.crop_center_x == pytest.approx(120.0)
    assert frame.crop_center_y == pytest.approx(80.0)
    assert frame.crop_width == pytest.approx(40.0)
    assert frame.crop_height == pytest.approx(20.0)
    assert frame.zoom > 1.0

    main_window._apply_pan_zoom_rotate_parameters(
        {"zoom": 2.5, "pan_x": 150.0, "pan_y": 120.0, "rotation": 180.0, "align": True}
    )
    assert frame.zoom == pytest.approx(2.5)
    assert frame.rotation == pytest.approx(180.0)
    assert frame.align_wcs is True
    assert main_window.menu_bar.action_zoom_align.isChecked()
    assert main_window.menu_bar.zoom_rotation_actions[180].isChecked()


def test_frame_lock_matches_zoom_orientation_and_rotation(main_window: MainWindow):
    _load_test_image(main_window, width=128, height=128)
    source = main_window.frame_manager.current_frame
    other = main_window.frame_manager.new_frame()
    other.image_data = np.zeros((128, 128), dtype=np.float32)
    other.original_image_data = other.image_data.copy()
    main_window._goto_frame_index(0)
    assert source is not None

    main_window._set_frame_lock_scope("frame", "image")
    main_window._set_zoom_level(8.0)
    main_window._set_orientation("xy")
    main_window._set_rotation(270)

    assert other.zoom == pytest.approx(8.0)
    assert other.flip_x is True and other.flip_y is True
    assert other.rotation == pytest.approx(270.0)


def test_rebuild_image_viewer_does_not_manually_delete_replaced_widget(
    main_window: MainWindow, monkeypatch
):
    replacement = QWidget()

    class OldViewer(QWidget):
        def deleteLater(self):
            raise AssertionError("old viewer should not be manually deleted")

    old_viewer = OldViewer()
    main_window.scroll_area.setWidget(old_viewer)
    main_window.image_viewer = old_viewer
    monkeypatch.setattr(main_window, "_create_image_viewer", lambda use_gpu: replacement)
    monkeypatch.setattr(main_window, "_display_image", lambda: None)

    main_window._rebuild_image_viewer(False)

    assert main_window.image_viewer is replacement
    assert main_window.scroll_area.widget() is replacement


def test_invert_updates_direction_arrows_without_full_rerender(
    main_window: MainWindow, monkeypatch
):
    _load_test_image(main_window, width=64, height=64)
    frame = main_window.frame_manager.current_frame
    assert frame is not None
    frame.wcs_handler = _make_test_wcs(64, 64)
    main_window._update_frame_display()

    overlay = main_window.image_viewer.contour_overlay
    before_north = overlay._north_vector
    before_east = overlay._east_vector
    assert before_north is not None
    assert before_east is not None

    monkeypatch.setattr(
        main_window,
        "_display_image",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected rerender")),
    )
    main_window._set_orientation("x")

    after_north = overlay._north_vector
    after_east = overlay._east_vector
    assert after_north is not None
    assert after_east is not None
    assert after_north != before_north
    assert after_east != before_east
