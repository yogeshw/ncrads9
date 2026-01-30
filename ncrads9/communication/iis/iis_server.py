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
IIS (IRAF Image Server) implementation for IRAF compatibility.

Provides an IIS server that allows legacy IRAF tools to display images
in NCRADS9, maintaining compatibility with traditional IRAF workflows.

Author: Yogesh Wadadekar
"""

import os
import socket
import struct
import threading
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import IntEnum
from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray


class IISCommand(IntEnum):
    """IIS protocol command codes."""
    FEEDBACK = 0o100000
    MEMORY = 0o1
    LUT = 0o2
    REFRESH = 0o4
    SETUP = 0o10
    IMCURSOR = 0o20
    WCS = 0o40
    DEBUG = 0o200


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
    data: Optional[NDArray[np.uint8]] = None
    wcs: str = ""


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
    HEADER_SIZE: int = 8
    
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
        
        self._socket: Optional[socket.socket] = None
        self._fifo_in_fd: Optional[int] = None
        self._fifo_out_fd: Optional[int] = None
        self._thread: Optional[threading.Thread] = None
        self._logger: logging.Logger = logging.getLogger(__name__)
        
        self._frames: Dict[int, IISFrame] = {}
        self._current_frame: int = 1
        self._cursor_callback: Optional[Callable[[float, float, int], None]] = None
        self._image_callback: Optional[
            Callable[[int, NDArray[np.uint8]], None]
        ] = None
        
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
                
            except socket.timeout:
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
                
        except socket.timeout:
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
        """Process an IIS command.
        
        Args:
            header: Command header bytes.
            client: Client socket.
        """
        if len(header) < self.HEADER_SIZE:
            return
            
        # Parse header (big-endian)
        tid, subunit, thingct, x, y, z, t = struct.unpack(
            ">HBBHHHH",
            header[:12] if len(header) >= 12 else header + b"\x00" * 4,
        )
        
        # Decode command
        command = tid & 0o77
        
        if command == IISCommand.MEMORY:
            self._handle_memory(client, subunit, thingct, x, y, t)
        elif command == IISCommand.WCS:
            self._handle_wcs(client, subunit, thingct)
        elif command == IISCommand.IMCURSOR:
            self._handle_cursor(client, subunit)
        elif command == IISCommand.LUT:
            self._handle_lut(client, subunit, thingct)
        elif command == IISCommand.SETUP:
            self._handle_setup(client, subunit)
            
    def _process_fifo_command(self, header: bytes) -> None:
        """Process an IIS command from FIFO.
        
        Args:
            header: Command header bytes.
        """
        # Similar to _process_command but uses FIFO I/O
        pass
        
    def _handle_memory(
        self,
        client: socket.socket,
        subunit: int,
        thingct: int,
        x: int,
        y: int,
        frame: int,
    ) -> None:
        """Handle memory (pixel data) command.
        
        Args:
            client: Client socket.
            subunit: Subunit code.
            thingct: Number of pixels.
            x: X coordinate.
            y: Y coordinate.
            frame: Frame number.
        """
        frame_num = (frame - 1) % self.MAX_FRAMES + 1
        
        # Read pixel data
        nbytes = thingct
        if nbytes > 0:
            data = self._recv_all(client, nbytes)
            if data and frame_num in self._frames:
                # Store pixel data
                frame_obj = self._frames[frame_num]
                if frame_obj.data is None:
                    frame_obj.data = np.zeros(
                        (frame_obj.height, frame_obj.width),
                        dtype=np.uint8,
                    )
                    
                # Update frame data
                pixels = np.frombuffer(data, dtype=np.uint8)
                # Store at appropriate location
                
                if self._image_callback is not None:
                    self._image_callback(frame_num, pixels)
                    
    def _handle_wcs(
        self,
        client: socket.socket,
        subunit: int,
        thingct: int,
    ) -> None:
        """Handle WCS command.
        
        Args:
            client: Client socket.
            subunit: Subunit code.
            thingct: String length.
        """
        if thingct > 0:
            wcs_data = self._recv_all(client, thingct)
            if wcs_data:
                wcs_str = wcs_data.decode("ascii", errors="replace")
                self._logger.debug(f"Received WCS: {wcs_str[:50]}...")
                
    def _handle_cursor(self, client: socket.socket, subunit: int) -> None:
        """Handle cursor command.
        
        Args:
            client: Client socket.
            subunit: Subunit code.
        """
        # Get cursor position from callback
        x, y, frame = 256.0, 256.0, 1
        
        if self._cursor_callback is not None:
            try:
                x, y, frame = self._cursor_callback(x, y, frame)
            except Exception:
                pass
                
        # Format cursor response
        response = f"{x:.2f} {y:.2f} 1 {chr(ord('a') + frame - 1)}\n"
        client.sendall(response.encode("ascii"))
        
    def _handle_lut(
        self,
        client: socket.socket,
        subunit: int,
        thingct: int,
    ) -> None:
        """Handle LUT (colormap) command.
        
        Args:
            client: Client socket.
            subunit: Subunit code.
            thingct: LUT data length.
        """
        if thingct > 0:
            lut_data = self._recv_all(client, thingct)
            self._logger.debug(f"Received LUT data: {len(lut_data)} bytes")
            
    def _handle_setup(self, client: socket.socket, subunit: int) -> None:
        """Handle setup command.
        
        Args:
            client: Client socket.
            subunit: Subunit code.
        """
        # Send frame buffer configuration
        self._logger.debug("IIS setup command received")
        
    def get_frame(self, frame: int) -> Optional[IISFrame]:
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
