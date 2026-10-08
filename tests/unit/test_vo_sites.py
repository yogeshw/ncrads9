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

"""DS9's Virtual Observatory window: its list of sites (`vo.tcl`)."""

from ncrads9.ui.dialogs import vo_sites_dialog as module

LISTING = (
    "cxc.harvard.edu:28571\tChandra X-ray Center\thttps://cxc.harvard.edu/vo/\n"
    "heasarc.gsfc.nasa.gov:28571\tHEASARC\thttps://heasarc.gsfc.nasa.gov/vo/\n"
)


def test_the_list_is_read_as_ds9_writes_it():
    sites = module.parse_sites(LISTING)
    assert [site.title for site in sites] == ["Chandra X-ray Center", "HEASARC"]
    assert sites[0].host == "cxc.harvard.edu:28571"


def test_the_first_list_that_answers_is_used():
    asked = []

    def fetch(url):
        asked.append(url)
        if url == module.SITE_LISTS[0]:
            raise OSError("down")
        return LISTING

    sites, note = module.load_sites(fetch)
    assert asked == list(module.SITE_LISTS[:2])
    assert len(sites) == 2 and note is None


def test_with_no_network_ds9s_own_list_is_used():
    def fetch(_url):
        raise OSError("offline")

    sites, note = module.load_sites(fetch)
    assert [site.host for site in sites] == ["xray1.physics.rutgers.edu:28571", "rinzai.rutgers.edu:28571"]
    assert "default list" in note


def test_ticking_a_site_opens_it(qapp):
    opened = []
    dialog = module.VOSitesDialog(fetch=lambda _url: LISTING, open_url=opened.append)
    assert len(dialog.boxes) == 2
    dialog.boxes[1].setChecked(True)
    assert opened == ["https://heasarc.gsfc.nasa.gov/vo/"]
    dialog.cancel()
    assert not any(box.isChecked() for box in dialog.boxes)
    dialog.help_me_choose()
    assert opened[-1] == module.HELP_URL
    dialog.close()


def test_the_analysis_menu_opens_it(qapp, tmp_path, monkeypatch):
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    window = MainWindow()
    window.vo.site_fetcher = lambda _url: LISTING
    window.menu_bar.action_virtual_observatory.trigger()
    qapp.processEvents()
    dialog = window._open_windows["VOSitesDialog"]
    assert dialog.windowTitle() == "Virtual Observatory"
    assert len(dialog.boxes) == 2
    dialog.close()
    window.close()


def test_xpa_vo(qapp, tmp_path, monkeypatch):
    from ncrads9.communication.xpa.xpa_commands import XPACommands
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    window = MainWindow()
    opened = []
    window.vo.site_fetcher = lambda _url: LISTING
    window.vo.site_opener = opened.append
    xpa = XPACommands(window)

    def run(line, get=False):
        words = line.split()
        return xpa.handle(words[0], {"args": words[1:], **({"get": True} if get else {})})

    assert run("vo connect heasarc")["status"] == "ok"
    assert opened == ["https://heasarc.gsfc.nasa.gov/vo/"]
    assert run("vo", get=True)["result"] == "heasarc.gsfc.nasa.gov:28571"
    assert run("vo disconnect heasarc")["status"] == "ok"
    assert run("vo", get=True)["result"] == ""
    assert run("vo nosuchsite")["status"] == "error"
    assert run("vo delay 20")["status"] == "ok"
    assert run("vo delay", get=True)["result"] == "20"
    assert run("vo method mime")["status"] == "ok"
    assert run("vo method xpa")["status"] == "error"
    window.close()
