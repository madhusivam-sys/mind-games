from __future__ import annotations

import logging
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from integrations.telegram_client import send_telegram_message
from services.cpr_scanner import download_bhavcopy_history, scan_latest, telegram_report
from utils.config import get_paths, get_settings


LOGGER = logging.getLogger(__name__)


def run_nightly_scan() -> None:
    settings = get_settings()
    timezone = ZoneInfo(settings.timezone)
    today = datetime.now(timezone).date()
    segments = tuple(value.strip().upper() for value in settings.cpr_scanner_segments.split(",") if value.strip())
    history = download_bhavcopy_history(today, settings.cpr_scanner_history_days, segments)
    results = scan_latest(history)
    send_telegram_message(settings.telegram_bot_token or "", settings.telegram_chat_id or "", telegram_report(results, settings.cpr_scanner_report_limit))
    LOGGER.info("Sent CPR scan with %s evaluated symbols", len(results))


def run_nightly_scan_with_retries(max_attempts: int, retry_seconds: float) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            run_nightly_scan()
            return
        except Exception:
            if attempt >= max_attempts:
                raise
            LOGGER.exception("Nightly CPR scan attempt %s/%s failed; retrying", attempt, max_attempts)
            time.sleep(retry_seconds)


def _next_run(now: datetime, hour: int, minute: int) -> datetime:
    """Return the next wall-clock run time; retained for scheduling diagnostics."""

    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return target if target > now else target + timedelta(days=1)


def _state_path() -> Path:
    return get_paths().processed_dir / "cpr_scheduler_state.json"


def _read_last_success(path: Path | None = None) -> datetime | None:
    state_path = path or _state_path()
    try:
        value = json.loads(state_path.read_text(encoding="utf-8"))["last_success"]
        return datetime.fromisoformat(value)
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _write_last_success(completed_at: datetime, path: Path | None = None) -> None:
    state_path = path or _state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"last_success": completed_at.isoformat()}), encoding="utf-8")
    temporary.replace(state_path)


def _is_catch_up_due(now: datetime, last_success: datetime | None, hour: int, minute: int) -> bool:
    scheduled_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now < scheduled_today:
        return False
    return last_success is None or last_success.astimezone(now.tzinfo).date() < now.date()


def _run_scheduled_scan() -> None:
    settings = get_settings()
    run_nightly_scan_with_retries(
        settings.cpr_report_max_attempts,
        settings.cpr_report_retry_minutes * 60.0,
    )
    completed_at = datetime.now(ZoneInfo(settings.timezone))
    _write_last_success(completed_at)
    LOGGER.info("Recorded successful CPR report at %s", completed_at.isoformat())


def build_scheduler() -> BlockingScheduler:
    settings = get_settings()
    timezone = ZoneInfo(settings.timezone)
    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(
        _run_scheduled_scan,
        CronTrigger(
            hour=settings.cpr_report_hour,
            minute=settings.cpr_report_minute,
            timezone=timezone,
        ),
        id="nightly-cpr-report",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=23 * 60 * 60,
    )
    return scheduler


def run_forever() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    timezone = ZoneInfo(settings.timezone)
    LOGGER.info(
        "CPR scheduler ready for %02d:%02d %s",
        settings.cpr_report_hour,
        settings.cpr_report_minute,
        settings.timezone,
    )
    now = datetime.now(timezone)
    if _is_catch_up_due(
        now,
        _read_last_success(),
        settings.cpr_report_hour,
        settings.cpr_report_minute,
    ):
        LOGGER.info("Today's scheduled report is missing; running catch-up now")
        try:
            _run_scheduled_scan()
        except Exception:
            LOGGER.exception("Catch-up CPR scan failed after all retry attempts")
    build_scheduler().start()


if __name__ == "__main__":
    run_forever()
