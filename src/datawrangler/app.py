import hashlib
import tempfile
from pathlib import Path

import duckdb
from flask import Flask, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from datawrangler.wrangling import preview_csv

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _file_fingerprint(path: Path) -> str:
    """Return a short fingerprint of a file's contents, or "dev" if it doesn't exist."""
    if not path.exists():
        return "dev"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def _result_template() -> str:
    """For htmx requests, reply with just the result section; otherwise the whole page."""
    if request.headers.get("HX-Request") == "true":
        return "_result.html"
    return "index.html"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["TRUSTED_HOSTS"] = ["datawrangler.org", "localhost", "127.0.0.1"]
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    # Lets templates add a fingerprint to the CSS address, so browsers fetch new versions.
    css_path = Path(app.root_path) / "static" / "css" / "app.css"
    app.jinja_env.globals["css_version"] = _file_fingerprint(css_path)

    # Trust the X-Forwarded-Host and X-Forwarded-Proto labels from the Cloudflare Worker.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_host=1, x_proto=1)  # type: ignore[method-assign]

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.post("/preview")
    def preview() -> tuple[str, int]:
        template = _result_template()
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return render_template(template, error="Please choose a CSV file."), 400

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "upload.csv"
            upload.save(path)
            try:
                result = preview_csv(path)
            except duckdb.Error:
                error = "Sorry, we couldn't read that file as a CSV."
                return render_template(template, error=error), 400

        return render_template(template, preview=result, filename=upload.filename), 200

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(error: RequestEntityTooLarge) -> tuple[str, int]:
        message = "That file is too big. The limit is 10 MB."
        return render_template(_result_template(), error=message), 413

    return app
