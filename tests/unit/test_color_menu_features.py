import os

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

from ncrads9.colormaps.colormap import Colormap
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


def test_color_menu_exposes_extended_actions(main_window: MainWindow):
    assert "aips0" in main_window.menu_bar.colormap_actions
    assert "standard" in main_window.menu_bar.colormap_actions
    assert "viridis" in main_window.menu_bar.colormap_actions
    assert main_window.menu_bar.action_reset_colormap is not None
    assert main_window.menu_bar.action_colormap_params is not None
    assert main_window.menu_bar.action_colorbar_ticks is not None


def test_colorbar_controls_update_widget_state(main_window: MainWindow):
    main_window._set_colorbar_orientation("horizontal")
    assert main_window.colorbar_widget.orientation == "horizontal"
    main_window._set_colorbar_numerics(False)
    assert main_window.colorbar_widget.show_numerics is False
    main_window._set_colorbar_spacing_mode("distance")
    assert main_window.colorbar_widget.spacing_mode == "distance"
    main_window._set_colorbar_font_size(10)
    assert main_window.colorbar_widget.label_font_size == 10


def test_register_user_colormap_adds_menu_action(main_window: MainWindow):
    data = np.linspace(0, 1, 256)
    colors = np.column_stack([data, data[::-1], data])
    cmap = Colormap("test_user_map", colors)
    main_window._register_user_colormap(cmap)
    assert "test_user_map" in main_window.custom_colormaps
    assert "test_user_map" in main_window.menu_bar.colormap_actions
