from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

MESSY_CSV = "name,city\n Ada , London\nAlan,Leeds\n Ada , London\n,\nAlan ,Leeds\n"


@pytest.fixture
def messy_csv(tmp_path: Path) -> Path:
    path = tmp_path / "messy.csv"
    path.write_text(MESSY_CSV)
    return path


def test_buttons_respond_to_choosing_a_file(
    page: Page, live_server: str, messy_csv: Path
) -> None:
    page.goto(live_server)
    preview = page.get_by_role("button", name="Refresh preview")
    download = page.get_by_role("button", name="Download cleaned CSV")
    hint = page.get_by_text("Choose a file to get started.")

    expect(preview).to_be_disabled()
    expect(download).to_have_count(0)
    expect(hint).to_be_visible()
    expect(page.get_by_label("Remove empty rows")).to_be_disabled()

    page.get_by_label("Choose a CSV file").set_input_files(messy_csv)

    expect(preview).to_be_enabled()
    expect(download).to_be_enabled()
    expect(hint).to_be_hidden()
    expect(page.get_by_label("Remove empty rows")).to_be_enabled()


def test_preview_updates_automatically(
    page: Page, live_server: str, messy_csv: Path
) -> None:
    page.goto(live_server)

    # Choosing a file shows the preview straight away, without clicking anything.
    page.get_by_label("Choose a CSV file").set_input_files(messy_csv)
    expect(page.get_by_text("5 rows, 2 columns.")).to_be_visible()

    # Ticking a box updates it.
    page.get_by_label("Remove duplicate rows").check()
    expect(page.get_by_text("Removed 1 duplicate row.")).to_be_visible()
    expect(page.get_by_text("4 rows, 2 columns.")).to_be_visible()


def test_download_saves_the_cleaned_file(
    page: Page, live_server: str, messy_csv: Path
) -> None:
    page.goto(live_server)
    page.get_by_label("Choose a CSV file").set_input_files(messy_csv)
    page.get_by_label("Trim extra spaces").check()
    page.get_by_label("Remove empty rows").check()
    page.get_by_label("Remove duplicate rows").check()

    expect(page.get_by_text("Removed 2 duplicate rows.")).to_be_visible()
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Download cleaned CSV").click()
    download = download_info.value

    assert download.suggested_filename == "messy-cleaned.csv"
    lines = Path(download.path()).read_text().splitlines()
    assert lines == ["name,city", "Ada,London", "Alan,Leeds"]


def test_unticking_a_column_removes_it(
    page: Page, live_server: str, messy_csv: Path
) -> None:
    page.goto(live_server)
    page.get_by_label("Choose a CSV file").set_input_files(messy_csv)
    page.get_by_label("city", exact=True).uncheck()
    expect(page.get_by_text("Removed 1 column.")).to_be_visible()

    with page.expect_download() as download_info:
        page.get_by_role("button", name="Download cleaned CSV").click()
    lines = Path(download_info.value.path()).read_text().splitlines()
    assert lines[0] == "name"


def test_file_errors_appear_by_the_file_chooser(
    page: Page, live_server: str, tmp_path: Path
) -> None:
    mixed = tmp_path / "mixed.csv"
    mixed.write_bytes(b"name,city\r\nAda,London\nAlan,Leeds\n")
    page.goto(live_server)
    page.get_by_label("Choose a CSV file").set_input_files(mixed)
    expect(page.locator("#file-error")).to_contain_text("mixes different line endings")
