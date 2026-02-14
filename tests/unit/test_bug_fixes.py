import importlib.util
from pathlib import Path

import numpy as np
import pytest

from ncrads9.colormaps.builtin_maps import get_builtin_colormap
from ncrads9.frames.frame_manager import FrameManager
from ncrads9.io.session.backup_reader import BackupReader
from ncrads9.utils.math_utils import apply_scaling

_SCALE_ALGO_PATH = Path(__file__).resolve().parents[2] / "ncrads9" / "rendering" / "scale_algorithms.py"
_SCALE_ALGO_SPEC = importlib.util.spec_from_file_location("ncrads9_scale_algorithms", _SCALE_ALGO_PATH)
assert _SCALE_ALGO_SPEC is not None and _SCALE_ALGO_SPEC.loader is not None
_SCALE_ALGO_MODULE = importlib.util.module_from_spec(_SCALE_ALGO_SPEC)
_SCALE_ALGO_SPEC.loader.exec_module(_SCALE_ALGO_MODULE)
scale_asinh = _SCALE_ALGO_MODULE.scale_asinh
scale_histogram_equalization = _SCALE_ALGO_MODULE.scale_histogram_equalization


def test_scale_asinh_rejects_nonpositive_parameter():
    data = np.array([[0.0, 0.5, 1.0]], dtype=np.float32)
    with pytest.raises(ValueError, match="positive"):
        scale_asinh(data, 0.0, 1.0, a=0.0)


def test_apply_scaling_asinh_rejects_nonpositive_parameter():
    data = np.array([0.0, 0.5, 1.0], dtype=np.float64)
    with pytest.raises(ValueError, match="positive"):
        apply_scaling(data, scale="asinh", asinh_a=0.0)


def test_scale_histogram_equalization_all_nan_returns_zeros():
    data = np.array([[np.nan, np.nan]], dtype=np.float32)
    result = scale_histogram_equalization(data, 0.0, 1.0)
    assert result.dtype == np.float32
    assert np.array_equal(result, np.zeros_like(data, dtype=np.float32))


def test_get_builtin_colormap_clamps_small_color_count():
    colormap = get_builtin_colormap("heat", n_colors=1)
    assert colormap is not None
    assert colormap.colors.shape == (2, 3)


def test_next_and_previous_frame_handle_stale_active_id():
    manager = FrameManager()
    first = manager.create_frame()
    second = manager.create_frame()

    manager._active_frame_id = 999
    manager.next_frame()
    assert manager.active_frame_id == first.frame_id

    manager._active_frame_id = 999
    manager.previous_frame()
    assert manager.active_frame_id == second.frame_id


def test_backup_reader_parse_region_ignores_missing_close_paren():
    reader = BackupReader(__file__)
    region = reader._parse_region("circle(10,20,5")
    assert region["type"] is None
    assert region["coords"] == []
