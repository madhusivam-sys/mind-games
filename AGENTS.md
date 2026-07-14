# AGENTS.md

Project: Bazaar Mind Games

Purpose:
Build an intraday trading intelligence system for Indian index futures using Market Profile, Volume Profile, Order Flow, Camarilla, CPR, and VWAP.

Operating rules:
- Prioritize interpretable rule-based logic over black-box predictions.
- No execution engine or broker order placement.
- Prevent forward-looking leakage in all features and labels.
- Keep modules small, typed, and testable.
- Return trader-readable reasons and invalidation logic for every setup.
- Prefer pandas/numpy implementations first.
- Add pytest tests for all non-trivial modules.
- Keep setup logic auditable.

Engineering guardrails:
- Keep live data connectors isolated under `src/ingestion/`.
- Keep feature generation under `src/features/` leak-safe and prefix-stable.
- Keep labels under `src/labels/` strictly separated from live scoring logic.
- Keep shared orchestration in `src/services/analysis.py`.
- Keep FastAPI endpoints thin and presentation-only logic inside `src/dashboard/`.
- Use `src/utils/config.py` for typed settings and repository paths.
- Use `src/utils/logging.py` for logger creation.
- Do not add duplicate business logic paths across API, dashboard, and research flows.
- If a dataset is too small for a stable train/test class split, prefer explicit baseline fallbacks over synthetic target manipulation.

Implemented setup contract:
Each score result returns:
- timestamp
- symbol
- setup_name
- score
- label
- reasons
- invalidation
- summary

Implemented setup list:
1. Responsive Buy
2. Responsive Sell
3. Breakout Continuation
4. Failed Breakout
5. Trap Detection
6. Absorption Warning
7. Confluence Score

The earlier 25-item list is a research backlog, not an implemented runtime contract. New
setups should be added individually with tests and documentation only when their rules exist.

Testing expectations:
- Add or update pytest coverage for every new setup module.
- Add focused unit or smoke tests for every changed non-trivial module.
- Do not add unnecessary test cases that do not protect behavior.
- Add prefix-stability tests for any feature or setup condition that could leak future information.
- Add API smoke coverage when setup output schemas change.
- Keep setup payload tests aligned with the setup contract above.
