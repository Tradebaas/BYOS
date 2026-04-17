# Backtest Engine Execution Architecture
*Documentatie over de robuuste, offline test-faciliteiten (Command Line).*

Dit document dient als referentie om lokaal gigantische datasets af the handelen met exact dezelfde handels-architectuur als de Live Bot. 

Het grote voordeel van deze architectuur is dat Layer 2 & 3 (Theorie & Strategie) **exact hetzelfde** werken als in de Live Bot. Alleen Layer 4 (de netwerk-laag van TopstepX) wordt vervangen voor een lokale tijdmachine in de vorm van `run_backtest.py`. Er is **geen Node.js, geen front-end UI en geen FastAPI server**. Waarderende lean-development en terminal snelheid.

---

## 💾 1. Data Acquisitie (De Brandstof)
*Jij hebt historische data nodig om de simulator te voeden.*

* **`data/historical/NQ_1min.csv`**
   * Het bestand waarin de historische koersen liggen opgeslagen.
* **`scripts/build_data_lake.py`**
   * **Rol: De Pomp.** Heb je verse data nodig uit TopstepX of wil je historische bar-data samenvoegen? Dit script trekt bulkdata netjes naar de `historical` map, gereed voor de simulator.


## 🏎 2. De Motor (De Simulator)
*De snelle "Offline-TopstepX" die maanden aan data in seconden doorslikt.*

* **`scripts/run_backtest.py`**
   * **Rol: De Tijdreiziger.** Hier gebeurt de absolute simulatie-magie. In plaats van de live kapitein (`live_fleet_commander.py`), draait deze simulator in "Fast Forward". 
   * **Hoe het werkt:** Via de CLI (terminal) start je dit script op en wijst een strategie aan (`--strategy dtd_golden_setup`). De engine injecteert exact hetzelfde JSON playbook als de Live Bot. Als de theorie in Layer 3 roept: "Order!", checkt de simulator vliegensvlug in de CSV of je bracket is geraakt. Slippage en fees kunnen direct door de simulatie-logica wiskundig berekend worden.

## 📊 3. Exporteren & Validatie
In de afwezigheid van flash dashboards, rapporteert `run_backtest.py` harde, betrouwbare `metrics` via JSON/CSV dumps of terminal-prints terug naar jou: Total Profit, Win-Rates, Consecutieve drawdowns en exact getimede executie-logs per seconde.

---

**Kortgezegd:** 
Waar de **Live Bot** leest uit: `Topstep Websocket -> Playbook Rules -> Live Broker Executie`,
Leest de **Backtester** uit: `Lokale CSV File -> Playbook Rules -> FAST-FWD Terminal Executie`. 

Je valideert vanmiddag lokaal in je CLI exáct de module-logica die de engine maandagochtend live gaat draaien! 
