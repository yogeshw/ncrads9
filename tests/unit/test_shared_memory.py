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

"""Loading an image out of shared memory (M9-30)."""

from __future__ import annotations

import io
import uuid
from multiprocessing import shared_memory

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.io import shared_memory as shm
from ncrads9.io.array_reader import ArraySpec

SIZE = 8


@pytest.fixture
def segment():
    """A POSIX shared-memory segment that is cleaned up afterwards."""
    made: list[shared_memory.SharedMemory] = []

    def create(payload: bytes) -> str:
        name = f"ncrads9-{uuid.uuid4().hex[:12]}"
        block = shared_memory.SharedMemory(create=True, size=max(1, len(payload)), name=name)
        block.buf[: len(payload)] = payload
        made.append(block)
        return name

    yield create
    for block in made:
        block.close()
        try:
            block.unlink()
        except FileNotFoundError:
            pass


def _fits_bytes(data) -> bytes:
    buffer = io.BytesIO()
    fits.PrimaryHDU(data=np.asarray(data)).writeto(buffer)
    return buffer.getvalue()


# -- what can be read -------------------------------------------------------------


def test_posix_segments_can_always_be_read():
    """Which is the point of reading them: no C extension needed."""
    kinds = shm.available()
    assert kinds["posix"] is True
    assert "sysv" in kinds


def test_a_fits_file_in_shared_memory_is_read(segment):
    data = np.arange(SIZE * SIZE, dtype=np.float32).reshape(SIZE, SIZE)
    name = segment(_fits_bytes(data))
    assert np.array_equal(shm.read_fits(name), data)


def test_a_cube_in_shared_memory_is_read(segment):
    data = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)
    name = segment(_fits_bytes(data))
    assert shm.read_fits(name).shape == (2, 4, 4)


def test_a_fits_file_whose_first_hdu_is_empty_is_read(segment):
    """A multi-extension file's primary usually holds nothing."""
    buffer = io.BytesIO()
    data = np.ones((4, 4), dtype=np.float32)
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(data=data)]).writeto(buffer)
    name = segment(buffer.getvalue())
    assert np.array_equal(shm.read_fits(name), data)


def test_a_raw_array_in_shared_memory_is_read(segment):
    data = np.arange(12, dtype=np.int16).reshape(3, 4)
    name = segment(data.astype(">i2").tobytes())
    read = shm.read_array(name, ArraySpec(4, 3, bitpix=16))
    assert np.array_equal(read, data)


def test_a_raw_array_takes_ds9s_specification_as_text(segment):
    data = np.arange(12, dtype=np.float32).reshape(3, 4)
    name = segment(data.astype(">f4").tobytes())
    read = shm.read_array(name, "[xdim=4,ydim=3,bitpix=-32]")
    assert np.array_equal(read, data)


def test_a_raw_array_can_step_over_a_header(segment):
    data = np.arange(6, dtype=np.int16)
    name = segment(b"XXXX" + data.astype(">i2").tobytes())
    read = shm.read_array(name, ArraySpec(3, 2, bitpix=16, skip=4))
    assert np.array_equal(read.ravel(), data)


def test_a_segment_too_small_for_its_specification_is_refused(segment):
    name = segment(b"\x00" * 8)
    with pytest.raises(shm.SharedMemoryError, match="needs"):
        shm.read_array(name, ArraySpec(64, 64, bitpix=-32))


def test_a_segment_that_is_not_there_is_reported():
    with pytest.raises(shm.SharedMemoryError, match="no shared-memory segment"):
        shm.read_bytes("ncrads9-nothing-here", "name")


def test_a_segment_that_is_not_fits_is_reported(segment):
    name = segment(b"not a FITS file at all" * 10)
    with pytest.raises(shm.SharedMemoryError, match="FITS"):
        shm.read_fits(name)


def test_a_fits_file_with_no_image_is_reported(segment):
    buffer = io.BytesIO()
    fits.HDUList([fits.PrimaryHDU()]).writeto(buffer)
    name = segment(buffer.getvalue())
    with pytest.raises(shm.SharedMemoryError, match="no image"):
        shm.read_fits(name)


def test_a_way_of_naming_a_segment_that_does_not_exist_is_refused():
    with pytest.raises(shm.SharedMemoryError, match="not a way of naming"):
        shm.read_bytes("x", "telepathy")


def test_system_v_without_the_package_says_what_is_missing():
    """DS9 uses System V segments; Python's standard library has none, so
    the message says what to install and what works without it."""
    if shm.available()["sysv"]:
        pytest.skip("sysv_ipc is installed, so this path is not the fallback")
    with pytest.raises(shm.SharedMemoryError, match="sysv_ipc"):
        shm.read_bytes(102, "key")
    with pytest.raises(shm.SharedMemoryError, match="sysv_ipc"):
        shm.read_bytes(102, "shmid")


# -- the shm XPA point ------------------------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    window._rebuild_image_viewer(False)
    yield window
    window.close()


@pytest.fixture
def xpa(main_window):
    from ncrads9.communication.xpa.xpa_commands import XPACommands

    return XPACommands(main_window)


def _set(xpa, *args):
    return xpa.handle("shm", {"args": list(args)})


def test_the_point_loads_a_fits_segment(xpa, main_window, segment):
    data = np.arange(SIZE * SIZE, dtype=np.float32).reshape(SIZE, SIZE)
    name = segment(_fits_bytes(data))

    assert _set(xpa, name)["status"] == "ok"
    assert np.array_equal(main_window.frame_manager.current_frame.image_data, data)
    # And nothing pretends it came from a file.
    assert main_window.frame_manager.current_frame.filepath is None


def test_the_point_takes_ds9s_payload_word(xpa, main_window, segment):
    name = segment(_fits_bytes(np.ones((4, 4), dtype=np.float32)))
    assert _set(xpa, "fits", "name", name)["status"] == "ok"


def test_the_point_loads_a_raw_array(xpa, main_window, segment):
    data = np.arange(12, dtype=np.float32).reshape(3, 4)
    name = segment(data.astype(">f4").tobytes())

    assert _set(xpa, "array", "name", name, "[xdim=4,ydim=3,bitpix=-32]")["status"] == "ok"
    assert np.array_equal(main_window.frame_manager.current_frame.image_data, data)


def test_a_raw_array_without_its_dimensions_is_refused(xpa, segment):
    name = segment(b"\x00" * 64)
    assert "dimensions" in _set(xpa, "array", "name", name)["message"]


def test_a_segment_that_is_not_there_is_reported_through_xpa(xpa):
    assert _set(xpa, "ncrads9-nothing-here")["status"] == "error"


def test_the_point_needs_a_segment(xpa):
    assert _set(xpa)["status"] == "error"
    assert _set(xpa, "fits", "name")["status"] == "error"


def test_the_point_says_which_kinds_can_be_read(xpa):
    result = xpa.handle("shm", {"get": True})["result"]
    assert "posix yes" in result
    assert "sysv" in result


def test_a_system_v_request_is_reported_rather_than_ignored(xpa):
    if shm.available()["sysv"]:
        pytest.skip("sysv_ipc is installed")
    assert "sysv_ipc" in _set(xpa, "key", "102")["message"]
