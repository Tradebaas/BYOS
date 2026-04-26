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
   * **Hoe het werkt:** Via de CLI (terminal) start je dit script op en wijst een strategie aan (`--strategy <naam_van_strategie_map>`). De engine injecteert exact hetzelfde JSON playbook als de Live Bot. Als de theorie in Layer 3 roept: "Order!", checkt de simulator vliegensvlug in de CSV of je bracket is geraakt. Slippage en fees kunnen direct door de simulatie-logica wiskundig berekend worden.

## 📊 3. Exporteren & Validatie
In de afwezigheid van flash dashboards, rapporteert `run_backtest.py` harde, betrouwbare `metrics` via JSON/CSV dumps of terminal-prints terug naar jou: Total Profit, Win-Rates, Consecutieve drawdowns en exact getimede executie-logs per seconde.

---

**Kortgezegd:** 
Waar de **Live Bot** leest uit: `Topstep Websocket -> Playbook Rules -> Live Broker Executie`,
Leest de **Backtester** uit: `Lokale CSV File -> Playbook Rules -> FAST-FWD Terminal Executie`. 

Je valideert vanmiddag lokaal in je CLI exáct de module-logica die de engine maandagochtend live gaat draaien! 

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
Om 100% parity te bieden ten opzichte van de live executie (TopStepX), implementeert de Backtest Simulator nu intern een "synthetic remainder candle". Wanneer een limietorder getriggerd wordt, reconstrueert de engine de op/neer volgorde van de minuut op de polariteit (Bullish/Bearish). Dit stript direct de 'pre-fill' data, en bouwt een virtuele rest-candle op ("vanaf het fill moment, tot het einde van de minuut"). SL en TP worden exclusief getoetst aan de rest-capaciteit van de M1 bar, met absolute precisie. Hierdoor matchen jouw live losses 1:1 met de gesimuleerde sessies.
