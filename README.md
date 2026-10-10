# DataWrangler

Clean, check and prepare your data. No coding needed.

**Live site:** https://datawrangler.org

DataWrangler is a web app for tidying up spreadsheet-style data files (CSV, TSV and
similar) without writing code. Upload a file, choose the columns to include and the
cleaning steps to apply, check the preview, and download the result.

## What it does

- **Reads** comma-, semicolon-, tab- and pipe-separated files, detecting the separator
  automatically (and letting you correct it).
- **Shows a preview** with each column's likely type, its number of empty cells and
  unique values, and any extra spaces made visible.
- **Cleans:** choose which columns to include, trim extra spaces, remove empty rows,
  remove duplicate rows, and tidy column names.
- **Downloads** the result in the original file's format by default (separator, line
  endings, quoting and more), or in a format you choose.

## The most important rule

Every value that goes in comes out exactly the same, unless you chose a cleaning step
that changes it.

With no cleaning steps chosen, the download is identical to the upload, byte for byte.
If a file can't be read without risking changes (for example, because some rows have a
different number of values from the header), DataWrangler explains why and refuses it,
rather than guessing. An automated test suite checks this rule against a range of tricky
files on every change.

## Privacy

Uploaded files are processed and then deleted straight away. Nothing is stored.
See the [privacy page](https://datawrangler.org/privacy) for details.

## Built with

- **App:** Python 3.14, Flask, Jinja2, Pydantic, DuckDB
- **Pages:** htmx, Alpine.js, Tailwind CSS
- **Hosting:** Docker, Gunicorn, Google Cloud Run, Cloudflare
- **Quality and security:** GitLab CI/CD, uv, Ruff, Mypy, Pytest, Playwright,
  TruffleHog, Renovate
- **Monitoring:** Sentry (set up so that uploaded data is never sent)

## Running it locally

You'll need [uv](https://docs.astral.sh/uv/) and the
[Tailwind CSS standalone CLI](https://tailwindcss.com/blog/standalone-cli) (version 4).

```sh
git clone https://gitlab.com/leehart3000/datawrangler.git
cd datawrangler
uv sync
tailwindcss -i src/datawrangler/static/src/input.css -o src/datawrangler/static/css/app.css
uv run flask --app datawrangler.app run --debug --port 8000
```

Then open http://127.0.0.1:8000.

To run all the checks (formatting, linting, type checks and tests):

```sh
uv run playwright install chromium   # first time only, for the browser tests
bash scripts/check.sh
```

## Repository

The main repository is on GitLab: https://gitlab.com/leehart3000/datawrangler.
The GitHub repository is a read-only mirror, so please raise any issues on GitLab.

## Status

Early development. The public demo cleans files without storing them. Accounts, saved
files and repeatable cleaning recipes are planned.

## Licence

DataWrangler is free software, licensed under the
[GNU Affero General Public License v3.0 or later](LICENSE) (AGPL-3.0-or-later).

In short: you may use, change and share it, but if you run a changed version for other
people to use over a network, you must offer them its source code under the same licence.