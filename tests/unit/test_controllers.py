# NCRADS9 - NCRA DS9 Viewer
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

"""The per-menu controllers extracted from MainWindow in M2.

Two things are checked for each controller: that its methods do what the
MainWindow methods they replaced did, and that the menu, XPA and the command
line all reach the *same* method -- which is the point of the split
(PLAN.md §4), and which they had already failed to do before it.
"""

import numpy as np
import pytest

from ncrads9.coordinates.coord_system import CoordinateContext, SkyFormat, SkyFrame
from ncrads9.rendering.scale_algorithms import ScaleAlgorithm
from ncrads9.ui.controllers.base import Controller
from ncrads9.ui.controllers.scale import SCALE_ACTIONS, ScaleController
from ncrads9.ui.controllers.wcs import FORMAT_ACTIONS, SKY_ACTIONS, WCSController
from ncrads9.ui.main_window import MainWindow
from ncrads9.utils.preferences import Preferences


@pytest.fixture
def main_window(qapp, monkeypatch):
    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    yield window
    window.close()


def _load_image(window, width=64, height=48):
    frame = window.frame_manager.current_frame
    image = np.arange(width * height, dtype=np.float32).reshape(height, width)
    frame.image_data = image.copy()
    frame.original_image_data = image.copy()
    window.z1 = None
    window.z2 = None
    window._update_frame_display()
    return frame


class TestControllerBase:
    """The shared accessors and guards."""

    def test_accessors_point_at_window_state(self, main_window):
        controller = Controller(main_window)
        assert controller.menu is main_window.menu_bar
        assert controller.frames is main_window.frame_manager
        assert controller.viewer is main_window.image_viewer
        assert controller.status_bar is main_window.status_bar
        assert controller.coords is main_window.coord_context

    def test_frame_follows_the_current_frame(self, main_window):
        controller = Controller(main_window)
        assert controller.frame is main_window.frame_manager.current_frame

    def test_require_frame_rejects_an_empty_frame(self, main_window):
        controller = Controller(main_window)
        assert controller.require_frame() is None

    def test_require_frame_returns_a_loaded_frame(self, main_window):
        frame = _load_image(main_window)
        assert Controller(main_window).require_frame() is frame

    def test_connect_and_sync_are_safe_no_ops(self, main_window):
        controller = Controller(main_window)
        controller.connect()
        controller.sync()


class TestScaleController:
    """The Scale menu."""

    def test_window_exposes_the_controller(self, main_window):
        assert isinstance(main_window.scale, ScaleController)

    @pytest.mark.parametrize(("suffix", "algorithm"), sorted(SCALE_ACTIONS.items()))
    def test_menu_action_selects_its_algorithm(self, main_window, suffix, algorithm):
        _load_image(main_window)
        getattr(main_window.menu_bar, f"action_scale_{suffix}").trigger()
        assert main_window.current_scale is algorithm

    @pytest.mark.parametrize(("suffix", "algorithm"), sorted(SCALE_ACTIONS.items()))
    def test_the_menu_shows_the_current_algorithm(self, main_window, suffix, algorithm):
        main_window.scale.set_scale(algorithm)
        checked = {
            name
            for name in SCALE_ACTIONS
            if getattr(main_window.menu_bar, f"action_scale_{name}").isChecked()
        }
        assert checked == {suffix}

    def test_set_scale_persists_on_the_frame(self, main_window):
        frame = _load_image(main_window)
        main_window.scale.set_scale(ScaleAlgorithm.LOG)
        assert frame.scale is ScaleAlgorithm.LOG

    def test_minmax_limits_come_from_the_data(self, main_window):
        frame = _load_image(main_window)
        main_window.scale.set_minmax_limits()
        assert main_window.z1 == pytest.approx(float(np.nanmin(frame.image_data)))
        assert main_window.z2 == pytest.approx(float(np.nanmax(frame.image_data)))
        assert frame.z1 == pytest.approx(main_window.z1)

    def test_reset_limits_discards_a_user_value(self, main_window):
        """Reset drops whatever the user set and recomputes from the data.

        It does not leave the limits as None: redrawing recomputes zscale and
        persists the result onto the frame. That is pre-existing behaviour --
        the MainWindow method this replaced did the same -- so the observable
        contract is "the stale value is gone", not "the field is None".
        """
        frame = _load_image(main_window)
        main_window.z1 = -999.0
        main_window.z2 = 999.0
        frame.z1 = -999.0
        frame.z2 = 999.0

        main_window.scale.reset_limits()

        assert main_window.z1 != -999.0
        assert frame.z1 != -999.0

    def test_rgb_limits_land_on_the_active_channel(self, main_window):
        main_window._new_frame_with_type("rgb")
        frame = main_window.frame_manager.current_frame
        image = np.arange(64, dtype=np.float32).reshape(8, 8)
        frame.rgb_channels["green"] = image
        frame.rgb_current_channel = "green"
        frame.image_data = image
        frame.original_image_data = image

        main_window.scale.set_minmax_limits()
        assert frame.rgb_channel_z1["green"] == pytest.approx(0.0)
        assert frame.rgb_channel_z2["green"] == pytest.approx(63.0)

    def test_no_image_means_no_change(self, main_window):
        main_window.scale.set_minmax_limits()
        assert main_window.z1 is None

    def test_dialog_params_map_onto_algorithms(self, main_window):
        _load_image(main_window)
        main_window.scale.apply_dialog_params({"scale_function": "Histogram Equalization"})
        assert main_window.current_scale is ScaleAlgorithm.HISTOGRAM_EQUALIZATION

    def test_dialog_params_apply_explicit_limits(self, main_window):
        _load_image(main_window)
        main_window.scale.apply_dialog_params(
            {"scale_function": "Linear", "auto_limits": False, "min_value": 5.0, "max_value": 9.0}
        )
        assert (main_window.z1, main_window.z2) == (5.0, 9.0)


class TestWCSController:
    """The WCS menu."""

    def test_window_exposes_the_controller(self, main_window):
        assert isinstance(main_window.wcs, WCSController)

    @pytest.mark.parametrize("name", SKY_ACTIONS)
    def test_menu_action_selects_its_sky_frame(self, main_window, name):
        getattr(main_window.menu_bar, f"action_wcs_{name}").trigger()
        assert main_window.coord_context.sky is SkyFrame(name)

    @pytest.mark.parametrize("name", FORMAT_ACTIONS)
    def test_menu_action_selects_its_format(self, main_window, name):
        getattr(main_window.menu_bar, f"action_wcs_{name}").trigger()
        assert main_window.coord_context.sky_format is SkyFormat(name)

    def test_changing_the_frame_keeps_the_format(self, main_window):
        main_window.wcs.set_format("degrees")
        main_window.wcs.set_sky_frame("galactic")
        assert main_window.coord_context.sky is SkyFrame.GALACTIC
        assert main_window.coord_context.sky_format is SkyFormat.DEGREES

    @pytest.mark.parametrize("name", SKY_ACTIONS)
    def test_the_menu_shows_the_current_frame(self, main_window, name):
        main_window.wcs.set_sky_frame(name)
        checked = {
            other for other in SKY_ACTIONS if getattr(main_window.menu_bar, f"action_wcs_{other}").isChecked()
        }
        assert checked == {name}

    def test_readout_is_blank_without_a_wcs(self, main_window):
        _load_image(main_window)
        main_window.wcs.update_readout(1, 1)
        assert "---" in main_window.status_bar.wcs_coord_label.text()

    def test_direction_arrows_toggle_tracks_the_action(self, main_window):
        """The window flag follows the action's checked state either way.

        The action ships checked -- arrows are on by default -- and `trigger()`
        flips a checkable action, so this asserts the relationship rather than
        an absolute starting value.
        """
        action = main_window.menu_bar.action_show_direction_arrows
        for _ in range(2):
            action.trigger()
            assert main_window._show_direction_arrows is action.isChecked()

    def test_arrows_are_cleared_when_there_is_no_wcs(self, main_window):
        _load_image(main_window)
        main_window._show_direction_arrows = True
        main_window.wcs.update_direction_arrows()
        overlay = main_window.image_viewer.contour_overlay
        assert overlay._north_vector is None


class TestRegionController:
    """The Region menu."""

    def test_window_exposes_the_controller(self, main_window):
        from ncrads9.ui.controllers.region import RegionController

        assert isinstance(main_window.region, RegionController)

    def test_drawing_a_region_does_not_crash_the_window(self, main_window):
        """M1 broke this and nothing noticed for a whole milestone.

        `_on_region_created` read `region.mode.value`, which existed on the
        overlay's own `Region` dataclass but not on the `BaseRegion` subclasses
        that replaced it. The M1 round-trip tests connected their own listener
        to the overlay's signal, so the window's handler was never exercised
        and every draw raised AttributeError in the running application.
        """
        from ncrads9.regions.shapes.circle import Circle

        _load_image(main_window)
        frame = main_window.frame_manager.current_frame
        region = Circle(center=(10.0, 10.0), radius=5.0)

        main_window.region.on_created(region)

        assert region in frame.regions
        assert "circle" in main_window.statusBar().currentMessage().lower()

    def test_selecting_a_region_does_not_crash_the_window(self, main_window):
        from ncrads9.regions.shapes.box import Box

        _load_image(main_window)
        main_window.region.on_selected(Box(center=(1.0, 2.0), width_box=3.0, height_box=4.0))
        assert "box" in main_window.statusBar().currentMessage().lower()

    @pytest.mark.parametrize(
        ("shape_factory", "expected"),
        [
            (
                lambda: __import__("ncrads9.regions.shapes.circle", fromlist=["Circle"]).Circle(
                    center=(0.0, 0.0), radius=1.0
                ),
                "circle",
            ),
            (
                lambda: __import__("ncrads9.regions.shapes.polygon", fromlist=["Polygon"]).Polygon(
                    vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]
                ),
                "polygon",
            ),
            (
                lambda: __import__("ncrads9.regions.shapes.point", fromlist=["Point"]).Point(
                    center=(0.0, 0.0)
                ),
                "point",
            ),
        ],
    )
    def test_describe_names_the_shape(self, shape_factory, expected):
        from ncrads9.ui.controllers.region import describe

        assert describe(shape_factory()) == expected

    def test_the_overlay_signal_reaches_the_controller(self, main_window):
        """End to end: a real gesture must not raise through the window."""
        from PyQt6.QtCore import QPointF, Qt
        from PyQt6.QtGui import QMouseEvent

        from ncrads9.ui.widgets.region_overlay import RegionMode

        _load_image(main_window, width=200, height=200)
        overlay = main_window.image_viewer.region_overlay
        overlay.set_zoom(1.0, (0.0, 0.0), image_width=0, image_height=0)
        main_window.region.set_mode(RegionMode.CIRCLE)

        def event(kind, x, y, button):
            return QMouseEvent(kind, QPointF(x, y), button, button, Qt.KeyboardModifier.NoModifier)

        overlay.mousePressEvent(event(QMouseEvent.Type.MouseButtonPress, 20, 20, Qt.MouseButton.LeftButton))
        overlay.mouseMoveEvent(
            QMouseEvent(
                QMouseEvent.Type.MouseMove,
                QPointF(40, 40),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        overlay.mouseReleaseEvent(
            event(QMouseEvent.Type.MouseButtonRelease, 40, 40, Qt.MouseButton.LeftButton)
        )

        frame = main_window.frame_manager.current_frame
        assert len(frame.regions) == 1
        assert len(overlay.regions) == 1

    def test_clear_returns_to_pan_mode(self, main_window):
        from ncrads9.regions.shapes.circle import Circle
        from ncrads9.ui.widgets.region_overlay import RegionMode

        _load_image(main_window)
        frame = main_window.frame_manager.current_frame
        frame.regions.append(Circle(center=(1.0, 1.0), radius=2.0))

        main_window.region.clear_regions()

        assert frame.regions == []
        assert main_window.image_viewer.region_overlay.mode is RegionMode.NONE


class TestOneMethodPerAction:
    """Menu, XPA and CLI must all land on the controller, not on copies."""

    def test_xpa_scale_uses_the_controller(self, main_window):
        from ncrads9.communication.xpa.xpa_commands import XPACommands

        _load_image(main_window)
        commands = XPACommands(main_window)
        commands.handle("scale", {"args": ["log"]})
        assert main_window.current_scale is ScaleAlgorithm.LOG

    def test_xpa_wcs_uses_the_controller(self, main_window):
        from ncrads9.communication.xpa.xpa_commands import XPACommands

        commands = XPACommands(main_window)
        commands.handle("wcs", {"action": "set", "system": "galactic"})
        assert main_window.coord_context.sky is SkyFrame.GALACTIC
        assert commands.handle("wcs", {})["result"] == "galactic"

    def test_cli_wcs_uses_the_controller(self, main_window):
        from ncrads9.app import apply_startup_cli

        apply_startup_cli(main_window, ["ncrads9", "-wcs", "fk4", "-degrees"])
        assert main_window.coord_context.sky is SkyFrame.FK4
        assert main_window.coord_context.sky_format is SkyFormat.DEGREES

    def test_the_window_no_longer_carries_the_moved_methods(self, main_window):
        """Shims would let call sites drift apart again."""
        for name in (
            "_set_scale",
            "_reset_scale_limits",
            "_scale_minmax",
            "_show_scale_dialog",
            "_apply_scale_params",
            "_set_wcs_system",
            "_set_wcs_format",
            "_update_wcs_display",
            "_update_direction_arrows",
            "_toggle_direction_arrows",
        ):
            assert not hasattr(main_window, name), name

    def test_every_controller_is_registered_for_sync(self, main_window):
        assert main_window.scale in main_window.controllers
        assert main_window.wcs in main_window.controllers
        main_window._sync_controllers()


class TestCoordinateContextIsShared:
    """One context, not a copy per consumer."""

    def test_the_window_holds_one_context(self, main_window):
        assert isinstance(main_window.coord_context, CoordinateContext)

    def test_the_controller_reads_the_window_context(self, main_window):
        main_window.wcs.set_sky_frame("icrs")
        assert main_window.wcs.coords is main_window.coord_context
