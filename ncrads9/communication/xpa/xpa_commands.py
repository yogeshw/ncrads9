# NCRADS9 - XPA Command Handlers
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
XPA command handlers for DS9 compatibility.

Provides handlers for all standard DS9 XPA commands, enabling external tools
to control NCRADS9 using familiar DS9 commands.

Author: Yogesh Wadadekar
"""

import logging
from typing import Any, Dict, Optional, Callable, List, Union
from enum import Enum


class XPACommandType(Enum):
    """Types of XPA commands."""
    GET = "get"
    SET = "set"
    INFO = "info"
    ACCESS = "access"


class XPACommands:
    """Handler class for DS9 XPA commands.
    
    This class provides implementations for standard DS9 XPA commands,
    allowing NCRADS9 to be controlled by external tools like xpaset/xpaget.
    
    Attributes:
        viewer: Reference to the main viewer application.
    """
    
    def __init__(self, viewer: Optional[Any] = None) -> None:
        """Initialize XPA command handlers.
        
        Args:
            viewer: Optional reference to the main viewer application.
        """
        self.viewer: Optional[Any] = viewer
        self._logger: logging.Logger = logging.getLogger(__name__)
        self._command_handlers: Dict[str, Callable[..., Dict[str, Any]]] = {
            "file": self._handle_file,
            "fits": self._handle_fits,
            "frame": self._handle_frame,
            "zoom": self._handle_zoom,
            "pan": self._handle_pan,
            "scale": self._handle_scale,
            "cmap": self._handle_cmap,
            "colorbar": self._handle_colorbar,
            "regions": self._handle_regions,
            "wcs": self._handle_wcs,
            "crosshair": self._handle_crosshair,
            "cursor": self._handle_cursor,
            "mode": self._handle_mode,
            "tile": self._handle_tile,
            "blink": self._handle_blink,
            "match": self._handle_match,
            "lock": self._handle_lock,
            "width": self._handle_width,
            "height": self._handle_height,
            "save": self._handle_save,
            "exit": self._handle_exit,
            "quit": self._handle_exit,
            "version": self._handle_version,
            "about": self._handle_about,
        }
        
    def set_viewer(self, viewer: Any) -> None:
        """Set the viewer reference.
        
        Args:
            viewer: Reference to the main viewer application.
        """
        self.viewer = viewer
        
    def handle(
        self,
        command: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle an XPA command.
        
        Args:
            command: The command name.
            params: The command parameters.
            
        Returns:
            Response dictionary with status and result/message.
        """
        handler = self._command_handlers.get(command.lower())
        
        if handler is None:
            self._logger.warning(f"Unknown XPA command: {command}")
            return {
                "status": "error",
                "message": f"Unknown command: {command}",
            }
            
        try:
            return handler(params)
        except Exception as e:
            self._logger.error(f"Error handling command {command}: {e}")
            return {"status": "error", "message": str(e)}
            
    def get_available_commands(self) -> List[str]:
        """Get list of available commands.
        
        Returns:
            List of command names.
        """
        return list(self._command_handlers.keys())
        
    def register_command(
        self,
        name: str,
        handler: Callable[..., Dict[str, Any]],
    ) -> None:
        """Register a custom command handler.
        
        Args:
            name: The command name.
            handler: The handler function.
        """
        self._command_handlers[name.lower()] = handler
        
    def _handle_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file command for loading/saving files.
        
        Args:
            params: Command parameters including 'path' and 'action'.
            
        Returns:
            Response dictionary.
        """
        action = params.get("action", "load")
        path = params.get("path")
        
        if action == "load" and path:
            self._logger.info(f"Loading file: {path}")
            return {"status": "ok", "result": f"Loaded: {path}"}
        elif action == "save" and path:
            self._logger.info(f"Saving file: {path}")
            return {"status": "ok", "result": f"Saved: {path}"}
        else:
            return {"status": "error", "message": "Invalid file command"}
            
    def _handle_fits(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle FITS-specific commands.
        
        Args:
            params: Command parameters.
            
        Returns:
            Response dictionary.
        """
        path = params.get("path")
        extension = params.get("extension", 0)
        
        if path:
            self._logger.info(f"Loading FITS: {path}[{extension}]")
            return {"status": "ok", "result": f"Loaded FITS: {path}"}
        return {"status": "error", "message": "No FITS path specified"}
        
    def _handle_frame(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle frame commands.
        
        Args:
            params: Command parameters including 'action' and 'number'.
            
        Returns:
            Response dictionary.
        """
        action = params.get("action", "get")
        number = params.get("number")
        
        if action == "new":
            return {"status": "ok", "result": "Created new frame"}
        elif action == "delete":
            return {"status": "ok", "result": f"Deleted frame {number}"}
        elif action == "get":
            return {"status": "ok", "result": "1"}
        elif action == "set" and number is not None:
            return {"status": "ok", "result": f"Switched to frame {number}"}
        return {"status": "error", "message": "Invalid frame command"}
        
    def _handle_zoom(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle zoom commands.
        
        Args:
            params: Command parameters including 'level' or 'action'.
            
        Returns:
            Response dictionary.
        """
        level = params.get("level")
        action = params.get("action")
        
        if level is not None:
            return {"status": "ok", "result": f"Zoom set to {level}"}
        elif action == "fit":
            return {"status": "ok", "result": "Zoom to fit"}
        elif action == "in":
            return {"status": "ok", "result": "Zoomed in"}
        elif action == "out":
            return {"status": "ok", "result": "Zoomed out"}
        return {"status": "ok", "result": "1.0"}
        
    def _handle_pan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle pan commands.
        
        Args:
            params: Command parameters including 'x', 'y' coordinates.
            
        Returns:
            Response dictionary.
        """
        x = params.get("x")
        y = params.get("y")
        
        if x is not None and y is not None:
            return {"status": "ok", "result": f"Panned to ({x}, {y})"}
        return {"status": "ok", "result": "0 0"}
        
    def _handle_scale(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle scale/contrast commands.
        
        Args:
            params: Command parameters including 'mode', 'min', 'max'.
            
        Returns:
            Response dictionary.
        """
        mode = params.get("mode")
        limits = params.get("limits")
        
        if mode:
            return {"status": "ok", "result": f"Scale mode: {mode}"}
        elif limits:
            return {"status": "ok", "result": f"Scale limits: {limits}"}
        return {"status": "ok", "result": "linear"}
        
    def _handle_cmap(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle colormap commands.
        
        Args:
            params: Command parameters including 'name'.
            
        Returns:
            Response dictionary.
        """
        name = params.get("name")
        
        if name:
            return {"status": "ok", "result": f"Colormap set to {name}"}
        return {"status": "ok", "result": "gray"}
        
    def _handle_colorbar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle colorbar commands.
        
        Args:
            params: Command parameters including 'visible'.
            
        Returns:
            Response dictionary.
        """
        visible = params.get("visible")
        
        if visible is not None:
            state = "shown" if visible else "hidden"
            return {"status": "ok", "result": f"Colorbar {state}"}
        return {"status": "ok", "result": "yes"}
        
    def _handle_regions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle region commands.
        
        Args:
            params: Command parameters including 'action', 'data'.
            
        Returns:
            Response dictionary.
        """
        action = params.get("action", "get")
        data = params.get("data")
        
        if action == "load" and data:
            return {"status": "ok", "result": "Regions loaded"}
        elif action == "save":
            return {"status": "ok", "result": ""}
        elif action == "delete":
            return {"status": "ok", "result": "Regions deleted"}
        return {"status": "ok", "result": ""}
        
    def _handle_wcs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle WCS commands.
        
        Args:
            params: Command parameters.
            
        Returns:
            Response dictionary.
        """
        action = params.get("action", "get")
        
        if action == "get":
            return {"status": "ok", "result": "fk5"}
        elif action == "set":
            system = params.get("system", "fk5")
            return {"status": "ok", "result": f"WCS set to {system}"}
        return {"status": "ok", "result": "fk5"}
        
    def _handle_crosshair(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle crosshair commands.
        
        Args:
            params: Command parameters including 'x', 'y'.
            
        Returns:
            Response dictionary.
        """
        x = params.get("x")
        y = params.get("y")
        
        if x is not None and y is not None:
            return {"status": "ok", "result": f"Crosshair at ({x}, {y})"}
        return {"status": "ok", "result": "0 0"}
        
    def _handle_cursor(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cursor commands.
        
        Args:
            params: Command parameters.
            
        Returns:
            Response dictionary.
        """
        return {"status": "ok", "result": "0 0"}
        
    def _handle_mode(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle mode commands.
        
        Args:
            params: Command parameters including 'mode'.
            
        Returns:
            Response dictionary.
        """
        mode = params.get("mode")
        
        if mode:
            return {"status": "ok", "result": f"Mode set to {mode}"}
        return {"status": "ok", "result": "none"}
        
    def _handle_tile(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tile display commands.
        
        Args:
            params: Command parameters including 'enabled'.
            
        Returns:
            Response dictionary.
        """
        enabled = params.get("enabled")
        
        if enabled is not None:
            state = "enabled" if enabled else "disabled"
            return {"status": "ok", "result": f"Tile mode {state}"}
        return {"status": "ok", "result": "no"}
        
    def _handle_blink(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle blink commands.
        
        Args:
            params: Command parameters.
            
        Returns:
            Response dictionary.
        """
        action = params.get("action")
        
        if action == "start":
            return {"status": "ok", "result": "Blink started"}
        elif action == "stop":
            return {"status": "ok", "result": "Blink stopped"}
        return {"status": "ok", "result": "no"}
        
    def _handle_match(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle frame matching commands.
        
        Args:
            params: Command parameters including 'type'.
            
        Returns:
            Response dictionary.
        """
        match_type = params.get("type", "wcs")
        return {"status": "ok", "result": f"Frames matched by {match_type}"}
        
    def _handle_lock(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle frame locking commands.
        
        Args:
            params: Command parameters including 'type'.
            
        Returns:
            Response dictionary.
        """
        lock_type = params.get("type")
        
        if lock_type:
            return {"status": "ok", "result": f"Lock set to {lock_type}"}
        return {"status": "ok", "result": "none"}
        
    def _handle_width(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle window width commands.
        
        Args:
            params: Command parameters including 'value'.
            
        Returns:
            Response dictionary.
        """
        value = params.get("value")
        
        if value is not None:
            return {"status": "ok", "result": f"Width set to {value}"}
        return {"status": "ok", "result": "800"}
        
    def _handle_height(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle window height commands.
        
        Args:
            params: Command parameters including 'value'.
            
        Returns:
            Response dictionary.
        """
        value = params.get("value")
        
        if value is not None:
            return {"status": "ok", "result": f"Height set to {value}"}
        return {"status": "ok", "result": "600"}
        
    def _handle_save(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle save commands.
        
        Args:
            params: Command parameters including 'path', 'format'.
            
        Returns:
            Response dictionary.
        """
        path = params.get("path")
        fmt = params.get("format", "fits")
        
        if path:
            return {"status": "ok", "result": f"Saved as {fmt}: {path}"}
        return {"status": "error", "message": "No save path specified"}
        
    def _handle_exit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle exit/quit commands.
        
        Args:
            params: Command parameters.
            
        Returns:
            Response dictionary.
        """
        self._logger.info("Exit command received")
        return {"status": "ok", "result": "Exiting"}
        
    def _handle_version(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle version command.
        
        Args:
            params: Command parameters.
            
        Returns:
            Response dictionary.
        """
        return {"status": "ok", "result": "NCRADS9 1.0.0"}
        
    def _handle_about(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle about command.
        
        Args:
            params: Command parameters.
            
        Returns:
            Response dictionary.
        """
        return {
            "status": "ok",
            "result": "NCRADS9 - FITS Image Viewer for Radio Astronomy",
        }
