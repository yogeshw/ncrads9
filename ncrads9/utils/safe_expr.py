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
Evaluating an arithmetic/boolean expression over numpy arrays, safely.

Two features evaluate a user's expression against a table's columns: the
catalogue filter (`catalogs.catalog_filter`) and the binned-table row filter
(`core.bin_table`). Both used to hand the translated expression straight to
`eval` with `{"__builtins__": {}}` as the globals, in the belief that an empty
builtins map is a sandbox. It is not. Given any object -- and a numpy array is
one -- an expression can climb from it to the interpreter's own machinery:

    x.__class__.__mro__[-1].__subclasses__()[N].__init__.__globals__['__builtins__']

reaches a live `__builtins__` with `open`, `__import__` and everything else,
so a filter string is arbitrary code. That matters because a filter is not
always typed by the person at the keyboard: it rides in on a saved catalogue
symbol file, on an XPA `catalog filter` command from any local process, and
inside a FITS *file name* through DS9's `file.fits[bin=x,y][expr]` syntax --
opening a file someone sent you was enough.

Every one of those escapes goes through attribute access: `.__class__`,
`.__globals__`, `.__subclasses__`. None of them is anything a coordinate
filter legitimately needs. So this evaluates the expression from its AST and
rejects any node that is not on a small allow-list -- and `ast.Attribute` is
not on it. Names are checked too: an expression may name only the columns and
the maths functions the caller provides, nothing else.

The result is that a legitimate filter evaluates exactly as it did before --
the same `eval` runs, over the same namespace -- while an expression reaching
for anything outside the allow-list is refused before it runs.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import ast
from typing import Any

#: The expression nodes a filter is allowed to be built from. Deliberately a
#: closed list: anything not named here -- an attribute access, a lambda, a
#: comprehension, a walrus, a starred argument, a formatted string -- is
#: refused, so the allow-list cannot be widened by accident.
_ALLOWED_NODES: tuple[type[ast.AST], ...] = (
    ast.Expression,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Subscript,
    ast.Slice,
    ast.List,
    ast.Tuple,
    # Operators and comparison operators.
    ast.And,
    ast.Or,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.BitAnd,
    ast.BitOr,
    ast.BitXor,
    ast.LShift,
    ast.RShift,
    ast.USub,
    ast.UAdd,
    ast.Invert,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)

# `ast.Index` existed before Python 3.9 and wrapped a subscript's value. It is
# gone in 3.9+, where the value sits directly under `Subscript`; include it
# when it is present so the allow-list is correct on either.
if hasattr(ast, "Index"):  # pragma: no cover - version dependent
    _ALLOWED_NODES = (*_ALLOWED_NODES, ast.Index)


class UnsafeExpression(ValueError):
    """An expression that uses something the allow-list does not permit."""


def _validate(tree: ast.AST, allowed_names: frozenset[str]) -> None:
    """Reject any node, name or attribute access the allow-list forbids.

    Raises:
        UnsafeExpression: on the first thing that is not permitted, named so
            the caller can put it in front of the user.
    """
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise UnsafeExpression(f"{type(node).__name__.lower()} is not allowed in a filter")
        # Belt and braces: `ast.Attribute` is simply absent from the
        # allow-list, but attribute access is *the* escape route, so it is
        # named here too rather than left to the list.
        if isinstance(node, ast.Attribute):  # pragma: no cover - unreachable via the list
            raise UnsafeExpression("attribute access is not allowed in a filter")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise UnsafeExpression(f"unknown name {node.id!r} in a filter")
        # A call's target must be a plain allowed name -- not an expression
        # that computes which function to call.
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in allowed_names:
                raise UnsafeExpression("only named functions may be called in a filter")
            if node.keywords:
                raise UnsafeExpression("keyword arguments are not allowed in a filter")


def safe_eval(source: str, namespace: dict[str, Any]) -> Any:
    """Evaluate `source` against `namespace`, allowing nothing else.

    Args:
        source: Python source for a single expression -- the output of a
            filter translator, over columns and whitelisted functions.
        namespace: Every name the expression may use, mapped to its value:
            the column arrays and the maths functions. `__builtins__` is
            forced empty and cannot be overridden.

    Returns:
        Whatever the expression evaluates to, exactly as `eval` would.

    Raises:
        UnsafeExpression: if the expression uses a node, a name, or an
            attribute access outside the allow-list.
        SyntaxError: if the expression will not parse. Left to propagate
            rather than reclassified as unsafe: a string that does not parse
            runs nothing, so it is an ordinary "bad filter" for the caller to
            report as it already reports any other, not a security refusal.
    """
    # `eval` tolerates leading and trailing whitespace on an expression
    # string; `ast.parse(mode="eval")` reads leading whitespace as an indent
    # and refuses it. The translators emit a leading space (`!x` becomes
    # ` ~x`), so strip before parsing to keep those expressions working.
    tree = ast.parse(source.strip(), mode="eval")

    # The names in scope are the only ones an expression may mention; anything
    # else -- including a leftover builtin name -- is rejected as unknown.
    _validate(tree, frozenset(namespace))

    scope = {**namespace, "__builtins__": {}}
    return eval(compile(tree, "<filter>", "eval"), scope)
