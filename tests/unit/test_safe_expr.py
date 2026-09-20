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

"""The filter sandbox, and the escape it was built to stop.

A catalogue filter and a binned-table row filter both `eval` a user's
expression. The expression is not always the user's own -- it rides in on a
saved symbol file, on an XPA command, and inside a FITS file name -- so the
evaluator must run the arithmetic and nothing else. It used to use
`{"__builtins__": {}}` as the sandbox, which is not one.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from astropy.io import fits
from astropy.table import Table

from ncrads9.catalogs import catalog_filter
from ncrads9.core import bin_table
from ncrads9.utils.safe_expr import UnsafeExpression, safe_eval

# -- the evaluator itself ------------------------------------------------------


def test_arithmetic_still_evaluates():
    assert safe_eval("1 + 2 * 3", {}) == 7


def test_names_in_scope_are_usable():
    values = safe_eval("a + b", {"a": np.array([1, 2]), "b": np.array([10, 20])})
    assert values.tolist() == [11, 22]


def test_a_whitelisted_function_can_be_called():
    assert safe_eval("sqrt(x)", {"sqrt": np.sqrt, "x": np.array([4.0])}).tolist() == [2.0]


def test_a_name_not_in_scope_is_refused():
    with pytest.raises(UnsafeExpression, match="unknown name"):
        safe_eval("nope", {})


def test_attribute_access_is_refused():
    """The first step of every escape: `.__class__`, `.__globals__`."""
    with pytest.raises(UnsafeExpression):
        safe_eval("x.__class__", {"x": np.array([1])})


def test_the_subclasses_gadget_is_refused():
    """The published escape from an empty-builtins eval, verbatim."""
    gadget = "x.__class__.__mro__[-1].__subclasses__()"
    with pytest.raises(UnsafeExpression):
        safe_eval(gadget, {"x": np.array([1])})


def test_dunder_import_is_refused():
    with pytest.raises(UnsafeExpression):
        safe_eval("__import__('os')", {})


def test_a_lambda_is_refused():
    with pytest.raises(UnsafeExpression):
        safe_eval("(lambda: 1)()", {})


def test_a_comprehension_is_refused():
    with pytest.raises(UnsafeExpression):
        safe_eval("[i for i in x]", {"x": np.array([1, 2])})


def test_calling_a_computed_target_is_refused():
    """Only a plain named function may be called, not one an expression picks
    -- calling the result of a call, or an item of a list, is refused."""
    with pytest.raises(UnsafeExpression):
        safe_eval("sqrt(x)(x)", {"sqrt": np.sqrt, "x": np.array([1.0])})


def test_a_builtins_map_cannot_be_supplied_through_the_namespace():
    """Even if a caller slipped `__builtins__` in, it is forced empty."""
    with pytest.raises(UnsafeExpression):
        safe_eval("open('x')", {"__builtins__": {"open": open}})


# -- the two features, end to end ----------------------------------------------


@pytest.fixture
def catalog_table():
    return Table({"Jmag": np.array([1.0, 2.0, 3.0]), "Class": np.array(["G", "K", "G"])})


def test_a_catalogue_filter_cannot_write_a_file(tmp_path, catalog_table):
    """The whole point: a filter from a symbol file must not touch the disk."""
    marker = tmp_path / "written"
    expr = f"contains.__globals__['__builtins__']['open']({str(marker)!r}, 'w')"
    with pytest.raises(catalog_filter.FilterError):
        catalog_filter.evaluate(catalog_table, expr)
    assert not marker.exists()


def test_a_legitimate_catalogue_filter_still_works(catalog_table):
    assert catalog_filter.evaluate(catalog_table, "$Jmag > 1.5").tolist() == [False, True, True]
    assert catalog_filter.evaluate(catalog_table, "[string equal $Class G]").tolist() == [True, False, True]


def test_a_bin_table_filter_cannot_execute_code(tmp_path):
    """The filter arrives inside a FITS file name, so this is opening a file."""
    path = tmp_path / "events.fits"
    fits.BinTableHDU.from_columns(
        [fits.Column(name="pha", format="E", array=np.array([1.0, 6.0, 3.0]))]
    ).writeto(path)

    marker = tmp_path / "written"
    gadget = (
        "pha.__class__.__mro__[-1].__subclasses__()[0].__init__.__globals__"
        f"['__builtins__']['open']({str(marker)!r}, 'w')"
    )
    with fits.open(path) as hdul, pytest.raises(bin_table.BinTableError):
        bin_table.apply_filter(hdul[1], gadget)
    assert not marker.exists()
    assert not os.path.exists(marker)
