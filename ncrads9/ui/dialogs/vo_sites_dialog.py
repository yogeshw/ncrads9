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
DS9's Virtual Observatory window (`VODialog`, `vo.tcl`).

DS9 keeps a list of VO analysis sites on the web, one per line as
`host<TAB>title<TAB>url`, fetched from the Chandra site with a second
source behind it and a built-in list if neither answers. The window shows
one checkbox per site; ticking one opens the site in the web browser,
from which the site sends data back to DS9.

DS9 can also connect to a site's XPA proxy (`xparemote`); NCRADS9 has no
remote XPA, so a site is reached through the browser alone, which is what
DS9's default method, `mime`, does anyway.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QAction, QDesktopServices, QKeySequence
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenuBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .modeless import make_modeless

#: Where DS9 looks for its list of sites, in order (`VOApply`).
SITE_LISTS: tuple[str, ...] = (
    "https://cxc.harvard.edu/chandraed/list.txt",
    "https://xray1.physics.rutgers.edu/vo/list.txtt",
)

#: DS9's own list for when neither answers.
DEFAULT_SITES = (
    "xray1.physics.rutgers.edu:28571\tRutgers Primary MOOC X-ray Analysis Server\t"
    "https://xray1.physics.rutgers.edu/archive.html\n"
    "rinzai.rutgers.edu:28571\tRutgers X-ray Analysis Server #2\thttps://rinzai.rutgers.edu/archive.html"
)

#: DS9's Help Me Choose.
HELP_URL = "https://ds9.si.edu/doc/ref/vo.html"


@dataclass(frozen=True)
class Site:
    """One VO site: its XPA host, its title and its web page."""

    host: str
    title: str
    url: str


def parse_sites(text: str) -> list[Site]:
    """DS9's site list: `host<TAB>title<TAB>url`, one per line (`VOParse`)."""
    sites = []
    for line in text.strip().splitlines():
        fields = line.split("\t")
        if len(fields) >= 3 and fields[2].strip():
            sites.append(Site(fields[0].strip(), fields[1].strip(), fields[2].strip()))
    return sites


def _fetch(url: str, timeout: float = 5.0) -> str:
    import urllib.request

    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def load_sites(fetch: Callable[[str], str] = _fetch) -> tuple[list[Site], str | None]:
    """The sites, from the first list that answers, or DS9's default list.

    Returns:
        The sites, and a note if the default list had to be used.
    """
    for url in SITE_LISTS:
        try:
            sites = parse_sites(fetch(url))
        except Exception:
            continue
        if sites:
            return sites, None
    return (
        parse_sites(DEFAULT_SITES),
        "Unable to access VO server list, please verify internet connection. Using default list.",
    )


class VOSitesDialog(QDialog):
    """The Virtual Observatory window.

    Args:
        parent: The main window.
        fetch: How the site list is read; replaced in tests.
        open_url: How a site is opened; the web browser by default.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        fetch: Callable[[str], str] = _fetch,
        open_url: Callable[[str], object] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Virtual Observatory")
        make_modeless(self)
        self._fetch = fetch
        self._open_url = open_url or (lambda url: QDesktopServices.openUrl(QUrl(url)))
        self._window = parent
        self.sites: list[Site] = []
        self.boxes: list[QCheckBox] = []

        layout = QVBoxLayout(self)
        layout.setMenuBar(self._build_menus())
        self._sites_group = QGroupBox("Sites")
        self._sites_layout = QVBoxLayout(self._sites_group)
        layout.addWidget(self._sites_group)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        buttons = QHBoxLayout()
        for label, slot in (
            ("Apply", self.apply),
            ("Help Me Choose", self.help_me_choose),
            ("Configure", self.configure),
            ("Close", self.close),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, s=slot: s())
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.apply()

    def _build_menus(self) -> QMenuBar:
        bar = QMenuBar(self)
        file_menu = bar.addMenu("&File")
        for label, slot in (
            ("Apply", self.apply),
            ("Cancel", self.cancel),
            (None, None),
            ("Help Me Choose", self.help_me_choose),
            ("Configure", self.configure),
            (None, None),
            ("Close", self.close),
        ):
            if label is None:
                file_menu.addSeparator()
                continue
            action = QAction(label, self)
            if label == "Close":
                action.setShortcut(QKeySequence(QKeySequence.StandardKey.Close))
            action.triggered.connect(lambda _checked=False, s=slot: s())
            file_menu.addAction(action)
        return bar

    # -- the list ------------------------------------------------------------

    def apply(self) -> None:
        """DS9's Apply: read the site list again and show it."""
        for box in self.boxes:
            box.deleteLater()
        self.boxes = []
        self.sites, note = load_sites(self._fetch)
        self.message.setText(note or "")
        for index, site in enumerate(self.sites):
            box = QCheckBox(f"{site.title} ({site.url})")
            box.toggled.connect(lambda on, i=index: self.check(i, on))
            self._sites_layout.addWidget(box)
            self.boxes.append(box)

    def cancel(self) -> None:
        """DS9's Cancel: untick every site."""
        for box in self.boxes:
            box.blockSignals(True)
            box.setChecked(False)
            box.blockSignals(False)

    def check(self, index: int, on: bool) -> None:
        """DS9's `VOCheck`: a ticked site is opened in the web browser."""
        if on and 0 <= index < len(self.sites):
            self._open_url(self.sites[index].url)

    # -- the buttons ---------------------------------------------------------

    def help_me_choose(self) -> None:
        """DS9's Help Me Choose: its page about the VO sites."""
        self._open_url(HELP_URL)

    def configure(self) -> None:
        """DS9's Configure: the HTTP preferences, where a proxy is set."""
        edit = getattr(self._window, "edit", None)
        if edit is not None and hasattr(edit, "show_preferences"):
            edit.show_preferences()
