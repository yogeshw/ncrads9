import os

import numpy as np
import pytest
from astropy.wcs import WCS
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ncrads9.core.wcs_handler import WCSHandler
from ncrads9.rendering.scale_algorithms import ScaleAlgorithm
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


def test_frame_menu_exposes_ds9_style_actions(main_window: MainWindow):
    assert main_window.menu_bar.action_new_frame_rgb is not None
    assert main_window.menu_bar.action_delete_all_frames is not None
    assert main_window.menu_bar.action_clear_frame is not None
    assert main_window.menu_bar.action_reset_frame is not None
    assert main_window.menu_bar.action_refresh_frame is not None
    assert main_window.menu_bar.action_fade_frames is not None
    assert main_window.menu_bar.goto_frame_menu is not None
    assert main_window.menu_bar.show_hide_frames_menu is not None
    assert main_window.menu_bar.move_frame_menu is not None
    assert main_window.menu_bar.frame_params_menu is not None


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


def test_delete_all_frames_resets_to_single_empty(main_window: MainWindow):
    _load_two_frames(main_window)
    assert main_window.frame_manager.num_frames == 2
    main_window._delete_all_frames()
    assert main_window.frame_manager.num_frames == 1
    frame = main_window.frame_manager.current_frame
    assert frame is not None
    assert frame.image_data is None


def test_clear_and_reset_frame_actions(main_window: MainWindow):
    frame = main_window.frame_manager.current_frame
    assert frame is not None
    frame.image_data = np.arange(100, dtype=np.float32).reshape(10, 10)
    frame.original_image_data = frame.image_data
    frame.colormap = "magma"
    frame.zoom = 3.0
    frame.contrast = 2.0
    main_window._reset_frame()
    assert frame.colormap == "grey"
    assert frame.zoom == 1.0
    assert frame.contrast == 1.0
    main_window._clear_frame()
    assert frame.image_data is None
    assert frame.original_image_data is None


def test_show_hide_frames_controls_active_tiling(main_window: MainWindow):
    _load_two_frames(main_window)
    main_window._hide_all_frames()
    assert len(main_window._active_frame_ids) == 1
    main_window._tile_frames(True)
    assert main_window._tile_layout is not None
    assert len(main_window._tile_layout["frame_indices"]) == 1
    main_window._show_all_frames()
    assert len(main_window._active_frame_ids) == 2


def test_move_frame_reorders_frame_stack(main_window: MainWindow):
    _load_two_frames(main_window)
    third = main_window.frame_manager.new_frame()
    third.image_data = np.zeros((10, 10), dtype=np.float32)
    third.original_image_data = third.image_data
    before = [frame.frame_id for frame in main_window.frame_manager.frames]
    main_window.frame_manager.goto_frame(2)
    main_window._move_frame_first()
    after = [frame.frame_id for frame in main_window.frame_manager.frames]
    assert after[0] == before[2]
    main_window._move_frame_last()
    after_last = [frame.frame_id for frame in main_window.frame_manager.frames]
    assert after_last[-1] == before[2]


def test_fade_mode_uses_timer(main_window: MainWindow):
    _load_two_frames(main_window)
    main_window._set_fade_interval(2000)
    main_window._toggle_fade(True)
    assert main_window._frame_display_mode == "fade"
    assert main_window._blink_timer.isActive()
    assert main_window._blink_timer.interval() == 2000
    main_window._toggle_fade(False)
    assert main_window._frame_display_mode == "single"


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


def test_rgb_frame_composes_channels_from_source_frames(main_window: MainWindow):
    red = np.array([[0.0, 10.0], [0.0, 10.0]], dtype=np.float32)
    green = np.array([[0.0, 0.0], [10.0, 10.0]], dtype=np.float32)
    blue = np.zeros((2, 2), dtype=np.float32)

    frame0 = main_window.frame_manager.current_frame
    frame0.image_data = red
    frame0.original_image_data = red

    frame1 = main_window.frame_manager.new_frame()
    frame1.image_data = green
    frame1.original_image_data = green

    frame2 = main_window.frame_manager.new_frame()
    frame2.image_data = blue
    frame2.original_image_data = blue

    main_window._new_frame_with_type("rgb")
    rgb_frame = main_window.frame_manager.current_frame
    assert rgb_frame is not None
    assert rgb_frame.frame_type == "rgb"

    main_window._apply_rgb_frame_channels_from_sources(
        rgb_frame,
        {"red": 0, "green": 1, "blue": 2},
    )
    composed = main_window._compose_rgb_frame_image(rgb_frame)
    assert composed is not None
    assert composed.shape == (2, 2, 3)
    assert composed[0, 1, 0] > 200  # red-dominant pixel
    assert composed[1, 0, 1] > 200  # green-dominant pixel


def test_load_fits_in_rgb_frame_updates_active_channel(main_window: MainWindow, monkeypatch):
    def _fake_load(self, filepath, memmap=True):
        self.filepath = filepath
        self.hdu_list = ["dummy"]
        return self.hdu_list

    def _fake_get_data(self, ext=0):
        return np.arange(16, dtype=np.float32).reshape(4, 4)

    def _fake_get_header(self, ext=0):
        return {}

    monkeypatch.setattr("ncrads9.ui.main_window.FITSHandler.load", _fake_load)
    monkeypatch.setattr("ncrads9.ui.main_window.FITSHandler.get_data", _fake_get_data)
    monkeypatch.setattr("ncrads9.ui.main_window.FITSHandler.get_header", _fake_get_header)

    main_window._new_frame_with_type("rgb")
    frame = main_window.frame_manager.current_frame
    assert frame is not None
    frame.rgb_current_channel = "green"

    main_window._load_fits_file("/tmp/rgb-green.fits")
    assert frame.rgb_channels["green"] is not None
    assert frame.image_data is frame.rgb_channels["green"]


def test_rgb_channel_view_settings_persist_independently(main_window: MainWindow):
    main_window._new_frame_with_type("rgb")
    frame = main_window.frame_manager.current_frame
    assert frame is not None
    frame.rgb_channels["red"] = np.arange(100, dtype=np.float32).reshape(10, 10)
    frame.rgb_channels["green"] = (np.arange(100, dtype=np.float32).reshape(10, 10) + 5.0)
    frame.rgb_current_channel = "red"
    main_window._sync_rgb_scalar_view(frame)

    main_window.current_scale = ScaleAlgorithm.LOG
    main_window.z1 = 1.0
    main_window.z2 = 9.0
    main_window.image_viewer.image_viewer.set_contrast_brightness(2.0, 0.2)
    main_window._persist_frame_view_state()

    frame.rgb_current_channel = "green"
    main_window.current_scale = ScaleAlgorithm.SQRT
    main_window.z1 = 0.0
    main_window.z2 = 6.0
    main_window.image_viewer.image_viewer.set_contrast_brightness(1.5, -0.1)
    main_window._persist_frame_view_state()

    assert frame.rgb_channel_scale["red"] == ScaleAlgorithm.LOG
    assert frame.rgb_channel_scale["green"] == ScaleAlgorithm.SQRT
    assert frame.rgb_channel_z1["red"] == pytest.approx(1.0)
    assert frame.rgb_channel_z2["green"] == pytest.approx(6.0)
    assert frame.rgb_channel_contrast["red"] == pytest.approx(2.0)
    assert frame.rgb_channel_brightness["green"] == pytest.approx(-0.1)

    frame.rgb_current_channel = "red"
    main_window._apply_frame_view_state(frame)
    assert main_window.current_scale == ScaleAlgorithm.LOG
    assert main_window.z1 == pytest.approx(1.0)
    assert main_window.z2 == pytest.approx(9.0)
    contrast, brightness = main_window.image_viewer.get_contrast_brightness()
    assert contrast == pytest.approx(2.0)
    assert brightness == pytest.approx(0.2)


def test_load_fits_keeps_handler_alive_and_clear_closes_it(main_window: MainWindow, monkeypatch):
    close_calls = {"count": 0}

    def _fake_load(self, filepath, memmap=True):
        self.filepath = filepath
        self.hdu_list = ["dummy"]
        return self.hdu_list

    def _fake_get_data(self, ext=0):
        return np.arange(100, dtype=np.float32).reshape(10, 10)

    def _fake_get_header(self, ext=0):
        return {}

    def _fake_close(self):
        close_calls["count"] += 1
        self.hdu_list = None

    monkeypatch.setattr("ncrads9.ui.main_window.FITSHandler.load", _fake_load)
    monkeypatch.setattr("ncrads9.ui.main_window.FITSHandler.get_data", _fake_get_data)
    monkeypatch.setattr("ncrads9.ui.main_window.FITSHandler.get_header", _fake_get_header)
    monkeypatch.setattr("ncrads9.ui.main_window.FITSHandler.close", _fake_close)

    main_window._load_fits_file("/tmp/test-large.fits")
    frame = main_window.frame_manager.current_frame
    assert frame is not None
    assert frame.fits_handler is not None

    main_window._clear_frame()
    assert close_calls["count"] == 1
    assert frame.fits_handler is None
