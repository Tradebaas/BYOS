# BYOS - Build Your Own System (Topstep Edition)

Welkom in het `BYOS` (Build Your Own System) project. Dit is het definitieve, stand-alone back-end framework voor het geautomatiseerd handelen van derivaten (NQ E-mini) via de TopstepX infrastructuur.

De software is ontworpen als een meedogenloze 'silent executor', gedreven door de GSD-methodiek (Get Shit Done). Geen toeters, geen bellen, alleen 100% stabiele, asynchrone node-naar-node PnL generatie.

> *"This engine builds discipline, mathematically enforcing what human psychology inevitably fails to respect."*

Deze documentatie dient als jouw **A-Z Handleiding**. Alles wat je nodig hebt om een nieuwe machine in te richten, een live-account te koppelen en de bot of backtester te starten staat hier beschreven. Alle applicatie-code leeft in de map `modular_trading_engine/`.

---

## 🏗️ Architectuur Overzicht (De 4 Lagen)

Om spaghetti-code te voorkomen en testen betrouwbaar te maken, werkt de bot met een ijzersterke scheiding van verantwoordelijkheden over 4 lagen. Lagen communiceren alleen 'downstream', ze mogen nooit logica of data uit een bovenliggende laag importeren.

1. **Layer 1: Data Acquisitie (`src/layer1_data/`)**
   - Vangt ruwe data (WebSocket ticks of historische CSV data) op en structureert dit in abstracte formaten (zoals `Candle` met o/h/l/c/vol attributen).
2. **Layer 2: Mathematische Theorie (`src/layer2_theory/`)**
   - De hersens van de marktanalyse. Hier leeft `MarketTheoryState`. Deze laag herkent structuren zoals *Premium/Discount iteraties*, *Origin Pools* en *Confirmation Hold Levels*. Dit is pure wiskunde, zonder besef van orders of geld.
3. **Layer 3: Strategie & Playbooks (`src/layer3_strategy/`)**
   - De vertaalslag van theorie naar handels-intenties. Gestuurd door `strategies/<naam>/strategy_playbook.json`. Hier worden theorie-events gefilterd (bijv. Killzones, Cooldowns) en omgezet in gestandaardiseerde ordertypes zoals de `RATLimitOrder` (inclusief Stop-Loss, Take-Profit en Breakeven-targets).
4. **Layer 4: Executie (`src/layer4_execution/`)**
   - De 'handen' van de bot. Dit is de `LiveFleetCommander` die communiceert met de TopstepX API om fysieke orders te plaatsen, posities te monitoren en stop-losses te verplaatsen (zoals het *Breakeven Shield*). Binnen deze laag leeft ook de offline backtest-simulator.

---

## ⚙️ Installatie & Setup

### 1. Python Environment
Zorg dat je Python 3.10+ hebt geïnstalleerd.
```bash
cd modular_trading_engine
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Variables (.env)
Kopieer `.env.example` naar `.env` in de `modular_trading_engine/` directory:
```bash
cp .env.example .env
```
Vul in je `.env` bestand je Topstep inloggegevens in. Deze worden gebruikt voor authenticatie.
```env
TOPSTEP_USERNAME=jouw_email@domein.com
TOPSTEP_PASSWORD=jouw_wachtwoord
```

### 3. Account ID Configureren
Voordat je live kunt handelen of posities kunt beheren, moet de bot weten op *welk specifiek account* hij orders mag vuren.
1. Zorg dat je in `modular_trading_engine/` staat. Draai het configuratiescript om je actieve accounts en bijbehorende ID's op te halen:
   ```bash
   PYTHONPATH=. python scripts/live/get_topstep_accounts.py
   ```
2. Zoek in de output naar het account dat je wilt traden (bijv. een actief Combine account). Noteer het `id` (een getal, bijv. `21637882`).
3. Open `strategies/dtd_golden_setup/execution_config.json`.
4. Zet het genoteerde ID bij `"account_id"`. Bevestig hier ook de markt (bijv. `NQ`).

---

## 🌊 De Strategie Flow (Van A-Z)

Hoe komt een order tot stand en hoe wordt deze beschermd? Dit is de levenscyclus van een trade in de live engine:

1. **De Data Pijplijn (WebSocket):** 
   De `TopstepRealtimeClient` in Layer 4 luistert live via een SignalR WebSocket naar de Market Hub. Zodra er een nieuwe 'tick' is (een trade op de markt), wordt deze doorgegeven.
2. **Aggregatie:** 
   De ruwe ticks worden geaggregeerd in 1-minuut `Candle` objecten. Zodra de minuut sluit, wordt deze kaars doorgegeven aan Layer 2.
3. **Theorie Detectie:** 
   `MarketTheoryState` analyseert de nieuwe kaars. Als er een specifiek patroon wordt gedetecteerd (bijvoorbeeld de prijs is teruggekeerd in een valid Origin Level en vertoont de juiste polariteit), roept de engine een `ConfirmationHoldLevelTrigger` event aan.
4. **Playbook Evaluatie:** 
   De `RuleEngine` in Layer 3 vangt dit theorie-event op en toetst het aan de `strategy_playbook.json`. 
   - *Filter check:* Vallen we binnen de handelstijd? (Killzone)
   - *Risk check:* Hebben we niet onlangs al een trade gehad? (Cooldown)
5. **Intentie Formatie:** 
   Als alles op groen staat, genereert de `limit_order_execution` module een `RATLimitOrder` (Risk Assessed Target Limit Order) intentie met nauwgezette offsets: Entry prijs, Stop-Loss prijs, Take-Profit prijs en de Breakeven-activatie prijs.
6. **Fysieke Order Plaatsing:** 
   De `LiveFleetCommander` (Layer 4) ontvangt de intentie. Hij gebruikt de `TopstepClient` om via een beveiligd REST endpoint de order met bijbehorende OCO (One Cancels Other) brackets daadwerkelijk in de TopstepX backend in te schieten.
7. **The Breakeven Shield (Trailing):** 
   Zodra de entry is gevuld, start de `_manage_breakeven` asynchrone taak binnen de Fleet Commander. Deze luistert continu naar de WebSocket voor je actuele PnL of positie. Zodra je positie in het groen komt (+10 punten in de NQ), zal de bot vliegensvlug en asynchroon een `modify_order` API-call doen om je originele Stop-Loss order te verplaatsen naar Entry + 2 ticks. Vanaf dit moment is de trade "risicovrij". 

---

## 🚀 Live Trading

Het starten van de live bot doe je pas als je de `.env` en de `execution_config.json` juist hebt ingericht.
```bash
# Zorg dat je in de virtual environment zit:
cd modular_trading_engine
source venv/bin/activate

# Draai de live commander:
PYTHONPATH=. python scripts/live/run_live_bot.py
```
De bot zal zelf historical data ophalen om 'op te warmen', waarna hij synchroniseert met de WebSocket en begint te wachten op signalen. Druk `Ctrl+C` om hem veilig te stoppen (let op: open posities moet je in je broker dashboard sluiten, orders sluit hij idealiter zelf af mits goed geprogrammeerd).

---

## ⏱️ Backtesting & Research

De backtest omgeving is ontworpen om gigantische datasets te verwerken via terminal-executie in seconden, zónder de productiecode te beïnvloeden. Layer 2 en Layer 3 blijven identiek, alleen Layer 4 wordt vervangen door de lokale `simulator.py`.

> [!CAUTION]
> **ABSOLUTE REGEL VOOR BACKTESTING:** 
> Experimenteren, aanpassen van parameters, of theorie-aanpassingen toetsen gebeurt ALTIJD en UITSLUITEND in de `.tmp/` map. **Je mag absoluut NOOIT productie-playbooks of source-code aanpassen puur om even een test te draaien.** Na het draaien van een lokaal experiment ruim je de `.tmp` directory op. Productie is 100% Read-Only!

### Een backtest uitvoeren:
1. **Data ophalen:** Voordat je test, heb je actuele data nodig. Zorg dat je bent ingelogd via de `.env`.
   ```bash
   cd modular_trading_engine
   PYTHONPATH=. python scripts/backtest/build_data_lake.py
   ```
2. **De Simulator starten:**
   ```bash
   # Test the dtd_golden_setup over de laatste 10 dagen:
   PYTHONPATH=. python scripts/backtest/run_backtest.py --strategy dtd_golden_setup --days 10
   ```
   De output toont nauwgezette logs over MFE (Maximum Favorable Excursion) en MAE, en een totaal PnL overzicht. Omdat we op M1 bars backtesten, heeft de simulator een *Synthetic Remainder Candle* methode ingebouwd die voorkomt dat Take-Profits "vals-positief" worden aangetikt in dezelfde bar als de entry.

---

## 📂 Navigatie (Waar staat wat?)

Een overzicht van het landschap voor als je zelf zaken gaat ontwikkelen in `modular_trading_engine/`:

*   `/src/layer1_data/`: Data definities (`models.py`) en de CSV inlezer.
*   `/src/layer2_theory/`: De markt-analist. Kijkt naar de bars en ontdekt patronen (`market_state.py`).
*   `/src/layer3_strategy/`: Vertaalt theorie naar actie. `rule_engine.py` regeert hier.
*   `/src/layer4_execution/`: Broker connecties (`topstep_client.py`), WebSockets (`topstep_realtime.py`), Live Bot (`live_fleet_commander.py`) en Simulator (`simulator.py`).
*   `/strategies/<naam>/`: Hier leeft de identiteit van een strategie (bijv. `dtd_golden_setup` of `origin_level_scalper`).
*   `/scripts/live/`: Hulpmiddelen en start-scripts voor de live omgeving.
*   `/scripts/backtest/`: De CLI-interface voor data ophalen en backtesting.
*   `/docs/`: Diepgaande documentatie!
    *   Lees `STRATEGY_BUILDING_BLOCKS.md` als je zelf modules wilt bouwen.
    *   Lees `LIVE_BOT_ARCHITECTURE.md` voor de details van de Topstep API impersonation en polling iteraties.
    *   Lees `BACKTEST_ARCHITECTURE.md` voor de MFE/MAE filosofie.

---
*Gebouwd met ijzeren discipline via de Get Shit Done methode.*
