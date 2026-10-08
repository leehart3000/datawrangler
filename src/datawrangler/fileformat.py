"""Detecting a CSV file's format details, so downloads can reproduce them exactly.

Format details aren't values, but they're part of the file, so the rule is:
detect what the original does, reproduce it by default, and only change it
when the user explicitly chooses to.
"""

import csv
import io
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

BYTE_ORDER_MARK = "\ufeff"
NEEDS_QUOTES = frozenset({",", '"', "\r", "\n"})

Quoting = Literal["none", "minimal", "all", "mixed"]


@dataclass(frozen=True)
class FileFormat:
    byte_order_mark: bool = False
    line_ending: str = "\n"
    mixed_line_endings: bool = False
    final_line_break: bool = True
    quoting: Quoting = "none"


def _scan_quoted(text: str) -> tuple[Counter[str], Quoting]:
    """Walk through a file that contains quotes, field by field.

    Returns the line endings found between rows (ignoring line breaks inside
    quoted values) and the quoting style.
    """
    endings: Counter[str] = Counter()
    quoted = unquoted = unnecessary = 0
    in_quotes = field_quoted = field_needs_quotes = False
    at_field_start = True
    position, length = 0, len(text)

    def finish_field() -> None:
        nonlocal quoted, unquoted, unnecessary, field_quoted, field_needs_quotes
        if field_quoted:
            quoted += 1
            if not field_needs_quotes:
                unnecessary += 1
        else:
            unquoted += 1
        field_quoted = field_needs_quotes = False

    while position < length:
        char = text[position]
        if in_quotes:
            if char == '"':
                if text.startswith('""', position):
                    field_needs_quotes = True
                    position += 2
                    continue
                in_quotes = False
            elif char in NEEDS_QUOTES:
                field_needs_quotes = True
            position += 1
        elif at_field_start and char == '"':
            in_quotes = field_quoted = True
            at_field_start = False
            position += 1
        elif char == ",":
            finish_field()
            at_field_start = True
            position += 1
        elif char in "\r\n":
            ending = "\r\n" if text.startswith("\r\n", position) else char
            endings[ending] += 1
            finish_field()
            at_field_start = True
            position += len(ending)
        else:
            at_field_start = False
            position += 1

    if text and not text.endswith(("\r", "\n")):
        finish_field()

    if quoted == 0:
        style: Quoting = "none"
    elif unquoted == 0:
        style = "all"
    elif unnecessary == 0:
        style = "minimal"
    else:
        style = "mixed"
    return endings, style


def detect_format(text: str) -> FileFormat:
    """Detect a file's format details from its full text (decoded as UTF-8, unchanged)."""
    byte_order_mark = text.startswith(BYTE_ORDER_MARK)
    if byte_order_mark:
        text = text[1:]

    if '"' in text:
        endings, quoting = _scan_quoted(text)
    else:
        # No quotes, so every line break is between rows, and counting is quick.
        windows = text.count("\r\n")
        endings = Counter(
            {
                "\r\n": windows,
                "\n": text.count("\n") - windows,
                "\r": text.count("\r") - windows,
            }
        )
        quoting = "none"

    found = [(ending, count) for ending, count in endings.most_common() if count]
    return FileFormat(
        byte_order_mark=byte_order_mark,
        line_ending=found[0][0] if found else "\n",
        mixed_line_endings=len(found) > 1,
        final_line_break=text.endswith(("\r", "\n")),
        quoting=quoting,
    )


def format_csv(
    header: Sequence[str], rows: Iterable[Sequence[Any]], file_format: FileFormat
) -> str:
    """Write a header and rows as CSV text, reproducing the given format details."""
    output = io.StringIO()
    writer = csv.writer(
        output,
        lineterminator=file_format.line_ending,
        quoting=csv.QUOTE_ALL if file_format.quoting == "all" else csv.QUOTE_MINIMAL,
    )
    writer.writerow(header)
    writer.writerows(rows)
    text = output.getvalue()
    if not file_format.final_line_break and text.endswith(file_format.line_ending):
        text = text[: -len(file_format.line_ending)]
    return (BYTE_ORDER_MARK if file_format.byte_order_mark else "") + text
