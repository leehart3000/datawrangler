# Stage 1: build the CSS with Tailwind.
FROM python:3.14-slim AS css

ADD --chmod=755 https://github.com/tailwindlabs/tailwindcss/releases/download/v4.3.2/tailwindcss-linux-x64 /usr/local/bin/tailwindcss

WORKDIR /app
COPY src ./src
RUN tailwindcss -i src/datawrangler/static/src/input.css -o src/datawrangler/static/css/app.css --minify

# Stage 2: the app itself.
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY README.md ./
COPY src ./src
COPY --from=css /app/src/datawrangler/static/css/app.css ./src/datawrangler/static/css/app.css
RUN uv sync --locked --no-dev --no-editable

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home appuser
USER appuser

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 'datawrangler.app:create_app()'"]