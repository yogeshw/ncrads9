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
from pathlib import Path
from typing import Any, Dict, Optional, Callable, List
from enum import Enum

from ...rendering.scale_algorithms import ScaleAlgorithm


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

    def _args(self, params: Dict[str, Any]) -> List[Any]:
        args = params.get("args", [])
        if isinstance(args, list):
            return args
        if args is None:
            return []
        return [args]

    def _first_arg(self, params: Dict[str, Any], default: Any = None) -> Any:
        args = self._args(params)
        if args:
            return args[0]
        return params.get("value", default)

    def _as_bool(self, value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        return None

    def _require_viewer(self) -> Optional[Dict[str, Any]]:
        if self.viewer is None:
            return {"status": "error", "message": "Viewer not connected"}
        return None
        
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
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        action = str(params.get("action", self._first_arg(params, "load"))).lower()
        path = params.get("path")
        if path is None:
            args = self._args(params)
            if action in {"load", "open"} and args:
                path = args[0]
            elif action in {"save", "saveas"} and len(args) > 1:
                path = args[1]

        if action in {"load", "open"}:
            if not path:
                return {"status": "error", "message": "No file path specified"}
            self.viewer.open_file(filepath=str(path))
            return {"status": "ok", "result": f"Loaded: {path}"}
        if action in {"save", "saveas"}:
            return {"status": "error", "message": "Save through XPA is not implemented"}
        if action in {"get", "current"}:
            frame = self.viewer.frame_manager.current_frame
            filename = frame.filepath.name if frame and frame.filepath else ""
            return {"status": "ok", "result": filename}
        return {"status": "error", "message": "Invalid file command"}
            
    def _handle_fits(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle FITS-specific commands.
        
        Args:
            params: Command parameters.
            
        Returns:
            Response dictionary.
        """
        params = dict(params)
        if "action" not in params:
            params["action"] = "load"
        return self._handle_file(params)
        
    def _handle_frame(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle frame commands.
        
        Args:
            params: Command parameters including 'action' and 'number'.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        action = str(params.get("action", self._first_arg(params, "get"))).lower()
        args = self._args(params)
        number = params.get("number")
        if number is None and action == "set" and args:
            number = args[0]
        if action not in {"new", "delete", "first", "last", "next", "prev", "previous", "get", "set"}:
            if isinstance(action, (int, float)) or str(action).isdigit():
                number = action
                action = "set"

        if action == "new":
            self.viewer._new_frame()
        elif action == "delete":
            self.viewer._delete_frame()
        elif action == "first":
            self.viewer._first_frame()
        elif action in {"prev", "previous"}:
            self.viewer._prev_frame()
        elif action == "next":
            self.viewer._next_frame()
        elif action == "last":
            self.viewer._last_frame()
        elif action == "set":
            if number is None:
                return {"status": "error", "message": "Frame number required"}
            index = max(0, int(number) - 1)
            frame = self.viewer.frame_manager.goto_frame(index)
            if frame is None:
                return {"status": "error", "message": f"Invalid frame: {number}"}
            self.viewer._update_frame_display()
        elif action == "get":
            return {
                "status": "ok",
                "result": str(self.viewer.frame_manager.current_index + 1),
            }
        else:
            return {"status": "error", "message": "Invalid frame command"}

        return {
            "status": "ok",
            "result": str(self.viewer.frame_manager.current_index + 1),
        }
        
    def _handle_zoom(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle zoom commands.
        
        Args:
            params: Command parameters including 'level' or 'action'.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        level = params.get("level")
        action = params.get("action")
        args = self._args(params)
        if action is None and args:
            action = str(args[0]).lower()
            if action not in {"fit", "in", "out", "to", "set", "get"}:
                level = args[0]

        if level is not None:
            self.viewer.image_viewer.zoom_to(float(level))
            self.viewer.status_bar.update_zoom(self.viewer.image_viewer.get_zoom())
            return {"status": "ok", "result": f"{self.viewer.image_viewer.get_zoom():.6g}"}
        if action in {"fit", "tofit"}:
            self.viewer._zoom_fit()
            return {"status": "ok", "result": f"{self.viewer.image_viewer.get_zoom():.6g}"}
        if action in {"in", "incr"}:
            self.viewer._zoom_in()
            return {"status": "ok", "result": f"{self.viewer.image_viewer.get_zoom():.6g}"}
        if action in {"out", "decr"}:
            self.viewer._zoom_out()
            return {"status": "ok", "result": f"{self.viewer.image_viewer.get_zoom():.6g}"}
        return {"status": "ok", "result": f"{self.viewer.image_viewer.get_zoom():.6g}"}
        
    def _handle_pan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle pan commands.
        
        Args:
            params: Command parameters including 'x', 'y' coordinates.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        x = params.get("x")
        y = params.get("y")
        args = self._args(params)
        if (x is None or y is None) and len(args) >= 2:
            x, y = args[0], args[1]
        if x is not None and y is not None:
            self.viewer._on_panner_pan(float(x), float(y))
        frame = self.viewer.frame_manager.current_frame
        if frame is None:
            return {"status": "ok", "result": "0 0"}
        return {"status": "ok", "result": f"{frame.pan_x:.6g} {frame.pan_y:.6g}"}
        
    def _handle_scale(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle scale/contrast commands.
        
        Args:
            params: Command parameters including 'mode', 'min', 'max'.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        mode = params.get("mode")
        limits = params.get("limits")
        args = self._args(params)
        if mode is None and args:
            mode = str(args[0]).lower()

        mode_map = {
            "linear": ScaleAlgorithm.LINEAR,
            "log": ScaleAlgorithm.LOG,
            "sqrt": ScaleAlgorithm.SQRT,
            "squared": ScaleAlgorithm.POWER,
            "power": ScaleAlgorithm.POWER,
            "asinh": ScaleAlgorithm.ASINH,
            "histeq": ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
            "histogram": ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
            "histogramequalization": ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
        }

        if mode in {"zscale"}:
            self.viewer._reset_scale_limits()
        elif mode in {"minmax"}:
            self.viewer._scale_minmax()
        elif mode in mode_map:
            self.viewer._set_scale(mode_map[mode])
        elif limits is not None and isinstance(limits, (list, tuple)) and len(limits) == 2:
            self.viewer.z1 = float(limits[0])
            self.viewer.z2 = float(limits[1])
            self.viewer._display_image()
        elif len(args) >= 2 and all(isinstance(v, (int, float)) for v in args[:2]):
            self.viewer.z1 = float(args[0])
            self.viewer.z2 = float(args[1])
            self.viewer._display_image()

        return {"status": "ok", "result": self.viewer.current_scale.name.lower()}
        
    def _handle_cmap(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle colormap commands.
        
        Args:
            params: Command parameters including 'name'.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        name = params.get("name", self._first_arg(params))
        cmap_map = {
            "gray": "grey",
            "grey": "grey",
            "heat": "heat",
            "cool": "cool",
            "rainbow": "rainbow",
            "viridis": "viridis",
            "plasma": "plasma",
            "inferno": "inferno",
            "magma": "magma",
        }
        if name is not None:
            selected = cmap_map.get(str(name).lower())
            if selected is None:
                return {"status": "error", "message": f"Unsupported colormap: {name}"}
            self.viewer._set_colormap(selected)
        return {"status": "ok", "result": self.viewer.current_colormap}
        
    def _handle_colorbar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle colorbar commands.
        
        Args:
            params: Command parameters including 'visible'.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        visible = params.get("visible", self._first_arg(params))
        if visible is not None:
            visible_bool = self._as_bool(visible)
            if visible_bool is not None:
                self.viewer.colorbar_dock.setVisible(visible_bool)
        return {"status": "ok", "result": "yes" if self.viewer.colorbar_dock.isVisible() else "no"}
        
    def _handle_regions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle region commands.
        
        Args:
            params: Command parameters including 'action', 'data'.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        action = str(params.get("action", self._first_arg(params, "get"))).lower()
        if action in {"delete", "clear"}:
            self.viewer._clear_regions()
            return {"status": "ok", "result": "Regions deleted"}
        frame = self.viewer.frame_manager.current_frame
        count = len(frame.regions) if frame else 0
        return {"status": "ok", "result": str(count)}
        
    def _handle_wcs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle WCS commands.
        
        Args:
            params: Command parameters.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        action = str(params.get("action", self._first_arg(params, "get"))).lower()
        if action == "set":
            system = str(params.get("system", self._first_arg(params, "fk5"))).lower()
            self.viewer._set_wcs_system(system)
            return {"status": "ok", "result": system}
        return {"status": "ok", "result": self.viewer.current_wcs_system}
        
    def _handle_crosshair(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle crosshair commands.
        
        Args:
            params: Command parameters including 'x', 'y'.
            
        Returns:
            Response dictionary.
        """
        return self._handle_cursor(params)
        
    def _handle_cursor(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cursor commands.
        
        Args:
            params: Command parameters.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        if self.viewer._last_mouse_pos is None:
            return {"status": "ok", "result": "0 0"}
        x, y = self.viewer._last_mouse_pos
        return {"status": "ok", "result": f"{x} {y}"}
        
    def _handle_mode(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle mode commands.
        
        Args:
            params: Command parameters including 'mode'.
            
        Returns:
            Response dictionary.
        """
        mode = params.get("mode", self._first_arg(params))
        if mode:
            return {"status": "ok", "result": str(mode)}
        return {"status": "ok", "result": "none"}
        
    def _handle_tile(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tile display commands.
        
        Args:
            params: Command parameters including 'enabled'.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        enabled = params.get("enabled", self._first_arg(params))
        enabled_bool = self._as_bool(enabled)
        if enabled_bool is not None:
            self.viewer.menu_bar.action_tile_frames.setChecked(enabled_bool)
            self.viewer._tile_frames(enabled_bool)
        return {
            "status": "ok",
            "result": "yes" if self.viewer.menu_bar.action_tile_frames.isChecked() else "no",
        }
        
    def _handle_blink(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle blink commands.
        
        Args:
            params: Command parameters.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        action = str(params.get("action", self._first_arg(params, "get"))).lower()
        if action in {"start", "on"}:
            self.viewer.menu_bar.action_blink_frames.setChecked(True)
            self.viewer._toggle_blink(True)
        elif action in {"stop", "off"}:
            self.viewer.menu_bar.action_blink_frames.setChecked(False)
            self.viewer._toggle_blink(False)
        return {
            "status": "ok",
            "result": "yes" if self.viewer._blink_timer.isActive() else "no",
        }
        
    def _handle_match(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle frame matching commands.
        
        Args:
            params: Command parameters including 'type'.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        match_type = str(params.get("type", self._first_arg(params, "wcs"))).lower()
        if match_type == "image":
            self.viewer._match_frames_image()
        else:
            self.viewer._match_frames_wcs()
            match_type = "wcs"
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
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        value = params.get("value", self._first_arg(params))
        if value is not None:
            self.viewer.resize(int(value), self.viewer.height())
        return {"status": "ok", "result": str(self.viewer.width())}
        
    def _handle_height(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle window height commands.
        
        Args:
            params: Command parameters including 'value'.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        value = params.get("value", self._first_arg(params))
        if value is not None:
            self.viewer.resize(self.viewer.width(), int(value))
        return {"status": "ok", "result": str(self.viewer.height())}
        
    def _handle_save(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle save commands.
        
        Args:
            params: Command parameters including 'path', 'format'.
            
        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        path = params.get("path", self._first_arg(params))
        if not path:
            return {"status": "error", "message": "No save path specified"}
        pixmap = self.viewer._get_current_pixmap()
        if pixmap is None:
            return {"status": "error", "message": "No image to save"}
        target = Path(str(path))
        if not pixmap.save(str(target)):
            return {"status": "error", "message": f"Failed to save {target}"}
        return {"status": "ok", "result": str(target)}
        
    def _handle_exit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle exit/quit commands.
        
        Args:
            params: Command parameters.
            
        Returns:
            Response dictionary.
        """
        if self.viewer is not None:
            self.viewer.close()
        self._logger.info("Exit command received")
        return {"status": "ok", "result": "Exiting"}
        
    def _handle_version(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle version command.
        
        Args:
            params: Command parameters.
            
        Returns:
            Response dictionary.
        """
        return {"status": "ok", "result": "NCRADS9 0.1.0"}
        
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
