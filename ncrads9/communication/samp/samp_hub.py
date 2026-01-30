# NCRADS9 - SAMP Hub Implementation
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
Optional SAMP hub implementation for NCRADS9.

Provides an embedded SAMP hub that can be started when no external hub
is available, enabling SAMP interoperability without requiring a separate
hub application.

Author: Yogesh Wadadekar
"""

import logging
import threading
from typing import Any, Dict, List, Optional

try:
    from astropy.samp import SAMPHubServer
    ASTROPY_SAMP_AVAILABLE = True
except ImportError:
    ASTROPY_SAMP_AVAILABLE = False


class SAMPHub:
    """Optional embedded SAMP hub for NCRADS9.
    
    This class provides an embedded SAMP hub implementation using astropy.samp,
    which can be started when no external hub is available.
    
    Attributes:
        running: Whether the hub is currently running.
        port: The port the hub is listening on.
    """
    
    DEFAULT_PORT: int = 21012
    
    def __init__(self, port: int = DEFAULT_PORT) -> None:
        """Initialize the SAMP hub.
        
        Args:
            port: The port to listen on.
        """
        self.port: int = port
        self.running: bool = False
        
        self._hub: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._logger: logging.Logger = logging.getLogger(__name__)
        
        if not ASTROPY_SAMP_AVAILABLE:
            self._logger.warning(
                "astropy.samp not available. SAMP hub functionality disabled."
            )
            
    def start(self, web_profile: bool = True) -> bool:
        """Start the SAMP hub.
        
        Args:
            web_profile: Whether to enable the web profile (default: True).
            
        Returns:
            True if the hub started successfully, False otherwise.
        """
        if not ASTROPY_SAMP_AVAILABLE:
            self._logger.error("astropy.samp not available")
            return False
            
        if self.running:
            self._logger.warning("SAMP hub is already running")
            return True
            
        try:
            self._hub = SAMPHubServer(
                web_profile=web_profile,
                web_port=self.port,
            )
            
            self._thread = threading.Thread(
                target=self._run_hub,
                daemon=True,
            )
            self._thread.start()
            
            self.running = True
            self._logger.info(f"SAMP hub started on port {self.port}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to start SAMP hub: {e}")
            self._cleanup()
            return False
            
    def _run_hub(self) -> None:
        """Run the hub in a background thread."""
        if self._hub is not None:
            try:
                self._hub.start()
            except Exception as e:
                self._logger.error(f"SAMP hub error: {e}")
                self.running = False
                
    def stop(self) -> None:
        """Stop the SAMP hub."""
        if not self.running:
            return
            
        self.running = False
        
        if self._hub is not None:
            try:
                self._hub.stop()
            except Exception as e:
                self._logger.error(f"Error stopping SAMP hub: {e}")
                
        self._cleanup()
        self._logger.info("SAMP hub stopped")
        
    def _cleanup(self) -> None:
        """Clean up hub resources."""
        self._hub = None
        self._thread = None
        self.running = False
        
    def is_running(self) -> bool:
        """Check if the hub is running.
        
        Returns:
            True if the hub is running, False otherwise.
        """
        return self.running
        
    def get_registered_clients(self) -> List[Dict[str, str]]:
        """Get list of registered clients.
        
        Returns:
            List of client information dictionaries.
        """
        if not self.is_running() or self._hub is None:
            return []
            
        try:
            # Access hub internals to get client list
            clients = []
            # Implementation would depend on astropy.samp internals
            return clients
        except Exception as e:
            self._logger.error(f"Error getting registered clients: {e}")
            return []
            
    @staticmethod
    def is_hub_running() -> bool:
        """Check if any SAMP hub is running.
        
        Returns:
            True if a hub is detected, False otherwise.
        """
        if not ASTROPY_SAMP_AVAILABLE:
            return False
            
        try:
            from astropy.samp import SAMPHubProxy
            hub = SAMPHubProxy()
            hub.connect()
            hub.disconnect()
            return True
        except Exception:
            return False
            
    @staticmethod
    def find_hub() -> Optional[str]:
        """Find an existing SAMP hub.
        
        Returns:
            Hub URL if found, None otherwise.
        """
        if not ASTROPY_SAMP_AVAILABLE:
            return None
            
        try:
            from astropy.samp import SAMPHubProxy
            hub = SAMPHubProxy()
            hub.connect()
            hub_url = hub.get_mtype()  # This might need adjustment
            hub.disconnect()
            return hub_url
        except Exception:
            return None
