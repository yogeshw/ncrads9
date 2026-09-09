# NCRADS9 - NCRA DS9 Viewer
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

"""Coordinate transformation and formatting.

`CoordinateContext` is the single place the application turns a sky position
into text. Before M1 the frame transform lived in `MainWindow` and the
sexagesimal formatting in `StatusBar`, so nothing else could reuse either half.

Reference values are for the nucleus of M51 (NGC 5194), whose ICRS position is
13h29m52.7s +47d11m43s -- the sample image shipped in ncrads9/sampleimages/.
"""

import pytest
from astropy.coordinates import SkyCoord
from astropy.io import fits

from ncrads9.coordinates.coord_system import (
    CoordFrame,
    CoordinateContext,
    SkyFormat,
    SkyFrame,
)
from ncrads9.coordinates.physical_coords import PhysicalTransform
from ncrads9.coordinates.sexagesimal import (
    degrees_to_dms,
    degrees_to_hms,
    dms_to_degrees,
    hms_to_degrees,
)

#: M51's nucleus, ICRS degrees.
M51_RA = 202.4696
M51_DEC = 47.1952

SAMPLE_FITS = "ncrads9/sampleimages/SDSS9_M51_g.fits"


class TestSexagesimal:
    """degrees <-> HMS/DMS."""

    def test_hms_of_m51(self):
        assert degrees_to_hms(M51_RA, precision=2) == "13:29:52.70"

    def test_dms_of_m51(self):
        assert degrees_to_dms(M51_DEC, precision=1) == "+47:11:42.7"

    def test_negative_declination_keeps_its_sign(self):
        assert degrees_to_dms(-30.5, precision=1).startswith("-30:30:00")

    @pytest.mark.parametrize("degrees", [0.0, 15.0, 202.4696, 359.9999])
    def test_hms_round_trip(self, degrees):
        h, m, s = (float(part) for part in degrees_to_hms(degrees, precision=6).split(":"))
        assert hms_to_degrees(int(h), int(m), s) == pytest.approx(degrees, abs=1e-6)

    @pytest.mark.parametrize("degrees", [0.0, 47.1952, -47.1952, 89.9999])
    def test_dms_round_trip(self, degrees):
        text = degrees_to_dms(degrees, precision=6)
        negative = text.startswith("-")
        d, m, s = (float(part) for part in text.lstrip("+-").split(":"))
        assert dms_to_degrees(int(d), int(m), s, negative=negative) == pytest.approx(degrees, abs=1e-6)


class TestFrameTransforms:
    """Sky-frame conversions must agree with astropy."""

    @pytest.mark.parametrize(
        ("sky", "astropy_frame"),
        [
            (SkyFrame.ICRS, "icrs"),
            (SkyFrame.FK5, "fk5"),
            (SkyFrame.FK4, "fk4"),
            (SkyFrame.GALACTIC, "galactic"),
        ],
    )
    def test_matches_astropy(self, sky, astropy_frame):
        context = CoordinateContext(sky=sky)
        lon, lat = context.transform(M51_RA, M51_DEC)

        expected = SkyCoord(ra=M51_RA, dec=M51_DEC, unit="deg", frame="icrs").transform_to(astropy_frame)
        expected_lon = expected.spherical.lon.deg
        expected_lat = expected.spherical.lat.deg

        assert lon == pytest.approx(expected_lon, abs=1e-9)
        assert lat == pytest.approx(expected_lat, abs=1e-9)

    def test_icrs_is_a_no_op(self):
        lon, lat = CoordinateContext(sky=SkyFrame.ICRS).transform(M51_RA, M51_DEC)
        assert (lon, lat) == pytest.approx((M51_RA, M51_DEC))

    def test_fk4_differs_from_fk5_by_about_precession(self):
        """B1950 vs J2000 differ by roughly half a degree for M51."""
        fk5 = CoordinateContext(sky=SkyFrame.FK5).transform(M51_RA, M51_DEC)
        fk4 = CoordinateContext(sky=SkyFrame.FK4).transform(M51_RA, M51_DEC)
        assert abs(fk5[0] - fk4[0]) == pytest.approx(0.53, abs=0.05)

    def test_galactic_latitude_of_m51(self):
        """M51 sits at high galactic latitude, near b = +68.6 deg."""
        _, b = CoordinateContext(sky=SkyFrame.GALACTIC).transform(M51_RA, M51_DEC)
        assert b == pytest.approx(68.56, abs=0.01)


class TestLabels:
    """Axis labels follow the frame, as in DS9's info panel."""

    @pytest.mark.parametrize(
        ("sky", "expected"),
        [
            (SkyFrame.FK5, ("RA", "Dec")),
            (SkyFrame.FK4, ("RA", "Dec")),
            (SkyFrame.ICRS, ("RA", "Dec")),
            (SkyFrame.GALACTIC, ("l", "b")),
            (SkyFrame.ECLIPTIC, ("Lon", "Lat")),
        ],
    )
    def test_sky_labels(self, sky, expected):
        assert CoordinateContext(sky=sky).labels == expected

    def test_pixel_frames_use_xy(self):
        assert CoordinateContext(frame=CoordFrame.IMAGE).labels == ("X", "Y")

    @pytest.mark.parametrize(
        ("sky", "hours"),
        [
            (SkyFrame.FK5, True),
            (SkyFrame.ICRS, True),
            (SkyFrame.FK4, True),
            (SkyFrame.GALACTIC, False),
            (SkyFrame.ECLIPTIC, False),
        ],
    )
    def test_only_equatorial_frames_use_hour_angle(self, sky, hours):
        assert CoordinateContext(sky=sky).uses_hour_angle is hours


class TestFormatting:
    """format_pair and describe produce the strings the UI shows."""

    def test_equatorial_sexagesimal(self):
        context = CoordinateContext(sky=SkyFrame.FK5, sky_format=SkyFormat.SEXAGESIMAL)
        assert context.describe_sky(M51_RA, M51_DEC) == "RA: 13:29:52.70 Dec: +47:11:42.7"

    def test_equatorial_degrees_carry_a_unit(self):
        context = CoordinateContext(sky=SkyFrame.FK5, sky_format=SkyFormat.DEGREES)
        text = context.describe_sky(M51_RA, M51_DEC)
        assert text == "RA: 202.46960 deg Dec: 47.19520 deg"

    def test_galactic_longitude_is_not_in_hours(self):
        context = CoordinateContext(sky=SkyFrame.GALACTIC, sky_format=SkyFormat.SEXAGESIMAL)
        lon_text, _ = context.format_sky(M51_RA, M51_DEC)
        # 104.85 deg, not 104.85/15 hours.
        assert lon_text.startswith("+104:")

    def test_pixel_frame_ignores_sexagesimal(self):
        """Image coordinates are plain numbers whatever the sky format says."""
        context = CoordinateContext(frame=CoordFrame.IMAGE, sky_format=SkyFormat.SEXAGESIMAL)
        assert context.format_pair(512.25, 256.5) == ("512.25000", "256.50000")

    def test_precision_is_honoured(self):
        loose = CoordinateContext(sky=SkyFrame.FK5, precision=0)
        tight = CoordinateContext(sky=SkyFrame.FK5, precision=4)
        assert len(tight.format_pair(M51_RA, M51_DEC)[0]) > len(loose.format_pair(M51_RA, M51_DEC)[0])


class TestContextConstruction:
    """from_names / with_sky / with_format."""

    def test_from_names(self):
        context = CoordinateContext.from_names(sky="galactic", sky_format="degrees")
        assert context.sky is SkyFrame.GALACTIC
        assert context.sky_format is SkyFormat.DEGREES

    def test_from_names_rejects_an_unknown_frame(self):
        with pytest.raises(ValueError):
            CoordinateContext.from_names(sky="b1900")

    def test_with_sky_does_not_mutate(self):
        original = CoordinateContext(sky=SkyFrame.FK5)
        changed = original.with_sky("fk4")
        assert original.sky is SkyFrame.FK5
        assert changed.sky is SkyFrame.FK4

    def test_with_format_preserves_the_frame(self):
        context = CoordinateContext(sky=SkyFrame.GALACTIC).with_format("degrees")
        assert context.sky is SkyFrame.GALACTIC
        assert context.sky_format is SkyFormat.DEGREES


class TestPhysicalTransform:
    """LTV/LTM physical coordinates."""

    def test_missing_keywords_give_the_identity(self):
        transform = PhysicalTransform.from_header(fits.Header())
        assert transform.is_identity
        assert transform.image_to_physical(10.0, 20.0) == (10.0, 20.0)

    def test_iraf_keywords_are_applied(self):
        header = fits.Header({"LTV1": -100.0, "LTV2": -200.0, "LTM1_1": 0.5, "LTM2_2": 0.5})
        transform = PhysicalTransform.from_header(header)
        assert transform.image_to_physical(0.0, 0.0) == (200.0, 400.0)
        assert transform.physical_to_image(200.0, 400.0) == (0.0, 0.0)

    @pytest.mark.parametrize(("x", "y"), [(0.0, 0.0), (37.5, 82.25), (-4.0, 1024.0)])
    def test_round_trip(self, x, y):
        transform = PhysicalTransform(ltv1=-12.0, ltv2=7.5, ltm1=2.0, ltm2=0.25)
        assert transform.physical_to_image(*transform.image_to_physical(x, y)) == pytest.approx((x, y))

    def test_a_zero_scale_falls_back_to_one(self):
        """A zero LTM would make the inverse undefined."""
        transform = PhysicalTransform.from_header(fits.Header({"LTM1_1": 0.0}))
        assert transform.ltm1 == 1.0

    def test_unparseable_values_fall_back_to_the_default(self):
        assert PhysicalTransform.from_header({"LTV1": "not-a-number"}).ltv1 == 0.0

    def test_no_header_at_all(self):
        assert PhysicalTransform.from_header(None).is_identity


class TestAgainstTheSampleImage:
    """Exercise the context against the WCS of a real shipped file."""

    def test_sample_image_centre_formats(self):
        from ncrads9.core.wcs_handler import WCSHandler

        with fits.open(SAMPLE_FITS) as hdul:
            handler = WCSHandler(hdul[0].header)
            height, width = hdul[0].data.shape

        assert handler.is_valid
        ra, dec = handler.pixel_to_world(width / 2, height / 2)

        context = CoordinateContext(sky=SkyFrame.FK5)
        text = context.describe_sky(ra, dec)
        # The cutout is centred on M51, so the hours field must read 13.
        assert text.startswith("RA: 13:")
        assert "Dec: +47:" in text

    def test_sample_image_physical_is_identity(self):
        """SDSS cutouts carry no LTV/LTM, so physical == image."""
        with fits.open(SAMPLE_FITS) as hdul:
            transform = PhysicalTransform.from_header(hdul[0].header)
        assert transform.is_identity
