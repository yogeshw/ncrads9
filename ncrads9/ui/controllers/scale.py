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
The Scale menu: transfer function and clip limits.

M5 adds what DS9 has and this does not: the percentile clipping presets
(99.5% down to 90%), ZMax, scale scope, the min/max method, and the ZScale
parameters dialog.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import numpy as np

from ...rendering.scale_algorithms import ScaleAlgorithm
from ..dialogs.scale_dialog import ScaleDialog
from .base import Controller

#: Menu action suffix -> algorithm, for connecting and for checkmarks.
SCALE_ACTIONS: dict[str, ScaleAlgorithm] = {
    "linear": ScaleAlgorithm.LINEAR,
    "log": ScaleAlgorithm.LOG,
    "sqrt": ScaleAlgorithm.SQRT,
    "squared": ScaleAlgorithm.POWER,
    "asinh": ScaleAlgorithm.ASINH,
    "histeq": ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
}

#: Algorithm -> the label the button bar uses.
BUTTON_LABELS: dict[ScaleAlgorithm, str] = {
    ScaleAlgorithm.LINEAR: "Linear",
    ScaleAlgorithm.LOG: "Log",
    ScaleAlgorithm.SQRT: "Sqrt",
    ScaleAlgorithm.POWER: "Squared",
    ScaleAlgorithm.ASINH: "Asinh",
    ScaleAlgorithm.HISTOGRAM_EQUALIZATION: "HistEq",
}

#: Scale dialog name -> algorithm. Sinh has no distinct implementation yet, so
#: it maps to asinh; M5-1 adds the real one.
DIALOG_SCALES: dict[str, ScaleAlgorithm] = {
    "Linear": ScaleAlgorithm.LINEAR,
    "Log": ScaleAlgorithm.LOG,
    "Power": ScaleAlgorithm.POWER,
    "Sqrt": ScaleAlgorithm.SQRT,
    "Squared": ScaleAlgorithm.POWER,
    "Asinh": ScaleAlgorithm.ASINH,
    "Sinh": ScaleAlgorithm.ASINH,
    "Histogram Equalization": ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
}


class ScaleController(Controller):
    """Owns the Scale menu."""

    def connect(self) -> None:
        """Wire the Scale menu."""
        for suffix, algorithm in SCALE_ACTIONS.items():
            action = getattr(self.menu, f"action_scale_{suffix}")
            action.triggered.connect(lambda _checked=False, a=algorithm: self.set_scale(a))

        self.menu.action_scale_zscale.triggered.connect(self.reset_limits)
        self.menu.action_scale_minmax.triggered.connect(self.set_minmax_limits)
        self.menu.action_scale_params.triggered.connect(self.show_dialog)

    def sync(self) -> None:
        """Tick the menu entry matching the current algorithm."""
        current = self.window.current_scale
        for suffix, algorithm in SCALE_ACTIONS.items():
            getattr(self.menu, f"action_scale_{suffix}").setChecked(algorithm == current)

    # -- transfer function ---------------------------------------------------

    def set_scale(self, scale: ScaleAlgorithm) -> None:
        """Set the image scaling algorithm.

        Args:
            scale: The scaling algorithm to use.
        """
        self.window.current_scale = scale
        self.window._persist_frame_view_state()
        self.sync()

        if scale in BUTTON_LABELS:
            self.window.button_bar.set_scale(BUTTON_LABELS[scale])

        if self.window.image_data is not None:
            self.refresh()
            self.status(f"Scale: {scale.name}")

    # -- clip limits ---------------------------------------------------------

    def _store_limits(self, z1: float | None, z2: float | None) -> None:
        """Record clip limits on the current frame.

        An RGB frame keeps limits per channel, so the values land on whichever
        channel is being edited rather than on the frame as a whole.
        """
        frame = self.frame
        if frame is None:
            return
        if frame.frame_type == "rgb":
            channel = frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
            frame.rgb_channel_z1[channel] = z1
            frame.rgb_channel_z2[channel] = z2
        else:
            frame.z1 = z1
            frame.z2 = z2

    def reset_limits(self) -> None:
        """Reset scale limits to ZScale auto-computed values."""
        if self.window.image_data is None:
            return
        self.window.z1 = None
        self.window.z2 = None
        self._store_limits(None, None)
        self.viewer.reset_contrast_brightness()
        self.refresh()
        self.status("Reset to ZScale limits")

    def set_minmax_limits(self) -> None:
        """Set scale limits to the data min and max."""
        data = self.window.image_data
        if data is None:
            return
        self.window.z1 = float(np.nanmin(data))
        self.window.z2 = float(np.nanmax(data))
        self._store_limits(self.window.z1, self.window.z2)
        self.viewer.reset_contrast_brightness()
        self.refresh()
        self.status(f"MinMax: {self.window.z1:.4g} to {self.window.z2:.4g}")

    # -- parameters dialog ---------------------------------------------------

    def show_dialog(self) -> None:
        """Show the Scale Parameters dialog."""
        if self.window.image_data is None:
            self.status("No image loaded")
            return

        dialog = ScaleDialog(self.window)
        # Connect before showing, so the dialog's Apply button works.
        dialog.scale_changed.connect(self.apply_dialog_params)
        dialog.exec()

    def apply_dialog_params(self, params: dict) -> None:
        """Apply settings from the Scale Parameters dialog."""
        scale_name = params.get("scale_function", "Linear")
        if scale_name in DIALOG_SCALES:
            self.window.current_scale = DIALOG_SCALES[scale_name]

        if not params.get("auto_limits", True):
            self.window.z1 = params.get("min_value", self.window.z1)
            self.window.z2 = params.get("max_value", self.window.z2)

        # The dialog's contrast slider spans 0-2 with 1.0 neutral; its bias
        # slider spans the same range but means -1..+1 around zero.
        contrast = params.get("contrast", 1.0)
        brightness = params.get("bias", 1.0) - 1.0
        self.window._set_viewer_contrast_brightness(contrast, brightness)

        self.refresh()
        self.window._persist_frame_view_state()
        self.status(
            f"Scale: {scale_name}, Contrast: {contrast:.2f}, Brightness: {brightness:.2f}",
        )
