from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from integrations.telegram_client import send_telegram_message
from services.cpr_scanner import download_bhavcopy_history, scan_latest, telegram_report
from utils.config import get_settings


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
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return target if target > now else target + timedelta(days=1)


def run_forever() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    timezone = ZoneInfo(settings.timezone)
    LOGGER.info("CPR scheduler ready for %02d:%02d %s", settings.cpr_report_hour, settings.cpr_report_minute, settings.timezone)
    while True:
        now = datetime.now(timezone)
        target = _next_run(now, settings.cpr_report_hour, settings.cpr_report_minute)
        time.sleep(max(1.0, (target - now).total_seconds()))
        try:
            run_nightly_scan_with_retries(settings.cpr_report_max_attempts, settings.cpr_report_retry_minutes * 60.0)
        except Exception:
            LOGGER.exception("Nightly CPR scan failed after all retry attempts")


if __name__ == "__main__":
    run_forever()
