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
Switching theme must not be able to run over a freed widget.

Applying a theme walks every live widget, and visiting one runs Python
-- so Python's cyclic collector can run inside the walk and free a
widget the walk still points at. That crashed the process: five
segfaults in six runs of one test pair, always with the same stack
(`setStyleSheet` -> the style walk -> `propagatePaletteChange` ->
`sipQComboBox::changeEvent` -> `QWidget::update`).

A crash cannot be asserted directly -- a test that segfaults takes the
whole run with it -- so these gates measure the conditions that made it
possible instead: that nothing is waiting to die when the walk starts,
and that nothing can die during it. The last one is the important one,
because it is checked from *inside* the walk.
"""

from __future__ import annotations

import gc

import pytest
from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QComboBox, QWidget

from ncrads9.ui.themes import restyle


class Probe(QComboBox):
    """A widget that reports on the world from inside the style walk.

    A combo box because that is what the crashing stack named: every
    widget built from Python has a sip subclass whose `changeEvent`
    re-enters the interpreter, which is where a collection can start.
    """

    def __init__(self) -> None:
        super().__init__()
        self.collector_was_enabled: list[bool] = []
        self.visits = 0

    def changeEvent(self, event) -> None:
        if event is not None and event.type() in (
            QEvent.Type.PaletteChange,
            QEvent.Type.StyleChange,
        ):
            self.visits += 1
            self.collector_was_enabled.append(gc.isenabled())
        super().changeEvent(event)


@pytest.fixture
def probe(qapp):
    """A live, visited widget -- and gone again afterwards."""
    made = Probe()
    made.addItems(["one", "two"])
    made.show()
    qapp.processEvents()
    yield made
    made.close()
    made.deleteLater()
    qapp.processEvents()


@pytest.fixture(autouse=True)
def collector_restored():
    """No test here may leave the collector off."""
    was = gc.isenabled()
    yield
    if was and not gc.isenabled():
        gc.enable()
        pytest.fail("a test left the cyclic collector disabled")


# -- the mechanism ----------------------------------------------------------------


def test_the_walk_is_visited_at_all(qapp, probe):
    """The rest of this file is worthless if the probe is never reached."""
    restyle.restyle(qapp, None, "QLabel { color: #010203; }")
    assert probe.visits > 0, "the style walk never reached the probe"


def test_no_collection_can_start_inside_the_walk(qapp, probe):
    """The gate for the crash.

    `changeEvent` is delivered from inside Qt's widget walk while the
    walk holds pointers to widgets it has not reached yet. A collection
    there can free one of them.
    """
    restyle.restyle(qapp, None, "QLabel { color: #040506; }")
    assert probe.collector_was_enabled, "the probe was never visited"
    assert not any(probe.collector_was_enabled), "the collector was live inside the style walk"


def test_the_collector_is_on_again_afterwards(qapp):
    """Held off for the walk, not for the process."""
    assert gc.isenabled()
    restyle.restyle(qapp, None, "")
    assert gc.isenabled()


def test_the_collector_is_on_again_after_a_failure(qapp, monkeypatch):
    """A theme that blows up half way must not leave the collector off
    for the rest of the session."""

    def explode(_app, _sheet):
        raise RuntimeError("bad stylesheet")

    monkeypatch.setattr(type(qapp), "setStyleSheet", explode)
    with pytest.raises(RuntimeError):
        restyle.restyle(qapp, None, "QLabel {}")
    assert gc.isenabled()


def test_a_collector_already_off_stays_off(qapp):
    """Nesting, and anyone who has turned it off deliberately: the
    context manager restores what it found, it does not impose."""
    gc.disable()
    try:
        restyle.restyle(qapp, None, "")
        assert not gc.isenabled(), "restyle re-enabled a collector it did not disable"
    finally:
        gc.enable()


def test_nothing_is_waiting_to_die_when_the_walk_starts(qapp):
    """Qt's DeferredDelete queue is drained first, so a widget that has
    been asked to die is not still standing during the walk."""
    doomed = QWidget()
    doomed.show()
    qapp.processEvents()
    doomed.deleteLater()
    seen: list[bool] = []
    with restyle.no_widget_may_die(qapp):
        try:
            doomed.isVisible()
            seen.append(True)
        except RuntimeError:
            seen.append(False)
    assert seen == [False], "a widget pending deletion was still alive inside the walk"


# -- every theme goes through it ---------------------------------------------------


@pytest.mark.parametrize("theme", ["System", "Light", "Dark"])
def test_every_theme_applies_under_the_protection(qapp, probe, theme):
    """Behavioural, not a check that `apply` calls a particular
    function: each theme is applied for real and the probe reports what
    the world looked like from inside that theme's own walk. A theme
    added later that sets the palette itself fails this."""
    from ncrads9.ui.controllers.edit import THEMES

    try:
        THEMES[theme].apply(qapp)
        assert probe.collector_was_enabled, f"{theme} never reached the probe"
        assert not any(probe.collector_was_enabled), f"{theme} walked with the collector live"
    finally:
        THEMES["System"].apply(qapp)


def test_no_theme_reaches_past_restyle(qapp):
    """The application-wide setters are the dangerous ones, and they
    belong to one module now. A theme calling them directly would be
    unprotected however careful the rest of this file is."""
    import pathlib

    themes = pathlib.Path("ncrads9/ui/themes")
    offenders = []
    for path in sorted(themes.glob("*.py")):
        if path.name == "restyle.py":
            continue
        text = path.read_text()
        for setter in ("app.setStyleSheet(", "app.setPalette(", "app.setStyle("):
            if setter in text:
                offenders.append(f"{path.name}: {setter}")
    assert offenders == [], "\n".join(offenders)
