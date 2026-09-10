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
Local catalog files: the formats DS9 loads and saves.

"Local catalog files in starbase (rdb) or CSV (with or without header) are
supported" (`ds9/doc/ref/catalog.html`), and its own Save writes starbase.
Tab-separated and VOTable are here too, because a catalog that came from a
cone search arrives as VOTable and re-reading it should not need a
conversion.

Starbase is the one worth describing, since it is not a format astropy
knows. From `starbase_header` in `ds9/library/starbase.tcl:142`:

    name<TAB>value        # any number of header lines, key and value
    RA<TAB>Dec<TAB>Jmag   # the column names
    --<TAB>---<TAB>----   # a rule of dashes, which is what ends the header
    10.5<TAB>41.2<TAB>9.1 # the rows

The rule of dashes is the only thing that marks where the header stops, so
a file without one is not starbase, and a file with one is -- which is how
`detect` tells the formats apart rather than trusting the extension.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import csv
import io
import re
from enum import Enum
from pathlib import Path

from astropy.table import Table


class CatalogFileError(ValueError):
    """A catalog file that cannot be read, for the reason given."""


class CatalogFormat(Enum):
    """The local formats DS9 reads and writes."""

    STARBASE = "starbase"
    TSV = "tsv"
    CSV = "csv"
    #: CSV whose first line is data, not column names.
    CSV_NO_HEADER = "csv-no-header"
    VOTABLE = "votable"


#: What each format is usually called on disk.
SUFFIXES: dict[CatalogFormat, tuple[str, ...]] = {
    CatalogFormat.STARBASE: (".rdb", ".tab", ".starbase"),
    CatalogFormat.TSV: (".tsv",),
    CatalogFormat.CSV: (".csv",),
    CatalogFormat.CSV_NO_HEADER: (),
    CatalogFormat.VOTABLE: (".xml", ".vot", ".votable"),
}

#: The file filter DS9's catalog Open and Save offer.
FILE_FILTER = (
    "Catalog Files (*.rdb *.tab *.csv *.tsv *.xml *.vot);;"
    "Starbase (*.rdb *.tab);;"
    "CSV (*.csv);;"
    "TSV (*.tsv);;"
    "VOTable (*.xml *.vot);;"
    "All Files (*)"
)

#: A starbase rule: dashes, tab-separated, and nothing else.
_RULE = re.compile(r"^-+(\s*\t\s*-+)*\s*$")

#: How many lines `detect` reads before deciding. A starbase header is
#: short in every file DS9 writes; reading the whole of a million-row
#: catalogue to classify it would be absurd.
DETECT_LINES = 60


def detect(text: str, path: str | Path | None = None) -> CatalogFormat:
    """Work out which format some catalog text is in.

    The content decides, not the extension: a `.txt` from a colleague is as
    likely to be starbase as anything, and a `.csv` full of tabs is a TSV
    whatever it is called. The extension is consulted only to choose
    between CSV and TSV when the text does not say.

    Args:
        text: The file's contents, or its first few kilobytes.
        path: Its name, used only as a tie-breaker.

    Returns:
        The format.
    """
    stripped = text.lstrip()
    if stripped.startswith("<?xml") or "<VOTABLE" in stripped[:2048].upper():
        return CatalogFormat.VOTABLE

    lines = [line for line in text.splitlines()[:DETECT_LINES] if line.strip()]
    for index, line in enumerate(lines):
        if _RULE.match(line) and index > 0:
            return CatalogFormat.STARBASE

    suffix = Path(path).suffix.lower() if path else ""
    if suffix in SUFFIXES[CatalogFormat.STARBASE]:
        # Named `.rdb` but with no rule of dashes: read it as starbase
        # anyway, so the error says what is actually wrong with it rather
        # than quietly reading the header line as the only column.
        return CatalogFormat.STARBASE
    if suffix in SUFFIXES[CatalogFormat.TSV]:
        return CatalogFormat.TSV
    if suffix in SUFFIXES[CatalogFormat.CSV]:
        return _csv_or_headerless(lines)

    # No rule and no telling extension: whichever delimiter appears more.
    sample = "\n".join(lines[:10])
    if sample.count("\t") > sample.count(","):
        return CatalogFormat.TSV
    return _csv_or_headerless(lines)


def _csv_or_headerless(lines: list[str]) -> CatalogFormat:
    """Whether a CSV's first line is column names or data.

    A first line whose fields are all numbers is data: no catalogue names a
    column `10.5`. Guessing the other way puts the first star in the header
    and loses it.
    """
    if not lines:
        return CatalogFormat.CSV
    fields = next(csv.reader([lines[0]]), [])
    if not fields:
        return CatalogFormat.CSV
    return CatalogFormat.CSV_NO_HEADER if all(_numeric(field) for field in fields) else CatalogFormat.CSV


def _numeric(text: str) -> bool:
    """Whether a field is a number."""
    try:
        float(text.strip())
    except ValueError:
        return False
    return True


# -- starbase ------------------------------------------------------------------


def parse_starbase(text: str) -> Table:
    """Read starbase (rdb): header lines, column names, a rule, then rows.

    Raises:
        CatalogFileError: If there is no rule of dashes, which is the only
            thing that marks the end of the header.
    """
    lines = text.splitlines()
    rule = next((index for index, line in enumerate(lines) if _RULE.match(line) and index > 0), None)
    if rule is None:
        raise CatalogFileError("not a starbase file: no rule of dashes after the column names")

    names = [name.strip() for name in lines[rule - 1].split("\t")]
    header = {}
    for line in lines[: rule - 1]:
        if "\t" in line:
            key, _, value = line.partition("\t")
            header[key.strip()] = value.strip()

    rows: list[list[str]] = []
    for line in lines[rule + 1 :]:
        if not line.strip():
            continue
        fields = [field.strip() for field in line.split("\t")]
        fields += [""] * (len(names) - len(fields))
        rows.append(fields[: len(names)])

    table = _table(names, rows)
    table.meta.update(header)
    return table


def to_starbase(table: Table) -> str:
    """Write starbase, which is what DS9's catalog Save produces."""
    names = [str(name) for name in table.colnames]
    lines = [f"{key}\t{value}" for key, value in (table.meta or {}).items() if key and value is not None]
    lines.append("\t".join(names))
    # The rule's dashes are conventionally as wide as the name above them,
    # which is what makes the file readable in a terminal.
    lines.append("\t".join("-" * max(1, len(name)) for name in names))
    for row in table:
        lines.append("\t".join(_field(row[name]) for name in names))
    return "\n".join(lines) + "\n"


# -- delimited -----------------------------------------------------------------


def parse_delimited(text: str, delimiter: str, header: bool = True) -> Table:
    """Read CSV or TSV, with or without a header row.

    Raises:
        CatalogFileError: If there are no rows at all.
    """
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any(field.strip() for field in row)]
    if not rows:
        raise CatalogFileError("the file holds no rows")

    if header:
        names = [name.strip() or f"col{index + 1}" for index, name in enumerate(rows[0])]
        body = rows[1:]
    else:
        # DS9's "CSV without header": columns are numbered, as its own
        # catalog window shows them.
        names = [f"col{index + 1}" for index in range(len(rows[0]))]
        body = rows

    widened = []
    for row in body:
        fields = [field.strip() for field in row]
        fields += [""] * (len(names) - len(fields))
        widened.append(fields[: len(names)])
    return _table(names, widened)


def to_delimited(table: Table, delimiter: str, header: bool = True) -> str:
    """Write CSV or TSV."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=delimiter, lineterminator="\n")
    names = [str(name) for name in table.colnames]
    if header:
        writer.writerow(names)
    for row in table:
        writer.writerow([_field(row[name]) for name in names])
    return output.getvalue()


# -- shared --------------------------------------------------------------------


def _field(value) -> str:
    """One cell as text, with a masked value written as nothing.

    A masked cell written as "--" -- which is how astropy prints one --
    would be read back as the string "--" rather than as missing.
    """
    import numpy as np

    if value is None or value is np.ma.masked:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    return str(value)


def _table(names: list[str], rows: list[list[str]]) -> Table:
    """Build a table, converting each column to numbers where it can be.

    Column by column rather than cell by cell: a column with one bad value
    in it is a text column, and half-converting it would leave a table
    whose type depends on which rows were read.
    """
    import numpy as np

    if not names:
        raise CatalogFileError("the file names no columns")

    table = Table()
    for index, name in enumerate(names):
        column = [row[index] if index < len(row) else "" for row in rows]
        table[name] = _convert(column, np)
    return table


def _convert(column: list[str], np):
    """One column as floats if every non-blank value is one, else as text.

    A column that is entirely blank comes back as NaN rather than as empty
    strings: it holds no information either way, and a float column can at
    least be compared and plotted, where a column of "" cannot.
    """
    values = [value.strip() for value in column]
    filled = [value for value in values if value != ""]
    if not filled:
        return np.full(len(values), np.nan, dtype=np.float64)
    if all(_numeric(value) for value in filled):
        return np.array([float(value) if value != "" else np.nan for value in values], dtype=np.float64)
    return np.array(values, dtype=object)


# -- the front door ------------------------------------------------------------


def parse(text: str, catalog_format: CatalogFormat | None = None, path: str | Path | None = None) -> Table:
    """Read a catalog from text in any of the supported formats.

    Args:
        text: The file's contents.
        catalog_format: The format. Detected when not given.
        path: The file's name, used only to help detection.

    Returns:
        The catalog.

    Raises:
        CatalogFileError: If it cannot be read.
    """
    chosen = catalog_format or detect(text, path)

    if chosen is CatalogFormat.STARBASE:
        return parse_starbase(text)
    if chosen is CatalogFormat.TSV:
        return parse_delimited(text, "\t")
    if chosen is CatalogFormat.CSV:
        return parse_delimited(text, ",")
    if chosen is CatalogFormat.CSV_NO_HEADER:
        return parse_delimited(text, ",", header=False)

    try:
        from astropy.io.votable import parse_single_table

        return parse_single_table(io.BytesIO(text.encode("utf-8"))).to_table(use_names_over_ids=True)
    except Exception as exc:
        raise CatalogFileError(f"cannot read as VOTable: {exc}") from exc


def to_text(table: Table, catalog_format: CatalogFormat = CatalogFormat.STARBASE) -> str:
    """Write a catalog in one of the supported formats.

    Raises:
        CatalogFileError: If the format cannot be written.
    """
    if catalog_format is CatalogFormat.STARBASE:
        return to_starbase(table)
    if catalog_format is CatalogFormat.TSV:
        return to_delimited(table, "\t")
    if catalog_format is CatalogFormat.CSV:
        return to_delimited(table, ",")
    if catalog_format is CatalogFormat.CSV_NO_HEADER:
        return to_delimited(table, ",", header=False)

    output = io.BytesIO()
    try:
        table.write(output, format="votable")
    except Exception as exc:
        raise CatalogFileError(f"cannot write as VOTable: {exc}") from exc
    return output.getvalue().decode("utf-8")


def format_for(path: str | Path) -> CatalogFormat:
    """The format a filename implies, for saving.

    Saving is the one place the extension decides: the user typed it, and
    there is no content to inspect yet.
    """
    suffix = Path(path).suffix.lower()
    for candidate, suffixes in SUFFIXES.items():
        if suffix in suffixes:
            return candidate
    return CatalogFormat.STARBASE


def load(path: str | Path, catalog_format: CatalogFormat | None = None) -> Table:
    """Read a catalog file.

    Raises:
        CatalogFileError: If it cannot be read.
        OSError: If it cannot be opened.
    """
    location = Path(path)
    text = location.read_text(encoding="utf-8", errors="replace")
    return parse(text, catalog_format, location)


def save(path: str | Path, table: Table, catalog_format: CatalogFormat | None = None) -> None:
    """Write a catalog file.

    Raises:
        CatalogFileError: If the format cannot be written.
        OSError: If it cannot be written.
    """
    location = Path(path)
    chosen = catalog_format or format_for(location)
    location.write_text(to_text(table, chosen), encoding="utf-8")
