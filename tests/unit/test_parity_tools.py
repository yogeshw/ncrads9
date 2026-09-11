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
import json
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

    def test_no_menu_action_is_unconnected(self, qapp):
        """Every menu entry must reach a handler. This keeps §3.8 honest.

        The ceiling was 3 until M2-14 wired Cut, Copy and Paste; it is now
        zero and must stay there. A new menu entry added without wiring fails
        here, which is how M2 caught itself unwiring five whole menus while
        moving a block of connect() calls around.
        """
        lines = _load("dump_menus").collect(annotate=True)
        unconnected = [line for line in lines if line.endswith("|UNCONNECTED")]
        assert unconnected == [], unconnected


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

    def test_the_xpa_example_corpus_is_committed_and_current(self):
        """C-6's corpus is generated from DS9's reference and committed, so
        the tests do not need the DS9 checkout. Regenerating it when the
        checkout is there is how a change in DS9's documentation reaches
        the conformance suite."""
        corpus = REPO_ROOT / "docs" / "parity" / "ds9_xpa_examples.json"
        assert corpus.is_file(), "run python tools/import_ds9_xpa_examples.py"
        built = json.loads(corpus.read_text())
        assert built["examples"] >= 1400
        assert "SAOImageDS9" in built["source"], "a copied file records where it came from"

        reference = REPO_ROOT / ".tmp_sao_ds9" / "ds9" / "doc" / "ref" / "xpa.html"
        if not reference.is_file():
            pytest.skip("the DS9 checkout is not here; run tools/fetch_ds9.sh to check freshness")
        assert _load("import_ds9_xpa_examples").main(["--check"]) == 0

    def test_menu_diff_passes_a_floor_it_meets(self, capsys):
        """C-1's ratchet. Without it parity is only reported, so a menu
        entry lost in a refactor goes unnoticed until someone reads the
        summary; `check.sh` and CI both pass `--minimum`."""
        assert _load("menu_diff").main(["--summary", "--minimum", "1"]) == 0
        capsys.readouterr()

    def test_menu_diff_fails_a_floor_it_misses(self, capsys):
        assert _load("menu_diff").main(["--minimum", "100"]) == 1
        captured = capsys.readouterr()
        assert "below the 100.0% floor" in captured.err
        assert "--missing" in captured.err, "it has to say how to find what went"

    def test_the_floor_in_force_is_the_parity_we_have(self):
        """The floor `check.sh` and CI use, checked here so the two cannot
        drift apart: a floor above what we have would fail every build, and
        one far below would ratchet nothing."""
        import re

        floor = re.search(
            r"menu_diff\.py --summary --minimum (\d+)", (REPO_ROOT / "tools/check.sh").read_text()
        )
        assert floor, "check.sh should pass a parity floor"
        workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text()
        assert f"--minimum {floor.group(1)}" in workflow, "CI and check.sh should agree"
        assert _load("menu_diff").main(["--minimum", floor.group(1)]) == 0
