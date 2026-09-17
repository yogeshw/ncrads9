# This file is part of ncrads9.
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

Every DS9 menu and submenu carries a dashed line at the top; clicking it
tears the menu off into a window of its own that stays open. For a menu
worked through repeatedly -- Scale, Colormap, Region Shape -- it turns a
click-and-hold into a panel sitting next to the image.

Qt has the same feature, so this is not a reimplementation: `QMenu`
already knows how to tear itself off. What is needed is to *ask* every
menu to allow it, including the ones in the tool windows' own menu bars,
and to fix what Qt's torn-off window gets wrong for this application.

**Asking every menu.** `enable` walks the whole menu tree rather than
naming menus, so a submenu added later is detachable without anyone
remembering to add it -- the same reason the menu tables are tables.

**The window Qt gives you.** A torn-off `QMenu` is a `Qt.WindowType.Tool`,
and a tool window with a parent is *always kept above it*. That is the
fault that was reported for the popups -- a window that floats over the
image and cannot be sent behind it -- arriving again by a different route,
and DS9's own tear-offs are ordinary toplevels that can go behind. So
`TearOffWatcher` re-flags each one into an ordinary window as it appears,
and gives it a title naming the application, since otherwise the window
list shows a bare word like `Shape`.

The re-flagging is deferred to the event loop rather than done inside the
show event: `setWindowFlags` hides and re-shows the widget, and doing that
to a widget in the middle of being shown is the kind of surgery on Qt's
own dispatch that this codebase has been bitten by before.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Iterator

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMenu, QMenuBar, QWidget

#: Qt's class name for the window a torn-off menu lives in. It is private
#: -- there is no importable type -- so it is recognised by name.
TORN_OFF_CLASS = "QTornOffMenu"

#: Marks a torn-off window this module has already adopted. `setWindowFlags`
#: shows the widget again, which would otherwise arrive as a second show
#: event and adopt it once more.
ADOPTED = "ncrads9_tearoff_adopted"

#: Marks a window whose menu bar has been walked, so showing it again does
#: not walk it again.
WALKED = "ncrads9_tearoff_walked"

#: An ordinary, movable window that can be sent behind the main one --
#: deliberately not `Tool`, which Qt uses and which cannot.
WINDOW_FLAGS = (
    Qt.WindowType.Window
    | Qt.WindowType.WindowTitleHint
    | Qt.WindowType.WindowSystemMenuHint
    | Qt.WindowType.WindowCloseButtonHint
)


def menu_bars(root: QWidget | QMenuBar | QMenu | None) -> list[QMenuBar | QMenu]:
    """The menu bars `root` holds, whichever way it holds them.

    `QMainWindow` owns one through `setMenuBar`; the tool windows here are
    dialogs that put a `QMenuBar` in their layout instead, which
    `menuBar()` knows nothing about. Both are looked for, so neither kind
    of window is quietly skipped.
    """
    if root is None:
        return []
    if isinstance(root, QMenuBar | QMenu):
        return [root]
    if not isinstance(root, QWidget):
        return []
    owned = root.menuBar() if hasattr(root, "menuBar") else None
    if owned is not None:
        return [owned]
    return list(root.findChildren(QMenuBar))


def menus(root: QWidget | QMenuBar | QMenu | None) -> Iterator[QMenu]:
    """Every menu below `root`, submenus included, each yielded once.

    Walked rather than listed: a submenu added later is detachable without
    anyone remembering to add it here.

    Args:
        root: A menu bar, a menu, or a window holding either.

    Yields:
        The menus, parents before children.
    """
    seen: set[int] = set()
    pending: list[QMenuBar | QMenu] = menu_bars(root)
    while pending:
        current = pending.pop(0)
        for action in current.actions():
            submenu = action.menu()
            if submenu is None or id(submenu) in seen:
                continue
            seen.add(id(submenu))
            yield submenu
            pending.append(submenu)


def enable(root: QWidget | QMenuBar | QMenu | None, enabled: bool = True) -> int:
    """Make every menu below `root` detachable, or stop it being so.

    Turning it off also puts away any menu already torn off, since the
    window would otherwise outlive the setting that allowed it.

    Args:
        root: As `menus`.
        enabled: Whether the menus may be torn off.

    Returns:
        How many menus were set, which is what a test counts.
    """
    count = 0
    for menu in menus(root):
        menu.setTearOffEnabled(enabled)
        if not enabled and menu.isTearOffMenuVisible():
            menu.hideTearOffMenu()
        count += 1
    return count


def enable_everywhere(enabled: bool = True) -> int:
    """Every window the application has open, the tool windows included.

    What a change of the preference needs: a plot window already on screen
    should start or stop offering tear-offs with everything else.
    """
    count = 0
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QMenu):
            continue
        count += enable(widget, enabled)
    return count


def torn_off_windows() -> list[QMenu]:
    """Every menu currently detached, across the whole application."""
    return [
        widget
        for widget in QApplication.topLevelWidgets()
        if isinstance(widget, QMenu) and widget.metaObject().className() == TORN_OFF_CLASS
    ]


class TearOffWatcher(QObject):
    """Turns Qt's torn-off menus into ordinary windows, and keeps new
    windows' menus detachable.

    One object on the `QApplication` rather than a call in each dialog:
    six tool windows build their own menu bars today, and the seventh
    would have been written without the call.
    """

    def __init__(self, enabled: bool = True) -> None:
        """
        Args:
            enabled: What new windows' menus start as. `enable` on the
                whole application is still the way to change the setting;
                this is what a window shown afterwards inherits.
        """
        super().__init__()
        self.enabled = enabled

    def install(self, app: QApplication | None = None) -> None:
        """Watch the application for windows appearing."""
        app = app or QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        """Adopt torn-off menus, and walk a new window's menu bar.

        Never consumes the event.
        """
        if event is None or watched is None or event.type() != QEvent.Type.Show:
            return False
        if isinstance(watched, QMenu):
            if watched.metaObject().className() == TORN_OFF_CLASS:
                self._adopt(watched)
            return False
        if isinstance(watched, QWidget) and watched.isWindow():
            self._walk(watched)
        return False

    # -- the two jobs --------------------------------------------------------

    def _adopt(self, window: QMenu) -> None:
        """Make one torn-off menu an ordinary window, on the next turn."""
        if window.property(ADOPTED):
            return
        window.setProperty(ADOPTED, True)
        QTimer.singleShot(0, lambda: self._reflag(window))

    @staticmethod
    def _reflag(window: QMenu) -> None:
        """Re-flag and re-show, guarding against the window having gone.

        Deferred, so by the time this runs the user may have closed it and
        Qt may have deleted it -- reaching a deleted C++ object through its
        Python wrapper raises rather than crashing, which is what the guard
        is for.
        """
        try:
            title = window.windowTitle()
            window.setWindowTitle(f"NCRADS9 -- {title}" if title else "NCRADS9 menu")
            window.setWindowFlags(WINDOW_FLAGS)
            window.show()
        except RuntimeError:
            return

    def _walk(self, window: QWidget) -> None:
        """Make a newly shown window's own menus detachable.

        Tool windows with menu bars -- the plot window, the catalogue
        window, Prism, Notes, the 3D panel -- get the setting without each
        having to ask for it.

        No test for whether the window *has* menus: they are dialogs that
        keep a `QMenuBar` in their layout, so they have no `menuBar()` to
        ask, and `menus` yields nothing for a window with none anyway.
        """
        if window.property(WALKED):
            return
        window.setProperty(WALKED, True)
        enable(window, self.enabled)
