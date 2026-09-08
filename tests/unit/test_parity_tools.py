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

"""Tests for the menu-parity tooling in tools/.

These guard the instrument itself: if the extractors silently stop finding
entries, the parity numbers in PLAN.md quietly become fiction.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPO_ROOT / "tools"
PARITY = REPO_ROOT / "docs" / "parity"
DS9_LIBRARY = REPO_ROOT / ".tmp_sao_ds9" / "ds9" / "library"

needs_ds9 = pytest.mark.skipif(
    not DS9_LIBRARY.is_dir(),
    reason="SAOImageDS9 reference checkout not present at .tmp_sao_ds9/",
)


def _load(name: str):
    """Import a tools/ script by path."""
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TestDS9MenuTree:
    """tools/ds9_menu_tree.py"""

    @needs_ds9
    def test_extracts_the_expected_order_of_magnitude(self):
        lines = _load("ds9_menu_tree").extract(DS9_LIBRARY.parent)
        entries = [line for line in lines if not line.startswith("#")]
        real = [line for line in entries if not line.endswith("|---")]
        # 526 at the time of writing; a wide band tolerates DS9 upgrades but
        # still catches an extractor that has stopped matching.
        assert 450 <= len(real) <= 650, len(real)

    @needs_ds9
    def test_resolves_composite_labels(self):
        """Labels built from a translated word plus a literal must resolve."""
        lines = _load("ds9_menu_tree").extract(DS9_LIBRARY.parent)
        joined = "\n".join(lines)
        for label in ("Zoom 1/32", "Bin 256", "0 Degrees", "Invert XY", "1 Second"):
            assert f"|{label}" in joined, label

    @needs_ds9
    def test_finds_every_top_level_menu(self):
        lines = _load("ds9_menu_tree").extract(DS9_LIBRARY.parent)
        paths = {line.split("|")[0] for line in lines if "|" in line}
        for menu in (
            ".file",
            ".edit",
            ".view",
            ".frame",
            ".bin",
            ".zoom",
            ".scale",
            ".color",
            ".region",
            ".illustrate",
            ".analysis",
        ):
            assert menu in paths, menu

    @needs_ds9
    def test_dynamic_entries_stay_rare(self):
        """Most DS9 labels are literal; a spike means the regexes regressed."""
        lines = _load("ds9_menu_tree").extract(DS9_LIBRARY.parent)
        dynamic = [line for line in lines if line.endswith("<dynamic>")]
        assert len(dynamic) <= 10, dynamic

    def test_missing_checkout_is_a_clear_error(self, tmp_path):
        with pytest.raises(SystemExit, match="not found"):
            _load("ds9_menu_tree").extract(tmp_path / "nope")


class TestDumpMenus:
    """tools/dump_menus.py"""

    def test_collects_our_menu_tree(self, qapp):
        lines = _load("dump_menus").collect()
        entries = [line for line in lines if not line.startswith("#")]
        real = [line for line in entries if not line.endswith("|---")]
        assert len(real) > 200, len(real)

    def test_emits_ds9_style_paths_and_kinds(self, qapp):
        lines = [line for line in _load("dump_menus").collect() if "|" in line]
        paths = {line.split("|")[0] for line in lines}
        kinds = {line.split("|")[1] for line in lines}
        assert ".file" in paths
        assert ".frame.match.frame" in paths
        assert kinds <= {"command", "cascade", "checkbutton", "radiobutton", "separator"}

    def test_strips_mnemonics_and_ellipses(self, qapp):
        labels = [line.split("|")[2] for line in _load("dump_menus").collect() if line.count("|") >= 2]
        assert not [label for label in labels if "&" in label]
        assert not [label for label in labels if label.endswith("...")]

    def test_connected_annotation_flags_dead_actions(self, qapp):
        """The annotation is what keeps PLAN.md 3.8 honest."""
        lines = _load("dump_menus").collect(annotate=True)
        unconnected = [line for line in lines if line.endswith("|UNCONNECTED")]
        # Cut/Copy/Paste are the known dead actions (TODO.md M2-14). If this
        # grows, a new menu entry was added without wiring it up.
        assert len(unconnected) <= 3, unconnected


class TestSnapshots:
    """The committed snapshots under docs/parity/."""

    def test_both_snapshots_are_committed(self):
        assert (PARITY / "ds9_menus.txt").is_file()
        assert (PARITY / "ncrads9_menus.txt").is_file()

    def test_our_snapshot_is_current(self, qapp):
        """CI regenerates and diffs this; fail early and locally instead."""
        expected = _load("dump_menus").collect()
        committed = [
            line
            for line in (PARITY / "ncrads9_menus.txt").read_text().splitlines()
            if line and not line.startswith("#")
        ]
        assert committed == [line for line in expected if not line.startswith("#")], (
            "docs/parity/ncrads9_menus.txt is stale. Regenerate with:\n"
            "  python tools/dump_menus.py --output docs/parity/ncrads9_menus.txt"
        )

    def test_menu_diff_reports_a_parity_summary(self, capsys):
        assert _load("menu_diff").main(["--summary"]) == 0
        out = capsys.readouterr().out
        assert "TOTAL" in out
        assert "parity" in out
