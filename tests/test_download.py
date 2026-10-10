import io

from datawrangler.app import create_app
from datawrangler.fileformat import file_fingerprint


def test_download_returns_cleaned_csv() -> None:
    client = create_app().test_client()
    data = {
        "file": (io.BytesIO(b"name,id\n Ada ,007\n Ada ,007\n"), "people.csv"),
        "trim_whitespace": "on",
        "remove_duplicates": "on",
    }
    response = client.post("/download", data=data, content_type="multipart/form-data")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "people-cleaned.csv" in response.headers["Content-Disposition"]
    # Leading zeros are kept, spaces are trimmed, and the duplicate is gone.
    assert response.data.decode().splitlines() == ["name,id", "Ada,007"]


def test_download_without_file_shows_error() -> None:
    client = create_app().test_client()
    response = client.post("/download", data={}, content_type="multipart/form-data")
    assert response.status_code == 400
    assert b"Please choose a file." in response.data


def test_download_can_change_the_line_endings() -> None:
    text = "a,b\n1,2\n"
    data = {
        "file": (io.BytesIO(text.encode()), "data.csv"),
        "format_for": file_fingerprint(text.encode()) + ":comma",
        "line_ending": "crlf",
        "quoting": "minimal",
        "final_line_break": "on",
    }
    client = create_app().test_client()
    response = client.post("/download", data=data, content_type="multipart/form-data")
    assert response.status_code == 200
    assert response.data == b"a,b\r\n1,2\r\n"


def test_mixed_line_endings_are_refused_with_a_clear_message() -> None:
    data = {"file": (io.BytesIO(b"a\r\n1\n"), "data.csv")}
    client = create_app().test_client()
    response = client.post("/download", data=data, content_type="multipart/form-data")
    assert response.status_code == 400
    assert b"line endings" in response.data


def test_empty_lines_between_rows_are_refused() -> None:
    data = {"file": (io.BytesIO(b"a,b\n1,2\n\n3,4\n"), "data.csv")}
    client = create_app().test_client()
    response = client.post("/download", data=data, content_type="multipart/form-data")
    assert response.status_code == 400
    assert b"empty lines between rows" in response.data


def test_download_can_change_the_separator_and_name() -> None:
    text = "a,b\n1,2\n"
    data = {
        "file": (io.BytesIO(text.encode()), "data.csv"),
        "format_for": file_fingerprint(text.encode()) + ":comma",
        "output_separator": "tab",
        "line_ending": "lf",
        "quoting": "minimal",
        "final_line_break": "on",
        "download_name": "my results",
    }
    client = create_app().test_client()
    response = client.post("/download", data=data, content_type="multipart/form-data")
    assert response.status_code == 200
    assert response.data == b"a\tb\n1\t2\n"
    assert 'filename="my_results.tsv"' in response.headers["Content-Disposition"]


def test_the_separator_can_be_corrected() -> None:
    # Commas and semicolons both appear once per line; detection picks commas.
    text = "a,b;c\n1,2;3\n"
    data = {
        "file": (io.BytesIO(text.encode()), "data.csv"),
        "separator_for": file_fingerprint(text.encode()),
        "separator": "semicolon",
    }
    client = create_app().test_client()
    response = client.post(
        "/preview",
        data=data,
        content_type="multipart/form-data",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert b"(detected)" in response.data
    assert b"a,b" in response.data  # Read with semicolons, "a,b" is one column name.


def test_a_name_suggesting_another_separator_is_pointed_out() -> None:
    data = {"file": (io.BytesIO(b"a,b\n1,2\n"), "data.tsv")}
    client = create_app().test_client()
    response = client.post(
        "/preview",
        data=data,
        content_type="multipart/form-data",
        headers={"HX-Request": "true"},
    )
    assert b"usually means it&#39;s separated by tabs" in response.data


def test_the_extension_can_be_chosen() -> None:
    text = "a,b\n1,2\n"
    data = {
        "file": (io.BytesIO(text.encode()), "messy.tsv"),
        "format_for": file_fingerprint(text.encode()) + ":comma",
        "line_ending": "lf",
        "quoting": "minimal",
        "final_line_break": "on",
        "download_name": "messy-cleaned",
        "download_extension": ".csv",
    }
    client = create_app().test_client()
    response = client.post("/download", data=data, content_type="multipart/form-data")
    assert response.status_code == 200
    assert 'filename="messy-cleaned.csv"' in response.headers["Content-Disposition"]
