from datawrangler.app import create_app


def test_pages_have_security_headers() -> None:
    response = create_app().test_client().get("/")
    headers = response.headers
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "max-age=" in headers["Strict-Transport-Security"]


def test_static_files_have_security_headers() -> None:
    response = create_app().test_client().get("/static/js/htmx-2.0.10.min.js")
    assert "Content-Security-Policy" in response.headers
