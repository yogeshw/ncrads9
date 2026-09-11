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
The colours a theme sets, as a `QPalette` rather than only a stylesheet.

A stylesheet styles the widgets it names. The themes named `QMainWindow`
and gave `QWidget` a text colour -- so under Dark the *main window* went
dark while every dialog kept Qt's default light grey background and wore
the dark theme's light grey text on it. Grey on grey: the popups were
unreadable, which is what was reported.

Naming `QDialog` too would fix those particular windows and leave the
next one to be written broken again. A palette is the right instrument:
Qt resolves it for every widget, including ones no rule mentions, and
including the parts of a widget a stylesheet cannot reach.

The System theme sets no palette of its own. It restores the one the
desktop handed us at startup, which is how Ubuntu's own dark mode shows
through -- imposing a palette there, even a dark one, would override the
user's actual desktop colours.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

#: Where the desktop's own palette is kept, on the `QApplication`. Stored
#: once, before any theme has had a chance to replace it.
DESKTOP_PALETTE_PROPERTY = "ncrads9_desktop_palette"


def remember_desktop_palette(app: QApplication | None = None) -> QPalette | None:
    """Keep the palette the platform gave us, the first time we are asked.

    Called before a theme replaces it. Recording it once is what lets the
    System theme put it back: by then the application's palette is
    whatever the last theme set, and the desktop's is gone.
    """
    app = app or QApplication.instance()
    if app is None:
        return None
    kept = app.property(DESKTOP_PALETTE_PROPERTY)
    if isinstance(kept, QPalette):
        return kept
    palette = QPalette(app.palette())
    app.setProperty(DESKTOP_PALETTE_PROPERTY, palette)
    return palette


def desktop_palette(app: QApplication | None = None) -> QPalette | None:
    """The palette the desktop gave us, or None if it was never recorded."""
    app = app or QApplication.instance()
    if app is None:
        return None
    kept = app.property(DESKTOP_PALETTE_PROPERTY)
    return QPalette(kept) if isinstance(kept, QPalette) else None


def build(
    window: str,
    window_text: str,
    base: str,
    alternate_base: str,
    text: str,
    button: str,
    button_text: str,
    bright_text: str,
    highlight: str,
    highlighted_text: str,
    link: str,
    disabled_text: str,
    tooltip_base: str,
    tooltip_text: str,
) -> QPalette:
    """One palette from a set of colours.

    Every role Qt consults for an ordinary widget is set, because a role
    left at its default is the one that shows up as a light patch in a
    dark window.
    """
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: window,
        QPalette.ColorRole.WindowText: window_text,
        QPalette.ColorRole.Base: base,
        QPalette.ColorRole.AlternateBase: alternate_base,
        QPalette.ColorRole.Text: text,
        QPalette.ColorRole.Button: button,
        QPalette.ColorRole.ButtonText: button_text,
        QPalette.ColorRole.BrightText: bright_text,
        QPalette.ColorRole.Highlight: highlight,
        QPalette.ColorRole.HighlightedText: highlighted_text,
        QPalette.ColorRole.Link: link,
        QPalette.ColorRole.LinkVisited: link,
        QPalette.ColorRole.ToolTipBase: tooltip_base,
        QPalette.ColorRole.ToolTipText: tooltip_text,
        QPalette.ColorRole.PlaceholderText: disabled_text,
    }
    for role, colour in roles.items():
        palette.setColor(role, QColor(colour))

    # Greyed-out controls need saying separately, or a disabled label is
    # drawn in the enabled text colour and reads as enabled.
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.HighlightedText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(disabled_text))
    return palette


#: The Dark theme's colours, matching its stylesheet's own `#1e1e1e`
#: window and `#d4d4d4` text so a styled widget and an unstyled one agree.
DARK = dict(
    window="#1e1e1e",
    window_text="#d4d4d4",
    base="#252526",
    alternate_base="#2d2d30",
    text="#d4d4d4",
    button="#333337",
    button_text="#d4d4d4",
    bright_text="#ffffff",
    highlight="#094771",
    highlighted_text="#ffffff",
    link="#4ea1d3",
    disabled_text="#7a7a7a",
    tooltip_base="#252526",
    tooltip_text="#d4d4d4",
)

#: The Light theme's, matching its `#f5f5f5` window.
LIGHT = dict(
    window="#f5f5f5",
    window_text="#202020",
    base="#ffffff",
    alternate_base="#f0f0f0",
    text="#202020",
    button="#e8e8e8",
    button_text="#202020",
    bright_text="#ffffff",
    highlight="#2f6fb5",
    highlighted_text="#ffffff",
    link="#1a5fb4",
    disabled_text="#9a9a9a",
    tooltip_base="#ffffdc",
    tooltip_text="#202020",
)


def dark() -> QPalette:
    """The Dark theme's palette."""
    return build(**DARK)


def light() -> QPalette:
    """The Light theme's palette."""
    return build(**LIGHT)


def is_dark(palette: QPalette) -> bool:
    """Whether a palette's window colour is a dark one.

    What the plot styling asks, so a matplotlib figure can follow the
    theme it is sitting in -- including the desktop's own, which we did
    not choose and cannot look up by name.
    """
    colour = palette.color(QPalette.ColorRole.Window)
    # Rec. 601 luma: a plain mean calls mid blues light that do not read
    # as light.
    luma = 0.299 * colour.redF() + 0.587 * colour.greenF() + 0.114 * colour.blueF()
    return luma < 0.5
