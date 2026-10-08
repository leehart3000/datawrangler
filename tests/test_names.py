from pathlib import Path

from datawrangler.wrangling import (
    CleaningOptions,
    clean_csv,
    columns_signature,
    preview_csv,
    tidy_column_names,
)


def test_no_options_leave_names_alone() -> None:
    assert tidy_column_names(["  odd  name "], trim=False, snake=False) == [
        "  odd  name "
    ]


def test_tidying_trims_and_collapses_spaces() -> None:
    assert tidy_column_names(["  First   Name "], trim=True, snake=False) == [
        "First Name"
    ]


def test_lowercase_with_underscores() -> None:
    assert tidy_column_names(["First Name (UK)"], trim=False, snake=True) == [
        "first_name_uk"
    ]


def test_clashing_names_are_numbered() -> None:
    assert tidy_column_names(["Name", "name "], trim=False, snake=True) == [
        "name",
        "name_2",
    ]


def test_empty_names_get_a_placeholder() -> None:
    assert tidy_column_names(["", "  "], trim=True, snake=False) == [
        "column_1",
        "column_2",
    ]


def test_renaming_keeps_column_choices_on_original_names(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    path.write_text("First Name,Last  Name,Home City\nAda,Lovelace,London\n")
    # Use the names exactly as DuckDB reads them, as the app does.
    original = preview_csv(path).all_columns
    options = CleaningOptions(
        snake_case_column_names=True,
        keep_columns=[0, 1],
        columns_for=columns_signature(original),
    )
    preview, report = clean_csv(path, options)
    assert [column.name for column in preview.columns] == ["first_name", "last_name"]
    assert preview.kept_columns == [0, 1]
    assert report.names_changed == 2
