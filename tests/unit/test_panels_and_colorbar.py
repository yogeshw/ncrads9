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
The panner's compass, the magnifier's feed, and the colorbar's ramp.

Three reported bugs, each in a widget that had no test of its own:

* the panner's N/E arrows pointed the wrong way -- the vectors arrive
  y-up and a painter's y runs down, and the negation was missing, so on
  a normally-oriented image the compass read N-down;
* the magnifier showed nothing, because the overlay owns the mouse and
  the hover never reached anything downstream of it -- which also left
  the cut graphs and the pixel table empty;
* a colour table that is not 256 entries long raised `IndexError` from
  inside the single-bar colorbar, *before* the image was drawn, so
  thirty of the Matplotlib colormaps appeared to have no effect at all.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits
from PyQt6.QtCore import QPoint
from PyQt6.QtTest import QTest

from ncrads9.colormaps.colormap import Colormap
from ncrads9.ui.panels.panner import COMPASS_LENGTH

SIZE = 64


def _fits(path, cdelt1=-0.001, cdelt2=0.001):
    """An image with a WCS whose orientation the test chooses."""
    rows, columns = np.indices((SIZE, SIZE))
    header = fits.Header(
        {
            "CRPIX1": SIZE // 2,
            "CRPIX2": SIZE // 2,
            "CRVAL1": 202.48,
            "CRVAL2": 47.21,
            "CDELT1": cdelt1,
            "CDELT2": cdelt2,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
        }
    )
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32), header=header).writeto(path)
    return path


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
    made = MainWindow()
    made._rebuild_image_viewer(False)
    yield made
    made.close()


# -- the panner's compass ----------------------------------------------------------


def _screen_compass(panner):
    """The arrows the painter will draw, as screen-space deltas.

    Read off `compass_arrows`, which is the geometry `_draw_compass`
    itself uses -- not recomputed here. A test that did its own y
    conversion would pass whether or not the painter did, which is
    exactly how the mirrored compass survived.
    """
    return {
        label: (tip.x() - origin.x(), tip.y() - origin.y())
        for label, (origin, tip) in panner.compass_arrows((128, 128)).items()
    }


def test_north_points_up_and_east_left_on_a_normal_image(window, tmp_path):
    """The reported bug. With RA increasing left and Dec up -- the usual
    orientation -- north is up the screen and east is to the left. It used
    to draw north pointing *down*: the compass was mirrored."""
    window.display.load_fits(str(_fits(tmp_path / "sky.fits")))
    arrows = _screen_compass(window.panner_panel)

    assert arrows["N"][1] < -COMPASS_LENGTH / 2, "north must point up the screen"
    assert abs(arrows["N"][0]) < 1.0, "and not sideways"
    assert arrows["E"][0] < -COMPASS_LENGTH / 2, "east must point left"
    assert abs(arrows["E"][1]) < 1.0, "and not up or down"


def test_the_compass_follows_a_flipped_declination_axis(window, tmp_path):
    """A negative CDELT2 puts north *down*, and the compass must say so
    rather than always drawing the same picture."""
    window.display.load_fits(str(_fits(tmp_path / "flipped.fits", cdelt2=-0.001)))
    arrows = _screen_compass(window.panner_panel)
    assert arrows["N"][1] > COMPASS_LENGTH / 2, "north is down when Dec decreases upward"


def test_the_compass_follows_a_flipped_right_ascension_axis(window, tmp_path):
    window.display.load_fits(str(_fits(tmp_path / "flipped_ra.fits", cdelt1=0.001)))
    arrows = _screen_compass(window.panner_panel)
    assert arrows["E"][0] > COMPASS_LENGTH / 2, "east is right when RA increases with x"


def test_the_compass_is_perpendicular(window, tmp_path):
    """North and east are at right angles on the sky, and a TAN projection
    at the reference point keeps them so on the screen."""
    window.display.load_fits(str(_fits(tmp_path / "sky.fits")))
    arrows = _screen_compass(window.panner_panel)
    (nx, ny), (ex, ey) = arrows["N"], arrows["E"]
    assert abs(nx * ex + ny * ey) < 2.0, "the arrows should be perpendicular"


def test_an_image_with_no_wcs_draws_no_compass(window, tmp_path):
    path = tmp_path / "plain.fits"
    fits.PrimaryHDU(data=np.zeros((SIZE, SIZE), dtype=np.float32)).writeto(path)
    window.display.load_fits(str(path))
    panner = window.panner_panel
    assert panner._north is None or panner._show_compass is False


def test_the_panner_paints_its_compass(window, tmp_path):
    """The arrows now carry heads, so the painter does more than draw two
    lines; a painter that throws takes the panner with it."""
    from PyQt6.QtGui import QPixmap

    window.display.load_fits(str(_fits(tmp_path / "sky.fits")))
    panner = window.panner_panel
    panner.resize(128, 128)
    panner._panner_label.render(QPixmap(128, 128))


# -- the magnifier's feed ----------------------------------------------------------


def test_a_hover_over_the_image_reaches_the_magnifier(window, tmp_path, qapp):
    """The reported bug: the zoom window showed no data.

    The overlay owns the mouse (M9-1), and nothing downstream of it was
    told where the cursor was -- the window relied on Qt propagating an
    ignored move event to a sibling's wrapper, which does not happen.
    """
    window.display.load_fits(str(_fits(tmp_path / "sky.fits")))
    window.resize(900, 700)
    window.show()
    qapp.processEvents()

    magnifier = window.magnifier_panel
    assert magnifier._cursor_pos is None, "nothing hovered yet"

    QTest.mouseMove(window.image_viewer.region_overlay, QPoint(300, 120))
    qapp.processEvents()

    assert magnifier._cursor_pos is not None, "a hover must reach the magnifier"
    assert not magnifier._magnifier_label.pixmap().isNull()


def test_the_overlay_announces_every_hover(window, tmp_path, qapp):
    """The signal itself. The window has to be shown: Qt delivers a
    synthetic move only to a widget that is actually mapped."""
    window.display.load_fits(str(_fits(tmp_path / "sky.fits")))
    window.resize(900, 700)
    window.show()
    qapp.processEvents()
    overlay = window.image_viewer.region_overlay

    seen: list[tuple[int, int]] = []
    overlay.hover_moved.connect(lambda x, y: seen.append((x, y)))
    QTest.mouseMove(overlay, QPoint(200, 120))
    qapp.processEvents()
    assert seen, "the overlay should say where the cursor is"


def test_a_hover_reaches_the_cut_graphs_and_the_pixel_table(window, tmp_path, qapp):
    """Everything that follows the cursor is downstream of the same signal,
    so they were all empty for the same reason."""
    window.display.load_fits(str(_fits(tmp_path / "sky.fits")))
    window.view.set_graph_visible("horizontal", True)
    window.resize(900, 700)
    window.show()
    qapp.processEvents()

    QTest.mouseMove(window.image_viewer.region_overlay, QPoint(300, 120))
    qapp.processEvents()
    assert window.horizontal_graph._graph_widget._data is not None


def test_a_hover_while_drawing_a_region_still_reports(window, tmp_path, qapp):
    """A mode that accepts the event must not silence the readout: the
    announcement happens before the mode sees the event."""
    from ncrads9.ui.controllers.region import RegionMode

    window.display.load_fits(str(_fits(tmp_path / "sky.fits")))
    window.resize(900, 700)
    window.show()
    qapp.processEvents()
    overlay = window.image_viewer.region_overlay
    window.region.set_mode(RegionMode.CIRCLE)

    seen: list[tuple[int, int]] = []
    overlay.hover_moved.connect(lambda x, y: seen.append((x, y)))
    QTest.mouseMove(overlay, QPoint(200, 120))
    qapp.processEvents()
    assert seen


# -- the colorbar's ramp -----------------------------------------------------------


@pytest.mark.parametrize("length", [2, 16, 128, 200, 256, 512])
def test_the_colorbar_ramps_a_table_of_any_length(qapp, length):
    """The reported bug. DS9's bundled `.lut` files hold 128 colours and so
    do thirty of the Matplotlib cascade's tables; the single-bar path
    indexed `linspace(0, 255, ...)` and raised `IndexError` on every one of
    them -- from inside `display()`, before the image was drawn."""
    from ncrads9.ui.widgets.colorbar_widget import ColorbarWidget

    table = np.stack([np.linspace(0.0, 1.0, length), np.zeros(length), np.zeros(length)], axis=-1)
    entry = type("Entry", (), {"colors": table, "vmin": 0.0, "vmax": 1.0, "label": ""})()

    widget = ColorbarWidget()
    try:
        widget.resize(400, 400)
        widget.show()
        qapp.processEvents()
        widget.set_colorbars([entry])
        image = widget.colorbar_label.pixmap().toImage()
        assert not image.isNull()
        # A ramp, not a flat block: the two ends must differ.
        low = image.pixelColor(1, 5).getRgb()[0]
        high = image.pixelColor(image.width() - 2, 5).getRgb()[0]
        assert abs(high - low) > 100, f"a {length}-colour table should still ramp"
    finally:
        widget.close()


def test_an_empty_table_does_not_raise(qapp):
    from ncrads9.ui.widgets.colorbar_widget import ColorbarWidget

    entry = type("Entry", (), {"colors": np.zeros((0, 3)), "vmin": 0.0, "vmax": 1.0, "label": ""})()
    widget = ColorbarWidget()
    try:
        widget.resize(200, 200)
        widget.set_colorbars([entry])
    finally:
        widget.close()


def test_every_colormap_on_the_menu_reaches_the_picture(window, tmp_path):
    """The gate. 186 colormaps are on the Color menu; every one must change
    what is drawn, except the handful that are genuinely greyscale.

    Before the colorbar fix this failed for thirty of them -- not because
    their tables were wrong, but because drawing the *colorbar* raised and
    took the image render down with it."""
    window.display.load_fits(str(_fits(tmp_path / "sky.fits")))
    actions = window.menu_bar.colormap_actions

    def samples():
        """Several points across the image, not one.

        The middle pixel alone cannot tell `grey` from its own reverse --
        both are mid-grey there -- and a gate that cannot tell those apart
        would pass a colormap that was silently ignored.
        """
        image = window.image_viewer.image_viewer._pixmap.toImage()
        row = image.height() // 2
        return tuple(
            image.pixelColor(int(image.width() * fraction), row).getRgb()[:3]
            for fraction in (0.02, 0.25, 0.5, 0.75, 0.97)
        )

    actions["grey"].trigger()
    grey = samples()

    #: Tables that really are a plain black-to-white ramp, so rendering
    #: exactly like `grey` is the right answer for them. `h5_yarg` is one
    #: despite its name -- "yarg" is "gray" backwards, but DS9's own
    #: `h5_yarg.sao` holds `(0,0)(1,1)` on all three channels, an
    #: unreversed ramp. Our copy is byte-identical to DS9's, so this
    #: matches DS9 rather than papering over anything; `gist_yarg` is the
    #: reversed grey that the name suggests.
    greyscale = {"grey", "standard", "h5_yarg"}
    unchanged = []
    for name, action in actions.items():
        action.trigger()
        if samples() == grey and name not in greyscale:
            unchanged.append(name)
    assert unchanged == [], f"{len(unchanged)} colormaps do not change the picture"


def test_a_short_table_does_not_abort_the_render(window, tmp_path):
    """The shape of the bug, stated directly: a colormap must not be able
    to stop the image being drawn."""
    window.display.load_fits(str(_fits(tmp_path / "sky.fits")))
    window.custom_colormaps["stubby"] = Colormap("stubby", [(1.0, 0.0, 0.0), (0.0, 0.0, 1.0)])
    window.menu_bar.colormap_actions["grey"].trigger()
    before = window.image_viewer.image_viewer._pixmap.toImage()
    reference = before.pixelColor(before.width() // 2, before.height() // 2).getRgb()[:3]

    window.current_colormap = "stubby"
    window.display.display()
    after = window.image_viewer.image_viewer._pixmap.toImage()
    assert after.pixelColor(after.width() // 2, after.height() // 2).getRgb()[:3] != reference


def test_the_colormap_dialog_opens_and_previews_the_chosen_map(qapp):
    """It raised `AttributeError` on construction until M9's button-bar
    pass, and drew a grey ramp whatever was selected; both are covered
    here so neither comes back."""
    from ncrads9.ui.dialogs.colormap_dialog import ColormapDialog

    dialog = ColormapDialog()
    try:
        names = [dialog._cmap_list.item(i).text() for i in range(dialog._cmap_list.count())]
        assert "heat" in names
        dialog._cmap_list.setCurrentRow(names.index("heat"))
        image = dialog._preview_label.pixmap().toImage()
        left = image.pixelColor(2, 20).getRgb()[:3]
        right = image.pixelColor(image.width() - 3, 20).getRgb()[:3]
        assert left != right, "the preview should ramp"
        assert right[0] > right[2], "heat runs to a warm colour, not to grey"
    finally:
        dialog.close()
