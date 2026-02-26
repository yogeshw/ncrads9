import os

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication, QFileDialog

from ncrads9.ui.main_window import MainWindow
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


def _load_test_image(main_window: MainWindow) -> None:
    frame = main_window.frame_manager.current_frame
    assert frame is not None
    image = np.arange(256, dtype=np.float32).reshape(16, 16)
    frame.image_data = image.copy()
    frame.original_image_data = image.copy()
    main_window.z1 = None
    main_window.z2 = None


def test_analysis_menu_exposes_ds9_style_actions(main_window: MainWindow):
    assert main_window.menu_bar.action_name_resolution is not None
    assert main_window.menu_bar.action_coordinate_grid is not None
    assert main_window.menu_bar.action_block_in is not None
    assert main_window.menu_bar.action_smooth is not None
    assert main_window.menu_bar.action_virtual_observatory is not None
    assert main_window.menu_bar.action_analysis_command_log is not None


def test_block_factor_actions_update_frame(main_window: MainWindow):
    _load_test_image(main_window)
    frame = main_window.frame_manager.current_frame
    assert frame is not None
    main_window._set_block_factor(4)
    assert frame.bin_factor == 4
    assert main_window.menu_bar.action_block_4.isChecked()


def test_smoothing_pipeline_updates_display_data(main_window: MainWindow):
    _load_test_image(main_window)
    frame = main_window.frame_manager.current_frame
    assert frame is not None
    original = main_window._get_display_image_data(frame).copy()
    settings = {
        "kernel_type": "Gaussian",
        "sigma": 1.5,
        "kernel_size": 5,
        "elliptical": False,
        "axis_ratio": 1.0,
        "position_angle": 0.0,
        "preserve_nan": True,
        "normalize": True,
    }
    main_window._apply_smooth_settings(settings)
    smoothed = main_window._get_display_image_data(frame)
    assert main_window.menu_bar.action_smooth.isChecked()
    assert smoothed.shape == original.shape
    assert not np.allclose(smoothed, original)


def test_grid_settings_enable_grid_action(main_window: MainWindow):
    main_window._apply_grid_settings({"coord_system": "WCS", "show_labels": True})
    assert main_window.menu_bar.action_coordinate_grid.isChecked()
    assert main_window._grid_settings is not None


def test_graph_visibility_controls(main_window: MainWindow):
    main_window._set_graph_visibility("Both")
    assert not main_window.horizontal_graph_dock.isHidden()
    assert not main_window.vertical_graph_dock.isHidden()
    main_window._set_graph_visibility("None")
    assert main_window.horizontal_graph_dock.isHidden()
    assert main_window.vertical_graph_dock.isHidden()


def test_analysis_mask_range(main_window: MainWindow):
    main_window._analysis_mask_mode = "range"
    main_window._analysis_mask_min = 0.0
    main_window._analysis_mask_max = 1.0
    data = np.array([[-1.0, 0.5, 2.0, np.nan]], dtype=np.float32)
    masked = main_window._apply_analysis_mask(data)
    assert np.isnan(masked[0, 0])
    assert np.isclose(masked[0, 1], 0.5)
    assert np.isnan(masked[0, 2])
    assert np.isnan(masked[0, 3])


def test_load_and_clear_analysis_commands(main_window: MainWindow, tmp_path, monkeypatch):
    command_file = tmp_path / "analysis_commands.txt"
    command_file.write_text("Quick URL|https://example.com\n", encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(command_file), "")),
    )
    main_window._load_analysis_commands()
    assert len(main_window._loaded_analysis_actions) == 1
    main_window._clear_analysis_commands(show_message=False)
    assert len(main_window._loaded_analysis_actions) == 0
