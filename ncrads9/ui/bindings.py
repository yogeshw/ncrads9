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
What the keyboard does, and how to change it.

DS9's keyboard shortcuts are fixed in its source (`ds9.tcl:459` and the
menus' accelerators). Ours are a table with a preference behind each, so a
shortcut can be changed and kept -- which is what the Keyboard Shortcuts
editor edits.

Only the commands worth a shortcut are in the table. Every menu entry
having one is not a kindness: it makes a list nobody reads and takes
combinations away from the ones that matter.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QKeySequence

#: Where a shortcut override is kept: `shortcut.<name>`.
PREFIX = "shortcut."


@dataclass(frozen=True)
class Binding:
    """One command that can have a shortcut.

    Attributes:
        name: What the preference calls it.
        label: What the editor calls it.
        action: The `MenuBar` attribute holding its `QAction`.
        default: The shortcut it has unless one is set.
    """

    name: str
    label: str
    action: str
    default: str


#: Every command with a shortcut, grouped as the menus group them.
BINDINGS: tuple[Binding, ...] = (
    Binding("open", "Open", "action_open", "Ctrl+O"),
    Binding("save", "Save", "action_save", "Ctrl+S"),
    Binding("save_as", "Save As", "action_save_as", "Ctrl+Shift+S"),
    Binding("print", "Print", "action_print", "Ctrl+P"),
    Binding("page_setup", "Page Setup", "action_page_setup", "Ctrl+Shift+P"),
    Binding("console", "Python Console", "action_console", "Ctrl+`"),
    Binding("exit", "Exit", "action_exit", "Ctrl+Q"),
    Binding("undo", "Undo", "action_undo", "Ctrl+Z"),
    Binding("redo", "Redo", "action_redo", "Ctrl+Shift+Z"),
    Binding("cut", "Cut", "action_cut", "Ctrl+X"),
    Binding("copy", "Copy", "action_copy", "Ctrl+C"),
    Binding("paste", "Paste", "action_paste", "Ctrl+V"),
    Binding("preferences", "Preferences", "action_preferences", "Ctrl+,"),
    Binding("zoom_in", "Zoom In", "action_zoom_in", "Ctrl++"),
    Binding("zoom_out", "Zoom Out", "action_zoom_out", "Ctrl+-"),
    Binding("zoom_fit", "Zoom to Fit", "action_zoom_fit", "Ctrl+0"),
    Binding("new_frame", "New Frame", "action_new_frame", "Ctrl+N"),
    Binding("delete_frame", "Delete Frame", "action_delete_frame", "Ctrl+W"),
    Binding("next_frame", "Next Frame", "action_next_frame", "Tab"),
    Binding("previous_frame", "Previous Frame", "action_prev_frame", "Shift+Tab"),
    Binding("header", "Header", "action_fits_header", "Ctrl+I"),
    Binding("notes", "Notes", "action_notes", "Ctrl+Shift+N"),
    Binding("prism", "Prism", "action_prism", "Ctrl+B"),
    Binding("fullscreen", "Full Screen", "action_fullscreen", "F11"),
)


def defaults() -> dict[str, str]:
    """Every binding's preference key and default shortcut."""
    return {PREFIX + binding.name: binding.default for binding in BINDINGS}


def by_name() -> dict[str, Binding]:
    """Every binding by name."""
    return {binding.name: binding for binding in BINDINGS}


def conflicts(shortcuts: dict[str, str]) -> dict[str, list[str]]:
    """Which shortcuts are asked for by more than one command.

    Two commands on one combination means one of them never fires, and
    which one is Qt's business rather than the user's -- so the editor says
    so rather than letting it happen quietly.

    Args:
        shortcuts: Binding name -> shortcut.

    Returns:
        Shortcut -> the names wanting it, for the ones wanted twice.
    """
    wanted: dict[str, list[str]] = {}
    for name, shortcut in shortcuts.items():
        text = QKeySequence(shortcut).toString()
        if not text:
            continue
        wanted.setdefault(text, []).append(name)
    return {text: names for text, names in wanted.items() if len(names) > 1}


def apply(menu, shortcuts: dict[str, str]) -> dict[str, str]:
    """Put a set of shortcuts on the menu.

    Args:
        menu: The `MenuBar`.
        shortcuts: Binding name -> shortcut. A name that is not there keeps
            its default; an empty string removes the shortcut, which is a
            legitimate thing to want.

    Returns:
        What each binding ended up with, for the ones whose action exists.
    """
    applied: dict[str, str] = {}
    for binding in BINDINGS:
        action = getattr(menu, binding.action, None)
        if action is None:
            continue
        wanted = shortcuts.get(binding.name, binding.default)
        action.setShortcut(QKeySequence(wanted))
        applied[binding.name] = action.shortcut().toString()
    return applied


def from_preferences(store) -> dict[str, str]:
    """The shortcuts a preferences store holds, defaults filled in."""
    found: dict[str, str] = {}
    for binding in BINDINGS:
        value = store.get(PREFIX + binding.name, binding.default)
        found[binding.name] = "" if value is None else str(value)
    return found
