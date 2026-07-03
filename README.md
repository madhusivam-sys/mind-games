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
