from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb


@dataclass(frozen=True)
class Column:
    name: str
    type: str


@dataclass(frozen=True)
class Preview:
    columns: list[Column]
    rows: list[tuple[Any, ...]]
    row_count: int


def preview_csv(path: Path, limit: int = 20) -> Preview:
    """Read a CSV file and return its columns, row count and first few rows."""
    with duckdb.connect() as con:
        relation = con.read_csv(str(path))
        columns = [
            Column(name, str(type_))
            for name, type_ in zip(relation.columns, relation.types, strict=True)
        ]
        count = relation.aggregate("count(*)").fetchone()
        rows = relation.limit(limit).fetchall()
    return Preview(columns=columns, rows=rows, row_count=int(count[0]) if count else 0)
