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

"""Every module under ncrads9/ must import.

This is deliberately cheap and deliberately broad. It exists because M1-0b
found a module that only imported by accident: catalog_table.py imported
QAction from PyQt6.QtWidgets, where it does not exist (PyQt6 moved it to
QtGui). CPython binds the names in a `from X import (a, b, c)` one at a time,
so the failure left every name *before* QAction bound and every name after it
unbound. QAction happened to sit late in the list, so the one name the module
needed at class-definition time was bound and the ImportError was swallowed by
a `try/except ImportError` that set HAS_QT = False.

Sorting the imports moved QAction second and the module stopped importing at
all. Nothing had ever exercised it, so nothing noticed either state. A test
that merely imports everything would have caught the original bug immediately.
"""

import importlib
import pathlib

import pytest

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[2] / "ncrads9"


def _module_names() -> list[str]:
    names = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        rel = path.relative_to(PACKAGE_ROOT.parent)
        name = str(rel.with_suffix("")).replace("/", ".")
        if name.endswith(".__init__"):
            name = name[: -len(".__init__")]
        if name.endswith(".__main__"):
            continue  # executing __main__ would start the app
        names.append(name)
    return names


MODULE_NAMES = _module_names()


def test_the_package_is_not_empty():
    assert len(MODULE_NAMES) > 150, MODULE_NAMES


@pytest.mark.parametrize("module_name", MODULE_NAMES)
def test_module_imports(module_name, qapp):
    """Import each module. qapp is required because many pull in PyQt6."""
    importlib.import_module(module_name)
