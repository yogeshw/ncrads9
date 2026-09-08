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

"""Extract SAOImageDS9's menu tree from its Tcl sources.

DS9 builds its menus imperatively in ``ds9/library/m*.tcl`` with calls of the
form::

    $ds9(mb).file add command -label [msgcat::mc {Open}] -command OpenDialog

This script parses those calls and emits one line per entry in a stable,
diffable format::

    <menu path>|<kind>|<label>

so it can be compared against ``tools/dump_menus.py`` output for NCRADS9.
Menu labels are the user-visible surface of DS9, which makes this the cheapest
honest measure of functional parity.

Usage::

    python tools/ds9_menu_tree.py                       # write the snapshot
    python tools/ds9_menu_tree.py --stdout              # print instead
    python tools/ds9_menu_tree.py --ds9-root /path/ds9  # non-default checkout

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Default location of the reference SAOImageDS9 checkout.
DEFAULT_DS9_ROOT = REPO_ROOT / ".tmp_sao_ds9" / "ds9"

#: Menu-defining Tcl files, in DS9's own menu-bar order.
MENU_FILES = (
    "mfile",
    "medit",
    "mview",
    "mframe",
    "mbin",
    "mzoom",
    "mscale",
    "mcolor",
    "mregion",
    "millustrate",
    "mwcs",
    "manalysis",
    "mhelp",
)

#: ``$ds9(mb)<path> add <kind> <rest>``
_ENTRY_RE = re.compile(r"\$ds9\(mb\)([a-zA-Z0-9._]*)\s+add\s+(\w+)(?P<rest>.*)$")

#: ``-label [msgcat::mc {Open}]`` or ``-label {128x128}``
_LABEL_RE = re.compile(r"-label\s+(?:\"?\[msgcat::mc\s+)?\{([^}]*)\}")

#: ``-label "[msgcat::mc {Zoom}] 1/32"`` -- a translated word plus a literal.
_LABEL_COMPOSITE_RE = re.compile(r"-label\s+\"\[msgcat::mc\s+\{([^}]*)\}\]\s*([^\"]*)\"")

#: ``-label "0 [msgcat::mc {Degrees}]"`` -- a literal plus a translated word.
_LABEL_COMPOSITE_REV_RE = re.compile(r"-label\s+\"([^\"\[]*?)\s*\[msgcat::mc\s+\{([^}]*)\}\]\"")

_CONTINUATION_RE = re.compile(r"\\\n\s*")


def _label_for(rest: str, kind: str) -> str:
    """Extract the user-visible label from the tail of an ``add`` call."""
    if kind == "separator":
        return "---"
    composite = _LABEL_COMPOSITE_RE.search(rest)
    if composite:
        head, tail = composite.group(1), composite.group(2).strip()
        return f"{head} {tail}".strip()
    reverse = _LABEL_COMPOSITE_REV_RE.search(rest)
    if reverse:
        head, tail = reverse.group(1).strip(), reverse.group(2)
        return f"{head} {tail}".strip()
    simple = _LABEL_RE.search(rest)
    if simple:
        return simple.group(1)
    # Menus built in a loop (colormap lists, WCS a-z, frame lists) have no
    # literal label. Mark them so the count stays honest without inventing text.
    return "<dynamic>"


def extract(ds9_root: Path) -> list[str]:
    """Return one ``path|kind|label`` line per DS9 menu entry."""
    library = ds9_root / "library"
    if not library.is_dir():
        raise SystemExit(
            f"error: {library} not found.\n" "Pass --ds9-root, or check out SAOImageDS9 at .tmp_sao_ds9/."
        )

    lines: list[str] = []
    for stem in MENU_FILES:
        source = library / f"{stem}.tcl"
        if not source.is_file():
            print(f"warning: {source} missing, skipping", file=sys.stderr)
            continue

        lines.append(f"# {stem}.tcl")
        text = _CONTINUATION_RE.sub(" ", source.read_text(errors="replace"))
        for raw in text.split("\n"):
            match = _ENTRY_RE.search(raw.strip())
            if not match:
                continue
            path, kind = match.group(1) or ".", match.group(2)
            lines.append(f"{path}|{kind}|{_label_for(match.group('rest'), kind)}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--ds9-root",
        type=Path,
        default=DEFAULT_DS9_ROOT,
        help=f"path to the ds9/ directory of a checkout (default: {DEFAULT_DS9_ROOT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "docs" / "parity" / "ds9_menus.txt",
        help="snapshot file to write",
    )
    parser.add_argument("--stdout", action="store_true", help="print instead of writing")
    args = parser.parse_args(argv)

    lines = extract(args.ds9_root)
    entries = [line for line in lines if not line.startswith("#")]
    real = [line for line in entries if not line.endswith("|---")]

    body = "\n".join(
        [
            "# SAOImageDS9 menu tree -- GENERATED, do not edit by hand.",
            "# Regenerate with: python tools/ds9_menu_tree.py",
            f"# entries: {len(entries)} ({len(real)} excluding separators)",
            "#",
            "# Format: <menu path>|<kind>|<label>",
            "#",
            "# Known limitation: DS9 builds some menus at runtime rather than",
            "# declaring them literally, so those entries appear as <dynamic> or",
            "# not at all. The largest case is the WCS menu, assembled by",
            "# CoordMenu (menu.tcl) from system x sky x format -- roughly 40",
            "# entries that this static extract cannot see. Treat the .wcs row of",
            "# tools/menu_diff.py as unreliable; PLAN.md section 5.11 has the real",
            "# comparison.",
            "",
            *lines,
            "",
        ]
    )

    if args.stdout:
        sys.stdout.write(body)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body)
        print(f"wrote {args.output} ({len(real)} entries excluding separators)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
