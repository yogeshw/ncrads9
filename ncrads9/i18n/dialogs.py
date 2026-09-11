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
Translating a dialog that has already been built.

The same trick the menus use (`menus.py`): walk the widgets once, after
they exist, translating each label and keeping the English on the widget
so a second pass translates from English rather than from the last
translation. No `tr()` at two hundred call sites, and the English a
translator needs stays in the source where it can be read.

**All of a dialog or none of it.** DS9's catalogue is a catalogue of
*menu* labels; it covers only a fraction of what a dialog says, and a
dialog with a French Apply button beside an English "Auto-calculate
limits" is harder to use than one that is honestly all English. So a
dialog is translated only when the catalogue covers `THRESHOLD` of its
labels, and left alone otherwise. As translations are written the
coverage rises and dialogs start translating themselves, one at a time,
with nothing here to change.

This is deliberately not `QTranslator`. Qt's own mechanism installs
between a widget and `tr()`, which is the call site we are avoiding; this
one runs over the finished widget tree, which is what lets the threshold
exist at all -- a per-string mechanism cannot see how much of a dialog it
failed to translate.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import (
    QAbstractButton,
    QDialog,
    QGroupBox,
    QLabel,
    QTabWidget,
    QWidget,
)

from . import catalogue

#: How much of a dialog the catalogue must cover before any of it is
#: translated. Four labels in five: enough that the odd untranslated
#: technical term reads as a technical term rather than as a gap.
THRESHOLD = 0.8

#: Marks a dialog this has already been through, so showing it twice does
#: not walk it twice.
DONE = "ncrads9_translated"

#: Text that is not a label: a number in a field, a separator, a value
#: the application filled in. Translating these is meaningless and they
#: would drag a dialog's coverage below the threshold for no reason.
_NOT_A_LABEL = frozenset({"", "-", "--", "...", ":", ",", ", "})


def _is_label(text: str) -> bool:
    """Whether some widget text is a label worth translating.

    A number, a punctuation mark, or a value the application put there is
    not something a catalogue has an entry for.
    """
    stripped = text.strip()
    if stripped.lower() in _NOT_A_LABEL or len(stripped) < 2:
        return False
    # A number, a size, a coordinate: nothing to translate.
    return any(character.isalpha() for character in stripped)


def labels(widget: QWidget) -> Iterator[tuple[Callable[[], str], Callable[[str], None]]]:
    """Every translatable label under a widget, as a getter and a setter.

    Covers what a dialog is made of: its title, its labels, its buttons,
    check boxes and radio buttons, its group boxes and its tab names.
    """
    if isinstance(widget, QDialog) and _is_label(widget.windowTitle()):
        yield (widget.windowTitle, widget.setWindowTitle)

    for child in widget.findChildren(QWidget):
        if isinstance(child, (QLabel, QAbstractButton)) and _is_label(child.text()):
            yield (child.text, child.setText)
        elif isinstance(child, QGroupBox) and _is_label(child.title()):
            yield (child.title, child.setTitle)
        elif isinstance(child, QTabWidget):
            for index in range(child.count()):
                if _is_label(child.tabText(index)):
                    yield (
                        lambda tabs=child, position=index: tabs.tabText(position),
                        lambda text, tabs=child, position=index: tabs.setTabText(position, text),
                    )


def coverage(widget: QWidget, translator: Callable[[str], str] | None = None) -> tuple[int, int]:
    """How much of a dialog the catalogue can translate.

    Returns:
        (translated, total). A dialog with no labels at all counts as
        fully covered, since there is nothing to get wrong.
    """
    convert = translator or catalogue.translate
    total = 0
    translated = 0
    for get, _set in labels(widget):
        english = get()
        total += 1
        if convert(english) != english:
            translated += 1
    return (translated, total)


def translate_dialog(
    widget: QWidget,
    translator: Callable[[str], str] | None = None,
    threshold: float = THRESHOLD,
) -> bool:
    """Translate a dialog, if the catalogue covers enough of it.

    Args:
        widget: The dialog, or any widget holding labels.
        translator: What to translate one label with. Defaults to the
            language in force.
        threshold: The fraction of labels that must have a translation
            before any of them is applied. Zero translates whatever it
            can, which is what a test that wants to see the mechanism
            work passes.

    Returns:
        Whether it was translated.
    """
    convert = translator or catalogue.translate

    # The English is read off the widget where a previous pass put it, so
    # changing language twice translates from English both times rather
    # than trying to translate a French label into German.
    pairs = []
    for get, set_text in labels(widget):
        english = get()
        pairs.append((english, set_text, convert(english)))

    if not pairs:
        return False
    covered = sum(1 for english, _set, found in pairs if found != english)
    if covered < threshold * len(pairs):
        return False

    for _english, set_text, found in pairs:
        set_text(found)
    widget.setProperty(DONE, True)
    return True


class DialogTranslator(QObject):
    """Translates each dialog the first time it is shown.

    One event filter on the application rather than a call in each
    dialog's constructor: dialogs are built all over the code and some
    only when first used, so a hook that runs when one appears catches
    every one of them, including any added later.
    """

    def __init__(self, translator: Callable[[str], str] | None = None, threshold: float = THRESHOLD):
        """
        Args:
            translator: What to translate with. Defaults to the language
                in force at the moment each dialog is shown.
            threshold: Passed to `translate_dialog`.
        """
        super().__init__()
        self._translator = translator
        self._threshold = threshold
        #: The dialogs translated, counted for the tests and the status bar.
        self.translated = 0
        #: The ones left in English because the catalogue covers too
        #: little of them, by window title -- which is the list of what a
        #: translator should work on next.
        self.untranslated: list[str] = []

    def eventFilter(self, watched, event) -> bool:
        """Translate a dialog as it is shown. Never consumes the event."""
        if (
            event is not None
            and event.type() == QEvent.Type.Show
            and isinstance(watched, QDialog)
            and not watched.property(DONE)
        ):
            # Marked before translating as well as after: a dialog whose
            # coverage is too low must not be walked again every time it
            # is shown.
            watched.setProperty(DONE, True)
            if translate_dialog(watched, self._translator, self._threshold):
                self.translated += 1
            else:
                self.untranslated.append(watched.windowTitle())
        return False


def install(application, translator: Callable[[str], str] | None = None) -> DialogTranslator:
    """Put a `DialogTranslator` on the application and return it."""
    filter_ = DialogTranslator(translator)
    application.installEventFilter(filter_)
    return filter_
