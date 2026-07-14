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
NSE_COMBINED_OI_URL = f"{NSE_ARCHIVE_ROOT}/nsccl/combineoi.zip"


class BhavcopyError(ValueError):
    """Raised when an NSE bhavcopy cannot be downloaded or normalised."""


@dataclass(frozen=True, slots=True)
class ScanConfig:
    narrow_percentile: float = 0.30
    max_narrow_width_percent: float = 0.70
    camarilla_tolerance_percent: float = 0.35
    minimum_history: int = 3
    universe_size: int = 50
    liquidity_lookback: int = 20


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
    "open_interest": ("opnintrst", "openinterest", "openint", "oi"),
    "change_in_open_interest": ("chnginopnintrst", "changeinopeninterest", "changeinoi", "chginoi"),
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
    """Build one row per stock/day with nearest-expiry OHLC and all-expiry participation."""

    normalised = pd.DataFrame(index=frame.index)
    normalised["session_date"] = _parse_dates(_column(frame, "date", required=True)).dt.date
    normalised["symbol"] = _column(frame, "symbol", required=True).astype(str).str.strip().str.upper()
    normalised["series"] = _column(frame, "series").fillna("").astype(str).str.strip().str.upper()
    normalised["instrument"] = _column(frame, "instrument").fillna("").astype(str).str.strip().str.upper()
    normalised["expiry"] = _parse_dates(_column(frame, "expiry"))
    normalised["option_type"] = _column(frame, "option_type").fillna("").astype(str).str.strip().str.upper()
    for column in ("open", "high", "low", "close", "volume", "turnover", "open_interest", "change_in_open_interest"):
        normalised[column] = pd.to_numeric(_column(frame, column, required=column in {"open", "high", "low", "close"}), errors="coerce")

    normalised = normalised.dropna(subset=["session_date", "symbol", "open", "high", "low", "close"])
    normalised = normalised[(normalised["symbol"] != "") & (normalised["high"] >= normalised["low"])]

    # Keep the scanner futures-only. UDiFF uses STF for stock futures while
    # legacy files use FUTSTK; both are normalized to the canonical FUTSTK
    # label. Cash shares, options, and index futures are intentionally excluded.
    is_stock_future = normalised["instrument"].isin(["STF", "FUTSTK"])
    future_rows = normalised[is_stock_future].copy()
    valid_expiry = future_rows["expiry"].isna() | (
        future_rows["expiry"].dt.date >= future_rows["session_date"]
    )
    future_rows = future_rows[valid_expiry].copy()
    future_rows["instrument"] = "FUTSTK"
    future_rows["asset_type"] = "F&O Stock Future"
    if not future_rows.empty:
        keys = ["symbol", "session_date"]
        aggregates = future_rows.groupby(keys, as_index=False, sort=False).agg(
            aggregate_volume=("volume", "sum"),
            aggregate_turnover=("turnover", "sum"),
            aggregate_open_interest=("open_interest", "sum"),
            reported_oi_change=("change_in_open_interest", "sum"),
            futures_expiries=("expiry", "nunique"),
        )
        nearest = future_rows.sort_values([*keys, "expiry"], na_position="last").groupby(keys, as_index=False, sort=False).first()
        future_rows = nearest.merge(aggregates, on=keys, how="left")

    result = future_rows.reset_index(drop=True)
    if result.empty:
        raise BhavcopyError("No NSE stock-futures contracts (FUTSTK/STF) were found in the supplied F&O bhavcopy")
    return result.sort_values(["symbol", "session_date"]).drop_duplicates(["symbol", "session_date", "asset_type"], keep="last").reset_index(drop=True)


def normalise_mwpl(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalise NSE's combined-OI report into one current row per symbol."""

    lookup = {_key(column): column for column in frame.columns}

    def field(*aliases: str, required: bool = True) -> pd.Series:
        for alias in aliases:
            if alias in lookup:
                return frame[lookup[alias]]
        if required:
            raise BhavcopyError(f"Combined-OI report is missing {aliases[0]!r}")
        return pd.Series(index=frame.index, dtype="object")

    result = pd.DataFrame(index=frame.index)
    result["symbol"] = field("nsesymbol", "symbol").astype(str).str.strip().str.upper()
    result["mwpl"] = pd.to_numeric(field("mwpl"), errors="coerce")
    result["combined_open_interest"] = pd.to_numeric(field("openinterest"), errors="coerce")
    result["future_equivalent_open_interest"] = pd.to_numeric(
        field("futureequivalentopeninterest", "futeqoi", required=False), errors="coerce"
    ).fillna(result["combined_open_interest"])
    limit = field("limitfornextday", required=False).fillna("").astype(str).str.strip()
    result["mwpl_ban"] = limit.str.contains("no fresh", case=False, regex=False)
    result["mwpl_utilization_pct"] = result["future_equivalent_open_interest"] / result["mwpl"].replace(0, np.nan) * 100.0
    return result.dropna(subset=["symbol", "mwpl"]).drop_duplicates("symbol", keep="last").reset_index(drop=True)


def download_mwpl_snapshot(client: httpx.Client | None = None) -> pd.DataFrame:
    """Download the latest official combined open-interest/MWPL snapshot."""

    owned_client = client is None
    http = client or httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 CPRScanner/1.0"})
    try:
        response = http.get(NSE_COMBINED_OI_URL)
        response.raise_for_status()
        return normalise_mwpl(_read_csv_payload(response.content, "combineoi.zip"))
    finally:
        if owned_client:
            http.close()


def attach_mwpl_snapshot(history: pd.DataFrame, snapshot: pd.DataFrame) -> pd.DataFrame:
    """Attach current MWPL fields only to the latest session in history."""

    result = history.copy()
    columns = ["mwpl", "combined_open_interest", "future_equivalent_open_interest", "mwpl_utilization_pct", "mwpl_ban"]
    for column in columns:
        result[column] = np.nan if column != "mwpl_ban" else False
    latest = result["session_date"].eq(result["session_date"].max())
    values = result.loc[latest, ["symbol"]].merge(snapshot[["symbol", *columns]], on="symbol", how="left")
    for column in columns:
        result.loc[latest, column] = values[column].to_numpy()
    result["mwpl_ban"] = result["mwpl_ban"].fillna(False).astype(bool)
    return result


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
    mwpl_snapshot: pd.DataFrame | None = None
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
        try:
            mwpl_snapshot = download_mwpl_snapshot(http)
        except (httpx.HTTPError, BhavcopyError, BadZipFile):
            # Do not block CPR/OI scanning when the separate MWPL report is late.
            pass
    finally:
        if owned_client:
            http.close()
    history = pd.concat(frames, ignore_index=True).sort_values(["symbol", "session_date"]).drop_duplicates(
        ["symbol", "session_date", "asset_type"], keep="last"
    ).reset_index(drop=True)
    return attach_mwpl_snapshot(history, mwpl_snapshot) if mwpl_snapshot is not None else history


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
    rows["aggregate_volume"] = rows.get("aggregate_volume", rows["volume"]).fillna(0)
    rows["aggregate_turnover"] = rows.get(
        "aggregate_turnover", rows.get("turnover", pd.Series(0.0, index=rows.index))
    ).fillna(0)
    rows["aggregate_open_interest"] = rows.get("aggregate_open_interest", pd.Series(np.nan, index=rows.index))
    group = rows.groupby(["asset_type", "symbol"], sort=False)
    rows["price_change_pct"] = group["close"].pct_change(fill_method=None) * 100.0
    rows["oi_change_pct"] = group["aggregate_open_interest"].pct_change(fill_method=None) * 100.0
    rows["volume_oi_ratio"] = rows["aggregate_volume"] / rows["aggregate_open_interest"].replace(0, np.nan)
    rows["liquidity_turnover"] = group["aggregate_turnover"].transform(
        lambda series: series.rolling(config.liquidity_lookback, min_periods=1).median()
    )
    rows["liquidity_volume"] = group["aggregate_volume"].transform(
        lambda series: series.rolling(config.liquidity_lookback, min_periods=1).median()
    )
    rows["oi_change_percentile"] = group["oi_change_pct"].transform(
        lambda series: series.abs().rolling(20, min_periods=config.minimum_history).rank(pct=True)
    )
    rows["volume_oi_median"] = group["volume_oi_ratio"].transform(
        lambda series: series.rolling(20, min_periods=config.minimum_history).median()
    )
    price_up = rows["price_change_pct"] > 0
    oi_up = rows["oi_change_pct"] > 0
    rows["oi_regime"] = np.select(
        [price_up & oi_up, ~price_up & oi_up, price_up & ~oi_up, ~price_up & ~oi_up],
        ["Long buildup", "Short buildup", "Short covering", "Long unwinding"],
        default="Indeterminate",
    )
    indeterminate = (
        rows["price_change_pct"].isna()
        | rows["oi_change_pct"].isna()
        | rows["price_change_pct"].eq(0)
        | rows["oi_change_pct"].eq(0)
    )
    rows.loc[indeterminate, "oi_regime"] = "Indeterminate"
    rows["high_oi_participation"] = (rows["oi_change_percentile"] >= 0.80) & (
        rows["volume_oi_ratio"] > rows["volume_oi_median"]
    )

    rows["pivot"], rows["bc"], rows["tc"] = _cpr(rows["prev_high"], rows["prev_low"], rows["prev_close"])
    rows["developing_pivot"], rows["developing_bc"], rows["developing_tc"] = _cpr(rows["high"], rows["low"], rows["close"])
    rows["prev_pivot"] = group["pivot"].shift(1)
    rows["prev_bc"] = group["bc"].shift(1)
    rows["prev_tc"] = group["tc"].shift(1)
    rows["cpr_width_percent"] = ((rows["tc"] - rows["bc"]) / rows["pivot"].replace(0, np.nan) * 100.0).abs()
    rows["width_percentile"] = group["cpr_width_percent"].transform(lambda series: series.rolling(20, min_periods=config.minimum_history).rank(pct=True))

    prior_range = rows["prev_high"] - rows["prev_low"]
    rows["h3"] = rows["prev_close"] + (prior_range * 1.1 / 4.0)
    rows["l3"] = rows["prev_close"] - (prior_range * 1.1 / 4.0)
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
    rows["near_h3"] = (rows["close"] - rows["h3"]).abs() <= tolerance
    rows["near_l3"] = (rows["close"] - rows["l3"]).abs() <= tolerance
    rows["developing_ascending"] = rows["developing_bc"] > rows["tc"]
    rows["developing_descending"] = rows["developing_tc"] < rows["bc"]
    rows["developing_inside"] = (rows["developing_bc"] >= rows["bc"]) & (rows["developing_tc"] <= rows["tc"])
    rows["developing_outside"] = (rows["developing_bc"] <= rows["bc"]) & (rows["developing_tc"] >= rows["tc"])
    return rows


def scan_latest(history: pd.DataFrame, config: ScanConfig = ScanConfig()) -> pd.DataFrame:
    features = build_scan_features(history, config)
    latest = features.groupby(["asset_type", "symbol"], sort=False, as_index=False).tail(1).copy()
    latest = latest[latest["prev_tc"].notna()].copy()
    liquidity = latest["liquidity_turnover"].where(latest["liquidity_turnover"] > 0, latest["liquidity_volume"])
    latest["liquidity_metric"] = liquidity.fillna(0)
    latest = latest.nlargest(min(config.universe_size, len(latest)), ["liquidity_metric", "liquidity_volume"]).copy()
    latest["liquidity_rank"] = latest["liquidity_metric"].rank(method="first", ascending=False).astype(int)

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
        ("near_h3", "Close near Camarilla H3", "bullish", 1),
        ("near_l3", "Close near Camarilla L3", "bearish", 1),
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
        technical_score = sum(weight for _, _, weight in matched)
        regime = str(row.get("oi_regime", "Indeterminate"))
        regime_scores = {
            "Bullish": {"Long buildup": 3, "Short buildup": -2, "Short covering": 1, "Long unwinding": -1},
            "Bearish": {"Long buildup": -2, "Short buildup": 3, "Short covering": -1, "Long unwinding": 1},
            "Neutral": {},
        }
        oi_score = regime_scores[direction].get(regime, 0)
        if bool(row.get("high_oi_participation", False)) and oi_score:
            oi_score += 1 if oi_score > 0 else -1
        utilization = row.get("mwpl_utilization_pct", np.nan)
        ban_value = row.get("mwpl_ban", False)
        banned = bool(ban_value) if pd.notna(ban_value) else False
        mwpl_score = (
            -3
            if banned or (pd.notna(utilization) and float(utilization) >= 90)
            else -1
            if pd.notna(utilization) and float(utilization) >= 80
            else 0
        )
        eligible = not banned and not (pd.notna(utilization) and float(utilization) >= 95)
        score = max(0, technical_score + oi_score + mwpl_score)
        records.append(
            {
                "symbol": row["symbol"],
                "asset_type": row["asset_type"],
                "session_date": row["session_date"],
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
                "direction": direction,
                "score": score,
                "technical_score": technical_score,
                "oi_score": oi_score,
                "mwpl_score": mwpl_score,
                "oi_regime": regime,
                "oi_change_pct": round(float(row["oi_change_pct"]), 2) if pd.notna(row.get("oi_change_pct")) else np.nan,
                "open_interest": int(row["aggregate_open_interest"]) if pd.notna(row.get("aggregate_open_interest")) else 0,
                "mwpl_utilization_pct": round(float(utilization), 1) if pd.notna(utilization) else np.nan,
                "mwpl_ban": banned,
                "eligible": eligible,
                "liquidity_rank": int(row["liquidity_rank"]),
                "liquidity_turnover": float(row["liquidity_turnover"]),
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
    return result.sort_values(["eligible", "score", "liquidity_rank"], ascending=[False, False, True]).reset_index(drop=True)


def telegram_report(results: pd.DataFrame, limit: int = 10) -> str:
    if results.empty:
        return "CPR Scanner: no symbols had enough history to evaluate."
    as_of = max(results["session_date"])
    lines = [f"📊 CPR + OI Scanner — {as_of}", "Top 50 liquid FUTSTK universe · technical watchlist only:", ""]
    eligible = results[results["eligible"]] if "eligible" in results else results
    for rank, (_, row) in enumerate(eligible.head(limit).iterrows(), start=1):
        lines.append(f"{rank}. {row['symbol']} | {row['direction']} | score {row['score']}")
        oi_text = (
            f"{row.get('oi_regime', 'OI unavailable')} ({row.get('oi_change_pct'):+.1f}%)"
            if pd.notna(row.get("oi_change_pct"))
            else "OI unavailable"
        )
        mwpl_text = (
            f"MWPL {row['mwpl_utilization_pct']:.1f}%"
            if pd.notna(row.get("mwpl_utilization_pct"))
            else "MWPL unavailable"
        )
        lines.append(f"   ₹{row['close']} · {oi_text} · {mwpl_text}")
        lines.append(f"   {row['reasons']}")
    lines.extend(["", "End-of-day bhavcopy screen. Verify price/action before making any decision."])
    return "\n".join(lines)
