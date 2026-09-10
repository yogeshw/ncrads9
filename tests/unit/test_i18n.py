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

"""The interface in DS9's eight languages (M9-31)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from astropy.io import fits

from ncrads9 import i18n
from ncrads9.i18n import catalogue
from ncrads9.i18n.menus import ENGLISH, english_label, translate_menu

SIZE = 16


@pytest.fixture(autouse=True)
def english_again():
    """Leave the language as it was found, whatever a test sets."""
    yield
    i18n.set_language(i18n.DEFAULT_LANGUAGE)


# -- the catalogues ---------------------------------------------------------------


def test_ds9s_eight_languages_all_have_a_catalogue():
    found = i18n.available()
    for language in ("cs", "da", "de", "es", "fr", "ja", "pt", "zh"):
        assert language in found, language
        assert found[language] > 50, language


def test_english_needs_no_catalogue():
    """It is what the source is written in."""
    assert i18n.available()["en"] == 0
    assert catalogue.Catalogue.load("en").messages == {}


def test_every_catalogue_says_where_it_came_from():
    """These are SAOImageDS9's translations, and a file that does not say so
    is a file nobody can check."""
    for language in ("fr", "ja", "zh"):
        document = json.loads((catalogue.LOCALES / f"{language}.json").read_text(encoding="utf-8"))
        assert "SAOImageDS9" in document["source"]
        assert "GNU GPL" in document["note"]
        assert document["language"] == language


def test_a_translation_is_not_the_english():
    """The importer used to capture the *next* line of DS9's file as the
    translation, which produced entries translating `Scale` to
    `::msgcat::mcset fr {Scaling Option}`."""
    for language in ("fr", "de", "ja"):
        messages = catalogue.Catalogue.load(language).messages
        for source, translated in messages.items():
            assert translated != source, (language, source)
            assert "msgcat" not in translated, (language, source)
            assert "\n" not in translated, (language, source)


def test_a_language_that_does_not_exist_falls_back_to_english():
    """A stale preference should not stop the application starting."""
    assert i18n.set_language("klingon").language == "en"
    assert i18n.translate("Open") == "Open"


def test_a_language_with_no_file_translates_nothing():
    assert len(catalogue.Catalogue.load("xx")) == 0


# -- looking a label up -----------------------------------------------------------


def test_a_plain_label_is_translated():
    i18n.set_language("fr")
    assert i18n.translate("Colormap") == "Carte de couleurs"


def test_an_accelerator_is_taken_off_and_put_back():
    """DS9's catalogue holds `Open`, not `&Open`, so a lookup that kept the
    ampersand would translate nothing at all."""
    i18n.set_language("fr")
    assert i18n.translate("&Open") == "&Ouvrir"


def test_an_ellipsis_is_taken_off_and_put_back():
    i18n.set_language("fr")
    assert i18n.translate("&Open...") == "&Ouvrir..."


def test_the_accelerator_goes_on_the_same_letter_where_it_survives():
    i18n.set_language("fr")
    # Frame -> Fenêtre, and the F is still there.
    assert i18n.translate("&Frame") == "&Fenêtre"


def test_a_translation_without_the_letter_loses_the_accelerator():
    """Rather than getting an arbitrary one: Qt assigns its own."""
    made = catalogue.Catalogue(language="xx", messages={"Zoom": "Vergrössern"})
    assert made.translate("&Zoom") == "Vergrössern"


def test_a_label_with_no_translation_is_left_alone():
    i18n.set_language("fr")
    assert i18n.translate("Blank Inf NaN Color") == "Blank Inf NaN Color"


def test_ds9s_own_gaps_are_ds9s_gaps():
    """`Zoom` is in DS9's French file with nothing beside it, so it stays in
    English. That is a fact about the catalogue, not a bug here."""
    i18n.set_language("fr")
    assert i18n.translate("Zoom") == "Zoom"


def test_the_whole_label_is_tried_before_it_is_taken_apart():
    made = catalogue.Catalogue(language="xx", messages={"Open...": "Ouvre tout"})
    assert made.translate("Open...") == "Ouvre tout"


def test_an_empty_label_is_left_alone():
    i18n.set_language("fr")
    assert i18n.translate("") == ""


def test_english_translates_nothing():
    i18n.set_language("en")
    assert i18n.translate("&Open...") == "&Open..."


def test_the_language_in_force_is_readable():
    i18n.set_language("de")
    assert i18n.current().language == "de"
    assert len(i18n.current()) > 0


# -- the menus --------------------------------------------------------------------


def test_a_menu_bar_is_translated(qapp):
    from ncrads9.ui.menu_bar import MenuBar

    i18n.set_language("fr")
    menu = MenuBar()
    changed = translate_menu(menu)

    assert changed > 20
    assert menu.file_menu.title() == "&Fichier"
    assert menu.action_open.text() == "&Ouvrir..."


def test_submenus_are_translated_too(qapp):
    from ncrads9.ui.menu_bar import MenuBar

    i18n.set_language("fr")
    menu = MenuBar()
    translate_menu(menu)
    assert menu.preserve_menu.title() != "&Preserve During Load"


def test_translating_twice_translates_from_the_english(qapp):
    """Otherwise a second pass -- a language changed while running --
    would translate a translation."""
    from ncrads9.ui.menu_bar import MenuBar

    menu = MenuBar()
    i18n.set_language("fr")
    translate_menu(menu)
    french = menu.action_open.text()

    i18n.set_language("de")
    translate_menu(menu)
    assert menu.action_open.text() != french

    i18n.set_language("en")
    translate_menu(menu)
    assert menu.action_open.text() == "&Open..."


def test_the_english_label_is_kept_where_the_tools_can_find_it(qapp):
    """The XPA points and the parity tools look entries up by their English
    names, and have to keep working in Japanese."""
    from ncrads9.ui.menu_bar import MenuBar

    i18n.set_language("ja")
    menu = MenuBar()
    translate_menu(menu)

    assert english_label(menu.action_open) == "&Open..."
    assert menu.action_open.property(ENGLISH) == "&Open..."


def test_an_untranslated_menu_still_answers_for_its_english(qapp):
    from ncrads9.ui.menu_bar import MenuBar

    menu = MenuBar()
    assert english_label(menu.action_open) == "&Open..."


# -- the language preference ------------------------------------------------------


def test_the_language_is_a_preference():
    from ncrads9.utils import preference_defs

    found = preference_defs.by_key()["language"]
    assert found.topic == "General"
    assert set(found.choices) >= {"en", "cs", "da", "de", "es", "fr", "ja", "pt", "zh"}
    assert found.default == "en"


def test_the_window_opens_in_the_language_the_preference_names(qapp, monkeypatch, tmp_path):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: (
            "fr" if key == "language" else (False if key == "use_gpu" else default)
        ),
    )
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32)).writeto(path)

    window = MainWindow()
    try:
        assert window.menu_bar.file_menu.title() == "&Fichier"
        # And the English is still there for everything that needs it.
        assert english_label(window.menu_bar.action_open) == "&Open..."
    finally:
        window.close()


def test_the_window_opens_in_english_by_default(qapp, monkeypatch):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    try:
        assert window.menu_bar.file_menu.title() == "&File"
    finally:
        window.close()


# -- the importer -----------------------------------------------------------------


def test_the_importer_reads_ds9s_format(tmp_path):
    """Including the `encoding convertfrom` wrapper DS9 puts round accented
    translations, and the untranslated entries it leaves empty."""
    import importlib.util

    path = tmp_path / "xx.msg"
    path.write_text(
        "::msgcat::mcset xx {Add} {Ajouter}\n"
        "::msgcat::mcset xx {Zoom} \n"
        "::msgcat::mcset xx {About} [encoding convertfrom iso8859-1 {A propos}]\n"
        "::msgcat::mcset xx {Same} {Same}\n",
        encoding="iso8859-1",
    )

    root = catalogue.LOCALES.parents[2]
    spec = importlib.util.spec_from_file_location(
        "import_ds9_messages", root / "tools" / "import_ds9_messages.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    found = module.read(path)
    assert found == {"Add": "Ajouter", "About": "A propos"}
