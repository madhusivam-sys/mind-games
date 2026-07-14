from __future__ import annotations

import pytest

from integrations import telegram_client
from integrations.telegram_client import TelegramError, send_telegram_message


class _Response:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code


class _Client:
    def __init__(self, responses: list[_Response], calls: list[dict[str, object]], **_: object) -> None:
        self.responses = responses
        self.calls = calls

    def __enter__(self) -> "_Client":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def post(self, url: str, json: dict[str, object]) -> _Response:
        self.calls.append({"url": url, "json": json})
        return self.responses.pop(0)


def test_send_telegram_message_chunks_long_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    responses = [_Response(), _Response()]
    monkeypatch.setattr(telegram_client.httpx, "Client", lambda **kwargs: _Client(responses, calls, **kwargs))

    send_telegram_message("secret", "123", "x" * 4500)

    assert len(calls) == 2
    assert len(str(calls[0]["json"]["text"])) == 4000  # type: ignore[index]
    assert len(str(calls[1]["json"]["text"])) == 500  # type: ignore[index]


def test_send_telegram_message_rejects_missing_or_empty_values() -> None:
    with pytest.raises(TelegramError, match="must be configured"):
        send_telegram_message("", "123", "report")
    with pytest.raises(TelegramError, match="cannot be empty"):
        send_telegram_message("secret", "123", "   ")


def test_send_telegram_message_wraps_api_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    responses = [_Response(403)]
    monkeypatch.setattr(telegram_client.httpx, "Client", lambda **kwargs: _Client(responses, calls, **kwargs))

    with pytest.raises(TelegramError, match="403"):
        send_telegram_message("secret", "123", "report")
