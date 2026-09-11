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
Matplotlib figures that follow the interface's colours.

A `Figure` knows nothing about Qt. Left alone it draws on white with
black text, so in a dark window -- ours, or the desktop's own dark mode --
every plot is a bright panel with a light border, and the four dialogs
that embed one looked like they had missed the theme.

The colours are read off the *widget's* palette rather than from a theme
name, because under the System theme the colours are the desktop's and we
never chose them: there is no name to look up.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QWidget

from .themes import palettes

#: How far the grid and the spines are faded from the text colour.
GRID_ALPHA = 0.25
SPINE_ALPHA = 0.6


def colours(widget: QWidget | None = None) -> dict[str, str]:
    """The figure colours for a widget's palette.

    Args:
        widget: The widget the figure is drawn in. None falls back to the
            application palette.

    Returns:
        `face`, `text` and `grid` as `#rrggbb` strings.
    """
    if widget is not None:
        palette = widget.palette()
    else:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        palette = app.palette() if app is not None else QPalette()

    face = palette.color(QPalette.ColorRole.Base)
    text = palette.color(QPalette.ColorRole.Text)
    return {
        "face": face.name(),
        "text": text.name(),
        "dark": palettes.is_dark(palette),
    }


def style_figure(figure, widget: QWidget | None = None) -> None:
    """Paint a figure and every axes on it in the interface's colours.

    Call it after the axes are built: it walks the axes the figure has,
    so a figure styled before anything was plotted on it would keep its
    white axes.
    """
    chosen = colours(widget)
    face, text = chosen["face"], chosen["text"]

    figure.set_facecolor(face)
    figure.set_edgecolor(face)

    for axes in figure.get_axes():
        axes.set_facecolor(face)
        axes.tick_params(colors=text, which="both")
        for spine in axes.spines.values():
            spine.set_color(text)
            spine.set_alpha(SPINE_ALPHA)
        axes.xaxis.label.set_color(text)
        axes.yaxis.label.set_color(text)
        if axes.get_title():
            axes.title.set_color(text)
        # Only restyle a grid that is already on: turning one on here
        # would add a grid to a plot that deliberately has none.
        if axes.xaxis._major_tick_kw.get("gridOn") or axes.yaxis._major_tick_kw.get("gridOn"):
            axes.grid(True, color=text, alpha=GRID_ALPHA)
        legend = axes.get_legend()
        if legend is not None:
            legend.get_frame().set_facecolor(face)
            legend.get_frame().set_edgecolor(text)
            for entry in legend.get_texts():
                entry.set_color(text)


def style_canvas(canvas, widget: QWidget | None = None) -> None:
    """Style a canvas's figure and repaint it."""
    style_figure(canvas.figure, widget if widget is not None else canvas)
    canvas.draw_idle()
