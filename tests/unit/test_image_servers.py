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

"""The image servers (M8-13 ... M8-18).

No network: the transport is injected everywhere.
"""

from __future__ import annotations

import gzip
import io

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.image_servers import fetch as fetch_module
from ncrads9.image_servers.servers import (
    SERVERS,
    Protocol,
    SizeUnit,
    by_name,
)


@pytest.fixture
def fits_bytes() -> bytes:
    """A FITS file made here, so no server is asked for one."""
    buffer = io.BytesIO()
    header = fits.Header(
        {
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CRPIX1": 5,
            "CRPIX2": 5,
            "CRVAL1": 150.0,
            "CRVAL2": 2.0,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
        }
    )
    fits.PrimaryHDU(data=np.zeros((10, 10), dtype=np.float32), header=header).writeto(buffer)
    return buffer.getvalue()


# -- the server table (M8-13 ... M8-17) ---------------------------------------


def test_ds9s_image_servers_are_all_here():
    names = {server.name for server in SERVERS}
    assert names == {
        "dsssao",
        "dsseso",
        "dssstsci",
        "twomass",
        "sdss",
        "skyview",
        "vla",
        "nvss",
        "vlss",
    }


@pytest.mark.parametrize("server", SERVERS, ids=lambda server: server.name)
def test_every_server_builds_a_url(server):
    url = server.query(150.0, 2.0, 10.0, 10.0)
    assert url.startswith("https://")
    assert "?" in url


@pytest.mark.parametrize(
    "name,fragments",
    [
        # Each server's own parameter names, from its DS9 `.tcl`.
        ("dsssao", ["r=150", "d=2", "e=J2000", "w=10", "c=gz"]),
        ("dsseso", ["ra=150", "dec=2", "equinox=J2000", "Sky-Survey=DSS1"]),
        ("dssstsci", ["r=150", "d=2", "f=fits", "v=poss2ukstu_red"]),
        ("twomass", ["objstr=150+2", "band=j"]),
        ("skyview", ["Position=150%2C2", "Return=FITS", "Pixels=512%2C512"]),
        ("nvss", ["RA=150", "Dec=2", "Cells=15.0+15.0", "MAPROJ=SIN"]),
        ("vlss", ["Cells=25.0+25.0"]),
        ("vla", ["RA=150+2", "ImageType=FITS+Image"]),
    ],
)
def test_each_servers_query_is_ds9s(name, fragments):
    url = by_name(name).query(150.0, 2.0, 10.0, 10.0)
    for fragment in fragments:
        assert fragment in url, f"{fragment} missing from {url}"


def test_vla_names_its_survey_in_the_path():
    """It is the one server that does."""
    assert "firstcutout" in by_name("vla").query(150.0, 2.0, 10.0, 10.0, "first")
    assert "gpscutout" in by_name("vla").query(150.0, 2.0, 10.0, 10.0, "gps")


def test_2mass_size_is_in_arcseconds():
    """The one server here that wants arcseconds, so ten arcminutes is 600."""
    assert "size=600" in by_name("twomass").query(150.0, 2.0, 10.0, 10.0)


def test_a_server_with_no_survey_choice_sends_none():
    assert by_name("dsssao").default_survey() == ""


def test_a_server_with_surveys_has_a_default():
    assert by_name("dssstsci").default_survey() == "poss2ukstu_red"


def test_ds9s_stsci_surveys_are_transcribed():
    values = [entry.value for entry in by_name("dssstsci").surveys]
    assert values == [
        "poss2ukstu_red",
        "poss2ukstu_ir",
        "poss2ukstu_blue",
        "poss1_blue",
        "poss1_red",
        "quickv",
    ]


def test_sdss_goes_through_sia_because_its_cutouts_are_jpeg():
    server = by_name("sdss")
    assert server.protocol is Protocol.SIA
    assert "FORMAT=image%2Ffits" in server.query(150.0, 2.0, 0.1, 0.1)


def test_every_other_server_returns_fits_directly():
    for server in SERVERS:
        if server.name != "sdss":
            assert server.protocol is Protocol.DIRECT


def test_the_size_units_differ_between_servers():
    """Ten from SkyView and ten from STScI are 36 times apart."""
    assert by_name("skyview").size_unit is SizeUnit.DEGREES
    assert by_name("dssstsci").size_unit is SizeUnit.ARCMIN


def test_an_unknown_server_is_not_found():
    assert by_name("nosuchserver") is None


# -- fetching (M8-13 ... M8-17) --------------------------------------------------


def _request(name: str = "dsssao"):
    return fetch_module.ImageRequest(by_name(name), 150.0, 2.0, 10.0, 10.0)


def test_a_fetched_image_is_saved_as_fits(fits_bytes):
    path = fetch_module.retrieve(_request(), transport=lambda url, timeout: fits_bytes)
    assert path.suffix == ".fits"
    assert path.read_bytes()[:9] == b"SIMPLE  ="


def test_a_gzipped_reply_is_decompressed(fits_bytes):
    """Three servers are asked for `c=gz`, as DS9 asks."""
    path = fetch_module.retrieve(_request(), transport=lambda url, timeout: gzip.compress(fits_bytes))
    assert path.read_bytes()[:9] == b"SIMPLE  ="


def test_an_html_reply_is_reported_with_its_own_words():
    """These CGIs answer a bad position with a page and a 200 status."""
    page = b"<html><body>No image found at that position</body></html>"
    with pytest.raises(fetch_module.ImageServerError, match="No image found"):
        fetch_module.retrieve(_request(), transport=lambda url, timeout: page)


def test_an_empty_reply_is_reported():
    with pytest.raises(fetch_module.ImageServerError, match="empty reply"):
        fetch_module.retrieve(_request(), transport=lambda url, timeout: b"")


def test_a_transport_failure_reaches_the_caller():
    def broken(url, timeout):
        raise fetch_module.ImageServerError("could not reach the image server")

    with pytest.raises(fetch_module.ImageServerError, match="could not reach"):
        fetch_module.retrieve(_request(), transport=broken)


def test_the_real_fetcher_refuses_a_non_http_url():
    with pytest.raises(fetch_module.ImageServerError, match="not an http URL"):
        fetch_module.fetch("file:///etc/passwd")


def test_a_sia_reply_is_followed_to_its_image(fits_bytes):
    """The first reply lists images; the image is a second fetch."""
    votable = b"""<?xml version="1.0"?>
<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE><TABLE>
<FIELD name="access_url" datatype="char" arraysize="*"/>
<FIELD name="access_format" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>
<TR><TD>https://example.invalid/preview.jpg</TD><TD>image/jpeg</TD></TR>
<TR><TD>https://example.invalid/image.fits</TD><TD>image/fits</TD></TR>
</TABLEDATA></DATA>
</TABLE></RESOURCE></VOTABLE>"""

    asked = []

    def transport(url, timeout):
        asked.append(url)
        return fits_bytes if url.endswith(".fits") else votable

    path = fetch_module.retrieve(_request("sdss"), transport=transport)
    assert len(asked) == 2
    # The JPEG preview is skipped in favour of the FITS.
    assert asked[1].endswith("image.fits")
    assert path.read_bytes()[:9] == b"SIMPLE  ="


def test_a_sia_reply_with_no_fits_is_reported():
    votable = b"""<?xml version="1.0"?>
<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE><TABLE>
<FIELD name="access_url" datatype="char" arraysize="*"/>
<FIELD name="access_format" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>
<TR><TD>https://example.invalid/p.jpg</TD><TD>image/jpeg</TD></TR>
</TABLEDATA></DATA>
</TABLE></RESOURCE></VOTABLE>"""
    with pytest.raises(fetch_module.ImageServerError, match="listed no FITS image"):
        fetch_module.retrieve(_request("sdss"), transport=lambda url, timeout: votable)


def test_an_unreadable_image_list_is_reported():
    with pytest.raises(fetch_module.ImageServerError, match="could not be read"):
        fetch_module.retrieve(_request("sdss"), transport=lambda url, timeout: b"not xml")


def test_is_fits_and_unpack():
    assert fetch_module.is_fits(b"SIMPLE  =                    T") is True
    assert fetch_module.is_fits(b"<html>") is False
    assert fetch_module.unpack(gzip.compress(b"plain")) == b"plain"
    assert fetch_module.unpack(b"plain") == b"plain"


# -- the dialog (M8-18) ------------------------------------------------------------


@pytest.mark.parametrize("name", [server.name for server in SERVERS])
def test_one_dialog_serves_every_server(qapp, name):
    from ncrads9.ui.dialogs.image_server_dialog import ImageServerDialog

    dialog = ImageServerDialog(by_name(name), (150.0, 2.0))
    assert dialog.windowTitle() == by_name(name).label
    dialog.close()


def test_the_dialog_shows_the_size_unit(qapp):
    """Ten degrees and ten arcminutes are not the same field."""
    from PyQt6.QtWidgets import QLabel

    from ncrads9.ui.dialogs.image_server_dialog import ImageServerDialog

    dialog = ImageServerDialog(by_name("skyview"))
    labels = [child.text() for child in dialog.findChildren(QLabel)]
    assert any("degrees" in text for text in labels)
    dialog.close()

    dialog = ImageServerDialog(by_name("dssstsci"))
    labels = [child.text() for child in dialog.findChildren(QLabel)]
    assert any("arcmin" in text for text in labels)
    dialog.close()


def test_the_dialog_offers_only_the_servers_surveys(qapp):
    from ncrads9.ui.dialogs.image_server_dialog import ImageServerDialog

    dialog = ImageServerDialog(by_name("dsssao"))
    assert dialog.survey() == ""
    dialog.close()

    dialog = ImageServerDialog(by_name("twomass"))
    assert dialog.survey() == "j"
    dialog.close()


def test_the_dialog_takes_the_frames_centre(qapp):
    from ncrads9.ui.dialogs.image_server_dialog import ImageServerDialog

    dialog = ImageServerDialog(by_name("dsssao"), (200.5, -30.25))
    assert dialog._longitude.value() == pytest.approx(200.5)
    assert dialog._latitude.value() == pytest.approx(-30.25)
    dialog.close()


def test_retrieve_announces_what_was_asked_for(qapp):
    from ncrads9.ui.dialogs.image_server_dialog import ImageServerDialog

    dialog = ImageServerDialog(by_name("dssstsci"), (150.0, 2.0))
    seen = []
    dialog.retrieve_requested.connect(lambda *args: seen.append(args))
    dialog._width.setValue(5.0)
    dialog._height.setValue(6.0)
    dialog.request()
    assert seen == [(150.0, 2.0, 5.0, 6.0, "poss2ukstu_red")]
    dialog.close()


def test_a_typed_name_is_resolved_before_retrieving(qapp):
    """DS9 resolves first and lets the user press Retrieve again."""
    from ncrads9.ui.dialogs.image_server_dialog import ImageServerDialog

    dialog = ImageServerDialog(by_name("dsssao"), (150.0, 2.0))
    asked = []
    dialog.name_requested.connect(asked.append)
    retrieved = []
    dialog.retrieve_requested.connect(lambda *args: retrieved.append(args))

    dialog._name.setText("M51")
    dialog._by_name.setChecked(True)
    dialog.request()
    assert asked == ["M51"]
    assert retrieved == []
    dialog.close()


def test_resolving_with_no_name_says_so(qapp):
    from ncrads9.ui.dialogs.image_server_dialog import ImageServerDialog

    dialog = ImageServerDialog(by_name("dsssao"))
    dialog.resolve()
    assert "Type an object name" in dialog._message.text()
    dialog.close()


# -- through the menu ---------------------------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path, fits_bytes):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.image_servers.transport = lambda url, timeout: fits_bytes
    yield window
    for dialog in list(window.image_servers._dialogs.values()):
        dialog.close()
    window.close()


def test_every_server_is_on_the_menu(main_window):
    assert set(main_window.menu_bar.image_server_actions) == {server.name for server in SERVERS}


def test_a_menu_entry_opens_its_dialog(main_window):
    main_window.menu_bar.image_server_actions["dssstsci"].trigger()
    assert "dssstsci" in main_window.image_servers._dialogs


def test_asking_twice_reuses_the_dialog(main_window):
    main_window.menu_bar.image_server_actions["dssstsci"].trigger()
    main_window.menu_bar.image_server_actions["dssstsci"].trigger()
    assert len(main_window.image_servers._dialogs) == 1


def test_a_retrieved_cutout_loads_into_a_new_frame(main_window):
    """Comparing it with what is loaded is the point; replacing that is not."""
    before = main_window.frame_manager.num_frames
    path = main_window.image_servers.retrieve(by_name("dsssao"), 150.0, 2.0, 10.0, 10.0)
    assert path is not None
    assert main_window.frame_manager.num_frames == before + 1
    assert main_window.frame_manager.current_frame.image_data is not None


def test_a_failed_retrieval_is_reported_and_loads_nothing(main_window):
    main_window.image_servers.transport = lambda url, timeout: b"<html>no data</html>"
    before = main_window.frame_manager.num_frames
    assert main_window.image_servers.retrieve(by_name("dsssao"), 150.0, 2.0, 10.0, 10.0) is None
    assert "did not return a FITS image" in main_window.status_bar.currentMessage()
    assert main_window.frame_manager.num_frames == before


def test_the_2mass_entry_is_shared_with_the_vo_menu(main_window):
    """The VO menu and the XPA both reach it by name."""
    assert main_window.menu_bar.action_analysis_2mass is (
        main_window.menu_bar.image_server_actions["twomass"]
    )
