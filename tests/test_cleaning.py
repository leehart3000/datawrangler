import io
from pathlib import Path

from datawrangler.app import create_app
from datawrangler.wrangling import CleaningOptions, clean_csv

# Row 3 repeats row 1, row 4 is empty, and row 5 only repeats row 2 once trimmed.
MESSY_CSV = "name,city\n Ada , London\nAlan,Leeds\n Ada , London\n,\nAlan ,Leeds\n"


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "data.csv"
    path.write_text(text)
    return path


def test_no_options_changes_nothing(tmp_path: Path) -> None:
    preview, report = clean_csv(_write(tmp_path, MESSY_CSV), CleaningOptions())
    assert report.rows_before == 5
    assert preview.row_count == 5


def test_all_options_clean_the_data(tmp_path: Path) -> None:
    options = CleaningOptions(
        trim_whitespace=True, remove_empty_rows=True, remove_duplicates=True
    )
    preview, report = clean_csv(_write(tmp_path, MESSY_CSV), options)
    assert preview.rows == [("Ada", "London"), ("Alan", "Leeds")]
    assert report.empty_rows_removed == 1
    assert report.duplicates_removed == 2


def test_options_are_read_from_form_values() -> None:
    options = CleaningOptions.model_validate({"trim_whitespace": "on"})
    assert options.trim_whitespace is True
    assert options.remove_duplicates is False


def test_preview_page_reports_removed_duplicates() -> None:
    client = create_app().test_client()
    data = {
        "file": (io.BytesIO(b"name\nAda\nAda\n"), "names.csv"),
        "remove_duplicates": "on",
    }
    response = client.post("/preview", data=data, content_type="multipart/form-data")
    assert response.status_code == 200
    assert b"Removed 1 duplicate row." in response.data


def test_column_summary_counts_empty_and_unique(tmp_path: Path) -> None:
    preview, _ = clean_csv(_write(tmp_path, MESSY_CSV), CleaningOptions())
    name_column = preview.columns[0]
    assert name_column.empty == 1
    assert name_column.distinct == 3  # " Ada ", "Alan" and "Alan "


def test_trimming_merges_values_in_the_summary(tmp_path: Path) -> None:
    options = CleaningOptions(trim_whitespace=True)
    preview, _ = clean_csv(_write(tmp_path, MESSY_CSV), options)
    assert preview.columns[0].distinct == 2  # "Ada" and "Alan"
