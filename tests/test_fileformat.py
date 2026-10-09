import pytest

from datawrangler.fileformat import (
    ChoiceNeededError,
    FileFormat,
    OutputChoices,
    detect_format,
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
    assert choices.format_for == "this-file"


def test_settings_for_another_file_are_ignored() -> None:
    detected = detect_format("a\r\n1\r\n")
    submitted = OutputChoices(format_for="another-file", line_ending="lf")
    assert effective_choices(detected, submitted, "this-file").line_ending == "crlf"


def test_mixed_line_endings_need_a_choice() -> None:
    detected = detect_format("a\r\n1\n")
    choices = effective_choices(detected, OutputChoices(), "this-file")
    with pytest.raises(ChoiceNeededError):
        to_file_format(choices)


def test_settings_from_the_page_are_used() -> None:
    submitted = OutputChoices(
        format_for="this-file",
        line_ending="lf",
        quoting="all",
        byte_order_mark=True,
        final_line_break=False,
    )
    detected = detect_format("a\r\n1\r\n")
    file_format = to_file_format(effective_choices(detected, submitted, "this-file"))
    assert file_format == FileFormat(
        byte_order_mark=True, line_ending="\n", final_line_break=False, quoting="all"
    )
