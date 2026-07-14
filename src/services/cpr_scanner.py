from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterable
from zipfile import BadZipFile, ZipFile

import httpx
import numpy as np
import pandas as pd


NSE_ARCHIVE_ROOT = "https://nsearchives.nseindia.com/content"


class BhavcopyError(ValueError):
    """Raised when an NSE bhavcopy cannot be downloaded or normalised."""


@dataclass(frozen=True, slots=True)
class ScanConfig:
    narrow_percentile: float = 0.30
    max_narrow_width_percent: float = 0.70
    camarilla_tolerance_percent: float = 0.35
    minimum_history: int = 3


_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("traddt", "bizdt", "timestamp", "date", "sessiondate"),
    "symbol": ("tckrsymb", "symbol", "ticker", "underlying"),
    "series": ("sctysrs", "series"),
    "instrument": ("fininstrmtp", "instrument", "instrumenttype"),
    "expiry": ("xprydt", "expirydate", "expiry"),
    "option_type": ("optntp", "optiontype", "optiontyp"),
    "open": ("opnpric", "open", "openprice"),
    "high": ("hghpric", "high", "highprice"),
    "low": ("lwpric", "low", "lowprice"),
    "close": ("clspric", "close", "closeprice"),
    "volume": ("ttltradgvol", "tottrdqty", "totaltradedquantity", "volume"),
    "turnover": ("ttltrfval", "tottrdval", "turnover"),
}


def _key(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def _read_csv_payload(payload: bytes, filename: str) -> pd.DataFrame:
    if filename.lower().endswith(".zip") or payload[:2] == b"PK":
        try:
            with ZipFile(BytesIO(payload)) as archive:
                csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
                if not csv_names:
                    raise BhavcopyError(f"{filename} does not contain a CSV file")
                with archive.open(csv_names[0]) as handle:
                    return pd.read_csv(handle, low_memory=False)
        except BadZipFile as exc:
            raise BhavcopyError(f"{filename} is not a valid ZIP archive") from exc
    return pd.read_csv(BytesIO(payload), low_memory=False)


def _column(frame: pd.DataFrame, name: str, required: bool = False) -> pd.Series:
    lookup = {_key(column): column for column in frame.columns}
    for alias in _ALIASES[name]:
        if alias in lookup:
            return frame[lookup[alias]]
    if required:
        raise BhavcopyError(f"Missing required {name!r} column. Received: {', '.join(map(str, frame.columns))}")
    return pd.Series(index=frame.index, dtype="object")


def _parse_dates(values: pd.Series) -> pd.Series:
    text = values.astype(str).str.strip()
    iso = text.str.match(r"^\d{4}[-/]\d{2}[-/]\d{2}")
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    parsed.loc[iso] = pd.to_datetime(text.loc[iso], errors="coerce", yearfirst=True)
    parsed.loc[~iso] = pd.to_datetime(text.loc[~iso], errors="coerce", dayfirst=True)
    return parsed


def normalise_bhavcopy(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert legacy or UDiFF CM/FO bhavcopy columns into daily OHLC rows."""

    normalised = pd.DataFrame(index=frame.index)
    normalised["session_date"] = _parse_dates(_column(frame, "date", required=True)).dt.date
    normalised["symbol"] = _column(frame, "symbol", required=True).astype(str).str.strip().str.upper()
    normalised["series"] = _column(frame, "series").fillna("").astype(str).str.strip().str.upper()
    normalised["instrument"] = _column(frame, "instrument").fillna("").astype(str).str.strip().str.upper()
    normalised["expiry"] = _parse_dates(_column(frame, "expiry"))
    normalised["option_type"] = _column(frame, "option_type").fillna("").astype(str).str.strip().str.upper()
    for column in ("open", "high", "low", "close", "volume", "turnover"):
        normalised[column] = pd.to_numeric(_column(frame, column, required=column in {"open", "high", "low", "close"}), errors="coerce")

    normalised = normalised.dropna(subset=["session_date", "symbol", "open", "high", "low", "close"])
    normalised = normalised[(normalised["symbol"] != "") & (normalised["high"] >= normalised["low"])]

    # Keep the scanner futures-only. UDiFF uses STF for stock futures while
    # legacy files use FUTSTK; both are normalized to the canonical FUTSTK
    # label. Cash shares, options, and index futures are intentionally excluded.
    is_stock_future = normalised["instrument"].isin(["STF", "FUTSTK"])
    future_rows = normalised[is_stock_future].copy()
    future_rows["instrument"] = "FUTSTK"
    future_rows["asset_type"] = "F&O Stock Future"
    if not future_rows.empty:
        future_rows = future_rows.sort_values(["symbol", "session_date", "expiry"])
        future_rows = future_rows.groupby(["symbol", "session_date"], as_index=False, sort=False).first()

    result = future_rows.reset_index(drop=True)
    if result.empty:
        raise BhavcopyError("No NSE stock-futures contracts (FUTSTK/STF) were found in the supplied F&O bhavcopy")
    return result.sort_values(["symbol", "session_date"]).drop_duplicates(["symbol", "session_date", "asset_type"], keep="last").reset_index(drop=True)


def load_bhavcopy_files(files: Iterable[tuple[str, bytes] | BinaryIO]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for item in files:
        if isinstance(item, tuple):
            filename, payload = item
        else:
            filename = Path(getattr(item, "name", "bhavcopy.csv")).name
            payload = item.read()
        frames.append(normalise_bhavcopy(_read_csv_payload(payload, filename)))
    if not frames:
        raise BhavcopyError("Select at least one CSV or ZIP bhavcopy")
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "session_date"]).drop_duplicates(
        ["symbol", "session_date", "asset_type"], keep="last"
    ).reset_index(drop=True)


def _archive_url(session_date: date, segment: str) -> str:
    segment = segment.upper()
    if segment not in {"CM", "FO"}:
        raise BhavcopyError("Segment must be CM or FO")
    filename = f"BhavCopy_NSE_{segment}_0_0_0_{session_date:%Y%m%d}_F_0000.csv.zip"
    return f"{NSE_ARCHIVE_ROOT}/{segment.lower()}/{filename}"


def download_bhavcopy_history(
    as_of: date,
    trading_days: int = 20,
    segments: tuple[str, ...] = ("FO",),
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    """Download recent official NSE UDiFF bhavcopies, skipping holidays/weekends."""

    if trading_days < 3 or trading_days > 90:
        raise BhavcopyError("History must be between 3 and 90 trading days")
    owned_client = client is None
    http = client or httpx.Client(timeout=20.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 CPRScanner/1.0"})
    if tuple(segment.upper() for segment in segments) != ("FO",):
        raise BhavcopyError("The CPR scanner accepts only the NSE F&O bhavcopy (FO stock futures)")
    frames: list[pd.DataFrame] = []
    try:
        for segment in segments:
            found = 0
            cursor = as_of
            attempts = 0
            while found < trading_days and attempts < trading_days * 3:
                attempts += 1
                if cursor.weekday() < 5:
                    response = http.get(_archive_url(cursor, segment))
                    if response.status_code == 200 and response.content[:2] == b"PK":
                        frames.append(normalise_bhavcopy(_read_csv_payload(response.content, f"{segment}-{cursor}.zip")))
                        found += 1
                    elif response.status_code not in {403, 404}:
                        response.raise_for_status()
                cursor -= timedelta(days=1)
            if found < 3:
                raise BhavcopyError(f"NSE returned only {found} usable {segment} bhavcopies. Try upload mode or an earlier date.")
    finally:
        if owned_client:
            http.close()
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "session_date"]).drop_duplicates(
        ["symbol", "session_date", "asset_type"], keep="last"
    ).reset_index(drop=True)


def _cpr(high: pd.Series, low: pd.Series, close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    pivot = (high + low + close) / 3.0
    raw_bc = (high + low) / 2.0
    raw_tc = (2.0 * pivot) - raw_bc
    return pivot, pd.concat([raw_bc, raw_tc], axis=1).min(axis=1), pd.concat([raw_bc, raw_tc], axis=1).max(axis=1)


def build_scan_features(history: pd.DataFrame, config: ScanConfig = ScanConfig()) -> pd.DataFrame:
    required = {"symbol", "session_date", "open", "high", "low", "close", "volume", "asset_type"}
    missing = required.difference(history.columns)
    if missing:
        raise BhavcopyError(f"Normalised history is missing: {', '.join(sorted(missing))}")

    rows = history.copy().sort_values(["asset_type", "symbol", "session_date"])
    group = rows.groupby(["asset_type", "symbol"], sort=False)
    for column in ("high", "low", "close"):
        rows[f"prev_{column}"] = group[column].shift(1)
    rows["prev_open"] = group["open"].shift(1)

    rows["pivot"], rows["bc"], rows["tc"] = _cpr(rows["prev_high"], rows["prev_low"], rows["prev_close"])
    rows["developing_pivot"], rows["developing_bc"], rows["developing_tc"] = _cpr(rows["high"], rows["low"], rows["close"])
    rows["prev_pivot"] = group["pivot"].shift(1)
    rows["prev_bc"] = group["bc"].shift(1)
    rows["prev_tc"] = group["tc"].shift(1)
    rows["cpr_width_percent"] = ((rows["tc"] - rows["bc"]) / rows["pivot"].replace(0, np.nan) * 100.0).abs()
    rows["width_percentile"] = group["cpr_width_percent"].transform(lambda series: series.rolling(20, min_periods=config.minimum_history).rank(pct=True))

    prior_range = rows["prev_high"] - rows["prev_low"]
    rows["r3"] = rows["prev_close"] + (prior_range * 1.1 / 4.0)
    rows["s3"] = rows["prev_close"] - (prior_range * 1.1 / 4.0)
    tolerance = rows["close"].abs() * (config.camarilla_tolerance_percent / 100.0)

    rows["narrow_cpr"] = (rows["width_percentile"] <= config.narrow_percentile) & (
        rows["cpr_width_percent"] <= config.max_narrow_width_percent
    )
    rows["ascending_cpr"] = rows["bc"] > rows["prev_tc"]
    rows["descending_cpr"] = rows["tc"] < rows["prev_bc"]
    rows["inside_cpr"] = (rows["bc"] >= rows["prev_bc"]) & (rows["tc"] <= rows["prev_tc"])
    rows["outside_cpr"] = (rows["bc"] <= rows["prev_bc"]) & (rows["tc"] >= rows["prev_tc"])
    rows["virgin_cpr_above"] = rows["low"] > rows["tc"]
    rows["virgin_cpr_below"] = rows["high"] < rows["bc"]
    rows["bullish_reversal"] = (rows["open"] < rows["pivot"]) & (rows["close"] > rows["tc"]) & (rows["prev_close"] < rows["prev_pivot"])
    rows["bearish_reversal"] = (rows["open"] > rows["pivot"]) & (rows["close"] < rows["bc"]) & (rows["prev_close"] > rows["prev_pivot"])
    rows["near_r3"] = (rows["close"] - rows["r3"]).abs() <= tolerance
    rows["near_s3"] = (rows["close"] - rows["s3"]).abs() <= tolerance
    rows["developing_ascending"] = rows["developing_bc"] > rows["tc"]
    rows["developing_descending"] = rows["developing_tc"] < rows["bc"]
    rows["developing_inside"] = (rows["developing_bc"] >= rows["bc"]) & (rows["developing_tc"] <= rows["tc"])
    rows["developing_outside"] = (rows["developing_bc"] <= rows["bc"]) & (rows["developing_tc"] >= rows["tc"])
    return rows


def scan_latest(history: pd.DataFrame, config: ScanConfig = ScanConfig()) -> pd.DataFrame:
    features = build_scan_features(history, config)
    latest = features.groupby(["asset_type", "symbol"], sort=False, as_index=False).tail(1).copy()
    latest = latest[latest["prev_tc"].notna()].copy()

    rules: tuple[tuple[str, str, str, int], ...] = (
        ("narrow_cpr", "Narrow CPR", "neutral", 2),
        ("ascending_cpr", "Ascending CPR", "bullish", 2),
        ("descending_cpr", "Descending CPR", "bearish", 2),
        ("inside_cpr", "Inside CPR", "neutral", 1),
        ("outside_cpr", "Outside CPR", "neutral", 1),
        ("virgin_cpr_above", "Virgin CPR below price", "bullish", 2),
        ("virgin_cpr_below", "Virgin CPR above price", "bearish", 2),
        ("bullish_reversal", "Bullish trend reversal", "bullish", 3),
        ("bearish_reversal", "Bearish trend reversal", "bearish", 3),
        ("near_r3", "Close near Camarilla R3", "bullish", 1),
        ("near_s3", "Close near Camarilla S3", "bearish", 1),
        ("developing_ascending", "Tomorrow CPR developing higher", "bullish", 2),
        ("developing_descending", "Tomorrow CPR developing lower", "bearish", 2),
        ("developing_inside", "Tomorrow CPR developing inside", "neutral", 1),
        ("developing_outside", "Tomorrow CPR developing outside", "neutral", 1),
    )

    records: list[dict[str, object]] = []
    for _, row in latest.iterrows():
        matched = [(label, direction, weight) for column, label, direction, weight in rules if bool(row.get(column, False))]
        bullish = sum(weight for _, direction, weight in matched if direction == "bullish")
        bearish = sum(weight for _, direction, weight in matched if direction == "bearish")
        direction = "Bullish" if bullish > bearish else "Bearish" if bearish > bullish else "Neutral"
        score = sum(weight for _, _, weight in matched)
        records.append(
            {
                "symbol": row["symbol"],
                "asset_type": row["asset_type"],
                "session_date": row["session_date"],
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
                "direction": direction,
                "score": score,
                "cpr_width_pct": round(float(row["cpr_width_percent"]), 3),
                "pivot": round(float(row["pivot"]), 2),
                "bc": round(float(row["bc"]), 2),
                "tc": round(float(row["tc"]), 2),
                "developing_pivot": round(float(row["developing_pivot"]), 2),
                "reasons": " · ".join(label for label, _, _ in matched) or "No configured CPR condition",
            }
        )
    result = pd.DataFrame(records)
    if result.empty:
        return result
    return result.sort_values(["score", "volume"], ascending=[False, False]).reset_index(drop=True)


def telegram_report(results: pd.DataFrame, limit: int = 10) -> str:
    if results.empty:
        return "CPR Scanner: no symbols had enough history to evaluate."
    as_of = max(results["session_date"])
    lines = [f"📊 CPR Scanner — {as_of}", "Top stocks to track (technical watchlist only):", ""]
    for rank, (_, row) in enumerate(results.head(limit).iterrows(), start=1):
        lines.append(f"{rank}. {row['symbol']} | {row['direction']} | score {row['score']}")
        lines.append(f"   ₹{row['close']} · {row['reasons']}")
    lines.extend(["", "End-of-day bhavcopy screen. Verify price/action before making any decision."])
    return "\n".join(lines)
