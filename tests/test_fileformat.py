from datawrangler.fileformat import FileFormat, detect_format, format_csv


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
