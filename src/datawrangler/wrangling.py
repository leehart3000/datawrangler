"""Reading, cleaning and writing data.

The most important rule: every value that goes in must come out exactly the same,
unless the user chose a cleaning step that changes it. If a file can't be read
faithfully, refuse it with a clear message rather than guess. Display aids (such as
markers for empty cells or extra spaces) belong in templates, never in downloads.
"""

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
from pydantic import BaseModel

# A temporary column used to remember each row's original position.
ROW_ID = "__datawrangler_row"


class CleaningOptions(BaseModel):
    """Which cleaning steps to apply. Each one is off unless switched on."""

    trim_whitespace: bool = False
    remove_empty_rows: bool = False
    remove_duplicates: bool = False
    tidy_column_names: bool = False
    snake_case_column_names: bool = False
    # Positions of the columns to keep, and a fingerprint of the columns they were chosen for.
    keep_columns: list[int] | None = None
    columns_for: str | None = None


class UnreadableFileError(Exception):
    """The file can't be read faithfully as a table, so it's refused rather than guessed at."""


class NoColumnsKeptError(Exception):
    """Raised when every column has been unticked."""

    def __init__(self, all_columns: list[str], signature: str) -> None:
        super().__init__("Please keep at least one column.")
        self.all_columns = all_columns
        self.signature = signature


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    empty: int = 0
    distinct: int = 0


@dataclass(frozen=True)
class Preview:
    columns: list[Column]
    rows: list[tuple[Any, ...]]
    row_count: int
    all_columns: list[str]
    columns_signature: str
    kept_columns: list[int]


@dataclass(frozen=True)
class CleaningReport:
    rows_before: int
    columns_removed: int
    empty_rows_removed: int
    duplicates_removed: int
    names_changed: int


@dataclass(frozen=True)
class _Cleaned:
    """The cleaned data, plus what's needed to describe it."""

    relation: duckdb.DuckDBPyRelation
    report: CleaningReport
    all_names: list[str]
    kept: list[int]
    names: list[str]


def columns_signature(names: list[str]) -> str:
    """A short fingerprint of a file's column names, to tell when a different file is chosen."""
    joined = "\x1f".join(names)
    return hashlib.sha256(joined.encode()).hexdigest()[:16]


def tidy_column_names(names: list[str], trim: bool, snake: bool) -> list[str]:
    """Tidy column names, keeping them unique. Returns the names unchanged if neither option is on."""
    if not (trim or snake):
        return names
    tidied: list[str] = []
    seen: set[str] = set()
    for position, name in enumerate(names, start=1):
        new = " ".join(name.split())
        if snake:
            new = re.sub(r"\W+", "_", new.lower()).strip("_")
        if not new:
            new = f"column_{position}"
        base, number = new, 2
        while new in seen:
            new = f"{base}_{number}"
            number += 1
        seen.add(new)
        tidied.append(new)
    return tidied


def read_header(path: Path) -> list[str]:
    """Read the header row exactly as written, using Python's own CSV reader."""
    try:
        with path.open(newline="", encoding="utf-8-sig") as file:
            header = next(csv.reader(file), None)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise UnreadableFileError from exc
    if not header:
        raise UnreadableFileError
    return header


def _quote(name: str) -> str:
    """Quote a name for SQL, so any name is treated only as a name."""
    return '"' + name.replace('"', '""') + '"'


def _literal(text: str) -> str:
    """Quote a piece of text for SQL, so it's treated only as text."""
    return "'" + text.replace("'", "''") + "'"


def _count(relation: duckdb.DuckDBPyRelation) -> int:
    result = relation.aggregate("count(*)").fetchone()
    return int(result[0]) if result else 0


def _column_stats(
    relation: duckdb.DuckDBPyRelation, row_count: int
) -> list[tuple[int, int]]:
    """Return (empty cells, distinct values) for each column, in one pass over the data."""
    quoted = [_quote(name) for name in relation.columns]
    expressions = ", ".join(f"count({q}), count(DISTINCT {q})" for q in quoted)
    result = relation.aggregate(expressions).fetchone()
    if result is None:
        return [(0, 0) for _ in quoted]
    filled_counts = result[0::2]
    distinct_counts = result[1::2]
    return [
        (row_count - int(filled), int(distinct))
        for filled, distinct in zip(filled_counts, distinct_counts, strict=True)
    ]


def _read_table(
    con: duckdb.DuckDBPyConnection, path: Path, column_count: int, all_varchar: bool
) -> duckdb.DuckDBPyRelation:
    """Read the CSV with its structure fixed, so DuckDB never has to guess.

    There is always a header row, nothing is skipped, and the separator is a comma.
    DuckDB uses simple internal names (c0, c1, ...); the real names come from read_header.
    Rows that don't fit (too few or too many values) make DuckDB stop with an error.
    """
    names = ", ".join(_literal(f"c{position}") for position in range(column_count))
    options = (
        "header = true, skip = 0, delim = ',', quote = '\"', escape = '\"', "
        f"names = [{names}], all_varchar = {'true' if all_varchar else 'false'}"
    )
    return con.sql(f"SELECT * FROM read_csv({_literal(str(path))}, {options})")


def _columns_to_keep(all_names: list[str], options: CleaningOptions) -> list[int]:
    """Work out which column positions to keep. Choices made for a different file are ignored."""
    positions = list(range(len(all_names)))
    if options.keep_columns is None or options.columns_for != columns_signature(
        all_names
    ):
        return positions
    wanted = set(options.keep_columns)
    kept = [position for position in positions if position in wanted]
    if not kept:
        raise NoColumnsKeptError(all_names, columns_signature(all_names))
    return kept


def _apply_cleaning(
    con: duckdb.DuckDBPyConnection, path: Path, options: CleaningOptions
) -> _Cleaned:
    """Read the CSV as exact text, and apply the chosen cleaning steps in order."""
    all_names = read_header(path)
    relation = _read_table(con, path, len(all_names), all_varchar=True)
    internal = relation.columns
    kept = _columns_to_keep(all_names, options)
    quoted = [_quote(internal[position]) for position in kept]
    rows_before = _count(relation)

    # Keep only the chosen columns, and number the rows so the order can be restored.
    relation = relation.project(
        ", ".join([*quoted, f"row_number() OVER () AS {ROW_ID}"])
    )

    if options.trim_whitespace:
        expressions = [f"NULLIF(trim({q}), '') AS {q}" for q in quoted]
        relation = relation.project(", ".join([*expressions, ROW_ID]))

    empty_rows_removed = 0
    if options.remove_empty_rows:
        before = _count(relation)
        relation = relation.filter(" OR ".join(f"{q} IS NOT NULL" for q in quoted))
        empty_rows_removed = before - _count(relation)

    duplicates_removed = 0
    if options.remove_duplicates:
        before = _count(relation)
        relation = relation.query(
            "data",
            "SELECT * FROM data QUALIFY row_number() OVER "
            f"(PARTITION BY {', '.join(quoted)} ORDER BY {ROW_ID}) = 1",
        )
        duplicates_removed = before - _count(relation)

    relation = relation.order(ROW_ID).project(", ".join(quoted))
    original = [all_names[position] for position in kept]
    names = tidy_column_names(
        original,
        trim=options.tidy_column_names,
        snake=options.snake_case_column_names,
    )
    report = CleaningReport(
        rows_before=rows_before,
        columns_removed=len(all_names) - len(kept),
        empty_rows_removed=empty_rows_removed,
        duplicates_removed=duplicates_removed,
        names_changed=sum(old != new for old, new in zip(original, names, strict=True)),
    )
    return _Cleaned(relation, report, all_names, kept, names)


def clean_csv(
    path: Path, options: CleaningOptions, limit: int = 20
) -> tuple[Preview, CleaningReport]:
    """Apply the chosen cleaning steps and preview the result."""
    with duckdb.connect() as con:
        cleaned = _apply_cleaning(con, path, options)
        # DuckDB's guess at each column's type, shown as information only.
        typed = _read_table(con, path, len(cleaned.all_names), all_varchar=False)
        types = [str(type_) for type_ in typed.types]
        rows = cleaned.relation.limit(limit).fetchall()
        row_count = _count(cleaned.relation)
        stats = _column_stats(cleaned.relation, row_count)

    columns = [
        Column(name, types[position], empty, distinct)
        for name, position, (empty, distinct) in zip(
            cleaned.names, cleaned.kept, stats, strict=True
        )
    ]
    preview = Preview(
        columns=columns,
        rows=rows,
        row_count=row_count,
        all_columns=cleaned.all_names,
        columns_signature=columns_signature(cleaned.all_names),
        kept_columns=cleaned.kept,
    )
    return preview, cleaned.report


def write_clean_csv(path: Path, options: CleaningOptions, output: Path) -> None:
    """Apply the chosen cleaning steps and save the result as a CSV file.

    The header row is written by Python with the real (or tidied) names, then
    DuckDB writes the data rows underneath.
    """
    body = output.with_name(output.name + ".rows")
    with duckdb.connect() as con:
        cleaned = _apply_cleaning(con, path, options)
        cleaned.relation.write_csv(str(body), header=False)

    with output.open("w", newline="", encoding="utf-8") as file:
        csv.writer(file, lineterminator="\n").writerow(cleaned.names)
        file.write(body.read_text(encoding="utf-8"))
    body.unlink()


def preview_csv(path: Path, limit: int = 20) -> Preview:
    """Read a CSV file and preview it without any cleaning."""
    preview, _ = clean_csv(path, CleaningOptions(), limit)
    return preview
