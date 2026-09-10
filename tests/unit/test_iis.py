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

"""The IRAF/IIS protocol, and interactive examine (M9-29).

The protocol half is tested against a client that speaks it -- the packets
IRAF would send, over a real socket -- rather than against the server's own
idea of itself. That is the only way to know it would work, short of
installing IRAF.
"""

from __future__ import annotations

import socket
import time

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.communication.iis.iis_server import (
    COMMAND,
    CURSOR_REPLY_SIZE,
    HEADER_SIZE,
    IIS_READ,
    PACKED,
    IISCommand,
    IISServer,
    build_header,
    decode_frame,
    parse_header,
)

SIZE = 32


# -- the packet header ------------------------------------------------------------


def test_a_header_is_eight_shorts():
    """DS9's `struct iism70` (`iis.c:83`), not the eight *bytes* this
    module used to read."""
    assert HEADER_SIZE == 16
    assert len(build_header(subunit=IISCommand.MEMORY)) == 16


def test_a_header_round_trips():
    header = build_header(subunit=IISCommand.MEMORY, thingct=-16, x=5, y=6, z=2)
    fields = parse_header(header)
    assert fields is not None
    tid, thingct, subunit, _checksum, x, y, z, _t = fields
    assert (thingct, subunit, x, y, z) == (-16, IISCommand.MEMORY, 5, 6, 2)
    assert tid == 0


def test_the_checksum_is_what_says_a_header_is_one():
    """The eight shorts sum to all-ones; anything else is not a header."""
    assert parse_header(b"\x00" * 16) is None
    assert parse_header(b"not a header at!") is None
    assert parse_header(b"short") is None


def test_a_header_from_the_other_byte_order_is_not_rejected():
    """A client on a machine of the other byte order still gets through,
    which is what DS9's swap-and-retry is for.

    Which reading wins is not decidable in general -- swapping the bytes
    within each short keeps the sum at all-ones surprisingly often -- and
    DS9 prefers the unswapped one. What matters, and what this asks, is
    that a swapped header is read rather than dropped.
    """
    import struct

    fields = [0, -16, int(IISCommand.MEMORY), 0, 5, 6, 2, 0]
    total = sum(fields) & 0o177777
    fields[3] = (0o177777 - total) & 0o177777
    packed = [value - 0x10000 if value > 0x7FFF else value for value in fields]

    assert parse_header(struct.pack("<8h", *packed)) is not None
    assert parse_header(struct.pack(">8h", *packed)) is not None


def test_the_frame_is_one_bit_per_frame():
    """`decode_frameno` (`iis.c:1055`): 01 is frame 1, 02 is frame 2, 04
    is frame 3."""
    assert decode_frame(0) == 1
    assert decode_frame(0o1) == 1
    assert decode_frame(0o2) == 2
    assert decode_frame(0o4) == 3
    assert decode_frame(0o10) == 4


def test_the_cursor_reply_is_the_fixed_size_iraf_reads():
    """IRAF reads `SZ_IMCURVAL` bytes, so a shorter reply leaves it
    waiting for the rest for ever."""
    reply = IISServer.cursor_reply(12.5, 34.25, 2)
    assert len(reply) == CURSOR_REPLY_SIZE
    assert reply.decode("ascii").split()[:3] == ["12.500", "34.250", "2"]


# -- the server, over a real socket -------------------------------------------------


class Client:
    """A client that speaks the IIS protocol, as IRAF's would."""

    def __init__(self, port: int) -> None:
        self.socket = socket.create_connection(("localhost", port), timeout=5.0)

    def send(self, **header) -> None:
        self.socket.sendall(build_header(**header))

    def write_pixels(self, pixels: bytes, x: int = 0, y: int = 0, frame: int = 1) -> None:
        """A packed memory write, which is how IRAF sends an image."""
        self.send(
            subunit=IISCommand.MEMORY,
            thingct=-len(pixels),
            tid=PACKED,
            x=x,
            y=y,
            z=1 << (frame - 1),
        )
        self.socket.sendall(pixels)

    def read_cursor(self) -> str:
        self.send(subunit=IISCommand.IMCURSOR, tid=IIS_READ)
        return self.socket.recv(CURSOR_REPLY_SIZE).decode("ascii").rstrip("\x00")

    def close(self) -> None:
        self.socket.close()


@pytest.fixture
def server():
    """A server on a port nothing else is using."""
    with socket.socket() as probe:
        probe.bind(("localhost", 0))
        port = probe.getsockname()[1]

    made = IISServer(socket_port=port)
    assert made.start() is True
    made.port = port
    yield made
    made.stop()


def _wait_for(predicate, seconds: float = 3.0) -> bool:
    """Wait for the server's thread to catch up."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_a_memory_write_reaches_the_frame_buffer(server):
    """The old `_handle_memory` never stored a pixel, so nothing IRAF sent
    could have been displayed."""
    seen: list[tuple[int, np.ndarray]] = []
    server.set_image_callback(lambda frame, data: seen.append((frame, data.copy())))

    client = Client(server.port)
    client.write_pixels(bytes([7, 8, 9, 10]), x=2, y=1)
    assert _wait_for(lambda: bool(seen))
    client.close()

    frame, data = seen[-1]
    assert frame == 1
    assert list(data[1, 2:6]) == [7, 8, 9, 10]


def test_a_write_gives_the_whole_frame_to_the_callback(server):
    """IRAF writes a line at a time; a caller handed one line could not
    display a frame."""
    seen: list[np.ndarray] = []
    server.set_image_callback(lambda _frame, data: seen.append(data))

    client = Client(server.port)
    client.write_pixels(bytes([1, 2, 3]))
    assert _wait_for(lambda: bool(seen))
    client.close()
    assert seen[-1].shape == (server.FRAME_HEIGHT, server.FRAME_WIDTH)


def test_two_writes_fill_in_rather_than_replace(server):
    seen: list[np.ndarray] = []
    server.set_image_callback(lambda _frame, data: seen.append(data.copy()))

    client = Client(server.port)
    client.write_pixels(bytes([1, 1, 1]), x=0, y=0)
    assert _wait_for(lambda: len(seen) == 1)
    client.write_pixels(bytes([2, 2, 2]), x=0, y=1)
    assert _wait_for(lambda: len(seen) == 2)
    client.close()

    data = seen[-1]
    assert list(data[0, :3]) == [1, 1, 1]
    assert list(data[1, :3]) == [2, 2, 2]


def test_a_write_names_the_frame_it_is_for(server):
    seen: list[int] = []
    server.set_image_callback(lambda frame, _data: seen.append(frame))

    client = Client(server.port)
    client.write_pixels(bytes([1]), frame=3)
    assert _wait_for(lambda: bool(seen))
    client.close()
    assert seen[-1] == 3


def test_a_write_past_the_end_of_the_frame_is_dropped_not_fatal(server):
    seen: list[int] = []
    server.set_image_callback(lambda frame, _data: seen.append(frame))

    client = Client(server.port)
    client.send(
        subunit=IISCommand.MEMORY,
        thingct=-4,
        tid=PACKED,
        x=0,
        y=server.FRAME_HEIGHT + 10,
        z=1,
    )
    client.socket.sendall(bytes([1, 2, 3, 4]))
    # Nothing is displayed, and the server is still answering.
    time.sleep(0.2)
    assert seen == []
    assert client.read_cursor() != ""
    client.close()


def test_reading_the_cursor_answers_where_it_is(server):
    server.set_cursor_callback(lambda _x, _y, frame: (11.0, 22.0, frame))
    client = Client(server.port)
    reply = client.read_cursor()
    client.close()
    assert reply.split()[:2] == ["11.000", "22.000"]


def test_a_cursor_callback_that_raises_does_not_kill_the_server(server):
    def boom(_x, _y, _frame):
        raise RuntimeError("no")

    server.set_cursor_callback(boom)
    client = Client(server.port)
    assert client.read_cursor() != ""
    client.close()


def test_writing_the_cursor_moves_it(server):
    moved: list[tuple[float, float, int]] = []
    server.set_cursor_write_callback(lambda x, y, frame: moved.append((x, y, frame)))

    client = Client(server.port)
    client.send(subunit=IISCommand.IMCURSOR, x=30, y=40, z=1)
    assert _wait_for(lambda: bool(moved))
    client.close()
    assert moved[-1][:2] == (30.0, 40.0)


def test_the_wcs_text_is_kept_and_can_be_read_back(server):
    client = Client(server.port)
    text = b"an image name\n1 0 0 1 0 0\n"
    client.send(subunit=IISCommand.WCS, thingct=-len(text), tid=PACKED, z=1)
    client.socket.sendall(text)
    assert _wait_for(lambda: bool(server._frames[1].wcs))

    client.send(subunit=IISCommand.WCS, thingct=-64, tid=IIS_READ | PACKED, z=1)
    read = client.socket.recv(64).decode("ascii").rstrip("\x00")
    client.close()
    assert "an image name" in read


def test_a_command_mode_lut_write_selects_the_frame(server):
    """Which is how IRAF says "display frame 2"."""
    chosen: list[int] = []
    server.set_frame_callback(chosen.append)

    client = Client(server.port)
    client.send(
        subunit=IISCommand.LUT | COMMAND,
        thingct=-2,
        tid=PACKED,
    )
    client.socket.sendall(b"\x00\x02")  # frame 2, big-endian
    assert _wait_for(lambda: bool(chosen))
    client.close()
    assert chosen[-1] == 2


def test_the_feedback_subunit_clears_a_frame(server):
    seen: list[np.ndarray] = []
    server.set_image_callback(lambda _frame, data: seen.append(data.copy()))

    client = Client(server.port)
    client.write_pixels(bytes([9, 9, 9]))
    assert _wait_for(lambda: bool(seen))

    client.send(subunit=IISCommand.FEEDBACK, z=1)
    assert _wait_for(lambda: len(seen) > 1 and not seen[-1].any())
    client.close()
    assert not seen[-1].any()


def test_a_packet_with_a_bad_checksum_is_ignored(server):
    seen: list[int] = []
    server.set_image_callback(lambda frame, _data: seen.append(frame))

    client = Client(server.port)
    client.socket.sendall(b"\x01" * HEADER_SIZE)
    time.sleep(0.2)
    assert seen == []
    client.close()


def test_the_unpacked_length_is_in_shorts(server):
    """`ndatabytes = -thingct`, doubled unless the packet is packed
    (`iis.c:566`)."""
    seen: list[np.ndarray] = []
    server.set_image_callback(lambda _frame, data: seen.append(data.copy()))

    client = Client(server.port)
    # thingct -2 with no PACKED flag means four bytes.
    client.send(subunit=IISCommand.MEMORY, thingct=-2, x=0, y=0, z=1)
    client.socket.sendall(bytes([1, 2, 3, 4]))
    assert _wait_for(lambda: bool(seen))
    client.close()
    assert list(seen[-1][0, :4]) == [1, 2, 3, 4]


def test_starting_twice_is_harmless(server):
    assert server.start() is True


def test_a_port_that_is_taken_is_reported():
    with socket.socket() as taken:
        taken.bind(("localhost", 0))
        taken.listen(1)
        port = taken.getsockname()[1]
        assert IISServer(socket_port=port).start() is False


# -- the controller over it -----------------------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    rows, columns = np.indices((SIZE, SIZE))
    path = tmp_path / "sky.fits"
    header = fits.Header(
        {
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CRPIX1": SIZE / 2,
            "CRPIX2": SIZE / 2,
            "CRVAL1": 150.0,
            "CRVAL2": 2.0,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
        }
    )
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32), header=header).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    yield window
    window.close()


def test_the_controller_starts_and_stops_the_server(main_window):
    with socket.socket() as probe:
        probe.bind(("localhost", 0))
        port = probe.getsockname()[1]

    assert main_window.iis.start(port) is True
    assert main_window.iis.running() is True
    assert main_window.iis.start(port) is True
    assert "already running" in main_window.status_bar.currentMessage()

    main_window.iis.stop()
    assert main_window.iis.running() is False


def test_a_port_that_cannot_be_had_is_reported(main_window):
    with socket.socket() as taken:
        taken.bind(("localhost", 0))
        taken.listen(1)
        assert main_window.iis.start(taken.getsockname()[1]) is False
    assert "could not be started" in main_window.status_bar.currentMessage()


def test_what_iraf_writes_is_displayed(main_window):
    """The whole point of the server: `display` in IRAF puts an image
    here."""
    data = np.arange(16, dtype=np.uint8).reshape(4, 4)
    main_window.iis.on_image(1, data)
    assert main_window.frame_manager.current_frame.image_data.shape == (4, 4)


def test_the_cursor_read_answers_with_the_crosshair(main_window):
    main_window.crosshair.move_to(12.0, 13.0)
    assert main_window.iis.on_cursor_read(0.0, 0.0, 1) == (12.0, 13.0, 1)


def test_the_cursor_read_falls_back_to_the_pointer(main_window):
    main_window.crosshair.set_enabled(False)
    main_window.frame_manager.current_frame.crosshair = None
    main_window._last_mouse_pos = (9, 10)
    x, y, _frame = main_window.iis.on_cursor_read(0.0, 0.0, 1)
    # The readout counts from zero and IIS from one.
    assert (x, y) == (10.0, 11.0)


def test_iraf_can_move_the_crosshair(main_window):
    main_window.iis.on_cursor_write(4.0, 5.0, 1)
    assert main_window.crosshair.position() == (4.0, 5.0)


def test_the_iis_filename_is_kept_per_frame(main_window):
    main_window.iis.set_filename("a.fits", 1)
    main_window.iis.set_filename("b.fits", 4)
    assert main_window.iis.filename(1) == "a.fits"
    assert main_window.iis.filename(4) == "b.fits"
    assert main_window.iis.filename(9) == ""


# -- interactive examine ---------------------------------------------------------------


def _click_soon(main_window, x: float, y: float, delay: int = 10) -> None:
    """Click on the image once the examine is waiting for it."""
    from PyQt6.QtCore import QTimer

    def click() -> None:
        overlay = main_window.image_viewer.region_overlay
        if overlay.examine_handler is not None:
            overlay.examine_handler(x, y)

    QTimer.singleShot(delay, click)


def test_an_examine_waits_for_a_click_and_answers(main_window):
    _click_soon(main_window, 10.0, 20.0)
    assert main_window.iis.examine("coordinate", "image") == "10 20"


def test_an_examine_that_is_never_clicked_gives_up(main_window):
    assert main_window.iis.examine("coordinate", timeout=50) == ""
    assert "nothing was clicked" in main_window.status_bar.currentMessage()


def test_an_examine_answers_in_sky_coordinates(main_window):
    _click_soon(main_window, 16.0, 16.0)
    answer = main_window.iis.examine("coordinate", "wcs", "fk5", "degrees")
    longitude, latitude = (float(value) for value in answer.split())
    assert longitude == pytest.approx(150.0, abs=0.01)
    assert latitude == pytest.approx(2.0, abs=0.01)


def test_an_examine_answers_in_sexagesimal(main_window):
    _click_soon(main_window, 16.0, 16.0)
    answer = main_window.iis.examine("coordinate", "wcs", "fk5", "sexagesimal")
    assert ":" in answer


def test_an_examine_answers_with_a_data_value(main_window):
    _click_soon(main_window, 11.0, 21.0)
    # The fixture's data is row + column, counting from zero.
    assert main_window.iis.examine("data") == "30"


def test_an_examine_answers_with_a_box_of_values(main_window):
    _click_soon(main_window, 11.0, 21.0)
    answer = main_window.iis.examine("data", width=3, height=3)
    rows = answer.splitlines()
    assert len(rows) == 3
    assert len(rows[0].split()) == 3


def test_an_examine_expands_a_macro(main_window):
    _click_soon(main_window, 7.0, 8.0)
    answer = main_window.iis.examine(macro="clicked at $x,$y in $filename")
    assert answer.startswith("clicked at 7,8 in ")
    assert "sky.fits" in answer


def test_the_examine_hook_is_put_back_afterwards(main_window):
    """Or every click after an examine would be swallowed."""
    overlay = main_window.image_viewer.region_overlay
    _click_soon(main_window, 1.0, 1.0)
    main_window.iis.examine("coordinate")
    assert overlay.examine_handler is None


# -- the iis and iexam XPA points --------------------------------------------------------


@pytest.fixture
def xpa(main_window):
    from ncrads9.communication.xpa.xpa_commands import XPACommands

    return XPACommands(main_window)


def test_the_iis_point_sets_and_reads_the_filename(xpa, main_window):
    assert xpa.handle("iis", {"args": ["filename", "foo.fits"]})["status"] == "ok"
    assert xpa.handle("iis", {"get": True})["result"] == "foo.fits"
    assert xpa.handle("iis", {"args": ["filename", "bar.fits", "4"]})["status"] == "ok"
    assert main_window.iis.filename(4) == "bar.fits"
    assert xpa.handle("iis", {"args": ["filename"]})["status"] == "error"
    assert xpa.handle("iis", {"args": ["wibble"]})["status"] == "error"


def test_the_iis_point_starts_and_stops_the_server(xpa, main_window):
    with socket.socket() as probe:
        probe.bind(("localhost", 0))
        port = probe.getsockname()[1]

    assert xpa.handle("iis", {"args": ["start", str(port)]})["status"] == "ok"
    assert main_window.iis.running() is True
    assert xpa.handle("iis", {"args": ["stop"]})["status"] == "ok"
    assert main_window.iis.running() is False


def test_the_iexam_point_answers_a_click(xpa, main_window):
    _click_soon(main_window, 5.0, 6.0)
    assert xpa.handle("iexam", {"get": True, "args": ["coordinate", "image"]})["result"] == "5 6"


def test_the_iexam_point_ignores_ds9s_event_word(xpa, main_window):
    """DS9 takes button, key or any; ours is always a button, since a key
    event needs the keyboard grab its cursor mode takes."""
    _click_soon(main_window, 5.0, 6.0)
    result = xpa.handle("iexam", {"get": True, "args": ["key", "coordinate", "image"]})
    assert result["result"] == "5 6"


def test_the_iexam_point_takes_a_sky_frame_as_a_shorthand(xpa, main_window):
    """`iexam coordinate fk5`, which DS9 documents."""
    _click_soon(main_window, 16.0, 16.0)
    answer = xpa.handle("iexam", {"get": True, "args": ["coordinate", "fk5"]})["result"]
    assert float(answer.split()[0]) == pytest.approx(150.0, abs=0.01)


def test_the_iexam_point_answers_data(xpa, main_window):
    _click_soon(main_window, 11.0, 21.0)
    assert xpa.handle("iexam", {"get": True, "args": ["data"]})["result"] == "30"


def test_the_iexam_point_expands_a_macro(xpa, main_window):
    _click_soon(main_window, 2.0, 3.0)
    answer = xpa.handle("iexam", {"get": True, "args": ["at $x,$y"]})["result"]
    assert answer == "at 2,3"


def test_imexam_is_an_alias_of_iexam(xpa, main_window):
    _click_soon(main_window, 1.0, 2.0)
    assert xpa.handle("imexam", {"get": True, "args": ["coordinate", "image"]})["result"] == "1 2"
