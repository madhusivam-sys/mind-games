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

Setup contract:
Each setup module must return:
- setup_name
- active
- direction
- score
- reasons
- invalidation
- targets
- context_fit

Initial setup list:
1. Initial Balance Breakout
2. Initial Balance Fade
3. Value Area Rotation Trade
4. Value Area Breakout
5. POC Magnet Trade
6. Poor High / Poor Low Repair
7. Single Print Retest
8. LVN Rejection
9. HVN Rotation
10. Double Distribution Continuation
11. Trend Day Pullback
12. Failed Trend Day
13. Inventory Correction
14. Gap and Go
15. Gap Fill
16. Value Migration Trend
17. Composite Balance Break
18. Acceptance Above Resistance
19. Rejection of Higher Prices
20. Absorption Setup
21. Delta Divergence
22. CVD Divergence
23. Stop Run Reversal
24. Liquidity Vacuum Move
25. Initiative vs Responsive Flip

Testing expectations:
- Add or update pytest coverage for every new setup module.
- Add focused unit or smoke tests for every changed non-trivial module.
- Do not add unnecessary test cases that do not protect behavior.
- Add prefix-stability tests for any feature or setup condition that could leak future information.
- Add API smoke coverage when setup output schemas change.
- Keep setup payload tests aligned with the setup contract above.
