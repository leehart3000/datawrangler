#!/bin/sh
# Runs all the code checks. Stops at the first one that fails.
set -e

tailwindcss -i src/datawrangler/static/src/input.css -o src/datawrangler/static/css/app.css

uv run ruff format
uv run ruff check --fix
uv run mypy src tests
uv run pytest