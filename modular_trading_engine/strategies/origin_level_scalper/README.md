# Origin Level Scalper Strategy

De **Origin Level Scalper** is een extreem pure en agressieve intraday daytrading strategie, exclusief ontworpen voor de Nasdaq E-mini (NQ / MNQ) markten. Waar oudere strategieën zoeken naar lange bevestigingen (Golden Setup), is de Origin Scalper volledig state-driven en slaat direct toe op de tweede test van een bewezen "Origin Level".

## Kernfilosofie
*   **Geen filters, pure prijsactie**: Deze strategie gebruikt standaard geen Premium/Discount filter of Cluster filter. Het vertrouwt 100% op de wiskundige validiteit van Break Levels.
*   **Limit Order Frontrunning**: In plaats van te wachten tot de prijs *in* de zone sluit, zet deze strategie direct na Test 1 een Limit Order klaar op de exacte grens van het level (plus een frontrun van 1 punt) om Test 2 haarscherp te vangen.
*   **Asymmetrisch Risico**: 1:2 Risk/Reward ratio. We riskeren 8.0 punten om er 16.0 te winnen. Pessimistische backtests tonen aan dat zelfs bij 1-minuut SL/TP collisions deze theorie winstgevend blijft.
*   **Isolatie & Hedging Beveiliging**: Maximaal 1 open positie. Zodra een limit order wordt gevuld, cancelt de L4 FleetCommander direct alle andere openstaande limits om hedging-restricties van Prop Firms (zoals Topstep) uit te sluiten.

## Playbook Configuratie

### 1. `OriginLevelTrigger`
- **Werking:** Scant in real-time de L2 `MarketTheoryState` op `OriginTracker` objecten.
- **Criteria:** Een level moet 1 succesvolle test hebben doorstaan (`test_count == 1`) én visueel zijn losgekomen van de test (`waiting_retest == True`).
- **P/D Filter:** Uitgeschakeld (`premium_discount_window_size: 0`). Alle gevalideerde levels zijn legitiem.

### 2. `KillzoneFilter`
Standaard NYC uitsluitingen (om onvoorspelbare volume-spikes te mijden):
- 09:20 - 09:40 EST (Open)
- 12:00 - 13:00 EST (Lunch)
- 15:49 - 18:00 EST (Slot/Maint)

### 3. `TTLTimeout`
- Als een Limit order langer dan 30 minuten klaarstaat zonder gevuld te worden, annuleert de engine de intentie om 'stale' setups te vermijden.

### 4. `RATLimitOrder`
- **Frontrun:** `entry_frontrun_ticks: 4` (1.0 punt frontrun om de fillkans te maximaliseren op de bounce).
- **SL:** 8.0 absolute punten.
- **TP:** 16.0 absolute punten.

## Prestaties (Backtest)
*Getest over ~4 maanden NQ data (Jan 2026 - Mei 2026).*
- **Aantal Trades:** ~2.268 trades
- **Win Rate:** ~54.2% (Ondanks pessimistische rendering van 1-minuut collisions).
- **Netto Winst (Simulatie):** >$200.000 op 1 NQ contract.
- **Drawdown:** Bewezen robuust onder de strikte Topstep/Apex limits ($2.000 max drawdown).

> **Waarschuwing:** Deze logica plaatst actief werkende Limit Orders direct in het orderboek van de broker. Zorg dat je L4 `LiveFleetCommander` configuratie goed omgaat met `max_positions: 1` door het annuleren van rest-orders zodra een fill plaatsvindt.
