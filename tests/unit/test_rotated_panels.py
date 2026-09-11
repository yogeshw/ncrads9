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

"""
The panner and the magnifier under rotation.

Reported: with the image rotated, the zoom and pan windows showed a
different part of it. They are fed a preview built by
`transform_image_array`, while the main view is painted through
`DisplayTransform` -- and the two turned *opposite ways*.
`np.rot90(k=1)` and `ndimage.rotate(+angle)` both turn counter-clockwise
in index space, which in a row-0-at-the-top display array looks
counter-clockwise on screen, where `QTransform.rotate(+angle)` turns
clockwise.

At 0 and 180 the two senses agree, which is why the fault only showed at
quarter turns and why it survived: half the cases looked right. Every
test here therefore checks all four.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from ncrads9.ui.view_transform import DisplayTransform, transform_image_array

#: The marker's image coordinates: off-centre and off-diagonal, so every
#: quarter turn puts it somewhere distinct, but far enough from the edge
#: that it stays inside the widget however the image is turned.
MARKER_X, MARKER_Y = 22, 26
SIZE = 64

#: The image the panel tests load. Bigger than the magnifier's 64-pixel
#: window, so "the marker is in the magnified region" is a real claim --
#: on a 64-pixel image the window covers the whole thing and the test
#: passes however wrong the rotation is.
PANEL_SIZE = 200

#: Where the marker sits on that image: off-centre both ways, and far
#: enough from the middle that a wrong quarter turn puts it outside the
#: magnifier's window.
PANEL_MARKER_X, PANEL_MARKER_Y = 60, 140

QUARTER_TURNS = [0.0, 90.0, 180.0, 270.0]


def _marker_at(array: np.ndarray) -> tuple[int, int]:
    """Where the brightest pixel is, as (x, y) in the array's own space."""
    flat = array.max(axis=2) if array.ndim == 3 else array
    row, column = np.argwhere(flat == flat.max())[0]
    return (int(column), int(row))


# -- the two rotations agree -------------------------------------------------------


@pytest.mark.parametrize("rotation", QUARTER_TURNS)
def test_the_array_turns_the_same_way_as_the_painter(rotation):
    """The bug, stated at its source.

    A display array and `DisplayTransform` must agree about where a pixel
    ends up. `DisplayTransform` is what paints the main view, so it is the
    authority; the array has to follow it.
    """
    array = np.zeros((SIZE, SIZE), dtype=np.float32)
    # Row 0 is the top in a display array, so a top-down y.
    top_y = SIZE - 1 - MARKER_Y
    array[top_y, MARKER_X] = 1000.0

    turned = transform_image_array(array, rotation, False, False)
    expected = DisplayTransform(width=SIZE, height=SIZE, rotation=rotation).source_to_display(
        float(MARKER_X), float(top_y)
    )

    got = _marker_at(turned)
    assert abs(got[0] - expected[0]) <= 1, f"{rotation}: x {got[0]} vs {expected[0]:.0f}"
    assert abs(got[1] - expected[1]) <= 1, f"{rotation}: y {got[1]} vs {expected[1]:.0f}"


@pytest.mark.parametrize("rotation", [30.0, 45.0, 137.0])
def test_an_arbitrary_angle_turns_the_same_way_too(rotation):
    """`ndimage.rotate` takes the non-quarter turns, and had the same sign
    error; a quarter-turn-only test would have missed it."""
    array = np.zeros((SIZE, SIZE), dtype=np.float32)
    top_y = SIZE - 1 - MARKER_Y
    array[top_y, MARKER_X] = 1000.0

    turned = transform_image_array(array, rotation, False, False)
    got = _marker_at(turned)

    transform = DisplayTransform(width=SIZE, height=SIZE, rotation=rotation)
    expected = transform.source_to_display(float(MARKER_X), float(top_y))
    # Interpolation spreads the marker, so this is looser than a quarter
    # turn's -- but a wrong *direction* is tens of pixels out, not three.
    assert abs(got[0] - expected[0]) <= 3, f"{rotation}: x {got[0]} vs {expected[0]:.0f}"
    assert abs(got[1] - expected[1]) <= 3, f"{rotation}: y {got[1]} vs {expected[1]:.0f}"


def test_a_flip_still_agrees_with_the_painter():
    """Flips were never wrong, and must not be broken by the sign change."""
    array = np.zeros((SIZE, SIZE), dtype=np.float32)
    top_y = SIZE - 1 - MARKER_Y
    array[top_y, MARKER_X] = 1000.0

    for flip_x, flip_y in ((True, False), (False, True), (True, True)):
        turned = transform_image_array(array, 0.0, flip_x, flip_y)
        expected = DisplayTransform(width=SIZE, height=SIZE, flip_x=flip_x, flip_y=flip_y).source_to_display(
            float(MARKER_X), float(top_y)
        )
        got = _marker_at(turned)
        assert abs(got[0] - expected[0]) <= 1, (flip_x, flip_y)
        assert abs(got[1] - expected[1]) <= 1, (flip_x, flip_y)


def test_a_quarter_turn_swaps_the_axes():
    """A non-square image makes a lost rotation obvious in the shape alone."""
    array = np.zeros((40, 80), dtype=np.float32)
    assert transform_image_array(array, 90.0, False, False).shape[:2] == (80, 40)
    assert transform_image_array(array, 270.0, False, False).shape[:2] == (80, 40)
    assert transform_image_array(array, 180.0, False, False).shape[:2] == (40, 80)


# -- what the panels actually show -------------------------------------------------


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    real_get = Preferences.get
    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else real_get(self, key, default),
    )

    # One bright pixel on an otherwise empty image: the only way to say
    # *which* part of the image a panel is showing is to mark one.
    data = np.zeros((PANEL_SIZE, PANEL_SIZE), dtype=np.float32)
    data[PANEL_MARKER_Y, PANEL_MARKER_X] = 1000.0
    path = tmp_path / "marker.fits"
    fits.PrimaryHDU(data=data).writeto(path)

    made = MainWindow()
    made._rebuild_image_viewer(False)
    made.display.load_fits(str(path))
    yield made
    made.close()


@pytest.mark.parametrize("rotation", QUARTER_TURNS)
def test_the_preview_and_the_main_view_agree(window, rotation):
    """The panels are fed this preview and the cursor is mapped by the
    viewer; if the two disagree the panels show the wrong place, which is
    exactly what was reported."""
    window.zoom.set_rotation(rotation)
    window.display.display()

    viewer = window.image_viewer.image_viewer
    mapped = viewer.map_image_to_display_coords(PANEL_MARKER_X, PANEL_MARKER_Y)
    assert mapped is not None

    preview = window.magnifier_panel._current_image
    assert preview is not None
    got = _marker_at(preview)
    assert abs(got[0] - mapped[0]) <= 1, f"{rotation}: preview x {got[0]} vs mapped {mapped[0]:.0f}"
    assert abs(got[1] - mapped[1]) <= 1, f"{rotation}: preview y {got[1]} vs mapped {mapped[1]:.0f}"


@pytest.mark.parametrize("rotation", QUARTER_TURNS)
def test_the_panner_and_the_magnifier_get_the_same_preview(window, rotation):
    window.zoom.set_rotation(rotation)
    window.display.display()
    np.testing.assert_array_equal(window.panner_panel._current_image, window.magnifier_panel._current_image)


@pytest.mark.parametrize("rotation", QUARTER_TURNS)
def test_the_preview_is_the_size_the_view_reports(window, rotation):
    """A quarter turn swaps the axes. The panner's view rectangle is
    computed against `get_display_image_size`, so if that and the preview
    disagree the rectangle is drawn in the wrong space."""
    window.zoom.set_rotation(rotation)
    window.display.display()

    width, height = window.image_viewer.get_display_image_size()
    preview = window.panner_panel._current_image
    assert (preview.shape[1], preview.shape[0]) == (width, height), rotation


@pytest.mark.parametrize("rotation", QUARTER_TURNS)
def test_hovering_a_pixel_magnifies_that_pixel(window, rotation, qapp):
    """End to end, the way a user meets it: put the pointer on the marker
    and the zoom window should show the marker."""
    window.resize(900, 700)
    window.show()
    qapp.processEvents()
    window.zoom.set_rotation(rotation)
    window.display.display()
    qapp.processEvents()

    overlay = window.image_viewer.region_overlay
    viewer = window.image_viewer.image_viewer
    display_x, display_y = viewer.map_image_to_display_coords(PANEL_MARKER_X, PANEL_MARKER_Y)
    zoom = window.image_viewer.get_zoom()
    offset = overlay.image_offset
    point = QPointF(display_x * zoom + offset[0], display_y * zoom + offset[1])
    assert overlay.rect().contains(point.toPoint()), f"{rotation}: {point} is outside {overlay.rect()}"
    # The overlay's own handler, with a constructed event, rather than
    # `QTest.mouseMove`: the offscreen platform drops a synthetic move at
    # some coordinates and not others, which would make this test pass or
    # fail for reasons that have nothing to do with rotation. Real
    # delivery is covered once, at rotation zero, in
    # `test_panels_and_colorbar.py`.
    overlay.mouseMoveEvent(
        QMouseEvent(
            QEvent.Type.MouseMove,
            point,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    qapp.processEvents()

    magnifier = window.magnifier_panel
    assert magnifier._cursor_pos is not None, "the hover should reach the magnifier"
    preview = magnifier._current_image
    half = magnifier._region_size // 2
    centre_x, centre_y = int(magnifier._cursor_pos.x()), int(magnifier._cursor_pos.y())
    region = preview[max(0, centre_y - half) : centre_y + half, max(0, centre_x - half) : centre_x + half]
    assert region.size > 0, rotation
    assert region.max() == preview.max(), f"{rotation}: the marker is not in the magnified region"


@pytest.mark.parametrize("rotation", QUARTER_TURNS)
def test_the_compass_still_agrees_after_a_rotation(window, rotation, tmp_path):
    """The panner's other overlay goes through the same transform, so a
    sign change there had to be checked too: north must turn with the
    image rather than against it."""
    header = fits.Header(
        {
            "CRPIX1": PANEL_SIZE // 2,
            "CRPIX2": PANEL_SIZE // 2,
            "CRVAL1": 202.0,
            "CRVAL2": 47.0,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
        }
    )
    path = tmp_path / f"wcs_{int(rotation)}.fits"
    fits.PrimaryHDU(data=np.zeros((PANEL_SIZE, PANEL_SIZE), dtype=np.float32), header=header).writeto(path)
    window.display.load_fits(str(path))
    window.zoom.set_rotation(rotation)
    window.display.display()

    arrows = window.panner_panel.compass_arrows((128, 128))
    assert set(arrows) == {"N", "E"}
    (origin, north_tip) = arrows["N"]
    (_origin, east_tip) = arrows["E"]
    north = (north_tip.x() - origin.x(), north_tip.y() - origin.y())
    east = (east_tip.x() - origin.x(), east_tip.y() - origin.y())

    # A rotation turns both arrows by the same amount, so whatever the
    # angle they stay perpendicular and keep the same handedness. The
    # sign is not asserted against a convention -- in a y-down painter it
    # is negative -- but against the unrotated case, which is the actual
    # invariant: the compass must turn *with* the image, not against it.
    assert abs(north[0] * east[0] + north[1] * east[1]) < 2.0, f"{rotation}: not perpendicular"
    cross = north[0] * east[1] - north[1] * east[0]
    assert cross < 0, f"{rotation}: the compass handedness flipped"

    # And it really did turn: at 90 degrees north is no longer up.
    if rotation in (90.0, 270.0):
        assert abs(north[0]) > abs(north[1]), f"{rotation}: north should point sideways"
    else:
        assert abs(north[1]) > abs(north[0]), f"{rotation}: north should point up or down"
