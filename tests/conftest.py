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

"""Pytest fixtures for NCRADS9 testing."""

import pytest
import numpy as np
from pathlib import Path


@pytest.fixture
def sample_image_data():
    """Create sample 2D image data for testing."""
    return np.random.random((100, 100)).astype(np.float32)


@pytest.fixture
def test_data_dir():
    """Return path to test data directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_fits_path(test_data_dir):
    """Return path to sample FITS file."""
    return test_data_dir / "sample.fits"
