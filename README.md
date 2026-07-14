# Bazaar Mind Games

Bazaar Mind Games is a production-style MVP for intraday trading intelligence on Indian index futures. It focuses on context building, interpretable scoring, alerts, research, and model experimentation for instruments such as Nifty Futures and Bank Nifty Futures.

## Purpose

This platform is intentionally analytics-only. It does not place trades or connect to a broker. The goal is to help a discretionary or semi-systematic trader understand session structure, value migration, order-flow context, and setup quality.

## Highlights

- CSV-first ingestion for intraday bars
- Session-aware Market Profile, Volume Profile, Order Flow, Camarilla, CPR, VWAP, and session context features
- Interpretable rule-based setup scoring and alerts
- Deterministic labeling helpers for research
- Explicitly labeled demo-only ML training and evaluation scripts
- Lightweight backtest and journal analytics modules
- FastAPI service endpoints and a Streamlit dashboard
- NSE stock-futures CPR scanner with official F&O UDiFF bhavcopy download/upload
- Scheduled 9 PM IST Telegram watchlist reports with auditable scan reasons
- Branded professional workspace using the supplied Bazaar Mind Games logo, Montserrat display typography, Lato body typography, and the official teal/indigo/green/olive palette

## Repo Structure

```text
bazaar-mind-games/
  configs/
  data/
  src/
    ingestion/
    features/
    labels/
    rules/
    models/
    backtest/
    journal/
    api/
    dashboard/
    utils/
    services/
  tests/
  run_app.py
```

## Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run Tests

```powershell
python -m pytest
python run_app.py test
```

## Launch Everything

```powershell
python run_app.py
python run_app.py all
```

## Launch API Only

```powershell
uvicorn api.main:app --reload
python run_app.py api
```

## Launch Dashboard Only

```powershell
streamlit run src/dashboard/app.py
python run_app.py dashboard
```

Open **CPR Scanner** in the Streamlit sidebar. It downloads only the official NSE F&O UDiFF bhavcopy or scans uploaded F&O CSV/ZIP files. The universe is restricted to stock futures: modern `STF` rows are normalized to legacy `FUTSTK`; cash equities, index futures, and options are excluded. Each nightly scan retains only the 50 most liquid underlyings, ranked by 20-session median FUTSTK turnover aggregated across all expiries. CPR prices still use the nearest-expiry contract.

The action-board score is auditable. The original CPR/Camarilla conditions create the technical score. Aggregate futures OI then confirms or challenges that direction: long buildup is price up/OI up, short buildup is price down/OI up, short covering is price up/OI down, and long unwinding is price down/OI down. A matching buildup adds up to 3 points, a matching covering/unwinding regime adds 1, and conflicting OI subtracts 1–3; exceptional OI participation adds one more point in the same direction. OI never changes the CPR direction by itself.

The intraday setup-engine weights are transparent heuristics, not statistically calibrated
probabilities. They must be walk-forward tested on representative history before production use.

The latest official NSE combined-OI report supplies MWPL utilization using Future Equivalent Open Interest. Utilization from 80–90% subtracts 1 point, 90% or higher subtracts 3, and 95% or an official `No Fresh Positions` status prevents the candidate from entering the Telegram shortlist. If the separate MWPL report is temporarily unavailable, the scanner labels it unavailable instead of estimating it.

## Telegram CPR Report

Create a Telegram bot with BotFather, send the bot one message, and place its token and your chat ID in `.env`:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DASHBOARD_PASSWORD=use-a-long-private-password
CPR_REPORT_HOUR=21
CPR_REPORT_MINUTE=0
CPR_SCANNER_SEGMENTS=FO
CPR_REPORT_MAX_ATTEMPTS=3
CPR_REPORT_RETRY_MINUTES=15
```

Run `docker compose up --build` for the web dashboard, API, and persistent daily scheduler. Docker starts the dashboard in production mode, so `DASHBOARD_PASSWORD` is required. The scanner is fixed to the NSE F&O segment, excludes expired contracts, and selects the nearest valid-expiry stock future per symbol. The configured timezone defaults to `Asia/Kolkata`. APScheduler coalesces missed executions and performs a startup catch-up when today's report has not succeeded. A failed nightly download or Telegram request is retried three times at 15-minute intervals by default.

The output is an end-of-day technical watchlist, not investment advice or an execution signal.

## Train Baseline Models

These commands train demonstration baselines on the bundled sample data. Artifacts are marked
`demo_only`; displayed outputs are not calibrated trading probabilities.

```powershell
python -m models.train_day_type
python -m models.train_breakout_model
python -m models.train_reversal_model
```

## Sample Data

A small placeholder dataset lives at `data/samples/nifty_futures_sample.csv` so the MVP can run without external dependencies.

## Roadmap

- richer profile and auction-quality metrics
- live data connectors
- better day-type taxonomy and replay tooling
- richer journaling and setup review workflows
- representative historical datasets, walk-forward validation, probability calibration, and experiment tracking
