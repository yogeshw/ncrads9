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
Looking a label up in a language.

One catalogue per language, read from JSON once and kept. The lookup has to
cope with what a Qt label actually looks like:

  * `&Zoom` -- the ampersand marks the keyboard accelerator, and is not
    part of the text to translate. It is taken off, the translation looked
    up, and an ampersand put back before the same letter if that letter is
    still in the translation. Leaving it in would translate nothing at all,
    since DS9's catalogue has `Zoom` and not `&Zoom`.
  * `Open...` -- the ellipsis is a convention, not words. It is taken off
    and put back.
  * `Zoom 1/2` -- DS9's catalogue has plenty of these verbatim, so the
    whole string is tried first.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

#: The language the interface is in when nothing says otherwise.
DEFAULT_LANGUAGE = "en"

#: DS9's eight, and English.
LANGUAGES: dict[str, str] = {
    "en": "English",
    "cs": "Čeština",
    "da": "Dansk",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "ja": "日本語",
    "pt": "Português",
    "zh": "中文",
}

#: Where the catalogues live.
LOCALES = Path(__file__).resolve().parent / "locales"

#: What a label can end with that is not part of its words.
SUFFIXES: tuple[str, ...] = ("...", "…")


@dataclass
class Catalogue:
    """One language's translations."""

    language: str = DEFAULT_LANGUAGE
    messages: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, language: str) -> Catalogue:
        """Read one language's catalogue.

        Args:
            language: A code from `LANGUAGES`.

        Returns:
            The catalogue, empty for English or for a language with no
            file -- an empty catalogue translates nothing, which is
            exactly right.
        """
        if language == DEFAULT_LANGUAGE:
            return cls(language=language)
        path = LOCALES / f"{language}.json"
        if not path.is_file():
            return cls(language=language)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(language=language)
        messages = document.get("messages")
        return cls(language=language, messages=dict(messages) if isinstance(messages, dict) else {})

    def __len__(self) -> int:
        """How many translations it holds."""
        return len(self.messages)

    def translate(self, text: str) -> str:
        """One label in this language, or the label itself.

        Args:
            text: The label, ampersand and ellipsis and all.

        Returns:
            The translation, with the accelerator and the ellipsis put
            back, or `text` unchanged when there is no translation.
        """
        if not text or not self.messages:
            return text

        # The whole thing first: DS9's catalogue holds plenty of labels
        # verbatim, punctuation included.
        found = self.messages.get(text)
        if found is not None:
            return found

        body = text
        suffix = ""
        for candidate in SUFFIXES:
            if body.endswith(candidate):
                body, suffix = body[: -len(candidate)], candidate
                break

        accelerator = ""
        if "&" in body:
            index = body.find("&")
            if index + 1 < len(body):
                accelerator = body[index + 1]
            body = body.replace("&", "", 1)

        found = self.messages.get(body) or self.messages.get(body.strip())
        if found is None:
            return text

        return _with_accelerator(found, accelerator) + suffix


def _with_accelerator(text: str, letter: str) -> str:
    """Put an accelerator back, if the translation still has its letter.

    A translation that no longer contains the letter gets no ampersand
    rather than an arbitrary one: `&Open` into French is `Ouvrir`, which
    has no `O`... it does, so it becomes `&Ouvrir`; `&Zoom` into a
    translation with no `z` simply loses its accelerator, which Qt handles
    by assigning one itself.
    """
    if not letter:
        return text
    lowered = text.lower()
    position = lowered.find(letter.lower())
    if position < 0:
        return text
    return text[:position] + "&" + text[position:]


#: The catalogue in force. Set by `set_language`.
_current = Catalogue()


def set_language(language: str) -> Catalogue:
    """Choose the language the interface is in.

    Args:
        language: A code from `LANGUAGES`. Anything else falls back to
            English rather than raising: a stale preference should not stop
            the application starting.

    Returns:
        The catalogue now in force.
    """
    global _current
    wanted = language if language in LANGUAGES else DEFAULT_LANGUAGE
    _current = Catalogue.load(wanted)
    return _current


def current() -> Catalogue:
    """The catalogue in force."""
    return _current


def translate(text: str) -> str:
    """One label in the language in force."""
    return _current.translate(text)


def available() -> dict[str, int]:
    """Every language with a catalogue, and how much each covers."""
    found = {DEFAULT_LANGUAGE: 0}
    for language in LANGUAGES:
        if language == DEFAULT_LANGUAGE:
            continue
        path = LOCALES / f"{language}.json"
        if path.is_file():
            found[language] = len(Catalogue.load(language))
    return found
