from datawrangler.app import _show_edge_spaces


def test_extra_spaces_are_made_visible() -> None:
    html = str(_show_edge_spaces(" Ada  "))
    assert html.count('title="Extra space"') == 3
    assert "Ada" in html


def test_spaces_in_the_middle_are_left_alone() -> None:
    assert str(_show_edge_spaces("New York")) == "New York"


def test_values_are_still_made_safe() -> None:
    html = str(_show_edge_spaces(" <script>"))
    assert "&lt;script&gt;" in html
    assert "<script>" not in html
