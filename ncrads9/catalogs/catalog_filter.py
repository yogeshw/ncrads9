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
The expressions DS9 filters a catalogue and chooses its symbols by.

"A filter is conditional expression, when evaluated for each row of the
catalog, if true, the row is displayed... The value of a column may be
indicated with `$<column name>`" (`ds9/doc/ref/catalog.html`):

    $_RAJ2000>180. && $_RAJ2000<270.
    $Jmag>11

DS9 evaluates these with Tcl's `expr`. There is no Tcl here, so they are
evaluated as Python instead, with `$column` substituted for the column's
value and `&&`/`||`/`!` translated -- which covers every example in DS9's
documentation except the two that call Tcl commands (`[string equal ...]`,
`[regexp ...]`). Those are recognised and translated too, because they are
the documented way to filter on a string column and an analysis file
written for DS9 should work.

Evaluation is vectorised over the whole column, so a filter on a hundred
thousand rows is one numpy expression rather than a hundred thousand
`eval` calls. That is also why the expression is compiled once and the
column arrays are the only thing that changes.

Nothing here evaluates arbitrary code with builtins available: the
namespace holds the columns, a short list of maths functions, and nothing
else. A catalogue filter is typed by the user, but a symbol expression can
arrive inside a saved symbol file.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import re

import numpy as np
from astropy.table import Table
from numpy.typing import NDArray


class FilterError(ValueError):
    """An expression that cannot be evaluated, for the reason given."""


#: `$column` or `${column}` -- a column reference.
_COLUMN = re.compile(r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)")

#: `[string equal $a $b]`, DS9's documented way to compare strings.
_STRING_EQUAL = re.compile(r"\[\s*string\s+equal\s+(\S+)\s+(\S+?)\s*\]")

#: `[regexp {pattern} $column]`, likewise for matching.
_REGEXP = re.compile(r"\[\s*regexp\s+\{?([^}\s]+)\}?\s+(\S+?)\s*\]")

#: `[expr ...]`, which in a symbol's text field means "evaluate this".
_EXPR = re.compile(r"\[\s*expr\s+(.+?)\s*\]")

#: What the evaluated expression may call. Deliberately short: everything
#: else, builtins included, is unavailable.
FUNCTIONS: dict[str, object] = {
    "abs": np.abs,
    "acos": np.arccos,
    "asin": np.arcsin,
    "atan": np.arctan,
    "atan2": np.arctan2,
    "ceil": np.ceil,
    "cos": np.cos,
    "cosh": np.cosh,
    "exp": np.exp,
    "floor": np.floor,
    "hypot": np.hypot,
    "log": np.log,
    "log10": np.log10,
    "max": np.maximum,
    "min": np.minimum,
    "pow": np.power,
    "round": np.round,
    "sin": np.sin,
    "sinh": np.sinh,
    "sqrt": np.sqrt,
    "tan": np.tan,
    "tanh": np.tanh,
    "pi": np.pi,
    "e": np.e,
    "true": True,
    "false": False,
    "isfinite": np.isfinite,
    "isnan": np.isnan,
    "contains": lambda column, text: np.char.find(np.asarray(column, dtype=str), str(text)) >= 0,
    "matches": lambda column, pattern: np.array(
        [bool(re.search(str(pattern), str(value))) for value in np.atleast_1d(column)]
    ),
}


def columns_used(expression: str) -> list[str]:
    """Which columns an expression refers to, in the order first seen."""
    found: list[str] = []
    for braced, plain in _COLUMN.findall(expression or ""):
        name = braced or plain
        if name and name not in found:
            found.append(name)
    return found


def translate(expression: str) -> str:
    """Turn one of DS9's Tcl expressions into the Python equivalent.

    Args:
        expression: The expression as the user typed it.

    Returns:
        Python source. Column references become `_c["name"]`, so a column
        called `class` or `max` cannot collide with a Python keyword or a
        function name -- which a plain identifier would.
    """
    text = expression or ""

    # `[expr ...]` is a wrapper meaning "this is an expression"; unwrap it.
    text = _EXPR.sub(lambda match: f"({match.group(1)})", text)
    text = _STRING_EQUAL.sub(
        lambda match: f"({_operand(match.group(1))} == {_operand(match.group(2))})", text
    )
    text = _REGEXP.sub(lambda match: f"matches({match.group(2)}, {match.group(1).strip('*')!r})", text)

    def column(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        return f'_c["{name}"]'

    text = _COLUMN.sub(column, text)

    # Tcl's operators. numpy needs the bitwise forms to work per row, and
    # `!` becomes `~` for the same reason.
    text = text.replace("&&", " & ").replace("||", " | ")
    text = re.sub(r"(?<![=!<>])!(?!=)", " ~", text)
    text = text.replace("<>", "!=")

    # And then each side of a `&` or `|` is parenthesised. Python binds the
    # bitwise operators *tighter* than the comparisons, so a bare
    # substitution turns `a>1 & a<2` into `a > (1 & a) < 2` -- which is not
    # a type error away from being wrong, it is a different question.
    return _parenthesise(text)


def _operand(word: str) -> str:
    """One operand of a Tcl string comparison.

    A `$column` reference is left alone -- it is translated a step later --
    and anything else is a bare word, which Tcl reads as a literal string
    and Python would read as an identifier. Quoting the column reference
    too, which is the mistake to make here, compares the *name* with the
    literal and every row comes out false.
    """
    text = word.strip()
    if text.startswith(("$", "_c[", "'", '"')):
        return text
    return repr(text)


def _parenthesise(text: str) -> str:
    """Wrap each side of a top-level `&` or `|` in brackets.

    Splitting only at depth zero and outside quotes, so a `&` inside a
    function call or a string is left alone.
    """
    parts: list[str] = []
    operators: list[str] = []
    depth = 0
    quote = ""
    start = 0

    index = 0
    while index < len(text):
        character = text[index]
        if quote:
            if character == quote:
                quote = ""
        elif character in "\"'":
            quote = character
        elif character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
        elif depth == 0 and character in "&|":
            # `&&` and `||` are already single characters by now.
            parts.append(text[start:index])
            operators.append(character)
            start = index + 1
        index += 1

    parts.append(text[start:])
    if not operators:
        return text

    wrapped = [f"({part.strip()})" if part.strip() else "()" for part in parts]
    joined = wrapped[0]
    for operator, part in zip(operators, wrapped[1:], strict=True):
        joined = f"{joined} {operator} {part}"
    return joined


def _namespace(table: Table, columns: list[str]) -> dict:
    """The columns an expression needs, as arrays, plus the functions.

    Raises:
        FilterError: If the expression names a column the table lacks.
    """
    lookup = {name.lower(): name for name in table.colnames}
    values: dict[str, NDArray] = {}

    for name in columns:
        actual = lookup.get(name.lower())
        if actual is None:
            raise FilterError(f"no such column: {name}")
        column = np.asarray(table[actual])
        if column.dtype.kind in "OSU":
            values[name] = column.astype(str)
        else:
            values[name] = column.astype(float)

    return {"_c": values, **FUNCTIONS, "__builtins__": {}}


def evaluate(table: Table, expression: str) -> NDArray[np.bool_]:
    """Evaluate a filter over a whole table at once.

    Args:
        table: The catalogue.
        expression: The filter. Empty means "every row".

    Returns:
        A boolean array, one entry per row.

    Raises:
        FilterError: If the expression cannot be evaluated.
    """
    rows = len(table)
    if not (expression or "").strip():
        return np.ones(rows, dtype=bool)

    source = translate(expression)
    namespace = _namespace(table, columns_used(expression))

    try:
        result = eval(source, namespace)
    except FilterError:
        raise
    except Exception as exc:
        raise FilterError(f"cannot evaluate {expression!r}: {exc}") from exc

    return _as_mask(result, rows, expression)


def _as_mask(result, rows: int, expression: str) -> NDArray[np.bool_]:
    """Turn whatever an expression produced into one mask per row.

    A constant -- DS9 documents `1`, `0`, `true` and `false` as always and
    never -- becomes every row or none.

    Raises:
        FilterError: If the result is neither a constant nor one value per
            row, which means the expression was not a per-row condition.
    """
    array = np.asarray(result)
    if array.ndim == 0:
        return np.full(rows, bool(array), dtype=bool)
    if array.shape[0] == rows:
        return array.astype(bool)
    raise FilterError(
        f"{expression!r} gave {array.shape[0]} values for {rows} rows; "
        "a filter must be true or false for each row"
    )


def evaluate_values(table: Table, expression: str, default: float = 0.0) -> NDArray[np.floating]:
    """Evaluate a numeric expression per row, for a symbol's size or angle.

    DS9's symbol editor takes `2`, `$Jmag`, `$Jmag/2.` and the like for its
    size and angle fields, evaluated the same way as a filter but wanted as
    numbers rather than as a condition.

    Args:
        table: The catalogue.
        expression: The expression. Empty gives `default` for every row.
        default: What an empty or unusable expression gives.

    Returns:
        One number per row.
    """
    rows = len(table)
    if not (expression or "").strip():
        return np.full(rows, float(default))

    try:
        source = translate(expression)
        namespace = _namespace(table, columns_used(expression))
        result = eval(source, namespace)
    except Exception:
        return np.full(rows, float(default))

    array = np.asarray(result, dtype=float)
    if array.ndim == 0:
        return np.full(rows, float(array))
    if array.shape[0] == rows:
        return array
    return np.full(rows, float(default))


def evaluate_text(table: Table, expression: str) -> list[str]:
    """Evaluate a symbol's text field, which is text unless told otherwise.

    "For the text portion, this is not true. It is assumed to be text,
    unless you explicitly use an expr operator" -- so `foo` is the word
    foo, `$Jmag` is the column's value, and `[expr $Jmag/2.]` is arithmetic
    (`ds9/doc/ref/catalog.html`).
    """
    rows = len(table)
    text = (expression or "").strip()
    if not text:
        return [""] * rows

    references = columns_used(text)
    has_expr = bool(_EXPR.search(text))

    if not references and not has_expr:
        # Plain text, the same above every symbol.
        return [text] * rows

    if has_expr or len(references) > 1 or text != f"${references[0]}":
        try:
            source = translate(text)
            namespace = _namespace(table, references)
            result = eval(source, namespace)
            array = np.atleast_1d(np.asarray(result))
            if array.shape[0] == rows:
                return [_pretty(value) for value in array]
            return [_pretty(array.item(0))] * rows
        except Exception:
            return [text] * rows

    # A bare `$column`: the column's value, formatted.
    namespace = _namespace(table, references)
    return [_pretty(value) for value in namespace["_c"][references[0]]]


def _pretty(value) -> str:
    """One symbol label, without a trailing `.0` on a whole number."""
    if isinstance(value, (float, np.floating)):
        if np.isnan(value):
            return ""
        return f"{value:g}"
    return str(value)
