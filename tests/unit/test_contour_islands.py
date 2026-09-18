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
A contour around one island must not run to the next one.

The reported fault: the lowest contour level joined one island to the
island beside it. It did, by a straight line, and the cause was two
things together.

scikit-image was never declared as a dependency, so on a clean install
`from skimage import measure` failed. The caller caught *any* exception
and reached for a second routine called `find_contours_scipy`, which was
not a contour tracer: it took every pixel on the level's boundary,
anywhere in the image, in raster order, and returned them as one array.
The overlay drew that array as a single polyline, so it ran from island to
island -- most visibly at the lowest level, where the islands are largest
and the jumps between them longest.

So the gates here are about *separateness*, and the important ones run
with scikit-image made unavailable, since that is the configuration a
clean install has and the one nobody was testing.
"""

from __future__ import annotations

import sys

import numpy as np
import pytest

from ncrads9.analysis.contour import ContourGenerator, trace

#: Where the two islands sit, and the empty channel between them.
LEFT_CENTRE = 32
RIGHT_CENTRE = 96
GAP = (48, 80)


def two_islands(noise: float = 0.0, seed: int = 1) -> np.ndarray:
    """Two well-separated Gaussian sources on an empty field."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:64, 0:128]
    data = np.zeros((64, 128), dtype=np.float64)
    for centre in (LEFT_CENTRE, RIGHT_CENTRE):
        data += 10.0 * np.exp(-(((x - centre) ** 2 + (y - 32) ** 2) / (2 * 6.0**2)))
    if noise:
        data = data + rng.normal(0.0, noise, data.shape)
    return data


@pytest.fixture
def without_skimage(monkeypatch):
    """A clean install: scikit-image absent, as it was undeclared."""
    monkeypatch.setitem(sys.modules, "skimage", None)
    monkeypatch.setitem(sys.modules, "skimage.measure", None)
    with pytest.raises(ImportError):
        from skimage import measure  # noqa: F401
    return True


def _spans_both(path: np.ndarray) -> bool:
    """Whether one path reaches across the channel into both islands."""
    columns = path[:, 1]
    return bool(columns.min() < GAP[0] and columns.max() > GAP[1])


def _crosses_the_gap(path: np.ndarray) -> bool:
    """Whether any point of a path lies in the empty channel."""
    columns = path[:, 1]
    return bool(np.any((columns > GAP[0]) & (columns < GAP[1])))


# -- the regression, with and without scikit-image ---------------------------------


@pytest.mark.parametrize("noise", [0.0, 0.2])
def test_no_contour_joins_two_islands(noise):
    data = two_islands(noise=noise)
    generator = ContourGenerator(data)
    levels = generator.generate_levels(10)
    joined = []
    for level, paths in zip(levels, generator.find_contours(levels), strict=True):
        for path in paths:
            if _spans_both(path):
                joined.append(f"level {level:.4g}: one path spans both islands")
    assert joined == [], "\n".join(joined)


@pytest.mark.parametrize("noise", [0.0, 0.2])
def test_no_contour_joins_two_islands_without_skimage(without_skimage, noise):
    """The configuration the fault was reported from."""
    data = two_islands(noise=noise)
    generator = ContourGenerator(data)
    levels = generator.generate_levels(10)
    joined = []
    for level, paths in zip(levels, generator.find_contours(levels), strict=True):
        for path in paths:
            if _spans_both(path):
                joined.append(f"level {level:.4g}: one path spans both islands")
    assert joined == [], "\n".join(joined)


def test_the_lowest_drawn_level_gives_one_path_per_island(without_skimage):
    """Named for the report: it was the lowest level that showed it."""
    generator = ContourGenerator(two_islands())
    levels = generator.generate_levels(10)
    for level, paths in zip(levels, generator.find_contours(levels), strict=True):
        if not paths:
            continue
        assert len(paths) == 2, f"level {level:.4g} gave {len(paths)} paths, not one per island"
        assert not any(_crosses_the_gap(path) for path in paths)
        return
    pytest.fail("no level produced a contour at all")


def test_nothing_is_drawn_in_the_channel_between_the_islands(without_skimage):
    """Where the straight line used to be."""
    generator = ContourGenerator(two_islands())
    levels = generator.generate_levels(10)
    for paths in generator.find_contours(levels):
        for path in paths:
            assert not _crosses_the_gap(path)


# -- the tracer agrees with scikit-image -------------------------------------------


@pytest.mark.parametrize(
    ("name", "level"),
    [("clean", 2.0), ("clean", 5.0), ("clean", 8.0), ("noisy", 1.0), ("noisy", 3.0)],
)
def test_our_tracer_matches_scikit_image(name, level):
    """Which tracer runs must change the speed and nothing else."""
    measure = pytest.importorskip("skimage.measure")
    data = two_islands(noise=0.2 if name == "noisy" else 0.0)
    ours = trace(data, level)
    theirs = measure.find_contours(data, level)
    assert len(ours) == len(theirs)
    assert sum(len(path) for path in ours) == sum(len(path) for path in theirs)
    assert sorted(len(path) for path in ours) == sorted(len(path) for path in theirs)


def test_a_saddle_keeps_two_islands_that_touch_at_a_corner_apart():
    """The one cell marching squares cannot resolve on its own.

    Two blocks meeting at a single corner are two sources, not one, and
    the choice is the same one scikit-image makes by default -- which is
    why the two tracers agree on real data as well.
    """
    data = np.zeros((7, 7))
    data[1:3, 1:3] = 5.0
    data[3:5, 3:5] = 5.0
    paths = trace(data, 2.5)
    assert len(paths) == 2, "a corner touch was traced as one island"


def test_an_island_running_off_the_edge_gives_an_open_path():
    """A contour clipped by the image border cannot be closed, and joining
    its two ends would draw a line across the data."""
    y, x = np.mgrid[0:32, 0:64]
    data = 10.0 * np.exp(-(((x - 0) ** 2 + (y - 16) ** 2) / (2 * 6.0**2)))
    paths = trace(data, 2.0)
    assert paths
    for path in paths:
        assert not np.allclose(path[0], path[-1]), "an edge-clipped contour was closed"


def test_an_interior_island_gives_a_closed_path():
    data = np.zeros((16, 16))
    data[6:10, 6:10] = 5.0
    paths = trace(data, 2.5)
    assert len(paths) == 1
    assert np.allclose(paths[0][0], paths[0][-1]), "an interior contour was left open"


def test_a_level_equal_to_the_data_still_contours():
    """`>=`, not `>`: a level typed to match the data exactly should draw
    something rather than nothing."""
    data = np.zeros((16, 16))
    data[6:10, 6:10] = 5.0
    assert trace(data, 5.0)


def test_blank_pixels_are_not_contoured_through():
    """A NaN says nothing about where the level lies, so the cells around
    it are left alone rather than joined across the gap."""
    data = np.zeros((16, 32))
    data[4:12, 2:8] = 5.0
    data[4:12, 24:30] = 5.0
    data[:, 12:20] = np.nan
    paths = trace(data, 2.5)
    assert paths
    for path in paths:
        assert not np.isnan(path).any()
        columns = path[:, 1]
        assert not (columns.min() < 10 and columns.max() > 22)


def test_an_empty_or_degenerate_array_is_not_an_error():
    assert trace(np.zeros((0, 0)), 1.0) == []
    assert trace(np.zeros((1, 5)), 1.0) == []
    assert trace(np.zeros((5, 5)), 1.0) == []


def test_a_single_level_lands_where_the_whole_set_does():
    """`get_contour_at_level` returned the *blocked* image's coordinates
    while `find_contours` returned the original's, so the same level came
    back in two different places depending on which was asked."""
    generator = ContourGenerator(two_islands(), method="block", smoothness=4)
    one = generator.get_contour_at_level(5.0)
    whole = generator.find_contours([5.0])[0]
    assert len(one) == len(whole)
    for mine, theirs in zip(sorted(one, key=len), sorted(whole, key=len), strict=True):
        assert np.allclose(mine, theirs)


def test_a_blocked_contour_lands_on_its_island():
    """The scaling back, checked against where the sources actually are."""
    generator = ContourGenerator(two_islands(), method="block", smoothness=4)
    paths = generator.find_contours([5.0])[0]
    assert len(paths) == 2
    centres = sorted(float(path[:, 1].mean()) for path in paths)
    assert abs(centres[0] - LEFT_CENTRE) < 4, centres
    assert abs(centres[1] - RIGHT_CENTRE) < 4, centres


# -- through the application -------------------------------------------------------


@pytest.fixture
def window(qapp, monkeypatch):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    real = Preferences.get
    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else real(self, key, default),
    )
    made = MainWindow()
    made._rebuild_image_viewer(False)
    frame = made.frame_manager.current_frame
    frame.image_data = two_islands().astype(np.float32)
    frame.original_image_data = frame.image_data
    yield made
    made.close()


def test_the_application_draws_separate_contours(window, without_skimage):
    """End to end, in the configuration that was broken: the paths the
    overlay is handed must not span both islands."""
    window.analysis.set_contours(True)
    paths = window._contour_paths
    assert paths, "no contours were produced"
    drawn = 0
    for level_paths in paths:
        for path in level_paths:
            # The overlay's paths are (x, y), so the columns are column 0.
            columns = path[:, 0]
            assert not (columns.min() < GAP[0] and columns.max() > GAP[1])
            drawn += 1
    assert drawn >= 2, "expected at least one contour per island"


def test_the_contour_failure_is_no_longer_swallowed(window, monkeypatch):
    """A real failure in the tracer must reach somebody rather than turning
    into a different, silently wrong contour."""
    from ncrads9.analysis import contour as contour_module

    def explode(_data, _level):
        raise RuntimeError("tracer broke")

    window.analysis.set_contours(True)
    monkeypatch.setattr(contour_module, "_paths", explode)
    with pytest.raises(RuntimeError):
        window.analysis.update_contours()


def test_scikit_image_is_a_declared_dependency():
    """The root cause. The tracer it provides was the primary path while
    nothing required it to be installed."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    assert "scikit-image" in (root / "pyproject.toml").read_text()
