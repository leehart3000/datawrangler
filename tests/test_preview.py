import io
from pathlib import Path

from datawrangler.app import create_app
from datawrangler.wrangling import preview_csv


def test_preview_csv_reads_columns_and_rows(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    path.write_text("name,age\nAda,36\nAlan,41\n")
    result = preview_csv(path)
    assert [column.name for column in result.columns] == ["name", "age"]
    assert result.row_count == 2
    assert result.rows[0] == ("Ada", "36")
    assert [column.type for column in result.columns] == ["VARCHAR", "BIGINT"]


def test_preview_page_shows_uploaded_data() -> None:
    client = create_app().test_client()
    data = {"file": (io.BytesIO(b"name,age\nAda,36\nAlan,41\n"), "people.csv")}
    response = client.post("/preview", data=data, content_type="multipart/form-data")
    assert response.status_code == 200
    assert b"people.csv" in response.data
    assert b"Ada" in response.data


def test_preview_without_file_shows_error() -> None:
    client = create_app().test_client()
    response = client.post("/preview", data={}, content_type="multipart/form-data")
    assert response.status_code == 400
    assert b"Please choose a CSV file." in response.data


def test_htmx_preview_returns_only_the_result() -> None:
    client = create_app().test_client()
    data = {"file": (io.BytesIO(b"name,age\nAda,36\nAlan,41\n"), "people.csv")}
    response = client.post(
        "/preview",
        data=data,
        content_type="multipart/form-data",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert b"Ada" in response.data
    assert b"<html" not in response.data


def test_too_large_upload_is_rejected() -> None:
    client = create_app().test_client()
    big_file = io.BytesIO(b"a" * (10 * 1024 * 1024 + 1))
    data = {"file": (big_file, "big.csv")}
    response = client.post("/preview", data=data, content_type="multipart/form-data")
    assert response.status_code == 413
    assert b"too big" in response.data
