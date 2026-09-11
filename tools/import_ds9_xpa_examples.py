#!/usr/bin/env python3
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
Harvest DS9's own XPA examples into a conformance corpus.

`ds9/doc/ref/xpa.html` documents every access point with a Syntax block and
an Example block, and the Example block is a list of real command lines --
`$xpaget ds9 dsssao size`, `$xpaset -p ds9 bin factor 4`. About fifteen
hundred of them. That is a specification written by the people who wrote
the thing being specified, which is a better conformance corpus than
anything hand-written here, and it costs nothing to extract.

The output is `docs/parity/ds9_xpa_examples.json`, which
`tests/unit/test_xpa_conformance.py` runs against our XPA. Committed rather
than generated at test time so the tests do not need the DS9 checkout.

Usage:
    python tools/import_ds9_xpa_examples.py
    python tools/import_ds9_xpa_examples.py --check   # fail if stale

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: DS9's reference, in the checkout `tools/fetch_ds9.sh` makes.
REFERENCE = ROOT / ".tmp_sao_ds9" / "ds9" / "doc" / "ref" / "xpa.html"

#: Where DS9 registers its access points. The reference has a handful of
#: typos -- `$xpaset -p ds9 connect` in the `xpa` section, where the point
#: is `xpa connect` -- and the registration list is what settles which
#: first word is a point and which is a subcommand written on its own.
REGISTRATIONS = ROOT / ".tmp_sao_ds9" / "ds9" / "library" / "xpa.tcl"

#: One `xpacmdadd $xpa <name>` line.
REGISTERED = re.compile(r"^\s*xpacmdadd \$xpa ([A-Za-z0-9]+)", re.M)

#: Where the corpus is written.
OUTPUT = ROOT / "docs" / "parity" / "ds9_xpa_examples.json"

#: The anchors that introduce one access point's section.
ANCHOR = re.compile(r'name="([\w.]+)" id="\1"')

#: An example line. DS9 writes reads as `$xpaget ds9 ...` and writes as
#: `$xpaset -p ds9 ...`; the `-p` form is the one that takes its argument
#: on the command line rather than on standard input.
GET = re.compile(r"^\s*\$xpaget ds9 (.+?)\s*$", re.M)
SET = re.compile(r"^\s*\$xpaset(?: -p)? ds9 (.+?)\s*$", re.M)


def sections(document: str) -> list[tuple[str, str]]:
    """Split the reference into (anchor, text) per access point."""
    anchors = [(m.group(1), m.start()) for m in ANCHOR.finditer(document)]
    found = []
    for index, (name, start) in enumerate(anchors):
        end = anchors[index + 1][1] if index + 1 < len(anchors) else len(document)
        found.append((name, html.unescape(re.sub(r"<[^>]+>", "", document[start:end]))))
    return found


def registered(source: str) -> set[str]:
    """The access-point names DS9 registers, lowercased.

    `3d` and `3D` are registered separately, as are `iexam` and `imexam`;
    lowercasing folds the first pair and leaves the second, which is what
    a caller sees.
    """
    return {name.lower() for name in REGISTERED.findall(source)}


def harvest(document: str, known: set[str]) -> dict[str, dict[str, list[str]]]:
    """Every documented example, keyed by the point it exercises.

    Keyed by the *first word of the command*, not by the anchor: DS9's
    anchor for `3d` is `threed` and for 2MASS is `twomass`, while the
    examples use the names a caller actually types. A first word that is
    not a registered point is a typo in the reference -- `$xpaset -p ds9
    connect` for `xpa connect` -- and is dropped rather than turned into
    an access point nobody has.
    """
    points: dict[str, dict[str, list[str]]] = {}
    dropped: list[str] = []
    for _anchor, text in sections(document):
        for kind, pattern in (("get", GET), ("set", SET)):
            for command in pattern.findall(text):
                # DS9's examples occasionally carry a trailing comment or
                # a shell pipeline; neither is part of the grammar.
                command = command.split("#")[0].split("|")[0].strip()
                if not command:
                    continue
                name = command.split()[0].lower()
                if name not in known:
                    dropped.append(command)
                    continue
                entry = points.setdefault(name, {"get": [], "set": []})
                if command not in entry[kind]:
                    entry[kind].append(command)
    if dropped:
        print(f"note: dropped {len(dropped)} example(s) naming no registered point: {sorted(set(dropped))}")
    return {name: points[name] for name in sorted(points)}


def document(points: dict[str, dict[str, list[str]]]) -> dict:
    """The corpus, with the provenance a copied file needs."""
    return {
        "source": "SAOImageDS9 ds9/doc/ref/xpa.html",
        "note": (
            "Command lines copied from SAOImageDS9's XPA reference, which is "
            "distributed under the GNU GPL, the same licence as this project. "
            "They are DS9's specification of its own access points and are used "
            "here as a conformance corpus. Regenerate with "
            "tools/import_ds9_xpa_examples.py."
        ),
        "points": len(points),
        "examples": sum(len(entry["get"]) + len(entry["set"]) for entry in points.values()),
        "commands": points,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit non-zero if the committed corpus is out of date",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args(argv)

    for needed in (REFERENCE, REGISTRATIONS):
        if not needed.is_file():
            print(f"error: {needed} is missing; run tools/fetch_ds9.sh first", file=sys.stderr)
            return 2

    known = registered(REGISTRATIONS.read_text(errors="replace"))
    built = document(harvest(REFERENCE.read_text(errors="replace"), known))
    built["registered"] = len(known)
    text = json.dumps(built, indent=2, ensure_ascii=False) + "\n"

    if arguments.check:
        if not arguments.output.is_file() or arguments.output.read_text() != text:
            print(f"error: {arguments.output} is out of date", file=sys.stderr)
            print("Run: python tools/import_ds9_xpa_examples.py", file=sys.stderr)
            return 1
        print(f"{arguments.output} is up to date: {built['examples']} examples")
        return 0

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(f"Wrote {arguments.output}: {built['examples']} examples over {built['points']} points")
    return 0


if __name__ == "__main__":
    sys.exit(main())
