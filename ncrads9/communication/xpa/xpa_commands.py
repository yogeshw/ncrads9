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

from ...coordinates import positions
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

        if handler is not None and bool(params.get("get")):
            # A read never writes -- the same rule the table enforces, and
            # it has to hold here too or `xpaget ds9 frame delete` deletes
            # the frame. A handler with a dedicated reader answers
            # precisely; one without answers with its plain current value,
            # the arguments dropped, which is imprecise but cannot do
            # damage. Being vague about an answer is a nuisance; answering
            # a question by changing the answer is a bug.
            reader = getattr(self, f"_read_{name}", None)
            try:
                if reader is not None:
                    return reader([str(word) for word in self._args(params)])
                return handler({"get": True, "action": "get"})
            except Exception as exc:
                self._logger.error("Error reading %s: %s", command, exc)
                return {"status": "error", "message": str(exc)}

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

        # A read never writes. Sixty-five of DS9's points take arguments on
        # a read -- `xpaget ds9 contour clear`, `xpaget ds9 dsssao size` --
        # and falling through to the setter for those would have `xpaget`
        # *clear the contours*, which is the worst kind of bug: a command
        # documented as a question that answers by changing something.
        if bool(params.get("get")):
            if point.query is not None:
                return {"status": "ok", "result": point.query(self.viewer, args)}
            if point.get is not None:
                return {"status": "ok", "result": point.get(self.viewer)}
            return {"status": "error", "message": f"{point.name} cannot be read"}

        if point.set is None and point.get is not None:
            return {"status": "ok", "result": point.get(self.viewer)}

        if point.set is None:
            return {"status": "error", "message": f"{point.name} cannot be set"}
        data = params.get("data")
        if data and point.name in ("regions", "region"):
            # `echo "circle 100 100 20" | xpaset ds9 regions`: the regions
            # arrive on standard input, in DS9's region syntax.
            text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else str(data)
            problem = access_points._region_command(self.viewer, text)
            return {"status": "error", "message": problem} if problem else {"status": "ok"}
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

    # -- file and fits -----------------------------------------------------

    def _read_file(self, args: list[str]) -> dict[str, Any]:
        """`xpaget ds9 file`: what the current frame was loaded from."""
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        frame = self.viewer.frame_manager.current_frame
        if frame is None or frame.filepath is None:
            return {"status": "ok", "result": ""}
        return {"status": "ok", "result": str(frame.file_spec or frame.filepath)}

    def _read_fits(self, args: list[str]) -> dict[str, Any]:
        """`xpaget ds9 fits [width|height|depth|bitpix|size ...|count|header
        [<ext>] [keyword <name>]|image|table|slice]`.

        Bare, or with `image`, `table` or `slice`, the answer is the FITS
        file itself, as bytes, for `xpaget ds9 fits > foo.fits`.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        frame = self.viewer.frame_manager.current_frame
        if frame is None or frame.image_data is None:
            return {"status": "error", "message": "the frame is empty"}
        words = [word.lower() for word in args]
        what = words[0] if words else ""

        image = getattr(frame, "image", None)
        shape = image.data.shape if image is not None else frame.image_data.shape
        width, height = int(shape[-1]), int(shape[-2])
        depth = int(shape[-3]) if len(shape) >= 3 else 1

        if what == "width":
            return {"status": "ok", "result": str(width)}
        if what == "height":
            return {"status": "ok", "result": str(height)}
        if what == "depth":
            return {"status": "ok", "result": str(depth)}
        if what == "bitpix":
            bitpix = getattr(image, "bitpix", None) if image is not None else None
            if bitpix is None:
                bitpix = (frame.header or {}).get("BITPIX", -32)
            return {"status": "ok", "result": str(bitpix)}
        if what == "count":
            segments = getattr(frame, "mosaic_segments", None)
            return {"status": "ok", "result": str(len(segments) if segments else 1)}
        if what == "size":
            return {"status": "ok", "result": self._fits_size(frame, words[1:], width, height)}
        if what == "header":
            return self._fits_header(frame, args[1:])
        if what in ("", "image", "table", "slice"):
            return {"status": "ok", "result": self._fits_bytes(frame, what)}
        return {"status": "error", "message": f"fits has no {what}"}

    @staticmethod
    def _fits_size(frame, words: list[str], width: int, height: int) -> str:
        """The image's size in pixels, or on the sky in the units asked for."""
        _values, system, sky, _format = positions.split_spec(words)
        unit = next((word for word in words if word in ("degrees", "arcmin", "arcsec", "arcsecs")), "degrees")
        if not system.startswith("wcs"):
            return f"{width} {height}"
        handler = positions.wcs_handler(frame, system)
        if handler is None:
            return f"{width} {height}"
        from astropy.wcs.utils import proj_plane_pixel_scales

        scales = proj_plane_pixel_scales(handler.wcs)
        factor = {"degrees": 1.0, "arcmin": 60.0}.get(unit, 3600.0)
        return f"{width * scales[0] * factor:.8g} {height * scales[1] * factor:.8g}"

    def _fits_header(self, frame, words: list[str]) -> dict[str, Any]:
        """`fits header [<ext>] [keyword <name>]`."""
        from astropy.io import fits

        keyword = None
        if "keyword" in [word.lower() for word in words]:
            at = [word.lower() for word in words].index("keyword")
            keyword = words[at + 1] if at + 1 < len(words) else None
            words = words[:at]
        header = None
        if words and words[0].lstrip("-").isdigit() and frame.filepath is not None:
            # DS9 counts extensions from one for the primary; a minus sign
            # asks for inheritance, which a single header does not need.
            ext = abs(int(words[0])) - 1
            try:
                header = fits.getheader(str(frame.filepath), ext=ext)
            except (OSError, IndexError) as exc:
                return {"status": "error", "message": str(exc)}
        if header is None:
            raw = frame.header or {}
            header = raw if isinstance(raw, fits.Header) else fits.Header(raw)
        if keyword is not None:
            value = header.get(keyword.upper())
            return {"status": "ok", "result": "" if value is None else str(value)}
        return {"status": "ok", "result": "\n".join(str(card) for card in header.cards)}

    @staticmethod
    def _fits_bytes(frame, what: str) -> bytes:
        """The frame's data as a FITS file in memory."""
        import io

        from astropy.io import fits

        raw = frame.header or {}
        header = raw.copy() if isinstance(raw, fits.Header) else fits.Header(raw)
        data = frame.image_data
        image = getattr(frame, "image", None)
        if what in ("", "image") and image is not None and image.data.ndim >= 3 and what == "":
            data = image.data
        for key in ("SIMPLE", "XTENSION", "BITPIX", "EXTEND", "PCOUNT", "GCOUNT"):
            header.remove(key, ignore_missing=True, remove_all=True)
        buffer = io.BytesIO()
        fits.PrimaryHDU(data=data, header=header).writeto(buffer)
        return buffer.getvalue()

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

        args = [str(word) for word in self._args(params)]
        verbs = {"load", "open", "save", "saveas", "get", "current", "new", "delete", "slice", "mask"}

        # `xpaset -p ds9 file foo.fits` is DS9's own first rule and the
        # commonest XPA command there is: a bare filename, no verb. The
        # first word was being read as the verb, so the path became the
        # verb and the whole thing was refused.
        action = str(params.get("action", "")).lower()
        if not action:
            action = args[0].lower() if args and args[0].lower() in verbs else "load"

        path = params.get("path")
        if path is None:
            candidates = [word for word in args if word.lower() not in verbs]
            path = candidates[0] if candidates else None

        if bool(params.get("get")) or action in {"get", "current"}:
            frame = self.viewer.frame_manager.current_frame
            return {
                "status": "ok",
                "result": str(frame.filepath) if frame and frame.filepath else "",
            }
        if action in {"load", "open", "new", "slice", "mask"}:
            if not path:
                return {"status": "error", "message": "No file path specified"}
            if action == "mask":
                # `fits mask foo.fits`: an overlay on the frame, not a new image.
                if not self.viewer.analysis.load_mask(str(path)):
                    return {"status": "error", "message": f"could not load {path} as a mask"}
                return {"status": "ok", "result": f"Loaded mask: {path}"}
            if action == "new":
                self.viewer.frame_controller.new_frame()
            if action == "slice":
                problem = self.viewer.file.open_as("slice", str(path))
                if problem:
                    return {"status": "error", "message": problem}
                return {"status": "ok", "result": f"Loaded: {path}"}
            self.viewer.file.open_file(filepath=str(path))
            return {"status": "ok", "result": f"Loaded: {path}"}
        if action in {"save", "saveas"}:
            if not path:
                return {"status": "error", "message": "No file path specified"}
            problem = self.viewer.file.save_fits_to(str(path))
            if problem:
                return {"status": "error", "message": problem}
            return {"status": "ok", "result": f"Saved: {path}"}
        if action == "delete":
            self.viewer.frame_controller.clear_current()
            return {"status": "ok"}
        return {"status": "error", "message": "Invalid file command"}

    def _load_piped_fits(self, data: bytes, verb: str) -> dict[str, Any]:
        """`cat foo.fits | xpaset ds9 fits [new|slice|mask]`: the file on stdin.

        Written to a temporary file and loaded from there, so every loader
        -- cube, mask, new frame -- sees an ordinary path.
        """
        import tempfile

        with tempfile.NamedTemporaryFile(prefix="ncrads9-xpa-", suffix=".fits", delete=False) as handle:
            handle.write(data if isinstance(data, bytes) else str(data).encode("latin-1"))
        return self._handle_file({"args": [verb, handle.name]})

    def _handle_fits(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle FITS-specific commands.

        Args:
            params: Command parameters.

        Returns:
            Response dictionary.
        """
        data = params.get("data")
        if data:
            words = [str(word).lower() for word in self._args(params)]
            verb = next((word for word in words if word in ("new", "slice", "mask")), "load")
            return self._load_piped_fits(data, verb)
        params = dict(params)
        if "action" not in params:
            params["action"] = "load"
        return self._handle_file(params)

    # -- frame -------------------------------------------------------------

    # DS9 names frames by number, and a frame keeps its number when another
    # is deleted or the order changes: delete Frame 1 of two and what is
    # left is Frame 2. These points therefore speak in frame ids, not in
    # positions in the list.

    def _frame_ids(self) -> list[int]:
        return [frame.frame_id for frame in self.viewer.frame_manager.frames]

    def _frame_index(self, frame_id: int) -> int | None:
        """Where the frame with this id is in the list, or None."""
        for index, frame in enumerate(self.viewer.frame_manager.frames):
            if frame.frame_id == frame_id:
                return index
        return None

    def _current_frame_id(self) -> str:
        frame = self.viewer.frame_manager.current_frame
        return str(frame.frame_id) if frame is not None else "0"

    def _goto_frame_id(self, frame_id: int) -> None:
        """Go to a frame by number, creating it if there is none, as DS9 does."""
        frames = self.viewer.frame_manager
        controller = self.viewer.frame_controller
        index = self._frame_index(frame_id)
        if index is None:
            # DS9 makes the frame asked for, under that number.
            controller.new_frame_of_type("base", frame_id=frame_id)
            index = self._frame_index(frame_id)
            if index is None:
                return
        frame = frames.frames[index]
        if frame.frame_id not in self.viewer._active_frame_ids:
            controller.set_active(frame.frame_id, True)
        controller.goto_index(index)

    def _targets(self, words: list[str]) -> list[int] | None:
        """The frames `[<integer>|all]` names, as list indices.

        Returns None if a number names no frame.
        """
        frames = self.viewer.frame_manager
        if not words:
            return [frames.current_index]
        if words[0].lower() == "all":
            return list(range(len(frames.frames)))
        if not words[0].isdigit():
            return None
        index = self._frame_index(int(words[0]))
        return None if index is None else [index]

    def _on_frames(self, indices: list[int], act) -> None:
        """Do something to each of several frames, coming back to this one."""
        frames = self.viewer.frame_manager
        home = frames.current_frame
        for index in indices:
            frames.goto_frame(index)
            act()
        if home is not None and home in frames.frames:
            frames.goto_frame(frames.frames.index(home))
        self.viewer.frame_controller.update_display()

    def _handle_frame(self, params: dict[str, Any]) -> dict[str, Any]:
        """DS9's `frame`.

        `frame <n>` goes to a frame (making it if need be), `frame new
        [rgb|hsv|hls|3d]` makes one, `delete|clear|reset|refresh|center|
        hide|show [<n>|all]` act on one frame or every frame, `move
        first|back|forward|last` reorders, `first|next|prev|last` step,
        and `match|lock <coordsys>` are Frame -> Match and Lock.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        words = [str(word) for word in self._args(params)]
        if not words and params.get("action") is not None:
            words = [str(params["action"])]
            if params.get("number") is not None:
                words.append(str(params["number"]))
        if not words:
            return {"status": "ok", "result": self._current_frame_id()}
        action = words[0].lower()
        rest = words[1:]
        controller = self.viewer.frame_controller
        frames = self.viewer.frame_manager

        def done(problem: str | None = None) -> dict[str, Any]:
            if problem:
                return {"status": "error", "message": problem}
            return {"status": "ok", "result": self._current_frame_id()}

        # The reads, arriving as a write -- `frame has grid` without `-p`.
        if action in ("all", "active", "has", "get") or (action == "frameno" and not rest):
            answer = self._frame_read(action, words)
            if answer is not None:
                return {"status": "ok", "result": answer}

        if action.isdigit():
            self._goto_frame_id(int(action))
            return done()
        if action == "frameno":
            if not rest[0].isdigit():
                return done(f"{rest[0]} is not a frame number")
            self._goto_frame_id(int(rest[0]))
            return done()
        if action == "set" and rest and rest[0].isdigit():
            self._goto_frame_id(int(rest[0]))
            return done()
        if action == "new":
            kind = rest[0].lower() if rest else "base"
            if kind == "hvsv":
                # DS9's own documentation spells it so.
                kind = "hsv"
            if kind not in ("base", "rgb", "hsv", "hls", "3d"):
                return done(f"{rest[0]} is not a kind of frame")
            controller.new_frame_of_type(kind)
            return done()
        if action in ("rgb", "hsv", "hls", "3d"):
            controller.new_frame_of_type(action)
            return done()
        if action in ("first", "next", "prev", "previous", "last"):
            {
                "first": controller.first,
                "next": controller.next,
                "prev": controller.previous,
                "previous": controller.previous,
                "last": controller.last,
            }[action]()
            return done()
        if action == "move":
            where = rest[0].lower() if rest else ""
            mover = {
                "first": controller.move_first,
                "back": controller.move_back,
                "forward": controller.move_forward,
                "last": controller.move_last,
            }.get(where)
            if mover is None:
                return done("move takes first, back, forward or last")
            mover()
            return done()
        if action in ("match", "lock"):
            if not rest:
                return done(f"frame {action} takes a coordinate system")
            point = self._points.get(action)
            problem = point.set(self.viewer, ["frame", *rest]) if point is not None else None
            return done(problem)

        if action in ("delete", "deleteall", "delete_all", "clear", "reset", "refresh", "center", "hide", "show"):
            if action in ("deleteall", "delete_all"):
                action, rest = "delete", ["all"]
            targets = self._targets(rest)
            if targets is None:
                return done(f"there is no frame {rest[0]}")
            if action == "delete":
                if rest and rest[0].lower() == "all":
                    controller.delete_all()
                    return done()
                frames.goto_frame(targets[0])
                controller.delete_current()
                return done()
            if action == "hide":
                for index in targets:
                    controller.set_active(frames.frames[index].frame_id, False)
                return done()
            if action == "show":
                if rest and rest[0].lower() == "all":
                    controller.show_all()
                    return done()
                for index in targets:
                    controller.set_active(frames.frames[index].frame_id, True)
                return done()
            act = {
                "clear": controller.clear_current,
                "reset": controller.reset_current,
                "refresh": controller.refresh_current,
                "center": self.viewer.zoom.center_image,
            }[action]
            if targets == [frames.current_index]:
                act()
            else:
                self._on_frames(targets, act)
            return done()
        return done(f"{words[0]} is not a frame command")

    def _read_frame(self, args: list[str]) -> dict[str, Any]:
        """`xpaget ds9 frame ...`, which has a grammar of its own."""
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        action = args[0].lower() if args else ""
        answer = self._frame_read(action, args)
        if answer is None:
            answer = self._current_frame_id()
        return {"status": "ok", "result": answer}

    def _frame_read(self, action: str, args: list[str]) -> str | None:
        """DS9's `xpaget ds9 frame ...`, or None if it is not a read.

        `frame has <capability>` answers yes or no for each of DS9's
        capabilities; one we have no notion of answers `no`, which is true
        and is what a script branches on.
        """
        frames = self.viewer.frame_manager
        controller = self.viewer.frame_controller

        if action in ("", "get", "frameno"):
            return self._current_frame_id()
        if action == "all":
            return " ".join(str(frame_id) for frame_id in self._frame_ids())
        if action == "active":
            return " ".join(str(frames.frames[index].frame_id) for index in controller.active_indices())
        if action == "lock":
            # The same text the `lock` point answers with, so the two
            # spellings of DS9's question give one answer.
            return access_points._lock_text(self.viewer)
        if action == "has":
            # `args` still carries the verb, since the dispatcher hands the
            # whole argument list over; `frame has fits cube` asks about
            # "fits cube", not about "has fits cube".
            return access_points.on_off(self._frame_has([w for w in args if w.lower() != "has"]))
        return None

    @staticmethod
    def _frame_has_wcs(frame, words: list[str]) -> bool:
        """`frame has wcs [celestial|linear] [<wcssys>]`."""
        kind = words[0] if words and words[0] in ("celestial", "linear") else ""
        names = [word for word in words if word not in ("celestial", "linear")]
        system = names[0] if names else "wcs"
        header = getattr(frame, "header", None)
        if not header:
            return False
        key = "" if system == "wcs" else system[3:].upper()
        if f"CTYPE1{key}" not in header:
            return False
        try:
            from astropy.io import fits
            from astropy.wcs import WCS

            described = WCS(header if isinstance(header, fits.Header) else fits.Header(header), key=key or " ")
        except Exception:
            return False
        if kind == "celestial":
            return bool(described.has_celestial)
        if kind == "linear":
            return not described.has_celestial
        return True

    def _frame_has(self, words: list[str]) -> bool:
        """Whether the current frame has what `frame has ...` asks about."""
        frame = self.viewer.frame_manager.current_frame
        if frame is None or not words:
            return False
        what = " ".join(word.lower() for word in words)
        data = getattr(frame, "image_data", None)
        if what.startswith("fits"):
            if data is None:
                return False
            if what == "fits cube":
                return getattr(frame, "image", None) is not None and frame.image.data.ndim >= 3
            if what == "fits bin":
                return bool(getattr(frame, "bin_table", None))
            if what == "fits mosaic":
                return bool(getattr(frame, "is_mosaic", False))
            return True
        if what.startswith("system "):
            system = what.split()[1]
            if system == "image":
                return data is not None
            what = "physical" if system in ("physical", "amplifier", "detector") else "wcs " + system
        if what.startswith("wcs"):
            return self._frame_has_wcs(frame, what.split()[1:])
        if what == "physical":
            header = getattr(frame, "header", None) or {}
            return any(key in header for key in ("LTM1_1", "LTM2_2", "LTV1", "LTV2"))
        if what in ("amplifier", "detector"):
            return False
        if what in ("datamin", "irafmin", "datasec"):
            return data is not None
        if what == "grid":
            return bool(self.viewer.menu_bar.action_coordinate_grid.isChecked())
        if what == "smooth":
            return bool(self.viewer.menu_bar.action_smooth.isChecked())
        if what.startswith("contour"):
            return bool(self.viewer.menu_bar.action_contours.isChecked())
        if what == "iis":
            return bool(self.viewer.iis.running())
        if what.startswith("marker"):
            regions = getattr(frame, "regions", [])
            if what == "marker select":
                return any(getattr(region, "selected", False) for region in regions)
            if what == "marker paste":
                return self.viewer.edit.clipboard() is not None
            if what == "marker undo":
                return self.viewer.undo.can_undo()
            return bool(regions)
        return False

    # -- zoom --------------------------------------------------------------

    @staticmethod
    def _zoom_value(word: str) -> float:
        """A zoom factor as DS9 writes it: `4`, `0.25` or `1/4`."""
        if "/" in word:
            numerator, denominator = word.split("/", 1)
            return float(numerator) / float(denominator)
        return float(word)

    def _zoom_text(self) -> str:
        """One zoom, or x and y when they differ, as DS9 answers."""
        zoom = self.viewer.image_viewer.get_zoom()
        getter = getattr(self.viewer.image_viewer, "get_aspect", None)
        aspect = float(getter()) if getter is not None else 1.0
        if abs(aspect - 1.0) > 1e-9:
            return f"{zoom:.6g} {zoom * aspect:.6g}"
        return f"{zoom:.6g}"

    def _read_zoom(self, args: list[str]) -> dict[str, Any]:
        """`xpaget ds9 zoom`: the current frame's zoom."""
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        return {"status": "ok", "result": self._zoom_text()}

    def _handle_zoom(self, params: dict[str, Any]) -> dict[str, Any]:
        """DS9's `zoom`.

        `zoom <value>` and `zoom to <value>` set the zoom absolutely, two
        values zoom x and y apart, `zoom to fit` fits, `zoom in` and `zoom
        out` step, `zoom open|close` shows the Pan Zoom Rotate window.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        words = [str(word).lower() for word in self._args(params)]
        if not words and params.get("level") is not None:
            words = [str(params["level"])]
        elif not words and params.get("action") is not None:
            words = [str(params["action"]).lower()]
        if words and words[0] == "to":
            words = words[1:]
        zoom = self.viewer.zoom

        if not words or words[0] in ("get",):
            return {"status": "ok", "result": self._zoom_text()}
        if words[0] in ("fit", "tofit"):
            zoom.zoom_fit()
        elif words[0] in ("in", "incr"):
            zoom.zoom_in()
        elif words[0] in ("out", "decr"):
            zoom.zoom_out()
        elif words[0] == "open":
            zoom.show_pan_zoom_rotate_dialog()
        elif words[0] == "close":
            self._close_window("PanZoomRotateDialog")
        else:
            try:
                values = [self._zoom_value(word) for word in words[:2]]
            except (ValueError, ZeroDivisionError):
                return {"status": "error", "message": f"{' '.join(words)} is not a zoom"}
            if min(values) <= 0:
                return {"status": "error", "message": "a zoom has to be positive"}
            if len(values) == 2 and abs(values[0] - values[1]) > 1e-9:
                # DS9's `zoom 2 4`: x and y apart.
                zoom.set_zoom(values[0], values[1])
            else:
                zoom.set_zoom(values[0])
        return {"status": "ok", "result": self._zoom_text()}

    def _close_window(self, name: str) -> None:
        """Close a tool window opened through `Controller.show_window`."""
        held = getattr(self.viewer, "_open_windows", {}) or {}
        dialog = held.get(name)
        if dialog is None:
            return
        try:
            dialog.close()
        except RuntimeError:
            # Already destroyed on the C++ side.
            pass

    # -- pan ---------------------------------------------------------------

    def _read_pan(self, args: list[str]) -> dict[str, Any]:
        """`xpaget ds9 pan [<coordsys> [<skyframe>] [<skyformat>]]`."""
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        place = self.viewer.zoom.pan_position()
        if place is None:
            return {"status": "ok", "result": "0 0"}
        _values, system, sky, sky_format = positions.split_spec(args)
        frame = self.viewer.frame_manager.current_frame
        return {"status": "ok", "result": positions.from_image(frame, *place, system, sky, sky_format)}

    def _handle_pan(self, params: dict[str, Any]) -> dict[str, Any]:
        """DS9's `pan`: `pan <x> <y> <coordsys> [<sky>]` moves by that much,
        `pan to <x> <y> <coordsys> [<sky>]` moves to there.

        A relative pan in a sky system is an offset in that system's
        units -- degrees, or the sexagesimal it is written in -- applied
        at the current centre, as DS9 applies it.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        words = [str(word) for word in self._args(params)]
        if not words and params.get("x") is not None and params.get("y") is not None:
            words = ["to", str(params["x"]), str(params["y"]), "image"]
        if not words:
            return self._read_pan([])
        lowered = words[0].lower()
        if lowered == "open":
            self.viewer.zoom.show_pan_zoom_rotate_dialog()
            return {"status": "ok"}
        if lowered == "close":
            self._close_window("PanZoomRotateDialog")
            return {"status": "ok"}

        absolute = lowered == "to"
        if absolute:
            words = words[1:]
        values, system, sky, _format = positions.split_spec(words)
        if len(values) < 2:
            return {"status": "error", "message": "pan takes an x and a y"}
        frame = self.viewer.frame_manager.current_frame
        place = self.viewer.zoom.pan_position()
        if frame is None or place is None:
            return {"status": "error", "message": "there is no image to pan"}

        try:
            if absolute:
                x, y = positions.to_image(frame, values[0], values[1], system, sky)
            elif system == "image":
                x, y = place[0] + float(values[0]), place[1] + float(values[1])
            elif system in ("physical", "amplifier", "detector"):
                transform = positions._physical(frame)
                px, py = transform.image_to_physical(*place)
                x, y = transform.physical_to_image(px + float(values[0]), py + float(values[1]))
            else:
                here = positions.from_image(frame, *place, system, sky, "degrees").split()
                x, y = positions.to_image(
                    frame,
                    str(float(here[0]) + float(values[0])),
                    str(float(here[1]) + float(values[1])),
                    system,
                    sky,
                )
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        self.viewer.zoom.pan_to_image(x, y)
        return {"status": "ok"}

    @staticmethod
    def _is_number(value: Any) -> bool:
        """Whether a word is a number, so a limit is not mistaken for a name."""
        try:
            float(value)
        except (TypeError, ValueError):
            return False
        return True

    #: Our algorithms by the names DS9's `scale` reads and writes.
    _SCALE_NAMES = {
        ScaleAlgorithm.LINEAR: "linear",
        ScaleAlgorithm.LOG: "log",
        ScaleAlgorithm.POWER: "pow",
        ScaleAlgorithm.SQRT: "sqrt",
        ScaleAlgorithm.SQUARED: "squared",
        ScaleAlgorithm.ASINH: "asinh",
        ScaleAlgorithm.SINH: "sinh",
        ScaleAlgorithm.HISTOGRAM_EQUALIZATION: "histequ",
    }

    def _scale_name(self) -> str:
        current = self.viewer.current_scale
        return self._SCALE_NAMES.get(current, current.name.lower())

    def _read_scale(self, args: list[str]) -> dict[str, Any]:
        """`xpaget ds9 scale [log exp|datasec|limits|mode|scope|lock [limits]]`."""
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        words = [word.lower() for word in args]
        scale = self.viewer.scale
        settings = scale.settings
        what = words[0] if words else ""
        if what == "":
            answer = self._scale_name()
        elif what == "log":
            answer = f"{settings.log_exponent:g}"
        elif what == "datasec":
            answer = access_points.on_off(settings.use_datasec)
        elif what == "limits":
            low, high = scale.current_limits()
            answer = f"{low:.8g} {high:.8g}"
        elif what == "mode":
            answer = scale.mode_key(settings)
        elif what == "scope":
            answer = settings.scope.value
        elif what == "lock":
            flag = "scale_limits" if words[1:2] == ["limits"] else "scale"
            answer = access_points.on_off(self.viewer.frame_controller.is_locked(flag))
        else:
            return {"status": "error", "message": f"scale has no {what}"}
        return {"status": "ok", "result": answer}

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
            "squared": ScaleAlgorithm.SQUARED,
            "pow": ScaleAlgorithm.POWER,
            "power": ScaleAlgorithm.POWER,
            "sinh": ScaleAlgorithm.SINH,
            "asinh": ScaleAlgorithm.ASINH,
            "histeq": ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
            "histequ": ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
            "histogram": ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
            "histogramequalization": ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
        }

        # DS9's other `scale` rules, which are not algorithms. Named here
        # so that a word which is neither an algorithm nor one of these can
        # be *refused*: `scale sideways` used to be accepted and quietly
        # leave the scale linear, which is the worst kind of reply.
        others = {
            "zscale",
            "zmax",
            "minmax",
            "mode",
            "limits",
            "scope",
            "datasec",
            "exp",
            "match",
            "lock",
            "open",
            "close",
            "user",
            "get",
        }
        if (
            mode is not None
            and str(mode).lower() not in mode_map
            and str(mode).lower() not in others
            and not self._is_number(mode)
        ):
            return {
                "status": "error",
                "message": f"{mode} is not a scale; try {', '.join(sorted(mode_map))}",
            }

        words = [str(word) for word in args]
        rest = words[1:]

        # DS9's sub-rules. These used to fall through to the return below,
        # which answered `ok` and the current scale while changing nothing.
        if mode == "mode":
            if not rest:
                return {"status": "error", "message": "scale mode takes a limit mode"}
            self.viewer.scale.set_limit_mode(rest[0].lower())
            return {"status": "ok", "result": self.viewer.scale.mode_key(self.viewer.scale.settings)}
        if mode == "limits":
            if len(rest) < 2 or not all(self._is_number(word) for word in rest[:2]):
                return {"status": "error", "message": "scale limits takes a low and a high"}
            self.viewer.scale.set_user_limits(float(rest[0]), float(rest[1]))
            return {"status": "ok"}
        if mode == "scope":
            if not rest:
                return {"status": "error", "message": "scale scope takes local or global"}
            self.viewer.scale.set_scope(rest[0].lower())
            return {"status": "ok"}
        if mode == "datasec":
            wanted = self._as_bool(rest[0]) if rest else None
            if wanted is None:
                return {"status": "error", "message": "scale datasec takes yes or no"}
            self.viewer.scale.set_use_datasec(wanted)
            return {"status": "ok"}
        if mode in ("log", "exp") and rest and self._is_number(rest[-1]):
            # `scale log exp 100`: the log scale and its exponent at once.
            self.viewer.scale.set_scale(ScaleAlgorithm.LOG)
            self.viewer.scale.set_log_exponent(float(rest[-1]))
            return {"status": "ok", "result": self._scale_name()}
        if mode in ("match", "lock"):
            # `scale match`, `scale match limits`, `scale lock [yes|no]`,
            # `scale lock limits [yes|no]`: the scale and the limits are
            # two separate locks, as they are on Frame -> Lock.
            limits_too = bool(rest) and rest[0].lower() == "limits"
            flag = "scale_limits" if limits_too else "scale"
            controller = self.viewer.frame_controller
            if mode == "match":
                (controller.match_scale_limits if limits_too else controller.match_scale)()
                return {"status": "ok"}
            values = rest[1:] if limits_too else rest
            wanted = self._as_bool(values[0]) if values else True
            if wanted is None:
                return {"status": "error", "message": f"{values[0]} is not yes or no"}
            controller.set_lock_flag(flag, wanted)
            return {"status": "ok"}
        if mode == "open":
            self.viewer.scale.show_dialog()
            return {"status": "ok"}
        if mode == "close":
            self._close_window("ScaleDialog")
            return {"status": "ok"}

        if mode in {"zscale"}:
            self.viewer.scale.reset_limits()
        elif mode in {"zmax", "user"}:
            self.viewer.scale.set_limit_mode(str(mode))
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

        return {"status": "ok", "result": self._scale_name()}

    # -- cmap --------------------------------------------------------------

    def _read_cmap(self, args: list[str]) -> dict[str, Any]:
        """`xpaget ds9 cmap [file|invert|value]`."""
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        what = args[0].lower() if args else ""
        if what == "invert":
            return {"status": "ok", "result": access_points.on_off(self.viewer.invert_colormap)}
        if what == "value":
            contrast, bias = self.viewer.color.contrast_bias()
            return {"status": "ok", "result": f"{contrast:.6g} {bias:.6g}"}
        if what == "file":
            return {"status": "ok", "result": f"{self.viewer.current_colormap}.lut"}
        if what in ("lock", "match"):
            locked = self.viewer.frame_controller.is_locked("colorbar")
            return {"status": "ok", "result": access_points.on_off(locked)}
        return {"status": "ok", "result": self.viewer.current_colormap}

    def _handle_cmap(self, params: dict[str, Any]) -> dict[str, Any]:
        """DS9's `cmap`: a colormap by name, `load`, `save`, `invert`, a
        contrast and bias, `tag load|save|delete`, `match`, `lock` and
        `open|close`."""
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        words = [str(word) for word in self._args(params)]
        if not words and params.get("name") is not None:
            words = [str(params["name"])]
        if not words:
            return self._read_cmap([])
        color = self.viewer.color
        verb = words[0].lower()
        rest = words[1:]

        def done(problem: str | None = None) -> dict[str, Any]:
            if problem:
                return {"status": "error", "message": problem}
            return {"status": "ok", "result": self.viewer.current_colormap}

        if verb == "load":
            return done(color.load_user_colormap(rest[0]) if rest else "cmap load takes a file")
        if verb == "save":
            return done(color.save_current_colormap(rest[0]) if rest else "cmap save takes a file")
        if verb == "invert":
            wanted = self._as_bool(rest[0]) if rest else True
            if wanted is None:
                return done(f"{rest[0]} is not yes or no")
            color.set_inverted(wanted)
            return done()
        if verb == "value" or (self._is_number(verb) and rest and self._is_number(rest[0])):
            numbers = rest if verb == "value" else words
            if len(numbers) < 2 or not all(self._is_number(word) for word in numbers[:2]):
                return done("cmap value takes a contrast and a bias")
            contrast, bias = float(numbers[0]), float(numbers[1])
            if not 0 <= contrast <= 10 or not 0 <= bias <= 1:
                return done("contrast runs from 0 to 10 and bias from 0 to 1")
            color.set_contrast_bias(contrast, bias)
            return done()
        if verb == "tag":
            what = rest[0].lower() if rest else ""
            if what == "load":
                return done(color.load_tags(rest[1]) if len(rest) > 1 else "cmap tag load takes a file")
            if what == "save":
                return done(color.save_tags(rest[1]) if len(rest) > 1 else "cmap tag save takes a file")
            if what in ("delete", "clear"):
                color.delete_tags()
                return done()
            return done("cmap tag takes load, save or delete")
        if verb == "match":
            self.viewer.frame_controller.match_colorbar()
            return done()
        if verb == "lock":
            wanted = self._as_bool(rest[0]) if rest else True
            self.viewer.frame_controller.set_lock_flag("colorbar", bool(wanted))
            return done()
        if verb == "open":
            color.show_dialog()
            return done()
        if verb == "close":
            self._close_window("ColormapDialog")
            return done()

        selected = color.normalize_name(words[0])
        if selected not in set(color.available_colormaps()):
            return done(f"Unsupported colormap: {words[0]}")
        color.set_colormap(selected)
        return done()

    # -- colorbar ----------------------------------------------------------

    def _colorbar_values(self) -> dict[str, str]:
        """Every setting `xpaget ds9 colorbar <name>` can ask for."""
        bar = self.viewer.colorbar_widget
        state = getattr(self.viewer, "view_state", None)
        locked = self.viewer.frame_controller.is_locked("colorbar") if hasattr(
            self.viewer.frame_controller, "is_locked"
        ) else False
        return {
            "": access_points.on_off(state.colorbar if state is not None else True),
            "orientation": getattr(bar, "orientation", "horizontal"),
            "numerics": access_points.on_off(getattr(bar, "show_numerics", True)),
            "space": getattr(bar, "spacing_mode", "value"),
            "font": getattr(bar, "label_font_family", "helvetica"),
            "fontsize": str(getattr(bar, "label_font_size", 9)),
            "fontweight": getattr(bar, "label_font_weight", "normal"),
            "fontslant": getattr(bar, "label_font_slant", "roman"),
            "size": str(getattr(bar, "bar_size", 20)),
            "ticks": str(getattr(bar, "tick_count", 11)),
            "lock": access_points.on_off(locked),
        }

    def _read_colorbar(self, args: list[str]) -> dict[str, Any]:
        """`xpaget ds9 colorbar [<setting>]`."""
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        what = args[0].lower() if args else ""
        values = self._colorbar_values()
        if what not in values:
            return {"status": "error", "message": f"colorbar has no {what}"}
        return {"status": "ok", "result": values[what]}

    def _handle_colorbar(self, params: dict[str, Any]) -> dict[str, Any]:
        """DS9's `colorbar`: shown or not, orientation, numerics, spacing,
        font, size, ticks, `match` and `lock`."""
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        words = [str(word).lower() for word in self._args(params)]
        if not words:
            # The application's own callers pass keywords, several at once;
            # each is the DS9 command of the same name.
            keyed = []
            for key in ("visible", "orientation", "numerics", "spacing", "ticks", "size"):
                value = params.get(key)
                if value is None:
                    continue
                text = access_points.on_off(value) if isinstance(value, bool) else str(value).lower()
                name = {"visible": None, "spacing": "space"}.get(key, key)
                keyed.append(([name] if name else []) + [text])
            if not keyed:
                return self._read_colorbar([])
            reply: dict[str, Any] = {"status": "ok"}
            for command in keyed:
                reply = self._handle_colorbar({"args": command})
                if reply.get("status") != "ok":
                    return reply
            return reply

        color = self.viewer.color
        bar = self.viewer.colorbar_widget
        verb, rest = words[0], words[1:]
        value = rest[0] if rest else ""

        def done(problem: str | None = None) -> dict[str, Any]:
            if problem:
                return {"status": "error", "message": problem}
            return {"status": "ok", "result": self._colorbar_values()[""]}

        shown = self._as_bool(verb)
        if shown is not None:
            color.set_colorbar_visible(shown)
            return done()
        if verb in ("horizontal", "vertical"):
            color.set_colorbar_orientation(verb)
            return done()
        if verb == "orientation":
            if value not in ("horizontal", "vertical"):
                return done("orientation is horizontal or vertical")
            color.set_colorbar_orientation(value)
            return done()
        if verb == "numerics":
            wanted = self._as_bool(value) if value else True
            if wanted is None:
                return done(f"{value} is not yes or no")
            color.set_colorbar_numerics(wanted)
            return done()
        if verb in ("space", "spacing"):
            if value not in ("value", "distance"):
                return done("space is value or distance")
            color.set_colorbar_spacing(value)
            return done()
        if verb == "font":
            if value not in bar.FONT_FAMILIES:
                return done("font is times, helvetica or courier")
            bar.set_label_font(family=value)
            return done()
        if verb == "fontweight":
            if value not in ("normal", "bold"):
                return done("fontweight is normal or bold")
            bar.set_label_font(weight=value)
            return done()
        if verb == "fontslant":
            if value not in ("roman", "italic"):
                return done("fontslant is roman or italic")
            bar.set_label_font(slant=value)
            return done()
        if verb in ("fontsize", "size", "ticks"):
            if not value.isdigit():
                return done(f"colorbar {verb} takes a whole number")
            if verb == "fontsize":
                color.set_colorbar_font_size(int(value))
            elif verb == "size":
                bar.set_bar_size(int(value))
            else:
                bar.set_tick_count(int(value))
            return done()
        if verb == "match":
            self.viewer.frame_controller.match_colorbar()
            return done()
        if verb == "lock":
            wanted = self._as_bool(value) if value else True
            self.viewer.frame_controller.set_lock_flag("colorbar", bool(wanted))
            return done()
        return done(f"colorbar has no {verb}")

    def _handle_wcs(self, params: dict[str, Any]) -> dict[str, Any]:
        """`xpaset ds9 wcs ...`: DS9's whole `wcs` grammar.

        `[[system] wcs|wcsa..wcsz] [[sky] fk4|fk5|icrs|galactic|ecliptic]
        [[skyformat] degrees|sexagesimal] [align yes|no] [reset]
        [load <file>] [replace [<int>] [<file>]] [append [<int>] [<file>]]
        [save [<int>] <file>] [open|close]`

        The grammar lives in `WCSController.command`, which the `-wcs`
        command-line option runs too, so the two cannot read it differently.
        `replace` and `append` with no file read what `xpaset` sent on its
        standard input.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error

        words = [str(word) for word in self._args(params)]
        if not words and params.get("system"):
            # The keyword form callers inside the application used to use.
            words = [str(params["system"])]
        data = params.get("data")
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        problem = self.viewer.wcs.command(words, data=data or None)
        if problem:
            return {"status": "error", "message": problem}
        return {"status": "ok", "result": self.viewer.wcs.report([])}

    def _read_wcs(self, args: list[str]) -> dict[str, Any]:
        """`xpaget ds9 wcs [system|sky|skyformat|align]`.

        A bare `wcs` answers with the system, as DS9's `wcssendparser.tac`
        does: `wcs`, or `wcsa`..`wcsz`.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        try:
            return {"status": "ok", "result": self.viewer.wcs.report(args)}
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}

    #: What `save` calls each of the `Save as` writers.
    _SAVE_WRITERS = {
        "fits": "image",
        "rgbimage": "rgb_image",
        "rgbcube": "rgb_cube",
        "hsvimage": "hsv_image",
        "hsvcube": "hsv_cube",
        "hlsimage": "hls_image",
        "hlscube": "hls_cube",
        "mecube": "mef_cube",
        "mosaic": "image",
        "mosaicimage": "image",
    }

    def _handle_save(self, params: dict[str, Any]) -> dict[str, Any]:
        """DS9's `save [fits|rgbimage|rgbcube|mecube|mosaic|mosaicimage]
        <filename> [image|table|slice]`: the frame's data, as FITS.

        This is not `saveimage`, which writes the rendered picture; `save`
        writes the data, which is what a script calling it wants back.
        """
        viewer_error = self._require_viewer()
        if viewer_error:
            return viewer_error
        words = [str(word) for word in self._args(params)]
        if params.get("path") is not None:
            words = [*([str(params["format"])] if params.get("format") else []), str(params["path"])]
        writer = "image"
        if words and words[0].lower() in self._SAVE_WRITERS:
            writer = self._SAVE_WRITERS[words.pop(0).lower()]
        # The trailing `image|table|slice` chooses what of a binned table
        # or cube is written; the frame holds the image and the slice
        # already, so it is accepted and has nothing more to choose.
        if words and words[-1].lower() in ("image", "table", "slice") and len(words) > 1:
            words.pop()
        if not words:
            return {"status": "error", "message": "No save path specified"}
        path = words[0]
        file_controller = self.viewer.file
        frame = self.viewer.frame_manager.current_frame
        if frame is None or frame.image_data is None:
            return {"status": "error", "message": "nothing to save; the frame is empty"}
        try:
            file_controller._write_as(Path(path), writer, frame)
        except Exception as exc:
            return {"status": "error", "message": f"could not write {path}: {exc}"}
        return {"status": "ok", "result": path}

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
