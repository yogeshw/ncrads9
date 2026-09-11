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
The button bar, and the gate that every button actually does something.

There was no test file for the bar at all, and sixty of its hundred and
seventeen buttons did nothing when clicked: a checkable action's button
was wired to `QAction.setChecked`, which emits `toggled` but *not*
`triggered`, and every controller here connects to `triggered`. So a
colormap button ticked itself and left the colormap alone -- which looks
like a working button, and is the reason it went unnoticed.

`test_every_button_reaches_its_action` is the gate. It is the button
bar's equivalent of M2-15's no-dead-menu-entries test, and it is written
to fail on exactly the shape of that bug: the click has to reach
`triggered`, not merely change an appearance.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits
from PyQt6.QtWidgets import QPushButton

from ncrads9.rendering.scale_algorithms import ScaleAlgorithm
from ncrads9.ui.button_bar import CATEGORIES

#: `File -> exit` closes the application, which ends the test session.
NOT_CLICKABLE = {("File", "exit")}

SIZE = 64


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path):
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
    header = fits.Header(
        {
            "CRPIX1": SIZE // 2,
            "CRPIX2": SIZE // 2,
            "CRVAL1": 202.48,
            "CRVAL2": 47.21,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
        }
    )
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32), header=header).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    yield window
    window.close()


@pytest.fixture
def quiet(monkeypatch):
    """Nothing may block: a good many of these buttons open a dialog."""
    from PyQt6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox

    ok = QMessageBox.StandardButton.Ok
    monkeypatch.setattr(QMessageBox, "exec", lambda self: ok)
    for name in ("information", "warning", "critical", "about"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda *a, **k: (0, False)))
    monkeypatch.setattr(QInputDialog, "getDouble", staticmethod(lambda *a, **k: (0.0, False)))
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)


def _button(window, category: str, label: str) -> QPushButton | None:
    """One button of one category, by the text on it."""
    window.button_bar.set_category(category)
    page = window.button_bar._pages[category]
    return next((b for b in page.findChildren(QPushButton) if b.text() == label), None)


# -- the gate ----------------------------------------------------------------------


def test_every_button_exists(main_window):
    """A button named in `CATEGORIES` that is not built is a button the user
    cannot find, and the bar would not say so."""
    missing = [
        f"{category}/{spec.label}"
        for category, specs in CATEGORIES
        for spec in specs
        if _button(main_window, category, spec.label) is None
    ]
    assert missing == []


def test_every_button_reaches_its_action(main_window, quiet):
    """Click every button and require that something *acted*.

    The gate. A menu-backed button must reach its action's `triggered`,
    and a command button must emit on `ButtonBar.command`. Sixty buttons
    failed this when it was written: they were wired to `setChecked`,
    which changes an appearance and tells no controller anything.

    A disabled button is allowed to do nothing -- that is what disabled
    means, and Undo with an empty stack is the honest case.
    """
    bar = main_window.button_bar
    dead: list[str] = []

    for category, specs in CATEGORIES:
        for spec in specs:
            if (category, spec.label) in NOT_CLICKABLE:
                continue
            button = _button(main_window, category, spec.label)
            assert button is not None, f"{category}/{spec.label}"

            if spec.command is not None:
                emitted: list[str] = []
                bar.command.connect(emitted.append)
                try:
                    button.click()
                finally:
                    bar.command.disconnect(emitted.append)
                if not emitted:
                    dead.append(f"{category}/{spec.label}: emitted nothing")
                continue

            action = getattr(main_window.menu_bar, spec.action, None)
            if action is None:
                dead.append(f"{category}/{spec.label}: no action {spec.action}")
                continue
            if not action.isEnabled():
                continue

            fired: list[object] = []
            action.triggered.connect(fired.append)
            try:
                button.click()
            finally:
                action.triggered.disconnect(fired.append)
            if not fired:
                dead.append(f"{category}/{spec.label}: click never reached triggered")

    assert dead == [], "\n".join(dead)


def test_a_disabled_action_disables_its_button(main_window):
    """Undo with nothing to undo. The button used to stay clickable beside
    a greyed menu entry, so it looked broken rather than unavailable."""
    undo = main_window.menu_bar.action_undo
    assert undo.isEnabled() is False
    assert _button(main_window, "Edit", "undo").isEnabled() is False

    from ncrads9.regions.shapes.circle import Circle

    frame = main_window.frame_manager.current_frame
    with main_window.undo.regions("Add Region"):
        frame.regions = [Circle(center=(10.0, 10.0), radius=3.0)]

    assert undo.isEnabled() is True
    assert _button(main_window, "Edit", "undo").isEnabled() is True


# -- what the buttons actually do --------------------------------------------------


@pytest.mark.parametrize(
    ("label", "expected"),
    [("grey", "grey"), ("heat", "heat"), ("cool", "cool"), ("rainbow", "rainbow"), ("viridis", "viridis")],
)
def test_a_colormap_button_changes_the_colormap(main_window, label, expected):
    """The bug the user reported: the Color page ticked and did nothing."""
    _button(main_window, "Color", label).click()
    assert main_window.current_colormap == expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("linear", ScaleAlgorithm.LINEAR),
        ("log", ScaleAlgorithm.LOG),
        ("sqrt", ScaleAlgorithm.SQRT),
        ("squared", ScaleAlgorithm.SQUARED),
        ("asinh", ScaleAlgorithm.ASINH),
        ("hist", ScaleAlgorithm.HISTOGRAM_EQUALIZATION),
    ],
)
def test_a_scale_button_changes_the_scale(main_window, label, expected):
    _button(main_window, "Scale", label).click()
    assert main_window.current_scale is expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [("fk5", "fk5"), ("fk4", "fk4"), ("icrs", "icrs"), ("galactic", "galactic"), ("ecliptic", "ecliptic")],
)
def test_a_wcs_button_changes_the_sky_frame(main_window, label, expected):
    _button(main_window, "WCS", label).click()
    assert main_window.coord_context.sky.value == expected


def test_the_sky_format_buttons_work(main_window):
    _button(main_window, "WCS", "sexagesimal").click()
    assert main_window.coord_context.sky_format.value == "sexagesimal"
    _button(main_window, "WCS", "degrees").click()
    assert main_window.coord_context.sky_format.value == "degrees"


@pytest.mark.parametrize("label", ["panner", "magnifier", "colorbar", "info"])
def test_a_view_button_hides_its_panel(main_window, label):
    before = getattr(main_window.view_state, label)
    _button(main_window, "View", label).click()
    assert getattr(main_window.view_state, label) is not before


@pytest.mark.parametrize(
    ("label", "expected"),
    [("horizontal", "horizontal"), ("vertical", "vertical"), ("basic", "basic"), ("advanced", "advanced")],
)
def test_a_layout_button_switches_the_layout(main_window, label, expected):
    _button(main_window, "View", label).click()
    assert main_window.view_state.layout.value == expected


def test_the_frame_mode_buttons_switch_modes(main_window):
    _button(main_window, "Frame", "tile").click()
    assert main_window._frame_display_mode == "tile"
    _button(main_window, "Frame", "single").click()
    assert main_window._frame_display_mode == "single"


@pytest.mark.parametrize(("label", "expected"), [("block 2", 32), ("block 4", 16), ("block 1", 64)])
def test_a_block_button_blocks(main_window, label, expected):
    """Blocking is a display operation, so it shows up in what the analysis
    tools read rather than in the frame's copy of the file."""
    _button(main_window, "Bin", label).click()
    frame = main_window.frame_manager.current_frame
    assert main_window.analysis.analysis_image_data(frame).shape[0] == expected


@pytest.mark.parametrize(
    ("label", "expected"), [("1/8", 0.125), ("1/2", 0.5), ("2", 2.0), ("4", 4.0), ("8", 8.0)]
)
def test_a_zoom_button_zooms(main_window, label, expected):
    """These are command buttons rather than menu-backed ones, which is why
    they were among the few that always worked."""
    _button(main_window, "Zoom", label).click()
    assert main_window.image_viewer.get_zoom() == pytest.approx(expected)


@pytest.mark.parametrize(("label", "expected"), [("x", "x"), ("y", "y"), ("xy", "xy"), ("none", "none")])
def test_an_orient_button_flips(main_window, label, expected):
    _button(main_window, "Zoom", label).click()
    assert main_window.zoom.orientation() == expected


@pytest.mark.parametrize("label", ["contours", "grid", "smooth"])
def test_an_analysis_toggle_button_toggles(main_window, label, quiet):
    actions = {
        "contours": main_window.menu_bar.action_contours,
        "grid": main_window.menu_bar.action_coordinate_grid,
        "smooth": main_window.menu_bar.action_smooth,
    }
    action = actions[label]
    assert action.isChecked() is False
    _button(main_window, "Analysis", label).click()
    assert action.isChecked() is True
    _button(main_window, "Analysis", label).click()
    assert action.isChecked() is False


def test_a_region_button_sets_the_drawing_mode(main_window):
    """The mode lives on the viewer, which is what draws; the bar's own
    tick is checked separately below."""
    for label in ("Circle", "Box", "Polygon", "Line", "Point"):
        _button(main_window, "Region", label).click()
        assert main_window.image_viewer.region_overlay.mode.value == label.lower()
        assert _button(main_window, "Region", label).isChecked() is True

    _button(main_window, "Region", "None").click()
    assert main_window.image_viewer.region_overlay.mode.value == "none"


# -- the button and its menu entry stay in step ------------------------------------


def test_the_menu_ticks_the_button(main_window):
    """The other direction: a colormap chosen from the *menu*, or by XPA,
    has to tick the bar too, or the two disagree about what is showing."""
    main_window.menu_bar.action_cmap_heat.trigger()
    assert _button(main_window, "Color", "heat").isChecked() is True
    assert _button(main_window, "Color", "grey").isChecked() is False


def test_xpa_ticks_the_button(main_window):
    from ncrads9.communication.xpa.xpa_commands import XPACommands

    XPACommands(main_window).handle("cmap", {"args": ["cool"]})
    assert main_window.current_colormap == "cool"
    assert _button(main_window, "Color", "cool").isChecked() is True


def test_the_buttons_still_work_after_the_bar_turns_vertical(main_window):
    """DS9's vertical and advanced layouts grid the bar beside the canvas.
    It re-grids the buttons it already has rather than rebuilding them; a
    rebuild that dropped the connections would be this same bug again."""
    main_window.button_bar.set_orientation(True)
    _button(main_window, "Color", "heat").click()
    assert main_window.current_colormap == "heat"

    main_window.button_bar.set_orientation(False)
    _button(main_window, "Color", "cool").click()
    assert main_window.current_colormap == "cool"


def test_an_exclusive_button_clicked_twice_stays_chosen(main_window):
    """A radio button clicked again is still chosen -- it must not untick
    itself and leave the bar disagreeing with the menu."""
    viridis = _button(main_window, "Color", "viridis")
    viridis.click()
    assert main_window.current_colormap == "viridis"
    viridis.click()
    assert main_window.current_colormap == "viridis"
    assert viridis.isChecked() is True
    assert main_window.menu_bar.action_cmap_viridis.isChecked() is True
