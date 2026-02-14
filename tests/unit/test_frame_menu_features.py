import os

import numpy as np
import pytest
from astropy.wcs import WCS
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ncrads9.core.wcs_handler import WCSHandler
from ncrads9.ui.main_window import MainWindow
from ncrads9.ui.widgets.region_overlay import RegionMode
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


def _load_two_frames(window: MainWindow) -> None:
    frame1 = window.frame_manager.current_frame
    frame1.image_data = np.arange(100, dtype=np.float32).reshape(10, 10)
    frame1.original_image_data = frame1.image_data

    frame2 = window.frame_manager.new_frame()
    frame2.image_data = (np.arange(100, dtype=np.float32).reshape(10, 10) + 10.0)
    frame2.original_image_data = frame2.image_data

    window.frame_manager.goto_frame(0)
    window._update_frame_display()


def _make_test_wcs(width: int, height: int) -> WCSHandler:
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [width / 2.0, height / 2.0]
    wcs.wcs.cdelt = [-0.0002777778, 0.0002777778]
    wcs.wcs.crval = [180.0, 45.0]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    return WCSHandler(wcs=wcs)


def test_blink_menu_advances_frames(main_window: MainWindow):
    _load_two_frames(main_window)
    assert main_window.frame_manager.current_index == 0

    main_window._toggle_blink(True)
    assert main_window._blink_timer.isActive()

    main_window._update_blink()
    assert main_window.frame_manager.current_index == 1

    main_window._toggle_blink(False)
    assert not main_window._blink_timer.isActive()


def test_tile_menu_toggles_tiled_display(main_window: MainWindow):
    _load_two_frames(main_window)
    assert main_window.menu_bar.action_tile_frames.isCheckable()

    main_window._tile_frames(True)
    assert main_window._tile_mode_enabled

    pixmap = main_window.image_viewer.pixmap()
    assert pixmap is not None
    assert pixmap.width() > 0 and pixmap.height() > 0

    main_window._tile_frames(False)
    assert not main_window._tile_mode_enabled


def test_mouse_move_uses_bottom_left_origin(main_window: MainWindow):
    frame = main_window.frame_manager.current_frame
    frame.image_data = np.arange(100, dtype=np.float32).reshape(10, 10)
    frame.original_image_data = frame.image_data
    main_window._update_frame_display()

    main_window._on_mouse_moved(2, 0)
    assert main_window.status_bar.pixel_coord_label.text() == "X: 2 Y: 0"
    assert main_window.status_bar.pixel_value_label.text() == "Value: 92"


def test_wcs_direction_arrows_default_and_toggle(main_window: MainWindow):
    frame = main_window.frame_manager.current_frame
    frame.image_data = np.arange(100, dtype=np.float32).reshape(10, 10)
    frame.original_image_data = frame.image_data
    frame.wcs_handler = _make_test_wcs(10, 10)
    main_window._update_frame_display()

    overlay = main_window.image_viewer.contour_overlay
    assert overlay._show_direction_arrows is True
    assert overlay._north_vector is not None
    assert overlay._east_vector is not None

    main_window.menu_bar.action_show_direction_arrows.trigger()
    assert overlay._show_direction_arrows is False


def test_clear_regions_returns_to_pan_mode(main_window: MainWindow):
    main_window._set_region_mode(RegionMode.CIRCLE)
    assert main_window.image_viewer.region_overlay.mode == RegionMode.CIRCLE

    main_window._clear_regions()
    assert main_window.image_viewer.region_overlay.mode == RegionMode.NONE
    assert main_window.image_viewer.region_overlay.testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents
    )


def test_tile_click_selects_frame_and_preserves_independent_settings(main_window: MainWindow):
    _load_two_frames(main_window)
    frames = main_window.frame_manager.frames
    frames[0].colormap = "grey"
    frames[1].colormap = "viridis"
    main_window.frame_manager.goto_frame(0)

    main_window._tile_frames(True)
    layout = main_window._tile_layout
    assert layout is not None

    gap = int(layout["gap"])
    cell_w = int(layout["cell_w"])
    tiled_h = int(layout["tiled_h"])
    y_top = gap + 1
    y_click = tiled_h - 1 - y_top

    x_second = gap + cell_w + gap + 1
    main_window._on_image_clicked(x_second, y_click, int(Qt.MouseButton.LeftButton.value))
    assert main_window.frame_manager.current_index == 1

    main_window._set_colormap("magma")
    assert frames[1].colormap == "magma"
    assert frames[0].colormap == "grey"


def test_panner_draws_viewport_rect_when_zoomed(main_window: MainWindow):
    frame = main_window.frame_manager.current_frame
    frame.image_data = np.zeros((1200, 1600), dtype=np.float32)
    frame.original_image_data = frame.image_data
    main_window._update_frame_display()
    main_window._zoom_actual()
    main_window._zoom_in()

    rect = main_window.panner_panel._view_rect
    assert rect is not None
    assert rect.width() < 1600
    assert rect.height() < 1200
