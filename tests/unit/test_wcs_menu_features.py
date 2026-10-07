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

"""DS9's WCS menu, Multiple WCS, the WCS Parameters window and `xpa wcs`."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from ncrads9.app import apply_startup_cli, parse_cli_sequence
from ncrads9.communication.xpa.xpa_commands import XPACommands
from ncrads9.core import wcs_keywords
from ncrads9.ui.controllers.wcs import command_length
from ncrads9.ui.main_window import MainWindow
from ncrads9.utils.preferences import Preferences

SIZE = 64

LETTERS = "abcdefghijklmnopqrstuvwxyz"


def _header() -> fits.Header:
    """An equatorial primary WCS and a galactic alternate `A`."""
    header = fits.Header()
    for key, value in (
        ("CTYPE1", "RA---TAN"),
        ("CTYPE2", "DEC--TAN"),
        ("CRPIX1", SIZE / 2),
        ("CRPIX2", SIZE / 2),
        ("CRVAL1", 202.48),
        ("CRVAL2", 47.21),
        ("CDELT1", -0.001),
        ("CDELT2", 0.001),
        ("DATE-OBS", "2020-01-02T03:04:05"),
        ("WCSNAMEA", "GALACTIC"),
        ("CTYPE1A", "GLON-TAN"),
        ("CTYPE2A", "GLAT-TAN"),
        ("CRPIX1A", SIZE / 2),
        ("CRPIX2A", SIZE / 2),
        ("CRVAL1A", 104.85),
        ("CRVAL2A", 68.56),
        ("CDELT1A", -0.001),
        ("CDELT2A", 0.001),
    ):
        header[key] = value
    return header


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(np.ones((SIZE, SIZE), np.float32), _header()).writeto(path)
    made = MainWindow()
    made.display.load_fits(str(path))
    made._last_mouse_pos = (10, 20)
    yield made
    made.wcs.close_dialog()
    made.close()


@pytest.fixture
def xpa(window):
    return XPACommands(window)


def _set(xpa, *words, data=None):
    params = {"args": list(words)}
    if data is not None:
        params["data"] = data
    return xpa.handle("wcs", params)


def _get(xpa, *words):
    return xpa.handle("wcs", {"get": True, "args": list(words)})


def _labels(menu) -> list[str]:
    return ["---" if action.isSeparator() else action.text().replace("&", "") for action in menu.actions()]


# -- the menu ----------------------------------------------------------------


def test_the_menu_is_ds9s_coord_menu(window):
    """`CoordMenu` (menu.tcl) + `WCS Parameters`, then our arrows."""
    menu = window.menu_bar
    assert _labels(menu.wcs_menu) == [
        "WCS",
        "Multiple WCS",
        "---",
        "FK4",
        "FK5",
        "ICRS",
        "Galactic",
        "Ecliptic",
        "---",
        "Degrees",
        "Sexagesimal",
        "---",
        "WCS Parameters...",
        "---",
        "Show Direction Arrows",
    ]
    assert _labels(menu.wcs_multiple_menu) == [f"WCS {letter}" for letter in LETTERS]
    assert list(menu.wcs_system_actions) == ["wcs", *(f"wcs{letter}" for letter in LETTERS)]


def test_each_group_is_exclusive(window):
    menu = window.menu_bar
    assert menu.wcs_system_action_group.isExclusive()
    assert menu.wcs_system_group.isExclusive()
    assert menu.wcs_format_group.isExclusive()
    menu.action_wcs_degrees.trigger()
    assert menu.action_wcs_degrees.isChecked() and not menu.action_wcs_sexagesimal.isChecked()


def test_the_button_bar_names_still_exist(window):
    for name in ("fk4", "fk5", "icrs", "galactic", "ecliptic", "sexagesimal", "degrees"):
        assert getattr(window.menu_bar, f"action_wcs_{name}").isCheckable()


def test_letters_the_image_lacks_are_greyed(window):
    actions = window.menu_bar.wcs_system_actions
    assert actions["wcs"].isEnabled()
    assert actions["wcsa"].isEnabled()
    assert not actions["wcsb"].isEnabled()


def test_picking_a_letter_selects_the_system(window):
    window.menu_bar.wcs_system_actions["wcsa"].trigger()
    assert window.coord_context.system == "wcsa"
    assert window.menu_bar.wcs_system_actions["wcsa"].isChecked()
    window.menu_bar.action_wcs_wcs.trigger()
    assert window.coord_context.system == "wcs"


# -- Multiple WCS: the readouts follow the system ------------------------------


def _expected_icrs(key: str, x: float, y: float) -> tuple[float, float]:
    world = WCS(_header(), key=key).pixel_to_world(x, y).icrs
    return world.ra.deg, world.dec.deg


def test_the_readout_follows_the_alternate(window):
    window.wcs.set_format("degrees")
    window.wcs.set_sky_frame("icrs")
    primary = window.status_bar.wcs_coord_label.text()

    window.wcs.set_system("wcsa")
    alternate = window.status_bar.wcs_coord_label.text()
    assert alternate != primary

    ra, dec = _expected_icrs("A", 10, 20)
    assert f"{ra:.5f}" in alternate and f"{dec:.5f}" in alternate


def test_the_handlers_differ_by_system(window):
    primary = window.wcs.handler
    window.wcs.set_system("wcsa")
    alternate = window.wcs.handler
    assert alternate is not primary
    assert alternate.key == "A" and alternate.is_valid
    assert window.wcs_handler is primary, "the primary stays what everything else computes with"


def test_a_missing_letter_blanks_the_readout(window):
    window.wcs.set_system("wcsq")
    assert not window.wcs.handler.is_valid
    assert "---" in window.status_bar.wcs_coord_label.text()


def test_the_info_panel_row_names_the_system(window):
    window.wcs.set_system("wcsa")
    window.view.update_cursor(10, 20)
    assert window.info_panel._values["wcs_label"].text().startswith("wcsa")


def test_the_grid_draws_through_the_alternate(window):
    window.wcs.set_system("wcsa")
    assert window.analysis._grid_wcs() is window.wcs.handler


# -- the frame's WCS ---------------------------------------------------------


def test_replace_and_reset(window):
    frame = window.frame_manager.current_frame
    assert (
        window.wcs.replace_wcs("CTYPE1 = 'RA---TAN'\nCTYPE2 = 'DEC--TAN'\nCRVAL1 = 10.0\nCRVAL2 = 20.0\n")
        is None
    )
    assert frame.header["CRVAL1"] == 10.0
    assert "CTYPE1A" not in frame.header, "replace swaps the whole WCS, alternates too"
    assert frame.header["DATE-OBS"] == "2020-01-02T03:04:05", "the date is not WCS"
    assert window.wcs_handler.wcs.wcs.crval[0] == pytest.approx(10.0)

    assert window.wcs.reset_wcs() is None
    assert frame.header["CRVAL1"] == pytest.approx(202.48)
    assert frame.header["CTYPE1A"] == "GLON-TAN"
    assert frame.wcs_original is None


def test_append_keeps_the_rest(window):
    frame = window.frame_manager.current_frame
    window.wcs.replace_wcs({"CRVAL1": "11.5"}, append=True)
    assert frame.header["CRVAL1"] == 11.5
    assert frame.header["CTYPE1A"] == "GLON-TAN"


def test_a_replaced_alternate_is_read_afresh(window):
    window.wcs.set_system("wcsa")
    before = window.wcs.handler
    window.wcs.replace_wcs({"CRVAL1A": "100.0"}, append=True)
    assert window.wcs.handler is not before
    assert window.wcs.handler.wcs.wcs.crval[0] == pytest.approx(100.0)


# -- the WCS Parameters window --------------------------------------------------


def test_the_dialog_is_modeless_and_has_ds9s_menus(window):
    from PyQt6.QtCore import Qt

    dialog = window.wcs.show_dialog()
    assert dialog.windowModality() == Qt.WindowModality.NonModal
    assert dialog.isVisible()
    bar = dialog.layout().menuBar()
    assert [menu.title().replace("&", "") for menu in (a.menu() for a in bar.actions())] == [
        "File",
        "Edit",
        "WCS",
        "Extension",
    ]
    assert [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())] == [
        "Keyword",
        "PVi_00",
        "PVi_18",
        "A_p_q",
        "B_p_q",
        "AP_p_q",
        "BP_p_q",
    ]
    for name in ("WCSNAME", "WCSAXES", "RADESYS", "EQUINOX", "EPOCH", "MJD-OBS", "DATE-OBS", "LATPOLE"):
        assert name in dialog.fields
    for axis in range(1, 5):
        for stem in ("CTYPE", "CRPIX", "CRVAL", "CUNIT", "CDELT"):
            assert f"{stem}{axis}" in dialog.fields
        for other in range(1, 5):
            assert f"CD{axis}_{other}" in dialog.fields and f"PC{axis}_{other}" in dialog.fields
    assert "PV4_35" in dialog.fields and "A_ORDER" in dialog.fields and "BP_9_0" in dialog.fields
    assert window.wcs.show_dialog() is dialog, "a second open raises the first"


def test_the_dialog_shows_and_switches_systems(window):
    dialog = window.wcs.show_dialog()
    assert dialog.fields["CTYPE1"].text() == "RA---TAN"
    assert dialog.fields["DATE-OBS"].text() == "2020-01-02T03:04:05"
    dialog.system_actions["wcsa"].trigger()
    assert dialog._labels["CTYPE1"].text() == "CTYPE1A"
    assert dialog.fields["CTYPE1"].text() == "GLON-TAN"
    assert dialog.fields["WCSNAME"].text() == "GALACTIC"


def test_dialog_apply_and_reset(window):
    frame = window.frame_manager.current_frame
    dialog = window.wcs.show_dialog()
    dialog.fields["CRVAL1"].setText("200.0")
    dialog.set_system("wcsa")
    dialog.fields["CRVAL2"].setText("60.0")
    dialog.actions_by_name["apply"].trigger()
    assert frame.header["CRVAL1"] == pytest.approx(200.0)
    assert frame.header["CRVAL2A"] == pytest.approx(60.0)

    dialog.actions_by_name["reset"].trigger()
    assert frame.header["CRVAL1"] == pytest.approx(202.48)
    assert frame.header["CRVAL2A"] == pytest.approx(68.56)
    assert dialog.fields["CRVAL2"].text() == "68.56"


def test_dialog_save_open_round_trip(window, tmp_path):
    dialog = window.wcs.show_dialog()
    saved = tmp_path / "out.wcs"
    assert dialog.save_file(str(saved))
    text = saved.read_text()
    assert "CTYPE1A = 'GLON-TAN'" in text and "CRVAL1  =               202.48" in text

    edited = tmp_path / "edited.wcs"
    edited.write_text(text.replace("202.48", "12.25"))
    assert dialog.open_file(str(edited))
    assert dialog.fields["CRVAL1"].text() == "12.25"
    assert window.frame_manager.current_frame.header["CRVAL1"] == pytest.approx(202.48), "open does not apply"
    assert dialog.apply()
    assert window.frame_manager.current_frame.header["CRVAL1"] == pytest.approx(12.25)
    assert dialog.save_file(str(saved))
    assert wcs_keywords.parse_wcs_text(saved.read_text()) == wcs_keywords.parse_wcs_text(edited.read_text())


# -- XPA: every example in DS9's reference ------------------------------------


def test_xpaget_wcs(xpa, window):
    assert _get(xpa)["result"] == "wcs"
    assert _get(xpa, "system")["result"] == "wcs"
    assert _get(xpa, "sky")["result"] == "fk5"
    assert _get(xpa, "skyformat")["result"] == "sexagesimal"
    assert _get(xpa, "align")["result"] == "no"
    assert _get(xpa, "bogus")["status"] == "error"


def test_xpaset_wcs_system(xpa, window):
    assert _set(xpa, "wcsa")["status"] == "ok"
    assert _get(xpa, "system")["result"] == "wcsa"
    assert _set(xpa, "wcs")["status"] == "ok"
    assert _get(xpa)["result"] == "wcs"
    assert _set(xpa, "system", "wcsa")["status"] == "ok"
    assert _get(xpa)["result"] == "wcsa"
    assert _set(xpa, "system", "wcs")["status"] == "ok"
    assert window.coord_context.system == "wcs"
    assert _set(xpa, "system", "fk5")["status"] == "error"


def test_xpaset_wcs_sky_and_format(xpa, window):
    assert _set(xpa, "galactic")["status"] == "ok"
    assert _get(xpa, "sky")["result"] == "galactic"
    assert _set(xpa, "fk5")["status"] == "ok"
    assert _set(xpa, "sky", "ecliptic")["status"] == "ok"
    assert window.coord_context.sky.value == "ecliptic"
    assert _set(xpa, "sky", "fk5")["status"] == "ok"
    assert _set(xpa, "b1950")["status"] == "ok"
    assert window.coord_context.sky.value == "fk4"
    assert _set(xpa, "degrees")["status"] == "ok"
    assert _get(xpa, "skyformat")["result"] == "degrees"
    assert _set(xpa, "sexagesimal")["status"] == "ok"
    assert _set(xpa, "skyformat", "degrees")["status"] == "ok"
    assert _set(xpa, "skyformat", "sexagesimal")["status"] == "ok"
    assert window.coord_context.sky_format.value == "sexagesimal"
    assert window.menu_bar.action_wcs_sexagesimal.isChecked()


def test_xpaset_wcs_align(xpa, window):
    assert _set(xpa, "align", "yes")["status"] == "ok"
    assert window.frame_manager.current_frame.align_wcs is True
    assert window.menu_bar.action_zoom_align.isChecked()
    assert _get(xpa, "align")["result"] == "yes"
    assert _set(xpa, "align", "no")["status"] == "ok"
    assert _get(xpa, "align")["result"] == "no"
    assert _set(xpa, "align", "maybe")["status"] == "error"


def test_xpaset_wcs_load_replace_append_save_reset(xpa, window, tmp_path):
    frame = window.frame_manager.current_frame
    foo = tmp_path / "foo.wcs"
    foo.write_text("CTYPE1 = 'RA---TAN'\nCTYPE2 = 'DEC--TAN'\nCRVAL1 = 1.5 / ra\nCRVAL2 = -2.5\n")

    assert _set(xpa, "load", str(foo))["status"] == "ok"
    assert frame.header["CRVAL1"] == pytest.approx(1.5)
    assert _set(xpa, "reset")["status"] == "ok"
    assert frame.header["CRVAL1"] == pytest.approx(202.48)

    assert _set(xpa, "replace", "1", str(foo))["status"] == "ok"
    assert frame.header["CRVAL2"] == pytest.approx(-2.5)
    assert _set(xpa, "reset", "1")["status"] == "ok"

    assert _set(xpa, "replace", str(foo))["status"] == "ok"
    assert _set(xpa, "reset")["status"] == "ok"

    bar = tmp_path / "bar.wcs"
    bar.write_text("CRVAL2A = 1.25\n")
    assert _set(xpa, "append", "1", str(bar))["status"] == "ok"
    assert frame.header["CRVAL2A"] == pytest.approx(1.25)
    assert frame.header["CRVAL1"] == pytest.approx(202.48)

    # `xpaset ds9 wcs replace < foo.wcs`: the keywords on standard input.
    assert _set(xpa, "replace", data=foo.read_text())["status"] == "ok"
    assert frame.header["CRVAL1"] == pytest.approx(1.5)
    assert _set(xpa, "append", data="CRVAL1 = 3.0")["status"] == "ok"
    assert frame.header["CRVAL1"] == pytest.approx(3.0)

    out = tmp_path / "out.wcs"
    assert _set(xpa, "save", str(out))["status"] == "ok"
    assert "CRVAL1  =                  3.0" in out.read_text()
    out1 = tmp_path / "out1.wcs"
    assert _set(xpa, "save", "1", str(out1))["status"] == "ok"
    assert out1.read_text() == out.read_text()

    assert _set(xpa, "load", str(tmp_path / "missing.wcs"))["status"] == "error"
    assert _set(xpa, "replace")["status"] == "error"
    assert _set(xpa, "frobnicate")["status"] == "error"


def test_xpaset_wcs_open_close(xpa, window):
    assert _set(xpa, "open")["status"] == "ok"
    assert window.wcs.dialog is not None and window.wcs.dialog.isVisible()
    assert _set(xpa, "close")["status"] == "ok"
    assert window.wcs.dialog is None


def test_several_words_in_one_command(xpa, window):
    assert _set(xpa, "wcsa", "galactic", "degrees")["status"] == "ok"
    assert (
        window.coord_context.system,
        window.coord_context.sky.value,
        window.coord_context.sky_format.value,
    ) == (
        "wcsa",
        "galactic",
        "degrees",
    )


# -- the command line ---------------------------------------------------------


def test_the_cli_takes_as_many_words_as_the_grammar(tmp_path):
    items = parse_cli_sequence(
        ["-wcs", "sky", "galactic", "image.fits", "-wcs", "replace", "1", "foo.wcs", "a.fits"]
    )
    assert [(item.kind, item.name, item.args) for item in items] == [
        ("option", "wcs", ["sky", "galactic"]),
        ("file", "image.fits", []),
        ("option", "wcs", ["replace", "1", "foo.wcs"]),
        ("file", "a.fits", []),
    ]
    assert command_length(["fk4", "degrees", "x.fits"]) == 2
    assert command_length(["align", "yes", "save", "out.wcs"]) == 4
    assert command_length(["image.fits"]) == 0


def test_the_cli_runs_the_same_grammar(window, tmp_path):
    foo = tmp_path / "foo.wcs"
    foo.write_text("CRVAL1 = 5.0\n")
    apply_startup_cli(
        window, ["ncrads9", "-wcs", "system", "wcsa", "-wcs", "ecliptic", "-wcs", "append", str(foo)]
    )
    assert window.coord_context.system == "wcsa"
    assert window.coord_context.sky.value == "ecliptic"
    assert window.frame_manager.current_frame.header["CRVAL1"] == pytest.approx(5.0)


# -- the `.wcs` text format ---------------------------------------------------


def test_parse_wcs_text_reads_ds9s_files():
    text = (
        "CTYPE1  = 'RA---TAN'           / projection\n"
        "CRVAL1  =    202.48 / reference\n"
        "DATE-OBS= '2020/01/02'\n"
        "RADECSYS= 'FK5'\n"
        "PC001001= 1.0\n"
        "OBJECT  = 'M51'\n"
        "END\n"
    )
    values = wcs_keywords.parse_wcs_text(text)
    assert values == {
        "CTYPE1": "RA---TAN",
        "CRVAL1": "202.48",
        "DATE-OBS": "2020/01/02",
        "RADESYS": "FK5",
        "PC1_1": "1.0",
    }


def test_parse_wcs_text_reads_an_unbroken_header_block():
    block = "".join(str(card) for card in _header().cards)
    values = wcs_keywords.parse_wcs_text(block)
    assert values["CTYPE1A"] == "GLON-TAN"
    assert values["CRVAL2"] == "47.21"


def test_values_round_trip_through_a_header():
    header = wcs_keywords.values_to_header(
        {"CRPIX1": "32", "CRVAL1": "1.5", "CTYPE1": "RA---TAN", "EMPTY": ""}
    )
    assert header["CRPIX1"] == 32 and header["CRVAL1"] == 1.5 and header["CTYPE1"] == "RA---TAN"
    assert "EMPTY" not in header
    text = wcs_keywords.format_wcs_text(_header())
    assert wcs_keywords.parse_wcs_text(text) == wcs_keywords.header_values(_header())
