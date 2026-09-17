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
DS9's eight Help entries, and whether they can be read.

The Help menu scored zero on parity: DS9's eight entries all open its
bundled documentation, and NCRADS9 offered a contents page, a shortcut list
and two About boxes -- nothing under any name a DS9 user knew. All eight are
answered now with NCRADS9's own material.

Two of the eight are generated rather than written, and those have the
gates that matter, because a written page that lists commands goes stale
the first time one is added: the reference manual must name every XPA
access point, and the release notes must name the package's own version.

The last group is the reason the contents page is in here too. Its
stylesheet named its colours outright -- `color: #2e3436` -- so under the
dark theme it drew near-black text on a near-black ground: the grey-on-grey
fault reported for the popups, surviving inside one of them because it was
in the *document*, where a widget palette cannot reach. The gate measures
rendered pixels, since that is the only place the fault was visible.
"""

from __future__ import annotations

from collections import Counter

import pytest
from PyQt6.QtGui import QPalette, QPixmap

from ncrads9 import __version__
from ncrads9.ui import help_documents
from ncrads9.ui.dialogs.help_contents_dialog import HelpContentsDialog
from ncrads9.ui.dialogs.help_document_dialog import HelpDocumentDialog

#: DS9's eight, in DS9's order (`.help` in docs/parity/ds9_menus.txt).
DS9_HELP_LABELS = (
    "Reference Manual",
    "User Manual",
    "FAQ",
    "Release Notes",
    "Help Desk",
    "Story of SAOImageDS9",
    "Acknowledgment",
    "About SAOImageDS9",
)

#: A luma gap below this reads as "text the same colour as its background".
#: The contents page under the dark theme measured 13.
MINIMUM_LUMA_GAP = 60


def _luma(colour) -> float:
    """Rec. 601 brightness, which is what the eye is doing here."""
    return 0.299 * colour.red() + 0.587 * colour.green() + 0.114 * colour.blue()


@pytest.fixture
def window(qapp, monkeypatch):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    made = MainWindow()
    made._rebuild_image_viewer(False)
    yield made
    made.close()


# -- the eight entries -------------------------------------------------------------


def test_the_menu_offers_every_ds9_entry_in_ds9s_order(window):
    labels = [
        action.text().replace("&", "")
        for action in window.menu_bar.help_menu.actions()
        if not action.isSeparator()
    ]
    assert labels[: len(DS9_HELP_LABELS)] == list(DS9_HELP_LABELS)


def test_our_own_entries_are_still_there(window):
    labels = [action.text().replace("&", "") for action in window.menu_bar.help_menu.actions()]
    for kept in ("Contents", "Keyboard Shortcuts", "About NCRADS9", "About Qt"):
        assert kept in labels


def test_every_entry_has_a_document_behind_it(window):
    assert len(help_documents.DOCUMENTS) == 8
    for name in help_documents.BY_NAME:
        assert name in window.menu_bar.help_document_actions


@pytest.mark.parametrize("document", help_documents.DOCUMENTS, ids=lambda d: d.name)
def test_a_document_says_something(document):
    """A menu entry that opens an empty window is worse than one that is
    missing: the user cannot tell it is unfinished."""
    body = document.html()
    assert len(body) > 500, f"{document.name} is a stub"
    assert document.title
    assert "<p" in body or "<ul" in body or "<table" in body


@pytest.mark.parametrize("name", list(help_documents.BY_NAME))
def test_choosing_an_entry_opens_its_window(window, name):
    window.menu_bar.help_document_actions[name].trigger()
    assert name in window.help._open
    opened = window.help._open[name]
    assert isinstance(opened, HelpDocumentDialog)
    assert opened.document.name == name
    opened.close()


def test_opening_one_twice_raises_the_first_window(window):
    window.menu_bar.help_document_actions["faq"].trigger()
    first = window.help._open["faq"]
    window.menu_bar.help_document_actions["faq"].trigger()
    assert window.help._open["faq"] is first
    first.close()


def test_an_unknown_document_is_reported_not_raised(window):
    window.help.show_document("no_such_page")
    assert "no_such_page" not in window.help._open


# -- the two generated pages -------------------------------------------------------


def test_the_reference_manual_names_every_access_point():
    """Generated from the table that implements them, so a point added
    without a line here is impossible."""
    from ncrads9.communication.xpa.access_points import ALL_POINTS

    body = help_documents.reference_manual()
    missing = [point.name for point in ALL_POINTS if point.name not in body]
    assert missing == [], f"absent from the reference manual: {missing}"


def test_the_reference_manual_names_the_aliases_too():
    from ncrads9.communication.xpa.access_points import ALL_POINTS

    body = help_documents.reference_manual()
    for point in ALL_POINTS:
        for alias in point.aliases or ():
            assert alias in body, f"{point.name}'s alias {alias} is not listed"


def test_the_reference_manual_says_how_to_use_it():
    body = help_documents.reference_manual()
    assert "xpaget" in body and "xpaset" in body


def test_the_release_notes_carry_the_packages_own_version():
    """Not a literal: a version written into the page falls behind
    `pyproject.toml` at the next release."""
    assert __version__ in help_documents.release_notes()


# -- readable under every theme ----------------------------------------------------


@pytest.mark.parametrize("theme", ["System", "Light", "Dark"])
def test_every_colour_a_document_uses_is_readable(qapp, theme):
    """Measured off the stylesheet, for each theme's own palette: the page's
    text, headings and links against the page's background."""
    from PyQt6.QtGui import QColor

    from ncrads9.ui.controllers.edit import THEMES

    try:
        THEMES[theme].apply(qapp)
        palette = qapp.palette()
        sheet = help_documents.stylesheet(palette)
        base = palette.color(QPalette.ColorRole.Base)
        for role in ("Text", "Link"):
            colour = palette.color(getattr(QPalette.ColorRole, role))
            gap = abs(_luma(colour) - _luma(base))
            assert gap >= MINIMUM_LUMA_GAP, f"{theme}: {role} {colour.name()} on {base.name()}, gap {gap:.0f}"
        # And the sheet really is using them rather than a literal.
        assert palette.color(QPalette.ColorRole.Text).name() in sheet
        assert QColor(base).name() in sheet
    finally:
        THEMES["System"].apply(qapp)


def _rendered_gap(dialog) -> float:
    """The widest luma gap between the page's background and its text.

    Rendered pixels rather than the stylesheet, because the fault was that
    a document ignored the palette entirely -- a stylesheet check would
    have passed while the page stayed unreadable.
    """
    pixmap = QPixmap(700, 450)
    dialog.render(pixmap)
    image = pixmap.toImage()
    counted = Counter(image.pixelColor(x, y).name() for y in range(60, 400, 2) for x in range(20, 660, 2))
    from PyQt6.QtGui import QColor

    background = QColor(counted.most_common(1)[0][0])
    return max(
        (abs(_luma(QColor(name)) - _luma(background)) for name, count in counted.items() if count >= 25),
        default=0.0,
    )


@pytest.mark.parametrize("theme", ["Light", "Dark"])
def test_a_help_page_is_readable_once_drawn(window, qapp, theme):
    """The regression test for the reported fault, on the page that had it
    and on the eight new ones."""
    from ncrads9.ui.controllers.edit import THEMES

    try:
        THEMES[theme].apply(qapp)
        unreadable = []
        pages = [("Contents", HelpContentsDialog(window))] + [
            (document.title, HelpDocumentDialog(document, window)) for document in help_documents.DOCUMENTS
        ]
        for title, dialog in pages:
            dialog.resize(700, 450)
            dialog.show()
            qapp.processEvents()
            gap = _rendered_gap(dialog)
            if gap < MINIMUM_LUMA_GAP:
                unreadable.append(f"{title}: widest gap {gap:.0f}")
            dialog.close()
            dialog.deleteLater()
        assert unreadable == [], "\n".join(unreadable)
    finally:
        THEMES["System"].apply(qapp)


def test_a_page_re_renders_when_the_theme_changes_under_it(window, qapp):
    """The colours are baked into the HTML when it is rendered, so a palette
    change has to rebuild the document; a repaint cannot reach inside it."""
    from ncrads9.ui.controllers.edit import THEMES

    try:
        THEMES["Light"].apply(qapp)
        dialog = HelpDocumentDialog(help_documents.BY_NAME["faq"], window)
        dialog.show()
        qapp.processEvents()
        light = dialog.browser.toHtml()

        THEMES["Dark"].apply(qapp)
        qapp.processEvents()
        assert dialog.browser.toHtml() != light, "the page kept the light theme's colours"
        dialog.close()
        dialog.deleteLater()
    finally:
        THEMES["System"].apply(qapp)


def test_the_contents_page_no_longer_names_its_own_colours():
    """The fault in one line. A colour written into the document cannot
    follow a theme, so none may be written in."""
    assert "#2e3436" not in HelpContentsDialog.HELP_HTML
    assert "color:" not in HelpContentsDialog.HELP_HTML
