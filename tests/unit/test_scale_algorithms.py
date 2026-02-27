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
#
# Author: Yogesh Wadadekar

"""Tests for rendering.scale_algorithms module."""

import numpy as np
import pytest

from ncrads9.rendering.scale_algorithms import compute_zscale_limits, scale_zscale

def test_compute_zscale_limits_all_nan_returns_default_range():
    data = np.full((64, 64), np.nan, dtype=np.float32)
    z1, z2 = compute_zscale_limits(data)
    assert z1 == pytest.approx(0.0)
    assert z2 == pytest.approx(1.0)


def test_compute_zscale_limits_large_image_sampling_returns_finite_bounds():
    data = np.linspace(0.0, 1.0, 4096 * 4096, dtype=np.float32).reshape(4096, 4096)
    data[::11, ::13] = np.nan
    z1, z2 = compute_zscale_limits(data, num_samples=2048)
    assert np.isfinite(z1)
    assert np.isfinite(z2)
    assert z1 < z2


def test_scale_zscale_output_is_normalized():
    rng = np.random.default_rng(42)
    data = rng.normal(size=(256, 256)).astype(np.float32)
    scaled = scale_zscale(data, float(np.nanmin(data)), float(np.nanmax(data)))
    assert scaled.dtype == np.float32
    assert float(np.nanmin(scaled)) >= 0.0
    assert float(np.nanmax(scaled)) <= 1.0
