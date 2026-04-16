# Phase 04.1: TradingView Pine Script Mechanics Parity Refactor

## Objective
Refactor the Layer 2 (Theory) and Layer 3 (Hold Level Trigger) backtesting logic to perfectly mirror the `pine editor` mechanics from TradingView. The goal is to move from theoretical structural fractals to literal sequence tracking (e.g. `red, green, green`), capturing the exact "best entry" Retroactive Lookback mechanics and stricter test validation requirements (`waitingOpposite`).

---

## 1. Break Level Creation (Candle Sequence vs Fractals)
We will rewrite the Break Level detection in `MarketTheoryState.process_candle` to match exactly your Pine definition:
*   **Bullish Break Level:** 1 Bearish candle, followed by 2 Bullish candles (`red, green, green`). The **LOW** of the first green candle becomes the Support Line.
*   **Bearish Break Level:** 1 Bullish candle, followed by 2 Bearish candles (`green, red, red`). The **HIGH** of the first red candle becomes the Resistance Line.

## 2. Highlander & Test Count Limit
*   We keep the logic exactly as it is now configured: `max_level_tests_allowed = 2`.
*   This perfectly matches "mag 0 of 1 keer getest zijn (als Origin Level)". 
    A Break Level + Test 1 + Test 2 = Wordt een Origin level. Daarna is hij nog geldig totdat Test 3 geraakt wordt.
*   **Geen extra wijzigingen nodig,** dit staat reeds ingesteld in de Playbook JSON en de Engine respects this.

## 3. Dynamische Hold Levels (De 'Beste Entry' Lookback Mode)
Dit is de grootste wijziging. We stappen af van statische `ReverseTrackers`.
*   **Nieuwe Logica in `VirginHoldLevelTrigger` (Layer 3):** Elke minuut itereren we over alle Active Highlander Origin Levels.
*   Voor elke Origin Level simuleren we jouw Pine Code `for j = lookback to 1` loop:
    *   We halen de geschiedenis van kaarsen op sinds de Original Bar (de bar waar de break is ontstaan).
    *   We scannen achteruit om de allerhoogste `Green Open` (voor een Bearish Origin) of laagste `Red Open` (voor een Bullish Origin) te vinden die **onder/boven** de muur is gebleven en niet met een Hard Close is gefaald of direct erna is afgestraft.
    *   Deze dynamisch gevonden prijs wordt de 'Best Hold Level'. 
    *   Als een level ongeraakt is (`holdTests == 0`), wordt daar een Limit Order gelegd.

## 4. Retest Validatie (waitingOpposite)
We passen `OriginTracker.process_candle` aan zodat een test pas telt als:
*   **Voor Weerstand (Bearish):** De prijs is eerst 'gescheiden' door **2 of meer RODE CANDLES**, gevolgd door een **GROENE CANDLE**. Pas daarna telt een overschrijding (high > price) waarbij de candle **groen** (`close > open`) sluit als een legitieme test (`lvl.testCount += 1`).
*   **Voor Support (Bullish):** Precies omgekeerd (2 of meer GROENE CANDLES, gevolgd door een RODE CANDLE, daarna een touch die **rood** sluit).

---

## Technical Approach
### Modified Files
*   **[MODIFY]** `src/layer2_theory/market_state.py`: Store L1 history cache, implement Red/Green Sequence Break detection. Remove `ReverseTracker` orchestration.
*   **[MODIFY]** `src/layer2_theory/origin_state_machine.py`: Add states `waiting_opposite` and `waiting_retest` tracking to enforce the color-sequence rules before allowing a test.
*   **[MODIFY]** `src/layer3_strategy/modules/hold_level_trigger.py`: Build the retro-lookback scanner for `bestLongHold` / `bestShortHold`.
*   **[DELETE]** `src/layer2_theory/reverse_level_tracker.py`: Becomes obsolete because Hold Levels aren't statically built anymore.

### Validation
We will run `test_pine_mechanics.py` over de 4 weken data en we verwachten wezenlijk andere (en betere) signalen die 1-op-1 matchen met TradingView.
