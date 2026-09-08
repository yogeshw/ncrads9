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

"""Zoom-to-fit must use the viewport it is given, not a widget's own size.

Both viewer backends previously derived zoom from a widget that has not been
laid out yet, which reports a few tens of pixels before the window is shown.
On the CPU path that produced a wrong crop zoom; on the GPU path -- the default
-- it produced a near-zero zoom for the first file opened at startup.
"""

import pytest
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPixmap

from ncrads9.rendering.gl_canvas import GLCanvas
from ncrads9.ui.image_viewer import ImageViewer


class TestGLCanvasZoomToFit:
    """ncrads9/rendering/gl_canvas.py"""

    @pytest.fixture
    def canvas(self, qapp):
        canvas = GLCanvas()
        canvas._image_width, canvas._image_height = 512, 512
        return canvas

    def test_uses_the_supplied_viewport(self, canvas):
        canvas.zoom_to_fit(QSize(800, 600))
        assert canvas.zoom == pytest.approx(600 / 512)

    def test_supplied_viewport_wins_over_widget_size(self, canvas):
        canvas.zoom_to_fit(QSize(4096, 4096))
        from_widget = min(canvas.width(), canvas.height()) / 512
        assert canvas.zoom == pytest.approx(8.0)
        assert canvas.zoom != pytest.approx(from_widget)

    def test_falls_back_to_widget_size_when_omitted(self, canvas):
        canvas.zoom_to_fit()
        expected = min(canvas.width() / 512, canvas.height() / 512)
        assert canvas.zoom == pytest.approx(expected)

    def test_degenerate_viewport_is_ignored(self, canvas):
        canvas.zoom_to_fit(QSize(800, 600))
        before = canvas.zoom
        canvas.zoom_to_fit(QSize(0, 0))
        assert canvas.zoom == pytest.approx(before)

    def test_no_image_is_a_no_op(self, qapp):
        canvas = GLCanvas()
        before = canvas.zoom
        canvas.zoom_to_fit(QSize(800, 600))
        assert canvas.zoom == pytest.approx(before)

    def test_centres_the_image(self, canvas):
        canvas.zoom_to_fit(QSize(800, 600))
        assert canvas.pan_offset == (256.0, 256.0)


class TestCPUViewerZoomFit:
    """ncrads9/ui/image_viewer.py"""

    def test_uses_the_supplied_container(self, qapp):
        viewer = ImageViewer()
        viewer.set_image(QPixmap(512, 512))
        viewer.zoom_fit(QSize(800, 600))
        # The CPU path keeps a 5% margin; the GPU path does not.
        assert viewer.get_zoom() == pytest.approx(600 / 512 * 0.95)

    def test_no_image_is_a_no_op(self, qapp):
        viewer = ImageViewer()
        before = viewer.get_zoom()
        viewer.zoom_fit(QSize(800, 600))
        assert viewer.get_zoom() == pytest.approx(before)
