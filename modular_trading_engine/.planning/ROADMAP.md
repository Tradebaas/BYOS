# Roadmap

## Phase 1: Layer 1 - Data Pipeline
- [x] Define data schemas and structs (OHLCV).
- [x] Implement standard 1-minute historical feed parser.
- [x] Setup pure interface bounds.

## Phase 2: Layer 2 - Core Domain
- [x] **Phase 2.0**: Isolate mathematical detectors (`hold_level.py`, `break_level.py`, `hard_close.py`, `origin_state_machine.py`) with unit tests.
- [x] **Phase 2.1**: Refactoring and removing legacy/category B trackers to streamline calculations. 
- [x] **Phase 2.2**: The Global Theory Board. Create `MarketTheoryState` class to route TopStep candles via pure Pine Script mechanics (test counts, waiting opposite constraints).

## Phase 3: Layer 3 - Strategy Playbooks
- [x] Design JSON configuration parser based on Playbook architecture.
- [x] Implement Rule Engine to compare live `MarketTheoryState` against JSON rules.
- [x] Enforce Strategy Containerization (strategies live in their own JSON folders without mutating code).

## Phase 4: The Core Lab / Backtest Engine
- [x] Scaffolding of a virtual Layer 1 and virtual Layer 4 (Simulated execution metrics).
- [x] Run full Logic via offline simulator, validating exact Pine Script logic parity.
- [x] Optimize limit order execution using `tick_size` dynamic math and execution interfaces.

## Phase 5: Live Execution & Broker Integration (Production Hardening)
- [x] Connect execution interface natively to REST API via `live_fleet_commander.py`.
- [x] Completely decouple and purge all old Web sockets and UI logic to enforce Terminal-First CLI architecture.
- [x] Fortify architecture via `pytest-archon` and pre-commit Git hooks ensuring Layer 1-4 modular boundaries remain unbroken.
- [x] **ACHIEVED: Production Ready for Live Fleet execution across Prop Firm accounts.**

## Phase 6: System Scaling
**Goal:** Abstract scaling across multiple instances and new strategy playbooks natively.
**Status:** Ongoing iteration inside local Strategy repositories.
