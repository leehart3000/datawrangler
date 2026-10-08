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


def test_buttons_are_disabled_until_a_file_is_chosen(
    page: Page, live_server: str, messy_csv: Path
) -> None:
    page.goto(live_server)
    preview = page.get_by_role("button", name="Refresh preview")
    download = page.get_by_role("button", name="Download cleaned CSV")
    hint = page.get_by_text("Choose a file to get started.")

    expect(preview).to_be_disabled()
    expect(download).to_be_disabled()
    expect(hint).to_be_visible()

    page.get_by_label("Choose a CSV file").set_input_files(messy_csv)

    expect(preview).to_be_enabled()
    expect(download).to_be_enabled()
    expect(hint).to_be_hidden()


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

    with page.expect_download() as download_info:
        page.get_by_role("button", name="Download cleaned CSV").click()
    download = download_info.value

    assert download.suggested_filename == "messy-cleaned.csv"
    lines = Path(download.path()).read_text().splitlines()
    assert lines == ["name,city", "Ada,London", "Alan,Leeds"]
