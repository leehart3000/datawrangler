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

from datawrangler.fileformat import (
    LINE_ENDING_LABELS,
    QUOTING_DESCRIPTIONS,
    ChoiceNeededError,
    FileFormat,
    OutputChoices,
    detect_format,
    effective_choices,
    file_fingerprint,
    to_file_format,
)
from datawrangler.monitoring import init_sentry
from datawrangler.wrangling import (
    CleaningOptions,
    NoColumnsKeptError,
    UnreadableFileError,
    clean_csv,
    write_clean_csv,
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
CSV_ERROR = (
    "Sorry, we couldn't read that file as a table without risking changes to your data. "
    "It needs a header row first, with every row having the same number of "
    "comma-separated values."
)
MIXED_LINE_ENDINGS_ERROR = (
    "Your file mixes different line endings (some Windows-style, some Unix or Mac-style). "
    "We can't read files like that reliably yet, so to avoid changing your data, "
    "we haven't processed it."
)
EXTRA_SPACE = Markup(
    '<span class="rounded-sm bg-amber-100 text-amber-700" title="Extra space">·</span>'
)


class UploadError(Exception):
    """A problem with what the visitor sent, with a message they can understand."""


def _file_fingerprint(path: Path) -> str:
    """Return a short fingerprint of a file's contents, or "dev" if it doesn't exist."""
    if not path.exists():
        return "dev"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


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


def _result_template() -> str:
    """For htmx requests, reply with just the result section; otherwise the whole page."""
    if request.headers.get("HX-Request") == "true":
        return "_result.html"
    return "index.html"


def _render_result(status: int, **context: object) -> tuple[str, int]:
    """Render the result. For htmx, this also includes the columns section, sent out of band."""
    template = _result_template()
    return render_template(template, oob=template == "_result.html", **context), status


def _form_data() -> dict[str, object]:
    """The form's values (ignoring empty ones), with the ticked columns gathered into a list."""
    data: dict[str, object] = {
        key: value for key, value in request.form.items() if value != ""
    }
    data.pop("keep_columns", None)
    if "columns_for" in request.form:
        data["keep_columns"] = request.form.getlist("keep_columns")
    return data


def _get_request() -> tuple[FileStorage, CleaningOptions, OutputChoices]:
    """Read the uploaded file, the cleaning options and the download settings from the form."""
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        raise UploadError("Please choose a CSV file.")
    form = _form_data()
    try:
        options = CleaningOptions.model_validate(form)
        choices = OutputChoices.model_validate(form)
    except ValidationError as exc:
        raise UploadError("Sorry, those options weren't valid.") from exc
    return upload, options, choices


def _detect(path: Path, submitted: OutputChoices) -> tuple[FileFormat, OutputChoices]:
    """Detect the uploaded file's format, and work out which download settings apply."""
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadError(CSV_ERROR) from exc
    detected = detect_format(text)
    if detected.mixed_line_endings:
        raise UploadError(MIXED_LINE_ENDINGS_ERROR)
    return detected, effective_choices(detected, submitted, file_fingerprint(data))


def create_app() -> Flask:
    init_sentry()
    app = Flask(__name__)
    app.config["TRUSTED_HOSTS"] = ["datawrangler.org", "localhost", "127.0.0.1"]
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    # Lets templates add a fingerprint to the CSS address, so browsers fetch new versions.
    css_path = Path(app.root_path) / "static" / "css" / "app.css"
    app.jinja_env.globals["css_version"] = _file_fingerprint(css_path)
    app.jinja_env.globals["LINE_ENDING_LABELS"] = LINE_ENDING_LABELS
    app.jinja_env.globals["QUOTING_DESCRIPTIONS"] = QUOTING_DESCRIPTIONS
    app.jinja_env.filters["show_spaces"] = _show_extra_spaces

    # Trust the X-Forwarded-Host and X-Forwarded-Proto labels from the Cloudflare Worker.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_host=1, x_proto=1)  # type: ignore[method-assign]

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.post("/preview")
    def preview() -> tuple[str, int]:
        upload, options, submitted = _get_request()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "upload.csv"
            upload.save(path)
            detected, choices = _detect(path, submitted)
            try:
                result, report = clean_csv(path, options)
            except NoColumnsKeptError as exc:
                return _render_result(
                    400,
                    columns_error=str(exc),
                    all_columns=exc.all_columns,
                    columns_signature=exc.signature,
                    kept_columns=[],
                    options=options,
                )
            except (UnreadableFileError, duckdb.Error) as exc:
                raise UploadError(CSV_ERROR) from exc

        return _render_result(
            200,
            preview=result,
            report=report,
            options=options,
            filename=upload.filename,
            all_columns=result.all_columns,
            columns_signature=result.columns_signature,
            kept_columns=result.kept_columns,
            detected=detected,
            choices=choices,
        )

    @app.post("/download")
    def download() -> Response:
        upload, options, submitted = _get_request()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "upload.csv"
            output = Path(tmp) / "cleaned.csv"
            upload.save(source)
            _, choices = _detect(source, submitted)
            try:
                write_clean_csv(source, options, output, to_file_format(choices))
            except ChoiceNeededError as exc:
                raise UploadError(str(exc)) from exc
            except NoColumnsKeptError as exc:
                raise UploadError(str(exc)) from exc
            except (UnreadableFileError, duckdb.Error) as exc:
                raise UploadError(CSV_ERROR) from exc
            data = output.read_bytes()

        stem = Path(secure_filename(upload.filename or "")).stem or "data"
        disposition = f'attachment; filename="{stem}-cleaned.csv"'
        return Response(
            data, mimetype="text/csv", headers={"Content-Disposition": disposition}
        )

    @app.errorhandler(UploadError)
    def upload_error(error: UploadError) -> tuple[str, int]:
        return _render_result(400, error=str(error))

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(error: RequestEntityTooLarge) -> tuple[str, int]:
        return _render_result(413, error="That file is too big. The limit is 10 MB.")

    return app
