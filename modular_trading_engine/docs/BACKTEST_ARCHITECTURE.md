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

> **Waarom `simulator.py` en `data_vault.py` in `src/layer4_execution/` staan:**
> De backtest-engine (simulator) implementeert dezelfde interface als de live broker-executielaag. De `pytest-archon` architectuurverifiers eisen dat executielogica in Layer 4 leeft — verplaatsing zou de architectuurtests breken. De scripts in `scripts/backtest/` zijn dunne CLI-wrappers die de engine aanroepen.

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

* **`scripts/backtest/run_backtest.py`**
   * **Rol: De Tijdreiziger.** In plaats van de live kapitein (`live_fleet_commander.py`), draait deze simulator in "Fast Forward". 
   * **Hoe het werkt:** Via de CLI start je dit script en wijs een strategie aan (`--strategy <naam>`). De engine injecteert exact hetzelfde JSON playbook als de Live Bot. Als de theorie in Layer 3 roept: "Order!", checkt de simulator vliegensvlug in de CSV of je bracket is geraakt. Slippage en fees kunnen direct door de simulatie-logica wiskundig berekend worden.

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

### De Oplossing: De 'Synthetic Remainder Candle'
Om 100% parity te bieden ten opzichte van de live executie (TopStepX), implementeert de M1 Backtest Simulator nu intern een "synthetic remainder candle". Wanneer een limietorder getriggerd wordt, reconstrueert de engine de op/neer volgorde van de minuut op de polariteit (Bullish/Bearish). Dit stript direct de 'pre-fill' data, en bouwt een virtuele rest-candle op ("vanaf het fill moment, tot het einde van de minuut"). SL en TP worden exclusief getoetst aan de rest-capaciteit van de M1 bar, met absolute precisie. Hierdoor matchen jouw live losses 1:1 met de gesimuleerde sessies.

---

## 🔍 5. Advanced Optimization & Custom Analytics (MFE/MAE)

Tijdens de iteratieve evaluatie van strategieën (zoals The Golden Setup) is gebleken dat we niet alleen naar PnL of Win-rates moeten kijken, maar ook naar de 'binnenkant' van een trade.
Hiervoor is de backtest-architectuur gaandeweg uitgebreid:

*   **MFE & MAE Tracking:** De Simulator (Layer 4) en de Exporter registreren `max_run_points` (Maximum Favorable Excursion / MFE) en `max_draw_points` (Maximum Adverse Excursion / MAE) op de tik nauwkeurig. Hiermee kunnen we achteraf in data-analyses precies zien of er ruimte was voor *Break-Even Shields*, *Dynamic Stop-Losses*, of *Killzones*.
*   **Geïsoleerde Optimalisatie (Zero Cowboy Coding):** Wanneer we experimenteren met nieuwe theorie-filters of strakkere Playbook-parameters, draaien we **nooit** zomaar wijzigingen door in de productie-`strategy_playbook.json`. 

---

## 🧪 6. De `.tmp` Sandbox Workflow

De map `.tmp/` dient als **wegwerp-sandbox** voor experimentele research. Het bevat:

| Bestandstype | Voorbeeld | Doel |
|---|---|---|
| Experiment-scripts | `run_trailing_experiment.py`, `run_be_backtest.py` | Geïsoleerde backtest-varianten |
| Playbook-klonen | `strategy_playbook_be.json`, `strategy_playbook_deep_dive.json` | Alternatieve parametersets |
| Analyse-scripts | `reconcile_trades.py`, `compare_trades.py`, `advanced_analysis.py` | Post-hoc trade reconciliatie |
| Gespecialiseerde simulators | `trailing_tp_simulator.py`, `time_exit_simulator.py` | Feature-specifieke tests |

**Workflow:**
1. Kloon het playbook naar een tijdelijke iteratie in `.tmp/`.
2. Draai de theorie af in isolatie.
3. Produceer een analyse (script-output, terminal metrics).
4. Trek conclusies (bijv. "De statische 12-punt Stop-Loss functioneert wiskundig beter dan een dynamische").
5. Pas de kennis toe in het productie-playbook.
6. Ruim output-dumps op (`.log`, `.txt`, `.csv` — deze worden door `.gitignore` geblokkeerd).

---

## 🔐 7. Architectuur Invarianten

Deze regels worden afgedwongen door `tests/test_architecture.py` (pytest-archon):

1. **Layer-scheiding is heilig:** Layer 1 (Data) → Layer 2 (Theorie) → Layer 3 (Strategie) → Layer 4 (Executie). Lagen mogen **nooit** opwaarts importeren.
2. **`simulator.py` = Layer 4:** De simulator implementeert de broker-executie interface en leeft daarom in `src/layer4_execution/`.
3. **Scripts importeren de engine, niet andersom:** De `scripts/` map bevat CLI-wrappers die de engine aanroepen via `sys.path`. De engine zelf weet niets van de scripts.
4. **Productie-code is read-only tijdens research:** Experimentele scripts in `.tmp/` mogen **nooit** productiecode wijzigen.

---

*Laatst bijgewerkt: 28 april 2026 — Herstructurering naar `scripts/live/` + `scripts/backtest/`, tick data support verwijderd op verzoek.*
