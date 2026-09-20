# NCRADS9 - XPA Server Implementation
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
XPA Server implementation for DS9 compatibility.

Provides an XPA server that allows external tools to communicate with NCRADS9
using the standard DS9 XPA protocol.

Author: Yogesh Wadadekar
"""

import getpass
import logging
import os
import socket
import subprocess
import threading
import time
from collections.abc import Callable
from typing import Any

from .xpa_commands import XPACommands
from .xpa_protocol import XPAProtocol


class XPAServer:
    """XPA server for DS9-compatible external tool communication.

    This class implements an XPA server that listens for incoming connections
    and handles XPA get/set commands for controlling the image viewer.

    Attributes:
        name: The XPA access point name (default: "ncrads9").
        host: The host address to bind to.
        port: The port number to listen on.
        running: Whether the server is currently running.
    """

    DEFAULT_NAME: str = "ncrads9"
    DEFAULT_HOST: str = "localhost"
    DEFAULT_PORT: int = 0

    #: The most a single request may be. An XPA command is a line, sometimes
    #: with a text payload -- a region list at the largest -- so 16 MiB is far
    #: more than any real one and still bounds what one client can make the
    #: server hold. Without a cap, a client that never sends a newline makes
    #: `_recv_request` accumulate without limit.
    MAX_REQUEST_BYTES: int = 16 * 1024 * 1024

    #: The most clients handled at once. Each connection is a thread, so an
    #: unbounded count is an unbounded thread (and file-descriptor) count --
    #: one client opening thousands of connections could exhaust either.
    #: XPA clients are short-lived and sequential, so this is generous.
    MAX_CONNECTIONS: int = 16

    #: The most half-finished xpaset/xpaget transactions kept at once. The
    #: first stage records the request and the second (`xpadata`) consumes it;
    #: a client that starts transactions and never sends the second stage
    #: would otherwise grow the table without bound. Over the cap, the oldest
    #: abandoned transaction is dropped -- far more than any real client has
    #: in flight, since it completes each before starting the next.
    MAX_PENDING_TRANSACTIONS: int = 256

    def __init__(
        self,
        name: str = DEFAULT_NAME,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        viewer: Any | None = None,
    ) -> None:
        """Initialize the XPA server.

        Args:
            name: The XPA access point name.
            host: The host address to bind to.
            port: The port number to listen on.
        """
        self.name: str = name
        self.host: str = host
        self.port: int = port
        self.running: bool = False

        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._protocol: XPAProtocol = XPAProtocol()
        self._commands: XPACommands = XPACommands(viewer)
        self._logger: logging.Logger = logging.getLogger(__name__)
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._pending_requests: dict[tuple[str, str], dict[str, Any]] = {}
        self._pending_lock = threading.Lock()
        self._next_pending_id = 1
        #: One permit per client that may be handled at once; a connection
        #: over the limit is closed rather than given a thread.
        self._connection_slots = threading.BoundedSemaphore(self.MAX_CONNECTIONS)
        self._xpans_socket: socket.socket | None = None
        self._xpans_stream = None
        self._xpans_process: subprocess.Popen | None = None

    def register_handler(self, command: str, handler: Callable[..., Any]) -> None:
        """Register a command handler.

        Args:
            command: The XPA command name.
            handler: The handler function to call for this command.
        """
        self._handlers[command.lower()] = handler
        self._logger.debug(f"Registered handler for command: {command}")

    def set_viewer(self, viewer: Any) -> None:
        """Set the viewer used by command handlers."""
        self._commands.set_viewer(viewer)

    def unregister_handler(self, command: str) -> None:
        """Unregister a command handler.

        Args:
            command: The XPA command name to unregister.
        """
        command_lower = command.lower()
        if command_lower in self._handlers:
            del self._handlers[command_lower]
            self._logger.debug(f"Unregistered handler for command: {command}")

    def start(self) -> bool:
        """Start the XPA server.

        Returns:
            True if the server started successfully, False otherwise.
        """
        if self.running:
            self._logger.warning("XPA server is already running")
            return False

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((self.host, self.port))
            self._socket.listen(5)
            self._socket.settimeout(1.0)
            self.port = self._socket.getsockname()[1]

            self.running = True
            self._thread = threading.Thread(target=self._accept_loop, daemon=True)
            self._thread.start()
            self._register_with_xpans()

            self._logger.info(f"XPA server started on {self.host}:{self.port}")
            return True

        except OSError as e:
            self._logger.error(f"Failed to start XPA server: {e}")
            self._cleanup()
            return False

    def stop(self) -> None:
        """Stop the XPA server."""
        self.running = False

        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._disconnect_xpans()
        self._cleanup()
        self._logger.info("XPA server stopped")

    def _cleanup(self) -> None:
        """Clean up server resources."""
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    def _accept_loop(self) -> None:
        """Main loop for accepting client connections."""
        while self.running and self._socket is not None:
            try:
                client_socket, address = self._socket.accept()
                self._logger.debug(f"Accepted connection from {address}")

                # Take a slot before giving the connection a thread. If they
                # are all in use, close this one now: a flood of connections
                # then costs nothing rather than a thread each.
                if not self._connection_slots.acquire(blocking=False):
                    self._logger.warning("XPA connection limit reached; dropping %s", address)
                    try:
                        client_socket.close()
                    except OSError:
                        pass
                    continue

                client_thread = threading.Thread(
                    target=self._handle_client_slot,
                    args=(client_socket, address),
                    daemon=True,
                )
                client_thread.start()

            except TimeoutError:
                continue
            except OSError:
                if self.running:
                    self._logger.error("Error accepting connection")
                break

    def _handle_client_slot(
        self,
        client_socket: socket.socket,
        address: tuple[str, int],
    ) -> None:
        """Handle a client, then give the connection slot back.

        The release is in a `finally` so a handler that raises still frees
        the slot -- otherwise a run of errors would leak the whole pool and
        the server would stop accepting anything.
        """
        try:
            self._handle_client(client_socket, address)
        finally:
            self._connection_slots.release()

    def _handle_client(
        self,
        client_socket: socket.socket,
        address: tuple[str, int],
    ) -> None:
        """Handle a client connection.

        Args:
            client_socket: The client socket.
            address: The client address tuple (host, port).
        """
        try:
            client_socket.settimeout(30.0)
            data = self._recv_request(client_socket)

            if data:
                request = self._protocol.parse_request(data)
                response_data = self._process_wire_request(request)
                client_socket.sendall(response_data)

        except TimeoutError:
            self._logger.warning(f"Client {address} timed out")
        except OSError as e:
            self._logger.error(f"Error handling client {address}: {e}")
        finally:
            try:
                client_socket.close()
            except OSError:
                pass

    def _recv_request(self, client_socket: socket.socket) -> bytes:
        """Receive one request payload, up to `MAX_REQUEST_BYTES`.

        A client that never sends a newline would otherwise keep this loop
        accumulating for the whole 30-second socket timeout; the cap stops it
        at a bounded amount. Anything past the cap is refused rather than
        truncated-and-run: a partial command is not a command.
        """
        chunks: list[bytes] = []
        total = 0
        while True:
            try:
                chunk = client_socket.recv(4096)
            except TimeoutError:
                break
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > self.MAX_REQUEST_BYTES:
                self._logger.warning("XPA request exceeded %d bytes; refusing it", self.MAX_REQUEST_BYTES)
                return b""
            if b"\n" in chunk:
                client_socket.settimeout(0.05)
        return b"".join(chunks)

    def _process_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Process an XPA request.

        Args:
            request: The parsed XPA request dictionary.

        Returns:
            The response dictionary.
        """
        command = request.get("command", "").lower()
        params = request.get("params", {})
        msg_type = request.get("msg_type")

        if msg_type == "xpaaccess" or command == "xpaaccess":
            return {"status": "ok", "result": self._protocol.get_access_info(self.name, self.host, self.port)}
        if msg_type == "xpainfo" or command == "xpainfo":
            commands = sorted(self._commands.get_available_commands())
            return {"status": "ok", "result": " ".join(commands)}

        if command in self._handlers:
            try:
                result = self._handlers[command](**params)
                return {"status": "ok", "result": result}
            except Exception as e:
                self._logger.error(f"Error executing command {command}: {e}")
                return {"status": "error", "message": str(e)}
        else:
            return self._commands.handle(command, params)

    def _process_wire_request(self, request: dict[str, Any]) -> bytes:
        """Process a parsed request and return wire-level bytes."""
        command = str(request.get("command", "")).lower()
        params = request.get("params", {})
        msg_type = request.get("msg_type")
        xpa_id = str(params.get("xpa_id", "")).strip()

        if command == "xpadata":
            return self._handle_xpadata(request)

        if msg_type in {"xpaset", "xpaget", "xpainfo"} and xpa_id:
            return self._start_xpa_transaction(request)

        response = self._process_request(request)
        return self._protocol.format_response(response)

    def _start_xpa_transaction(self, request: dict[str, Any]) -> bytes:
        """Start a two-step XPA transaction for xpaset/xpaget clients."""
        params = request.get("params", {})
        xpa_id = str(params.get("xpa_id", "x0"))
        with self._pending_lock:
            pending_key = f"0x{self._next_pending_id:08x}"
            pending_fd = str(self._next_pending_id)
            self._next_pending_id += 1
            self._pending_requests[(pending_key, pending_fd)] = request
            # Drop the oldest abandoned transactions once over the cap. A dict
            # keeps insertion order, so the first key is the oldest.
            while len(self._pending_requests) > self.MAX_PENDING_TRANSACTIONS:
                oldest = next(iter(self._pending_requests))
                self._pending_requests.pop(oldest, None)
        return (
            f"{xpa_id} XPA$DATA connect {pending_key} {pending_fd} "
            f"(NCRADS9:{self.name} {self.host}:{self.port})\n"
        ).encode()

    def _handle_xpadata(self, request: dict[str, Any]) -> bytes:
        """Handle second-stage XPA data channel request."""
        params = request.get("params", {})
        args = params.get("args", []) if isinstance(params.get("args"), list) else []
        if len(args) >= 3 and str(args[0]) == "-f":
            pending_key = str(args[1])
            pending_fd = str(args[2])
        else:
            return b"? XPA$ERROR invalid xpadata request\n"

        with self._pending_lock:
            pending = self._pending_requests.pop((pending_key, pending_fd), None)
        if pending is None:
            return b"? XPA$ERROR no pending request\n"

        xpa_id = str(pending.get("params", {}).get("xpa_id", "x0"))
        response = self._process_request(pending)
        if response.get("status") == "ok":
            result = response.get("result", "")
            msg_type = str(pending.get("msg_type", "xpaset"))
            if msg_type == "xpaset":
                return f"{xpa_id} XPA$OK\n".encode()
            return f"{result}\n".encode()
        message = str(response.get("message", "Unknown error"))
        return f"{xpa_id} XPA$ERROR {message}\n".encode()

    def _register_with_xpans(self) -> None:
        """Register this access point with xpans if available."""
        nsinet = os.environ.get("XPA_NSINET", "$host:14285")
        host_part, port_part = nsinet.split(":", 1) if ":" in nsinet else ("$host", nsinet)
        ns_host = "127.0.0.1" if host_part in {"$host", "localhost"} else host_part
        try:
            ns_port = int(port_part)
        except ValueError:
            ns_port = 14285

        if not self._connect_xpans(ns_host, ns_port):
            self._start_xpans()
            if not self._connect_xpans(ns_host, ns_port):
                self._logger.warning("Unable to register XPA access point with xpans")
                return

        user = getpass.getuser()
        register_host = "127.0.0.1" if self.host in {"localhost", "127.0.0.1"} else self.host
        registration = f"add {register_host}:{self.port} NCRADS9:{self.name} gs {user}\n"
        assert self._xpans_stream is not None
        self._xpans_stream.write(registration.encode("utf-8"))
        self._xpans_stream.flush()
        response = self._xpans_stream.readline().decode("utf-8", errors="ignore").strip()
        if not response.startswith("XPA$OK") and "XPA$EXISTS" not in response:
            self._logger.warning("xpans registration failed: %s", response)

    def _connect_xpans(self, host: str, port: int) -> bool:
        """Connect and handshake with xpans."""
        try:
            self._xpans_socket = socket.create_connection((host, port), timeout=1.5)
            self._xpans_stream = self._xpans_socket.makefile("rwb", buffering=0)
            self._xpans_stream.write(b"version 2.1.20\n")
            self._xpans_stream.flush()
            version_reply = self._xpans_stream.readline().decode("utf-8", errors="ignore")
            return version_reply.startswith("XPA$VERSION")
        except Exception:
            self._disconnect_xpans()
            return False

    def _start_xpans(self) -> None:
        """Start xpans name server if available."""
        try:
            self._xpans_process = subprocess.Popen(
                ["xpans", "-e"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.3)
        except Exception:
            self._xpans_process = None

    def _disconnect_xpans(self) -> None:
        """Close xpans registration connection."""
        if self._xpans_stream is not None:
            try:
                self._xpans_stream.close()
            except Exception:
                pass
            self._xpans_stream = None
        if self._xpans_socket is not None:
            try:
                self._xpans_socket.close()
            except Exception:
                pass
            self._xpans_socket = None

    @property
    def address(self) -> str:
        """Get the server address string.

        Returns:
            The server address in "host:port" format.
        """
        return f"{self.host}:{self.port}"

    def is_running(self) -> bool:
        """Check if the server is running.

        Returns:
            True if the server is running, False otherwise.
        """
        return self.running
