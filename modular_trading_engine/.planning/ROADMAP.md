# Roadmap

## Phase 1: Layer 1 - Data Pipeline
- Define data schemas and structs (OHLCV).
- Implement standard 1-minute historical feed parser.
- Setup pure interface bounds.

## Phase 2: Layer 2 - Core Domain
- [x] **Phase 2.0 (Completed)**: Isolate mathematical detectors (`hold_level.py`, `break_level.py`, `hard_close.py`, `origin_state_machine.py`) with unit tests.

### Phase 2.1: Remaining Horizontal Modules (Completed)
- [x] Implement `reverse_level.py` (Hold Levels tested twice).
- [x] Implement `deep_dive.py` (Tracking wicks piercing levels without Hard Close).
- [x] Implement `polarity_state.py` (Invalidation tracking target generation).
- [x] Implement `pandoras_box.py` (Neutral zone tracker between valid top/bottom Hold Levels).
- [x] Implement `trends.py` (`trend_tracker.py` for Diagonal and lateral connections).

### Phase 2.2: The Global Theory Board (Completed)
- [x] Implement `MarketTheoryState` class.
- [x] Route raw TopStep `candle` objects to all active trackers simultaneously.
- [x] Create real-time state querying interface for Layer 3 (Active Highlanders, Targets).

## Phase 3: Layer 3 - Strategy Playbooks
- [ ] Design JSON configuration parser based on `STRATEGY_SCHEMA_BLUEPRINT.md`.
- [ ] Implement Rule Engine to compare live `MarketTheoryState` (Phase 2.2) against JSON rules (e.g., `origin_tests_max`).
- [ ] Build execution signal output mechanism upon theory match.

## Phase 4: The Core Lab / Backtest Engine
- [ ] Scaffolding of a virtual Layer 1 (Historical CSV rapid ingestion) and virtual Layer 4 (Simulated execution metrics).
- [ ] Run full DayTrading Decrypted logic end-to-end to capture MFE/MAE matrices.
- [ ] Optimize limit offsets and target ratios using pure data output.

## Phase 5: Live Execution & TopStep Integration
- [ ] Connect `BrokerIntegrator` interface natively to TopStep WS/REST.
- [ ] Implement Fleet Commander orchestrator for real Multi-Account limits and bracket orders (OCO).
- [ ] Enforce max loss rules and Risk management.
