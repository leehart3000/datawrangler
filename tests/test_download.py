import io

from datawrangler.app import create_app


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
    assert b"Please choose a CSV file." in response.data
