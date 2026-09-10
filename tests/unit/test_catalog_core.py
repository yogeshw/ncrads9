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

"""Local catalog files, the server list, and the query layer (M8-5, M8-11, M8-12).

Nothing here touches the network: every query goes through an injected
transport, which is what `catalog_query.Transport` is for.
"""

from __future__ import annotations

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.table import Table

from ncrads9.catalogs import catalog_query, servers
from ncrads9.catalogs.catalog_file import (
    CatalogFileError,
    CatalogFormat,
    detect,
    format_for,
    load,
    parse,
    save,
    to_text,
)

#: A starbase file of the shape DS9 writes: header pairs, names, a rule.
STARBASE = "name\tTest catalog\nsource\tVizieR\nRA\tDec\tJmag\n--\t---\t----\n10.5\t41.2\t9.1\n10.6\t41.3\t\n"


# -- local catalog files (M8-5) -------------------------------------------------


def test_starbase_reads_its_columns_and_rows():
    table = parse(STARBASE)
    assert table.colnames == ["RA", "Dec", "Jmag"]
    assert len(table) == 2
    assert table["RA"][0] == pytest.approx(10.5)


def test_starbase_keeps_its_header_pairs():
    """They are the catalogue's provenance; DS9 shows them in a Header view."""
    assert parse(STARBASE).meta["name"] == "Test catalog"
    assert parse(STARBASE).meta["source"] == "VizieR"


def test_a_blank_starbase_cell_reads_as_missing():
    """Not as the string "", which would make the column text."""
    table = parse(STARBASE)
    assert np.isnan(table["Jmag"][1])


def test_a_short_starbase_row_is_padded():
    table = parse("A\tB\tC\n-\t-\t-\n1\t2\n")
    assert len(table) == 1
    assert np.isnan(table["C"][0])


def test_a_file_with_no_rule_is_not_starbase():
    with pytest.raises(CatalogFileError, match="no rule of dashes"):
        parse("RA\tDec\n10.5\t41.2\n", CatalogFormat.STARBASE)


def test_starbase_round_trips():
    table = parse(STARBASE)
    again = parse(to_text(table, CatalogFormat.STARBASE))
    assert again.colnames == table.colnames
    assert again["RA"][0] == pytest.approx(table["RA"][0])
    assert again.meta["name"] == "Test catalog"


def test_csv_with_a_header():
    table = parse("RA,Dec,Jmag\n10.5,41.2,9.1\n", CatalogFormat.CSV)
    assert table.colnames == ["RA", "Dec", "Jmag"]
    assert len(table) == 1


def test_csv_without_a_header_numbers_its_columns():
    """DS9's "CSV without header"; its own window shows them numbered."""
    table = parse("10.5,41.2\n10.6,41.3\n", CatalogFormat.CSV_NO_HEADER)
    assert table.colnames == ["col1", "col2"]
    assert len(table) == 2


def test_tsv():
    table = parse("RA\tDec\n10.5\t41.2\n", CatalogFormat.TSV)
    assert table.colnames == ["RA", "Dec"]


@pytest.mark.parametrize(
    "text,expected",
    [
        (STARBASE, CatalogFormat.STARBASE),
        ("RA,Dec\n10.5,41.2\n", CatalogFormat.CSV),
        ("10.5,41.2\n10.6,41.3\n", CatalogFormat.CSV_NO_HEADER),
        ("RA\tDec\n10.5\t41.2\n", CatalogFormat.TSV),
        ('<?xml version="1.0"?><VOTABLE/>', CatalogFormat.VOTABLE),
    ],
)
def test_the_format_is_detected_from_the_content(text, expected):
    """A `.txt` from a colleague is as likely to be starbase as anything."""
    assert detect(text) is expected


def test_a_csv_extension_full_of_tabs_is_read_as_tsv():
    assert detect("RA\tDec\n1\t2\n", "x.csv") is CatalogFormat.CSV


def test_a_numeric_first_line_is_data_not_column_names():
    """No catalogue names a column `10.5`; guessing wrong loses the first star."""
    assert detect("10.5,41.2\n10.6,41.3\n") is CatalogFormat.CSV_NO_HEADER


def test_a_column_with_one_bad_value_stays_text():
    """Half-converting it would make the type depend on which rows were read."""
    table = parse("A,B\n1,ok\n2,also ok\n", CatalogFormat.CSV)
    assert table["A"].dtype.kind == "f"
    assert table["B"].dtype.kind == "O"


def test_a_file_with_no_rows_is_an_error():
    with pytest.raises(CatalogFileError, match="no rows"):
        parse("", CatalogFormat.CSV)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("cat.rdb", CatalogFormat.STARBASE),
        ("cat.tab", CatalogFormat.STARBASE),
        ("cat.csv", CatalogFormat.CSV),
        ("cat.tsv", CatalogFormat.TSV),
        ("cat.vot", CatalogFormat.VOTABLE),
        ("cat.unknown", CatalogFormat.STARBASE),
    ],
)
def test_saving_takes_its_format_from_the_name(name, expected):
    """Saving is the one place the extension decides; the user typed it."""
    assert format_for(name) is expected


@pytest.mark.parametrize(
    "catalog_format",
    [CatalogFormat.STARBASE, CatalogFormat.CSV, CatalogFormat.TSV, CatalogFormat.VOTABLE],
)
def test_every_format_round_trips_through_a_file(tmp_path, catalog_format):
    table = Table({"RA": [10.5, 10.6], "Dec": [41.2, 41.3], "Name": ["a", "b"]})
    path = tmp_path / "cat.dat"
    save(path, table, catalog_format)
    again = load(path, catalog_format)
    assert list(again.colnames) == list(table.colnames)
    assert len(again) == 2
    assert again["RA"][0] == pytest.approx(10.5)


def test_a_masked_cell_round_trips_as_missing():
    """Written as astropy's "--" it would read back as that string."""
    table = Table({"A": [1.0, np.nan], "B": [2.0, 3.0]})
    again = parse(to_text(table, CatalogFormat.CSV), CatalogFormat.CSV)
    assert np.isnan(again["A"][1])
    assert again["B"][1] == pytest.approx(3.0)


def test_unreadable_votable_says_so():
    with pytest.raises(CatalogFileError, match="cannot read as VOTable"):
        parse("<VOTABLE>truncated", CatalogFormat.VOTABLE)


# -- the server list (M8-11, M8-12) ----------------------------------------------


def test_ds9s_catalogue_list_is_transcribed():
    """`icat(def)` in `ds9/library/cat.tcl:48`."""
    assert len(servers.CATALOGS) == 39
    assert servers.SECTIONS == (
        "Database",
        "Optical",
        "Infrared",
        "High Energy",
        "Radio",
        "Observation Logs",
    )


def test_every_catalogue_is_in_a_section():
    assert all(entry.section in servers.SECTIONS for entry in servers.CATALOGS)


def test_every_catalogue_name_is_distinct():
    names = [entry.name for entry in servers.CATALOGS]
    assert len(names) == len(set(names))


@pytest.mark.parametrize(
    "name,service,identifier",
    [
        ("catgaia", servers.Service.CDS, "I/345/gaia2"),
        ("catsimbad", servers.Service.SIMBAD, ""),
        ("catned", servers.Service.NED, ""),
        ("catskybot", servers.Service.SKYBOT, ""),
        ("catcsc", servers.Service.CXC, "Current Release"),
    ],
)
def test_catalogues_name_their_service(name, service, identifier):
    entry = servers.by_name(name)
    assert entry is not None
    assert entry.service is service
    assert entry.identifier == identifier


def test_a_cds_catalogue_has_a_vizier_identifier():
    for entry in servers.CATALOGS:
        if entry.service is servers.Service.CDS:
            assert entry.identifier, entry.label


def test_an_unknown_name_is_not_found():
    assert servers.by_name("catnosuch") is None


def test_ds9s_mirrors_are_offered():
    """A user in India should not be querying Strasbourg."""
    assert len(servers.MIRRORS) >= 5
    assert servers.mirror_url("iucaa") != servers.mirror_url("cds")


def test_an_unknown_mirror_falls_back_to_cds():
    assert servers.mirror_url("nowhere") == servers.MIRROR_URLS["cds"]


# -- the query layer (M8-11) -----------------------------------------------------------


@pytest.fixture
def rows() -> Table:
    return Table(
        {
            "_RAJ2000": [150.0, 150.1, 150.2],
            "_DEJ2000": [2.0, 2.1, 2.2],
            "Jmag": [9.1, 10.2, 11.3],
        }
    )


@pytest.fixture
def center() -> SkyCoord:
    return SkyCoord(150.0 * u.deg, 2.0 * u.deg)


def test_a_request_uses_ds9s_default_radius(center):
    """500 arcseconds, DS9's `pcat(loc)`."""
    request = catalog_query.request_for("catgaia", center)
    assert request.radius.to_value(u.arcsec) == pytest.approx(500.0)


def test_a_request_knows_which_mirror_it_would_go_to(center):
    request = catalog_query.request_for("catgaia", center, mirror="sao")
    assert "harvard" in request.url


def test_a_request_for_an_unknown_catalogue_is_refused(center):
    with pytest.raises(catalog_query.CatalogQueryError, match="No such catalog"):
        catalog_query.request_for("catnosuch", center)


def test_a_query_reports_how_many_rows(center, rows):
    result = catalog_query.run(catalog_query.request_for("catgaia", center), transport=lambda request: rows)
    assert result.rows == 3
    assert "3 rows" in result.message
    assert bool(result) is True


def test_an_empty_result_says_so(center):
    result = catalog_query.run(catalog_query.request_for("catgaia", center), transport=lambda request: None)
    assert result.table is None
    assert "no objects found" in result.message
    assert bool(result) is False


def test_a_failed_query_comes_back_as_a_message_not_an_exception(center):
    """A window that vanished because a server was down would be worse."""

    def broken(request):
        raise RuntimeError("server down")

    result = catalog_query.run(catalog_query.request_for("catgaia", center), transport=broken)
    assert result.table is None
    assert "server down" in result.message


def test_hitting_the_row_limit_is_reported(center):
    """A field that hit the cap is not the field the user asked about."""
    big = Table({"_RAJ2000": np.zeros(10), "_DEJ2000": np.zeros(10)})
    request = catalog_query.request_for("catgaia", center, row_limit=4)
    result = catalog_query.run(request, transport=lambda r: big)
    assert result.rows == 4
    assert "there are more" in result.message


def test_an_unknown_service_is_refused(center):
    from dataclasses import replace

    request = catalog_query.request_for("catgaia", center)
    broken = replace(request.server, service=None)
    with pytest.raises(catalog_query.CatalogQueryError):
        catalog_query.fetch(replace(request, server=broken))


# -- finding the coordinate columns ------------------------------------------------------


@pytest.mark.parametrize(
    "names,expected",
    [
        (["_RAJ2000", "_DEJ2000"], ("_RAJ2000", "_DEJ2000")),
        (["RAJ2000", "DEJ2000"], ("RAJ2000", "DEJ2000")),
        (["RA", "DEC"], ("RA", "DEC")),
        (["ra", "dec"], ("ra", "dec")),
        (["RA_ICRS", "DE_ICRS"], ("RA_ICRS", "DE_ICRS")),
        (["s_ra", "s_dec"], ("s_ra", "s_dec")),
        (["RA_2000", "DEC_2000"], ("RA_2000", "DEC_2000")),
        (["Jmag", "Kmag"], None),
    ],
)
def test_the_coordinate_columns_are_found(names, expected):
    """Every server names them differently and the overlay needs them."""
    table = Table({name: [1.0] for name in names})
    assert catalog_query.coordinate_columns(table) == expected


def test_the_more_specific_pair_wins():
    """A VizieR table with a stray `ra` column uses the one VizieR meant."""
    table = Table({"_RAJ2000": [1.0], "_DEJ2000": [2.0], "ra": [3.0], "dec": [4.0]})
    assert catalog_query.coordinate_columns(table) == ("_RAJ2000", "_DEJ2000")


def test_positions_are_read_as_sky_coordinates(rows):
    found = catalog_query.positions(rows)
    assert found is not None
    assert len(found) == 3
    assert found[0].ra.deg == pytest.approx(150.0)


def test_a_table_with_no_coordinates_has_no_positions():
    assert catalog_query.positions(Table({"Jmag": [9.1]})) is None


def test_coordinates_that_are_not_numbers_are_no_positions():
    """A catalogue with sexagesimal strings is a list without an overlay,
    not a crash."""
    table = Table({"RA": ["10:00:00"], "DEC": ["+02:00:00"]})
    assert catalog_query.positions(table) is None


# -- the menu (M8-12) -------------------------------------------------------------------


def test_every_catalogue_is_on_the_menu(qapp):
    from ncrads9.ui.menu_bar import MenuBar

    menu = MenuBar()
    assert set(menu.catalog_actions) == {entry.name for entry in servers.CATALOGS}


def test_the_menu_is_grouped_into_ds9s_sections(qapp):
    from ncrads9.ui.menu_bar import MenuBar

    menu = MenuBar()
    labels = [action.text() for action in menu.analysis_catalogs_menu.actions()]
    for section in servers.SECTIONS:
        assert section in labels
