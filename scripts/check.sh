#!/bin/sh
# Runs all the code checks. Stops at the first one that fails.
set -e

uv run ruff format
uv run ruff check
uv run mypy src tests
uv run pytest