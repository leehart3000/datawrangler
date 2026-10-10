from pathlib import Path

import pytest
from playwright.sync_api import Page, ViewportSize, expect

pytestmark = pytest.mark.e2e

# iPhone SE, one of the narrowest common phones.
PHONE: ViewportSize = {"width": 375, "height": 667}


# Lists elements that stick out past the right edge of the screen, ignoring things
# inside a sideways-scrolling box (like the preview table), which is allowed.
FIND_TOO_WIDE = """
() => {
  const limit = document.documentElement.clientWidth;
  return [...document.querySelectorAll("body *")]
    .filter((el) => el.getBoundingClientRect().right > limit + 1)
    .filter((el) => !el.parentElement.closest(".overflow-x-auto"))
    .map((el) => {
      const name = el.tagName.toLowerCase() + (el.id ? "#" + el.id : "");
      return name + ' "' + (el.textContent || "").trim().slice(0, 50) + '"';
    });
}
"""


def page_scrolls_sideways(page: Page) -> bool:
    """True if anything makes the whole page wider than the screen."""
    return bool(
        page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
    )


def too_wide(page: Page) -> list[str]:
    """The elements sticking out past the edge of the screen, to explain a failure."""
    result: list[str] = page.evaluate(FIND_TOO_WIDE)
    return result


@pytest.fixture
def wide_csv(tmp_path: Path) -> Path:
    """A deliberately awkward file: many columns, long values, and a long name."""
    header = ",".join(f"a_rather_long_column_name_{n}" for n in range(1, 13))
    row = ",".join(f"a_long_value_without_any_spaces_{n}" for n in range(1, 13))
    path = tmp_path / "a_very_long_file_name_without_any_spaces_final_version_2.csv"
    path.write_text(header + "\n" + (row + "\n") * 5)
    return path


def test_home_page_fits_a_phone(page: Page, live_server: str, wide_csv: Path) -> None:
    page.set_viewport_size(PHONE)
    page.goto(live_server)
    assert not page_scrolls_sideways(page), too_wide(page)

    page.get_by_label("Choose a file").set_input_files(wide_csv)
    expect(page.locator("#result table")).to_be_visible()
    assert not page_scrolls_sideways(page), too_wide(page)


def test_privacy_page_fits_a_phone(page: Page, live_server: str) -> None:
    page.set_viewport_size(PHONE)
    page.goto(f"{live_server}/privacy")
    assert not page_scrolls_sideways(page), too_wide(page)
