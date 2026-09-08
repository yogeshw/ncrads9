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

"""Report NCRADS9's menu parity against SAOImageDS9.

Reads the two generated snapshots and reports, per top-level menu, how many DS9
entries NCRADS9 provides. This is the parity instrument referenced by PLAN.md
section 9; it is advisory, not a gate -- NCRADS9 deliberately diverges in
places (see PLAN.md section 7).

Usage::

    python tools/menu_diff.py --summary        # per-menu counts
    python tools/menu_diff.py --missing        # DS9 entries with no counterpart
    python tools/menu_diff.py --extra          # NCRADS9 entries DS9 lacks
    python tools/menu_diff.py --menu frame     # restrict to one menu

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PARITY_DIR = REPO_ROOT / "docs" / "parity"

#: Labels that differ only cosmetically between the two applications.
LABEL_ALIASES = {
    "save as": "save as",
    "delete all frames": "delete all frames",
    "show/hide frames": "show/hide frames",
    "coordinate grid parameters": "coordinate grid parameters",
    "show status bar": "statusbar",
    "show toolbar": "toolbar",
}


def _normalise(label: str) -> str:
    """Fold a label to a comparable key."""
    key = label.strip().lower().removesuffix("...").strip()
    return LABEL_ALIASES.get(key, key)


def _load(path: Path) -> dict[str, set[str]]:
    """Load a snapshot into {top-level menu: {normalised labels}}."""
    if not path.is_file():
        raise SystemExit(
            f"error: {path} not found.\n"
            "Generate the snapshots first:\n"
            "  python tools/ds9_menu_tree.py\n"
            "  python tools/dump_menus.py --output docs/parity/ncrads9_menus.txt"
        )

    by_menu: dict[str, set[str]] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        menu_path, kind, label = parts[0], parts[1], parts[2]
        if kind == "separator" or label in ("---", "<dynamic>"):
            continue
        top = menu_path.lstrip(".").split(".")[0] or "(root)"
        by_menu.setdefault(top, set()).add(_normalise(label))
    return by_menu


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--summary", action="store_true", help="per-menu counts")
    parser.add_argument("--missing", action="store_true", help="DS9 entries not in NCRADS9")
    parser.add_argument("--extra", action="store_true", help="NCRADS9 entries not in DS9")
    parser.add_argument("--menu", help="restrict output to one top-level menu")
    args = parser.parse_args(argv)

    if not (args.summary or args.missing or args.extra):
        args.summary = True

    ds9 = _load(PARITY_DIR / "ds9_menus.txt")
    ours = _load(PARITY_DIR / "ncrads9_menus.txt")

    menus = sorted(set(ds9) | set(ours))
    if args.menu:
        menus = [m for m in menus if m == args.menu.lower().lstrip(".")]
        if not menus:
            raise SystemExit(f"error: no such menu; known: {', '.join(sorted(set(ds9) | set(ours)))}")

    if args.summary:
        total_ds9 = total_have = 0
        print(f"{'menu':<14}{'DS9':>6}{'ours':>7}{'shared':>8}{'missing':>9}  parity")
        print("-" * 60)
        for menu in menus:
            d, o = ds9.get(menu, set()), ours.get(menu, set())
            shared = len(d & o)
            pct = f"{100 * shared / len(d):.0f}%" if d else "n/a"
            print(f"{menu:<14}{len(d):>6}{len(o):>7}{shared:>8}{len(d - o):>9}  {pct:>5}")
            total_ds9 += len(d)
            total_have += shared
        print("-" * 60)
        overall = f"{100 * total_have / total_ds9:.0f}%" if total_ds9 else "n/a"
        print(f"{'TOTAL':<14}{total_ds9:>6}{'':>7}{total_have:>8}{total_ds9 - total_have:>9}  {overall:>5}")
        print(
            "\nCounts compare menu labels only; a shared label does not imply "
            "equivalent behaviour.\nSee PLAN.md section 5 for the feature-level "
            "inventory."
        )

    if args.missing:
        print("\n=== In DS9, absent from NCRADS9 ===")
        for menu in menus:
            gap = sorted(ds9.get(menu, set()) - ours.get(menu, set()))
            if gap:
                print(f"\n[{menu}] {len(gap)}")
                for label in gap:
                    print(f"  - {label}")

    if args.extra:
        print("\n=== In NCRADS9, absent from DS9 ===")
        print("(Intentional divergences are listed in PLAN.md section 7.)")
        for menu in menus:
            extra = sorted(ours.get(menu, set()) - ds9.get(menu, set()))
            if extra:
                print(f"\n[{menu}] {len(extra)}")
                for label in extra:
                    print(f"  + {label}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
