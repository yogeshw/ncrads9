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
Translating a menu that has already been built.

The menus are built from literals -- `QAction("&Open...")` -- in one long,
readable file, and DS9's are built the same way with `msgcat::mc` wrapped
round each label. Wrapping ours the same way would mean touching two
thousand lines and would put the English text a translator needs *behind* a
function call.

So the translation happens once, afterwards: walk the menu, translate each
label, keep the English one on the action so a second pass -- a language
changed while running -- translates from English rather than from the last
translation.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from . import catalogue

#: Where an action's English label is kept, so translating twice is safe.
ENGLISH = "ncrads9_english_text"


def translate_menu(bar, translator=None) -> int:
    """Translate a whole menu bar, submenus and all.

    Args:
        bar: A `QMenuBar` or `QMenu`.
        translator: What to translate one label with. Defaults to the
            language in force.

    Returns:
        How many labels came back different from their English.
    """
    convert = translator or catalogue.translate
    changed = 0

    for action in bar.actions():
        english = action.property(ENGLISH)
        if english is None:
            english = action.text()
            action.setProperty(ENGLISH, english)
        if english:
            translated = convert(english)
            if translated != action.text():
                action.setText(translated)
            if translated != english:
                changed += 1

        submenu = action.menu()
        if submenu is not None:
            title = submenu.property(ENGLISH)
            if title is None:
                title = submenu.title()
                submenu.setProperty(ENGLISH, title)
            if title:
                submenu.setTitle(convert(title))
            changed += translate_menu(submenu, convert)

    return changed


def english_label(action) -> str:
    """One action's English label, whatever language it is showing.

    The XPA points and the parity tools look menu entries up by their
    English names, and they have to keep working in Japanese.
    """
    kept = action.property(ENGLISH)
    return str(kept) if kept else action.text()
