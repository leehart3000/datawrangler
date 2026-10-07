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


@dataclass(frozen=True)
class Column:
    name: str
    type: str


@dataclass(frozen=True)
class Preview:
    columns: list[Column]
    rows: list[tuple[Any, ...]]
    row_count: int


@dataclass(frozen=True)
class CleaningReport:
    rows_before: int
    empty_rows_removed: int
    duplicates_removed: int


def _quote(name: str) -> str:
    """Quote a column name for SQL, so any name (even with spaces or quotes) is safe."""
    return '"' + name.replace('"', '""') + '"'


def _count(relation: duckdb.DuckDBPyRelation) -> int:
    result = relation.aggregate("count(*)").fetchone()
    return int(result[0]) if result else 0


def _apply_cleaning(
    con: duckdb.DuckDBPyConnection, path: Path, options: CleaningOptions
) -> tuple[duckdb.DuckDBPyRelation, CleaningReport]:
    """Read the CSV as exact text, and apply the chosen cleaning steps in order."""
    # all_varchar keeps every value exactly as written (so "007" stays "007").
    relation = con.read_csv(str(path), all_varchar=True)
    quoted = [_quote(name) for name in relation.columns]
    rows_before = _count(relation)

    # Number the rows, so the original order can be restored at the end.
    relation = relation.project(f"*, row_number() OVER () AS {ROW_ID}")

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
    report = CleaningReport(rows_before, empty_rows_removed, duplicates_removed)
    return relation, report


def clean_csv(
    path: Path, options: CleaningOptions, limit: int = 20
) -> tuple[Preview, CleaningReport]:
    """Apply the chosen cleaning steps and preview the result."""
    with duckdb.connect() as con:
        # DuckDB's guess at each column's type, shown as information only.
        types = [str(type_) for type_ in con.read_csv(str(path)).types]
        relation, report = _apply_cleaning(con, path, options)
        names = relation.columns
        rows = relation.limit(limit).fetchall()
        row_count = _count(relation)

    columns = [Column(name, type_) for name, type_ in zip(names, types, strict=True)]
    return Preview(columns=columns, rows=rows, row_count=row_count), report


def write_clean_csv(path: Path, options: CleaningOptions, output: Path) -> None:
    """Apply the chosen cleaning steps and save the result as a CSV file."""
    with duckdb.connect() as con:
        relation, _ = _apply_cleaning(con, path, options)
        relation.write_csv(str(output))


def preview_csv(path: Path, limit: int = 20) -> Preview:
    """Read a CSV file and preview it without any cleaning."""
    preview, _ = clean_csv(path, CleaningOptions(), limit)
    return preview
