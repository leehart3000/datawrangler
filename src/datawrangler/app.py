import hashlib
import re
import tempfile
from pathlib import Path

import duckdb
from flask import Flask, Response, render_template, request
from markupsafe import Markup, escape
from pydantic import ValidationError
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

from datawrangler.wrangling import (
    CleaningOptions,
    NoColumnsKeptError,
    clean_csv,
    write_clean_csv,
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
CSV_ERROR = "Sorry, we couldn't read that file as a CSV."
EXTRA_SPACE = Markup(
    '<span class="rounded-sm bg-amber-100 text-amber-700" title="Extra space">·</span>'
)


def _show_extra_spaces(value: object) -> Markup:
    """Show extra spaces as highlighted dots: at the start or end, and repeats in the middle."""
    text = str(value)
    if not text.strip():
        return EXTRA_SPACE * len(text)
    start = len(text) - len(text.lstrip())
    end = len(text.rstrip())
    middle = str(escape(text[start:end]))
    # In each run of spaces, keep the first as a normal space and mark the rest.
    middle = re.sub(
        r"(?<= ) +", lambda match: str(EXTRA_SPACE * len(match.group())), middle
    )
    return EXTRA_SPACE * start + Markup(middle) + EXTRA_SPACE * (len(text) - end)


class UploadError(Exception):
    """A problem with what the visitor sent, with a message they can understand."""


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


def _form_data() -> dict[str, object]:
    """The form's values, with the ticked columns gathered into a list."""
    data: dict[str, object] = dict(request.form.items())
    data.pop("keep_columns", None)
    if "columns_for" in request.form:
        data["keep_columns"] = request.form.getlist("keep_columns")
    return data


def _get_upload_and_options() -> tuple[FileStorage, CleaningOptions]:
    """Read the uploaded file and the ticked cleaning options from the form."""
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        raise UploadError("Please choose a CSV file.")
    try:
        options = CleaningOptions.model_validate(_form_data())
    except ValidationError as exc:
        raise UploadError("Sorry, those cleaning options weren't valid.") from exc
    return upload, options


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["TRUSTED_HOSTS"] = ["datawrangler.org", "localhost", "127.0.0.1"]
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    # Lets templates add a fingerprint to the CSS address, so browsers fetch new versions.
    css_path = Path(app.root_path) / "static" / "css" / "app.css"
    app.jinja_env.globals["css_version"] = _file_fingerprint(css_path)
    app.jinja_env.filters["show_spaces"] = _show_extra_spaces

    # Trust the X-Forwarded-Host and X-Forwarded-Proto labels from the Cloudflare Worker.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_host=1, x_proto=1)  # type: ignore[method-assign]

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.post("/preview")
    def preview() -> tuple[str, int]:
        upload, options = _get_upload_and_options()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "upload.csv"
            upload.save(path)
            try:
                result, report = clean_csv(path, options)
            except NoColumnsKeptError as exc:
                return render_template(
                    _result_template(),
                    error=str(exc),
                    all_columns=exc.all_columns,
                    columns_signature=exc.signature,
                    kept_columns=[],
                ), 400
            except duckdb.Error as exc:
                raise UploadError(CSV_ERROR) from exc

        return render_template(
            _result_template(),
            preview=result,
            report=report,
            options=options,
            filename=upload.filename,
            all_columns=result.all_columns,
            columns_signature=result.columns_signature,
            kept_columns=result.kept_columns,
        ), 200

    @app.post("/download")
    def download() -> Response:
        upload, options = _get_upload_and_options()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "upload.csv"
            output = Path(tmp) / "cleaned.csv"
            upload.save(source)
            try:
                write_clean_csv(source, options, output)
            except NoColumnsKeptError as exc:
                raise UploadError(str(exc)) from exc
            except duckdb.Error as exc:
                raise UploadError(CSV_ERROR) from exc
            data = output.read_bytes()

        stem = Path(secure_filename(upload.filename or "")).stem or "data"
        disposition = f'attachment; filename="{stem}-cleaned.csv"'
        return Response(
            data, mimetype="text/csv", headers={"Content-Disposition": disposition}
        )

    @app.errorhandler(UploadError)
    def upload_error(error: UploadError) -> tuple[str, int]:
        return render_template(_result_template(), error=str(error)), 400

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(error: RequestEntityTooLarge) -> tuple[str, int]:
        message = "That file is too big. The limit is 10 MB."
        return render_template(_result_template(), error=message), 413

    return app
