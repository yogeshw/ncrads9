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


"""DS9's bundled colour tables, and the parsers that read them."""

from __future__ import annotations

import numpy as np
import pytest

from ncrads9.colormaps.bundled import (
    BUNDLED,
    CATEGORIES,
    DATA_DIRECTORY,
    USER_CATEGORY,
    available,
    category_of,
    colormap_label,
    load,
    path_of,
)
from ncrads9.colormaps.sao_parser import parse_sao_file

#: How many tables are bundled, after dropping the four that duplicate
#: NCRADS9 built-ins. See `colormaps/data/README.md`.
EXPECTED_BUNDLED = 164


def test_ds9s_ten_cascades_are_all_present():
    assert list(CATEGORIES) == [
        "h5utils",
        "Matplotlib Uniform",
        "Matplotlib Sequential",
        "Matplotlib Diverging",
        "Matplotlib Cyclic",
        "Cubehelix",
        "Gist",
        "Topographic",
        "Scientific Colour Maps",
        "Solar Colormaps",
    ]


def test_every_bundled_name_has_a_file():
    assert len(BUNDLED) == EXPECTED_BUNDLED
    assert len(available()) == EXPECTED_BUNDLED


def test_no_name_is_in_two_cascades():
    counts: dict[str, int] = {}
    for names in CATEGORIES.values():
        for name in names:
            counts[name] = counts.get(name, 0) + 1
    assert [name for name, count in counts.items() if count > 1] == []


def test_the_data_directory_holds_only_tables_and_its_readme():
    unexpected = [
        path.name
        for path in DATA_DIRECTORY.iterdir()
        if path.suffix.lower() not in (".sao", ".lut") and path.name != "README.md"
    ]
    assert unexpected == []


def test_the_four_duplicated_builtins_are_not_bundled():
    """One name resolving to two sources is a bug waiting to happen."""
    for name in ("viridis", "inferno", "magma", "plasma"):
        assert path_of(name) is None
        assert name not in BUNDLED


def test_every_table_loads_and_is_not_flat():
    """A parser that silently returns one colour is the failure to catch."""
    flat = []
    for name in sorted(BUNDLED):
        colormap = load(name)
        assert colormap is not None, name
        assert colormap.colors.shape[1] == 3, name
        assert colormap.colors.shape[0] >= 2, name
        assert np.isfinite(colormap.colors).all(), name
        assert colormap.colors.min() >= 0.0 and colormap.colors.max() <= 1.0, name
        if np.allclose(colormap.colors, colormap.colors[0]):
            flat.append(name)
    assert flat == []


def test_loading_is_cached():
    assert load("scm_broc") is load("scm_broc")


def test_an_unknown_name_loads_to_none():
    assert load("no_such_colormap") is None
    assert path_of("no_such_colormap") is None


def test_category_of_finds_the_cascade():
    assert category_of("scm_broc") == "Scientific Colour Maps"
    assert category_of("h5_jet") == "h5utils"
    assert category_of("no_such_colormap") is None


@pytest.mark.parametrize(
    ("name", "label"),
    [
        ("scm_broc", "broc"),
        ("h5_jet", "jet"),
        ("mpl_RdYlBu", "RdYlBu"),
        ("gist_heat", "heat"),
        ("solar_soho_171", "soho 171"),
        ("cubehelix0", "cubehelix0"),
        ("tpglarf", "tpglarf"),
    ],
)
def test_labels_drop_the_family_prefix(name, label):
    assert colormap_label(name) == label


def test_the_user_cascade_is_named_as_ds9_names_it():
    assert USER_CATEGORY == "User"
    assert USER_CATEGORY not in CATEGORIES


# -- the .sao parser ---------------------------------------------------------


def test_sao_control_points_all_on_one_line():
    """DS9 writes a whole channel on one line, hundreds of pairs of it.

    The parser used to strip the punctuation and take the first two numbers,
    which gave one control point per channel and so a flat colour for every
    one of DS9's own .sao files -- and it did that without raising.
    """
    colormap = parse_sao_file(DATA_DIRECTORY / "gist_heat.sao")
    assert colormap.colors.shape == (256, 3)
    assert not np.allclose(colormap.colors, colormap.colors[0])


def test_gist_heat_runs_black_to_white():
    """A named table with a known appearance, as an end-to-end check."""
    colours = parse_sao_file(DATA_DIRECTORY / "gist_heat.sao").colors
    assert colours[0].tolist() == pytest.approx([0.0, 0.0, 0.0], abs=0.01)
    assert colours[-1].tolist() == pytest.approx([1.0, 1.0, 1.0], abs=0.02)
    # Red rises first, then green, then blue: that is what makes it a heat
    # table rather than a grey one.
    quarter, half, three_quarters = colours[64], colours[128], colours[192]
    assert quarter[0] > quarter[1] >= quarter[2]
    assert half[0] > half[1] >= half[2]
    assert three_quarters[0] >= three_quarters[1] > three_quarters[2]


def test_h5_jet_runs_blue_to_red():
    colours = parse_sao_file(DATA_DIRECTORY / "h5_jet.sao").colors
    assert colours[0][2] > colours[0][0]
    assert colours[-1][0] > colours[-1][2]


def test_a_grey_table_is_monotonic_and_neutral():
    """h5utils' gray runs white to black, so only monotonicity is asserted."""
    colours = parse_sao_file(DATA_DIRECTORY / "h5_gray.sao").colors
    steps = np.diff(colours[:, 0])
    assert np.all(steps <= 1e-6) or np.all(steps >= -1e-6)
    # Neutral means the three channels agree at every step.
    assert colours[:, 0].tolist() == pytest.approx(colours[:, 1].tolist(), abs=1e-6)
    assert colours[:, 0].tolist() == pytest.approx(colours[:, 2].tolist(), abs=1e-6)


def test_the_pseudocolor_line_is_not_read_as_a_channel(tmp_path):
    """DS9 writes the table's class on a line of its own before the channels."""
    path = tmp_path / "tiny.sao"
    path.write_text("# comment\nPSEUDOCOLOR\nRED:\n(0,0)(1,1)\nGREEN:\n(0,0)(1,0.5)\nBLUE:\n(0,1)(1,0)\n")
    colours = parse_sao_file(path).colors
    assert colours[0].tolist() == pytest.approx([0.0, 0.0, 1.0])
    assert colours[-1].tolist() == pytest.approx([1.0, 0.5, 0.0])


def test_one_point_per_line_is_still_accepted(tmp_path):
    """The format the parser was originally written for."""
    path = tmp_path / "perline.sao"
    path.write_text("RED:\n0 0\n1 1\nGREEN:\n0,0\n1,1\nBLUE:\n(0, 0)\n(1, 1)\n")
    colours = parse_sao_file(path).colors
    assert colours[0].tolist() == pytest.approx([0.0, 0.0, 0.0])
    assert colours[-1].tolist() == pytest.approx([1.0, 1.0, 1.0])


# -- resolution through the Color controller ---------------------------------


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
    yield window
    window.close()


def test_every_cascade_entry_is_selectable(main_window):
    """A menu entry that cannot be applied is worse than no entry.

    The menu registers its actions under a lowercased key, and eighteen of
    DS9's files are mixed-case (`mpl_Greys`, `scm_batlowK`), so the lookup
    has to ignore case at both ends.
    """
    for names in CATEGORIES.values():
        for name in names:
            assert name.lower() in main_window.menu_bar.colormap_actions, name
            assert main_window.color.colormap(name) is not None, name


def test_the_controller_resolves_a_bundled_name(main_window):
    colormap = main_window.color.colormap("scm_broc")
    assert colormap.colors.shape[1] == 3


def test_a_builtin_wins_over_a_bundled_file(main_window):
    """`grey` is a built-in; nothing bundled should shadow it."""
    assert main_window.color.colormap("grey") is not None


def test_selecting_a_bundled_colormap_sticks(main_window):
    import numpy as np

    frame = main_window.frame_manager.current_frame
    frame.image_data = np.arange(64, dtype=np.float32).reshape(8, 8)
    frame.original_image_data = frame.image_data

    main_window.menu_bar.colormap_actions["gist_heat"].trigger()
    assert main_window.current_colormap == "gist_heat"
    assert main_window.menu_bar.colormap_actions["gist_heat"].isChecked()


def test_an_unknown_colormap_is_reported(main_window):
    main_window.color.set_colormap("nonesuch")
    assert "Unsupported colormap" in main_window.status_bar.currentMessage()


def test_the_available_list_covers_the_bundled_ones(main_window):
    offered = set(main_window.color.available_colormaps())
    assert {name.lower() for name in BUNDLED} <= offered


def test_names_resolve_whatever_their_case():
    assert path_of("MPL_GREYS") == path_of("mpl_Greys")
    assert load("mpl_greys") is not None
    assert load("mpl_Greys") is not None
