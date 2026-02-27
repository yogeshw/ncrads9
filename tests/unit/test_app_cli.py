import os
from pathlib import Path

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

from ncrads9.app import (
    _cli_help_requested,
    apply_startup_cli,
    open_cli_help_in_browser,
    parse_cli_sequence,
)
from ncrads9.rendering.scale_algorithms import ScaleAlgorithm
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


def test_parse_cli_sequence_preserves_order():
    items = parse_cli_sequence(
        ["image.fits", "-rgb", "-red", "r.fits", "-green", "g.fits", "-blue", "b.fits", "-tile"]
    )
    assert items[0].kind == "file"
    assert items[0].name == "image.fits"
    assert items[1].kind == "option"
    assert items[1].name == "rgb"
    assert items[2].name == "red" and items[2].args == ["r.fits"]
    assert items[3].name == "green" and items[3].args == ["g.fits"]
    assert items[4].name == "blue" and items[4].args == ["b.fits"]
    assert items[5].name == "tile" and items[5].args == []


def test_parse_cli_sequence_keeps_file_after_scale_flag():
    items = parse_cli_sequence(["-log", "image.fits"])
    assert len(items) == 2
    assert items[0].kind == "option" and items[0].name == "log" and items[0].args == []
    assert items[1].kind == "file" and items[1].name == "image.fits"


def test_parse_cli_sequence_supports_mixed_option_arities():
    items = parse_cli_sequence(["-scale", "log", "-pan", "10", "20", "image.fits"])
    assert items[0].name == "scale" and items[0].args == ["log"]
    assert items[1].name == "pan" and items[1].args == ["10", "20"]
    assert items[2].kind == "file" and items[2].name == "image.fits"


def test_apply_startup_cli_builds_rgb_composite(main_window: MainWindow, monkeypatch):
    fake_data = {
        "r.fits": np.array([[0.0, 10.0], [0.0, 10.0]], dtype=np.float32),
        "g.fits": np.array([[0.0, 0.0], [10.0, 10.0]], dtype=np.float32),
        "b.fits": np.array([[5.0, 5.0], [5.0, 5.0]], dtype=np.float32),
    }

    def _fake_open(self, checked=False, filepath=None):
        if isinstance(checked, str) and filepath is None:
            filepath = checked
        assert filepath is not None
        frame = self.frame_manager.current_frame
        frame.filepath = Path(filepath)
        frame.image_data = fake_data[Path(filepath).name]
        frame.original_image_data = frame.image_data

    monkeypatch.setattr(MainWindow, "open_file", _fake_open)

    apply_startup_cli(
        main_window,
        ["ncrads9", "-rgb", "-red", "r.fits", "-green", "g.fits", "-blue", "b.fits"],
    )
    frame = main_window.frame_manager.current_frame
    assert frame is not None
    assert frame.frame_type == "rgb"
    assert frame.rgb_channels["red"] is not None
    assert frame.rgb_channels["green"] is not None
    assert frame.rgb_channels["blue"] is not None
    composite = main_window._compose_rgb_frame_image(frame)
    assert composite is not None
    assert composite.shape == (2, 2, 3)


def test_apply_startup_cli_log_then_file_loads_image(main_window: MainWindow, monkeypatch):
    opened_paths = []

    def _fake_open(self, checked=False, filepath=None):
        if isinstance(checked, str) and filepath is None:
            filepath = checked
        assert filepath is not None
        opened_paths.append(filepath)
        frame = self.frame_manager.current_frame
        frame.filepath = Path(filepath)
        frame.image_data = np.arange(100, dtype=np.float32).reshape(10, 10)
        frame.original_image_data = frame.image_data

    monkeypatch.setattr(MainWindow, "open_file", _fake_open)
    apply_startup_cli(main_window, ["ncrads9", "-log", "image.fits"])
    assert opened_paths == ["image.fits"]
    assert main_window.current_scale == ScaleAlgorithm.LOG
    assert main_window.frame_manager.current_frame.image_data is not None


def test_apply_startup_cli_applies_display_options(main_window: MainWindow, monkeypatch):
    def _fake_open(self, checked=False, filepath=None):
        if isinstance(checked, str) and filepath is None:
            filepath = checked
        frame = self.frame_manager.current_frame
        frame.filepath = Path(filepath or "image.fits")
        frame.image_data = np.arange(100, dtype=np.float32).reshape(10, 10)
        frame.original_image_data = frame.image_data

    monkeypatch.setattr(MainWindow, "open_file", _fake_open)

    apply_startup_cli(
        main_window,
        ["ncrads9", "image.fits", "-log", "-bin", "2", "-tile", "-invert", "-wcs", "fk4", "-degrees"],
    )
    assert main_window.current_scale == ScaleAlgorithm.LOG
    assert main_window.frame_manager.current_frame.bin_factor == 2
    assert main_window._tile_mode_enabled
    assert main_window.invert_colormap
    assert main_window.current_wcs_system == "fk4"
    assert main_window.current_wcs_format == "degrees"


def test_cli_help_detection():
    assert _cli_help_requested(["ncrads9", "--help"])
    assert _cli_help_requested(["ncrads9", "-h"])
    assert _cli_help_requested(["ncrads9", "-help"])
    assert not _cli_help_requested(["ncrads9", "image.fits"])


def test_open_cli_help_in_browser_writes_and_opens(monkeypatch, tmp_path):
    opened = {"url": None}
    monkeypatch.setattr("ncrads9.app.tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr("ncrads9.app.webbrowser.open", lambda url, new=0: opened.__setitem__("url", url) or True)

    help_path = open_cli_help_in_browser()
    assert help_path.exists()
    content = help_path.read_text(encoding="utf-8")
    assert "NCRADS9 Command Line Options" in content
    assert "-rgb" in content
    assert opened["url"] == help_path.as_uri()


def test_apply_startup_cli_colormap_alias(main_window: MainWindow, monkeypatch):
    def _fake_open(self, checked=False, filepath=None):
        frame = self.frame_manager.current_frame
        frame.filepath = Path(filepath or "image.fits")
        frame.image_data = np.arange(100, dtype=np.float32).reshape(10, 10)
        frame.original_image_data = frame.image_data

    monkeypatch.setattr(MainWindow, "open_file", _fake_open)
    apply_startup_cli(main_window, ["ncrads9", "image.fits", "-color", "heat"])
    assert main_window.current_colormap == "heat"
