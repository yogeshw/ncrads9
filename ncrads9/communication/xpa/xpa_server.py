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

import socket
import threading
import logging
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
    DEFAULT_PORT: int = 14285
    
    def __init__(
        self,
        name: str = DEFAULT_NAME,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
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
        self._commands: XPACommands = XPACommands()
        self._logger: logging.Logger = logging.getLogger(__name__)
        self._handlers: Dict[str, Callable[..., Any]] = {}
        
    def register_handler(self, command: str, handler: Callable[..., Any]) -> None:
        """Register a command handler.
        
        Args:
            command: The XPA command name.
            handler: The handler function to call for this command.
        """
        self._handlers[command.lower()] = handler
        self._logger.debug(f"Registered handler for command: {command}")
        
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
            
            self.running = True
            self._thread = threading.Thread(target=self._accept_loop, daemon=True)
            self._thread.start()
            
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
            data = client_socket.recv(4096)
            
            if data:
                request = self._protocol.parse_request(data)
                response = self._process_request(request)
                response_data = self._protocol.format_response(response)
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
                
    def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process an XPA request.
        
        Args:
            request: The parsed XPA request dictionary.
            
        Returns:
            The response dictionary.
        """
        command = request.get("command", "").lower()
        params = request.get("params", {})
        
        if command in self._handlers:
            try:
                result = self._handlers[command](**params)
                return {"status": "ok", "result": result}
            except Exception as e:
                self._logger.error(f"Error executing command {command}: {e}")
                return {"status": "error", "message": str(e)}
        else:
            return self._commands.handle(command, params)
            
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
