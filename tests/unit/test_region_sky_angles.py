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

"""Region angles between image and sky, and `wcsa`..`wcsz` region files."""

import math

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.coordinates import ds9_coords
from ncrads9.frames.frame import Frame
from ncrads9.regions import region_coords
from ncrads9.regions.region_parser import RegionParser
from ncrads9.regions.shapes.ellipse import Ellipse


def _frame(rotation: float = 0.0, mirrored: bool = False, alternate: bool = False) -> Frame:
    from ncrads9.core.wcs_handler import WCSHandler

    scale = 0.001
    theta = math.radians(rotation)
    sign = 1.0 if mirrored else -1.0
    header = fits.Header(
        {
            "NAXIS": 2,
            "NAXIS1": 64,
            "NAXIS2": 64,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CRPIX1": 32,
            "CRPIX2": 32,
            "CRVAL1": 202.48,
            "CRVAL2": 47.21,
            "CD1_1": sign * scale * math.cos(theta),
            "CD1_2": -scale * math.sin(theta) * (-sign),
            "CD2_1": sign * scale * math.sin(theta),
            "CD2_2": scale * math.cos(theta),
        }
    )
    if alternate:
        header.update(
            {
                "CTYPE1A": "RA---TAN",
                "CTYPE2A": "DEC--TAN",
                "CRPIX1A": 32,
                "CRPIX2A": 32,
                "CRVAL1A": 202.50,
                "CRVAL2A": 47.21,
                "CDELT1A": -scale,
                "CDELT2A": scale,
            }
        )
    frame = Frame(frame_id=1)
    frame.header = header
    frame.image_data = np.zeros((64, 64), dtype=np.float32)
    frame.wcs_handler = WCSHandler(header)
    return frame


def test_north_up_east_left_keeps_the_angle():
    frame = _frame()
    assert ds9_coords.image_angle_to(frame, 30.0, 32, 32, "wcs", "fk5") == pytest.approx(30.0, abs=0.01)


def test_a_turned_image_takes_out_the_turn():
    frame = _frame(rotation=20.0)
    sky = ds9_coords.image_angle_to(frame, 50.0, 32, 32, "wcs", "fk5")
    assert sky == pytest.approx(30.0, abs=0.05) or sky == pytest.approx(70.0, abs=0.05)
    assert ds9_coords.angle_to_image(frame, sky, 32, 32, "wcs", "fk5") == pytest.approx(50.0, abs=0.01)


def test_a_mirrored_image_reverses_the_sense():
    frame = _frame(mirrored=True)
    # East to the right: west points along -x, and angles run the other way.
    assert ds9_coords.image_angle_to(frame, 30.0, 32, 32, "wcs", "fk5") == pytest.approx(150.0, abs=0.01)
    assert not ds9_coords.sky_is_usual(frame, 32, 32, "wcs", "fk5")


def test_an_ellipse_round_trips_through_fk5_on_a_turned_image():
    frame = _frame(rotation=35.0)
    ellipse = Ellipse(center=(30.0, 28.0), semi_major=6.0, semi_minor=3.0, angle=12.0)
    text = region_coords.write([ellipse], frame, system="wcs", sky="fk5")
    back = region_coords.place(RegionParser().parse_string(text), frame)[0]
    assert back.angle == pytest.approx(12.0, abs=0.01)
    assert back.center[0] == pytest.approx(30.0, abs=1e-3)
    written = [line for line in text.splitlines() if line.startswith("ellipse")][0]
    assert float(written.rstrip(")").split(",")[-1]) != pytest.approx(12.0, abs=0.5)


def test_a_wcsa_file_is_placed_through_the_a_description():
    frame = _frame(alternate=True)
    text = "# Region file format: DS9 version 4.1\nwcsa;fk5;circle(202.5,47.21,3.6\")\n"
    region = region_coords.place(RegionParser().parse_string(text), frame)[0]
    # The `a` description puts 202.50 on the reference pixel; the primary
    # would have put it about 14 pixels away.
    assert region.center[0] == pytest.approx(32.0, abs=0.01)
    assert region.center[1] == pytest.approx(32.0, abs=0.01)


def test_writing_in_wcsa_names_the_description():
    frame = _frame(alternate=True)
    ellipse = Ellipse(center=(32.0, 32.0), semi_major=6.0, semi_minor=3.0, angle=0.0)
    text = region_coords.write([ellipse], frame, system="wcsa", sky="fk5")
    assert "wcsa;fk5" in text
    back = region_coords.place(RegionParser().parse_string(text), frame)[0]
    assert back.center[0] == pytest.approx(32.0, abs=1e-3)
