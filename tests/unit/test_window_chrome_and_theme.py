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
Every popup can be moved, and every popup follows the theme.

Two reported faults:

* some popups "cannot be dragged out of the way". None was frameless --
  seven carried `WindowStaysOnTopHint`, so they floated over the image
  whatever the user did and could not be sent behind the main window. On
  a small screen there was nowhere to put them.
* under a dark theme "a few windows that popup have a grey background and
  poor readability of text". The themes styled `QMainWindow`'s background
  and gave `QWidget` only a text *colour*, so every dialog kept Qt's
  default light grey ground and wore the dark theme's light grey text on
  it. Grey on grey.

Both gates walk every dialog in the application rather than a list
someone has to remember to extend.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QPixmap

from ncrads9.ui.themes import palettes

SIZE = 64

#: A luma gap below this reads as "text the same colour as its background".
#: Grey-on-grey, the reported fault, measured 27.
MINIMUM_LUMA_GAP = 60


def _luma(colour) -> float:
    """Rec. 601 brightness, which is what the eye is doing here."""
    return 0.299 * colour[0] + 0.587 * colour[1] + 0.114 * colour[2]


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

    made = MainWindow()
    made._rebuild_image_viewer(False)
    made.display.load_fits(str(path))
    yield made
    made.close()


@pytest.fixture
def quiet(monkeypatch):
    """Nothing may block while forty dialogs are built."""
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
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)


def _dialogs(window):
    """One of every dialog the application can put on screen.

    Built with real arguments, because most take more than a parent and a
    gate that skipped those would have missed the very windows reported.
    """
    from astropy.table import Table

    from ncrads9.analysis.plot import PlotState
    from ncrads9.catalogs.catalog_set import LoadedCatalog
    from ncrads9.colormaps.color_tags import ColorTag
    from ncrads9.image_servers.servers import SERVERS
    from ncrads9.regions.shapes.circle import Circle
    from ncrads9.ui.dialogs import (
        analysis_text_dialog,
        array_dialog,
        catalog_search_dialog,
        catalog_window,
        centroid_dialog,
        color_tag_dialog,
        colormap_dialog,
        console_dialog,
        contour_dialog,
        crop_parameters_dialog,
        crosshair_dialog,
        frame_3d_dialog,
        grid_dialog,
        group_dialog,
        header_dialog,
        help_contents_dialog,
        histogram_dialog,
        illustrate_dialog,
        image_server_dialog,
        keyboard_shortcuts_dialog,
        mask_dialog,
        movie_dialog,
        notes_dialog,
        page_setup_dialog,
        pan_zoom_rotate_dialog,
        pixel_table_dialog,
        plot_window,
        preferences_dialog,
        print_dialog,
        prism_dialog,
        region_dialog,
        save_dialog,
        scale_dialog,
        smooth_dialog,
        statistics_dialog,
        symbol_editor_dialog,
        tile_dialog,
        vo_query_dialog,
        vo_registry_dialog,
    )

    data = window.frame_manager.current_frame.image_data
    region = Circle(center=(10.0, 10.0), radius=4.0)
    catalog = LoadedCatalog(name="cat", table=Table({"RA": [1.0], "DEC": [2.0]}))
    header = fits.Header({"BITPIX": -32})

    yield "AnalysisTextDialog", analysis_text_dialog.AnalysisTextDialog("T", "body", window)
    yield "ArrayDialog", array_dialog.ArrayDialog(None, window)
    yield "CatalogSearchDialog", catalog_search_dialog.CatalogSearchDialog("cds", window)
    yield "CatalogWindow", catalog_window.CatalogWindow(catalog, window)
    yield "CentroidDialog", centroid_dialog.CentroidDialog(10.0, 30, window)
    yield "ColorTagDialog", color_tag_dialog.ColorTagDialog(ColorTag(start=0.1, stop=0.2), window)
    yield "ColormapDialog", colormap_dialog.ColormapDialog(window)
    yield "ConsoleDialog", console_dialog.ConsoleDialog(window, window)
    yield "ContourDialog", contour_dialog.ContourDialog(window)
    yield "CropParametersDialog", crop_parameters_dialog.CropParametersDialog(window.crop, window)
    yield "CrosshairDialog", crosshair_dialog.CrosshairDialog(window.crosshair, window)
    yield "Frame3DDialog", frame_3d_dialog.Frame3DDialog(window.frame_3d, window)
    yield "GridDialog", grid_dialog.GridDialog(None, window)
    yield "GroupDialog", group_dialog.GroupDialog([region], window)
    yield "HeaderDialog", header_dialog.HeaderDialog(header, window)
    yield "HelpContentsDialog", help_contents_dialog.HelpContentsDialog(window)
    yield "HistogramDialog", histogram_dialog.HistogramDialog(data, window)
    yield "IllustrateDialog", illustrate_dialog.IllustrateDialog(window.illustrate, window)
    yield "ImageServerDialog", image_server_dialog.ImageServerDialog(SERVERS[0], (10.0, 20.0), window)
    yield "KeyboardShortcutsDialog", keyboard_shortcuts_dialog.KeyboardShortcutsDialog(window)
    yield "MaskDialog", mask_dialog.MaskDialog(None, "", window)
    yield "MovieDialog", movie_dialog.MovieDialog(window, False)
    yield "NotesDialog", notes_dialog.NotesDialog(window.notes, window)
    yield "PageSetupDialog", page_setup_dialog.PageSetupDialog(None, window)
    yield "PanZoomRotateDialog", pan_zoom_rotate_dialog.PanZoomRotateDialog(window)
    yield "PixelTableDialog", pixel_table_dialog.PixelTableDialog(data, 5, 5, 5, window)
    yield "PlotWindow", plot_window.PlotWindow(PlotState(), window)
    yield "PreferencesDialog", preferences_dialog.PreferencesDialog(window)
    yield "PrintDialog", print_dialog.PrintDialog(None, window)
    yield "PrismDialog", prism_dialog.PrismDialog(window, window)
    yield "RegionDialog", region_dialog.RegionDialog(region, None, window)
    yield "SaveDialog", save_dialog.SaveDialog(window)
    yield "ScaleDialog", scale_dialog.ScaleDialog(window)
    yield "SmoothDialog", smooth_dialog.SmoothDialog(window)
    yield "StatisticsDialog", statistics_dialog.StatisticsDialog(data, window)
    yield "SymbolEditorDialog", symbol_editor_dialog.SymbolEditorDialog(None, ["RA"], window)
    yield "TileParametersDialog", tile_dialog.TileParametersDialog(window.frame_controller, window)
    yield "DisplaySizeDialog", tile_dialog.DisplaySizeDialog(800, 600, window)
    yield "VOQueryDialog", vo_query_dialog.VOQueryDialog(window, 10.0, 20.0)
    yield "VORegistryDialog", vo_registry_dialog.VORegistryDialog((10.0, 20.0), window)


# -- every popup can be moved ------------------------------------------------------


def test_every_popup_can_be_dragged(window, quiet):
    """The gate for the first fault.

    A window the user can move needs a title bar and must not be
    frameless, and it must not insist on staying above everything --
    which is what "cannot be dragged out of the way" turned out to mean.
    """
    immovable = []
    counted = 0
    for name, dialog in _dialogs(window):
        counted += 1
        flags = dialog.windowFlags()
        kind = flags & Qt.WindowType.WindowType_Mask
        problems = []
        if flags & Qt.WindowType.FramelessWindowHint:
            problems.append("frameless")
        if not flags & Qt.WindowType.WindowTitleHint:
            problems.append("no title bar")
        if flags & Qt.WindowType.WindowStaysOnTopHint:
            problems.append("always on top")
        if kind not in (Qt.WindowType.Dialog, Qt.WindowType.Window):
            problems.append(f"window type {kind}")
        if problems:
            immovable.append(f"{name}: {', '.join(problems)}")
        dialog.close()
    assert counted >= 40, "the gate should cover every dialog"
    assert immovable == [], "\n".join(immovable)


def test_no_window_in_the_application_stays_on_top(window, quiet):
    """Stated separately because it is the specific regression: seven
    dialogs carried the flag, and one more added later would be as hard
    to get out of the way as those were."""
    on_top = [
        name for name, dialog in _dialogs(window) if dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    ]
    assert on_top == []


def test_a_popup_is_not_modal_so_the_image_stays_usable(window, quiet):
    """The non-modal ones must stay non-modal: a modal popup cannot be
    moved aside *and* worked around, which is the same complaint."""
    from PyQt6.QtWidgets import QDialog

    for name in ("HeaderDialog", "StatisticsDialog", "PixelTableDialog", "HelpContentsDialog"):
        dialog = next(d for n, d in _dialogs(window) if n == name)
        assert isinstance(dialog, QDialog)
        assert dialog.windowModality() == Qt.WindowModality.NonModal, name
        dialog.close()


# -- every popup follows the theme -------------------------------------------------


@pytest.mark.parametrize("theme", ["Light", "Dark"])
def test_every_popup_is_readable_under_each_theme(window, quiet, qapp, theme):
    """The gate for the second fault.

    Each dialog is rendered and its background compared with the text
    colour it will draw with. Under Dark this measured a gap of 27 --
    light grey text on Qt's default light grey ground.
    """
    from ncrads9.ui.controllers.edit import THEMES

    THEMES[theme].apply(qapp)
    try:
        unreadable = []
        for name, dialog in _dialogs(window):
            dialog.resize(400, 300)
            dialog.show()
            qapp.processEvents()
            pixmap = QPixmap(400, 300)
            dialog.render(pixmap)
            background = pixmap.toImage().pixelColor(3, 3).getRgb()[:3]
            text = dialog.palette().color(QPalette.ColorRole.WindowText).getRgb()[:3]
            gap = abs(_luma(background) - _luma(text))
            if gap < MINIMUM_LUMA_GAP:
                unreadable.append(f"{name}: background {background} vs text {text}, gap {gap:.0f}")
            dialog.close()
        assert unreadable == [], "\n".join(unreadable)
    finally:
        THEMES["System"].apply(qapp)


def test_the_dark_theme_darkens_a_dialog_not_only_the_main_window(qapp):
    """The bug in one line: `QMainWindow` was styled and nothing else was."""
    from PyQt6.QtWidgets import QDialog

    from ncrads9.ui.controllers.edit import THEMES

    THEMES["Dark"].apply(qapp)
    try:
        dialog = QDialog()
        window_colour = dialog.palette().color(QPalette.ColorRole.Window)
        assert palettes.is_dark(
            dialog.palette()
        ), f"a dialog under Dark should be dark, not {window_colour.name()}"
        dialog.close()
    finally:
        THEMES["System"].apply(qapp)


def test_the_system_theme_keeps_the_desktops_own_colours(qapp):
    """What System means. Ubuntu's dark mode is the desktop's palette, not
    one of ours, so System must restore it rather than impose a palette --
    and must restore it after Dark has replaced it."""
    from ncrads9.ui.controllers.edit import THEMES

    desktop = palettes.build(
        window="#353535",
        window_text="#ffffff",
        base="#2a2a2a",
        alternate_base="#3a3a3a",
        text="#ffffff",
        button="#454545",
        button_text="#ffffff",
        bright_text="#ff0000",
        highlight="#e95420",
        highlighted_text="#ffffff",
        link="#2a7fff",
        disabled_text="#808080",
        tooltip_base="#353535",
        tooltip_text="#ffffff",
    )
    original = qapp.palette()
    qapp.setProperty(palettes.DESKTOP_PALETTE_PROPERTY, None)
    qapp.setPalette(desktop)
    try:
        THEMES["System"].apply(qapp)
        assert palettes.is_dark(qapp.palette()), "System on a dark desktop stays dark"

        THEMES["Dark"].apply(qapp)
        THEMES["System"].apply(qapp)
        assert (
            qapp.palette().color(QPalette.ColorRole.Window).name() == "#353535"
        ), "System must put the desktop's own colours back, not Dark's or Fusion's"
    finally:
        qapp.setProperty(palettes.DESKTOP_PALETTE_PROPERTY, None)
        qapp.setPalette(original)
        THEMES["System"].apply(qapp)


def test_a_palette_sets_the_disabled_colours_too(qapp):
    """A role left at its default is the light patch that shows up in a
    dark window; a greyed control drawn in the enabled colour reads as
    enabled."""
    dark = palettes.dark()
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        enabled = dark.color(QPalette.ColorGroup.Normal, role).name()
        disabled = dark.color(QPalette.ColorGroup.Disabled, role).name()
        assert enabled != disabled, role


def test_is_dark_reads_brightness_not_a_single_channel():
    light = palettes.light()
    dark = palettes.dark()
    assert palettes.is_dark(dark) is True
    assert palettes.is_dark(light) is False


# -- the plots follow the theme ----------------------------------------------------


@pytest.mark.parametrize("theme", ["Light", "Dark"])
def test_a_matplotlib_figure_follows_the_theme(window, quiet, qapp, theme):
    """A `Figure` knows nothing about Qt: left alone it draws on white with
    black text, so in a dark window every plot was a bright panel."""
    from ncrads9.ui.controllers.edit import THEMES
    from ncrads9.ui.dialogs.histogram_dialog import HistogramDialog

    THEMES[theme].apply(qapp)
    try:
        data = window.frame_manager.current_frame.image_data
        dialog = HistogramDialog(data, window)
        try:
            face = dialog.figure.get_facecolor()[:3]
            axes = dialog.figure.get_axes()[0]
            expected_dark = theme == "Dark"
            # The figure's ground must be on the same side of mid-grey as
            # the interface's.
            assert (sum(face) / 3 < 0.5) is expected_dark, f"{theme}: figure face {face}"
            assert tuple(axes.get_facecolor()[:3]) == tuple(face), "the axes match the figure"
            label = axes.xaxis.label.get_color()
            assert label != "black" if expected_dark else True
        finally:
            dialog.close()
    finally:
        THEMES["System"].apply(qapp)


def test_the_plot_helper_reads_the_widgets_palette(qapp):
    """Not a theme *name*: under System the colours are the desktop's and
    there is no name to look up."""
    from PyQt6.QtWidgets import QWidget

    from ncrads9.ui import plot_theme

    widget = QWidget()
    widget.setPalette(palettes.dark())
    chosen = plot_theme.colours(widget)
    assert chosen["dark"] is True

    widget.setPalette(palettes.light())
    assert plot_theme.colours(widget)["dark"] is False
    widget.close()


def test_styling_a_figure_leaves_a_gridless_plot_gridless(qapp):
    """A plot that deliberately has no grid must not gain one."""
    from matplotlib.figure import Figure

    from ncrads9.ui import plot_theme

    figure = Figure()
    axes = figure.add_subplot(111)
    axes.plot([0, 1], [0, 1])
    plot_theme.style_figure(figure)
    assert not axes.xaxis._major_tick_kw.get("gridOn", False)
