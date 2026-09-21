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
What a walk through all 803 menu items turned up.

Three faults, each covering several menu entries:

* six windows you are meant to read *while* looking at the image --
  Statistics, Histogram, Header, Reference Manual, Keyboard Shortcuts and
  Scale Parameters -- declared `NonModal` in their own constructors and
  were then shown with `exec()`, which makes a dialog modal whatever it
  asked for. The application froze behind each one.
* the same fault in the windows you *adjust* while looking at the image:
  Contour, Coordinate Grid, Smooth, Mask and Colormap Parameters, and
  Preferences. Each one applies its settings to the picture it is sitting
  on top of, and each was shown with `exec()` -- so Apply changed something
  the reader could not see and could not uncover until they closed the
  window.
* `Frame -> Lock` has eight flags and only `Block` was live. The other
  seven recorded the tick and never acted on it.
* `Frame -> Match -> Axes Order` was a stub, `Match -> Bin` promised a
  milestone that had already shipped, and `Frame -> HSV.../HLS...` said
  "not yet implemented" while sitting on a working dialog.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QDialog, QRadioButton

from ncrads9.rendering.scale_algorithms import ScaleAlgorithm

SIZE = 64


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    real_get = Preferences.get
    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else real_get(self, key, default),
    )
    rows, columns = np.indices((SIZE, SIZE))
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32)).writeto(path)

    made = MainWindow()
    made._rebuild_image_viewer(False)
    made.display.load_fits(str(path))
    yield made
    made.close()


@pytest.fixture
def two_frames(window, tmp_path):
    """A second frame, so Match and Lock have something to act on."""
    second = tmp_path / "second.fits"
    rows, columns = np.indices((SIZE, SIZE))
    fits.PrimaryHDU(data=(rows + columns + 500).astype(np.float32)).writeto(second)
    window.frame_controller.new_frame()
    window.display.load_fits(str(second))
    assert len(window.frame_manager.frames) == 2
    return window


@pytest.fixture
def two_cubes(window, tmp_path):
    """Two frames holding data cubes, for the axis-order work."""
    planes = np.random.default_rng(0).normal(size=(5, 32, 32)).astype(np.float32)
    for index in range(2):
        path = tmp_path / f"cube{index}.fits"
        fits.PrimaryHDU(data=planes).writeto(path)
        if index:
            window.frame_controller.new_frame()
        window.display.load_fits(str(path))
    return window


# -- the six windows that froze the application ------------------------------------

#: Menu action -> the dialog it should put on screen, without blocking.
READING_WINDOWS = [
    ("action_statistics", "StatisticsDialog"),
    ("action_histogram", "HistogramDialog"),
    ("action_fits_header", "HeaderDialog"),
    ("action_help_contents", "HelpContentsDialog"),
    ("action_keyboard_shortcuts", "KeyboardShortcutsDialog"),
    ("action_scale_params", "ScaleDialog"),
]

#: The windows you *adjust* while looking at the image. Same rule, and the
#: same test: each applies to the picture behind it, so each has to leave
#: that picture usable.
PARAMETER_WINDOWS = [
    ("action_contour_params", "ContourDialog"),
    ("action_coordinate_grid_params", "GridDialog"),
    ("action_smooth_params", "SmoothDialog"),
    ("action_mask_params", "MaskDialog"),
    ("action_colormap_params", "ColormapDialog"),
    ("action_preferences", "PreferencesDialog"),
]


def _visible(qapp) -> dict[str, QDialog]:
    return {
        type(widget).__name__: widget
        for widget in qapp.topLevelWidgets()
        if isinstance(widget, QDialog) and widget.isVisible()
    }


@pytest.mark.parametrize(("action_name", "dialog_name"), READING_WINDOWS)
def test_a_reading_window_opens_beside_the_image(window, qapp, action_name, dialog_name):
    """The gate. If the menu item is still `exec()`-ing, this test hangs
    rather than fails -- which is itself the report, and is what triggering
    these items did to the application.
    """
    getattr(window.menu_bar, action_name).trigger()
    qapp.processEvents()

    shown = _visible(qapp)
    assert dialog_name in shown, f"{action_name} put nothing on screen"
    assert shown[dialog_name].windowModality() == Qt.WindowModality.NonModal
    shown[dialog_name].close()


@pytest.mark.parametrize(("action_name", "dialog_name"), PARAMETER_WINDOWS)
def test_a_parameters_window_leaves_the_image_usable(window, qapp, action_name, dialog_name):
    """Modeless, and a window in its own right.

    Shown with `exec()` these sat over the image they were changing and
    could not be pushed aside; every Apply went somewhere invisible. As
    with the reading windows, a regression hangs here rather than failing,
    which is the same report the user got.
    """
    getattr(window.menu_bar, action_name).trigger()
    qapp.processEvents()

    shown = _visible(qapp)
    assert dialog_name in shown, f"{action_name} put nothing on screen"
    dialog = shown[dialog_name]
    assert dialog.windowModality() == Qt.WindowModality.NonModal
    assert not dialog.isModal()
    # A title bar to take hold of, and the buttons to get it out of the way.
    flags = dialog.windowFlags()
    assert flags & Qt.WindowType.WindowTitleHint
    assert flags & Qt.WindowType.WindowMinMaxButtonsHint
    # Never pinned over the image: that was the other way of making a window
    # impossible to move aside.
    assert not (flags & Qt.WindowType.WindowStaysOnTopHint)
    dialog.close()


@pytest.mark.parametrize(("action_name", "dialog_name"), PARAMETER_WINDOWS)
def test_a_parameters_window_is_not_opened_twice(window, qapp, action_name, dialog_name):
    for _ in range(3):
        getattr(window.menu_bar, action_name).trigger()
        qapp.processEvents()
    count = sum(
        1 for widget in qapp.topLevelWidgets() if type(widget).__name__ == dialog_name and widget.isVisible()
    )
    assert count == 1
    _visible(qapp)[dialog_name].close()


def test_a_reading_window_is_not_opened_twice(window, qapp):
    """Opening the same one again raises what is already up. Without the
    reference kept alongside, a modeless dialog is collected the moment it
    is shown -- and without the check, five Statistics windows stack."""
    for _ in range(3):
        window.menu_bar.action_statistics.trigger()
        qapp.processEvents()
    count = sum(
        1
        for widget in qapp.topLevelWidgets()
        if type(widget).__name__ == "StatisticsDialog" and widget.isVisible()
    )
    assert count == 1
    _visible(qapp)["StatisticsDialog"].close()


def test_closing_a_reading_window_lets_it_be_opened_again(window, qapp):
    window.menu_bar.action_statistics.trigger()
    qapp.processEvents()
    _visible(qapp)["StatisticsDialog"].close()
    qapp.processEvents()

    window.menu_bar.action_statistics.trigger()
    qapp.processEvents()
    assert "StatisticsDialog" in _visible(qapp)
    _visible(qapp)["StatisticsDialog"].close()


def test_no_dialog_that_asks_to_be_modeless_is_shown_modally():
    """The rule behind the fix, checked against the source.

    A dialog that sets `NonModal` in its own constructor and is then
    shown with `exec()` is modal anyway -- `exec()` wins. Eight of them
    were, so the application froze behind windows that had explicitly
    asked not to freeze it. This is cheaper and broader than opening
    every one: it reads the code.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[2] / "ncrads9" / "ui"
    modeless = set()
    for path in (root / "dialogs").glob("*.py"):
        text = path.read_text()
        # Either spelling: the flag set by hand, or `make_modeless`, which
        # is the same thing plus the window flags. A dialog that switched to
        # the helper must not drop out of this guard.
        if "NonModal" in text or "make_modeless(" in text:
            modeless.update(re.findall(r"class (\w+)\(Q\w+\)", text))
    assert modeless, "the dialogs should declare their modality"

    offenders = []
    for path in (root / "controllers").glob("*.py"):
        text = path.read_text()
        for name in modeless:
            for match in re.finditer(rf"\b{name}\(", text):
                # The statement the construction begins: `exec()` inside it
                # is the contradiction.
                statement = text[match.end() : match.end() + 400].split("\n\n")[0]
                if ".exec()" in statement:
                    offenders.append(f"{path.name}: {name}")
    assert (
        sorted(set(offenders)) == []
    ), "these declare NonModal and are shown with exec(), which makes them modal"


# -- Frame -> Lock -----------------------------------------------------------------


def test_locking_the_scale_brings_the_frames_into_line(two_frames):
    window = two_frames
    window.frame_controller.set_lock_flag("scale", True)
    window.scale.set_scale(ScaleAlgorithm.LOG)
    assert {frame.scale for frame in window.frame_manager.frames} == {ScaleAlgorithm.LOG}


def test_locking_the_colorbar_brings_the_frames_into_line(two_frames):
    window = two_frames
    window.frame_controller.set_lock_flag("colorbar", True)
    window.color.set_colormap("heat")
    assert {frame.colormap for frame in window.frame_manager.frames} == {"heat"}


def test_locking_the_limits_brings_the_frames_into_line(two_frames):
    window = two_frames
    window.frame_controller.set_lock_flag("scale_limits", True)
    window.scale.set_limit_mode("minmax")
    limits = {(frame.z1, frame.z2) for frame in window.frame_manager.frames}
    assert len(limits) == 1, limits


def test_an_unlocked_setting_stays_on_its_own_frame(two_frames):
    """The other half of the claim: without the lock, a change must *not*
    spread. A propagation that ignored the flag would pass the tests above
    and be just as wrong."""
    window = two_frames
    window.frame_controller.set_lock_flag("colorbar", False)
    window.color.set_colormap("cool")
    assert len({frame.colormap for frame in window.frame_manager.frames}) == 2


def test_turning_a_lock_on_acts_at_once(two_frames):
    """DS9's locks take effect when ticked, not at the next change."""
    window = two_frames
    window.scale.set_scale(ScaleAlgorithm.SQRT)
    other = [f for f in window.frame_manager.frames if f is not window.frame_manager.current_frame]
    other[0].scale = ScaleAlgorithm.LINEAR

    window.frame_controller.set_lock_flag("scale", True)
    assert other[0].scale is ScaleAlgorithm.SQRT


def test_every_lock_flag_is_either_live_or_says_why(two_frames):
    """The gate for the seven dead ticks. A flag must move the other
    frames, or explain that there is nothing to move -- never tick
    silently and do nothing, which is what six of these did."""
    window = two_frames
    for flag in window._frame_lock_flags:
        window.status_bar.clearMessage()
        window.frame_controller.set_lock_flag(flag, True)
        assert window.status_bar.currentMessage(), f"{flag} ticked without saying anything"
        assert window.frame_controller.is_locked(flag) is True


def test_the_shared_settings_say_so_rather_than_pretending(two_frames):
    """Bin and Smooth are the window's settings, not the frame's, so every
    frame already matches. Said plainly -- and `Match -> Bin` used to
    promise the feature "arrives in M5-16", which had long since shipped."""
    window = two_frames
    window.frame_controller.match_bin()
    assert "shared by every frame" in window.status_bar.currentMessage()
    window.frame_controller.match_smooth()
    assert window.status_bar.currentMessage()


# -- Frame -> Match -> Axes Order --------------------------------------------------


def test_matching_the_axis_order_copies_it(two_cubes):
    window = two_cubes
    window.frame_controller.set_axis_order("321")
    orders = [frame.axis_order for frame in window.frame_manager.frames]
    assert len(set(orders)) == 2, "only the current frame should have changed"

    window.frame_controller.match_axes_order()
    assert {frame.axis_order for frame in window.frame_manager.frames} == {"321"}


def test_locking_the_axis_order_keeps_them_together(two_cubes):
    window = two_cubes
    window.frame_controller.set_lock_flag("axes_order", True)
    window.frame_controller.set_axis_order("213")
    assert {frame.axis_order for frame in window.frame_manager.frames} == {"213"}


def test_matching_the_axis_order_with_no_cube_says_so(two_frames):
    two_frames.frame_controller.match_axes_order()
    assert "no other frame holds a data cube" in two_frames.status_bar.currentMessage().lower()


def test_a_matched_slice_index_stays_inside_the_new_axis(window, tmp_path):
    """The axis a cube is sliced along changes length with the order, so a
    frame parked on a high slice has to be pulled back inside it."""
    planes = np.zeros((3, 40, 8), dtype=np.float32)
    for index in range(2):
        path = tmp_path / f"oblong{index}.fits"
        fits.PrimaryHDU(data=planes).writeto(path)
        if index:
            window.frame_controller.new_frame()
        window.display.load_fits(str(path))

    for frame in window.frame_manager.frames:
        frame.slice_index = 2
    window.frame_controller.set_axis_order("312")
    window.frame_controller.match_axes_order()
    for frame in window.frame_manager.frames:
        assert frame.slice_index >= 0


# -- Frame -> HSV... and HLS... ----------------------------------------------------


@pytest.mark.parametrize(
    ("frame_type", "labels"),
    [
        ("rgb", ["Red", "Green", "Blue"]),
        ("hsv", ["Hue", "Saturation", "Value"]),
        ("hls", ["Hue", "Lightness", "Saturation"]),
    ],
)
def test_each_colour_space_has_its_own_parameters_dialog(window, qapp, frame_type, labels):
    """HSV and HLS reported "not yet implemented" while the RGB dialog they
    could have shared sat next to them. The three planes are the same three
    slots; only the labels differ."""
    window.frame_controller.show_frame_dialog(frame_type)
    qapp.processEvents()

    dialogs = [
        widget
        for widget in qapp.topLevelWidgets()
        if isinstance(widget, QDialog) and widget.windowTitle() == frame_type.upper()
    ]
    assert dialogs, f"{frame_type} opened no dialog"
    dialog = dialogs[-1]
    try:
        assert window.frame_manager.current_frame.frame_type == frame_type
        assert [r.text() for r in dialog.findChildren(QRadioButton)][:3] == labels
        assert [c.text() for c in dialog.findChildren(QCheckBox)][:3] == labels
    finally:
        dialog.close()


def test_an_unknown_frame_dialog_is_reported(window):
    window.frame_controller.show_frame_dialog("wibble")
    assert "no WIBBLE parameters dialog" in window.status_bar.currentMessage()


def test_the_rgb_menu_entry_does_not_pass_its_checked_state_as_a_colour_space(window, qapp):
    """`triggered` carries a bool. Bound straight to a method whose first
    argument is the colour space, it asks for one called "False"."""
    window.menu_bar.action_frame_rgb_dialog.trigger()
    qapp.processEvents()
    assert window.frame_manager.current_frame.frame_type == "rgb"
    for widget in qapp.topLevelWidgets():
        if isinstance(widget, QDialog) and widget.windowTitle() == "RGB":
            widget.close()


@pytest.mark.parametrize(
    ("space", "name", "slot"),
    [
        ("rgb", "green", "green"),
        ("hsv", "value", "blue"),
        ("hsv", "hue", "red"),
        ("hls", "lightness", "green"),
        ("hls", "saturation", "blue"),
    ],
)
def test_xpa_takes_ds9s_name_for_a_channel(window, space, name, slot):
    """DS9 names the planes per colour space -- `hsv value`, `hls
    lightness` -- while they are stored under one set of keys. A script
    written for DS9 uses DS9's names."""
    from ncrads9.communication.xpa.xpa_commands import XPACommands

    commands = XPACommands(window)
    assert commands.handle(space, {"args": []})["status"] == "ok"
    reply = commands.handle(space, {"args": ["channel", name]})
    assert reply["status"] == "ok", reply.get("message")
    assert window.frame_manager.current_frame.rgb_current_channel == slot


def test_xpa_refuses_a_channel_no_colour_space_has(window):
    from ncrads9.communication.xpa.xpa_commands import XPACommands

    commands = XPACommands(window)
    commands.handle("hsv", {"args": []})
    reply = commands.handle("hsv", {"args": ["channel", "puce"]})
    assert reply["status"] == "error"
    assert "not a channel" in reply["message"]


# -- Frame -> Match -> Frame (the view only, not the colours) ----------------------


def test_matching_the_frame_view_copies_pan_zoom_and_orientation(two_frames):
    """DS9's Match -> Frame -> Image aligns the view: pan, zoom, rotation and
    orientation, and nothing else."""
    window = two_frames
    window.frame_manager.goto_frame(0)
    source = window.frame_manager.current_frame
    source.zoom = 3.0
    source.pan_x, source.pan_y = 40.0, 25.0
    source.rotation = 90.0
    source.flip_x = True

    window.frame_controller.match_image()

    other = window.frame_manager.frames[1]
    assert other.zoom == pytest.approx(3.0)
    assert other.pan_x == pytest.approx(40.0) and other.pan_y == pytest.approx(25.0)
    assert other.rotation == pytest.approx(90.0)
    assert other.flip_x is True
    assert other.align_wcs is False


def test_matching_the_frame_view_leaves_the_colours_and_scale_alone(two_frames):
    """The bug: matching the view used to clobber every other frame's
    colormap, scale and limits, which have Match entries of their own."""
    window = two_frames
    window.frame_manager.goto_frame(0)
    source = window.frame_manager.current_frame
    other = window.frame_manager.frames[1]

    source.colormap = "heat"
    source.scale = ScaleAlgorithm.LOG
    source.z1, source.z2 = 1.0, 2.0
    other.colormap = "cool"
    other.scale = ScaleAlgorithm.LINEAR
    other.z1, other.z2 = 10.0, 20.0

    window.frame_controller.match_image()

    # The view matched, the colours and scaling did not.
    assert other.colormap == "cool"
    assert other.scale is ScaleAlgorithm.LINEAR
    assert (other.z1, other.z2) == (10.0, 20.0)


def test_matching_wcs_aligns_the_view_without_touching_the_colours(two_frames):
    window = two_frames
    window.frame_manager.goto_frame(0)
    source = window.frame_manager.current_frame
    other = window.frame_manager.frames[1]
    if not (source.wcs_handler and source.wcs_handler.is_valid):
        pytest.skip("fixture frame has no WCS")
    other.colormap = "cool"
    source.colormap = "heat"
    source.zoom = 5.0

    window.frame_controller.match_wcs()

    assert other.zoom == pytest.approx(5.0)
    assert other.align_wcs is True
    assert other.colormap == "cool"  # untouched


# -- Frame -> Match -> Slice (the cube slice, not the view) ------------------------


def test_matching_the_slice_steps_the_other_cube(two_cubes):
    """Match -> Slice used to align the frame view; it should step the other
    cubes to the current frame's slice, DS9's MatchCube."""
    window = two_cubes
    window.frame_manager.goto_frame(0)
    window.frame_controller.set_slice(3)
    other = window.frame_manager.frames[1]
    other.slice_index = 0

    window.frame_controller.match_slice("image")

    assert other.slice_index == 3


def test_matching_the_slice_with_no_cube_says_so(two_frames):
    two_frames.frame_controller.match_slice("image")
    assert "no other frame holds a data cube" in two_frames.status_bar.currentMessage().lower()
