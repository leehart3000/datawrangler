import pytest

from datawrangler.fileformat import (
    ChoiceNeededError,
    FileFormat,
    OutputChoices,
    detect_format,
    detect_separator,
    download_extension,
    effective_choices,
    format_csv,
    to_file_format,
)


def test_plain_file() -> None:
    assert detect_format("a,b\n1,2\n") == FileFormat()


def test_windows_line_endings_and_byte_order_mark() -> None:
    detected = detect_format("\ufeffa,b\r\n1,2\r\n")
    assert detected.byte_order_mark
    assert detected.line_ending == "\r\n"
    assert not detected.mixed_line_endings


def test_mixed_line_endings() -> None:
    assert detect_format("a\r\nb\nc\n").mixed_line_endings


def test_no_final_line_break() -> None:
    assert not detect_format("a,b\n1,2").final_line_break


def test_line_break_inside_quotes_is_not_a_line_ending() -> None:
    detected = detect_format('a,b\r\n1,"x\ny"\r\n')
    assert detected.line_ending == "\r\n"
    assert not detected.mixed_line_endings


def test_quoting_styles() -> None:
    assert detect_format("a,b\n1,2\n").quoting == "none"
    assert detect_format('a,b\n1,"x, y"\n').quoting == "minimal"
    assert detect_format('"a","b"\n"1","2"\n').quoting == "all"
    assert detect_format('"a",b\n1,2\n').quoting == "mixed"


def test_format_csv_reproduces_the_details() -> None:
    file_format = FileFormat(
        byte_order_mark=True, line_ending="\r\n", final_line_break=False, quoting="all"
    )
    assert format_csv(["a"], [["1"]], file_format) == '\ufeff"a"\r\n"1"'


def test_settings_default_to_the_detected_format() -> None:
    detected = detect_format("a\r\n1\r\n")
    choices = effective_choices(detected, OutputChoices(), "this-file")
    assert choices.line_ending == "crlf"
    assert choices.format_for == "this-file:comma"


def test_settings_for_another_file_are_ignored() -> None:
    detected = detect_format("a\r\n1\r\n")
    submitted = OutputChoices(format_for="another-file", line_ending="lf")
    assert effective_choices(detected, submitted, "this-file").line_ending == "crlf"


def test_mixed_line_endings_need_a_choice() -> None:
    detected = detect_format("a\r\n1\n")
    choices = effective_choices(detected, OutputChoices(), "this-file")
    with pytest.raises(ChoiceNeededError):
        to_file_format(choices, detected)


def test_settings_from_the_page_are_used() -> None:
    submitted = OutputChoices(
        format_for="this-file:comma",
        line_ending="lf",
        quoting="all",
        byte_order_mark=True,
        final_line_break=False,
    )
    detected = detect_format("a\r\n1\r\n")
    choices = effective_choices(detected, submitted, "this-file")
    file_format = to_file_format(choices, detected)
    assert file_format == FileFormat(
        byte_order_mark=True, line_ending="\n", final_line_break=False, quoting="all"
    )


def test_empty_lines_at_the_end_are_counted() -> None:
    detected = detect_format("a,b\n1,2\n\n\n")
    assert detected.trailing_blank_lines == 2
    assert detected.blank_lines_inside == 0


def test_empty_lines_between_rows_are_counted() -> None:
    assert detect_format("a,b\n\n1,2\n").blank_lines_inside == 1


def test_empty_lines_inside_quoted_values_do_not_count() -> None:
    detected = detect_format('a,b\n1,"x\n\ny"\n')
    assert detected.blank_lines_inside == 0
    assert detected.trailing_blank_lines == 0


def test_format_csv_adds_the_empty_lines_back() -> None:
    file_format = FileFormat(trailing_blank_lines=2)
    assert format_csv(["a"], [["1"]], file_format) == "a\n1\n\n\n"


def test_separator_commas() -> None:
    assert detect_separator("a,b,c\n1,2,3\n") == ","


def test_separator_semicolons() -> None:
    text = "Username; Identifier;First name\nbooker12;9012;Rachel\n\n\n"
    assert detect_separator(text) == ";"


def test_separator_tabs() -> None:
    assert detect_separator("a\tb\n1\t2\n") == "\t"


def test_separator_pipes() -> None:
    assert detect_separator("a|b\n1|2\n") == "|"


def test_separator_ignores_commas_inside_values() -> None:
    assert detect_separator("name;note\nAda;Hello, world\nAlan;Hi\n") == ";"


def test_separator_falls_back_to_the_header() -> None:
    # The line break inside quotes upsets the line-by-line count, so the header decides.
    assert detect_separator('a;b\n1;"x\ny"\n') == ";"


def test_download_extension_rules() -> None:
    assert (
        download_extension(".tsv", ",", ",") == ".tsv"
    )  # Unchanged: keep the original.
    assert download_extension(".csv", ",", "\t") == ".tsv"  # Changed to tabs.
    assert download_extension(".tsv", "\t", ",") == ".csv"  # Changed to commas.
    assert (
        download_extension(".txt", ",", ";") == ".txt"
    )  # No standard: keep the original.
    assert download_extension("", ",", ",") == ".csv"  # No original extension.
