# Requirements

## Validated & Engine Hardened

**Layer 1: Candle Engine**
- [x] Central OHLCV Datastore enabling deterministic resampling
- [x] Historical fast-loading (CSV) for offline & rapid backtesting
- [x] Safe isolation from downstream state modifications

**Layer 2: Core Domain (Immutable Mathematics)**
- [x] Implement `hold_level.py` (Push/Pullback validation logic)
- [x] Implement `break_level.py` (Sequence tracking)
- [x] Implement `origin_state_machine.py` (Pure Pine Script logic parity: `waiting_opposite`, `test_count`)
- [x] Implement `hard_close.py` (Strict True/False boundary intersection validator)
- [x] Isolated interface ensuring NO dependency on PnL or trade configurations
- [x] Categorie B Trackers (Reverse, Polarity, DeepDive, Trend) were PURGED to maintain lean domain performance.

**Layer 3: Strategy Playbooks**
- [x] JSON schema loader / parser for tactical configurations (`config_parser.py`)
- [x] Generic Rule Engine to dynamically execute modules against Market States
- [x] Base modules isolated (`ConfirmationHoldLevelTrigger`, `TTLTimeout`, `RATLimitOrderExecution`, `KillzoneFilter`)

**Layer 4: Execution Vault**
- [x] Fleet Commander orchestrator (`live_fleet_commander.py`) capable of routing signals autonomously
- [x] Native TopStepX Broker Interface mapping REST API payloads
- [x] Local Backtesting Simulator simulating strict gray-candle math

## Active / Next
- [ ] Implement `manage_breakeven` mechanics strictly across Live and Simulator modules in L4.
- [ ] Central DB Event Logging exporting state changes across multiple terminal sessions for offline validation.

## Out of Scope
- [Direct Frontend / React UI] — Handled in parallel / later milestones. Architecture remains strictly 100% headless/CLI.
- [AI optimization of the playbook strings itself] — Optimization comes after robust mechanical tracking is assured.
