# Modular Trading Engine

An institutional-grade, 100% modular, objective, and relentlessly scalable automated trading engine based on the CCTA (Core Content Trading Approach) framework.

## Core Vision & Values

1. **Absolute Separation of Concerns:** Theory is mathematical and immutable. The data layer knows nothing of the strategy layer.
2. **Generic & Modular (Lego Blocks):** Pure mathematical theory modules (Layer 2) connect to execution via clean JSON/YAML playbooks (Layer 3).
3. **Mathematical Objectivity:** Strict binary evaluation (True/False). No vague criteria.
4. **No Tech Debt:** Functions are small, specific, and explicitly typed to prevent god-classes.
5. **No Terminological Pollution:** Only predefined CCTA vocabulary (e.g., Hold Levels, Hard Close, Pandora's Box) is permitted. No external retail trading terms.

## High-Level Architecture

The system operates strictly across four distinct layers communicating via interfaces:

- **Layer 1: Data / Candle Engine**
  The backbone handling 1-minute OHLCV ingestion (TopStep REST/WS), caching, and timeframe-agnostic resampling.
  
- **Layer 2: Core Domain (Immutable Building Blocks)**
  Pure math detectors and validators that calculate price action (`hold_level.py`, `hard_close.py`, etc.). Operations do not factor in PnL, accounts, or strategy.

- **Layer 3: Variable Configuration (The Playbooks)**
  Strategy execution rules defined as declarative configurations (e.g., `max_origin_tests`). This layer pairs Layer 2 mathematical states against tactical intent.

- **Layer 4: Execution & Risk Management (The Vault)**
  Translates playbook signals to the broker via a Fleet Commander. Manages multi-account OCO routing, risk gates (news, max loss constraints), and position lifecycle observation.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| **Python Ecosystem** | Native suitability for MLX scaling, FastAPI async capabilities natively supporting Websockets. | Decided |
| **GSD Orchestration** | Ensures relentless adherence to layer separation without AI hallucinatory drift. | Decided |
| **JSON Strategy Playbooks** | Allows GUI-based strategy building in the future without touching Python Core execution code. | Decided |
| **Event Logging** | Full OHLCV recording on state-transitions mapped securely to post-trade MFE/MAE measurement. | Pending |

---
*Last updated: April 2026 after initialization*
