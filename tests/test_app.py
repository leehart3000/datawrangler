import re

import pytest

from datawrangler.app import create_app


def test_home_page_shows_header_and_heading() -> None:
    client = create_app().test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b">Data<span" in response.data
    assert b"Clean, check and prepare your data.</h1>" in response.data
    assert b'rel="icon"' in response.data


def test_logo_is_served() -> None:
    client = create_app().test_client()
    response = client.get("/static/img/logo.svg")
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"


def test_favicon_is_linked_and_served() -> None:
    client = create_app().test_client()
    page = client.get("/")
    assert b"img/favicon.svg" in page.data
    response = client.get("/static/img/favicon.svg")
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"


def test_request_via_cloudflare_is_accepted() -> None:
    client = create_app().test_client()
    response = client.get("/", headers={"X-Forwarded-Host": "datawrangler.org"})
    assert response.status_code == 200


def test_unknown_host_is_rejected() -> None:
    client = create_app().test_client()
    response = client.get("/", headers={"X-Forwarded-Host": "evil.example"})
    assert response.status_code == 400


def test_privacy_page() -> None:
    response = create_app().test_client().get("/privacy")
    assert response.status_code == 200
    assert b"never stored" in response.data


EXTERNAL_LINK = re.compile(rb'<a\b[^>]*href="https?://[^"]*"[^>]*>')


@pytest.mark.parametrize("path", ["/", "/privacy"])
def test_external_links_open_in_new_tab(path: str) -> None:
    client = create_app().test_client()
    page = client.get(path).data
    links = EXTERNAL_LINK.findall(page)
    assert links
    for link in links:
        assert b'target="_blank"' in link
        assert b'rel="noopener"' in link
