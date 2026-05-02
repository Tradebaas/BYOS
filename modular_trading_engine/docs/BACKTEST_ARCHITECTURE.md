# Backtest Engine Execution Architecture
*Documentatie over de robuuste, offline test-faciliteiten (Command Line).*

Dit document dient als referentie om lokaal gigantische datasets af te handelen met exact dezelfde handels-architectuur als de Live Bot. 

Het grote voordeel van deze architectuur is dat Layer 2 & 3 (Theorie & Strategie) **exact hetzelfde** werken als in de Live Bot. Alleen Layer 4 (de netwerk-laag van TopstepX) wordt vervangen voor een lokale tijdmachine. Er is **geen Node.js, geen front-end UI en geen FastAPI server**. Waarderende lean-development en terminal snelheid.

---

## 📂 0. Project Structuur (Live vs. Backtest)

De scripts zijn opgesplitst in twee expliciete mappen om productie- en research-code fysiek te scheiden:

```
scripts/
├── live/                           ← Productie (Live Trading)
│   └── get_topstep_accounts.py     ← Account discovery & JWT test
│
└── backtest/                       ← Research & Validatie
    ├── run_backtest.py             ← De 1-minuut bar simulator (M1)
    ├── build_data_lake.py          ← Historische NQ data pomp
    ├── build_es_data_lake.py       ← Historische ES data pomp
    └── verify_lake.py              ← Integriteitscheck op CSV data
```

De **Live Bot** zelf (`live_fleet_commander.py`) draait **niet** vanuit `scripts/` — die leeft in `src/layer4_execution/` als onderdeel van de engine-kern. Het onderscheid is:

| Entrypoint | Doel | Locatie |
|---|---|---|
| `live_fleet_commander.py` | Live trading bot (TopstepX WebSocket) | `src/layer4_execution/` |
| `run_backtest.py` | Offline M1 bar-simulatie | `scripts/backtest/` |
| `get_topstep_accounts.py` | Live account/JWT utility | `scripts/live/` |

> **Waarom `simulator.py`, `data_vault.py` en `backtest_engine.py` in `src/layer4_execution/` staan:**
> De backtest-engine implementeert dezelfde interface als de live broker-executielaag. De `pytest-archon` architectuurverifiers eisen dat executielogica in Layer 4 leeft — verplaatsing zou de architectuurtests breken. De `BacktestSession` (in `backtest_engine.py`) bundelt deze componenten tot één Single Source of Truth voor simulaties. De scripts in `scripts/backtest/` zijn uitsluitend dunne CLI-wrappers die de `BacktestSession` aanroepen.

---

## 💾 1. Data Acquisitie (De Brandstof)
*Jij hebt historische data nodig om de simulator te voeden.*

### Bar-data (M1 Candles)

* **`data/historical/NQ_1min.csv`** — Het bestand met historische 1-minuut koersen.
* **`scripts/backtest/build_data_lake.py`** — **De Pomp.** Trekt bulkdata uit TopstepX REST API naar de `historical/` map. Gebruikt de headless JWT-authenticatie.
* **`scripts/backtest/build_es_data_lake.py`** — Identiek, maar voor E-mini S&P 500 (ES) futures.
* **`scripts/backtest/verify_lake.py`** — Controleert de integriteit en continuïteit van de CSV data (gaps, duplicaten, timestamps).

---

## 🏎 2. De M1 Bar Simulator (De Motor)
*De snelle "Offline-TopstepX" die maanden aan data in seconden doorslikt.*

* **`src/layer4_execution/backtest_engine.py` (De BacktestSession)**
   * **Rol: De Centrale Offline Engine.** Waar de live bot draait via `live_fleet_commander.py`, draait de backtest EXCLUSIEF via de `BacktestSession` class. Deze class combineert de data vault, de rules engine, en de pessimistische simulator logica. Het stript alle custom for-loops en fungeert als de Single Source of Truth.
   
* **`scripts/backtest/run_backtest.py`**
   * **Rol: De Tijdreiziger (CLI Wrapper).** Start dit script via de CLI en wijs een strategie aan (`--strategy <naam>`). Het script laadt de CSV-data, roept `BacktestSession.run()` aan, en print een geformatteerd PnL-rapport inclusief de nieuwste broker commissies. Slippage en fees worden wiskundig meeberekend.

```bash
# Backtest de DTD Golden Setup over de laatste 10 dagen:
cd modular_trading_engine
python3 scripts/backtest/run_backtest.py --strategy dtd_golden_setup --days 10

# Specifiek datumbereik:
python3 scripts/backtest/run_backtest.py --strategy dtd_golden_setup --start 2026-04-01 --end 2026-04-15
```

---

## 📊 3. Exporteren & Validatie
In de afwezigheid van flash dashboards, rapporteren alle backtest-scripts harde, betrouwbare metrics via JSON/CSV dumps of terminal-prints: Total Profit, Win-Rates, Consecutieve drawdowns en exact getimede executie-logs per seconde.

**Kortgezegd:** 
Waar de **Live Bot** leest uit: `Topstep WebSocket → Playbook Rules → Live Broker Executie`,
Leest de **M1 Backtester** uit: `Lokale CSV File → Playbook Rules → FAST-FWD Terminal Executie`.

---

## 🧠 4. Lessons Learned & Execution Parity (The GSD Method)

### The Intra-bar Granularity Illusion
Wanneer backtests draaien op M1 (1 minuut) data, ontstaat er een dodelijke blinde vlek bij limit orders die in *hetzelfde* tijdsframe worden gevuld waarin ook een TP (Take Profit) of SL (Stop Loss) geraakt zou kunnen worden. Backtesters vergelijken vaak statisch of de `Low` van de minuut de TP heeft geraakt, zonder chronologisch besef. 

**Voorbeeld:**
Een minuut opent op `100`, daalt naar `95` (Low), schiet omhoog naar `110` (High), en sluit op `105`.
Een short limiet order op `108` wordt in deze minuut gevuld, en heeft een TP op `98`. 
Een foute simulator ziet dat de `Low` (`95`) lager is dan de TP (`98`) en registreert een **WIN**. 
Dit is een illusie! Omdat het een **Bullish candle** betreft (Close > Open), moet de prijs *eerst* gedaald zijn naar `95` (de Low), om vervolgens omhoog te vliegen naar `110` (de High), waar de order pas gevuld wordt op `108`. Vanaf dat punt (de top) daalt hij nog slechts naar de sluiting op `105`. Jouw TP op `98` werd dus na je fill **nooit meer geraakt**. Waarschijnlijk werd in de minuten daaropvolgend onverwachts je SL the pakken genomen. Dit was het verschil tussen een "Backtest-Win" en een "Live-Loss".

### De Oplossing: De 'Synthetic Remainder Candle' & Pessimistische Rules
Om 100% parity te bieden ten opzichte van de live executie (TopStepX), implementeert de M1 Backtest Simulator nu intern een "synthetic remainder candle". Wanneer een limietorder getriggerd wordt, reconstrueert de engine de op/neer volgorde van de minuut op de polariteit (Bullish/Bearish). Dit stript direct de 'pre-fill' data, en bouwt een virtuele rest-candle op ("vanaf het fill moment, tot het einde van de minuut"). 

**Pessimistische Intra-Bar Worst-Case:** Als binnen één M1 candle *zowel* de SL als de TP wordt geraakt, gaat de engine er in de backtest *altijd* van uit dat de SL eerst werd geraakt, ongeacht de kleur van de candle. Dit creëert absolute zekerheid in de win-rates, neutraliseert look-ahead bias volledig en bouwt de meest strenge simulatie die mogelijk is.

Daarnaast wordt standaard over elke afgesloten trade $7.60 aan broker commissies en fees berekend om de uiteindelijke USD netto winst compleet reëel te houden.

### The Stateful Filter Cooldown Illusion (Continuous PnL Passing)
Tijdens backtesting kan er een enorme discrepantie ontstaan (minder trades in backtest dan live) als de engine de PnL van een afgesloten trade blijft doorgeven op *elke* minuut die daarop volgt. In de live `LiveFleetCommander` wordt het resultaat (`pending_last_trade_result`) exact **één keer** naar de `RuleEngine` gestuurd op het moment van sluiten, en daarna direct gereset naar `None`. 

Als een backtest script (zoals een `.tmp` experiment) simpelweg de laatste trade uit de vault trekt en deze blijft injecteren in `engine.evaluate()`, zal een stateful filter (zoals `LossCooldownFilter`) concluderen dat de *laatste verliesgevende trade* op **de huidige minuut** is gebeurd. Hierdoor wordt de "30 minuten cooldown timer" elke minuut gereset, waardoor er in die richting **nooit meer** getrade wordt. 

**De Oplossing (De 100% Parity Regel):**
Tijdens elke backtest of sandbox iteratie moet de loop-iterator de lengte van `vault.trades` bijhouden (bijv. `prev_trade_count`). De `last_trade_result` mag **uitsluitend** aan de engine worden doorgegeven als `len(vault.trades) > prev_trade_count`. Daarna moet de state gereset worden. Doe je dit niet, dan vernietig je onbewust je Win-Rate en Trade-Volume simulaties.

---

## 🔍 5. Advanced Optimization & Custom Analytics (MFE/MAE)

Tijdens de iteratieve evaluatie van strategieën (zoals The Golden Setup) is gebleken dat we niet alleen naar PnL of Win-rates moeten kijken, maar ook naar de 'binnenkant' van een trade.
Hiervoor is de backtest-architectuur gaandeweg uitgebreid:

*   **MFE & MAE Tracking:** De Simulator (Layer 4) en de Exporter registreren `max_run_points` (Maximum Favorable Excursion / MFE) en `max_draw_points` (Maximum Adverse Excursion / MAE) op de tik nauwkeurig. Hiermee kunnen we achteraf in data-analyses precies zien of er ruimte was voor *Break-Even Shields*, *Dynamic Stop-Losses*, of *Killzones*.
*   **Geïsoleerde Optimalisatie (Zero Cowboy Coding):** Wanneer we experimenteren met nieuwe theorie-filters of strakkere Playbook-parameters, draaien we **nooit** zomaar wijzigingen door in de productie-`strategy_playbook.json`. 

---

## 🧪 6. De `.tmp` Sandbox Workflow & Strict Backtest Mandate

De map `.tmp/` dient als **wegwerp-sandbox** voor experimentele research. Echter, we hebben in het verleden herhaaldelijk dezelfde kapitale fout gemaakt: het schrijven van custom iteratie-scripts (zoals `origin_sweep.py` of `monthly_eval.py`) die zélf proberen PnL uit te rekenen.

### 🚫 De Absolute Hoofdregel voor Backtesting
**HET IS TEN STRENGSTE VERBODEN OM CUSTOM PNL EVALUATIE-LOOPS TE SCHRIJVEN IN `.tmp` SCRIPTS.**

Elke keer als een AI-agent of ontwikkelaar een snelle iteratie-loop schrijft om "even snel een theorie te backtesten", vallen we ten prooi aan de **Intra-bar Look-Ahead Bias** (zie sectie 4). Deze custom scripts controleren vaak pas op de *volgende* candle of een Stop Loss (SL) is geraakt, en negeren de realiteit dat de SL direct op de entry-candle (de intrabar wick) geraakt had kunnen worden. Hierdoor zagen we in simulaties +$206k winst, wat in realiteit -$13k verlies was.

**De GSD Validatie Pipeline (Single Source of Truth):**
1. **Theorie bouwen:** Experimenteer met Level detectie en market structure in `.tmp/` scripts. *Je mag hier tellen hoe vaak een theorie voorkomt.*
2. **Kloon Playbook:** Maak een variant aan van het playbook (`strategy_playbook_experiment.json`) in de officiële `strategies/` map of in `.tmp/`.
3. **Gebruik de Motor:** Roep **ALTIJD** `scripts/backtest/run_backtest.py` aan via de terminal om de financiële resultaten uit te rekenen. Als je een eigen `.tmp` sweeper of loop schrijft, gebruik dan ALTIJD de `BacktestSession` class uit `src/layer4_execution/backtest_engine.py`. Schrijf NOOIT zelf een iteratie (zoals `for row in df.iterrows()`) voor executie of PnL berekening!
4. **Accepteer de realiteit:** De `BacktestSession` resultaten zijn onomstotelijk en strikt pessimistisch. Is het verliesgevend? Pas dan theorie aan, maar wantrouw nóóit de engine.

| Bestandstype | Voorbeeld | Doel |
|---|---|---|
| Theorie/Setup Detectors | `find_levels.py` | Puur voor het identificeren van setups (ZONDER PnL executie) |
| Playbook-klonen | `strategy_playbook_be.json` | Alternatieve parametersets voor `run_backtest.py` of `BacktestSession` sweeps |
| Analyse-scripts | `analyze_mfe_mae.py` | Post-hoc trade reconciliatie na de officiële backtest |

**Workflow stappen:**
1. Pas de theorie (`Layer 2`) of executie modules (`Layer 3`) aan.
2. Voer `python3 scripts/backtest/run_backtest.py --strategy <naam> --days 120` uit.
3. Analyseer de terminal output of de gedumpte CSV-logs.
4. Ruim output-dumps en overbodige `.tmp` scripts direct op na iteratie.

---

## 🔐 7. Architectuur Invarianten

Deze regels worden afgedwongen door de GSD Methodiek en `pytest-archon`:

1. **Layer-scheiding is heilig:** Layer 1 (Data) → Layer 2 (Theorie) → Layer 3 (Strategie) → Layer 4 (Executie). Lagen mogen **nooit** opwaarts importeren.
2. **`simulator.py` = Layer 4:** De simulator implementeert de broker-executie interface en leeft in `src/layer4_execution/`. Het is de enige code die PnL mag berekenen.
3. **Scripts importeren de engine, niet andersom:** De `scripts/` map bevat CLI-wrappers die de engine aanroepen.
4. **Productie-code is read-only tijdens research:** Experimentele scripts in `.tmp/` mogen **nooit** productiecode wijzigen tenzij dit expliciet goedgekeurd is via een plan.

---

*Laatst bijgewerkt: 2 Mei 2026 — Introductie van BacktestSession, Pessimistische Intra-Bar Worst-Case Rules en Broker Commissies.*
