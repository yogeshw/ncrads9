# NCRADS9 - SAMP Client Implementation
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
SAMP client implementation using astropy.samp.

Provides a SAMP client for Virtual Observatory interoperability, enabling
communication with other VO tools like TOPCAT, Aladin, and DS9.

Author: Yogesh Wadadekar
"""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

try:
    from astropy.samp import SAMPIntegratedClient
    from astropy.samp.errors import SAMPHubError
    ASTROPY_SAMP_AVAILABLE = True
except ImportError:
    ASTROPY_SAMP_AVAILABLE = False

from .samp_handlers import SAMPHandlers


class SAMPClient:
    """SAMP client for Virtual Observatory interoperability.
    
    This class provides a SAMP client implementation using astropy.samp,
    enabling NCRADS9 to communicate with other VO applications.
    
    Attributes:
        name: The SAMP client name.
        description: Client description.
        connected: Whether the client is connected to a hub.
    """
    
    CLIENT_NAME: str = "NCRADS9"
    CLIENT_DESCRIPTION: str = "NCRADS9 FITS Image Viewer"
    
    def __init__(
        self,
        name: str = CLIENT_NAME,
        description: str = CLIENT_DESCRIPTION,
    ) -> None:
        """Initialize the SAMP client.
        
        Args:
            name: The SAMP client name.
            description: Client description.
        """
        self.name: str = name
        self.description: str = description
        self.connected: bool = False
        
        self._client: Optional[Any] = None
        self._handlers: SAMPHandlers = SAMPHandlers()
        self._logger: logging.Logger = logging.getLogger(__name__)
        self._lock: threading.Lock = threading.Lock()
        self._callbacks: Dict[str, List[Callable[..., None]]] = {}
        
        if not ASTROPY_SAMP_AVAILABLE:
            self._logger.warning(
                "astropy.samp not available. SAMP functionality disabled."
            )
            
    def connect(self) -> bool:
        """Connect to a SAMP hub.
        
        Returns:
            True if connection successful, False otherwise.
        """
        if not ASTROPY_SAMP_AVAILABLE:
            self._logger.error("astropy.samp not available")
            return False
            
        with self._lock:
            if self.connected:
                self._logger.warning("Already connected to SAMP hub")
                return True
                
            try:
                self._client = SAMPIntegratedClient(
                    name=self.name,
                    description=self.description,
                )
                self._client.connect()
                self.connected = True
                
                self._register_mtypes()
                self._logger.info("Connected to SAMP hub")
                return True
                
            except Exception as e:
                self._logger.error(f"Failed to connect to SAMP hub: {e}")
                self._client = None
                return False
                
    def disconnect(self) -> None:
        """Disconnect from the SAMP hub."""
        with self._lock:
            if self._client is not None and self.connected:
                try:
                    self._client.disconnect()
                    self._logger.info("Disconnected from SAMP hub")
                except Exception as e:
                    self._logger.error(f"Error disconnecting from hub: {e}")
                finally:
                    self._client = None
                    self.connected = False
                    
    def is_connected(self) -> bool:
        """Check if connected to a SAMP hub.
        
        Returns:
            True if connected, False otherwise.
        """
        return self.connected and self._client is not None
        
    def _register_mtypes(self) -> None:
        """Register SAMP message types (mtypes) with the hub."""
        if self._client is None:
            return
            
        mtypes = [
            "image.load.fits",
            "table.load.fits",
            "table.load.votable",
            "coord.pointAt.sky",
            "table.highlight.row",
            "table.select.rowList",
            "samp.hub.event.shutdown",
            "samp.hub.event.register",
            "samp.hub.event.unregister",
        ]
        
        for mtype in mtypes:
            try:
                self._client.bind_receive_notification(
                    mtype,
                    self._handle_notification,
                )
                self._client.bind_receive_call(
                    mtype,
                    self._handle_call,
                )
            except Exception as e:
                self._logger.error(f"Failed to register mtype {mtype}: {e}")
                
    def _handle_notification(
        self,
        private_key: str,
        sender_id: str,
        mtype: str,
        params: Dict[str, Any],
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Handle incoming SAMP notification.
        
        Args:
            private_key: The client's private key.
            sender_id: The sender's public ID.
            mtype: The message type.
            params: Message parameters.
            extra: Extra data (unused).
        """
        self._logger.debug(f"Received notification: {mtype} from {sender_id}")
        self._handlers.handle_message(mtype, sender_id, params)
        self._fire_callbacks(mtype, sender_id, params)
        
    def _handle_call(
        self,
        private_key: str,
        sender_id: str,
        msg_id: str,
        mtype: str,
        params: Dict[str, Any],
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Handle incoming SAMP call.
        
        Args:
            private_key: The client's private key.
            sender_id: The sender's public ID.
            msg_id: The message ID.
            mtype: The message type.
            params: Message parameters.
            extra: Extra data (unused).
            
        Returns:
            Response dictionary.
        """
        self._logger.debug(f"Received call: {mtype} from {sender_id}")
        result = self._handlers.handle_message(mtype, sender_id, params)
        self._fire_callbacks(mtype, sender_id, params)
        return result or {}
        
    def _fire_callbacks(
        self,
        mtype: str,
        sender_id: str,
        params: Dict[str, Any],
    ) -> None:
        """Fire registered callbacks for a message type.
        
        Args:
            mtype: The message type.
            sender_id: The sender's public ID.
            params: Message parameters.
        """
        callbacks = self._callbacks.get(mtype, [])
        for callback in callbacks:
            try:
                callback(sender_id, params)
            except Exception as e:
                self._logger.error(f"Error in callback for {mtype}: {e}")
                
    def register_callback(
        self,
        mtype: str,
        callback: Callable[[str, Dict[str, Any]], None],
    ) -> None:
        """Register a callback for a message type.
        
        Args:
            mtype: The message type to listen for.
            callback: The callback function (sender_id, params) -> None.
        """
        if mtype not in self._callbacks:
            self._callbacks[mtype] = []
        self._callbacks[mtype].append(callback)
        
    def unregister_callback(
        self,
        mtype: str,
        callback: Callable[[str, Dict[str, Any]], None],
    ) -> None:
        """Unregister a callback.
        
        Args:
            mtype: The message type.
            callback: The callback function to remove.
        """
        if mtype in self._callbacks:
            try:
                self._callbacks[mtype].remove(callback)
            except ValueError:
                pass
                
    def send_image(
        self,
        url: str,
        recipient: Optional[str] = None,
        name: Optional[str] = None,
    ) -> bool:
        """Send an image to other SAMP clients.
        
        Args:
            url: URL of the FITS image.
            recipient: Optional specific recipient ID.
            name: Optional image name.
            
        Returns:
            True if message sent successfully.
        """
        if not self.is_connected():
            self._logger.error("Not connected to SAMP hub")
            return False
            
        params = {"url": url}
        if name:
            params["name"] = name
            
        return self._send_message("image.load.fits", params, recipient)
        
    def send_table(
        self,
        url: str,
        table_id: Optional[str] = None,
        recipient: Optional[str] = None,
    ) -> bool:
        """Send a table to other SAMP clients.
        
        Args:
            url: URL of the table file.
            table_id: Optional table identifier.
            recipient: Optional specific recipient ID.
            
        Returns:
            True if message sent successfully.
        """
        if not self.is_connected():
            self._logger.error("Not connected to SAMP hub")
            return False
            
        params = {"url": url}
        if table_id:
            params["table-id"] = table_id
            
        return self._send_message("table.load.fits", params, recipient)
        
    def send_coordinates(
        self,
        ra: float,
        dec: float,
        recipient: Optional[str] = None,
    ) -> bool:
        """Send sky coordinates to other SAMP clients.
        
        Args:
            ra: Right ascension in degrees.
            dec: Declination in degrees.
            recipient: Optional specific recipient ID.
            
        Returns:
            True if message sent successfully.
        """
        if not self.is_connected():
            self._logger.error("Not connected to SAMP hub")
            return False
            
        params = {"ra": str(ra), "dec": str(dec)}
        return self._send_message("coord.pointAt.sky", params, recipient)
        
    def _send_message(
        self,
        mtype: str,
        params: Dict[str, Any],
        recipient: Optional[str] = None,
    ) -> bool:
        """Send a SAMP message.
        
        Args:
            mtype: The message type.
            params: Message parameters.
            recipient: Optional specific recipient ID.
            
        Returns:
            True if message sent successfully.
        """
        if self._client is None:
            return False
            
        try:
            message = {"samp.mtype": mtype, "samp.params": params}
            
            if recipient:
                self._client.notify(recipient, message)
            else:
                self._client.notify_all(message)
                
            self._logger.debug(f"Sent message: {mtype}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to send message {mtype}: {e}")
            return False
            
    def get_registered_clients(self) -> List[Dict[str, str]]:
        """Get list of registered SAMP clients.
        
        Returns:
            List of client info dictionaries.
        """
        if not self.is_connected() or self._client is None:
            return []
            
        try:
            clients = []
            client_ids = self._client.get_registered_clients()
            
            for client_id in client_ids:
                metadata = self._client.get_metadata(client_id)
                clients.append({
                    "id": client_id,
                    "name": metadata.get("samp.name", "Unknown"),
                    "description": metadata.get(
                        "samp.description.text", ""
                    ),
                })
                
            return clients
            
        except Exception as e:
            self._logger.error(f"Failed to get registered clients: {e}")
            return []
            
    def set_handlers(self, handlers: SAMPHandlers) -> None:
        """Set the message handlers.
        
        Args:
            handlers: SAMPHandlers instance.
        """
        self._handlers = handlers
