import tempfile
from pathlib import Path

import duckdb
from flask import Flask, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from datawrangler.wrangling import preview_csv

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["TRUSTED_HOSTS"] = ["datawrangler.org", "localhost", "127.0.0.1"]
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    # Trust the X-Forwarded-Host and X-Forwarded-Proto labels from the Cloudflare Worker.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_host=1, x_proto=1)  # type: ignore[method-assign]

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.post("/preview")
    def preview() -> str | tuple[str, int]:
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return render_template("index.html", error="Please choose a CSV file."), 400

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "upload.csv"
            upload.save(path)
            try:
                result = preview_csv(path)
            except duckdb.Error:
                error = "Sorry, we couldn't read that file as a CSV."
                return render_template("index.html", error=error), 400

        return render_template("preview.html", preview=result, filename=upload.filename)

    return app
