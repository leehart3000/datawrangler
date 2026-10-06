from datawrangler.app import create_app


def test_home_page_shows_title() -> None:
    client = create_app().test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"DataWrangler</h1>" in response.data
    assert b"/static/css/app.css?v=" in response.data


def test_request_via_cloudflare_is_accepted() -> None:
    client = create_app().test_client()
    response = client.get("/", headers={"X-Forwarded-Host": "datawrangler.org"})
    assert response.status_code == 200


def test_unknown_host_is_rejected() -> None:
    client = create_app().test_client()
    response = client.get("/", headers={"X-Forwarded-Host": "evil.example"})
    assert response.status_code == 400
