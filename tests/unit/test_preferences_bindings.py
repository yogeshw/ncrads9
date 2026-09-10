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

"""Preferences across DS9's topics, and the shortcut editor (M9-32, M9-33)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits
from PyQt6.QtGui import QKeySequence

from ncrads9.ui import bindings
from ncrads9.utils import preference_defs

SIZE = 16


# -- the preference table ---------------------------------------------------------


def test_the_topics_are_ds9s():
    """Someone who knows where a setting lives in DS9 should find it in the
    same place here (`prefsdialog.tcl:57`)."""
    for topic in ("General", "Precision", "Startup", "Scale", "Color", "Region", "Print"):
        assert topic in preference_defs.TOPICS


def test_nearly_every_topic_has_something_on_it():
    """An empty page in the list is a promise the dialog does not keep."""
    filled = preference_defs.by_topic()
    assert len(filled) >= len(preference_defs.TOPICS) - 1


def test_every_preference_is_one_of_the_kinds_the_dialog_can_draw():
    for preference in preference_defs.PREFERENCES:
        assert preference.kind in preference_defs.KINDS, preference.key


def test_every_preference_belongs_to_a_topic_that_exists():
    for preference in preference_defs.PREFERENCES:
        assert preference.topic in preference_defs.TOPICS, preference.key


def test_no_two_preferences_share_a_key():
    keys = [preference.key for preference in preference_defs.PREFERENCES]
    assert len(keys) == len(set(keys))


def test_every_choice_preference_defaults_to_one_of_its_choices():
    """A default outside the list means the combo silently shows something
    else the first time it opens."""
    for preference in preference_defs.PREFERENCES:
        if preference.kind == "choice":
            assert preference.default in preference.choices, preference.key


def test_every_numeric_default_is_inside_its_range():
    for preference in preference_defs.PREFERENCES:
        if preference.kind in ("int", "float"):
            assert preference.minimum <= preference.default <= preference.maximum, preference.key


def test_the_defaults_are_the_table():
    defaults = preference_defs.defaults()
    assert len(defaults) == len(preference_defs.PREFERENCES)
    assert defaults["theme"] == "System"


def test_the_controller_takes_its_defaults_from_the_table(qapp):
    """Two lists of defaults is one list too many."""
    from ncrads9.ui.controllers.edit import PREFERENCE_DEFAULTS

    for key, value in preference_defs.defaults().items():
        assert PREFERENCE_DEFAULTS[key] == value


# -- the bindings table ------------------------------------------------------------


def test_every_binding_names_a_real_menu_action(qapp):
    from ncrads9.ui.menu_bar import MenuBar

    menu = MenuBar()
    for binding in bindings.BINDINGS:
        assert getattr(menu, binding.action, None) is not None, binding.name


def test_no_two_bindings_share_a_name():
    names = [binding.name for binding in bindings.BINDINGS]
    assert len(names) == len(set(names))


def test_the_default_shortcuts_do_not_clash():
    """Two commands on one combination means one never fires."""
    assert bindings.conflicts({b.name: b.default for b in bindings.BINDINGS}) == {}


def test_every_default_shortcut_is_a_shortcut():
    for binding in bindings.BINDINGS:
        assert not QKeySequence(binding.default).isEmpty(), binding.name


def test_conflicts_are_found():
    found = bindings.conflicts({"a": "Ctrl+O", "b": "Ctrl+O", "c": "Ctrl+P"})
    assert list(found) == ["Ctrl+O"]
    assert sorted(found["Ctrl+O"]) == ["a", "b"]


def test_an_empty_shortcut_is_not_a_conflict():
    """Two commands with no shortcut are not fighting over one."""
    assert bindings.conflicts({"a": "", "b": ""}) == {}


def test_applying_a_shortcut_reaches_the_menu(qapp):
    from ncrads9.ui.menu_bar import MenuBar

    menu = MenuBar()
    applied = bindings.apply(menu, {"open": "Ctrl+Shift+O"})
    assert applied["open"] == "Ctrl+Shift+O"
    assert menu.action_open.shortcut().toString() == "Ctrl+Shift+O"


def test_a_shortcut_can_be_removed(qapp):
    """Which is a legitimate thing to want: a combination taken back for
    something else."""
    from ncrads9.ui.menu_bar import MenuBar

    menu = MenuBar()
    bindings.apply(menu, {"open": ""})
    assert menu.action_open.shortcut().toString() == ""


def test_what_is_not_overridden_keeps_its_default(qapp):
    from ncrads9.ui.menu_bar import MenuBar

    menu = MenuBar()
    applied = bindings.apply(menu, {"open": "Ctrl+Shift+O"})
    assert applied["save"] == "Ctrl+S"


def test_the_preferences_store_fills_in_the_defaults():
    class Store:
        def get(self, key, default=None):
            return "Ctrl+Alt+O" if key == "shortcut.open" else default

    found = bindings.from_preferences(Store())
    assert found["open"] == "Ctrl+Alt+O"
    assert found["save"] == "Ctrl+S"


# -- the dialog --------------------------------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32)).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    yield window
    window.close()


@pytest.fixture
def dialog(main_window):
    from ncrads9.ui.dialogs.preferences_dialog import PreferencesDialog

    made = PreferencesDialog(main_window)
    made.load_preferences(main_window.edit.preferences_dict())
    yield made
    made.close()


def test_the_dialog_lists_every_topic(dialog):
    listed = [dialog.topics.item(row).text() for row in range(dialog.topics.count())]
    assert "General" in listed
    assert "Bindings" in listed
    assert len(listed) >= 25


def test_the_dialog_has_a_control_for_every_preference(dialog):
    """Which is what generating them from the table buys."""
    for preference in preference_defs.PREFERENCES:
        assert preference.key in dialog.editors, preference.key


def test_choosing_a_topic_shows_its_page(dialog):
    listed = [dialog.topics.item(row).text() for row in range(dialog.topics.count())]
    dialog.topics.setCurrentRow(listed.index("Scale"))
    assert dialog._pages["Scale"].isVisibleTo(dialog)
    assert not dialog._pages["General"].isVisibleTo(dialog)


def test_the_values_round_trip(dialog):
    dialog.load_preferences(
        {
            "autosave": False,
            "autosave_interval": 12,
            "theme": "Dark",
            "nan_color": "#123456",
            "http_proxy": "proxy.example",
            "examine_zoom": 8.0,
        }
    )
    values = dialog.values()
    assert values["autosave"] is False
    assert values["autosave_interval"] == 12
    assert values["theme"] == "Dark"
    assert values["nan_color"] == "#123456"
    assert values["http_proxy"] == "proxy.example"
    assert values["examine_zoom"] == pytest.approx(8.0)


def test_a_preference_the_table_does_not_know_is_ignored(dialog):
    """An old preferences file should not stop the dialog opening."""
    dialog.load_preferences({"a_setting_from_1998": True})
    assert "a_setting_from_1998" not in dialog.values()


def test_applying_emits_every_preference(dialog):
    seen: list[dict] = []
    dialog.preferences_changed.connect(seen.append)
    dialog.buttons["apply"].click()

    assert seen
    for preference in preference_defs.PREFERENCES:
        assert preference.key in seen[0]
    # And the shortcuts, which are preferences too.
    assert "shortcut.open" in seen[0]


def test_restoring_defaults_puts_everything_back(dialog):
    dialog.load_preferences({"autosave_interval": 99, "theme": "Dark"})
    dialog.buttons["defaults"].click()
    values = dialog.values()
    assert values["autosave_interval"] == preference_defs.by_key()["autosave_interval"].default
    assert values["theme"] == "System"


def test_the_old_settings_method_still_works(dialog):
    """The Edit controller and its tests call it by that name."""
    assert dialog._get_settings() == dialog.values()


# -- the shortcut editor -----------------------------------------------------------


def test_the_editor_has_a_row_for_every_binding(dialog):
    assert dialog.shortcut_table.rowCount() == len(bindings.BINDINGS)
    for binding in bindings.BINDINGS:
        assert binding.name in dialog.shortcut_editors


def test_the_editor_starts_from_the_defaults(dialog):
    assert dialog.shortcut_editors["open"].keySequence().toString() == "Ctrl+O"


def test_changing_a_shortcut_comes_out_in_the_values(dialog):
    dialog.shortcut_editors["open"].setKeySequence(QKeySequence("Ctrl+Alt+O"))
    assert dialog.values()["shortcut.open"] == "Ctrl+Alt+O"


def test_a_conflict_is_pointed_out_rather_than_left_to_qt(dialog):
    dialog.shortcut_editors["open"].setKeySequence(QKeySequence("Ctrl+S"))
    clashes = dialog.check_conflicts()
    assert "Ctrl+S" in clashes
    assert "Conflicts:" in dialog._conflicts.text()
    assert "Open" in dialog._conflicts.text()


def test_no_conflict_says_nothing(dialog):
    dialog.check_conflicts()
    assert dialog._conflicts.text() == ""


def test_the_shortcuts_can_be_restored_on_their_own(dialog):
    dialog.shortcut_editors["open"].setKeySequence(QKeySequence("Ctrl+Alt+O"))
    dialog.load_preferences({"theme": "Dark"})
    dialog.restore_shortcuts()
    assert dialog.shortcut_editors["open"].keySequence().toString() == "Ctrl+O"
    # And nothing else was touched.
    assert dialog.values()["theme"] == "Dark"


def test_applying_preferences_changes_the_menus_shortcut(main_window):
    main_window.edit.apply_preferences({"shortcut.open": "Ctrl+Alt+O"}, persist=False, show_message=False)
    assert main_window.menu_bar.action_open.shortcut().toString() == "Ctrl+Alt+O"


def test_the_shortcuts_are_applied_at_startup(main_window):
    """A shortcut kept in the preferences has to reach the menu without the
    dialog being opened."""
    assert main_window.menu_bar.action_open.shortcut().toString() == "Ctrl+O"
    assert main_window.menu_bar.action_console.shortcut().toString() != ""
