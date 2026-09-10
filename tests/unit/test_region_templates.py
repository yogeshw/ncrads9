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

"""Template regions and the bundled instrument FOVs (M6-18, M6-19)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.core.wcs_handler import WCSHandler
from ncrads9.regions import region_template
from ncrads9.regions.region_parser import RegionParser
from ncrads9.regions.shapes.composite import Composite

#: The instruments DS9 bundles templates for, and how many files each has.
DS9_TEMPLATE_COUNT = 23


def _header(crval1: float = 150.0, crval2: float = 2.0) -> fits.Header:
    return fits.Header(
        {
            "NAXIS": 2,
            "NAXIS1": 400,
            "NAXIS2": 400,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CRPIX1": 200.0,
            "CRPIX2": 200.0,
            "CRVAL1": crval1,
            "CRVAL2": crval2,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
        }
    )


@pytest.fixture
def wcs() -> WCSHandler:
    return WCSHandler(_header())


# -- what is bundled -----------------------------------------------------------


def test_ds9s_instrument_templates_are_bundled():
    assert len(region_template.bundled_templates()) == DS9_TEMPLATE_COUNT


@pytest.mark.parametrize(
    "name",
    ["chandra/acis/acis-i", "chandra/hrc/hrc-s", "xmm/epicpn", "heasarc/suzaku/xis", "mmt/swirc"],
)
def test_each_instrument_family_is_present(name):
    assert name in region_template.bundled_templates()


@pytest.mark.parametrize("name", sorted(region_template.bundled_templates()))
def test_every_bundled_template_loads(wcs, name):
    """Twenty-two of these parsed as nothing before the M6-18 parser work."""
    placed = region_template.load(region_template.bundled_templates()[name], wcs)
    assert placed


# -- placing -------------------------------------------------------------------


def test_a_template_lands_on_the_image_centre(wcs):
    placed = region_template.load(region_template.bundled_templates()["chandra/acis/acis-i"], wcs)
    composite = placed[0]
    assert isinstance(composite, Composite)
    assert composite.center == pytest.approx((200.0, 200.0), abs=2.0)


def test_a_template_lands_where_it_is_told(wcs):
    placed = region_template.load(
        region_template.bundled_templates()["chandra/acis/acis-i"], wcs, reference=(150.05, 2.05)
    )
    # 0.05 degrees at 0.001 deg/pixel is fifty pixels from the centre.
    assert placed[0].center[1] == pytest.approx(250.0, abs=3.0)


def test_the_members_move_with_it(wcs):
    placed = region_template.load(region_template.bundled_templates()["chandra/acis/acis-i"], wcs)
    for member in placed[0].regions:
        assert 0 < member.center[0] < 400
        assert 0 < member.center[1] < 400


def test_a_template_needs_a_wcs():
    """It is offsets from a sky position; there is nowhere else to put it."""
    with pytest.raises(region_template.TemplateError, match="WCS"):
        region_template.load(region_template.bundled_templates()["xmm/epicpn"], WCSHandler(fits.Header()))


def test_a_plain_region_file_is_not_a_template(wcs, tmp_path):
    path = tmp_path / "plain.reg"
    path.write_text("# Region file format: DS9 version 4.1\nfk5\ncircle(150,2,0.01)\n")
    with pytest.raises(region_template.TemplateError, match="not a template"):
        region_template.load(path, wcs)


# -- saving ---------------------------------------------------------------------


def test_saving_writes_a_template(wcs, tmp_path):
    regions = RegionParser().parse_string("image\ncircle(200,200,10)\nbox(220,200,10,10)\n")
    path = tmp_path / "mine.tpl"
    region_template.save(path, regions, wcs)

    text = path.read_text()
    assert region_template.TEMPLATE_SYSTEM in text
    parser = RegionParser()
    parser.parse_file(path)
    assert parser.relative is True


def test_saving_does_not_move_what_is_on_screen(wcs, tmp_path):
    """The regions handed in are the ones the user is looking at."""
    regions = RegionParser().parse_string("image\ncircle(200,200,10)\n")
    region_template.save(tmp_path / "mine.tpl", regions, wcs)
    assert regions[0].center == (200.0, 200.0)


def test_a_template_round_trips_back_to_the_same_pixels(wcs, tmp_path):
    regions = RegionParser().parse_string("image\ncircle(210,190,10)\nbox(180,220,10,10)\n")
    path = tmp_path / "round.tpl"
    region_template.save(path, regions, wcs)

    reloaded = region_template.load(path, wcs)
    assert reloaded[0].center == pytest.approx((210.0, 190.0), abs=0.1)
    assert reloaded[1].center == pytest.approx((180.0, 220.0), abs=0.1)


def test_a_template_saved_on_one_image_loads_onto_another(tmp_path):
    """That is what a template is for: the same instrument, a different sky."""
    here = WCSHandler(_header())
    elsewhere = WCSHandler(_header(crval1=83.6, crval2=-5.4))

    regions = RegionParser().parse_string("image\ncircle(210,190,10)\n")
    path = tmp_path / "instrument.tpl"
    region_template.save(path, regions, here)

    placed = region_template.load(path, elsewhere)
    assert placed[0].center == pytest.approx((210.0, 190.0), abs=0.5)


def test_saving_needs_a_wcs(tmp_path):
    regions = RegionParser().parse_string("image\ncircle(200,200,10)\n")
    with pytest.raises(region_template.TemplateError, match="WCS"):
        region_template.save(tmp_path / "no.tpl", regions, WCSHandler(fits.Header()))


# -- through the menu ------------------------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    window._rebuild_image_viewer(False)
    frame = window.frame_manager.current_frame
    frame.image_data = np.zeros((400, 400), dtype=np.float32)
    frame.wcs_handler = WCSHandler(_header())
    frame.regions = []
    yield window
    window.close()


def test_every_bundled_template_is_on_the_menu(main_window):
    assert set(main_window.menu_bar.region_fov_actions) == set(region_template.bundled_templates())


def test_the_fov_menu_is_a_tree(main_window):
    """DS9 builds its cascade from the same directory tree."""
    labels = [action.text() for action in main_window.menu_bar.region_menu.actions()]
    assert "&Instrument FOV" in labels


def test_choosing_an_instrument_loads_its_regions(main_window):
    main_window.menu_bar.region_fov_actions["chandra/acis/acis-i"].trigger()
    regions = main_window.frame_manager.current_frame.regions
    assert len(regions) == 1
    assert isinstance(regions[0], Composite)
    assert "acis-i" in main_window.status_bar.currentMessage()


def test_loading_onto_an_image_with_no_wcs_says_so(main_window):
    main_window.frame_manager.current_frame.wcs_handler = WCSHandler(fits.Header())
    main_window.menu_bar.region_fov_actions["xmm/epicpn"].trigger()
    assert "WCS" in main_window.status_bar.currentMessage()
    assert main_window.frame_manager.current_frame.regions == []


def test_saving_a_template_from_the_menu(main_window, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QFileDialog

    path = tmp_path / "menu.tpl"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))
    main_window.frame_manager.current_frame.regions = RegionParser().parse_string(
        "image\ncircle(200,200,10)\n"
    )
    main_window.menu_bar.action_template_save.trigger()
    assert region_template.TEMPLATE_SYSTEM in path.read_text()


def test_saving_with_no_regions_says_so(main_window):
    main_window.menu_bar.action_template_save.trigger()
    assert "No regions to save" in main_window.status_bar.currentMessage()
