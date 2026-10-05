from datawrangler.app import create_app


def test_home_page_says_hello() -> None:
    client = create_app().test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Hello from DataWrangler!" in response.data
