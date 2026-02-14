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

import logging
import socket
import threading
import os
import getpass
import subprocess
import time
from typing import Optional, Callable, Dict, Any, Tuple

from .xpa_protocol import XPAProtocol
from .xpa_commands import XPACommands


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
    
    def __init__(
        self,
        name: str = DEFAULT_NAME,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        viewer: Optional[Any] = None,
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
        
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._protocol: XPAProtocol = XPAProtocol()
        self._commands: XPACommands = XPACommands(viewer)
        self._logger: logging.Logger = logging.getLogger(__name__)
        self._handlers: Dict[str, Callable[..., Any]] = {}
        self._pending_requests: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._pending_lock = threading.Lock()
        self._next_pending_id = 1
        self._xpans_socket: Optional[socket.socket] = None
        self._xpans_stream = None
        self._xpans_process: Optional[subprocess.Popen] = None
        
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
                
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True,
                )
                client_thread.start()
                
            except socket.timeout:
                continue
            except OSError:
                if self.running:
                    self._logger.error("Error accepting connection")
                break
                
    def _handle_client(
        self,
        client_socket: socket.socket,
        address: Tuple[str, int],
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
                
        except socket.timeout:
            self._logger.warning(f"Client {address} timed out")
        except OSError as e:
            self._logger.error(f"Error handling client {address}: {e}")
        finally:
            try:
                client_socket.close()
            except OSError:
                pass

    def _recv_request(self, client_socket: socket.socket) -> bytes:
        """Receive one request payload."""
        chunks = []
        while True:
            try:
                chunk = client_socket.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            chunks.append(chunk)
            if b"\n" in chunk:
                client_socket.settimeout(0.05)
        return b"".join(chunks)
                
    def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
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

    def _process_wire_request(self, request: Dict[str, Any]) -> bytes:
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

    def _start_xpa_transaction(self, request: Dict[str, Any]) -> bytes:
        """Start a two-step XPA transaction for xpaset/xpaget clients."""
        params = request.get("params", {})
        xpa_id = str(params.get("xpa_id", "x0"))
        with self._pending_lock:
            pending_key = f"0x{self._next_pending_id:08x}"
            pending_fd = str(self._next_pending_id)
            self._next_pending_id += 1
            self._pending_requests[(pending_key, pending_fd)] = request
        return (
            f"{xpa_id} XPA$DATA connect {pending_key} {pending_fd} "
            f"(NCRADS9:{self.name} {self.host}:{self.port})\n"
        ).encode("utf-8")

    def _handle_xpadata(self, request: Dict[str, Any]) -> bytes:
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
                return f"{xpa_id} XPA$OK\n".encode("utf-8")
            return f"{result}\n".encode("utf-8")
        message = str(response.get("message", "Unknown error"))
        return f"{xpa_id} XPA$ERROR {message}\n".encode("utf-8")

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
