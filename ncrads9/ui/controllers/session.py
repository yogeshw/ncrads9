# NCRADS9 - NCRA DS9-like FITS Viewer
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
File -> Backup and Restore, and the automatic backup behind them.

What is captured is everything the session would be poorer for losing: each
frame's file and extension, its view, its scale and colours, its regions,
its crop and crosshair, the contour and grid settings, the colour tags, and
the illustrate layer. What is deliberately *not* captured is anything that
can be worked out again from those -- the rendered pixmap, the scale limits
of a frame whose mode computes them, the panner's view rectangle.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ...frames.crop import CropRegion
from ...grid.grid_config import GridConfig
from ...illustrate import illustrate_file
from ...io.session import autosave, backup
from ...regions.region_parser import RegionParser
from ...regions.region_writer import RegionWriter
from ...rendering.scale_algorithms import ScaleAlgorithm
from .base import Controller

#: The frame fields that are plain values and restore by being set back.
FRAME_FIELDS: tuple[str, ...] = (
    "block_factor",
    "colormap",
    "invert_colormap",
    "z1",
    "z2",
    "zoom",
    "pan_x",
    "pan_y",
    "rotation",
    "flip_x",
    "flip_y",
    "align_wcs",
    "contrast",
    "brightness",
    "slice_index",
    "axis_order",
    "hdu_index",
    "frame_type",
)


class SessionController(Controller):
    """Saves and restores whole sessions."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: The automatic backup's timer, started by `start_autosave`.
        self.timer: QTimer | None = None
        #: What went wrong during the last restore -- a file that has moved,
        #: a region file that no longer parses. Collected rather than
        #: reported one at a time, so the last thing said about a restore is
        #: not a message about its first frame.
        self.problems: list[str] = []

    def connect(self) -> None:
        """Wire File -> Backup and Restore."""
        self.menu.action_backup.triggered.connect(lambda _checked=False: self.backup())
        self.menu.action_restore.triggered.connect(lambda _checked=False: self.restore())

    # -- capturing -------------------------------------------------------------

    def capture(self) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
        """The session as plain data, plus the arrays that need a file.

        Returns:
            (state, arrays). A frame loaded from a file is captured as that
            file's specification; only a frame whose pixels came from
            somewhere else has them written out, which is what keeps a
            backup of a night's work small.
        """
        window = self.window
        arrays: dict[str, np.ndarray] = {}
        frames = []

        for frame in self.frames.frames:
            captured = self._capture_frame(frame)
            if frame.file_spec is None and frame.filepath is None and frame.image_data is not None:
                key = f"frame_{frame.frame_id}"
                arrays[key] = np.asarray(frame.image_data)
                captured["data"] = key
            frames.append(captured)

        state: dict[str, Any] = {
            "frames": frames,
            "current": self.frames.current_index,
            "active": sorted(window._active_frame_ids),
            "display_mode": window._frame_display_mode,
            "edit_mode": window.edit_mode,
            "scale_limits": _plain_dataclass(window.scale_limits),
            "grid": self.window.analysis.grid_config.to_dict(),
            "contours": window._contour_settings,
            "illustrate": illustrate_file.serialise(window.illustrate.layer.elements),
            "illustrate_visible": window.illustrate.layer.visible,
            "crosshair": {
                "enabled": window.crosshair.enabled,
                "color": window.crosshair.color,
                "size": window.crosshair.size,
                "locked": window.crosshair.locked,
            },
            "nan_color": window.nan_color,
        }
        return (state, arrays)

    def _capture_frame(self, frame) -> dict[str, Any]:
        """One frame as plain data."""
        captured: dict[str, Any] = {"frame_id": frame.frame_id}
        for name in FRAME_FIELDS:
            value = getattr(frame, name, None)
            captured[name] = value.value if isinstance(value, ScaleAlgorithm) else value
        captured["scale"] = frame.scale.value if frame.scale is not None else None
        captured["file_spec"] = frame.file_spec or (str(frame.filepath) if frame.filepath else None)
        captured["crop"] = list(frame.crop.corners[0] + frame.crop.corners[1]) if frame.crop else None
        captured["crop_z"] = list(frame.crop_z) if frame.crop_z else None
        captured["crosshair"] = list(frame.crosshair) if frame.crosshair else None
        captured["color_tags"] = frame.color_tags.to_text() if frame.color_tags is not None else None
        captured["regions"] = (
            RegionWriter(coordinate_system="image").to_string(frame.regions) if frame.regions else ""
        )
        return captured

    # -- restoring ---------------------------------------------------------------

    def apply(self, state: dict[str, Any], arrays: dict[str, np.ndarray]) -> int:
        """Put a captured session back.

        Args:
            state: What `capture` produced.
            arrays: Its arrays.

        Returns:
            How many frames were restored.
        """
        window = self.window
        captured = state.get("frames") or []
        self.problems = []

        self.window.frame_controller.delete_all()
        restored = 0
        for index, saved in enumerate(captured):
            if index > 0:
                self.window.frame_controller.new_frame()
            if self._apply_frame(saved, arrays):
                restored += 1

        window._frame_display_mode = state.get("display_mode", "single")
        for name in ("scale_limits",):
            values = state.get(name)
            if isinstance(values, dict):
                window.scale_limits = _dataclass_from(type(window.scale_limits), values)

        grid = state.get("grid")
        if isinstance(grid, dict):
            window.analysis.grid_config = GridConfig.from_dict(grid)
        contours = state.get("contours")
        if isinstance(contours, dict):
            window._contour_settings = contours

        window.illustrate.layer.clear()
        for element in illustrate_file.parse(str(state.get("illustrate") or "")):
            window.illustrate.layer.add(element)
        window.illustrate.set_visible(bool(state.get("illustrate_visible", True)))

        crosshair = state.get("crosshair") or {}
        window.crosshair.color = crosshair.get("color", window.crosshair.color)
        window.crosshair.size = int(crosshair.get("size", window.crosshair.size))
        window.crosshair.locked = bool(crosshair.get("locked", False))
        window.nan_color = str(state.get("nan_color", window.nan_color))

        wanted = int(state.get("current", 0))
        if 0 <= wanted < self.frames.num_frames:
            self.window.frame_controller.goto_index(wanted)
        if state.get("edit_mode"):
            window.edit.set_mode(str(state["edit_mode"]))

        window.crosshair.set_enabled(bool(crosshair.get("enabled", False)))
        window.display.display()
        return restored

    def _apply_frame(self, saved: dict[str, Any], arrays: dict[str, np.ndarray]) -> bool:
        """Put one frame back. Returns whether its data came back with it."""
        spec = saved.get("file_spec")
        key = saved.get("data")
        loaded = False

        if spec:
            path = Path(str(spec).split("[")[0])
            if path.exists():
                try:
                    self.window.display.load_fits(str(spec))
                    loaded = True
                except Exception as exc:
                    self.problems.append(f"could not reload {path.name}: {exc}")
            else:
                self.problems.append(f"{path.name} is no longer there")
        elif key and key in arrays:
            # Data with no file behind it: put the pixels straight on the
            # frame, which is what the loader would have left there.
            data = np.asarray(arrays[key])
            frame = self.frames.current_frame
            if frame is not None:
                frame.image_data = data
                frame.original_image_data = data
                self.window.z1 = None
                self.window.z2 = None
                loaded = True

        frame = self.frames.current_frame
        if frame is None:
            return loaded

        for name in FRAME_FIELDS:
            if name in saved and saved[name] is not None:
                setattr(frame, name, saved[name])
        if saved.get("scale"):
            frame.scale = ScaleAlgorithm(saved["scale"])
        corners = saved.get("crop")
        frame.crop = CropRegion(*corners) if corners else None
        frame.crop_z = tuple(saved["crop_z"]) if saved.get("crop_z") else None
        frame.crosshair = tuple(saved["crosshair"]) if saved.get("crosshair") else None

        tags = saved.get("color_tags")
        if tags:
            from ...colormaps.color_tags import ColorTagSet

            frame.color_tags = ColorTagSet.from_text(tags)

        text = saved.get("regions") or ""
        if text.strip():
            try:
                frame.regions = RegionParser().parse_string(text)
            except Exception as exc:
                self.problems.append(f"could not restore regions: {exc}")
        return loaded

    # -- the menu entries -----------------------------------------------------------

    def backup(self, path: str | None = None) -> bool:
        """DS9's File -> Backup: write the session to a file."""
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self.window, "Backup Session", "", backup.FILE_FILTER)
        if not path:
            return False
        state, arrays = self.capture()
        try:
            backup.save(path, state, arrays)
        except backup.BackupError as exc:
            self.status(f"Backup failed: {exc}", 4000)
            return False
        self.status(f"Session backed up to {Path(path).name}", 3000)
        return True

    def restore(self, path: str | None = None) -> bool:
        """DS9's File -> Restore: read a session back."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self.window, "Restore Session", "", backup.FILE_FILTER)
        if not path:
            return False
        try:
            state, arrays = backup.load(path)
        except backup.BackupError as exc:
            self.status(f"Restore failed: {exc}", 4000)
            return False

        restored = self.apply(state, arrays)
        message = f"Restored {restored} frame(s) from {Path(path).name}"
        if self.problems:
            message += f" -- {len(self.problems)} problem(s): {self.problems[0]}"
        self.status(message, 5000 if self.problems else 3000)
        return True

    # -- the automatic backup --------------------------------------------------------

    def enabled(self) -> bool:
        """Whether the automatic backup is on."""
        return bool(self.window.preferences.get("autosave", autosave.DEFAULT_ENABLED))

    def interval(self) -> int:
        """How often it is written, in milliseconds."""
        return autosave.interval_ms(
            self.window.preferences.get("autosave_interval", autosave.DEFAULT_INTERVAL_MINUTES)
        )

    def start_autosave(self) -> bool:
        """Start writing an automatic backup, if the preference allows it.

        Returns:
            Whether the timer was started.
        """
        self.stop_autosave()
        if not self.enabled():
            return False
        self.timer = QTimer(self.window)
        self.timer.timeout.connect(self.write_autosave)
        self.timer.start(self.interval())
        return True

    def stop_autosave(self) -> None:
        """Stop writing one."""
        if self.timer is not None:
            self.timer.stop()
            self.timer = None

    def write_autosave(self) -> bool:
        """Write the automatic backup now."""
        state, arrays = self.capture()
        try:
            backup.save(autosave.path(), state, arrays)
        except backup.BackupError:
            return False
        return True

    def offer_recovery(self, ask: bool = True) -> bool:
        """On startup, offer to restore what a crash left behind.

        DS9 deletes its automatic backup on a clean exit, so one still
        being there means the last run did not finish (`autosave.tcl`).

        Args:
            ask: Whether to ask. False restores it without asking, which is
                what a test wants.

        Returns:
            Whether a session was restored.
        """
        if not autosave.exists():
            return False
        if ask:
            answer = QMessageBox.question(
                self.window,
                "Auto Backup",
                "Found an automatic backup from a session that did not finish. Restore it?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                autosave.remove()
                return False

        restored = self.restore(str(autosave.path()))
        autosave.remove()
        return restored

    def clean_exit(self) -> None:
        """Remove the automatic backup, which is what a clean exit means."""
        self.stop_autosave()
        autosave.remove()


def _plain_dataclass(value) -> dict[str, Any]:
    """A dataclass of scalars and enums as plain data."""
    return {key: (item.value if hasattr(item, "value") else item) for key, item in asdict(value).items()}


def _dataclass_from(kind, values: dict[str, Any]):
    """A dataclass back from plain data, ignoring anything it does not have."""
    import dataclasses

    fields = {field.name: field for field in dataclasses.fields(kind)}
    arguments = {}
    for key, value in values.items():
        field = fields.get(key)
        if field is None:
            continue
        annotation = field.type
        if isinstance(annotation, str):
            # Enums are stored by value; the field's default says which type.
            default = field.default
            if hasattr(default, "value") and not isinstance(default, (int, float, str, bool)):
                arguments[key] = type(default)(value)
                continue
        arguments[key] = value
    return kind(**arguments)
