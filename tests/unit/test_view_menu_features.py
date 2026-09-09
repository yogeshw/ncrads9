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


"""The View menu, the buttonbar and the panner compass, in a real window.

`test_window_layout.py` covers the layout pieces on their own; this covers
them wired into `MainWindow` -- the menu driving the state, the buttons
driving the menu, and the readout being filled.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from ncrads9.core.wcs_handler import WCSHandler, available_alternates
from ncrads9.ui.button_bar import CATEGORIES, ButtonBar, ButtonSpec
from ncrads9.ui.controllers.view import LAYOUT_ACTIONS, PANEL_ACTIONS
from ncrads9.ui.layout.view_state import INFO_FIELDS, ViewLayout
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


def _wcs_header(width: int = 10, height: int = 10, alternate: bool = False) -> fits.Header:
    """A small tangent-plane header, optionally with a galactic alternate."""
    header = fits.Header(
        {
            "NAXIS": 2,
            "NAXIS1": width,
            "NAXIS2": height,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CRVAL1": 202.48,
            "CRVAL2": 47.23,
            "CRPIX1": width / 2,
            "CRPIX2": height / 2,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
            "OBJECT": "M51",
            "BUNIT": "Jy/beam",
        }
    )
    if alternate:
        header.update(
            {
                "CTYPE1A": "GLON-TAN",
                "CTYPE2A": "GLAT-TAN",
                "CRVAL1A": 104.85,
                "CRVAL2A": 68.56,
                "CRPIX1A": width / 2,
                "CRPIX2A": height / 2,
                "CDELT1A": -0.001,
                "CDELT2A": 0.001,
            }
        )
    return header


def _load(window: MainWindow, alternate: bool = False) -> None:
    """Put a small WCS image on the current frame."""
    header = _wcs_header(alternate=alternate)
    frame = window.frame_manager.current_frame
    frame.image_data = np.arange(100, dtype=np.float32).reshape(10, 10)
    frame.original_image_data = frame.image_data
    frame.header = header
    frame.filepath = Path("m51.fits")
    frame.wcs_handler = WCSHandler(wcs=WCS(header))
    window.frame_controller.update_display()


# -- the shell replaces the docks --------------------------------------------


def test_window_has_no_dock_widgets(main_window):
    """M3 replaced every QDockWidget with the fixed shell."""
    from PyQt6.QtWidgets import QDockWidget

    assert main_window.findChildren(QDockWidget) == []


def test_shell_is_the_central_widget(main_window):
    assert main_window.centralWidget() is main_window.shell


def test_panels_exist_and_are_plain_widgets(main_window):
    from PyQt6.QtWidgets import QDockWidget

    for name in ("info_panel", "panner_panel", "magnifier_panel", "horizontal_graph", "vertical_graph"):
        panel = getattr(main_window, name)
        assert not isinstance(panel, QDockWidget), name


# -- the View menu -----------------------------------------------------------


def test_every_view_action_is_wired(main_window):
    """The M0 guard checks receivers; this checks the effect."""
    menu = main_window.menu_bar
    for attribute, layout in LAYOUT_ACTIONS.items():
        getattr(menu, attribute).trigger()
        assert main_window.view_state.layout is layout


def test_layout_actions_are_one_radio_group(main_window):
    menu = main_window.menu_bar
    menu.action_view_vertical.trigger()
    assert menu.action_view_vertical.isChecked()
    assert not menu.action_view_horizontal.isChecked()


def test_panel_toggles_reach_the_state(main_window):
    menu = main_window.menu_bar
    for name, attribute in PANEL_ACTIONS.items():
        action = getattr(menu, attribute)
        action.setChecked(False)
        assert getattr(main_window.view_state, name) is False
        action.setChecked(True)
        assert getattr(main_window.view_state, name) is True


def test_hiding_the_panner_hides_the_widget(main_window):
    main_window.menu_bar.action_view_panner.setChecked(False)
    assert main_window.panner_panel.isHidden()
    main_window.menu_bar.action_view_panner.setChecked(True)
    assert not main_window.panner_panel.isHidden()


def test_icons_toggle_drives_the_toolbar(main_window):
    """DS9 calls the icon bars Icons; ours is the toolbar."""
    main_window.menu_bar.action_view_icons.setChecked(False)
    assert main_window.main_toolbar.isHidden()
    main_window.menu_bar.action_view_icons.setChecked(True)
    assert not main_window.main_toolbar.isHidden()


def test_show_toolbar_is_the_icons_action(main_window):
    menu = main_window.menu_bar
    assert menu.action_show_toolbar is menu.action_view_icons


def test_colorbar_action_is_shared_with_the_color_menu(main_window):
    """One action in two menus, so the two tick marks cannot disagree."""
    menu = main_window.menu_bar
    assert menu.action_colorbar is menu.action_view_colorbar


def test_colorbar_toggle_hides_the_colorbar(main_window):
    main_window.menu_bar.action_view_colorbar.setChecked(False)
    assert main_window.colorbar_widget.isHidden()
    assert main_window.view_state.colorbar is False


def test_color_controller_routes_through_the_view(main_window):
    main_window.color.set_colorbar_visible(False)
    assert main_window.view_state.colorbar is False


def test_graph_toggles_show_the_cut_graphs(main_window):
    main_window.menu_bar.action_view_graph_horizontal.setChecked(True)
    assert not main_window.horizontal_graph.isHidden()
    main_window.menu_bar.action_view_graph_horizontal.setChecked(False)
    assert main_window.horizontal_graph.isHidden()


def test_multi_colorbar_reaches_the_state(main_window):
    """It announced itself as deferred until M5-12 gave it an effect.

    What it does now is tested in `test_color_tags.py`; this only checks that
    the toggle reaches the state.
    """
    main_window.menu_bar.action_view_multi_colorbar.setChecked(False)
    assert main_window.view_state.multi is False
    main_window.menu_bar.action_view_multi_colorbar.setChecked(True)
    assert main_window.view_state.multi is True


def test_info_field_toggles_cover_every_field(main_window):
    """One menu entry per field, including the twenty-six alternate WCSes."""
    actions = main_window.menu_bar.info_field_actions
    # `value` is the one field DS9 grids with no toggle.
    assert set(actions) == set(INFO_FIELDS) - {"value"}


def test_info_field_toggle_shows_the_row(main_window):
    action = main_window.menu_bar.info_field_actions["minmax"]
    action.setChecked(True)
    assert main_window.info_panel.field_visible("minmax")
    action.setChecked(False)
    assert not main_window.info_panel.field_visible("minmax")


def test_unknown_panel_and_field_are_reported_not_raised(main_window):
    main_window.view.set_panel("no_such_panel", True)
    assert "Unknown panel" in main_window.status_bar.currentMessage()
    main_window.view.set_info_field("no_such_field", True)
    assert "Unknown info-panel field" in main_window.status_bar.currentMessage()


def test_sync_ticks_the_menu_from_the_state(main_window):
    main_window.view_state.layout = ViewLayout.ADVANCED
    main_window.view_state.panner = False
    main_window.view.sync()
    assert main_window.menu_bar.action_view_advanced.isChecked()
    assert not main_window.menu_bar.action_view_panner.isChecked()


def test_layout_switch_regrids_without_error(main_window):
    for layout in ViewLayout:
        main_window.view.set_layout(layout)
        assert main_window.view_state.layout is layout


def test_set_layout_accepts_a_string(main_window):
    main_window.view.set_layout("vertical")
    assert main_window.view_state.layout is ViewLayout.VERTICAL


# -- the information panel, filled ------------------------------------------


def test_loading_fills_the_image_rows(main_window):
    _load(main_window)
    panel = main_window.info_panel
    assert panel._values["filename"].text() == "m51.fits"
    assert panel._values["object"].text() == "M51"
    assert panel._values["bunit"].text() == "Jy/beam"
    assert panel._values["frame"].text() == "Frame 1"


def test_mouse_move_fills_the_cursor_rows(main_window):
    _load(main_window)
    main_window.view.update_cursor(4, 6)
    panel = main_window.info_panel
    # DS9 numbers image pixels from one.
    assert (panel._values["image_x"].text(), panel._values["image_y"].text()) == ("5", "7")
    assert panel._values["value"].text() != ""
    assert panel._values["wcs_label"].text() == "fk5"
    assert ":" in panel._values["wcs_x"].text()


def test_physical_defaults_to_image_without_ltv(main_window):
    _load(main_window)
    main_window.view.update_cursor(4, 6)
    panel = main_window.info_panel
    assert panel._values["physical_x"].text() == "5"


def test_physical_follows_ltv_and_ltm(main_window):
    _load(main_window)
    header = main_window.frame_manager.current_frame.header
    header["LTV1"] = -100.0
    header["LTM1_1"] = 1.0
    main_window.view.update_cursor(4, 6)
    assert main_window.info_panel._values["physical_x"].text() == "105"


def test_minmax_row_reports_values_and_positions(main_window):
    _load(main_window)
    main_window.view.set_info_field("minmax", True)
    main_window.view.refresh_info()
    panel = main_window.info_panel
    assert panel._values["min"].text() == "0"
    assert panel._values["max"].text() == "99"
    # arange(100).reshape(10, 10): the minimum is at numpy row 0, which is
    # image row 10 counting from the bottom.
    assert (panel._values["min_x"].text(), panel._values["min_y"].text()) == ("0", "9")
    assert (panel._values["max_x"].text(), panel._values["max_y"].text()) == ("9", "0")


def test_keyword_row_reads_the_card_the_user_typed(main_window):
    _load(main_window)
    main_window.view.set_info_field("keyword", True)
    main_window.info_panel.keyword_entry.setText("object")
    main_window.view.update_cursor(1, 1)
    assert main_window.info_panel._values["keyword"].text() == "M51"


def test_cursor_off_the_image_blanks_the_value(main_window):
    _load(main_window)
    main_window.view.update_cursor(500, 500)
    assert main_window.info_panel._values["value"].text() == ""


def test_no_frame_clears_the_panel(main_window):
    main_window.info_panel.set_filename("stale.fits")
    main_window.frame_manager.frames.clear()
    main_window.view.refresh_info()
    assert main_window.info_panel._values["filename"].text() == ""


def test_refresh_info_does_not_open_files(main_window, monkeypatch):
    """It is a readout; it must never trigger a load.

    `MainWindow.fits_handler` opens the file when a frame has a path but no
    handler, which would mean a disk read on every redisplay.
    """
    frame = main_window.frame_manager.current_frame
    frame.filepath = Path("/nonexistent/does-not-exist.fits")
    frame.image_data = np.zeros((4, 4), dtype=np.float32)
    frame.header = None
    frame.fits_handler = None
    main_window.view.refresh_info()
    assert main_window.info_panel._values["object"].text() == ""


# -- alternate WCS -----------------------------------------------------------


def test_available_alternates_finds_the_letters():
    assert available_alternates(_wcs_header()) == ()
    assert available_alternates(_wcs_header(alternate=True)) == ("a",)
    assert available_alternates(None) == ()


def test_alternate_wcs_row_is_filled_when_shown(main_window):
    _load(main_window, alternate=True)
    main_window.view.set_info_field("wcs_a", True)
    main_window.view.update_cursor(4, 6)
    panel = main_window.info_panel
    assert panel._values["wcs_a_label"].text() == "wcsa"
    assert panel._values["wcs_a_x"].text() != ""


def test_alternate_wcs_row_stays_blank_when_hidden(main_window):
    _load(main_window, alternate=True)
    main_window.view.update_cursor(4, 6)
    assert main_window.info_panel._values["wcs_a_x"].text() == ""


def test_alternate_handlers_are_cached_per_frame(main_window):
    _load(main_window, alternate=True)
    main_window.view.set_info_field("wcs_a", True)
    main_window.view.update_cursor(1, 1)
    first = main_window.view._alternate_handlers()
    main_window.view.update_cursor(2, 2)
    assert main_window.view._alternate_handlers() is first


def test_alternate_wcs_reads_its_own_frame(main_window):
    """A galactic alternate must not come back as the primary's RA/Dec."""
    header = _wcs_header(alternate=True)
    primary = WCSHandler(header).pixel_to_world(5, 5)
    alternate = WCSHandler(header, key="a").pixel_to_world(5, 5)
    assert abs(primary[0] - alternate[0]) > 1.0


# -- the buttonbar -----------------------------------------------------------


def test_every_button_names_a_real_action(main_window):
    """A renamed action would otherwise leave a dead button."""
    menu = main_window.menu_bar
    for _category, specs in CATEGORIES:
        for spec in specs:
            if spec.action is not None:
                assert hasattr(menu, spec.action), spec.action


def test_every_command_family_has_a_handler(main_window):
    families = {
        spec.command.split(":", 1)[0]
        for _category, specs in CATEGORIES
        for spec in specs
        if spec.command is not None
    }
    assert families <= set(MainWindow.BUTTON_COMMANDS)


def test_categories_match_the_menus(main_window):
    """DS9's first row is the menu names."""
    names = [name for name, _specs in CATEGORIES]
    assert names[:6] == ["File", "Edit", "View", "Frame", "Bin", "Zoom"]
    assert names[-1] == "Help"


def test_spec_needs_exactly_one_target():
    with pytest.raises(ValueError):
        ButtonSpec("x")
    with pytest.raises(ValueError):
        ButtonSpec("x", action="action_open", command="zoom:1")


def test_selecting_a_category_switches_the_second_row(main_window):
    bar = main_window.button_bar
    bar.set_category("Zoom")
    assert bar.current_category() == "Zoom"
    bar.set_category("Scale")
    assert bar.current_category() == "Scale"


def test_unknown_category_is_ignored(main_window):
    bar = main_window.button_bar
    bar.set_category("Nonexistent")
    assert bar.current_category() == "File"


def test_action_button_triggers_its_action(main_window):
    bar = main_window.button_bar
    bar.set_category("Zoom")
    button = _button(bar, "Zoom", "in")
    fired = []
    main_window.menu_bar.action_zoom_in.triggered.connect(lambda: fired.append(True))
    button.click()
    assert fired


def test_checkable_button_mirrors_its_action(main_window):
    """The menu, a shortcut or an XPA command can all change it."""
    bar = main_window.button_bar
    button = _button(bar, "Scale", "log")
    main_window.menu_bar.action_scale_log.setChecked(True)
    assert button.isChecked()
    main_window.menu_bar.action_scale_log.setChecked(False)
    assert not button.isChecked()


def test_command_button_reaches_its_controller(main_window):
    bar = main_window.button_bar
    _load(main_window)
    _button(bar, "Region", "Circle").click()
    assert bar._command_buttons["region"]["Circle"].isChecked()


def test_command_family_is_exclusive(main_window):
    bar = main_window.button_bar
    bar.set_region_mode("Box")
    assert bar._command_buttons["region"]["Box"].isChecked()
    bar.set_region_mode("Line")
    assert not bar._command_buttons["region"]["Box"].isChecked()


def test_zoom_command_button_zooms(main_window):
    _load(main_window)
    bar = main_window.button_bar
    _button(bar, "Zoom", "1/2").click()
    assert bar._command_buttons["zoom"]["1/2"].isChecked()


def test_unhandled_command_is_reported(main_window):
    main_window._on_button_bar_command("nosuchfamily:x")
    assert "Unhandled button" in main_window.status_bar.currentMessage()


def _button(bar: ButtonBar, category: str, label: str):
    """Find one button on a category's page."""
    from PyQt6.QtWidgets import QPushButton

    page = bar._pages[category]
    for button in page.findChildren(QPushButton):
        if button.text() == label:
            return button
    raise AssertionError(f"no {label!r} button in {category}")


# -- the panner compass ------------------------------------------------------


def test_compass_goes_to_the_panner(main_window):
    """DS9 draws the compass in the panner, not over the data."""
    _load(main_window)
    panner = main_window.panner_panel
    assert panner._show_compass is True
    assert panner._north is not None
    assert panner._east is not None


def test_compass_clears_without_a_wcs(main_window):
    frame = main_window.frame_manager.current_frame
    frame.image_data = np.zeros((8, 8), dtype=np.float32)
    frame.original_image_data = frame.image_data
    frame.wcs_handler = None
    main_window.frame_controller.update_display()
    assert main_window.panner_panel._show_compass is False


def test_panner_and_magnifier_receive_the_image(main_window):
    """These were fed behind a `hasattr(self, ...)` that was never true."""
    _load(main_window)
    assert main_window.panner_panel._current_image is not None
    assert main_window.magnifier_panel._current_image is not None


# -- themes ------------------------------------------------------------------


def test_themes_cover_the_preferences_dialog_choices(main_window):
    """The dialog offers exactly the three themes that exist."""
    from ncrads9.ui.controllers.edit import THEMES

    assert set(THEMES) == {"System", "Light", "Dark"}


def test_applying_a_theme_sets_the_stylesheet(main_window):
    from PyQt6.QtWidgets import QApplication

    from ncrads9.ui.themes.dark import DarkTheme

    main_window.edit.apply_theme("Dark")
    assert QApplication.instance().styleSheet() == DarkTheme.STYLESHEET
    main_window.edit.apply_theme("System")


def test_reapplying_the_same_theme_is_skipped(main_window, monkeypatch):
    """Restyling walks every live widget, so it must happen only on a change."""
    from ncrads9.ui.controllers.edit import THEME_PROPERTY
    from ncrads9.ui.themes.dark import DarkTheme

    calls = []
    monkeypatch.setattr(DarkTheme, "apply", classmethod(lambda cls, app=None: calls.append(1)))
    main_window.edit.apply_theme("Dark")
    main_window.edit.apply_theme("Dark")
    assert len(calls) == 1

    from PyQt6.QtWidgets import QApplication

    QApplication.instance().setProperty(THEME_PROPERTY, None)


def test_unknown_theme_is_reported(main_window):
    main_window.edit.apply_theme("Solarized")
    assert "Unknown theme" in main_window.status_bar.currentMessage()


def test_theme_is_a_preference(main_window):
    from ncrads9.ui.controllers.edit import PREFERENCE_DEFAULTS

    assert PREFERENCE_DEFAULTS["theme"] == "System"
    assert "theme" in main_window.edit.preferences_dict()
