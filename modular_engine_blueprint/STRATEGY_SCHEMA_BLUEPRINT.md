# Strategy Schema Blueprint

This document defines the configuration-driven **Strategy Playbook**. It separates the execution logic (the "Reference Strategy") from the mathematically pure Theory Engine (which persists Break, Origin, and Hold Levels). By isolating the execution rules, any interface can construct, visually edit, and deploy trading strategies without modifying the underlying Python core.

## 1. Concept: Theory Memory vs. Strategy Execution

*   **Theory Memory (The Engine)**: Records every pivot, Hold Level, Break Level, and Origin Level based purely on market mechanics. It tracks the "Highlander" lifecycle of Origin Levels indefinitely until invalidated by a Hard Close.
*   **Strategy Execution (The Playbook)**: Evaluates whether a recorded theory object fits specific trading conditions (e.g., maximum tests, timeframe matching, hold level formations).

## 2. The Reference Strategy Playbook

The flagship strategy targets a pullback validation after a polarity shift. The playbook specifies its parameters declaratively.

### 2.1 Configuration Schema

```json
{
  "strategy_id": "ccta_reference_strategy_base",
  "timeframes": ["1m"],
  "monitoring": {
    "target_level": "origin_level",
    "required_polarity": true
  },
  "invalidation_rules": {
    "origin_tests_max": 1,
    "time_expiry_after_hold_validation": {
      "type": "candles",
      "value": 20
    }
  },
  "entry_rules": {
    "condition": "untested_hold_level_post_origin",
    "order_type": "LIMIT",
    "order_placement": "exact_hold_level",
    "stacking_preference": "oldest_origin"
  }
}
```

### 2.2 Break-down of Execution Rules

1.  **Monitoring Target (`origin_level`)**: The playbook binds exclusively to Origin Levels generated within the specified `timeframes` (1m).
2.  **Trade Invalidation (`origin_tests_max: 1`)**: Although the Origin Level persists mathematically as long as the Highlander rule holds, this *specific strategy* requires that the Origin Level has been tested no more than once after its initial confirmation.
3.  **Entry Trigger (`untested_hold_level_post_origin`)**: The strategy waits for the formation and confirmation (via Hard Close) of a new Hold Level formed *post* Origin creation.
4.  **Order Placement (`LIMIT`)**: An exact Limit Order is placed at the numerical value of the newly validated Hold Level. Market orders are explicitly avoided for this strategy.
5.  **Expiry (`time_expiry_after_hold_validation`)**: The limit order is held open for exactly 20 candles/minutes starting from the precise moment the Hold Level achieved **Valid** status (the moment the Hard Close occurred).

## 3. Playbook Engineering Mandates

1.  **No Context Dilution**: A strategy schema cannot change how a level is defined. It can only filter when a defined level is acted upon.
2.  **Frontend Agnostic**: The JSON structure maps 1:1 with any no-code visual strategy builder. Every key must map to a deterministic validation function in the engine's playbook evaluator.
