"""Detecting a delimited file's format details, so downloads can reproduce them exactly.

Format details aren't values, but they're part of the file, so the rule is:
detect what the original does, reproduce it by default, and only change it
when the user explicitly chooses to.
"""

import csv
import hashlib
import io
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

BYTE_ORDER_MARK = "\ufeff"
LINE_BREAK = re.compile(r"\r\n|\n|\r")

Quoting = Literal["none", "minimal", "all", "mixed"]
LineEndingCode = Literal["lf", "crlf", "cr"]
LINE_ENDING_CODES: dict[str, LineEndingCode] = {"\n": "lf", "\r\n": "crlf", "\r": "cr"}
LINE_ENDINGS: dict[LineEndingCode, str] = {
    code: end for end, code in LINE_ENDING_CODES.items()
}
LINE_ENDING_LABELS: dict[LineEndingCode, str] = {
    "lf": "Unix and Mac (LF)",
    "crlf": "Windows (CRLF)",
    "cr": "Old Mac (CR)",
}
QUOTING_DESCRIPTIONS: dict[str, str] = {
    "none": "has no quoted values",
    "minimal": "quotes values only where needed",
    "all": "quotes every value",
    "mixed": "quotes some values but not others",
}

SeparatorCode = Literal["comma", "semicolon", "tab", "pipe"]
SEPARATORS: dict[SeparatorCode, str] = {
    "comma": ",",
    "semicolon": ";",
    "tab": "\t",
    "pipe": "|",
}
SEPARATOR_CODES: dict[str, SeparatorCode] = {
    sep: code for code, sep in SEPARATORS.items()
}
SEPARATOR_DESCRIPTIONS: dict[SeparatorCode, str] = {
    "comma": "commas",
    "semicolon": "semicolons",
    "tab": "tabs",
    "pipe": "pipes (|)",
}
SEPARATOR_LABELS: dict[SeparatorCode, str] = {
    "comma": "Commas (,)",
    "semicolon": "Semicolons (;)",
    "tab": "Tabs",
    "pipe": "Pipes (|)",
}


@dataclass(frozen=True)
class FileFormat:
    delimiter: str = ","
    byte_order_mark: bool = False
    line_ending: str = "\n"
    mixed_line_endings: bool = False
    final_line_break: bool = True
    quoting: Quoting = "none"
    trailing_blank_lines: int = 0
    blank_lines_inside: int = 0

    @property
    def line_ending_code(self) -> LineEndingCode:
        return LINE_ENDING_CODES[self.line_ending]

    @property
    def separator_code(self) -> SeparatorCode:
        return SEPARATOR_CODES[self.delimiter]


def _count_outside_quotes(line: str, char: str) -> int:
    """Count a character in a line, ignoring any inside quoted values."""
    count, in_quotes = 0, False
    for current in line:
        if current == '"':
            in_quotes = not in_quotes
        elif current == char and not in_quotes:
            count += 1
    return count


def detect_separator(text: str, sample_lines: int = 20) -> str:
    """Guess which separator a file uses.

    In a real table, the separator appears the same number of times on every line.
    So the first choice is a separator that appears equally (and at least once) on
    each of the first lines. If none does, use whichever appears most in the header
    row. If none appears at all, the file has a single column: use a comma.
    """
    if text.startswith(BYTE_ORDER_MARK):
        text = text[1:]
    lines = [line for line in LINE_BREAK.split(text) if line][:sample_lines]
    if not lines:
        return ","

    best, best_count = "", 0
    for candidate in SEPARATORS.values():
        counts = {_count_outside_quotes(line, candidate) for line in lines}
        if len(counts) == 1:
            count = counts.pop()
            if count > best_count:
                best, best_count = candidate, count
    if best:
        return best

    header_counts = {
        sep: _count_outside_quotes(lines[0], sep) for sep in SEPARATORS.values()
    }
    most_common = max(header_counts, key=lambda sep: header_counts[sep])
    return most_common if header_counts[most_common] else ","


def _blank_line_counts(blank: list[bool]) -> tuple[int, int]:
    """Count the empty lines at the end, and the empty lines anywhere else."""
    trailing = 0
    for is_blank in reversed(blank):
        if not is_blank:
            break
        trailing += 1
    return trailing, sum(blank) - trailing


def _scan_quoted(text: str, delimiter: str) -> tuple[Counter[str], Quoting, list[bool]]:
    """Walk through a file that contains quotes, field by field.

    Returns the line endings found between rows, the quoting style, and whether
    each line is empty. Line breaks inside quoted values are part of the value,
    so they don't count as line endings or empty lines.
    """
    needs_quotes = frozenset({delimiter, '"', "\r", "\n"})
    endings: Counter[str] = Counter()
    blank: list[bool] = []
    quoted = unquoted = unnecessary = 0
    in_quotes = field_quoted = field_needs_quotes = False
    at_field_start = True
    position, length, line_start = 0, len(text), 0

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
            elif char in needs_quotes:
                field_needs_quotes = True
            position += 1
        elif at_field_start and char == '"':
            in_quotes = field_quoted = True
            at_field_start = False
            position += 1
        elif char == delimiter:
            finish_field()
            at_field_start = True
            position += 1
        elif char in "\r\n":
            ending = "\r\n" if text.startswith("\r\n", position) else char
            endings[ending] += 1
            blank.append(position == line_start)
            finish_field()
            at_field_start = True
            position += len(ending)
            line_start = position
        else:
            at_field_start = False
            position += 1

    if text and not text.endswith(("\r", "\n")):
        finish_field()
        blank.append(False)

    if quoted == 0:
        style: Quoting = "none"
    elif unquoted == 0:
        style = "all"
    elif unnecessary == 0:
        style = "minimal"
    else:
        style = "mixed"
    return endings, style, blank


def detect_format(text: str, delimiter: str = ",") -> FileFormat:
    """Detect a file's format details from its full text (decoded as UTF-8, unchanged)."""
    byte_order_mark = text.startswith(BYTE_ORDER_MARK)
    if byte_order_mark:
        text = text[1:]

    if '"' in text:
        endings, quoting, blank = _scan_quoted(text, delimiter)
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
        lines = LINE_BREAK.split(text)
        if text.endswith(("\r", "\n")):
            lines.pop()  # Nothing comes after the final line break.
        blank = [line == "" for line in lines]

    trailing, inside = _blank_line_counts(blank) if text else (0, 0)
    found = [(ending, count) for ending, count in endings.most_common() if count]
    return FileFormat(
        delimiter=delimiter,
        byte_order_mark=byte_order_mark,
        line_ending=found[0][0] if found else "\n",
        mixed_line_endings=len(found) > 1,
        final_line_break=text.endswith(("\r", "\n")),
        quoting=quoting,
        trailing_blank_lines=trailing,
        blank_lines_inside=inside,
    )


def format_csv(
    header: Sequence[str], rows: Iterable[Sequence[Any]], file_format: FileFormat
) -> str:
    """Write a header and rows as delimited text, reproducing the given format details."""
    output = io.StringIO()
    writer = csv.writer(
        output,
        delimiter=file_format.delimiter,
        lineterminator=file_format.line_ending,
        quoting=csv.QUOTE_ALL if file_format.quoting == "all" else csv.QUOTE_MINIMAL,
    )
    writer.writerow(header)
    writer.writerows(rows)
    text = output.getvalue()
    if not file_format.final_line_break and text.endswith(file_format.line_ending):
        text = text[: -len(file_format.line_ending)]
    if file_format.final_line_break and file_format.trailing_blank_lines:
        text += file_format.line_ending * file_format.trailing_blank_lines
    return (BYTE_ORDER_MARK if file_format.byte_order_mark else "") + text


class InputChoices(BaseModel):
    """How to read the uploaded file, as set on the page."""

    separator_for: str | None = None
    separator: SeparatorCode | None = None


class OutputChoices(BaseModel):
    """The download's format details, as set on the page."""

    format_for: str | None = None
    output_separator: SeparatorCode | None = None
    line_ending: LineEndingCode | None = None
    quoting: Literal["minimal", "all"] | None = None
    byte_order_mark: bool = False
    final_line_break: bool = False
    keep_trailing_blank_lines: bool = False
    download_name: str | None = None
    download_extension: Literal["auto", ".csv", ".tsv", ".txt"] = "auto"


class ChoiceNeededError(Exception):
    """The original file is mixed in some way, so the user must choose."""


def file_fingerprint(data: bytes) -> str:
    """A short fingerprint of a file's whole contents, to tell when a different file is chosen."""
    return hashlib.sha256(data).hexdigest()[:16]


def effective_choices(
    detected: FileFormat,
    submitted: OutputChoices,
    fingerprint: str,
    default_name: str = "data-cleaned",
) -> OutputChoices:
    """Use the settings from the page if they were made for this file, read this way.

    Otherwise, match the original. The settings remember the separator the file was
    read with, so correcting that resets them. Where the original is mixed, the
    setting is left empty, so the user has to choose.
    """
    key = f"{fingerprint}:{detected.separator_code}"
    if submitted.format_for == key:
        return submitted
    quoting: Literal["minimal", "all"] | None
    if detected.quoting == "mixed":
        quoting = None
    elif detected.quoting == "all":
        quoting = "all"
    else:
        quoting = "minimal"
    return OutputChoices(
        format_for=key,
        output_separator=detected.separator_code,
        line_ending=None if detected.mixed_line_endings else detected.line_ending_code,
        quoting=quoting,
        byte_order_mark=detected.byte_order_mark,
        final_line_break=detected.final_line_break,
        keep_trailing_blank_lines=detected.trailing_blank_lines > 0,
        download_name=default_name,
    )


def to_file_format(choices: OutputChoices, detected: FileFormat) -> FileFormat:
    """Turn the settings into the format to write, checking every choice has been made."""
    if choices.line_ending is None:
        raise ChoiceNeededError(
            "Your file mixes different line endings. "
            "Please choose which to use in the download."
        )
    if choices.quoting is None:
        raise ChoiceNeededError(
            "Your file quotes some values but not others. "
            "Please choose how to quote values in the download."
        )
    delimiter = (
        SEPARATORS[choices.output_separator]
        if choices.output_separator
        else detected.delimiter
    )
    return FileFormat(
        delimiter=delimiter,
        byte_order_mark=choices.byte_order_mark,
        line_ending=LINE_ENDINGS[choices.line_ending],
        final_line_break=choices.final_line_break,
        quoting=choices.quoting,
        trailing_blank_lines=(
            detected.trailing_blank_lines if choices.keep_trailing_blank_lines else 0
        ),
    )


def download_extension(
    original_suffix: str, input_delimiter: str, output_delimiter: str
) -> str:
    """Choose the download's extension.

    Keep the original's, unless the separator has been changed to tabs or commas,
    in which case use the standard extension for those.
    """
    if output_delimiter == input_delimiter and original_suffix:
        return original_suffix
    if output_delimiter == "\t":
        return ".tsv"
    if output_delimiter == ",":
        return ".csv"
    return original_suffix or ".csv"
