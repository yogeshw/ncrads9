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

"""Translating the dialogs, all-or-nothing (M9-31)."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ncrads9.i18n import catalogue
from ncrads9.i18n import dialogs as translation

#: A tiny catalogue, so a test says what it is testing rather than
#: depending on how much of DS9's French file happens to cover a dialog.
FRENCH = {
    "Apply": "Appliquer",
    "Cancel": "Annuler",
    "Close": "Fermer",
    "Colour": "Couleur",
    "Width": "Largeur",
    "Appearance": "Apparence",
    "Scale": "Échelle",
    "Zoom Parameters": "Paramètres de zoom",
}


@pytest.fixture
def translate():
    """Translate with `FRENCH` and nothing else."""
    return catalogue.Catalogue(language="fr", messages=dict(FRENCH)).translate


@pytest.fixture
def dialog(qapp):
    """A dialog with one of everything the walker has to find."""
    made = QDialog()
    made.setWindowTitle("Zoom Parameters")
    layout = QVBoxLayout(made)

    group = QGroupBox("Appearance")
    inner = QVBoxLayout(group)
    inner.addWidget(QLabel("Colour"))
    inner.addWidget(QLabel("Width:"))
    inner.addWidget(QCheckBox("Scale"))
    layout.addWidget(group)

    tabs = QTabWidget()
    tabs.addTab(QWidget(), "Apply")
    layout.addWidget(tabs)

    layout.addWidget(QPushButton("Apply"))
    layout.addWidget(QPushButton("Cancel"))
    yield made
    made.close()


# -- finding the labels ------------------------------------------------------------


def test_every_kind_of_label_is_found(dialog):
    found = {get() for get, _set in translation.labels(dialog)}
    assert found == {"Zoom Parameters", "Appearance", "Colour", "Width:", "Scale", "Apply", "Cancel"}


def test_what_is_not_a_label_is_left_alone(qapp):
    """A number in a read-only field and a separator are not words."""
    made = QDialog()
    layout = QVBoxLayout(made)
    for text in ("", "-", "--", ":", "1.00", "42", "  "):
        layout.addWidget(QLabel(text))
    assert list(translation.labels(made)) == []
    made.close()


def test_a_label_with_a_number_in_it_is_still_a_label(qapp):
    made = QDialog()
    QVBoxLayout(made).addWidget(QLabel("Level 1"))
    assert [get() for get, _set in translation.labels(made)] == ["Level 1"]
    made.close()


# -- the threshold -----------------------------------------------------------------


def test_coverage_counts_what_can_be_translated(dialog, translate):
    translated, total = translation.coverage(dialog, translate)
    # Eight, not seven: `Apply` is on both a tab and a button, and each
    # is a label that has to be set.
    assert total == 8
    # Every one of them is in the little catalogue; `Width:` through the
    # colon rule, which is how a form row is written.
    assert translated == 8


def test_a_dialog_the_catalogue_covers_is_translated(dialog, translate):
    assert translation.translate_dialog(dialog, translate) is True
    assert dialog.windowTitle() == "Paramètres de zoom"
    labels = {get() for get, _set in translation.labels(dialog)}
    assert "Appliquer" in labels
    assert "Largeur:" in labels, "the colon comes back on"


def test_a_dialog_the_catalogue_barely_covers_is_left_in_english(dialog, qapp):
    """The point of the threshold: a French Apply beside an English
    'Auto-calculate limits' is harder to read than honest English."""
    thin = catalogue.Catalogue(language="fr", messages={"Apply": "Appliquer"}).translate
    assert translation.translate_dialog(dialog, thin) is False
    assert dialog.windowTitle() == "Zoom Parameters"
    assert {get() for get, _set in translation.labels(dialog)} >= {"Apply", "Cancel", "Colour"}


def test_a_threshold_of_zero_translates_whatever_it_can(dialog, qapp):
    thin = catalogue.Catalogue(language="fr", messages={"Apply": "Appliquer"}).translate
    assert translation.translate_dialog(dialog, thin, threshold=0.0) is True
    assert dialog.windowTitle() == "Zoom Parameters", "no translation, so unchanged"
    assert "Appliquer" in {get() for get, _set in translation.labels(dialog)}


def test_a_dialog_with_no_labels_is_not_claimed_as_translated(qapp):
    empty = QDialog()
    assert translation.translate_dialog(empty) is False
    empty.close()


def test_translating_twice_does_not_translate_a_translation(dialog, translate):
    """The second pass reads the labels as they now are; a catalogue that
    has no entry for `Appliquer` must leave it alone rather than mangle it."""
    translation.translate_dialog(dialog, translate)
    before = {get() for get, _set in translation.labels(dialog)}
    translation.translate_dialog(dialog, translate, threshold=0.0)
    assert {get() for get, _set in translation.labels(dialog)} == before


# -- the event filter --------------------------------------------------------------


def test_a_dialog_is_translated_when_it_is_shown(qapp, dialog, translate):
    watcher = translation.DialogTranslator(translate)
    qapp.installEventFilter(watcher)
    try:
        dialog.show()
        qapp.processEvents()
        assert watcher.translated == 1
        assert dialog.windowTitle() == "Paramètres de zoom"
    finally:
        qapp.removeEventFilter(watcher)


def test_a_dialog_is_only_walked_once(qapp, dialog, translate):
    watcher = translation.DialogTranslator(translate)
    qapp.installEventFilter(watcher)
    try:
        for _ in range(3):
            dialog.show()
            dialog.hide()
            qapp.processEvents()
        assert watcher.translated == 1
    finally:
        qapp.removeEventFilter(watcher)


def test_a_dialog_left_in_english_is_named_for_a_translator(qapp, dialog):
    """The list of what to translate next is the list of what did not
    reach the threshold, which is worth keeping rather than discarding."""
    thin = catalogue.Catalogue(language="fr", messages={"Apply": "Appliquer"}).translate
    watcher = translation.DialogTranslator(thin)
    qapp.installEventFilter(watcher)
    try:
        dialog.show()
        qapp.processEvents()
        assert watcher.translated == 0
        assert watcher.untranslated == ["Zoom Parameters"]
    finally:
        qapp.removeEventFilter(watcher)


def test_the_filter_never_swallows_an_event(qapp, dialog, translate):
    watcher = translation.DialogTranslator(translate)
    assert watcher.eventFilter(dialog, None) is False


def test_installing_returns_the_filter(qapp, translate):
    watcher = translation.install(qapp, translate)
    try:
        assert isinstance(watcher, translation.DialogTranslator)
    finally:
        qapp.removeEventFilter(watcher)


# -- what it does to the real dialogs ----------------------------------------------


def test_a_form_rows_colon_does_not_hide_the_word():
    """Almost every dialog label is a form row written `Width:`, and DS9's
    catalogue holds `Width`. Without the colon rule the whole vocabulary
    would miss."""
    french = catalogue.Catalogue(language="fr", messages={"Width": "Largeur"})
    assert french.translate("Width:") == "Largeur:"
    assert french.translate("Width") == "Largeur"
    assert french.translate("Height:") == "Height:"


def test_ds9s_catalogue_does_not_yet_cover_a_dialog(qapp):
    """The honest state of M9-31: DS9's catalogue is a catalogue of *menu*
    labels, so it covers about a fifth of what a dialog says and no dialog
    reaches the threshold. This test is the record of that, and it will
    fail -- usefully -- when translations are written and one does."""
    from ncrads9.ui.dialogs.scale_dialog import ScaleDialog

    french = catalogue.Catalogue.load("fr")
    made = ScaleDialog()
    translated, total = translation.coverage(made, french.translate)
    made.close()
    assert total > 10, "a dialog with labels to count"
    assert translated < translation.THRESHOLD * total, (
        f"the French catalogue now covers {translated}/{total} of the Scale dialog; "
        "if translations have been written, raise this and let the dialogs translate"
    )
