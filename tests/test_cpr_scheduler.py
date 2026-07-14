from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

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


def test_scheduler_state_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-state.json"
    completed_at = datetime(2026, 7, 14, 21, 2, tzinfo=ZoneInfo("Asia/Kolkata"))

    cpr_scheduler._write_last_success(completed_at, path)

    assert cpr_scheduler._read_last_success(path) == completed_at


def test_catch_up_is_due_only_after_schedule_and_without_today_success() -> None:
    timezone = ZoneInfo("Asia/Kolkata")
    before = datetime(2026, 7, 14, 20, 59, tzinfo=timezone)
    after = datetime(2026, 7, 14, 21, 1, tzinfo=timezone)
    yesterday = datetime(2026, 7, 13, 21, 0, tzinfo=timezone)
    today = datetime(2026, 7, 14, 21, 0, tzinfo=timezone)

    assert not cpr_scheduler._is_catch_up_due(before, None, 21, 0)
    assert cpr_scheduler._is_catch_up_due(after, None, 21, 0)
    assert cpr_scheduler._is_catch_up_due(after, yesterday, 21, 0)
    assert not cpr_scheduler._is_catch_up_due(after, today, 21, 0)


def test_scheduler_uses_cron_and_misfire_protection() -> None:
    scheduler = cpr_scheduler.build_scheduler()
    job = scheduler.get_job("nightly-cpr-report")

    assert job is not None
    assert job.coalesce is True
    assert job.max_instances == 1
    assert job.misfire_grace_time == 23 * 60 * 60
