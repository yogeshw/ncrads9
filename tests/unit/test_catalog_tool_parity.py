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

"""The catalog tool as DS9's catalog dialog: the Object section, the
catalogue it was opened for, the Match dialog and Name Resolution.

No network: the catalogue transport and the name resolver are replaced
throughout, and every request they would have made is recorded instead.
"""

from __future__ import annotations

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.table import Table

from ncrads9.catalogs import name_server, sky_position
from ncrads9.catalogs.catalog_match import match
from ncrads9.catalogs.servers import Service

SIZE = 200

#: Where the name resolver says every object is: inside the test image.
RESOLVED = SkyCoord(150.05 * u.deg, 2.03 * u.deg)


def _header() -> fits.Header:
    return fits.Header(
        {
            "NAXIS": 2,
            "NAXIS1": SIZE,
            "NAXIS2": SIZE,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CRPIX1": SIZE / 2,
            "CRPIX2": SIZE / 2,
            "CRVAL1": 150.0,
            "CRVAL2": 2.0,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
        }
    )


@pytest.fixture
def rows() -> Table:
    return Table(
        {
            "_RAJ2000": [150.00, 150.02, 149.98],
            "_DEJ2000": [2.00, 2.02, 1.98],
            "Jmag": [9.0, 11.0, 13.0],
        }
    )


@pytest.fixture
def requests() -> list:
    return []


@pytest.fixture
def lookups() -> list:
    return []


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path, rows, requests, lookups):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32), header=_header()).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))

    def transport(request):
        requests.append(request)
        return rows

    def resolver(name, server):
        lookups.append((name, server))
        if name == "nowhere":
            raise RuntimeError("not found")
        return RESOLVED

    window.catalog.transport = transport
    window.analysis.name_resolver = resolver
    yield window
    for catalog_window in list(window.catalog._windows.values()):
        catalog_window.close()
    if window.analysis._name_dialog is not None:
        window.analysis._name_dialog.close()
    window.close()


def _tool(main_window):
    """The catalog window most recently opened."""
    return list(main_window.catalog._windows.values())[-1]


# -- the Object section ---------------------------------------------------------


def test_the_window_has_ds9s_object_section(main_window):
    window = main_window.catalog.show_tool()
    assert window._sky.count() == len(sky_position.SKY_FRAMES)
    assert [window._format.itemText(i) for i in range(window._format.count())] == ["degrees", "sexagesimal"]
    assert [window._radius_unit.itemText(i) for i in range(window._radius_unit.count())] == [
        "degrees",
        "arcmin",
        "arcsec",
    ]
    assert window.max_rows() == 5000
    assert window.retrieve_button.text() == "Retrieve"
    for command in ("retrieve", "update_frame", "update_crosshair"):
        assert command in window.actions_by_name
    assert window.actions_by_name["update_frame"].text() == "Update from Current &Frame"


def test_a_menu_query_starts_from_the_frame_centre_and_size(main_window, requests):
    """`TBLUpdate`: the radius is a quarter of width plus height."""
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    request = requests[-1]
    assert request.center.separation(SkyCoord(150 * u.deg, 2 * u.deg)).arcsec < 10
    # 200 pixels of 3.6": (720 + 720) / 4 = 360" = 6'.
    assert request.radius.to_value(u.arcmin) == pytest.approx(6.0, rel=1e-3)
    window = _tool(main_window)
    assert window.radius_unit() == "arcmin"
    assert float(window._radius.text()) == pytest.approx(6.0, rel=1e-3)


def test_retrieve_uses_the_dialogs_radius_unit_and_row_limit(main_window, requests):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    window = _tool(main_window)
    window._radius_unit.setCurrentText("arcsec")
    assert float(window._radius.text()) == pytest.approx(360.0, rel=1e-3)
    window._radius.setText("42")
    window.set_max_rows(2)
    window.retrieve_button.click()

    request = requests[-1]
    assert request.radius.to_value(u.arcsec) == pytest.approx(42.0)
    assert request.row_limit == 2
    # Replaced, not piled up: one dialog, one catalogue.
    assert len(main_window.catalog.catalogs) == 1
    assert len(main_window.catalog.catalogs.catalogs[0].table) == 2


def test_retrieve_uses_a_typed_position(main_window, requests):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    window = _tool(main_window)
    window.set_sky("fk5", "sexagesimal")
    window.set_position_text("10:00:10", "+02:01:00")
    window._request("retrieve")
    expected = SkyCoord("10:00:10 +02:01:00", unit=(u.hourangle, u.deg), frame="fk5")
    assert requests[-1].center.separation(expected).arcsec < 0.5


def test_changing_the_coordinate_menu_converts_the_position(main_window):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    window = _tool(main_window)
    before = window.position()
    window.set_sky("fk5", "sexagesimal")
    assert ":" in window.position_text()[0]
    window.set_sky("galactic", "degrees")
    assert float(window.position_text()[0]) == pytest.approx(before.galactic.l.deg, abs=1e-4)
    assert window.position().separation(before).arcsec < 0.5


def test_update_from_crosshair_takes_the_crosshairs_position(main_window):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    window = _tool(main_window)
    frame = main_window.frame_manager.current_frame
    frame.crosshair = (20.0, 150.0)
    window.actions_by_name["update_crosshair"].trigger()
    longitude, latitude = frame.wcs_handler.pixel_to_world(20.0, 150.0)
    assert window.position().separation(SkyCoord(longitude * u.deg, latitude * u.deg)).arcsec < 0.5


def test_update_from_frame_puts_it_back(main_window):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    window = _tool(main_window)
    window.set_position_text("151", "3")
    window._radius.setText("1")
    window.actions_by_name["update_frame"].trigger()
    assert window.position().separation(SkyCoord(150 * u.deg, 2 * u.deg)).arcsec < 10
    assert float(window._radius.text()) == pytest.approx(6.0, rel=1e-3)


def test_a_name_is_resolved_and_searched_around(main_window, requests, lookups):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    window = _tool(main_window)
    window.name_server_actions["ned-sao"].trigger()
    window.set_object_name("M 99")
    window.retrieve_button.click()
    assert lookups[-1] == ("M 99", "ned-sao")
    assert requests[-1].center.separation(RESOLVED).arcsec < 0.5
    assert window.position().separation(RESOLVED).arcsec < 0.5


def test_a_name_that_will_not_resolve_queries_nothing(main_window, requests):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    window = _tool(main_window)
    asked = len(requests)
    window.set_object_name("nowhere")
    window.retrieve_button.click()
    assert len(requests) == asked
    assert "nowhere" in window.status_text()


def test_the_mirror_menu_reaches_the_request(main_window, requests):
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    window = _tool(main_window)
    window.mirror_actions["iucaa"].trigger()
    window.retrieve_button.click()
    assert requests[-1].mirror == "iucaa"


# -- the catalogue it was opened for ------------------------------------------------


@pytest.mark.parametrize(
    ("name", "service", "identifier"),
    [
        ("cat2mass", Service.CDS, "II/246/out"),
        ("catgaia", Service.CDS, "I/345/gaia2"),
        ("catnvss", Service.CDS, "VIII/65/nvss"),
        ("catsimbad", Service.SIMBAD, ""),
        ("catned", Service.NED, ""),
    ],
)
def test_each_menu_entry_queries_its_own_catalogue(main_window, requests, name, service, identifier):
    main_window.menu_bar.catalog_actions[name].trigger()
    assert requests[-1].server.service is service
    assert requests[-1].server.identifier == identifier
    assert _tool(main_window).selected_server().name == name


def test_the_catalog_tool_opens_empty_and_queries_nothing(main_window, requests):
    main_window.menu_bar.action_catalog_tool.trigger()
    windows = list(main_window.catalog._windows.values())
    assert len(windows) == 1, "Catalog Tool must open one window, not a VO query as well"
    window = windows[0]
    assert window.selected_server() is None
    assert requests == []
    window.retrieve_button.click()
    assert requests == []
    assert "Choose a catalog" in window.status_text()


def test_the_catalog_tool_queries_the_catalogue_chosen(main_window, requests):
    window = main_window.catalog.show_tool()
    window.set_server("catfirst")
    window.retrieve_button.click()
    assert requests[-1].server.identifier == "VIII/71/first"
    assert main_window.catalog.catalogs.catalogs[-1].name == "FIRST Survey"


def test_a_typed_vizier_identifier_is_queried(main_window, requests):
    window = main_window.catalog.show_tool()
    window._catalog_choice.setEditText("J/ApJ/123/45")
    window.retrieve_button.click()
    assert requests[-1].server.service is Service.CDS
    assert requests[-1].server.identifier == "J/ApJ/123/45"


@pytest.mark.parametrize("action", ["action_analysis_vizier", "action_catalog_vizier"])
def test_vizier_opens_the_tool_rather_than_querying_2mass(main_window, requests, action):
    getattr(main_window.menu_bar, action).trigger()
    assert requests == []
    window = _tool(main_window)
    assert window.selected_server() is None
    assert window.position() is not None


def test_the_vo_controller_no_longer_hard_codes_2mass():
    import inspect

    from ncrads9.ui.controllers import vo

    assert "II/246/out" not in inspect.getsource(vo)


# -- Catalog Match ------------------------------------------------------------------------


def test_the_match_dialog_is_ds9s(qapp):
    from ncrads9.ui.dialogs.catalog_match_dialog import CatalogMatchDialog

    dialog = CatalogMatchDialog(["A", "B", "C"])
    assert dialog.first.currentText() == "A"
    assert dialog.second.currentText() == "B"
    assert [dialog.function.itemData(i) for i in range(3)] == ["1and2", "1not2", "2not1"]
    assert [dialog.returned.itemData(i) for i in range(3)] == ["1and2", "1only", "2only"]
    assert dialog.unique.isEnabled() and dialog.returned.isEnabled()

    dialog.function.setCurrentIndex(1)
    assert not dialog.unique.isEnabled()
    assert not dialog.returned.isEnabled()

    dialog.error.setValue(3.0)
    dialog.unit.setCurrentText("arcmin")
    assert dialog.error.value() == pytest.approx(0.05)
    assert dialog.values().radius_arcsec == pytest.approx(3.0)
    dialog.close()


def test_match_runs_from_one_dialog(main_window, monkeypatch):
    from PyQt6.QtWidgets import QDialog, QInputDialog

    from ncrads9.ui.dialogs.catalog_match_dialog import CatalogMatchDialog

    def refuse(*_args, **_kwargs):
        raise AssertionError("Catalog Match must not ask through QInputDialog")

    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(refuse))
    monkeypatch.setattr(QInputDialog, "getDouble", staticmethod(refuse))

    def answer(dialog):
        dialog.error.setValue(10.0)
        dialog.returned.setCurrentIndex(2)
        dialog.unique.setChecked(False)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(CatalogMatchDialog, "exec", answer)

    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    main_window.menu_bar.catalog_actions["cat2mass"].trigger()
    main_window.menu_bar.action_catalog_match.trigger()

    names = [entry.name for entry in main_window.catalog.catalogs]
    assert len(names) == 3
    assert "1and2" in names[-1]
    settings = main_window.catalog.settings
    assert settings["match_error"] == "10 arcsec"
    assert settings["match_return"] == "2only"
    assert settings["match_unique"] == "no"


def test_cancelling_the_match_dialog_matches_nothing(main_window, monkeypatch):
    from PyQt6.QtWidgets import QDialog

    from ncrads9.ui.dialogs.catalog_match_dialog import CatalogMatchDialog

    monkeypatch.setattr(CatalogMatchDialog, "exec", lambda dialog: QDialog.DialogCode.Rejected)
    main_window.menu_bar.catalog_actions["catgaia"].trigger()
    main_window.menu_bar.catalog_actions["cat2mass"].trigger()
    main_window.menu_bar.action_catalog_match.trigger()
    assert len(main_window.catalog.catalogs) == 2


def test_return_2only_gives_the_second_catalogues_columns():
    first = Table({"ra": [10.0], "dec": [20.0], "a": [1]})
    second = Table({"ra": [10.0], "dec": [20.0], "b": [2]})
    result = match(first, second, 5.0, "1and2", "2only")
    assert "b" in result.colnames and "a" not in result.colnames


# -- Name Resolution ----------------------------------------------------------------------


def _name_dialog(main_window):
    main_window.menu_bar.action_name_resolution.trigger()
    return main_window.analysis._name_dialog


def test_name_resolution_is_a_dialog_not_a_prompt(main_window, monkeypatch):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QInputDialog

    def refuse(*_args, **_kwargs):
        raise AssertionError("Name Resolution must not ask through QInputDialog")

    monkeypatch.setattr(QInputDialog, "getText", staticmethod(refuse))
    dialog = _name_dialog(main_window)
    assert dialog is not None and dialog.isVisible()
    assert dialog.windowModality() == Qt.WindowModality.NonModal
    assert list(dialog.server_actions) == [value for _label, value in name_server.SERVERS]
    assert dialog.server == "simbad-cds"
    assert not dialog.pan_button.isEnabled()
    # Opened twice, it is raised rather than stacked.
    main_window.menu_bar.action_name_resolution.trigger()
    assert main_window.analysis._name_dialog is dialog


def test_retrieve_reads_out_the_position_in_the_chosen_system(main_window, lookups):
    dialog = _name_dialog(main_window)
    dialog.server_actions["ned-cds"].trigger()
    dialog.set_object_name("M 99")
    dialog.retrieve()
    assert lookups[-1] == ("M 99", "ned-cds")
    x, y = dialog.position_text()
    expected = RESOLVED.fk5
    assert float(x) == pytest.approx(expected.ra.deg, abs=1e-6)
    assert float(y) == pytest.approx(expected.dec.deg, abs=1e-6)

    dialog.set_sky("galactic", "sexagesimal")
    x, _y = dialog.position_text()
    assert ":" in x
    assert sky_position.parse_position(*dialog.position_text(), "galactic").separation(RESOLVED).arcsec < 0.5
    assert dialog.pan_button.isEnabled() and dialog.crosshair_button.isEnabled()
    # The choice of server is DS9's global `pnres(server)`.
    assert main_window.analysis.name_server == "ned-cds"


def test_pan_to_centres_the_image_on_it(main_window, monkeypatch):
    panned = []
    monkeypatch.setattr(main_window.zoom, "on_panner_pan", lambda x, y: panned.append((x, y)))
    dialog = _name_dialog(main_window)
    dialog.set_object_name("M 99")
    dialog.retrieve()
    assert panned == []
    dialog.pan_button.click()
    x, y = main_window.wcs_handler.world_to_pixel(RESOLVED.ra.deg, RESOLVED.dec.deg)
    assert panned[-1] == pytest.approx((float(x), float(y)))


def test_crosshair_to_moves_the_crosshair_there(main_window):
    dialog = _name_dialog(main_window)
    dialog.set_object_name("M 99")
    dialog.retrieve()
    dialog.action_crosshair.trigger()
    x, y = main_window.wcs_handler.world_to_pixel(RESOLVED.ra.deg, RESOLVED.dec.deg)
    assert main_window.edit_mode == "crosshair"
    assert main_window.frame_manager.current_frame.crosshair == pytest.approx((float(x), float(y)))


def test_a_name_that_will_not_resolve_says_so(main_window):
    dialog = _name_dialog(main_window)
    dialog.set_object_name("nowhere")
    dialog.retrieve()
    assert "nowhere" in dialog.status_text()
    assert dialog.coord is None
    assert not dialog.pan_button.isEnabled()


def test_an_empty_name_is_refused_without_asking(main_window, lookups):
    dialog = _name_dialog(main_window)
    dialog.retrieve()
    assert lookups == []
    assert "Object Name" in dialog.status_text()


def test_the_xpa_route_uses_the_same_resolver(main_window, lookups):
    assert main_window.analysis.resolve_name("M 99") is None
    assert lookups[-1] == ("M 99", "simbad-cds")
    assert main_window._last_resolved_name == "M 99"
    assert main_window.analysis.resolve_name("nowhere") is not None


def test_the_real_resolver_asks_sesame_for_the_chosen_database(monkeypatch):
    """`fetch` is the one network call; with `from_name` replaced it is not made."""
    from astropy.coordinates import name_resolve

    seen = []

    def fake(cls, name, *args, **kwargs):
        seen.append((name, name_resolve.sesame_database.get(), list(name_resolve.sesame_url.get())))
        return RESOLVED

    monkeypatch.setattr(SkyCoord, "from_name", classmethod(fake))
    assert name_server.resolve("M 99", "ned-sao").separation(RESOLVED).arcsec < 1e-6
    name, database, urls = seen[-1]
    assert (name, database) == ("M 99", "ned")
    assert urls == [name_server.SESAME_URLS["sao"]]


def test_sky_position_round_trips():
    coord = SkyCoord(150 * u.deg, 2 * u.deg)
    for sky in sky_position.SKY_FRAMES:
        for skyformat in sky_position.SKY_FORMATS:
            text = sky_position.format_position(coord, sky, skyformat)
            assert sky_position.parse_position(*text, sky).separation(coord).arcsec < 0.05
    with pytest.raises(sky_position.PositionError):
        sky_position.radius_quantity("-1", "arcmin")
