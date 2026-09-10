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
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

from ...rendering.scale_algorithms import ScaleAlgorithm
from . import access_points


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

    def __init__(self, viewer: Any | None = None) -> None:
        """Initialize XPA command handlers.

        Args:
            viewer: Optional reference to the main viewer application.
        """
        self.viewer: Any | None = viewer
        self._logger: logging.Logger = logging.getLogger(__name__)
        #: DS9's access points that are a value or a call each, by name and
        #: by alias. The ones with real grammars are handlers below.
        self._points = access_points.by_name()
        self._command_handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "file": self._handle_file,
            "fits": self._handle_fits,
            "frame": self._handle_frame,
            "zoom": self._handle_zoom,
            "pan": self._handle_pan,
            "scale": self._handle_scale,
            "cmap": self._handle_cmap,
            "colorbar": self._handle_colorbar,
            "wcs": self._handle_wcs,
            "save": self._handle_save,
            "exit": self._handle_exit,
            "quit": self._handle_exit,
            "3d": self._handle_3d,
            "prism": self._handle_prism,
            "version": self._handle_version,
            "about": self._handle_about,
        }

    def set_viewer(self, viewer: Any) -> None:
        """Set the viewer reference.

        Args:
            viewer: Reference to the main viewer application.
        """
        self.viewer = viewer

    def _args(self, params: dict[str, Any]) -> list[Any]:
        args = params.get("args", [])
        if isinstance(args, list):
            return args
        if args is None:
            return []
        return [args]

    def _first_arg(self, params: dict[str, Any], default: Any = None) -> Any:
        args = self._args(params)
        if args:
            return args[0]
        return params.get("value", default)

    def _as_bool(self, value: Any) -> bool | None:
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

    def _require_viewer(self) -> dict[str, Any] | None:
        if self.viewer is None:
            return {"status": "error", "message": "Viewer not connected"}
        return None

    def handle(
        self,
        command: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle an XPA command.

        Args:
            command: The command name.
            params: The command parameters.

        Returns:
            Response dictionary with status and result/message.
        """
        # DS9 registers a handful of its points twice, once in each case
        # -- `3d` and `3D` are the same command -- so the name is lowered
        # and registered once.
        name = command.lower()
        handler = self._command_handlers.get(name)

        if handler is None:
            # The hand-written handlers above are the points with real
            # grammars; everything else is in the table, which is most of
            # DS9's 145.
            point = self._points.get(name)
            if point is not None:
                try:
                    return self._table_point(point, params)
                except Exception as exc:
                    self._logger.error("Error handling command %s: %s", command, exc)
                    return {"status": "error", "message": str(exc)}

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

    def _table_point(self, point, params: dict[str, Any]) -> dict[str, Any]:
        """Answer one access point out of the table.

        `xpaget` reads, `xpaset` sets, and a point that cannot do the one
        asked for says so rather than pretending.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        args = [str(value) for value in self._args(params)]
        if not args:
            # The hand-written handlers take their argument by keyword --
            # `{"enabled": True}`, `{"value": 2}` -- and callers inside the
            # application still do, so a point in the table understands
            # both rather than silently doing nothing for one of them.
            for key in ("value", "enabled", "action", "level", "name", "mode", "type"):
                if key in params and params[key] is not None:
                    found = params[key]
                    args = [access_points.on_off(found) if isinstance(found, bool) else str(found)]
                    break

        asked_to_read = bool(params.get("get"))
        if asked_to_read and point.query is not None:
            # A read that takes arguments: `xpaget ds9 dsssao size`,
            # `xpaget ds9 iexam coordinate image`. Without this, an
            # argument would make every read look like a write.
            return {"status": "ok", "result": point.query(self.viewer, args)}

        getting = asked_to_read and not args

        if getting or (point.set is None and point.get is not None):
            if point.get is None:
                return {"status": "error", "message": f"{point.name} cannot be read"}
            return {"status": "ok", "result": point.get(self.viewer)}

        if point.set is None:
            return {"status": "error", "message": f"{point.name} cannot be set"}
        problem = point.set(self.viewer, args)
        if problem:
            return {"status": "error", "message": problem}
        return {"status": "ok"}

    def get_available_commands(self) -> list[str]:
        """Get list of available commands.

        Returns:
            Every access point's name, the table's included.
        """
        return sorted({*self._command_handlers, *self._points})

    def describe_points(self) -> str:
        """What `xpaget ds9 xpa` lists: every point and what it does."""
        lines = []
        for name in self.get_available_commands():
            point = self._points.get(name)
            summary = point.summary if point is not None else ""
            lines.append(f"{name}\t{summary}" if summary else name)
        return "\n".join(lines)

    def register_command(
        self,
        name: str,
        handler: Callable[..., dict[str, Any]],
    ) -> None:
        """Register a custom command handler.

        Args:
            name: The command name.
            handler: The handler function.
        """
        self._command_handlers[name.lower()] = handler

    def _handle_file(self, params: dict[str, Any]) -> dict[str, Any]:
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
            self.viewer.file.open_file(filepath=str(path))
            return {"status": "ok", "result": f"Loaded: {path}"}
        if action in {"save", "saveas"}:
            return {"status": "error", "message": "Save through XPA is not implemented"}
        if action in {"get", "current"}:
            frame = self.viewer.frame_manager.current_frame
            filename = frame.filepath.name if frame and frame.filepath else ""
            return {"status": "ok", "result": filename}
        return {"status": "error", "message": "Invalid file command"}

    def _handle_fits(self, params: dict[str, Any]) -> dict[str, Any]:
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

    def _handle_frame(self, params: dict[str, Any]) -> dict[str, Any]:
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
        if action not in {
            "new",
            "rgb",
            "hsv",
            "hls",
            "3d",
            "delete",
            "deleteall",
            "delete_all",
            "clear",
            "reset",
            "refresh",
            "first",
            "last",
            "next",
            "prev",
            "previous",
            "get",
            "set",
        }:
            if isinstance(action, (int, float)) or str(action).isdigit():
                number = action
                action = "set"

        if action == "new":
            self.viewer.frame_controller.new_frame()
        elif action in {"rgb", "hsv", "hls", "3d"}:
            if hasattr(self.viewer.frame_controller, "new_frame_of_type"):
                self.viewer.frame_controller.new_frame_of_type(action)
            else:
                self.viewer.frame_controller.new_frame()
        elif action == "delete":
            self.viewer.frame_controller.delete_current()
        elif action in {"deleteall", "delete_all"}:
            if hasattr(self.viewer.frame_controller, "delete_all"):
                self.viewer.frame_controller.delete_all()
        elif action == "clear":
            if hasattr(self.viewer.frame_controller, "clear_current"):
                self.viewer.frame_controller.clear_current()
        elif action == "reset":
            if hasattr(self.viewer.frame_controller, "reset_current"):
                self.viewer.frame_controller.reset_current()
        elif action == "refresh":
            if hasattr(self.viewer.frame_controller, "refresh_current"):
                self.viewer.frame_controller.refresh_current()
        elif action == "first":
            self.viewer.frame_controller.first()
        elif action in {"prev", "previous"}:
            self.viewer.frame_controller.previous()
        elif action == "next":
            self.viewer.frame_controller.next()
        elif action == "last":
            self.viewer.frame_controller.last()
        elif action == "set":
            if number is None:
                return {"status": "error", "message": "Frame number required"}
            index = max(0, int(number) - 1)
            frame = self.viewer.frame_manager.goto_frame(index)
            if frame is None:
                return {"status": "error", "message": f"Invalid frame: {number}"}
            self.viewer.frame_controller.update_display()
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

    def _handle_zoom(self, params: dict[str, Any]) -> dict[str, Any]:
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
            self.viewer.zoom.zoom_fit()
            return {"status": "ok", "result": f"{self.viewer.image_viewer.get_zoom():.6g}"}
        if action in {"in", "incr"}:
            self.viewer.zoom.zoom_in()
            return {"status": "ok", "result": f"{self.viewer.image_viewer.get_zoom():.6g}"}
        if action in {"out", "decr"}:
            self.viewer.zoom.zoom_out()
            return {"status": "ok", "result": f"{self.viewer.image_viewer.get_zoom():.6g}"}
        return {"status": "ok", "result": f"{self.viewer.image_viewer.get_zoom():.6g}"}

    def _handle_pan(self, params: dict[str, Any]) -> dict[str, Any]:
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
            self.viewer.zoom.on_panner_pan(float(x), float(y))
        frame = self.viewer.frame_manager.current_frame
        if frame is None:
            return {"status": "ok", "result": "0 0"}
        return {"status": "ok", "result": f"{frame.pan_x:.6g} {frame.pan_y:.6g}"}

    def _handle_scale(self, params: dict[str, Any]) -> dict[str, Any]:
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
            self.viewer.scale.reset_limits()
        elif mode in {"minmax"}:
            self.viewer.scale.set_minmax_limits()
        elif mode in mode_map:
            self.viewer.scale.set_scale(mode_map[mode])
        elif limits is not None and isinstance(limits, (list, tuple)) and len(limits) == 2:
            self.viewer.z1 = float(limits[0])
            self.viewer.z2 = float(limits[1])
            self.viewer.display.display()
        elif len(args) >= 2 and all(isinstance(v, (int, float)) for v in args[:2]):
            self.viewer.z1 = float(args[0])
            self.viewer.z2 = float(args[1])
            self.viewer.display.display()

        return {"status": "ok", "result": self.viewer.current_scale.name.lower()}

    def _handle_cmap(self, params: dict[str, Any]) -> dict[str, Any]:
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
        if name is not None:
            selected = str(name).lower().strip()
            if selected == "gray":
                selected = "grey"
            if hasattr(self.viewer.color, "available_colormaps"):
                available = set(self.viewer.color.available_colormaps())
            else:
                available = {"grey", "heat", "cool", "rainbow", "viridis", "plasma", "inferno", "magma"}
            if selected not in available:
                return {"status": "error", "message": f"Unsupported colormap: {name}"}
            self.viewer.color.set_colormap(selected)
        return {"status": "ok", "result": self.viewer.current_colormap}

    def _handle_colorbar(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle colorbar commands.

        Args:
            params: Command parameters including 'visible'.

        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        args = self._args(params)
        visible = params.get("visible")
        if visible is None and args:
            candidate = self._as_bool(args[0])
            if candidate is not None:
                visible = candidate
        if visible is not None:
            visible_bool = self._as_bool(visible)
            if visible_bool is not None and hasattr(self.viewer.view, "set_colorbar_visible"):
                self.viewer.view.set_colorbar_visible(visible_bool)

        orientation = params.get("orientation")
        if orientation is None and args:
            first = str(args[0]).lower()
            if first in {"horizontal", "vertical"}:
                orientation = first
        if orientation is not None and hasattr(self.viewer.color, "set_colorbar_orientation"):
            self.viewer.color.set_colorbar_orientation(str(orientation).lower())

        numerics = params.get("numerics")
        if numerics is None and len(args) > 1:
            numerics = args[1]
        if numerics is not None and hasattr(self.viewer.color, "set_colorbar_numerics"):
            numerics_bool = self._as_bool(numerics)
            if numerics_bool is not None:
                self.viewer.color.set_colorbar_numerics(numerics_bool)

        spacing = params.get("spacing")
        if spacing is not None and hasattr(self.viewer.color, "set_colorbar_spacing"):
            spacing_mode = str(spacing).lower()
            if spacing_mode in {"value", "distance"}:
                self.viewer.color.set_colorbar_spacing(spacing_mode)

        ticks = params.get("ticks")
        if ticks is not None and hasattr(self.viewer, "colorbar_widget"):
            try:
                self.viewer.colorbar_widget.set_tick_count(int(ticks))
            except (TypeError, ValueError):
                pass

        size = params.get("size")
        if size is not None and hasattr(self.viewer, "colorbar_widget"):
            try:
                self.viewer.colorbar_widget.set_bar_size(int(size))
            except (TypeError, ValueError):
                pass

        result = "yes"
        state = getattr(self.viewer, "view_state", None)
        if state is not None:
            result = "yes" if state.colorbar else "no"
        return {"status": "ok", "result": result}

    def _handle_wcs(self, params: dict[str, Any]) -> dict[str, Any]:
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
            self.viewer.wcs.set_sky_frame(system)
            return {"status": "ok", "result": system}
        return {"status": "ok", "result": self.viewer.coord_context.sky.value}

    def _handle_save(self, params: dict[str, Any]) -> dict[str, Any]:
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
        pixmap = self.viewer.file.current_pixmap()
        if pixmap is None:
            return {"status": "error", "message": "No image to save"}
        target = Path(str(path))
        if not pixmap.save(str(target)):
            return {"status": "error", "message": f"Failed to save {target}"}
        return {"status": "ok", "result": str(target)}

    def _handle_exit(self, params: dict[str, Any]) -> dict[str, Any]:
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

    #: What `prism import` and `prism export` call each format, and what
    #: `catalogs/catalog_file.py` calls it (`xpa.html`, the prism section).
    PRISM_FORMATS = {"xml": "votable", "rdb": "starbase", "tsv": "tsv"}

    def _handle_3d(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the `3d` access point.

        `xpaset -p ds9 3d` makes the frame a 3D frame; `3d vp <az> <el>`
        turns it, `3d scale`, `3d method mip|aip` and
        `3d background none|azimuth|elevation` are the rest of the dialog
        (`ds9/doc/ref/3d.html`).

        Args:
            params: The command's arguments.

        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        controller = getattr(self.viewer, "frame_3d", None)
        if controller is None:
            return {"status": "error", "message": "3D frames not available"}

        args = [str(value) for value in self._args(params)]
        if not args:
            if params.get("get"):
                return {"status": "ok", "result": controller.describe()}
            # A bare `3d` creates a 3D frame, as DS9's parser has it.
            self.viewer.frame_controller.new_frame_of_type("3d")
            return {"status": "ok"}

        command = args[0].lower()
        rest = args[1:]

        if command in ("vp", "view"):
            if len(rest) < 2:
                return {"status": "error", "message": "3d vp needs an azimuth and an elevation"}
            controller.set_view(azimuth=float(rest[0]), elevation=float(rest[1]))
            return {"status": "ok"}
        if command == "az":
            if not rest:
                return {"status": "error", "message": "3d az needs an angle"}
            controller.set_view(azimuth=float(rest[0]))
            return {"status": "ok"}
        if command == "el":
            if not rest:
                return {"status": "error", "message": "3d el needs an angle"}
            controller.set_view(elevation=float(rest[0]))
            return {"status": "ok"}
        if command == "scale":
            if not rest:
                return {"status": "error", "message": "3d scale needs a factor"}
            controller.set_view(scale=float(rest[0]))
            return {"status": "ok"}
        if command == "method":
            if not rest or not controller.set_method(rest[0].lower()):
                return {"status": "error", "message": "3d method is mip or aip"}
            return {"status": "ok"}
        if command == "background":
            if not rest or not controller.set_background(rest[0].lower()):
                return {
                    "status": "error",
                    "message": "3d background is none, azimuth or elevation",
                }
            return {"status": "ok"}
        if command in ("highlite", "border", "compass"):
            if not rest:
                return {"status": "ok", "result": str(controller.setting(command))}
            wanted = self._as_bool(rest[0])
            if wanted is None:
                controller.set_setting(f"{command}_color", rest[0])
            else:
                controller.set_setting(command, wanted)
            return {"status": "ok"}
        if command == "lock":
            wanted = self._as_bool(rest[0]) if rest else None
            controller.set_locked(bool(wanted))
            return {"status": "ok"}
        if command == "match":
            controller.match()
            return {"status": "ok"}
        if command == "reset":
            controller.reset()
            return {"status": "ok"}
        if command == "open":
            controller.show_dialog()
            return {"status": "ok"}
        if command == "close":
            dialog = getattr(controller, "_dialog", None)
            if dialog is not None:
                dialog.close()
            return {"status": "ok"}

        return {"status": "error", "message": f"Unknown 3d command: {command}"}

    def _handle_prism(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the `prism` access point.

        `xpaget` lists the open windows; `xpaset` opens one, loads a file
        into it, walks its extensions or plots one of its columns. The whole
        syntax is in `ds9/doc/ref/xpa.html` under `prism`.

        Args:
            params: The command's arguments.

        Returns:
            Response dictionary.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        controller = getattr(self.viewer, "prism", None)
        if controller is None:
            return {"status": "error", "message": "Prism not available"}

        args = [str(value) for value in self._args(params)]
        if not args:
            # `xpaget prism` lists the windows; `xpaset -p prism` opens one.
            if params.get("get"):
                return {"status": "ok", "result": "\n".join(controller.refs())}
            controller.ensure()
            return {"status": "ok", "result": "\n".join(controller.refs())}

        command = args[0].lower()
        rest = args[1:]

        if command == "open":
            # Bare `prism` and `prism open` both open on the current frame's
            # file, as DS9's parser has them (`prismparser.tac:49`).
            controller.show()
            return {"status": "ok"}
        if command == "current":
            if not rest or not controller.set_current(rest[0]):
                return {"status": "error", "message": "Unable to find PRISM window"}
            return {"status": "ok"}

        if command == "load":
            if not rest:
                return {"status": "error", "message": "prism load needs a filename"}
            controller.show(rest[0])
            return {"status": "ok"}

        if command in ("import", "export"):
            if len(rest) < 2 or rest[0].lower() not in self.PRISM_FORMATS:
                return {"status": "error", "message": f"prism {command} needs a format and a file"}
            from ...catalogs import catalog_file

            chosen = catalog_file.CatalogFormat(self.PRISM_FORMATS[rest[0].lower()])
            dialog = controller.ensure()
            action = dialog.import_table if command == "import" else dialog.export_table
            ok = action(chosen, rest[1])
            return {"status": "ok"} if ok else {"status": "error", "message": f"prism {command} failed"}

        # `prism foo.fits`: a bare filename opens a window on that file
        # (`prismparser.tac:51`).
        from pathlib import Path

        if len(args) == 1 and Path(args[0]).exists():
            controller.show(args[0])
            return {"status": "ok"}

        dialog = controller.latest
        if dialog is None:
            return {"status": "error", "message": "No PRISM window"}

        if command == "clear":
            dialog.clear()
            return {"status": "ok"}
        if command == "ext":
            if not rest or not dialog.select_extension(rest[0]):
                return {"status": "error", "message": "No such extension"}
            return {"status": "ok"}
        if command in ("first", "next", "prev", "last"):
            {
                "first": dialog.first_block,
                "next": dialog.next_block,
                "prev": dialog.previous_block,
                "last": dialog.last_block,
            }[command]()
            return {"status": "ok"}
        if command == "goto":
            if not rest:
                return {"status": "error", "message": "prism goto needs a row"}
            dialog.goto_row(int(float(rest[0])))
            return {"status": "ok"}
        if command == "image":
            return (
                {"status": "ok"} if dialog.load_image() else {"status": "error", "message": "No file loaded"}
            )
        if command == "mode":
            if not rest:
                return {"status": "ok", "result": dialog.plot_mode}
            dialog.plot_mode = rest[0].lower()
            return {"status": "ok"}

        if command == "histogram":
            if not rest:
                return {"status": "error", "message": "prism histogram needs a column"}
            bins = int(float(rest[1])) if len(rest) > 1 else None
            low, high = (float(rest[2]), float(rest[3])) if len(rest) > 3 else (None, None)
            plot = dialog.histogram(rest[0], bins, low, high)
            return {"status": "ok"} if plot is not None else {"status": "error", "message": "Unable to plot"}

        if command == "plot":
            # The last word says which of the remaining columns are errors:
            # xy, xyex, xyey or xyexey (`xpa.html`).
            columns = list(rest)
            shape = columns.pop().lower() if columns and columns[-1].lower().startswith("xy") else "xy"
            if len(columns) < 2:
                return {"status": "error", "message": "prism plot needs two columns"}
            x_error = y_error = None
            extra = columns[2:]
            if shape == "xyex" and extra:
                x_error = extra[0]
            elif shape == "xyey" and extra:
                y_error = extra[0]
            elif shape == "xyexey" and len(extra) > 1:
                x_error, y_error = extra[0], extra[1]
            plot = dialog.plot(columns[0], columns[1], x_error, y_error)
            return {"status": "ok"} if plot is not None else {"status": "error", "message": "Unable to plot"}

        return {"status": "error", "message": f"Unknown prism command: {command}"}

    def _handle_version(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle version command.

        Args:
            params: Command parameters.

        Returns:
            Response dictionary.
        """
        return {"status": "ok", "result": "NCRADS9 0.1.0"}

    def _handle_about(self, params: dict[str, Any]) -> dict[str, Any]:
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
