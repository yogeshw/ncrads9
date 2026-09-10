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

"""Composite regions: Create and Dissolve (M6-17)."""

from __future__ import annotations

import numpy as np
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QImage, QPainter, QPixmap

from ncrads9.regions.region_parser import RegionParser
from ncrads9.regions.region_renderer import RegionRenderer
from ncrads9.regions.shapes.composite import Composite


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
    frame.image_data = np.zeros((64, 64), dtype=np.float32)
    frame.regions = RegionParser().parse_string("image\ncircle(10,10,5)\nbox(20,20,6,6)\ncircle(30,30,5)\n")
    yield window
    window.close()


def _select(window, *indices: int) -> None:
    for position, region in enumerate(window.frame_manager.current_frame.regions):
        region.selected = position in indices


def test_creating_a_composite_folds_the_selection_in(main_window):
    frame = main_window.frame_manager.current_frame
    _select(main_window, 0, 1)
    main_window.menu_bar.action_composite_create.trigger()

    assert len(frame.regions) == 2
    composite = frame.regions[0]
    assert isinstance(composite, Composite)
    assert len(composite.regions) == 2


def test_a_composite_takes_the_place_of_its_first_member(main_window):
    """Folding regions up must not also bring them to the front."""
    frame = main_window.frame_manager.current_frame
    _select(main_window, 1, 2)
    main_window.menu_bar.action_composite_create.trigger()
    assert isinstance(frame.regions[1], Composite)


def test_the_new_composite_is_what_is_selected(main_window):
    frame = main_window.frame_manager.current_frame
    _select(main_window, 0, 1)
    main_window.menu_bar.action_composite_create.trigger()
    assert [region.selected for region in frame.regions] == [True, False]


def test_one_region_is_not_a_composite(main_window):
    _select(main_window, 0)
    main_window.menu_bar.action_composite_create.trigger()
    assert "two or more" in main_window.status_bar.currentMessage()
    assert len(main_window.frame_manager.current_frame.regions) == 3


def test_dissolving_puts_the_members_back(main_window):
    frame = main_window.frame_manager.current_frame
    _select(main_window, 0, 1)
    main_window.menu_bar.action_composite_create.trigger()
    main_window.menu_bar.action_composite_dissolve.trigger()

    assert len(frame.regions) == 3
    assert not any(isinstance(region, Composite) for region in frame.regions)
    assert all(region.selected for region in frame.regions[:2])


def test_dissolving_puts_them_back_where_the_composite_was(main_window):
    frame = main_window.frame_manager.current_frame
    _select(main_window, 1, 2)
    main_window.menu_bar.action_composite_create.trigger()
    main_window.menu_bar.action_composite_dissolve.trigger()
    assert [type(region).__name__ for region in frame.regions] == ["Circle", "Box", "Circle"]


def test_dissolving_something_that_is_not_a_composite_says_so(main_window):
    _select(main_window, 0)
    main_window.menu_bar.action_composite_dissolve.trigger()
    assert "composite" in main_window.status_bar.currentMessage().lower()


def test_a_composite_moves_as_one(main_window):
    frame = main_window.frame_manager.current_frame
    _select(main_window, 0, 1)
    main_window.menu_bar.action_composite_create.trigger()
    composite = frame.regions[0]
    before = [region.center for region in composite.regions]
    composite.move(5, 7)
    after = [region.center for region in composite.regions]
    assert all((b[0] + 5, b[1] + 7) == pytest.approx(a) for b, a in zip(before, after, strict=True))


def test_a_composite_draws_its_children(qapp):
    """It used to draw a four-pixel cross and nothing else."""
    regions = RegionParser().parse_string("image\ncircle(50,50,20)\nbox(50,50,30,30)\n")
    composite = Composite(regions=regions)

    def ink(drawn) -> int:
        pixmap = QPixmap(400, 400)
        pixmap.fill()
        painter = QPainter(pixmap)
        RegionRenderer().render(painter, drawn, lambda x, y: QPointF(200 + (x - 50), 200 - (y - 50)))
        painter.end()
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        buffer = image.constBits()
        buffer.setsize(image.height() * image.bytesPerLine())
        rows = np.frombuffer(buffer, dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
        canvas = rows[:, : image.width() * 3].reshape(image.height(), image.width(), 3).copy()
        return int((canvas.min(axis=2) < 250).sum())

    assert ink([composite]) > ink([]) + 100
