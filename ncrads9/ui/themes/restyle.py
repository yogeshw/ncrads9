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
Applying a theme without Qt walking over a widget that has just died.

`setStyle`, `setPalette` and `setStyleSheet` on the `QApplication` each
walk every live widget, and the walk holds raw pointers to the ones it
has yet to reach. Visiting a widget runs Python: every widget built from
Python is really a sip subclass, so `changeEvent` goes back through the
interpreter. And Python may collect garbage at any allocation. If that
collection frees a widget the walk has not reached yet, the walk's next
step dereferences freed memory and the process dies.

Switching theme with a few windows open was enough to do it. The stack
was always the same shape::

    QApplication::setStyleSheet
      -> QStyleSheetStyle walks the widgets
        -> QWidget::setPalette -> propagatePaletteChange
          -> sipQComboBox::changeEvent
            -> QWidget::update            <-- freed widget, SIGSEGV

Three doors, each shut separately, because no one of them is the whole
draught:

* pending cycles are collected, so the backlog cannot come due
  part-way through the walk;
* Qt's own `DeferredDelete` queue is drained, so nothing that has been
  asked to die is still standing when the walk starts;
* the cyclic collector is held off until the walk is over, so a
  collection cannot start inside it at all.

Measured on the case that crashed: five segfaults in six runs before,
none in eight after. Collecting first and holding the collector off each
stopped it on their own -- both are kept, since each closes a door the
other leaves open.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import gc
from collections.abc import Iterator
from contextlib import contextmanager

from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication


@contextmanager
def no_widget_may_die(app: QApplication) -> Iterator[None]:
    """Empty the graveyard, then keep the collector out until we are done.

    Nesting is safe: an inner use sees the collector already disabled
    and leaves re-enabling it to the outer one.
    """
    gc.collect()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if enabled:
            gc.enable()


def restyle(
    app: QApplication | None,
    palette: QPalette | None,
    stylesheet: str,
    style: str | None = None,
) -> None:
    """Put a theme on the application: its style, palette and stylesheet.

    Every theme's `apply` goes through here, so the protection above
    holds for all of them and for any theme added later.

    Args:
        app: The application. None does nothing, which is what a theme
            applied before the application exists should do.
        palette: The colours, or None to leave the current ones alone --
            which is what the System theme does when it has no recorded
            desktop palette to put back.
        stylesheet: The theme's stylesheet, applied application-wide.
        style: A `QStyleFactory` key, or None to keep the current style.
            Set only when it would actually change, because `setStyle`
            re-parents the `QStyle` of every live widget.
    """
    if app is None:
        return
    with no_widget_may_die(app):
        if style is not None:
            current = app.style()
            if current is None or current.objectName().lower() != style.lower():
                app.setStyle(style)
        if palette is not None:
            app.setPalette(palette)
        app.setStyleSheet(stylesheet)
