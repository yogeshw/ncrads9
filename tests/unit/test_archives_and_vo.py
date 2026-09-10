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

"""Archives, footprint servers and the VO registry (M8-19, M8-20, M8-21).

Every fetch is injected; nothing here reaches a network.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.catalogs import footprints, vo_registry

SIZE = 200


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


#: A footprint reply of the shape both servers send.
FOOTPRINT_VOTABLE = """<?xml version="1.0"?>
<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE><TABLE>
<FIELD name="ObsId" datatype="char" arraysize="*"/>
<FIELD name="Instrument" datatype="char" arraysize="*"/>
<FIELD name="regionSTCS" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>
<TR><TD>1234</TD><TD>ACIS-S</TD><TD>Polygon J2000 149.99 1.99 150.01 1.99 150.01 2.01 149.99 2.01</TD></TR>
<TR><TD>5678</TD><TD>HRC-I</TD><TD>Polygon J2000 149.98 1.98 150.02 1.98 150.02 2.02 149.98 2.02</TD></TR>
<TR><TD>9012</TD><TD>ACIS-I</TD><TD>not a polygon</TD></TR>
</TABLEDATA></DATA>
</TABLE></RESOURCE></VOTABLE>"""


# -- footprint servers (M8-20) --------------------------------------------------


def test_ds9s_two_footprint_servers_are_here():
    """`ifp(def)` in `ds9/library/fp.tcl:22`."""
    assert {server.name for server in footprints.SERVERS} == {"fpcxc", "fphla"}


def test_the_chandra_server_lists_its_instruments():
    assert footprints.by_name("fpcxc").instruments == ("ACIS-S", "ACIS-I", "HRC-S", "HRC-I")


def test_the_hla_server_lists_eleven():
    assert len(footprints.by_name("fphla").instruments) == 11


def test_a_footprint_request_builds_a_cone_query():
    request = footprints.FootprintRequest(footprints.by_name("fpcxc"), 150.0, 2.0, 15.0, ("ACIS-S", "ACIS-I"))
    url = request.url()
    assert "RA=150" in url and "DEC=2" in url
    # Fifteen arcminutes is a quarter of a degree, which is what SR takes.
    assert "SR=0.25" in url
    assert url.count("inst=") == 2


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Polygon J2000 10.1 41.2 10.2 41.2 10.2 41.3", [(10.1, 41.2), (10.2, 41.2), (10.2, 41.3)]),
        ("POLYGON ICRS 1 2 3 4 5 6", [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]),
        ("Polygon 1 2 3 4 5 6", [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]),
        ("Circle 10 20 1", []),
        ("", []),
    ],
)
def test_stcs_polygons_are_read(text, expected):
    assert footprints.parse_stcs(text) == expected


def test_the_frame_name_is_not_read_as_a_coordinate():
    """`J2000` holds digits that a plain number scan takes for a declination
    of two thousand."""
    assert footprints.parse_stcs("Polygon J2000 10.1 41.2 10.2 41.3")[0] == (10.1, 41.2)


def test_an_odd_number_of_coordinates_drops_the_stray_one():
    assert len(footprints.parse_stcs("Polygon 1 2 3 4 5")) == 2


def test_a_footprint_query_reads_its_reply():
    request = footprints.FootprintRequest(footprints.by_name("fpcxc"), 150.0, 2.0)
    result = footprints.query(request, fetcher=lambda url, timeout: FOOTPRINT_VOTABLE)
    assert len(result.table) == 3
    # The row whose outline will not parse is listed but not drawn.
    assert len(result.polygons) == 2
    assert "3 observations, 2 outlines" in result.message


def test_a_footprint_query_that_finds_nothing_says_so():
    empty = '<?xml version="1.0"?><VOTABLE><RESOURCE/></VOTABLE>'
    request = footprints.FootprintRequest(footprints.by_name("fpcxc"), 150.0, 2.0)
    result = footprints.query(request, fetcher=lambda url, timeout: empty)
    assert "nothing covers" in result.message


def test_a_footprint_failure_is_reported_not_raised():
    def broken(url, timeout):
        raise RuntimeError("server down")

    request = footprints.FootprintRequest(footprints.by_name("fpcxc"), 150.0, 2.0)
    assert "server down" in footprints.query(request, fetcher=broken).message


def test_the_footprint_fetcher_refuses_a_non_http_url():
    with pytest.raises(footprints.FootprintError, match="not an http URL"):
        footprints.fetch("file:///etc/passwd")


def test_a_table_with_no_outline_column_yields_no_polygons():
    from astropy.table import Table

    assert footprints.extract_polygons(Table({"ObsId": ["1"]})) == []


# -- the VO registry (M8-21) --------------------------------------------------------


REGISTRY_VOTABLE = """<?xml version="1.0"?>
<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE><TABLE>
<FIELD name="ivoid" datatype="char" arraysize="*"/>
<FIELD name="res_title" datatype="char" arraysize="*"/>
<FIELD name="res_description" datatype="char" arraysize="*"/>
<FIELD name="access_url" datatype="char" arraysize="*"/>
<FIELD name="role_name" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>
<TR><TD>ivo://a/one</TD><TD>Survey One</TD><TD>An infrared survey</TD><TD>https://a.invalid/sia</TD><TD>Observatory A</TD></TR>
<TR><TD>ivo://a/one</TD><TD>Survey One</TD><TD>An infrared survey</TD><TD>https://a.invalid/sia</TD><TD>Observatory A</TD></TR>
<TR><TD>ivo://b/two</TD><TD>Survey Two</TD><TD>An optical survey</TD><TD>https://b.invalid/sia</TD><TD>Observatory B</TD></TR>
</TABLEDATA></DATA>
</TABLE></RESOURCE></VOTABLE>"""


def test_the_four_service_kinds_have_standard_ids():
    for kind in vo_registry.ServiceKind:
        assert kind.standard_id.startswith("ivo://ivoa.net/std/")
        assert kind.label


def test_the_discovery_query_filters_on_the_standard_id():
    query = vo_registry.discovery_query(vo_registry.ServiceKind.SIA)
    assert "ivo://ivoa.net/std/sia" in query
    assert query.startswith("SELECT TOP")


def test_keywords_use_the_registrys_full_text_match():
    """A plain LIKE misses a description that words it differently."""
    query = vo_registry.discovery_query(vo_registry.ServiceKind.SIA, "infrared")
    assert "ivo_hasword" in query
    assert "infrared" in query


def test_a_quote_in_the_keywords_is_escaped():
    query = vo_registry.discovery_query(vo_registry.ServiceKind.SIA, "O'Brien")
    assert "O''Brien" in query


def test_discovery_reads_its_reply():
    result = vo_registry.discover(
        vo_registry.ServiceKind.SIA, fetcher=lambda url, body, timeout: REGISTRY_VOTABLE
    )
    assert len(result.services) == 2
    assert result.services[0].title == "Survey One"
    assert result.services[0].publisher == "Observatory A"


def test_one_resource_registered_twice_is_listed_once():
    """A resource can register several interfaces; the rest are noise."""
    result = vo_registry.discover(
        vo_registry.ServiceKind.SIA, fetcher=lambda url, body, timeout: REGISTRY_VOTABLE
    )
    assert len({service.url for service in result.services}) == len(result.services)


def test_discovery_that_finds_nothing_says_so():
    empty = '<?xml version="1.0"?><VOTABLE><RESOURCE/></VOTABLE>'
    result = vo_registry.discover(vo_registry.ServiceKind.TAP, fetcher=lambda url, body, timeout: empty)
    assert "No Table Access Protocol services found" in result.message


def test_a_registry_failure_is_reported_not_raised():
    def broken(url, body, timeout):
        raise RuntimeError("registry down")

    assert "registry down" in vo_registry.discover(vo_registry.ServiceKind.SIA, fetcher=broken).message


def test_an_unreadable_registry_reply_is_reported():
    result = vo_registry.discover(vo_registry.ServiceKind.SIA, fetcher=lambda url, body, timeout: "not xml")
    assert "could not read" in result.message


@pytest.mark.parametrize(
    "kind,fragments",
    [
        (vo_registry.ServiceKind.CONE_SEARCH, ["RA=150", "DEC=2", "SR=0.1"]),
        (vo_registry.ServiceKind.SIA, ["POS=150%2C2", "SIZE=0.1"]),
        (vo_registry.ServiceKind.SSA, ["POS=150%2C2", "SIZE=0.1"]),
    ],
)
def test_a_service_query_url_matches_its_protocol(kind, fragments):
    service = vo_registry.Service("ivo://x", "X", kind, "https://x.invalid/service")
    url = vo_registry.service_query_url(service, 150.0, 2.0, 0.1)
    for fragment in fragments:
        assert fragment in url


def test_a_service_url_that_already_has_a_query_gets_an_ampersand():
    service = vo_registry.Service("ivo://x", "X", vo_registry.ServiceKind.SIA, "https://x.invalid/s?v=1")
    assert "?v=1&POS=" in vo_registry.service_query_url(service, 150.0, 2.0, 0.1)


def test_a_tap_service_cannot_be_asked_about_a_position():
    """It answers ADQL; offering it a cone search is a request it cannot take."""
    service = vo_registry.Service(
        "ivo://x", "TAP Thing", vo_registry.ServiceKind.TAP, "https://x.invalid/tap"
    )
    with pytest.raises(vo_registry.RegistryError, match="answers ADQL"):
        vo_registry.service_query_url(service, 150.0, 2.0, 0.1)


def test_querying_a_service_reads_its_rows():
    rows = """<?xml version="1.0"?>
<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE><TABLE>
<FIELD name="ra" datatype="double"/><FIELD name="dec" datatype="double"/>
<DATA><TABLEDATA><TR><TD>150.0</TD><TD>2.0</TD></TR></TABLEDATA></DATA>
</TABLE></RESOURCE></VOTABLE>"""
    service = vo_registry.Service(
        "ivo://x", "X", vo_registry.ServiceKind.CONE_SEARCH, "https://x.invalid/cone"
    )
    table, message = vo_registry.query_service(
        service, 150.0, 2.0, 0.1, fetcher=lambda url, body, timeout: rows
    )
    assert table is not None and len(table) == 1
    assert "1 rows" in message


def test_the_registry_fetcher_refuses_a_non_http_url():
    with pytest.raises(vo_registry.RegistryError, match="not an http URL"):
        vo_registry.fetch("file:///etc/passwd")


# -- through the menus --------------------------------------------------------------


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
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32), header=_header()).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    window.catalog.footprint_fetcher = lambda url, timeout: FOOTPRINT_VOTABLE
    window.vo.registry_fetcher = lambda url, body, timeout: REGISTRY_VOTABLE
    yield window
    for catalog_window in list(window.catalog._windows.values()):
        catalog_window.close()
    if window.vo._registry_dialog is not None:
        window.vo._registry_dialog.close()
    window.close()


def test_both_footprint_servers_are_on_the_menu(main_window):
    assert set(main_window.menu_bar.footprint_actions) == {"fpcxc", "fphla"}


def test_a_footprint_query_loads_and_draws(main_window):
    main_window.menu_bar.footprint_actions["fpcxc"].trigger()
    assert len(main_window.catalog.catalogs) == 1
    # Two readable outlines become two polygon regions.
    assert len(main_window.frame_manager.current_frame.regions) == 2


def test_footprint_outlines_are_tagged_so_they_can_be_cleared(main_window):
    """An outline is a region once drawn, and there is no other way to tell
    it from one the user made."""
    main_window.menu_bar.footprint_actions["fpcxc"].trigger()
    regions = main_window.frame_manager.current_frame.regions
    assert all(any(tag.startswith("footprint") for tag in region.tags) for region in regions)


def test_clear_all_removes_the_outlines_and_the_catalogue(main_window):
    main_window.menu_bar.footprint_actions["fpcxc"].trigger()
    main_window.menu_bar.action_footprint_clear_all.trigger()
    assert main_window.frame_manager.current_frame.regions == []
    assert len(main_window.catalog.catalogs) == 0


def test_clear_all_leaves_the_users_own_regions_alone(main_window):
    from ncrads9.regions.region_parser import RegionParser

    frame = main_window.frame_manager.current_frame
    frame.regions = RegionParser().parse_string("image\ncircle(50,50,5)\n")
    main_window.menu_bar.footprint_actions["fpcxc"].trigger()
    main_window.menu_bar.action_footprint_clear_all.trigger()
    assert len(frame.regions) == 1


def test_a_footprint_query_with_no_wcs_says_so(main_window):
    from ncrads9.core.wcs_handler import WCSHandler

    main_window.frame_manager.current_frame.wcs_handler = WCSHandler(fits.Header())
    main_window.menu_bar.footprint_actions["fpcxc"].trigger()
    assert "no WCS" in main_window.status_bar.currentMessage()


def test_the_archive_links_are_on_the_menu(main_window):
    assert set(main_window.menu_bar.archive_actions) == {
        "simbad_sao",
        "simbad_cds",
        "ads_sao",
        "ads_cds",
    }


def test_an_archive_link_opens_a_url(main_window, monkeypatch):
    from PyQt6.QtGui import QDesktopServices

    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toString())))
    main_window.menu_bar.archive_actions["simbad_cds"].trigger()
    assert opened and "simbad.u-strasbg.fr" in opened[0]


def test_an_unknown_archive_is_reported(main_window):
    assert main_window.vo.open_archive("nosucharchive") is False


def test_chandra_by_obsid_opens_the_archive(main_window, monkeypatch):
    from PyQt6.QtGui import QDesktopServices

    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toString())))
    assert main_window.vo.chandra_by_obsid("1234") == "1234"
    assert "obsid=1234" in opened[0]


def test_a_non_numeric_obsid_is_refused(main_window):
    assert main_window.vo.chandra_by_obsid("not-an-id") is None
    assert "not an observation ID" in main_window.status_bar.currentMessage()


def test_chandra_by_cone_search_uses_the_footprint_server(main_window):
    main_window.menu_bar.action_archive_chandra_cone.trigger()
    assert len(main_window.catalog.catalogs) == 1


def test_the_registry_browser_opens(main_window):
    main_window.menu_bar.action_vo_registry.trigger()
    assert main_window.vo._registry_dialog is not None


def test_the_registry_browser_discovers_and_lists(main_window):
    main_window.menu_bar.action_vo_registry.trigger()
    dialog = main_window.vo._registry_dialog
    dialog._words.setText("infrared")
    dialog.discover()
    assert dialog._table.rowCount() == 2
    assert dialog.selected() is None


def test_a_discovered_service_can_be_queried(main_window):
    rows = """<?xml version="1.0"?>
<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE><TABLE>
<FIELD name="ra" datatype="double"/><FIELD name="dec" datatype="double"/>
<DATA><TABLEDATA><TR><TD>150.0</TD><TD>2.0</TD></TR></TABLEDATA></DATA>
</TABLE></RESOURCE></VOTABLE>"""

    service = vo_registry.Service(
        "ivo://x", "Survey One", vo_registry.ServiceKind.CONE_SEARCH, "https://x.invalid/cone"
    )
    main_window.vo.registry_fetcher = lambda url, body, timeout: rows
    loaded = main_window.vo.query_vo_service(service, 150.0, 2.0, 0.1)
    assert loaded is not None
    assert loaded.name == "Survey One"
    assert len(main_window.catalog.catalogs) == 1


def test_querying_a_tap_service_is_refused_with_a_reason(main_window):
    service = vo_registry.Service(
        "ivo://x", "TAP Thing", vo_registry.ServiceKind.TAP, "https://x.invalid/tap"
    )
    assert main_window.vo.query_vo_service(service, 150.0, 2.0, 0.1) is None
    assert "ADQL" in main_window.status_bar.currentMessage()


def test_the_browser_will_not_offer_query_for_tap(qapp):
    from ncrads9.ui.dialogs.vo_registry_dialog import VORegistryDialog

    dialog = VORegistryDialog((150.0, 2.0))
    dialog.show_result(
        vo_registry.DiscoveryResult(
            services=[vo_registry.Service("i", "T", vo_registry.ServiceKind.TAP, "https://x.invalid/tap")],
            message="1 service",
        )
    )
    dialog._table.selectRow(0)
    assert dialog._query_button.isEnabled() is False
    dialog.close()
