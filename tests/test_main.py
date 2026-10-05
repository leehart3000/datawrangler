import pytest

from datawrangler import main


def test_main_prints_greeting(capsys: pytest.CaptureFixture[str]) -> None:
    main()
    assert "Hello from datawrangler!" in capsys.readouterr().out
