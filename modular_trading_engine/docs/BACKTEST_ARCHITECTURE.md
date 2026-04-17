# Backtest Engine Architecture & UI Guide
*Documentatie over de exacte keten van componenten die verantwoordelijk is voor de Visuele Neumorphic Backtester.*

Dit document dient als referentie om de momenteel draaiende backtester (inclusief PnL UI en Simulator motor) 1-op-1 over te dragen naar een nieuw project. Het grote voordeel van deze architectuur is dat Layer 2 & 3 (Theorie & Strategie) **exact hetzelfde** werken als in de Live Bot. Alleen de netwerk-laag (TopstepX) wordt omgewisseld voor een lokale simulator!

---

## 🖥 1. De Voorkant (User Interface)
*De visuele Neumorphic web-applicatie (Light/Dark mode) waarmee je statistieken en de PnL curve leest.*

* **`backtest_ui/index.html` & `backtest_ui/style.css`**
   * **Rol: Het Gezicht.** De superstrakke user interface met moderne glaseffecten en light/dark wisselknop. Toont in één oogopslag je win-rate, total profit, drawdown en het equity-grafiekje.
* **`backtest_ui/app.js`**
   * **Rol: Het Paneel.** Vangt de knopdruk "Run Backtest" op en praat met je lokale Python-server (zie Stap 2). Hij ontvangt grote blokken data, snijdt dit in stukkies, tekent de PnL-lijn in de grafiek, en berekent de Win/Loss statistieken op je beeldscherm.

---

## 🔌 2. De Brug (De FastAPI Server)
*De lokale stekkerdoos die je browser verbindt met de zware theorie-motor.*

* **`src/api/backtest_server.py`**
   * **Rol: De Opstarter.** Het simpele script (`uvicorn`) dat in feite lokaal poort `8002` (of vergelijkbaar) openzet zodat je browser (app.js) met je Python-mapjes kan communiceren.
* **`src/api/backtest_router.py`**
   * **Rol: De Verkeersleider.** Ontvangt het JSON-verzoek van de UI (bijvoorbeeld "Backtest Dag X t/m Y met 15-punt SL"). Hij trekt direct Data uit je CSV's, roept de Simulator aan (zie Stap 3) en geeft als een razende de resulterende trades direct terug naar het browservenster.

---

## 🏎 3. De Motor (De Simulator)
*De "Offline-TopstepX" die maanden aan data in seconden doorslikt zonder internetvertraging.*

* **`src/layer4_execution/simulator.py`**
   * **Rol: De Tijdreiziger.** Hier gebeurt de absolute magie! In plaats van de `live_fleet_commander.py` (die elke 10 sec wacht), draait deze simulator in "Fast Forward". 
   * **Hoe het werkt:** Hij injecteert exact dezelfde `layer3_strategy` en `playbook config` als je live-bot! Alleen voert hij geen echte netwerkcalls uit, maar 'simuleert' hij Fill-prijzen. Als de theorie zegt: "Order plaatsen", kijkt de simulator simpelweg of de volgende CSV-candle die prijs van je Bracket geraakt zou hebben, en stelt dan de virtuele winst of het verlies (Slippage inclusief!) vast.
* **`src/layer1_data/csv_parser.py`** (of `resampler.py`)
   * **Rol: De Brandstofpomp.** Neemt ruwe Topstep export data (`data/historical/NQ_1min.csv`) van je harde schijf, leest ze razendsnel in en stuurt ze één voor één als lopende band pakketjes naar de Simulator zodat die precies de echte markt van vroeger kan nabootsen.

---

**Kortgezegd:** 
Waar de **Live Bot** kijkt naar: `Klok -> Rule Engine -> TopstepX Server`,
kijkt deze **Backtester** naar: `CSV Bestand -> Rule Engine -> FAST-FWD Simulator -> Jij in je Browser`. Door de strikte modulariteit test je dus in seconden exáct de wiskunde die morgenochtend live gedraaid gaat worden! 
