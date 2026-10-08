import threading
from collections.abc import Iterator

import pytest
from werkzeug.serving import make_server

from datawrangler.app import create_app


@pytest.fixture(scope="session")
def live_server() -> Iterator[str]:
    """Run the app in the background for browser tests, and return its address."""
    server = make_server("127.0.0.1", 0, create_app())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
