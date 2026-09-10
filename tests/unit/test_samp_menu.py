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

"""File -> SAMP and File -> SAMP Hub (M9-27, M9-28).

Nothing here talks to a real hub: a SAMP hub is another process, and a test
that started one would be testing astropy's hub rather than ours. What is
tested is what this application does -- what it broadcasts, to whom, and
what it says when it cannot.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

SIZE = 16


class FakeClient:
    """A SAMP client that writes down what it was asked to send."""

    def __init__(self, connected: bool = True, sends: bool = True) -> None:
        self.connected = connected
        self.sends = sends
        self.sent: list[tuple[str, str, str | None]] = []
        self.clients = [
            {"id": "c1", "name": "Topcat"},
            {"id": "c2", "name": "Aladin"},
        ]

    def is_connected(self) -> bool:
        return self.connected

    def get_registered_clients(self):
        return self.clients

    def send_image(self, url, recipient=None, name=None) -> bool:
        self.sent.append(("image", url, recipient))
        return self.sends

    def send_table(self, url, table_id=None, recipient=None) -> bool:
        self.sent.append(("table", url, recipient))
        return self.sends

    def disconnect(self) -> None:
        self.connected = False


class FakeHub:
    """A hub that starts and stops without a process."""

    def __init__(self, starts: bool = True) -> None:
        self.starts = starts
        self.running = False
        self.web = None

    def start(self, web_profile: bool = True) -> bool:
        self.web = web_profile
        self.running = self.starts
        return self.running

    def stop(self) -> None:
        self.running = False

    def is_running(self) -> bool:
        return self.running


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32)).writeto(path)
    return path


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path, image):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(image))
    yield window
    window.close()


@pytest.fixture
def connected(main_window):
    """A window that thinks it is connected to a hub."""
    client = FakeClient()
    main_window._samp_client = client
    main_window._samp_connected = True
    main_window.samp.sync()
    return client


# -- the menus ------------------------------------------------------------------


def test_the_file_menu_has_ds9s_two_samp_submenus(main_window):
    menu = main_window.menu_bar
    assert [
        action.text().replace("&", "") for action in menu.samp_file_menu.actions() if not action.isSeparator()
    ] == ["Connect", "Disconnect", "Image", "Table"]
    assert [
        action.text().replace("&", "") for action in menu.samp_hub_menu.actions() if not action.isSeparator()
    ] == ["Information", "Start", "Stop"]


def test_image_and_table_each_have_a_broadcast(main_window):
    for kind in ("image", "table"):
        submenu = main_window.menu_bar.samp_broadcast_menus[kind]
        assert submenu.actions()[0].text().replace("&", "") == "Broadcast"


def test_broadcasting_is_off_until_connected(main_window):
    for action in main_window.menu_bar.samp_broadcast_actions.values():
        assert action.isEnabled() is False


def test_connecting_enables_broadcasting(main_window, connected):
    for action in main_window.menu_bar.samp_broadcast_actions.values():
        assert action.isEnabled() is True
    assert main_window.menu_bar.action_samp_file_connect.isEnabled() is False
    assert main_window.menu_bar.action_samp_file_disconnect.isEnabled() is True


def test_the_registered_clients_appear_under_each_kind(main_window, connected):
    """A broadcast goes to everything; the entries under it send to one,
    which is how you get an image into Topcat and not into Aladin."""
    for kind in ("image", "table"):
        labels = [
            action.text()
            for action in main_window.menu_bar.samp_broadcast_menus[kind].actions()
            if not action.isSeparator()
        ]
        assert labels == ["&Broadcast", "Topcat", "Aladin"]


def test_the_client_list_is_rebuilt_rather_than_appended_to(main_window, connected):
    """Otherwise every refresh doubles it."""
    main_window.samp.refresh_clients()
    main_window.samp.refresh_clients()
    labels = [
        action.text()
        for action in main_window.menu_bar.samp_broadcast_menus["image"].actions()
        if not action.isSeparator()
    ]
    assert labels == ["&Broadcast", "Topcat", "Aladin"]


def test_disconnecting_empties_the_client_list(main_window, connected):
    main_window.samp.disconnect_hub()
    labels = [
        action.text()
        for action in main_window.menu_bar.samp_broadcast_menus["image"].actions()
        if not action.isSeparator()
    ]
    assert labels == ["&Broadcast"]


# -- broadcasting ----------------------------------------------------------------


def test_broadcasting_an_image_sends_its_url(main_window, connected, image):
    """SAMP passes a URL rather than the bytes, so what goes is a file
    URL the other application can open."""
    assert main_window.samp.broadcast("image") is True
    kind, url, recipient = connected.sent[0]
    assert kind == "image"
    assert url == image.as_uri()
    assert recipient is None


def test_broadcasting_to_one_client(main_window, connected):
    assert main_window.samp.broadcast("image", "c1") is True
    assert connected.sent[0][2] == "c1"


def test_the_client_entries_send_to_that_client(main_window, connected):
    entries = [
        action
        for action in main_window.menu_bar.samp_broadcast_menus["image"].actions()
        if action.text() == "Aladin"
    ]
    entries[0].trigger()
    assert connected.sent[0][2] == "c2"


def test_broadcasting_without_a_hub_says_so(main_window):
    assert main_window.samp.broadcast("image") is False
    assert "Connect to a SAMP hub first" in main_window.status_bar.currentMessage()


def test_broadcasting_a_frame_with_no_file_says_so(main_window, connected):
    """A frame whose pixels came from an array over XPA has no URL to
    send, and a broken URL would be worse than a message."""
    main_window.frame_controller.new_frame()
    main_window.display.load_array(np.zeros((4, 4), dtype=np.float32))
    assert main_window.samp.broadcast("image") is False
    assert "no file behind it" in main_window.status_bar.currentMessage()


def test_a_send_that_fails_is_reported(main_window):
    main_window._samp_client = FakeClient(sends=False)
    main_window._samp_connected = True
    assert main_window.samp.broadcast("image") is False
    assert "could not be broadcast" in main_window.status_bar.currentMessage()


def test_something_that_is_not_broadcast_is_refused(main_window, connected):
    assert main_window.samp.broadcast("spectrum") is False
    assert "not something SAMP broadcasts" in main_window.status_bar.currentMessage()


def test_broadcasting_a_table_sends_the_catalogue_it_came_from(main_window, connected, tmp_path):
    from astropy.table import Table

    from ncrads9.catalogs.catalog_set import LoadedCatalog

    path = tmp_path / "cat.tsv"
    path.write_text("A\tB\n1\t2\n")
    main_window.catalog.add(LoadedCatalog(name="cat", table=Table({"A": [1], "B": [2]}), source=str(path)))

    assert main_window.samp.broadcast("table") is True
    kind, url, _recipient = connected.sent[-1]
    assert kind == "table"
    assert url == path.as_uri()


def test_broadcasting_a_table_that_was_never_saved_says_so(main_window, connected):
    from astropy.table import Table

    from ncrads9.catalogs.catalog_set import LoadedCatalog

    main_window.catalog.add(LoadedCatalog(name="from a server", table=Table({"A": [1]})))
    assert main_window.samp.broadcast("table") is False
    assert "no file behind it" in main_window.status_bar.currentMessage()


# -- the hub ---------------------------------------------------------------------


def test_starting_and_stopping_the_hub(main_window):
    hub = FakeHub()
    main_window.samp.hub = hub

    assert main_window.samp.start_hub() is True
    assert hub.running is True
    assert "SAMP hub started" in main_window.status_bar.currentMessage()

    assert main_window.samp.stop_hub() is True
    assert hub.running is False
    assert "stopped" in main_window.status_bar.currentMessage()


def test_the_hub_serves_the_web_profile_by_default(main_window):
    """M9-28: a browser-based tool can only join over the web profile."""
    hub = FakeHub()
    main_window.samp.hub = hub
    main_window.samp.start_hub()
    assert hub.web is True
    assert "web profile" in main_window.status_bar.currentMessage()


def test_the_web_profile_can_be_turned_off(main_window):
    hub = FakeHub()
    main_window.samp.hub = hub
    main_window.samp.web_profile = False
    main_window.samp.start_hub()
    assert hub.web is False


def test_the_menu_greys_out_what_makes_no_sense(main_window):
    hub = FakeHub()
    main_window.samp.hub = hub
    main_window.samp.sync()
    assert main_window.menu_bar.action_samp_hub_start.isEnabled() is True
    assert main_window.menu_bar.action_samp_hub_stop.isEnabled() is False

    main_window.samp.start_hub()
    assert main_window.menu_bar.action_samp_hub_start.isEnabled() is False
    assert main_window.menu_bar.action_samp_hub_stop.isEnabled() is True


def test_starting_a_hub_twice_is_harmless(main_window):
    main_window.samp.hub = FakeHub()
    main_window.samp.start_hub()
    assert main_window.samp.start_hub() is True
    assert "already running" in main_window.status_bar.currentMessage()


def test_stopping_a_hub_that_is_not_running(main_window):
    assert main_window.samp.stop_hub() is True
    assert "No SAMP hub is running here" in main_window.status_bar.currentMessage()


def test_a_hub_that_will_not_start_is_reported(main_window):
    main_window.samp.hub = FakeHub(starts=False)
    assert main_window.samp.start_hub() is False
    assert "could not be started" in main_window.status_bar.currentMessage()


def test_information_says_what_is_there(main_window, connected):
    main_window.samp.hub = FakeHub()
    main_window.samp.start_hub()

    text = main_window.samp.information()
    assert "running here" in text
    assert "Web profile: yes" in text
    assert "Connected: yes" in text
    assert "Registered clients: 2" in text
    assert "Topcat" in text


def test_information_with_nothing_running(main_window, monkeypatch):
    from ncrads9.communication.samp.samp_hub import SAMPHub

    monkeypatch.setattr(SAMPHub, "is_hub_running", staticmethod(lambda: False))
    text = main_window.samp.information()
    assert "none running" in text
    assert "Connected: no" in text


def test_information_notices_a_hub_somebody_else_is_running(main_window, monkeypatch):
    from ncrads9.communication.samp.samp_hub import SAMPHub

    monkeypatch.setattr(SAMPHub, "is_hub_running", staticmethod(lambda: True))
    monkeypatch.setattr(SAMPHub, "find_hub", staticmethod(lambda: "localhost:1234"))
    text = main_window.samp.information()
    assert "running elsewhere" in text
    assert "localhost:1234" in text


def test_the_information_dialog_shows_it(main_window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    shown = {}
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.update(text=self.text()))
    main_window.menu_bar.action_samp_hub_information.trigger()
    assert "Hub:" in shown["text"]


def test_closing_the_window_stops_the_hub(main_window):
    """A hub that outlived the application would hold its port."""
    hub = FakeHub()
    main_window.samp.hub = hub
    main_window.samp.start_hub()
    main_window.samp.clean_exit()
    assert hub.running is False


# -- the samp XPA point ----------------------------------------------------------


@pytest.fixture
def xpa(main_window):
    from ncrads9.communication.xpa.xpa_commands import XPACommands

    return XPACommands(main_window)


def test_the_samp_point_broadcasts(xpa, main_window, connected, image):
    assert xpa.handle("samp", {"args": ["image", "broadcast"]})["status"] == "ok"
    assert connected.sent[0][1] == image.as_uri()


def test_the_samp_point_sends_to_one_client(xpa, main_window, connected):
    assert xpa.handle("samp", {"args": ["image", "c1"]})["status"] == "ok"
    assert connected.sent[0][2] == "c1"


def test_the_samp_point_starts_and_stops_the_hub(xpa, main_window):
    main_window.samp.hub = FakeHub()
    assert xpa.handle("samp", {"args": ["hub", "start"]})["status"] == "ok"
    assert main_window.samp.hub_running() is True
    assert xpa.handle("samp", {"args": ["hub", "stop"]})["status"] == "ok"
    assert main_window.samp.hub_running() is False


def test_the_samp_point_sets_the_web_profile(xpa, main_window):
    assert xpa.handle("samp", {"args": ["hub", "web", "no"]})["status"] == "ok"
    assert main_window.samp.web_profile is False


def test_the_samp_point_reports_what_is_there(xpa, main_window, connected):
    result = xpa.handle("samp", {"get": True})["result"]
    assert "Connected: yes" in result


def test_the_samp_point_refuses_nonsense(xpa, main_window):
    assert xpa.handle("samp", {"args": ["wibble"]})["status"] == "error"
    assert xpa.handle("samp", {"args": ["hub", "wibble"]})["status"] == "error"
