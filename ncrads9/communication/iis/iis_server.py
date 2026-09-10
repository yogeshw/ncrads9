# NCRADS9 - IIS Server Implementation
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

"""
The IRAF/IIS "imtool" protocol, so IRAF's `display` and `imexam` can talk
to us.

The protocol is a 16-byte header -- eight big-endian shorts -- followed by
however much data the header says, and it is specified by DS9's own
implementation, `tksao/iis/iis.c`:

    struct iism70 { short tid, thingct, subunit, checksum, x, y, z, t; }

    subunit & 077   which command: MEMORY 01, LUT 02, FEEDBACK 05,
                    IMCURSOR 020, WCS 021
    tid & 0100000   IIS_READ: this is a read rather than a write
    tid & 040000    PACKED: the data is bytes rather than shorts
    subunit & 0100000  COMMAND: a command-mode write
    -thingct        how much data follows, in shorts unless PACKED
    z               the frame, one bit per frame: 01 is frame 1, 02 is
                    frame 2, 04 is frame 3
    checksum        the eight shorts sum to 0177777; if they do not, the
                    sender's byte order is the other one

What this module had before was a plausible-looking sketch: an 8-byte
header read as `>HBBHHHH`, the command taken from `tid` rather than
`subunit`, and a memory write that never stored a pixel. None of it could
have talked to IRAF. M9-29 rewrote the packet layer from the
specification above and tested it against a client that speaks it.

Author: Yogesh Wadadekar
"""

import logging
import os
import socket
import struct
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from numpy.typing import NDArray


class IISCommand(IntEnum):
    """The subunits an IIS packet can address (`iis.c:63`)."""

    MEMORY = 0o1
    LUT = 0o2
    FEEDBACK = 0o5
    IMCURSOR = 0o20
    WCS = 0o21


#: Flags in a packet's `tid`.
IIS_READ = 0o100000
PACKED = 0o40000
IMC_SAMPLE = 0o40000

#: A flag in its `subunit`.
COMMAND = 0o100000

#: What the low bits of `subunit` hold: which command it is.
SUBUNIT_MASK = 0o77

#: What the low bits of `x` and `y` hold.
XY_MASK = 0o77777

#: How large a packet header is: eight shorts.
HEADER_SIZE = 16

#: How long the cursor reply is. IRAF reads a fixed-size buffer
#: (`SZ_IMCURVAL`, `iis.c:75`), so a shorter reply leaves it waiting.
CURSOR_REPLY_SIZE = 160


def decode_frame(z: int) -> int:
    """Which frame a packet's `z` names.

    One bit per frame: 01 is frame 1, 02 is frame 2, 04 is frame 3
    (`decode_frameno`, `iis.c:1055`).
    """
    value = int(z) & 0o177777
    if not value:
        return 1
    position = 0
    while not value & 1:
        value >>= 1
        position += 1
    return max(1, position + 1)


def parse_header(header: bytes) -> tuple[int, ...] | None:
    """One IIS packet header, in whichever byte order it came in.

    Args:
        header: Sixteen bytes.

    Returns:
        (tid, thingct, subunit, checksum, x, y, z, t), or None if the
        bytes are not a packet header in either byte order.
    """
    if len(header) < HEADER_SIZE:
        return None
    for order in (">", "<"):
        fields = struct.unpack(order + "8h", header[:HEADER_SIZE])
        # The eight shorts sum to all-ones; that is what says the byte
        # order is right, and it is how IRAF's own clients are detected.
        if sum(fields) & 0o177777 == 0o177777:
            return fields
    return None


def build_header(
    subunit: int,
    thingct: int = 0,
    tid: int = 0,
    x: int = 0,
    y: int = 0,
    z: int = 0,
    t: int = 0,
) -> bytes:
    """One IIS packet header, checksum and all.

    Here so that a test -- or a script driving us the way IRAF does -- can
    speak the protocol without writing the checksum by hand.
    """
    fields = [tid, thingct, subunit, 0, x, y, z, t]
    total = sum(fields) & 0o177777
    fields[3] = (0o177777 - total) & 0o177777
    packed = [value - 0x10000 if value > 0x7FFF else value for value in fields]
    return struct.pack(">8h", *packed)


@dataclass
class IISFrame:
    """Represents an IIS frame buffer.

    Attributes:
        number: Frame number (1-indexed).
        width: Frame width in pixels.
        height: Frame height in pixels.
        data: Frame pixel data.
        wcs: WCS mapping string.
    """

    number: int
    width: int
    height: int
    data: NDArray[np.uint8] | None = None
    wcs: str = ""


class _FifoChannel:
    """A pair of FIFOs behind the small part of a socket the handlers use.

    The protocol is the same over a socket and over IRAF's `/dev/imt1i`
    and `/dev/imt1o`; only the reading and writing differ, so the handlers
    are given one of these instead of a socket and never learn which they
    have.
    """

    def __init__(self, read_fd: int, write_fd: int | None) -> None:
        """
        Args:
            read_fd: The FIFO IRAF writes to.
            write_fd: The FIFO IRAF reads from, or None if it is not open.
        """
        self._read_fd = read_fd
        self._write_fd = write_fd

    def recv(self, size: int) -> bytes:
        """Read up to `size` bytes, as a socket's `recv` does."""
        try:
            return os.read(self._read_fd, size)
        except OSError:
            return b""

    def sendall(self, data: bytes) -> None:
        """Write everything, as a socket's `sendall` does."""
        if self._write_fd is None:
            return
        try:
            os.write(self._write_fd, data)
        except OSError:
            pass


class IISServer:
    """IIS server for IRAF tool compatibility.

    This class implements an IIS server that listens for connections from
    IRAF tools and handles image display and cursor communication.

    Attributes:
        fifo_in: Input FIFO path (from IRAF).
        fifo_out: Output FIFO path (to IRAF).
        running: Whether the server is running.
    """

    DEFAULT_FIFO_IN: str = "/dev/imt1i"
    DEFAULT_FIFO_OUT: str = "/dev/imt1o"
    DEFAULT_SOCKET_PATH: str = "/tmp/.IMT%d"

    FRAME_WIDTH: int = 512
    FRAME_HEIGHT: int = 512
    MAX_FRAMES: int = 16
    HEADER_SIZE: int = HEADER_SIZE

    def __init__(
        self,
        fifo_in: str = DEFAULT_FIFO_IN,
        fifo_out: str = DEFAULT_FIFO_OUT,
        use_socket: bool = True,
        socket_port: int = 5137,
    ) -> None:
        """Initialize the IIS server.

        Args:
            fifo_in: Path to input FIFO.
            fifo_out: Path to output FIFO.
            use_socket: Whether to use socket instead of FIFOs.
            socket_port: Port for socket connection.
        """
        self.fifo_in: str = fifo_in
        self.fifo_out: str = fifo_out
        self.use_socket: bool = use_socket
        self.socket_port: int = socket_port
        self.running: bool = False

        self._socket: socket.socket | None = None
        self._fifo_in_fd: int | None = None
        self._fifo_out_fd: int | None = None
        self._thread: threading.Thread | None = None
        self._logger: logging.Logger = logging.getLogger(__name__)

        self._frames: dict[int, IISFrame] = {}
        self._current_frame: int = 1
        self._cursor_callback: Callable[[float, float, int], None] | None = None
        #: Called when IRAF *moves* the cursor rather than reading it.
        self._cursor_write_callback: Callable[[float, float, int], None] | None = None
        #: Called when IRAF selects a frame through the LUT subunit.
        self._frame_callback: Callable[[int], None] | None = None
        self._image_callback: Callable[[int, NDArray[np.uint8]], None] | None = None

        # Initialize frames
        for i in range(1, self.MAX_FRAMES + 1):
            self._frames[i] = IISFrame(
                number=i,
                width=self.FRAME_WIDTH,
                height=self.FRAME_HEIGHT,
            )

    def set_cursor_callback(
        self,
        callback: Callable[[float, float, int], None],
    ) -> None:
        """Set callback for cursor read events.

        Args:
            callback: Function(x, y, frame) to call on cursor read.
        """
        self._cursor_callback = callback

    def set_cursor_write_callback(
        self,
        callback: Callable[[float, float, int], None],
    ) -> None:
        """Set what happens when IRAF moves the cursor.

        Args:
            callback: Called with (x, y, frame).
        """
        self._cursor_write_callback = callback

    def set_frame_callback(self, callback: Callable[[int], None]) -> None:
        """Set what happens when IRAF selects a frame.

        Args:
            callback: Called with the frame number.
        """
        self._frame_callback = callback

    def set_image_callback(
        self,
        callback: Callable[[int, NDArray[np.uint8]], None],
    ) -> None:
        """Set callback for image display events.

        Args:
            callback: Function(frame, data) to call on image write.
        """
        self._image_callback = callback

    def start(self) -> bool:
        """Start the IIS server.

        Returns:
            True if server started successfully.
        """
        if self.running:
            self._logger.warning("IIS server already running")
            return True

        try:
            if self.use_socket:
                return self._start_socket()
            else:
                return self._start_fifo()
        except Exception as e:
            self._logger.error(f"Failed to start IIS server: {e}")
            self._cleanup()
            return False

    def _start_socket(self) -> bool:
        """Start socket-based IIS server.

        Returns:
            True if successful.
        """
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind(("localhost", self.socket_port))
            self._socket.listen(1)
            self._socket.settimeout(1.0)

            self.running = True
            self._thread = threading.Thread(
                target=self._socket_loop,
                daemon=True,
            )
            self._thread.start()

            self._logger.info(f"IIS server started on port {self.socket_port}")
            return True

        except OSError as e:
            self._logger.error(f"Failed to start IIS socket server: {e}")
            return False

    def _start_fifo(self) -> bool:
        """Start FIFO-based IIS server.

        Returns:
            True if successful.
        """
        # Check if FIFOs exist
        if not os.path.exists(self.fifo_in):
            self._logger.error(f"Input FIFO not found: {self.fifo_in}")
            return False

        if not os.path.exists(self.fifo_out):
            self._logger.error(f"Output FIFO not found: {self.fifo_out}")
            return False

        try:
            self.running = True
            self._thread = threading.Thread(
                target=self._fifo_loop,
                daemon=True,
            )
            self._thread.start()

            self._logger.info("IIS server started using FIFOs")
            return True

        except OSError as e:
            self._logger.error(f"Failed to start IIS FIFO server: {e}")
            return False

    def stop(self) -> None:
        """Stop the IIS server."""
        self.running = False

        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        self._cleanup()
        self._logger.info("IIS server stopped")

    def _cleanup(self) -> None:
        """Clean up server resources."""
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

        if self._fifo_in_fd is not None:
            try:
                os.close(self._fifo_in_fd)
            except OSError:
                pass
            self._fifo_in_fd = None

        if self._fifo_out_fd is not None:
            try:
                os.close(self._fifo_out_fd)
            except OSError:
                pass
            self._fifo_out_fd = None

    def _socket_loop(self) -> None:
        """Main loop for socket connections."""
        while self.running and self._socket is not None:
            try:
                client, addr = self._socket.accept()
                self._logger.debug(f"IIS connection from {addr}")

                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client,),
                    daemon=True,
                )
                client_thread.start()

            except TimeoutError:
                continue
            except OSError:
                if self.running:
                    self._logger.error("Error accepting IIS connection")
                break

    def _fifo_loop(self) -> None:
        """Main loop for FIFO connections."""
        while self.running:
            try:
                # Open FIFOs (blocking)
                self._fifo_in_fd = os.open(self.fifo_in, os.O_RDONLY)
                self._fifo_out_fd = os.open(self.fifo_out, os.O_WRONLY)

                self._process_fifo()

            except OSError as e:
                self._logger.error(f"FIFO error: {e}")
                if self.running:
                    import time

                    time.sleep(1.0)
            finally:
                if self._fifo_in_fd is not None:
                    try:
                        os.close(self._fifo_in_fd)
                    except OSError:
                        pass
                    self._fifo_in_fd = None
                if self._fifo_out_fd is not None:
                    try:
                        os.close(self._fifo_out_fd)
                    except OSError:
                        pass
                    self._fifo_out_fd = None

    def _handle_client(self, client: socket.socket) -> None:
        """Handle a client connection.

        Args:
            client: Client socket.
        """
        try:
            client.settimeout(30.0)

            while self.running:
                header = self._recv_all(client, self.HEADER_SIZE)
                if not header:
                    break

                self._process_command(header, client)

        except TimeoutError:
            pass
        except Exception as e:
            self._logger.error(f"Error handling IIS client: {e}")
        finally:
            try:
                client.close()
            except OSError:
                pass

    def _process_fifo(self) -> None:
        """Process commands from FIFO."""
        if self._fifo_in_fd is None:
            return

        while self.running:
            try:
                header = os.read(self._fifo_in_fd, self.HEADER_SIZE)
                if not header or len(header) < self.HEADER_SIZE:
                    break

                self._process_fifo_command(header)

            except OSError:
                break

    def _recv_all(self, sock: socket.socket, size: int) -> bytes:
        """Receive exactly size bytes from socket.

        Args:
            sock: Socket to receive from.
            size: Number of bytes to receive.

        Returns:
            Received bytes.
        """
        data = b""
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                break
            data += chunk
        return data

    def _process_command(
        self,
        header: bytes,
        client: socket.socket,
    ) -> None:
        """Handle one IIS packet.

        Args:
            header: The sixteen header bytes.
            client: The socket it came in on, and the one a reply goes out
                on.
        """
        fields = parse_header(header)
        if fields is None:
            self._logger.debug("IIS packet with a bad checksum in either byte order")
            return

        tid, thingct, subunit, _checksum, x, y, z, t = fields
        tid &= 0o177777
        subunit &= 0o177777
        command = subunit & SUBUNIT_MASK

        # The data length is a negative count of shorts, or of bytes when
        # the packet says it is packed.
        nbytes = -int(thingct)
        if not tid & PACKED:
            nbytes *= 2

        if command == IISCommand.MEMORY:
            self._handle_memory(client, tid, nbytes, x & XY_MASK, y & XY_MASK, z)
        elif command == IISCommand.WCS:
            self._handle_wcs(client, tid, nbytes, z)
        elif command == IISCommand.IMCURSOR:
            self._handle_cursor(client, tid, x & XY_MASK, y & XY_MASK, z)
        elif command == IISCommand.LUT:
            self._handle_lut(client, subunit, nbytes)
        elif command == IISCommand.FEEDBACK:
            self._handle_feedback(z)
        else:
            self._logger.debug("IIS subunit %o is not one we answer", command)

    def _process_fifo_command(self, header: bytes) -> None:
        """Handle one IIS packet that arrived on a FIFO.

        The header is the same; only where the data and the reply go
        differs, and the FIFO is wrapped so the handlers cannot tell.
        """
        if self._fifo_in_fd is None:
            return
        self._process_command(header, _FifoChannel(self._fifo_in_fd, self._fifo_out_fd))

    def _handle_memory(
        self,
        client,
        tid: int,
        nbytes: int,
        x: int,
        y: int,
        z: int,
    ) -> None:
        """A frame-buffer read or write: the pixels themselves.

        A write puts `nbytes` pixels into the frame at (x, y) and tells
        whoever is watching that the frame changed -- which is what makes
        IRAF's `display` put an image on the screen. IRAF writes a line at
        a time, so the buffer is kept and filled in rather than replaced.
        """
        number = decode_frame(z)
        frame = self._frames.setdefault(
            number,
            IISFrame(number=number, width=self.FRAME_WIDTH, height=self.FRAME_HEIGHT),
        )
        if frame.data is None:
            frame.data = np.zeros((frame.height, frame.width), dtype=np.uint8)
        self._current_frame = number

        if tid & IIS_READ:
            # A read: hand back what is in the buffer, from (x, y) on.
            flat = frame.data.reshape(-1)
            start = min(y * frame.width + x, flat.size)
            chunk = flat[start : start + max(0, nbytes)]
            payload = chunk.tobytes()
            if len(payload) < nbytes:
                payload += b"\x00" * (nbytes - len(payload))
            client.sendall(payload)
            return

        if nbytes <= 0:
            return
        data = self._recv_all(client, nbytes)
        if not data:
            return

        pixels = np.frombuffer(data, dtype=np.uint8)
        flat = frame.data.reshape(-1)
        start = min(y * frame.width + x, flat.size)
        room = flat.size - start
        if room <= 0:
            self._logger.debug("IIS write past the end of frame %d", number)
            return
        flat[start : start + min(room, pixels.size)] = pixels[: min(room, pixels.size)]

        if self._image_callback is not None:
            # The whole frame, not the fragment: the caller displays a
            # frame, and a caller handed one line of it could not.
            self._image_callback(number, frame.data)

    def _handle_wcs(self, client, tid: int, nbytes: int, z: int) -> None:
        """The WCS text IRAF sends with an image, or a request for it."""
        number = decode_frame(z)
        frame = self._frames.setdefault(
            number,
            IISFrame(number=number, width=self.FRAME_WIDTH, height=self.FRAME_HEIGHT),
        )

        if tid & IIS_READ:
            text = (frame.wcs or "").encode("ascii", "replace")
            client.sendall(text.ljust(max(nbytes, len(text)), b"\x00"))
            return

        if nbytes <= 0:
            return
        data = self._recv_all(client, nbytes)
        if data:
            frame.wcs = data.decode("ascii", "replace").rstrip("\x00\n")

    def _handle_cursor(self, client, tid: int, x: int, y: int, z: int) -> None:
        """Read or write the logical image cursor.

        A read answers with the cursor position; a write moves it. IRAF's
        blocking read -- where it waits for the user to click -- is not
        answered here, because an unattended reply of the current position
        is more useful than a socket that never answers: `imexam` gets a
        position rather than hanging.
        """
        if not tid & IIS_READ:
            frame = decode_frame(z) if z else self._current_frame
            if self._cursor_write_callback is not None:
                self._cursor_write_callback(float(x), float(y), frame)
            return

        position = (float(x), float(y), self._current_frame)
        if self._cursor_callback is not None:
            try:
                answer = self._cursor_callback(*position)
                if answer is not None:
                    position = answer
            except Exception:
                self._logger.exception("The IIS cursor callback raised")

        client.sendall(self.cursor_reply(*position))

    @staticmethod
    def cursor_reply(x: float, y: float, frame: int, key: str = "") -> bytes:
        """The cursor value as IRAF reads it.

        `"%10.3f %10.3f %d %s %s\n"` in a fixed 160-byte buffer
        (`xim_retCursorVal`, `iis.c:1072`). The fixed size matters: IRAF
        reads that many bytes, so a shorter reply leaves it waiting.
        """
        text = f"{x:10.3f} {y:10.3f} {int(frame)} {key} \n"
        return text.encode("ascii", "replace").ljust(CURSOR_REPLY_SIZE, b"\x00")

    def _handle_lut(self, client, subunit: int, nbytes: int) -> None:
        """A command-mode LUT write, which is how IRAF selects a frame."""
        if nbytes <= 0:
            return
        data = self._recv_all(client, nbytes)
        if not data or not subunit & COMMAND:
            return
        # The first short is the frame, one bit per frame as everywhere
        # else in this protocol.
        try:
            (word,) = struct.unpack(">h", data[:2])
        except struct.error:
            return
        self._current_frame = decode_frame(word)
        if self._frame_callback is not None:
            self._frame_callback(self._current_frame)

    def _handle_feedback(self, z: int) -> None:
        """A frame clear, which is all the feedback subunit is used for."""
        number = decode_frame(z)
        frame = self._frames.get(number)
        if frame is not None:
            frame.data = np.zeros((frame.height, frame.width), dtype=np.uint8)
            frame.wcs = ""
        self._current_frame = number
        if self._image_callback is not None and frame is not None:
            self._image_callback(number, frame.data)

    def _handle_setup(self, client: socket.socket, subunit: int) -> None:
        """Handle setup command.

        Args:
            client: Client socket.
            subunit: Subunit code.
        """
        # Send frame buffer configuration
        self._logger.debug("IIS setup command received")

    def get_frame(self, frame: int) -> IISFrame | None:
        """Get a frame buffer.

        Args:
            frame: Frame number (1-indexed).

        Returns:
            IISFrame object or None.
        """
        return self._frames.get(frame)

    def set_current_frame(self, frame: int) -> None:
        """Set the current frame.

        Args:
            frame: Frame number (1-indexed).
        """
        if 1 <= frame <= self.MAX_FRAMES:
            self._current_frame = frame

    def get_current_frame(self) -> int:
        """Get the current frame number.

        Returns:
            Current frame number.
        """
        return self._current_frame

    def is_running(self) -> bool:
        """Check if the server is running.

        Returns:
            True if running, False otherwise.
        """
        return self.running
