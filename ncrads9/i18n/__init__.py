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
The interface in DS9's eight languages.

DS9 ships translations for Czech, Danish, German, Spanish, French,
Japanese, Portuguese and Chinese (`ds9/msgs/*.msg`). Those translations are
the labels on DS9's menus, and our menus say mostly the same things -- so
they are the right place to start, and `tools/import_ds9_messages.py`
converts them into `locales/*.json` for us. They are SAOImageDS9's work,
under the same GNU GPL this project uses.

What is translated is what a label goes through `translate()` for: the
menus, the window titles, and the dialogs' own labels as they are given
one. A status message is not translated -- there are thousands, DS9's
catalogue has none of them, and a half-translated sentence is worse than
an English one.

Coverage is DS9's coverage, which is partial: `Zoom`, `Scale` and
`Contours` are in DS9's French file with no translation beside them, so
they stay in English there. That is a fact about the catalogue, not a bug
here.

Author: Yogesh Wadadekar
"""

from .catalogue import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    Catalogue,
    available,
    current,
    set_language,
    translate,
)

__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGES",
    "Catalogue",
    "available",
    "current",
    "set_language",
    "translate",
]
