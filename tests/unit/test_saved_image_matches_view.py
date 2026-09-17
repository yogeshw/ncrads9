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
Save Image, Export and Print write what is on the screen.

`current_pixmap` used to re-render the array: it reproduced the *data* --
scale, limits, colormap -- at the file's own resolution and nothing else.
So a saved image had no zoom, no pan, no rotation, and none of the
overlays: no regions, no contours, no coordinate grid, no catalogue
symbols, no illustrations. What you saved was never what you were
looking at, which is the one thing Save Image is for.

The overlays are child widgets of the viewer, so the view is grabbed
rather than redrawn -- there is no second drawing path to keep in step
with the first, which is how they came to be missing.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

SIZE = 64


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

    rows, columns = np.indices((SIZE, SIZE))
    header = fits.Header(
        {
            "CRPIX1": SIZE // 2,
            "CRPIX2": SIZE // 2,
            "CRVAL1": 202.48,
            "CRVAL2": 47.21,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
        }
    )
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32), header=header).writeto(path)

    made = MainWindow()
    made._rebuild_image_viewer(False)
    # Sized but not shown. A grab needs a laid-out viewport, not a mapped
    # window, and `show()` here destabilised the *theme* tests later in
    # the run: applying a theme restyles every live widget, and a
    # previously-shown window's tree makes that crash Qt offscreen --
    # which `apply_theme` already warns about in its own docstring.
    made.resize(900, 700)
    made.scroll_area.resize(880, 400)
    qapp.processEvents()
    made.display.load_fits(str(path))
    qapp.processEvents()
    yield made
    # Destroyed, not merely closed. `close()` leaves the widget tree
    # alive, and applying a theme walks *every* live widget -- so a
    # window left behind by one test crashes a later one that switches
    # theme. One leaked MainWindow per test is the real fault here.
    made.close()
    made.deleteLater()
    qapp.processEvents()


def _image(window):
    pixmap = window.file.current_pixmap()
    assert pixmap is not None and not pixmap.isNull()
    return pixmap.toImage()


def _colours(image, step: int = 4) -> set[int]:
    return {image.pixel(x, y) for y in range(0, image.height(), step) for x in range(0, image.width(), step)}


# -- the view, not the array -------------------------------------------------------


def test_the_saved_image_is_the_size_of_the_view(window):
    """Not the size of the *file*. A 64-pixel image saved at 64x64 whatever
    the zoom is the symptom that was reported."""
    viewport = window.scroll_area.viewport()
    image = _image(window)
    assert (image.width(), image.height()) == (viewport.width(), viewport.height())
    assert image.width() != SIZE, "saving the array's own size is the bug"


def test_zooming_changes_what_is_saved(window, qapp):
    window.zoom.set_zoom(1.0)
    qapp.processEvents()
    at_one = _image(window)

    window.zoom.set_zoom(8.0)
    qapp.processEvents()
    at_eight = _image(window)

    assert at_one != at_eight, "the zoom must reach the saved image"


def test_panning_changes_what_is_saved(window, qapp):
    window.zoom.set_zoom(8.0)
    qapp.processEvents()
    before = _image(window)

    bar = window.scroll_area.horizontalScrollBar()
    if bar.maximum() <= bar.minimum():
        pytest.skip("the view does not scroll at this size")
    bar.setValue(bar.maximum())
    qapp.processEvents()
    assert _image(window) != before


def test_rotating_changes_what_is_saved(window, qapp):
    before = _image(window)
    window.zoom.set_rotation(90.0)
    qapp.processEvents()
    assert _image(window) != before


# -- the overlays ------------------------------------------------------------------


def test_a_region_is_saved_with_the_image(window, qapp):
    """The reported omission. A red circle has to be *in* the picture."""
    from ncrads9.regions.shapes.circle import Circle

    frame = window.frame_manager.current_frame
    circle = Circle(center=(32.0, 32.0), radius=15.0)
    circle.color = "red"
    frame.regions = [circle]
    window.region.show_frame_regions(frame)
    qapp.processEvents()

    assert _red_pixels(_image(window)) > 5, "the region should be drawn into the saved image"


def test_contours_are_saved_with_the_image(window, qapp):
    before = _image(window)
    window.menu_bar.action_contours.trigger()
    qapp.processEvents()
    assert _image(window) != before


def test_the_coordinate_grid_is_saved_with_the_image(window, qapp):
    before = _image(window)
    window.menu_bar.action_coordinate_grid.trigger()
    qapp.processEvents()
    assert _image(window) != before


def _red_pixels(image) -> int:
    """How much of the picture is the red an overlay was drawn in.

    Every pixel, not a sample: an overlay draws a one-pixel line, and a
    sampling stride walks straight over it.
    """
    return sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).red() > 150
        and image.pixelColor(x, y).green() < 90
        and image.pixelColor(x, y).blue() < 90
    )


def test_an_illustration_is_saved_with_the_image(window, qapp):
    """The illustrate layer is another child overlay, so it comes along
    with the rest -- which is the point of grabbing rather than redrawing.

    Counted rather than compared: "the picture changed" would also pass if
    something else had moved, and what is being claimed is that the
    illustration is *in* it.
    """
    from ncrads9.illustrate.elements import Circle as Illustration
    from ncrads9.illustrate.elements import Style

    assert _red_pixels(_image(window)) == 0, "nothing red before"

    window.illustrate.layer.add(Illustration(x=200.0, y=100.0, radius=40.0, style=Style(color="red")))
    # Through the controller, which points the overlay at the layer and
    # asks it to repaint.
    window.illustrate.attach()
    window.illustrate.refresh()
    qapp.processEvents()

    assert _red_pixels(_image(window)) > 5


# -- the overlays are the size of the viewer -------------------------------------


def test_the_overlays_track_the_viewer(window, qapp):
    """Found while chasing the save: *all four* overlays sat at the
    widget's 100x100 minimum while the viewer was eight hundred pixels
    wide, so regions, contours, catalogue symbols and illustrations were
    clipped to that corner -- on screen as well as in a saved image.

    The overlays are sized from the inner viewer's geometry, and the
    inner viewer resizes *itself* when the image or the zoom changes;
    nothing told the wrapper until the window was next resized.
    """
    viewer = window.image_viewer
    inner = viewer.image_viewer.size()
    assert inner.width() > 100, "the viewer should have grown to hold the image"
    for name in ("region_overlay", "contour_overlay", "catalog_overlay", "illustrate_overlay"):
        assert getattr(viewer, name).size() == inner, name


def test_the_overlays_follow_a_zoom(window, qapp):
    window.zoom.set_zoom(6.0)
    qapp.processEvents()
    viewer = window.image_viewer
    for name in ("region_overlay", "contour_overlay", "catalog_overlay", "illustrate_overlay"):
        assert getattr(viewer, name).size() == viewer.image_viewer.size(), name


# -- what is written to disk -------------------------------------------------------


@pytest.mark.parametrize("suffix", ["png", "jpeg", "tiff"])
def test_save_image_writes_the_view(window, qapp, tmp_path, monkeypatch, suffix):
    """End to end: the file on disk is the size of the view, not the array."""
    from PyQt6.QtWidgets import QFileDialog

    target = tmp_path / f"shot.{suffix}"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
    window.zoom.set_zoom(4.0)
    qapp.processEvents()

    window.file.save_image(suffix)
    assert target.is_file() and target.stat().st_size > 0

    from PyQt6.QtGui import QImage

    written = QImage(str(target))
    assert not written.isNull()
    viewport = window.scroll_area.viewport()
    assert (written.width(), written.height()) == (viewport.width(), viewport.height())


def test_the_xpa_saveimage_point_writes_the_view(window, qapp, tmp_path):
    from PyQt6.QtGui import QImage

    from ncrads9.communication.xpa.xpa_commands import XPACommands

    target = tmp_path / "xpa.png"
    window.zoom.set_zoom(2.0)
    qapp.processEvents()
    reply = XPACommands(window).handle("saveimage", {"args": [str(target)]})
    assert reply["status"] == "ok", reply.get("message")

    written = QImage(str(target))
    viewport = window.scroll_area.viewport()
    assert (written.width(), written.height()) == (viewport.width(), viewport.height())


# -- the fallback ------------------------------------------------------------------


def test_a_window_that_was_never_shown_still_saves_something(qapp, tmp_path, monkeypatch):
    """A grab needs a viewport. Without one -- a window built and never
    shown, which is how the printing tests drive it -- the array is
    rendered instead. Poorer, since it carries no overlays, but not
    nothing."""
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    path = tmp_path / "unshown.fits"
    fits.PrimaryHDU(data=np.arange(SIZE * SIZE, dtype=np.float32).reshape(SIZE, SIZE)).writeto(path)

    made = MainWindow()
    made._rebuild_image_viewer(False)
    made.display.load_fits(str(path))
    try:
        pixmap = made.file.current_pixmap()
        assert pixmap is not None and not pixmap.isNull()
    finally:
        made.close()


def test_no_image_means_no_pixmap(qapp, tmp_path, monkeypatch):
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    made = MainWindow()
    made._rebuild_image_viewer(False)
    try:
        assert made.file.current_pixmap() is None
    finally:
        made.close()


def test_a_flat_grab_is_recognised_as_a_failure():
    """The guard for the OpenGL path, where a driver can hand back an
    empty black rectangle. One flat colour is not a picture of anything."""
    from PyQt6.QtGui import QColor, QPixmap

    from ncrads9.ui.controllers.file import FileController

    blank = QPixmap(40, 40)
    blank.fill(QColor("black"))
    assert FileController._is_blank(blank) is True

    painted = QPixmap(40, 40)
    painted.fill(QColor("black"))
    from PyQt6.QtGui import QPainter

    painter = QPainter(painted)
    painter.fillRect(0, 0, 20, 40, QColor("white"))
    painter.end()
    assert FileController._is_blank(painted) is False
