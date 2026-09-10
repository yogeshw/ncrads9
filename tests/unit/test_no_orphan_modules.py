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

"""No new orphan modules.

PLAN.md §3.1 found 116 of 191 modules unreachable from `ncrads9.app` -- more
than half the package was code the application never ran, much of it a
skeleton or a second implementation of something the UI already did inline.
M1 brought that down; this test stops it climbing back.

Every module that is still unreachable has to be named in `PENDING_ADOPTION`
below, together with the milestone that adopts or deletes it. Adding a module
without touching that list fails the test, which forces the choice -- adopt,
delete, or defer with a reason -- to be made deliberately rather than by
accident.

See `docs/parity/skeletons.md` for what each pending module needs.
"""

import ast
import pathlib

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parents[2] / "ncrads9"

#: Where the application starts. Anything these cannot reach is an orphan.
ENTRY_POINTS = ("ncrads9.app", "ncrads9.__main__")

#: Unreachable modules, mapped to the milestone that resolves each.
#:
#: A module here is not necessarily dead: several are complete and correct but
#: not yet wired to a UI that can reach them (the coordinate helpers, the io
#: writers, the theme definitions). Others are skeletons. `skeletons.md` says
#: which is which.
PENDING_ADOPTION: dict[str, str] = {
    # M8 -- catalogs, image servers, VO.
    # Its `get_images` is the SDSS image backend M8-17 wires up; its
    # catalogue queries go through VizieR like every other CDS catalogue.
    "catalogs.sdss": "M8-17",
    # M9 -- remaining subsystems.
    "communication.iis.iis_server": "M9-29",
    # M4 -- FITS coverage.
    # A save dialog with a format combo, duplicating QFileDialog's filter.
    # DS9 puts each format on its own `Save as` entry and so does M4, so
    # nothing needs this. Delete, not adopt.
    "ui.dialogs.save_dialog": "delete -- superseded by the Save as submenu",
    # Widgets with no host yet.
    "ui.widgets.region_list": "M6-15",
    "ui.widgets.color_picker": "M6-10",
    "ui.widgets.scale_widget": "M5-8",
    "ui.widgets.spinbox_slider": "M5-8",
    # Known broken as well as unreachable -- see skeletons.md.
    "colormaps.colorbar_widget": "M5-12 (PyQt5-era code, or delete)",
    # Utilities nothing calls yet.
    "utils.math_utils": "M5-1",
    # Was expected to load the buttonbar's icons. DS9's buttonbar is text,
    # so M3-3's is too, and this has no caller until the icon bars land.
    "utils.resources": "M9-24",
    "utils.threading": "M8-13",
}


def _module_name(path: pathlib.Path) -> str:
    name = str(path.relative_to(PACKAGE.parent).with_suffix("")).replace("/", ".")
    return name[: -len(".__init__")] if name.endswith(".__init__") else name


def _import_graph() -> tuple[dict[str, pathlib.Path], dict[str, set[str]]]:
    """Map every module to the ncrads9 modules it imports."""
    modules = {_module_name(p): p for p in PACKAGE.rglob("*.py")}
    edges: dict[str, set[str]] = {}

    for name, path in modules.items():
        targets: set[str] = set()
        tree = ast.parse(path.read_text())
        parts = name.split(".")
        # A package's __init__ resolves relative imports against itself; a
        # plain module resolves them against its parent package.
        base_package = parts if path.name == "__init__.py" else parts[:-1]

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    trimmed = (
                        base_package[: len(base_package) - (node.level - 1)]
                        if node.level > 1
                        else base_package
                    )
                    target = ".".join([*trimmed, *([node.module] if node.module else [])])
                else:
                    target = node.module or ""
                if target.startswith("ncrads9"):
                    targets.add(target)
                    targets.update(f"{target}.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.Import):
                targets.update(a.name for a in node.names if a.name.startswith("ncrads9"))
        edges[name] = targets

    return modules, edges


def _reachable(modules: dict[str, pathlib.Path], edges: dict[str, set[str]]) -> set[str]:
    """Modules reachable from the entry points, following imports."""
    seen: set[str] = set()
    stack = [entry for entry in ENTRY_POINTS if entry in modules]

    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        for target in edges.get(name, ()):
            # `from pkg.mod import Thing` records both `pkg.mod` and
            # `pkg.mod.Thing`; only the former is a module.
            if target in modules:
                stack.append(target)
            else:
                parent = target.rsplit(".", 1)[0]
                if parent in modules:
                    stack.append(parent)
    return seen


def _orphans() -> set[str]:
    """Unreachable modules, excluding package facades.

    A package's `__init__.py` is skipped: the application imports submodules
    directly (`from ..regions.region_parser import RegionParser`), so the
    facades are never imported even when everything they re-export is in use.
    They are the public API surface, not dead code.
    """
    modules, edges = _import_graph()
    reachable = _reachable(modules, edges)
    return {name for name in set(modules) - reachable if modules[name].name != "__init__.py"}


ORPHANS = _orphans()


def test_entry_points_exist():
    modules, _ = _import_graph()
    for entry in ENTRY_POINTS:
        assert entry in modules, entry


def test_the_graph_walk_finds_something():
    """Guard against the analysis silently returning nothing."""
    modules, edges = _import_graph()
    reachable = _reachable(modules, edges)
    assert len(reachable) > 50, len(reachable)
    assert "ncrads9.ui.main_window" in reachable
    assert "ncrads9.regions.region_parser" in reachable


def test_no_unlisted_orphan_modules():
    """Every unreachable module must name the milestone that resolves it."""
    unlisted = sorted(name.removeprefix("ncrads9.") for name in ORPHANS)
    unlisted = [name for name in unlisted if name not in PENDING_ADOPTION]
    assert not unlisted, (
        "These modules are unreachable from ncrads9.app and not listed in "
        "PENDING_ADOPTION:\n  "
        + "\n  ".join(unlisted)
        + "\n\nEither wire the module up, delete it, or add it to "
        "PENDING_ADOPTION with the milestone that will."
    )


def test_pending_list_has_no_stale_entries():
    """A module that got adopted must be removed from PENDING_ADOPTION."""
    orphan_names = {name.removeprefix("ncrads9.") for name in ORPHANS}
    adopted = sorted(set(PENDING_ADOPTION) - orphan_names)
    assert not adopted, (
        "These modules are now reachable, so they should be removed from "
        "PENDING_ADOPTION:\n  " + "\n  ".join(adopted)
    )


@pytest.mark.parametrize("module", sorted(PENDING_ADOPTION))
def test_pending_modules_exist(module):
    """PENDING_ADOPTION must not accumulate names of deleted files."""
    assert (PACKAGE / f"{module.replace('.', '/')}.py").is_file(), module


def test_orphan_count_does_not_grow():
    """A ratchet on the headline number from PLAN.md §3.1.

    M1 brought the orphan count down from 116 to 71, M3 to 60, M4 to 56 and
    M6 to 48 -- the last by making every shape DS9 documents parseable, which
    reached eight shape modules at once. Raise this ceiling only
    when a milestone deliberately adds an unreachable module -- never to make
    a failing run pass.
    """
    assert len(ORPHANS) <= 48, (
        f"{len(ORPHANS)} orphan modules; the M6 baseline is 48. " "New unreachable code needs a reason."
    )
