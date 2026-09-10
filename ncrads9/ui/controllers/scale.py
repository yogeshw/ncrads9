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

DS9 splits this menu in two. The top is the transfer function -- how data is
stretched between two values -- and the rest is where those two values come
from: a mode, a min/max method, a scope, Use DATASEC, and the ZScale
parameters. `rendering/scale_algorithms.py` holds the first,
`rendering/scale_limits.py` the second, and this controller wires both to the
menu and to the dialogs.

The limit settings live on the window rather than per frame. DS9 keeps them
per frame with `Frame -> Lock -> Scale` to tie frames together; NCRADS9 keeps
one set and caches the *computed* limits per frame in `frame.z1`/`frame.z2`,
so switching frames still restores what you saw. Making the settings
per-frame is a Lock/Match question and belongs with M9's remaining lock work.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtWidgets import QInputDialog

from ...frames.crop import blank_outside
from ...frames.frame import Frame
from ...rendering.scale_algorithms import ScaleAlgorithm
from ...rendering.scale_limits import (
    LimitMode,
    LimitScope,
    MinMaxMethod,
    ScaleLimits,
    compute_limits,
)
from ..dialogs.scale_dialog import ScaleDialog
from .base import Controller

#: Menu action suffix -> algorithm, for connecting and for checkmarks.
SCALE_ACTIONS: dict[str, ScaleAlgorithm] = {
    "linear": ScaleAlgorithm.LINEAR,
    "log": ScaleAlgorithm.LOG,
    "power": ScaleAlgorithm.POWER,
    "sqrt": ScaleAlgorithm.SQRT,
    "squared": ScaleAlgorithm.SQUARED,
    "asinh": ScaleAlgorithm.ASINH,
    "sinh": ScaleAlgorithm.SINH,
    "histeq": ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
}

#: Algorithm -> the label the button bar uses.
BUTTON_LABELS: dict[ScaleAlgorithm, str] = {
    ScaleAlgorithm.LINEAR: "linear",
    ScaleAlgorithm.LOG: "log",
    ScaleAlgorithm.POWER: "power",
    ScaleAlgorithm.SQRT: "sqrt",
    ScaleAlgorithm.SQUARED: "squared",
    ScaleAlgorithm.ASINH: "asinh",
    ScaleAlgorithm.SINH: "sinh",
    ScaleAlgorithm.HISTOGRAM_EQUALIZATION: "hist",
}

#: Scale-dialog name -> algorithm. The dialog spells them out in full.
DIALOG_SCALES: dict[str, ScaleAlgorithm] = {
    "Linear": ScaleAlgorithm.LINEAR,
    "Log": ScaleAlgorithm.LOG,
    "Power": ScaleAlgorithm.POWER,
    "Sqrt": ScaleAlgorithm.SQRT,
    "Squared": ScaleAlgorithm.SQUARED,
    "Asinh": ScaleAlgorithm.ASINH,
    "Sinh": ScaleAlgorithm.SINH,
    "Histogram Equalization": ScaleAlgorithm.HISTOGRAM_EQUALIZATION,
}

#: Limit-menu name -> the mode it selects. A percentile preset is keyed by
#: its own figure, and `set_limit_mode` reads the number out of the key.
LIMIT_MODES: dict[str, LimitMode] = {
    "minmax": LimitMode.MINMAX,
    "zscale": LimitMode.ZSCALE,
    "zmax": LimitMode.ZMAX,
    "user": LimitMode.USER,
}

#: The bounds the parameter prompts accept.
MIN_SAMPLE_INCREMENT, MAX_SAMPLE_INCREMENT = 1, 1000
MIN_ZSCALE_SAMPLES, MAX_ZSCALE_SAMPLES = 10, 100_000
MIN_CONTRAST, MAX_CONTRAST = 0.001, 10.0
MIN_EXPONENT, MAX_EXPONENT = 1.001, 1_000_000.0

#: Decimal places the numeric prompts offer.
PROMPT_DECIMALS = 4


class ScaleController(Controller):
    """Owns the Scale menu."""

    def connect(self) -> None:
        """Wire the Scale menu."""
        menu = self.menu

        for suffix, algorithm in SCALE_ACTIONS.items():
            action = menu.scale_function_actions[suffix]
            action.triggered.connect(lambda _checked=False, a=algorithm: self.set_scale(a))

        for exponent, action in menu.log_exponent_actions.items():
            action.triggered.connect(lambda _checked=False, e=exponent: self.set_log_exponent(e))
        menu.action_log_exponent_other.triggered.connect(self.ask_log_exponent)

        for name, action in menu.scale_limit_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.set_limit_mode(key))
        menu.action_scale_user_limits.triggered.connect(self.ask_user_limits)

        for name, action in menu.scale_scope_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.set_scope(key))

        for name, action in menu.minmax_method_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.set_minmax_method(key))
        menu.action_sample_parameters.triggered.connect(self.ask_sample_increment)

        menu.action_use_datasec.toggled.connect(self.set_use_datasec)
        menu.action_zscale_parameters.triggered.connect(self.ask_zscale_parameters)
        menu.action_scale_params.triggered.connect(self.show_dialog)

    def sync(self) -> None:
        """Tick every Scale entry to match the current settings."""
        menu = self.menu
        current = self.window.current_scale
        for suffix, algorithm in SCALE_ACTIONS.items():
            menu.scale_function_actions[suffix].setChecked(algorithm == current)

        settings = self.settings
        for exponent, action in menu.log_exponent_actions.items():
            action.setChecked(exponent == settings.log_exponent)
        for name, action in menu.scale_limit_actions.items():
            action.setChecked(self.mode_key(settings) == name)
        for name, action in menu.scale_scope_actions.items():
            action.setChecked(settings.scope.value == name)
        for name, action in menu.minmax_method_actions.items():
            action.setChecked(settings.method.value == name)
        menu.action_use_datasec.setChecked(settings.use_datasec)

    @staticmethod
    def mode_key(settings: ScaleLimits) -> str:
        """The menu key one settings object corresponds to."""
        if settings.mode is LimitMode.PERCENT:
            return f"{settings.percent:g}"
        return settings.mode.value

    # -- transfer function ---------------------------------------------------

    def set_scale(self, scale: ScaleAlgorithm) -> None:
        """Set the image scaling algorithm.

        Args:
            scale: The scaling algorithm to use.
        """
        self.window.current_scale = scale
        self.window.frame_controller.persist_view_state()
        self.sync()

        if scale in BUTTON_LABELS:
            self.window.button_bar.set_scale(BUTTON_LABELS[scale])

        if self.window.image_data is not None:
            self.refresh()
            self.status(f"Scale: {scale.name.lower()}")

    def on_button_bar_scale(self, label: str) -> None:
        """Select an algorithm from a button-bar label."""
        wanted = label.strip().lower()
        for algorithm, text in BUTTON_LABELS.items():
            if text == wanted:
                self.set_scale(algorithm)
                return

    def set_log_exponent(self, exponent: float) -> None:
        """Set DS9's Log Exponent, which drives log and power alike.

        Args:
            exponent: The exponent. Values at or below one are refused, since
                the formulas divide by its logarithm.
        """
        if not MIN_EXPONENT <= float(exponent) <= MAX_EXPONENT:
            self.status(f"Log exponent must be between {MIN_EXPONENT} and {MAX_EXPONENT:g}", 3000)
            return
        self.update(log_exponent=float(exponent))
        self.status(f"Log exponent: {exponent:g}")

    def ask_log_exponent(self) -> None:
        """Prompt for a log exponent that is not one of the presets."""
        value, ok = QInputDialog.getDouble(
            self.window,
            "Log Exponent",
            "Exponent:",
            value=self.settings.log_exponent,
            min=MIN_EXPONENT,
            max=MAX_EXPONENT,
            decimals=PROMPT_DECIMALS,
        )
        if ok:
            self.set_log_exponent(value)

    # -- limit settings ------------------------------------------------------

    @property
    def settings(self) -> ScaleLimits:
        """The window's limit settings."""
        return self.window.scale_limits

    def update(self, **changes) -> None:
        """Replace one or more settings, then restretch and redisplay."""
        self.window.scale_limits = replace(self.window.scale_limits, **changes)
        self.sync()
        self.invalidate()

    def invalidate(self) -> None:
        """Recompute the limits from the current settings and redisplay.

        Computed here rather than left for the next display pass, so that
        choosing a mode immediately puts numbers on the frame -- which is
        what `Frame -> Match/Lock -> Scale and Limits` copies between frames,
        and what the information panel's Low High row reads.
        """
        data = self.window.image_data
        if data is None:
            self.window.z1 = None
            self.window.z2 = None
            self.store_limits(None, None)
            return

        low, high = self.compute_limits(data)
        self.window.z1, self.window.z2 = low, high
        self.store_limits(low, high)
        self.refresh()

    def set_limit_mode(self, key: str) -> None:
        """Select a limit mode from its menu key.

        Args:
            key: A key of `MenuBar.scale_limit_actions` -- one of
                `LIMIT_MODES`, or a percentile figure such as "99.5".
        """
        mode = LIMIT_MODES.get(key)
        if mode is not None:
            self.update(mode=mode)
            self.status(f"Limits: {self.settings.describe()}")
            return

        try:
            settings = self.settings.with_mode(LimitMode.PERCENT, float(key))
        except ValueError as exc:
            self.status(str(exc), 3000)
            return
        self.window.scale_limits = settings
        self.sync()
        self.invalidate()
        self.status(f"Limits: {settings.describe()}")

    def set_scope(self, scope: str) -> None:
        """Measure the limits over the slice on screen, or the whole extension.

        Args:
            scope: "local" or "global".
        """
        try:
            value = LimitScope(scope)
        except ValueError:
            self.status(f"Unknown scale scope: {scope}", 3000)
            return
        self.update(scope=value)
        self.status(f"Scale scope: {value.value}")

    def set_minmax_method(self, method: str) -> None:
        """Choose how the Min Max mode finds the extremes.

        Args:
            method: One of "scan", "sample", "datamin", "irafminmax".
        """
        try:
            value = MinMaxMethod(method)
        except ValueError:
            self.status(f"Unknown min/max method: {method}", 3000)
            return
        self.update(method=value)
        self.status(f"Min max method: {value.value}")

    def set_use_datasec(self, use: bool) -> None:
        """Restrict the limit measurement to the header's `DATASEC`."""
        self.update(use_datasec=bool(use))
        self.status(f"Use DATASEC: {'yes' if use else 'no'}")

    def set_user_limits(self, low: float, high: float) -> None:
        """Set the limits by hand, and switch to User mode.

        Args:
            low: The low limit.
            high: The high limit. Swapped with `low` if it is smaller.
        """
        low, high = float(low), float(high)
        if high < low:
            low, high = high, low
        self.update(mode=LimitMode.USER, user_low=low, user_high=high)
        self.status(f"Limits: {low:.6g} to {high:.6g}")

    def ask_user_limits(self) -> None:
        """Prompt for the two limits (DS9's `Scale -> Other`)."""
        settings = self.settings
        current = self.current_limits()
        low, ok = QInputDialog.getDouble(
            self.window,
            "Scale Limits",
            "Low:",
            value=settings.user_low if settings.mode is LimitMode.USER else current[0],
            decimals=PROMPT_DECIMALS,
        )
        if not ok:
            return
        high, ok = QInputDialog.getDouble(
            self.window,
            "Scale Limits",
            "High:",
            value=settings.user_high if settings.mode is LimitMode.USER else current[1],
            decimals=PROMPT_DECIMALS,
        )
        if ok:
            self.set_user_limits(low, high)

    def ask_sample_increment(self) -> None:
        """Prompt for the Sample method's increment."""
        value, ok = QInputDialog.getInt(
            self.window,
            "Sample Parameters",
            "Sample increment:",
            value=self.settings.sample_increment,
            min=MIN_SAMPLE_INCREMENT,
            max=MAX_SAMPLE_INCREMENT,
        )
        if ok:
            self.update(sample_increment=int(value))
            self.status(f"Sample increment: {value}")

    def ask_zscale_parameters(self) -> None:
        """Prompt for contrast, sample count and samples per line."""
        settings = self.settings
        contrast, ok = QInputDialog.getDouble(
            self.window,
            "ZScale Parameters",
            "Contrast:",
            value=settings.contrast,
            min=MIN_CONTRAST,
            max=MAX_CONTRAST,
            decimals=PROMPT_DECIMALS,
        )
        if not ok:
            return
        samples, ok = QInputDialog.getInt(
            self.window,
            "ZScale Parameters",
            "Number of samples:",
            value=settings.samples,
            min=MIN_ZSCALE_SAMPLES,
            max=MAX_ZSCALE_SAMPLES,
        )
        if not ok:
            return
        per_line, ok = QInputDialog.getInt(
            self.window,
            "ZScale Parameters",
            "Samples per line:",
            value=settings.samples_per_line,
            min=1,
            max=MAX_ZSCALE_SAMPLES,
        )
        if not ok:
            return
        self.update(
            contrast=float(contrast),
            samples=int(samples),
            samples_per_line=int(per_line),
        )
        self.status(f"ZScale: contrast {contrast:g}, {samples} samples")

    # -- computing the limits ------------------------------------------------

    def compute_limits(
        self,
        data: NDArray[np.floating] | None,
        frame: Frame | None = None,
    ) -> tuple[float, float]:
        """The clip limits for one array under the current settings.

        This is the single entry point the display pipeline uses, so every
        rendering path -- scalar, RGB channel and tile preview -- honours the
        mode, method, scope and DATASEC settings alike.

        Args:
            data: The array being displayed.
            frame: The frame it came from, for its header and, when the scope
                is Global, for the whole extension behind the displayed
                slice. Defaults to the current frame.

        Returns:
            (low, high).
        """
        frame = frame if frame is not None else self.frame
        header = getattr(frame, "header", None) if frame is not None else None
        whole = None
        if frame is not None and frame.image is not None:
            whole = frame.image.data
        crop = getattr(frame, "crop", None) if frame is not None else None
        if crop is not None:
            # DS9's CROPSEC: a cropped frame measures the crop, not the whole
            # extension, so the stretch suits what is actually on screen.
            # Blanked pixels are not finite and drop out by themselves.
            # Data that has already been blocked has a different shape, and
            # was blanked on its way through the display pipeline anyway.
            reference = frame.image_data
            if data is not None and reference is not None and data.shape == reference.shape:
                data = blank_outside(data, crop)
            if whole is not None and whole.shape == getattr(reference, "shape", None):
                whole = blank_outside(whole, crop)
        return compute_limits(data, self.settings, header=header, global_data=whole)

    def current_limits(self) -> tuple[float, float]:
        """The limits in force now, computing them if they are not cached."""
        if self.window.z1 is not None and self.window.z2 is not None:
            return float(self.window.z1), float(self.window.z2)
        return self.compute_limits(self.window.image_data)

    def store_limits(self, z1: float | None, z2: float | None) -> None:
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
        """Recompute the limits from scratch and clear contrast and bias."""
        if self.window.image_data is None:
            return
        self.viewer.reset_contrast_brightness()
        self.invalidate()
        self.status(f"Limits reset: {self.settings.describe()}")

    def set_minmax_limits(self) -> None:
        """Switch to the Min Max mode. Kept for XPA and the button bar."""
        self.set_limit_mode("minmax")

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

        if params.get("auto_limits", True):
            self.window.scale_limits = replace(self.window.scale_limits, mode=LimitMode.MINMAX)
            self.window.z1 = None
            self.window.z2 = None
        else:
            low = params.get("min_value")
            high = params.get("max_value")
            if low is not None and high is not None:
                self.set_user_limits(low, high)

        # The dialog's contrast slider spans 0-2 with 1.0 neutral; its bias
        # slider spans the same range but means -1..+1 around zero.
        contrast = params.get("contrast", 1.0)
        brightness = params.get("bias", 1.0) - 1.0
        # Contrast and bias belong to the colour pipeline.
        self.window.color.set_contrast_brightness(contrast, brightness)

        self.sync()
        self.refresh()
        self.window.frame_controller.persist_view_state()
        self.status(
            f"Scale: {scale_name}, Contrast: {contrast:.2f}, Brightness: {brightness:.2f}",
        )
