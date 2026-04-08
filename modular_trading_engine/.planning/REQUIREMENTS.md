# Requirements

## Validated

(None yet — ship to validate)

## Active

**Layer 1: Candle Engine**
- [ ] Central OHLCV Datastore enabling deterministic resampling
- [ ] Historical fast-loading (CSV/Database) for offline & rapid backtesting
- [ ] Live WebSocket data stream compatibility

**Layer 2: Core Domain (Immutable Mathematics)**
- [x] Implement `hold_level.py` (Push/Pullback validation logic)
- [x] Implement `break_level.py` (Candle structure & tracking logic)
- [x] Implement `origin_state_machine.py` (Separation sequence & Highlander logic)
- [x] Implement `hard_close.py` (Strict True/False boundary intersection validator)
- [x] Isolated interface ensuring NO dependency on PnL or trade configurations
- [ ] Implement `reverse_level.py` (Escalated Hold Levels)
- [ ] Implement `deep_dive.py` (Test state modifier)
- [ ] Implement `polarity_state.py` (Targeting mechanics after Hard Close invalidation)
- [ ] Implement `pandoras_box.py` (Neutral price enclosure tracking)
- [ ] Implement `trends.py` (Horizontal & diagonal theory extensions)
- [ ] Implement mathematical isolation for Entry mechanisms (Layer 3 delegates RATs, Shields, Triggers as pure playbook configs, not Layer 2 calculations)

**Layer 3: Strategy Playbooks**
- [ ] JSON schema loader / parser for tactical configurations
- [ ] Generic Rule Engine to compare Layer 2 output against Playbook conditions
- [ ] One canonical "Reference Strategy" schema mapped to base CCTA concepts

**Layer 4: Execution Vault**
- [ ] Fleet Commander orchestrator capable of abstract multi-account routing
- [ ] Native TopStepX Broker Interface wrapper (translating generic orders to API actions)
- [ ] Trade Operations Logger exporting state changes, MFE/MAE strings, and final trade logic to central DB/table store

## Out of Scope

- [Direct Frontend / React UI] — Handled in parallel / later milestones.
- [AI optimization of the playbook strings itself] — Optimization comes after robust mechanical tracking is assured.
