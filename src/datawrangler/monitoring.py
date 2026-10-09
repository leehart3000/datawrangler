"""Error reporting with Sentry, set up so that uploaded data is never sent."""

import os

import sentry_sdk
from sentry_sdk.types import Event, Hint

REMOVED = "[removed: may contain uploaded data]"


def remove_exception_text(event: Event, hint: Hint) -> Event:
    """Blank out error messages, which can quote parts of the data that caused them."""
    for exception in event.get("exception", {}).get("values", []):
        exception["value"] = REMOVED
    return event


def init_sentry() -> None:
    """Send error reports to Sentry, but only if SENTRY_DSN is set."""
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        release=os.environ.get("APP_VERSION"),
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        traces_sample_rate=0.0,
        before_send=remove_exception_text,
    )
