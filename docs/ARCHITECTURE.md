# Bazaar Mind Games Architecture

## Purpose

Bazaar Mind Games is an analytics-only intraday trading intelligence system for Indian index futures. It builds auction-market context from market data, scores interpretable setups, exposes the results through REST APIs, and presents them in a lightweight Streamlit dashboard. It does not place trades or connect to a broker execution API.

## Runtime Surfaces

The project has three runtime surfaces:

- FastAPI REST API: the contract-first backend surface for ingestion, analysis, live market data, signals, and runtime controls.
- Streamlit dashboard: a lightweight operator UI that consumes REST APIs instead of duplicating business logic.
- Docker image: a portable runtime image for API and dashboard services.

## Source Layout

```text
src/
  api/            FastAPI app, routers, request/response schemas
  dashboard/      Streamlit UI, API client, reusable display components
  services/       Application orchestration and workflow services
  integrations/   External market-data and broker/alert client boundaries
  features/       Leak-safe feature engineering
  rules/          Interpretable setup scoring and alert rules
  labels/         Offline research labels, separated from live scoring
  models/         Baseline model training, registry, and inference
  ingestion/      CSV/session loading and validation
  backtest/       Lightweight scenario and metrics engine
  journal/        Trade review and analytics helpers
  utils/          Shared config, time, math, and logging utilities
```

## End-to-End Workflow

1. Market data enters through `services.market_data_service`.
2. Data is loaded either from CSV samples or live REST integrations.
3. Feature modules calculate VWAP, CPR, Camarilla, profile, order-flow, and session context.
4. Rule modules score setups and produce trader-readable reasons, invalidation, targets, and labels.
5. Service orchestration packages features, scores, alerts, model predictions, and briefing text.
6. FastAPI routers expose these payloads as REST endpoints with generated OpenAPI documentation.
7. The Streamlit dashboard calls the REST API through `dashboard.api_client`.
8. The dashboard renders the backend-owned context and API console without duplicating scoring logic.

## REST and OpenAPI Contract

FastAPI generates the OpenAPI document at:

```text
/openapi.json
/docs
```

Future API changes should:

- Add or update Pydantic request/response schemas in `src/api/schemas.py` or route-local typed models.
- Keep routers thin and delegate workflow behavior to services.
- Preserve backward-compatible response keys unless a versioned route replaces them.
- Add API smoke tests when output schemas or route behavior changes.
- Update the dashboard API catalog when a public endpoint is added, removed, or renamed.

## SOLID Design Rules

- Single Responsibility: feature modules calculate features, rule modules score setups, services orchestrate workflows, routers expose HTTP contracts, and dashboard modules render UI.
- Open/Closed: add new setup logic through new rule functions/classes and service composition rather than rewriting endpoint handlers.
- Liskov Substitution: integration clients should preserve method contracts so fake clients in tests can replace live providers.
- Interface Segregation: dashboards and routers should depend on narrow service methods, not broad concrete implementation details.
- Dependency Inversion: high-level services should depend on client/service interfaces or injected collaborators where practical.

## Decoupling and Future Microservices

The current monolith is intentionally modular. To migrate toward microservices later, split along these boundaries:

- Market data service: live data, history, ticks, option chain, and index components.
- Analysis service: feature generation, setup scoring, alerts, and briefings.
- Model service: model registry and inference.
- Dashboard/UI service: REST-consuming presentation layer.

To keep that path open:

- Do not import dashboard modules from API/services.
- Do not call external providers directly from routers.
- Keep payloads JSON-serializable and schema-first.
- Keep business rules out of Streamlit pages.
- Keep test fakes aligned with integration client contracts.

## Module Documentation Expectations

Each non-trivial module should explain:

- What responsibility it owns.
- What inputs it accepts.
- What output contract it returns.
- Any leakage, data-quality, or session-boundary assumptions.

Each class should have a short docstring describing its role. Comments should explain non-obvious trading logic, orchestration, or failure handling. Avoid comments that merely restate code.

## Testing Strategy

Testing should stay focused and behavioral:

- Unit tests for feature calculations, labels, setup scoring, and service orchestration.
- API smoke tests for REST routes and OpenAPI coverage.
- Dashboard catalog tests to keep the UI aligned with public API paths.
- Prefix-stability tests for any feature or setup condition that could leak future information.
- Docker smoke tests in CI to verify the image can import the FastAPI app.

Avoid unnecessary test cases that do not protect behavior.

## Local Commands

```powershell
.\venv\Scripts\python.exe -m pytest -q
$env:PYTHONPATH = "src"; .\venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
$env:PYTHONPATH = "src"; .\venv\Scripts\python.exe -m streamlit run src/dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

## CI Workflow

GitHub Actions runs:

1. Python dependency installation.
2. Pytest unit and smoke tests.
3. FastAPI app import smoke test.
4. Docker image build.
5. FastAPI app import smoke test inside Docker.
