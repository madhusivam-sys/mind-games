from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "configs"


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Resolved repository paths used across the application."""

    root: Path
    config_dir: Path
    data_root: Path

    @property
    def sample_csv(self) -> Path:
        return self.data_root / "samples" / "nifty_futures_sample.csv"

    @property
    def processed_dir(self) -> Path:
        return self.data_root / "processed"

    @property
    def model_dir(self) -> Path:
        return self.processed_dir / "models"

    def config_file(self, name: str) -> Path:
        return self.config_dir / name


class Settings(BaseSettings):
    """Environment-backed application settings."""

    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_name: str = Field(default="Bazaar Mind Games", alias="APP_NAME")
    dashboard_password: str | None = Field(default=None, alias="DASHBOARD_PASSWORD")
    data_root: Path = Field(default=ROOT_DIR / "data", alias="DATA_ROOT")
    database_url: str = Field(default="sqlite:///./data/processed/bazaar_mind_games.db", alias="DATABASE_URL")
    default_symbol: str = Field(default="NIFTY_FUT", alias="DEFAULT_SYMBOL")
    timezone: str = Field(default="Asia/Kolkata", alias="TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    market_data_api_base_url: str | None = Field(default=None, alias="MARKET_DATA_API_BASE_URL")
    market_data_api_key: str | None = Field(default=None, alias="MARKET_DATA_API_KEY")
    market_data_api_key_header: str = Field(default="X-API-Key", alias="MARKET_DATA_API_KEY_HEADER")
    market_data_api_timeout_seconds: float = Field(default=10.0, alias="MARKET_DATA_API_TIMEOUT_SECONDS")
    market_data_api_max_retries: int = Field(default=2, alias="MARKET_DATA_API_MAX_RETRIES")
    truedata_base_url: str = Field(default="https://history.truedata.in", alias="TRUEDATA_BASE_URL")
    truedata_bearer_token: str | None = Field(default=None, alias="TRUEDATA_BEARER_TOKEN")
    truedata_timeout_seconds: float = Field(default=10.0, alias="TRUEDATA_TIMEOUT_SECONDS")
    truedata_max_retries: int = Field(default=2, alias="TRUEDATA_MAX_RETRIES")
    truedata_bidask: int = Field(default=1, alias="TRUEDATA_BIDASK")
    truedata_comp: bool = Field(default=False, alias="TRUEDATA_COMP")
    truedata_live_username: str | None = Field(default=None, alias="TRUEDATA_LIVE_USERNAME")
    truedata_live_password: str | None = Field(default=None, alias="TRUEDATA_LIVE_PASSWORD")
    truedata_live_url: str = Field(default="push.truedata.in", alias="TRUEDATA_LIVE_URL")
    truedata_live_port: int = Field(default=9084, alias="TRUEDATA_LIVE_PORT")
    truedata_live_full_feed: bool = Field(default=True, alias="TRUEDATA_LIVE_FULL_FEED")
    truedata_live_dry_run: bool = Field(default=False, alias="TRUEDATA_LIVE_DRY_RUN")
    truedata_live_backfill_interval: str = Field(default="1min", alias="TRUEDATA_LIVE_BACKFILL_INTERVAL")
    truedata_live_backfill_bars: int = Field(default=200, alias="TRUEDATA_LIVE_BACKFILL_BARS")
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")
    cpr_report_hour: int = Field(default=21, ge=0, le=23, alias="CPR_REPORT_HOUR")
    cpr_report_minute: int = Field(default=0, ge=0, le=59, alias="CPR_REPORT_MINUTE")
    cpr_scanner_history_days: int = Field(default=20, ge=3, le=90, alias="CPR_SCANNER_HISTORY_DAYS")
    cpr_scanner_segments: str = Field(default="CM", alias="CPR_SCANNER_SEGMENTS")
    cpr_scanner_report_limit: int = Field(default=10, ge=1, le=30, alias="CPR_SCANNER_REPORT_LIMIT")
    cpr_report_max_attempts: int = Field(default=3, ge=1, le=10, alias="CPR_REPORT_MAX_ATTEMPTS")
    cpr_report_retry_minutes: int = Field(default=15, ge=1, le=120, alias="CPR_REPORT_RETRY_MINUTES")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_paths() -> AppPaths:
    settings = get_settings()
    return AppPaths(root=ROOT_DIR, config_dir=CONFIG_DIR, data_root=settings.data_root)


@lru_cache(maxsize=None)
def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=3)
def load_project_config(name: str) -> dict[str, Any]:
    return load_yaml(get_paths().config_file(name))


def repo_path(*parts: str) -> Path:
    return ROOT_DIR.joinpath(*parts)
