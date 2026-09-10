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
Convert DS9's message catalogues into ours.

DS9 ships one Tcl file per language, each a list of

    ::msgcat::mcset fr {Add} {Ajouter}
    ::msgcat::mcset fr {About} [encoding convertfrom iso8859-1 {À propos de}]

where an empty translation means "not translated". This reads those and
writes one JSON file per language into `ncrads9/i18n/locales/`.

Run it against a DS9 checkout when the translations are updated:

    python tools/import_ds9_messages.py .tmp_sao_ds9/ds9/msgs

The translations are SAOImageDS9's, under the same GNU GPL this project
uses, and the provenance is recorded in each file it writes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

#: `::msgcat::mcset <lang> {source} <translation>`, where the translation
#: is a brace group, a bare word, an `[encoding convertfrom ...]` wrapper,
#: or nothing at all.
#: Horizontal whitespace only: a `\s*` here would cross the newline and
#: swallow the *next* entry as this one's translation, which is how an
#: untranslated string came out holding the following line.
ENTRY = re.compile(
    r"^::msgcat::mcset[ \t]+(\w+)[ \t]+\{(?P<source>[^}\n]*)\}[ \t]*(?P<rest>[^\n]*?)[ \t]*$",
    re.M,
)

#: The `[encoding convertfrom <encoding> {text}]` DS9 wraps accented
#: translations in, because its own files are Latin-1.
WRAPPED = re.compile(r"\[encoding\s+convertfrom\s+(?P<encoding>[\w-]+)\s+\{(?P<text>.*)\}\s*\]")


def translation(rest: str, encoding: str) -> str:
    """One entry's translation, unwrapped, or "" if there is none."""
    text = rest.strip()
    if not text:
        return ""

    wrapped = WRAPPED.match(text)
    if wrapped is not None:
        # The file was read as Latin-1, so the characters are already
        # right; the wrapper only says what they were.
        return wrapped.group("text")

    if text.startswith("{") and text.endswith("}"):
        return text[1:-1]
    return text


def read(path: Path) -> dict[str, str]:
    """One language's translations, the untranslated entries left out."""
    text = path.read_text(encoding="iso8859-1")
    found: dict[str, str] = {}
    for match in ENTRY.finditer(text):
        source = match.group("source")
        value = translation(match.group("rest"), "iso8859-1")
        if source and value and value != source:
            found[source] = value
    return found


def main(argv: list[str]) -> int:
    """Convert every `.msg` in a directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="DS9's msgs directory")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "ncrads9" / "i18n" / "locales",
        help="where to write the JSON catalogues",
    )
    arguments = parser.parse_args(argv)

    if not arguments.source.is_dir():
        print(f"{arguments.source} is not a directory", file=sys.stderr)
        return 1
    arguments.output.mkdir(parents=True, exist_ok=True)

    total = 0
    for message_file in sorted(arguments.source.glob("*.msg")):
        entries = read(message_file)
        total += len(entries)
        document = {
            "language": message_file.stem,
            "source": "SAOImageDS9 ds9/msgs/" + message_file.name,
            "note": (
                "Translations from SAOImageDS9, used under the GNU GPL. "
                "Regenerate with tools/import_ds9_messages.py."
            ),
            "messages": entries,
        }
        target = arguments.output / f"{message_file.stem}.json"
        target.write_text(
            json.dumps(document, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"{message_file.name}: {len(entries)} translations -> {target.name}")

    print(f"{total} translations in all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
