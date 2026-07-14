# Bazaar Mind Games

Bazaar Mind Games is a production-style MVP for intraday trading intelligence on Indian index futures. It focuses on context building, interpretable scoring, alerts, research, and model experimentation for instruments such as Nifty Futures and Bank Nifty Futures.

## Purpose

This platform is intentionally analytics-only. It does not place trades or connect to a broker. The goal is to help a discretionary or semi-systematic trader understand session structure, value migration, order-flow context, and setup quality.

## Highlights

- CSV-first ingestion for intraday bars
- Session-aware Market Profile, Volume Profile, Order Flow, Camarilla, CPR, VWAP, and session context features
- Interpretable rule-based setup scoring and alerts
- Deterministic labeling helpers for research
- Baseline ML training and evaluation scripts
- Lightweight backtest and journal analytics modules
- FastAPI service endpoints and a Streamlit dashboard
- NSE equity and F&O CPR scanner with official UDiFF bhavcopy download/upload
- Scheduled 9 PM IST Telegram watchlist reports with auditable scan reasons

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

Open **CPR Scanner** in the Streamlit sidebar. It can download recent official NSE UDiFF bhavcopies or scan uploaded CSV/ZIP files. The scanner covers narrow, ascending/descending, reversal, virgin, inside/outside, Camarilla S3/R3, and developing CPR conditions.

## Telegram CPR Report

Create a Telegram bot with BotFather, send the bot one message, and place its token and your chat ID in `.env`:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DASHBOARD_PASSWORD=use-a-long-private-password
CPR_REPORT_HOUR=21
CPR_REPORT_MINUTE=0
CPR_SCANNER_SEGMENTS=CM
CPR_REPORT_MAX_ATTEMPTS=3
CPR_REPORT_RETRY_MINUTES=15
```

Run `docker compose up --build` for the web dashboard, API, and persistent daily scheduler. Use `CPR_SCANNER_SEGMENTS=CM,FO` to include nearest-expiry futures. The configured timezone defaults to `Asia/Kolkata`. A failed nightly download or Telegram request is retried three times at 15-minute intervals by default.

The output is an end-of-day technical watchlist, not investment advice or an execution signal.

## Train Baseline Models

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
- model registry metadata and experiment tracking
