from __future__ import annotations

import pytest

from services import cpr_scheduler


def test_nightly_scan_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    def flaky_scan() -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary NSE failure")

    monkeypatch.setattr(cpr_scheduler, "run_nightly_scan", flaky_scan)
    monkeypatch.setattr(cpr_scheduler.time, "sleep", sleeps.append)

    cpr_scheduler.run_nightly_scan_with_retries(max_attempts=3, retry_seconds=15.0)

    assert attempts == 3
    assert sleeps == [15.0, 15.0]


def test_nightly_scan_raises_after_final_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def failed_scan() -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("Telegram unavailable")

    monkeypatch.setattr(cpr_scheduler, "run_nightly_scan", failed_scan)
    monkeypatch.setattr(cpr_scheduler.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="Telegram unavailable"):
        cpr_scheduler.run_nightly_scan_with_retries(max_attempts=3, retry_seconds=0.0)
    assert attempts == 3
