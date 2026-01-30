# NCRADS9 - SAMP Message Handlers
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
SAMP message handlers for NCRADS9.

Provides handlers for standard SAMP message types used in Virtual Observatory
interoperability.

Author: Yogesh Wadadekar
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse


class SAMPHandlers:
    """Handler class for SAMP messages.
    
    This class provides handlers for standard SAMP message types,
    enabling NCRADS9 to respond to messages from other VO applications.
    
    Attributes:
        viewer: Reference to the main viewer application.
    """
    
    def __init__(self, viewer: Optional[Any] = None) -> None:
        """Initialize SAMP handlers.
        
        Args:
            viewer: Optional reference to the main viewer application.
        """
        self.viewer: Optional[Any] = viewer
        self._logger: logging.Logger = logging.getLogger(__name__)
        self._handlers: Dict[str, Callable[..., Optional[Dict[str, Any]]]] = {
            "image.load.fits": self._handle_image_load_fits,
            "table.load.fits": self._handle_table_load_fits,
            "table.load.votable": self._handle_table_load_votable,
            "coord.pointAt.sky": self._handle_coord_point_at_sky,
            "table.highlight.row": self._handle_table_highlight_row,
            "table.select.rowList": self._handle_table_select_row_list,
            "samp.hub.event.shutdown": self._handle_hub_shutdown,
            "samp.hub.event.register": self._handle_hub_register,
            "samp.hub.event.unregister": self._handle_hub_unregister,
        }
        self._event_callbacks: Dict[str, List[Callable[..., None]]] = {}
        
    def set_viewer(self, viewer: Any) -> None:
        """Set the viewer reference.
        
        Args:
            viewer: Reference to the main viewer application.
        """
        self.viewer = viewer
        
    def handle_message(
        self,
        mtype: str,
        sender_id: str,
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle a SAMP message.
        
        Args:
            mtype: The message type.
            sender_id: The sender's public ID.
            params: Message parameters.
            
        Returns:
            Optional response dictionary.
        """
        handler = self._handlers.get(mtype)
        
        if handler is None:
            self._logger.warning(f"No handler for mtype: {mtype}")
            return None
            
        try:
            self._logger.debug(f"Handling {mtype} from {sender_id}")
            return handler(sender_id, params)
        except Exception as e:
            self._logger.error(f"Error handling {mtype}: {e}")
            return {"samp.status": "samp.error", "samp.error.message": str(e)}
            
    def register_handler(
        self,
        mtype: str,
        handler: Callable[..., Optional[Dict[str, Any]]],
    ) -> None:
        """Register a custom message handler.
        
        Args:
            mtype: The message type.
            handler: The handler function.
        """
        self._handlers[mtype] = handler
        
    def register_event_callback(
        self,
        event: str,
        callback: Callable[..., None],
    ) -> None:
        """Register a callback for internal events.
        
        Args:
            event: The event name.
            callback: The callback function.
        """
        if event not in self._event_callbacks:
            self._event_callbacks[event] = []
        self._event_callbacks[event].append(callback)
        
    def _fire_event(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Fire an internal event.
        
        Args:
            event: The event name.
            *args: Positional arguments for callbacks.
            **kwargs: Keyword arguments for callbacks.
        """
        callbacks = self._event_callbacks.get(event, [])
        for callback in callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self._logger.error(f"Error in event callback for {event}: {e}")
                
    def _handle_image_load_fits(
        self,
        sender_id: str,
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle image.load.fits message.
        
        Args:
            sender_id: The sender's public ID.
            params: Message parameters including 'url'.
            
        Returns:
            Response dictionary.
        """
        url = params.get("url")
        name = params.get("name")
        
        if not url:
            return {
                "samp.status": "samp.error",
                "samp.error.message": "No URL provided",
            }
            
        self._logger.info(f"Loading FITS image from {url}")
        
        # Extract file path from URL
        file_path = self._url_to_path(url)
        
        self._fire_event("image_load", file_path, name)
        
        return {"samp.status": "samp.ok"}
        
    def _handle_table_load_fits(
        self,
        sender_id: str,
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle table.load.fits message.
        
        Args:
            sender_id: The sender's public ID.
            params: Message parameters including 'url'.
            
        Returns:
            Response dictionary.
        """
        url = params.get("url")
        table_id = params.get("table-id")
        
        if not url:
            return {
                "samp.status": "samp.error",
                "samp.error.message": "No URL provided",
            }
            
        self._logger.info(f"Loading FITS table from {url}")
        
        file_path = self._url_to_path(url)
        self._fire_event("table_load", file_path, table_id, "fits")
        
        return {"samp.status": "samp.ok"}
        
    def _handle_table_load_votable(
        self,
        sender_id: str,
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle table.load.votable message.
        
        Args:
            sender_id: The sender's public ID.
            params: Message parameters including 'url'.
            
        Returns:
            Response dictionary.
        """
        url = params.get("url")
        table_id = params.get("table-id")
        
        if not url:
            return {
                "samp.status": "samp.error",
                "samp.error.message": "No URL provided",
            }
            
        self._logger.info(f"Loading VOTable from {url}")
        
        file_path = self._url_to_path(url)
        self._fire_event("table_load", file_path, table_id, "votable")
        
        return {"samp.status": "samp.ok"}
        
    def _handle_coord_point_at_sky(
        self,
        sender_id: str,
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle coord.pointAt.sky message.
        
        Args:
            sender_id: The sender's public ID.
            params: Message parameters including 'ra' and 'dec'.
            
        Returns:
            Response dictionary.
        """
        try:
            ra = float(params.get("ra", 0))
            dec = float(params.get("dec", 0))
        except (ValueError, TypeError):
            return {
                "samp.status": "samp.error",
                "samp.error.message": "Invalid coordinates",
            }
            
        self._logger.info(f"Pointing at RA={ra}, Dec={dec}")
        self._fire_event("coord_point", ra, dec)
        
        return {"samp.status": "samp.ok"}
        
    def _handle_table_highlight_row(
        self,
        sender_id: str,
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle table.highlight.row message.
        
        Args:
            sender_id: The sender's public ID.
            params: Message parameters including 'table-id' and 'row'.
            
        Returns:
            Response dictionary.
        """
        table_id = params.get("table-id")
        url = params.get("url")
        row = params.get("row")
        
        try:
            row_index = int(row) if row is not None else None
        except (ValueError, TypeError):
            row_index = None
            
        self._logger.debug(f"Highlight row {row_index} in table {table_id}")
        self._fire_event("table_highlight_row", table_id, url, row_index)
        
        return {"samp.status": "samp.ok"}
        
    def _handle_table_select_row_list(
        self,
        sender_id: str,
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle table.select.rowList message.
        
        Args:
            sender_id: The sender's public ID.
            params: Message parameters including 'table-id' and 'row-list'.
            
        Returns:
            Response dictionary.
        """
        table_id = params.get("table-id")
        url = params.get("url")
        row_list = params.get("row-list", [])
        
        # Convert row list to integers
        try:
            rows = [int(r) for r in row_list]
        except (ValueError, TypeError):
            rows = []
            
        self._logger.debug(f"Select {len(rows)} rows in table {table_id}")
        self._fire_event("table_select_rows", table_id, url, rows)
        
        return {"samp.status": "samp.ok"}
        
    def _handle_hub_shutdown(
        self,
        sender_id: str,
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle samp.hub.event.shutdown message.
        
        Args:
            sender_id: The sender's public ID.
            params: Message parameters.
            
        Returns:
            None (no response expected).
        """
        self._logger.info("SAMP hub is shutting down")
        self._fire_event("hub_shutdown")
        return None
        
    def _handle_hub_register(
        self,
        sender_id: str,
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle samp.hub.event.register message.
        
        Args:
            sender_id: The sender's public ID.
            params: Message parameters including 'id'.
            
        Returns:
            None (no response expected).
        """
        client_id = params.get("id")
        self._logger.debug(f"Client registered: {client_id}")
        self._fire_event("client_register", client_id)
        return None
        
    def _handle_hub_unregister(
        self,
        sender_id: str,
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle samp.hub.event.unregister message.
        
        Args:
            sender_id: The sender's public ID.
            params: Message parameters including 'id'.
            
        Returns:
            None (no response expected).
        """
        client_id = params.get("id")
        self._logger.debug(f"Client unregistered: {client_id}")
        self._fire_event("client_unregister", client_id)
        return None
        
    def _url_to_path(self, url: str) -> str:
        """Convert a file URL to a local path.
        
        Args:
            url: The URL to convert.
            
        Returns:
            Local file path.
        """
        parsed = urlparse(url)
        
        if parsed.scheme == "file":
            return parsed.path
        elif parsed.scheme in ("http", "https", "ftp"):
            return url
        else:
            return url
            
    def get_supported_mtypes(self) -> List[str]:
        """Get list of supported message types.
        
        Returns:
            List of supported mtype strings.
        """
        return list(self._handlers.keys())
