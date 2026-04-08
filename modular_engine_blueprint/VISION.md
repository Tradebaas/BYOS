# Modular Trading Engine - Architectuur Visie

Dit document beschrijft de visie en de fundamentele architectuur voor een compleet modulaire, mechanische trading engine. Doel is om een robuuste "blueprint" te vormen waarin de wiskundige theorie volledig gescheiden is van handelsstrategieën.

## 1. Onze Visie & Kernwaarden

Dit project is geen retail hobby-script. Het is een extreem robuuste, meedogenloos schaalbare en modulaire 'Institutional-Grade' trading engine. Om dit te bereiken en te behouden, zijn we gebonden aan een ijzeren, onbreekbare denkwijze:

**Waar we voor staan (De Fundering):**
*   **Absolute Ontkoppeling (Separation of Concerns):** De wiskunde op een grafiek (de theorie) is onveranderlijk. Een Hold Level is en blijft een Hold Level, ongeacht welke grensverleggende strategie je hanteert. De datalaag weet niets van de strategielaag.
*   **Generiek & Modulair:** We bouwen 'Legoblokjes'. We leggen geen starre routes vast, maar bouwen pure theoriemodules die overal inzetbaar zijn (Laag 2), verbonden via schone JSON-playbooks (Laag 3).
*   **Wiskundige Objectiviteit:** Geen "ongeveer" geraakt. Onze theorieregels kennen alleen 1 (True) of 0 (False). Een candle validéert tot Kandidaat of niet; er is geen grijs gebied.

**Wat we absoluut NIET willen (De Vijand):**
*   **Geen Tech Debt & Spaghetti:** Zodra patroonherkenning verstrengeld raakt met order-executie breekt alles. We verbieden lange complexe code-loopings (God Classes).
*   **Geen AI-Hallucinaties:** Om te voorkomen dat AI iteraties de code kapotmaken, weigeren we grote/onoverzichtelijke bestanden. Strikte functie-limieten garanderen controleerbaarheid (zie *`ENGINEERING_STANDARDS_BLUEPRINT.md`*).
*   **Geen Terminologische Vervuiling:** SMC of externe retail terminologie is verboden. Onze terminologie is uitsluitend gebaseerd op CCTA.
*   **Geen Hardcoded Strategieën:** Geen winst of "timeout" logica vastsmeden in theorie in Python bestanden. 

**De Grote Oplossing:** 
Een waterdichte vier-laags architectuur waarbij de theorie (Laag 2) enkel en alleen als wiskundige API voor de Strategie Playbooks (Laag 3) functioneert.

## 2. De Binaire Bouwstenen (Modules)

In de `engine/modules/` map komen puur functionele componenten te leven. Deze modules weten **niets** van orders, accounts of winstverbod; ze berekenen alleen prijsactie.

### A. Level Detectors
*   **Break Level Locator**: Bepaalt uitsluitend de wicks van opeenvolgende candles van dezelfde kleur om structuur te identificeren.
*   **Hold Level Detector**: Berekent in een 'move' de uiterste body-test point (front side greediest spot) vergeleken met de wick.
*   **Origin Level Tracker**: Volgt geïdentificeerde Break Levels op en houdt een hit-counter bij. Valideert of er 'Candle Separation' is opgetreden om *Polarity* te activeren.

### B. Validatie Mechanismes
*   **Tested State Validator**: Puur binaire scanner die meetelt of de prijs exact tot op de 'penny' gehit is. Geen "dichtbij genoeg" logica.
*   **Hard Close Engine**: Ontvangt een referentieniveau (ongeacht het type) en analyseert de inkomende candle: sluiten *beide* randen van de body buiten het niveau in de kleurlijnrichting? Returnt `True` of `False`.
*   **Deep Dive Tracker**: Returnt `True` als een wick door een referentieniveau steekt, zónder dat er een Hard Close plaatsvindt.

### C. Strategische Analysers
*   **RAT (Rejection as Target) Monitor**: Een scanner die terug in de tijd kijkt naar ongeteste Hold Levels en deze bundelt als datapunten voor mogelijke koersdoelen.
*   **Combo Level Linker**: Knoopt concepten over meerdere timeframes aan elkaar met de stricte *Forward and Down* regel.
*   **Pandora's Box Detector**: Identificeert periodes van markt-besluiteloosheid wanneer de prijs ingeklemd raakt tussen twee structurele Hold Levels.

## 3. De Data Flow

Een modulaire orkestratie-laag of configuratie (bijvoorbeeld via een JSON-configuratie of visuele builder) verbindt de modules:

1.  **De Data Feed**: Price action en candles komen binnen (OHLCV).
2.  **Theorie Update**: De inkomende candles worden door de actieve *Level Detectors* gegooid. Deze modules handelen puur wiskundig en updaten uitsluitend hun status (bijv. "Een nieuw ongetest Hold Level is geregistreerd op prijs X").
3.  **Strategie Evaluatie (Rules Engine)**:
    *   De engine valideert de configuratie van de strategie ten opzichte van de actieve wiskundige status.
    *   Er wordt geverifieerd of er *Conditions* zijn doorbroken, en of *Triggers* en *Shields* geraakt zijn om open trades te beheren.
4.  **Executie**: Uitsluitend wanneer de strategie-voorwaarden compleet overeenkomen met de wiskundige chart data, wordt er een actie ge-initieerd richting een geïsoleerde Order-Executie module.

## 4. Richtlijnen voor Ontwikkeling
- **Strikte Terminologie**: Elke module, variabele en functie in deze codebase MOET en ZAL de 100% exacte bewoording gebruiken. Externe trading termen (zoals SMC) zijn ten strengste verboden. Zie de terminology file voor de vastgestelde definities.
- **Geen Impliciete Logica**: Elke wiskundige beslissing moet worden losgetrokken in een expliciete, unit-testbare functie.
- **Geen Tijd/Staat in Theorie**: Expiry tijden of willekeurige limieten horen niet in de theoretische laag. De puur wiskundige theoriemodule onthoudt het level tot in het oneindige, of totdat het wiskundig invalid wordt (bijv. via een Hard Close). De tactische logica bepaalt vervolgens of we deze data wel of niet negeren in een trade.

## 5. Scope & Ecosystem (De "End-State")

Om dit te realiseren, spreken we een heldere en robuuste scope af die modulair, schaalbaar en "dummy-proof" is:

1. **Pure Modules (De Lego-blokjes):**
   * Elke module (bijv. Hold Level Detector) is een opzichzelfstaand bestand met exact één verantwoordelijkheid.
   * *Dummy-proof*: Bovenin elk bestand staat een menselijk leesbare uitleg van de EXACTE CCTA regels die deze module handhaaft. Niets meer, niets minder.

2. **Super Robuuste Config Engine (De Lijm):**
   * Strategieën worden *nooit* meer hardcoded gebouwd. In plaats daarvan gebruiken we een definitiebestand (JSON, YAML of Python-DSL) waarin we simpelweg blokjes koppelen (bijv: `Als Hold Level Tests < 2` EN `Geen Hard Close` -> `Enter Trade`).
   * Dit stelt ons in staat om tig verschillende strategieën te bouwen en te testen zónder ooit de kern logica aan te raken.

3. **Visuele Frontend & Backtester:**
   * Een UI (uiteindelijk via web of lokaal dashboard) waar nieuwe strategieën samengeklikt of geconfigureerd kunnen worden.
   * **Simulatie Engine**: Krijgt geëxporteerde historische TopStep candle-data, voert deze bliksemsnel door de Config Engine, en spuugt de exacte trade resultaten uit.
   * Na goedkeuring van de backtest-resultaten kan de strategie-configuratie direct worden opgeslagen in de repository als "Active Blueprint".

4. **Generieke Order Orchestrator (Broker Agnostisch):**
   * In eerste instantie bouwen we vlekkeloos aan de TopstepX flow (die momenteel al werkt).
   * De architectuur isoleert de "Broker API" volledig via een interface. Zodra de signalen uit de Config Engine komen, dwingen we absolute doelen (bijv. Stop Loss ticks, Profit Target ticks) af. Pas in de allerlaatste stap vertaalt een specifieke `TopstepIntegrator` of `FuturesBrokerIntegrator` dit naar API calls.

Met deze blueprint kan theorie ononderbroken groeien en kunnen we talloze handelsstrategieën kwantitatief backtesten en opslaan, zonder het gevaar op spaghetti-code of theorie-vervuiling.
