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
Detachable menus, as DS9 has them.

Qt can already tear a `QMenu` off, so the work is in asking every menu --
including the ones in the tool windows' own menu bars, which are dialogs
holding a `QMenuBar` in a layout rather than windows with a `menuBar()` --
and in the window Qt hands back.

That window is the part worth gating. Qt makes a torn-off menu a
`Qt.WindowType.Tool`, and a tool window with a parent is *always kept
above it*: exactly the fault that was reported for the popups, arriving
again by a different route. DS9's own tear-offs are ordinary toplevels
that can be pushed behind the image, and so are these.

The other half is that a torn-off menu must keep *working*. Qt's copy
shares the source menu's `QAction` objects rather than duplicating them,
so this is Qt's guarantee rather than ours -- but it is the whole point of
the feature, and if it ever stopped holding the menus would look right and
do nothing.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QPalette, QPixmap

from ncrads9.ui import tearoff
from ncrads9.utils import preference_defs

#: A luma gap below this reads as "text the same colour as its background".
MINIMUM_LUMA_GAP = 60


def _luma(colour: QColor) -> float:
    return 0.299 * colour.red() + 0.587 * colour.green() + 0.114 * colour.blue()


def _settle(qapp) -> None:
    """Let the deferred re-flagging run.

    The watcher re-flags on the next turn of the loop rather than inside
    the show event, so a test has to give it that turn.
    """
    qapp.processEvents()
    qapp.sendPostedEvents(None, 0)
    qapp.processEvents()


def _torn_holding(action: QAction):
    """The torn-off window showing `action`, found by object identity.

    Several menus offer a `Circle`; only one of them offers *this*
    `Circle`, and the torn-off copy shares the original action rather than
    making one of its own.
    """
    for window in tearoff.torn_off_windows():
        if any(candidate is action for candidate in window.actions()):
            return window
    return None


@pytest.fixture
def window(qapp, monkeypatch):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    real = Preferences.get
    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else real(self, key, default),
    )
    made = MainWindow()
    made._rebuild_image_viewer(False)
    frame = made.frame_manager.current_frame
    frame.image_data = np.arange(64 * 64, dtype=np.float32).reshape(64, 64)
    frame.original_image_data = frame.image_data
    made.show()
    qapp.processEvents()
    yield made
    for menu in tearoff.menus(made):
        if menu.isTearOffMenuVisible():
            menu.hideTearOffMenu()
    made.close()
    qapp.processEvents()


def _set_tearoff(window, enabled: bool) -> None:
    """Change the preference the way the Preferences dialog does."""
    prefs = window.edit.preferences_dict()
    prefs["menu_tearoff"] = enabled
    window.edit.apply_preferences(prefs, persist=False, show_message=False)


# -- every menu, and every submenu -------------------------------------------------


def test_the_setting_is_on_by_default_as_it_is_in_ds9():
    assert preference_defs.by_key()["menu_tearoff"].default is True


def test_it_is_a_preference_under_ds9s_own_topic():
    """DS9 keeps its menu settings under `Menus and Buttons`, and so do we,
    so somebody who knows where it lives in DS9 finds it here."""
    preference = preference_defs.by_key()["menu_tearoff"]
    assert preference.topic == "Menus and Buttons"
    assert preference.kind == "bool"


def test_every_menu_in_the_main_window_can_be_detached(window):
    found = list(tearoff.menus(window))
    assert len(found) > 80, "the walk should reach the whole menu tree"
    stuck = [menu.title() for menu in found if not menu.isTearOffEnabled()]
    assert stuck == [], f"not detachable: {stuck}"


def test_the_walk_reaches_a_submenu_three_deep(window):
    """Region -> Shape -> Point. DS9 tears off submenus too, and a walk that
    stopped at the top level would look right from the menu bar."""
    deep = window.menu_bar.region_point_menu
    assert deep in list(tearoff.menus(window))
    assert deep.isTearOffEnabled()


def test_the_walk_yields_each_menu_once(window):
    found = list(tearoff.menus(window))
    assert len(found) == len({id(menu) for menu in found})


def test_a_menu_added_later_is_detachable_when_the_setting_is_applied(window):
    """The walk is a walk, not a list: a submenu added after startup needs
    no line anywhere for the next apply to reach it."""
    late = window.menu_bar.region_menu.addMenu("Late")
    late.addAction("Something")
    assert not late.isTearOffEnabled()
    _set_tearoff(window, True)
    assert late.isTearOffEnabled()


# -- the window Qt hands back ------------------------------------------------------


def test_a_detached_menu_is_an_ordinary_movable_window(window, qapp):
    """The gate. Qt makes it a `Tool`, which is always kept above its
    parent -- the reported fault about popups that cannot be pushed out of
    the way, by another route."""
    window.menu_bar.region_shape_menu.showTearOffMenu()
    _settle(qapp)

    torn = tearoff.torn_off_windows()
    assert len(torn) == 1
    detached = torn[0]
    flags = detached.windowFlags()
    kind = flags & Qt.WindowType.WindowType_Mask
    assert kind == Qt.WindowType.Window, f"window kind {int(kind)}, not an ordinary window"
    assert not flags & Qt.WindowType.WindowStaysOnTopHint
    assert not flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowTitleHint, "no title bar to drag it by"


def test_a_detached_menus_title_names_the_application(window, qapp):
    """`Shape` alone in a window list says nothing about what it belongs
    to, and several menus share a word."""
    window.menu_bar.region_shape_menu.showTearOffMenu()
    _settle(qapp)
    title = tearoff.torn_off_windows()[0].windowTitle()
    assert title.startswith("NCRADS9")
    assert "Shape" in title


def test_two_menus_can_be_detached_at_once(window, qapp):
    """The point of the feature: Scale open beside Colormap."""
    window.menu_bar.scale_menu.showTearOffMenu()
    window.menu_bar.region_shape_menu.showTearOffMenu()
    _settle(qapp)
    assert len(tearoff.torn_off_windows()) == 2


def test_closing_a_detached_menu_puts_it_back(window, qapp):
    """Closing the window must return the menu to normal and let it be
    detached again -- the close button is one we asked Qt for, so the round
    trip is worth checking rather than assuming."""
    shape_menu = window.menu_bar.region_shape_menu
    shape_menu.showTearOffMenu()
    _settle(qapp)
    detached = tearoff.torn_off_windows()[0]

    detached.close()
    _settle(qapp)
    assert not shape_menu.isTearOffMenuVisible()
    assert tearoff.torn_off_windows() == []

    shape_menu.showTearOffMenu()
    _settle(qapp)
    assert shape_menu.isTearOffMenuVisible()
    again = tearoff.torn_off_windows()
    assert len(again) == 1
    assert again[0].windowTitle().startswith("NCRADS9")


def test_the_adoption_happens_once_per_window(window, qapp):
    """`setWindowFlags` shows the widget again, which arrives as a second
    show event; adopting twice would re-title an already-titled window."""
    window.menu_bar.region_shape_menu.showTearOffMenu()
    _settle(qapp)
    detached = tearoff.torn_off_windows()[0]
    once = detached.windowTitle()
    _settle(qapp)
    assert detached.windowTitle() == once
    assert once.count("NCRADS9") == 1


# -- a detached menu must still work -----------------------------------------------


def test_an_action_chosen_in_a_detached_menu_reaches_the_application(window, qapp):
    """Without this the feature is decorative."""
    from ncrads9.ui.widgets.region_overlay import RegionMode

    shape_menu = window.menu_bar.region_shape_menu
    ellipse = window.menu_bar.region_shape_actions["ellipse"]
    shape_menu.showTearOffMenu()
    _settle(qapp)

    detached = _torn_holding(ellipse)
    assert detached is not None, "the detached window does not hold the menu's own actions"
    next(action for action in detached.actions() if action is ellipse).trigger()
    qapp.processEvents()
    assert window.image_viewer.region_overlay.mode is RegionMode.ELLIPSE


def test_a_checkable_action_stays_in_step_with_the_menu(window, qapp):
    """Choosing a shape from the menu bar must tick it in the detached copy
    too, or the two disagree about what is armed."""
    shape_menu = window.menu_bar.region_shape_menu
    box = window.menu_bar.region_shape_actions["box"]
    shape_menu.showTearOffMenu()
    _settle(qapp)
    detached = _torn_holding(box)
    assert detached is not None

    window.menu_bar.region_shape_actions["box"].trigger()
    qapp.processEvents()
    assert next(a for a in detached.actions() if a is box).isChecked()

    window.menu_bar.region_shape_actions["circle"].trigger()
    qapp.processEvents()
    assert not next(a for a in detached.actions() if a is box).isChecked()


def test_an_action_added_after_detaching_appears_in_the_detached_menu(window, qapp):
    """The Color menu grows a row when a user colour table is loaded, and
    a detached copy that missed it would be wrong until reopened."""
    colormap_menu = window.menu_bar.user_colormap_menu
    colormap_menu.showTearOffMenu()
    _settle(qapp)
    detached = tearoff.torn_off_windows()[0]
    before = len(detached.actions())

    added = window.menu_bar.add_user_colormap_action("a-late-table")
    qapp.processEvents()
    assert len(detached.actions()) == before + 1
    assert any(action is added for action in detached.actions())


# -- the preference ----------------------------------------------------------------


def test_turning_it_off_makes_every_menu_undetachable(window):
    _set_tearoff(window, False)
    assert [m.title() for m in tearoff.menus(window) if m.isTearOffEnabled()] == []


def test_turning_it_off_puts_away_a_menu_already_detached(window, qapp):
    """The window would otherwise outlive the setting that allowed it."""
    shape_menu = window.menu_bar.region_shape_menu
    shape_menu.showTearOffMenu()
    _settle(qapp)
    assert shape_menu.isTearOffMenuVisible()

    _set_tearoff(window, False)
    qapp.processEvents()
    assert not shape_menu.isTearOffMenuVisible()


def test_turning_it_back_on_restores_every_menu(window):
    _set_tearoff(window, False)
    _set_tearoff(window, True)
    stuck = [m.title() for m in tearoff.menus(window) if not m.isTearOffEnabled()]
    assert stuck == []


# -- the tool windows' own menu bars -----------------------------------------------


def test_a_tool_windows_menus_are_detachable_too(window, qapp):
    """DS9's tool windows have menu bars and tear-offs, and so do ours.
    Through the watcher rather than a call in each dialog: six tool windows
    build their own bars today and the seventh would have been written
    without it."""
    from ncrads9.analysis.plot import PlotState
    from ncrads9.ui.dialogs.plot_window import PlotWindow

    plot = PlotWindow(PlotState(), window)
    plot.show()
    qapp.processEvents()
    found = list(tearoff.menus(plot))
    assert len(found) >= 4, "the plot window's own menus were not found"
    assert [m.title() for m in found if not m.isTearOffEnabled()] == []
    plot.close()
    plot.deleteLater()
    qapp.processEvents()


def test_a_tool_window_shown_while_it_is_off_does_not_offer_it(window, qapp):
    from ncrads9.ui.dialogs.notes_dialog import NotesDialog

    _set_tearoff(window, False)
    notes = NotesDialog(window.notes, window)
    notes.show()
    qapp.processEvents()
    assert [m.title() for m in tearoff.menus(notes) if m.isTearOffEnabled()] == []
    notes.close()
    notes.deleteLater()
    qapp.processEvents()


def test_a_menu_bar_kept_in_a_layout_is_found(window, qapp):
    """`QMainWindow` owns its bar through `setMenuBar`; these dialogs put a
    `QMenuBar` in their layout instead, where `menuBar()` cannot see it. A
    walk that only asked `menuBar()` skipped every tool window in silence."""
    from ncrads9.ui.dialogs.notes_dialog import NotesDialog

    notes = NotesDialog(window.notes, window)
    assert not hasattr(notes, "menuBar")
    assert tearoff.menu_bars(notes), "a bar held in a layout was not found"
    assert list(tearoff.menus(notes))
    notes.close()
    notes.deleteLater()
    qapp.processEvents()


def test_a_window_with_no_menus_is_harmless(window, qapp):
    from ncrads9.ui.dialogs.header_dialog import HeaderDialog

    header = HeaderDialog(None, window)
    header.show()
    qapp.processEvents()
    assert list(tearoff.menus(header)) == []
    assert tearoff.enable(header, True) == 0
    header.close()
    header.deleteLater()
    qapp.processEvents()


# -- readable, like every other window ---------------------------------------------


@pytest.mark.parametrize("theme", ["Light", "Dark"])
def test_a_detached_menu_is_readable_under_each_theme(window, qapp, theme):
    """A torn-off menu is a `QMenu`, so the theme's stylesheet reaches it --
    asserted rather than assumed, since it is a window of its own and the
    popup gate walks a list that cannot include it."""
    from ncrads9.ui.controllers.edit import THEMES

    try:
        THEMES[theme].apply(qapp)
        qapp.processEvents()
        window.menu_bar.region_shape_menu.showTearOffMenu()
        _settle(qapp)
        detached = tearoff.torn_off_windows()[0]
        detached.resize(240, 400)
        qapp.processEvents()

        pixmap = QPixmap(240, 400)
        detached.render(pixmap)
        image = pixmap.toImage()
        counted = Counter(image.pixelColor(x, y).name() for y in range(5, 395, 2) for x in range(5, 235, 2))
        background = QColor(counted.most_common(1)[0][0])
        gap = max(
            (abs(_luma(QColor(name)) - _luma(background)) for name, count in counted.items() if count >= 25),
            default=0.0,
        )
        assert gap >= MINIMUM_LUMA_GAP, f"{theme}: widest gap {gap:.0f} on {background.name()}"
        window.menu_bar.region_shape_menu.hideTearOffMenu()
        qapp.processEvents()
    finally:
        THEMES["System"].apply(qapp)


def test_the_detached_window_follows_the_palette(window, qapp):
    """It is styled as a menu, not left with Qt's own default colours --
    the grey-on-grey fault, which a separate toplevel is where it would
    reappear."""
    from ncrads9.ui.controllers.edit import THEMES

    try:
        THEMES["Dark"].apply(qapp)
        qapp.processEvents()
        window.menu_bar.scale_menu.showTearOffMenu()
        _settle(qapp)
        detached = tearoff.torn_off_windows()[0]
        from ncrads9.ui.themes import palettes

        assert palettes.is_dark(detached.palette()), (
            f"a detached menu under Dark should be dark, not "
            f"{detached.palette().color(QPalette.ColorRole.Window).name()}"
        )
        window.menu_bar.scale_menu.hideTearOffMenu()
        qapp.processEvents()
    finally:
        THEMES["System"].apply(qapp)


# -- the deferred re-flag ----------------------------------------------------------


def test_re_flagging_a_window_that_has_gone_is_not_an_error(qapp):
    """The re-flag runs on the next turn of the loop, by which time the
    user may have closed the window and Qt deleted it."""
    from PyQt6.QtWidgets import QMenu

    doomed = QMenu()
    doomed.addAction("One")
    doomed.deleteLater()
    qapp.processEvents()
    tearoff.TearOffWatcher._reflag(doomed)  # must not raise


def test_the_watcher_never_swallows_an_event(window, qapp):
    """An event filter that consumed a show event would stop the window
    appearing at all."""
    from PyQt6.QtCore import QEvent

    watcher = window.edit.tearoff
    event = QEvent(QEvent.Type.Show)
    assert watcher.eventFilter(window, event) is False
    assert watcher.eventFilter(None, None) is False
    assert watcher.eventFilter(window, QEvent(QEvent.Type.Paint)) is False
