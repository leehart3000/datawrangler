import pytest
import sentry_sdk

from datawrangler.monitoring import REMOVED, init_sentry, remove_exception_text


def test_sentry_stays_off_without_a_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    init_sentry()
    assert not sentry_sdk.get_client().is_active()


def test_error_messages_are_removed_before_sending() -> None:
    event = {"exception": {"values": [{"type": "ValueError", "value": "Ada,London"}]}}
    cleaned = remove_exception_text(event, {})  # type: ignore[arg-type]
    exception = cleaned["exception"]["values"][0]
    assert exception["value"] == REMOVED
    assert exception["type"] == "ValueError"
