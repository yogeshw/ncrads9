#!/usr/bin/env python3
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

"""Dump NCRADS9's menu tree in the same format as ``tools/ds9_menu_tree.py``.

Emits one line per menu entry::

    <menu path>|<kind>|<label>

Paths mirror DS9's Tcl widget paths (``.file``, ``.frame.match.frame``) so the
two snapshots diff directly. ``kind`` uses DS9's vocabulary -- ``command``,
``cascade``, ``checkbutton``, ``radiobutton``, ``separator`` -- inferred from
the Qt action's checkable/exclusive state.

Usage::

    python tools/dump_menus.py                        # print to stdout
    python tools/dump_menus.py --output FILE          # write a snapshot
    python tools/dump_menus.py --connected            # annotate dead actions

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Qt must be able to start without a display before anything imports it.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: Maps NCRADS9's top-level menu titles onto DS9's widget-path names, so the
#: two snapshots line up. NCRADS9's `VO` menu has no DS9 counterpart (DS9
#: reaches VO features from Analysis); `.vo` is used so it sorts visibly.
TOP_LEVEL_PATHS = {
    "File": "file",
    "Edit": "edit",
    "View": "view",
    "Frame": "frame",
    "Bin": "bin",
    "Zoom": "zoom",
    "Scale": "scale",
    "Color": "color",
    "Region": "region",
    "Illustrate": "illustrate",
    "VO": "vo",
    "WCS": "wcs",
    "Analysis": "analysis",
    "Help": "help",
}


def _clean(label: str) -> str:
    """Strip Qt mnemonics and trailing dialog ellipses from a menu label."""
    return label.replace("&", "").removesuffix("...").strip()


def _slug(label: str) -> str:
    """Derive a DS9-ish path segment from a submenu label."""
    return _clean(label).lower().replace(" ", "").replace("/", "")


def _kind(action: object) -> str:
    """Classify a QAction the way DS9 classifies its menu entries."""
    from PyQt6.QtGui import QAction

    assert isinstance(action, QAction)
    if action.isSeparator():
        return "separator"
    if action.menu() is not None:
        return "cascade"
    if action.isCheckable():
        # An action in an exclusive group is a radiobutton; otherwise a toggle.
        group = action.actionGroup()
        if group is not None and group.isExclusive():
            return "radiobutton"
        return "checkbutton"
    return "command"


def _walk(menu: object, path: str, lines: list[str], annotate: bool) -> None:
    """Depth-first walk of a QMenu, appending one line per entry."""
    from PyQt6.QtWidgets import QMenu

    assert isinstance(menu, QMenu)
    for action in menu.actions():
        kind = _kind(action)
        if kind == "separator":
            lines.append(f"{path}|separator|---")
            continue

        label = _clean(action.text())
        suffix = ""
        if annotate and kind != "cascade" and not action.receivers(action.triggered):
            suffix = "|UNCONNECTED"
        lines.append(f"{path}|{kind}|{label}{suffix}")

        submenu = action.menu()
        if submenu is not None:
            _walk(submenu, f"{path}.{_slug(label)}", lines, annotate)


def collect(annotate: bool = False) -> list[str]:
    """Build the NCRADS9 menu snapshot.

    A full ``MainWindow`` is constructed because several menus are populated
    from runtime state (colormap list, frame list), so a static read of
    ``menu_bar.py`` would understate the tree.
    """
    from PyQt6.QtWidgets import QApplication

    from ncrads9.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        lines: list[str] = []
        for action in window.menu_bar.actions():
            submenu = action.menu()
            if submenu is None:
                continue
            title = _clean(action.text())
            path = "." + TOP_LEVEL_PATHS.get(title, _slug(title))
            lines.append(f"# {title}")
            _walk(submenu, path, lines, annotate)
        return lines
    finally:
        window.close()
        del window
        app.processEvents()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", type=Path, help="snapshot file to write")
    parser.add_argument(
        "--connected",
        action="store_true",
        help="mark actions with no connected receiver as UNCONNECTED",
    )
    args = parser.parse_args(argv)

    lines = collect(annotate=args.connected)
    entries = [line for line in lines if not line.startswith("#")]
    real = [line for line in entries if not line.endswith("|---")]

    body = "\n".join(
        [
            "# NCRADS9 menu tree -- GENERATED, do not edit by hand.",
            "# Regenerate with: python tools/dump_menus.py --output docs/parity/ncrads9_menus.txt",
            f"# entries: {len(entries)} ({len(real)} excluding separators)",
            "#",
            "# Format: <menu path>|<kind>|<label>",
            "",
            *lines,
            "",
        ]
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body)
        print(f"wrote {args.output} ({len(real)} entries excluding separators)")
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
