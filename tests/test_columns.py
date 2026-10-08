import io
from pathlib import Path

import pytest

from datawrangler.app import create_app
from datawrangler.wrangling import (
    CleaningOptions,
    NoColumnsKeptError,
    clean_csv,
    columns_signature,
)

CSV = "name,city,age\nAda,London,36\nAda,Leeds,36\n"
SIGNATURE = columns_signature(["name", "city", "age"])


def _write(tmp_path: Path) -> Path:
    path = tmp_path / "people.csv"
    path.write_text(CSV)
    return path


def test_keeps_only_the_chosen_columns(tmp_path: Path) -> None:
    options = CleaningOptions(keep_columns=[0, 2], columns_for=SIGNATURE)
    preview, report = clean_csv(_write(tmp_path), options)
    assert [column.name for column in preview.columns] == ["name", "age"]
    assert preview.all_columns == ["name", "city", "age"]
    assert report.columns_removed == 1


def test_duplicates_are_judged_on_the_kept_columns(tmp_path: Path) -> None:
    options = CleaningOptions(
        keep_columns=[0, 2], columns_for=SIGNATURE, remove_duplicates=True
    )
    preview, report = clean_csv(_write(tmp_path), options)
    assert preview.rows == [("Ada", "36")]
    assert report.duplicates_removed == 1


def test_choices_for_a_different_file_are_ignored(tmp_path: Path) -> None:
    options = CleaningOptions(keep_columns=[0], columns_for="another-file")
    preview, _ = clean_csv(_write(tmp_path), options)
    assert len(preview.columns) == 3


def test_unticking_every_column_is_an_error(tmp_path: Path) -> None:
    options = CleaningOptions(keep_columns=[], columns_for=SIGNATURE)
    with pytest.raises(NoColumnsKeptError):
        clean_csv(_write(tmp_path), options)


def test_download_includes_only_the_chosen_columns() -> None:
    client = create_app().test_client()
    data = {
        "file": (io.BytesIO(CSV.encode()), "people.csv"),
        "columns_for": SIGNATURE,
        "keep_columns": ["0", "2"],
    }
    response = client.post("/download", data=data, content_type="multipart/form-data")
    assert response.status_code == 200
    assert response.data.decode().splitlines()[0] == "name,age"


def test_no_columns_shows_message_and_tick_boxes() -> None:
    client = create_app().test_client()
    data = {"file": (io.BytesIO(CSV.encode()), "people.csv"), "columns_for": SIGNATURE}
    response = client.post(
        "/preview",
        data=data,
        content_type="multipart/form-data",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 400
    assert b"Please keep at least one column." in response.data
    assert b'name="keep_columns"' in response.data
