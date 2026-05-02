# Architectuur & Werkwijze: DTD Golden Setup (A-Z Referentie)

Dit document bevat de exacte regels, configuraties en uitzonderingen van de draaiende strategie, gespecificeerd in mensentaal maar **100% gekoppeld aan de programmacode**. Er is **nul ruimte voor interpretatie**. De codebase reageert exact zoals hieronder beschreven.

---

## 1. De Hoofd-Loop (De Dirigent)

**Betrokken Script:** `src/layer4_execution/live_fleet_commander.py`

Dit is de hoofdloop van het systeem en fungeert als de dirigent tussen de Topstep Broker, Layer 1 (Data), Layer 2 (Theorie) en Layer 3 (Strategie).

*   **Opstarten & Auth:** Zodra het script start, lanceert hij via `src/layer4_execution/auth.py` een invisible (headless) browser. Hiermee kaapt hij veilig de verborgen JWT-autorisatietoken van TopstepX Web. Zonder token stopt de bot.
*   **Data Syncing:** In de "warming up the engine" fase leest hij het geheugen van de strategie in. Eerst `data/historical/NQ_1min.csv` voor historische context, waarna hij exáct de gap van de ontbrekende minuten (aantal seconden gesloten na de laatste opgeslagen candle) live downloadt van de Topstep datafeed.
*   **De Polling Loop:** Elke 10 seconden (ingesteld in `execution_config.json` via `"poll_interval_sec": 10`) doet de bot een check voor nieuwe prijsdata.
*   **Candle Selectie (De Ghost-Tick Uitzondering):** Hij voedt *uitsluitend volledig gesloten 1-minuut candles* aan het geheugen. Zodra de UTC-clock overslaat en de minuut afgesloten is, is de candle definitief en wordt hij aan de `MarketTheoryState` toegevoegd. Vluchtige prijsonderhandelingen binnen de openstaande minuut worden genegeerd (geen haperende valse signalen).
*   **Risicomanagement & Max Posities:** Als er lokaal een position op TopstepX open is (de parameter `positionSize != 0` in je portfolio), wordt de live loop gepauzeerd in het sturen van nieuwe orders (`max_positions = 1` configuratie). OCO Limit orders worden uitgesloten van fire-and-forget loops.
*   **Order Synchronisatie & Annulatie (De Anti-Ghost Exception):** Heeft TopstepX een openstaande Limit-Order die onbekend is bij de strategie (omdat een TTL vervallen is of een Hold Level ge-hardclosed werd)? Dan annuleert dit script direct de broker-order (`CancelAll`) om te matchen met ons lege geheugen.
*   **Uitvoer (Anti-Spam Slot):** Zodra Layer 3 de "Golden Setup" detecteert, stuurt hij het OrderIntent exact naar Topstep. Om spam API-calls te voorkomen, slaat hij onthoudt hij de limit order als *Locked* totdat deze geannuleerd wordt.

---

## 2. De Regelmotor en Pijplijn (Layer 3)

**Betrokken Script:** `src/layer3_strategy/rule_engine.py`

*   **Configuratie Mapping:** Dit script laadt letterlijk alle modulaire checks in vanuit de file `strategy_playbook.json`. Het functioneert als een lopende band (pipeline) waar historische kaarsen en prijzen per filter afvallen.
*   **De Pipeline Volgorde:** 
    1.  `ConfirmationHoldLevelTrigger` (Patroon zoeker)
    2.  `KillzoneFilter` (Tijdsfilter)
    3.  `LossCooldownFilter` (Revenge-trading blokkade)
    4.  `TTLTimeout` (Versheidsfilter)
    5.  `RATLimitOrder` (Uitvoer inspector en Order Converter)

Zodra iets álle filters overleeft, is het een `OrderIntent` (een koop/verkoop beslissing).

---

## 3. Het "Brein": De Setup en Theorieregels

**Betrokken Script:** `src/layer3_strategy/modules/confirmation_hold_level_trigger.py`

Dit script definieert de The Golden Setup in 5 afzonderlijke, strikte stappen, toegepast op de afgelopen `bias_window_size` (standaard **300 minuten** in playbook).

### Fase 1: Identificatie van de Bouwstenen (Test Blok vs. Executie Blok)
De bot zoekt naar **twee afzonderlijke structuren** om The Golden Setup compleet te maken. De code eist dat een theorie level eerst gefaald en "getest" wordt door de markt, voordat hij instapt op een *nieuw* vers tegen-blok.

*   **Structuurdefinitie (Een Blok):** 
    *   *Short Blok:* Groene Hold candle -> Rode Break candle -> Rode Bevestigingscandle.
    *   *Long Blok:* Rode Hold candle -> Groene Break candle -> Groene Bevestigingscandle.
    *(Elk blok dat niet exact uit deze 3 kaarsen in die volgorde bestaat, telt niet).*

*   **Bouwsteen A: Het Test Blok (In code: `anchor`)**
    Dit is een oude, fundamentele 3-candle structuur die in het verleden is gevormd. Het systeem markeert dit als een validatie-zone. De bot vuurt op dit level nog **geen** trades af.

*   **Bouwsteen B: Het Executie Blok (In code: `b2`)**
    Dit is een spiksplinternieuwe 3-candle structuur die in tegenovergestelde/resulterende richting ontstaat *nadat* het Test Blok fysiek is aangeraakt (zie Fase 3). Zodra de bot een Limit Order naar Topstep verzendt, wordt de entry-prijs verankerd op de body (OPEN) van **dít Executie Blok**, NIET op de prijs van het originele Test Blok.

### Fase 2: Hard Close Check (De Genadeloze Killer)
Zodra een Test Blok (`anchor`) of Executie Blok is gevonden, controleert de engine elke minuut of deze structuur tussentijds structureel is overwonnen.
*   **De Ingeladen Externe Regel:** *Hard close onder de OPEN van een bearish/bullish hold level invalideert dat level.*
*   **Hoe het gecodeerd staat:** De scheidingslijn is de **OPEN** (voorkant body) van de Hold Level Candle.
*   **Short Invalidation:** Vormt zich een *Groene* candle die compleet **BOVEN de body-open** van de groene Hold candle van het level `opent` EN `sluit`? -> Structuur doorbroken. Setup dood.
*   **Long Invalidation:** Vormt zich een *Rode* candle die compleet **ONDER de body-open** van de rode Hold candle `opent` EN `sluit`? -> Structuur doorbroken. Setup dood. 
*(Let op: Enkele wicks - hoe diep ook - door deze zone heen veroorzaken géén invalidatie, zolang het body-gewicht er niet voorbij sluit).*

### Fase 3: De Target Bevestiging (De "Test" Trigger)
Hier smelten het Test Blok (`anchor`) en het Executie Blok (`b2`) samen tot één geverifieerd signaal.
*   **De Trigger:** De Engine activeert The Golden Setup pas zodra de live marktprijs de instapwaarde (de extremiteit / wick aan de voorkant) van het levende **Test Blok** heeft gepenetreerd ("getest"). 
*   **Het Instapmoment:** Vanaf het minuut-tiende dat het Test Blok fysiek werd aangetikt en succesvol functioneerde als bumper (zonder dat er een *Hard Close* volgde), zoekt de bot naar dat opvolgende **Executie Blok** dat de omslag bevestigt.
*   **Resultaat:** Zodra het Executie Blok (`b2`) compleet en gesloten is, markeert het algoritme deze als een actief `OrderIntent` waarbij de entry limiet order fysiek klaargezet wordt op de OPEN prijs van de Hold candle van dít Executie Blok.

### Fase 4: Premium / Discount Berekening
Een confirmed setup mag in deze strategie *uitsluitend* gehandeld worden in een voordelige marktrange.
*   **Regel:** De Engine haalt de actuele local top & bottom op over de laatste `premium_discount_window_size` (standaard **150 minuten/candles** in playbook). 
*   **Uitsluiting:** Formeert zich een Short (sell) setup in de onderste helft (Discount zone)? Genegeerd. Formeert zich een Buy setup in de bovenste helft (Premium zone)? Genegeerd. Enkel met de marktrichting mee wordt geaccepteerd.

### Fase 5: Simulatielock
*   Zodra een Order op tafel ligt op de live markt, plaatst de scanner de historisch in het verleden gevonden trades *ook* op de loopband in memory en simuleert `sim_frontrun_points`, `tp_points` en `sl_points`. Hiermee test de code intern in fracties van seconden of de trade inmiddels (historisch tot nu) was ingevuld en afgesloten of ge-lossed-out en daarmee onschadelijk.

---

## 4. De Tijdsrestrictie

**Betrokken Script:** `src/layer3_strategy/modules/killzone_filter.py`
**Configuratie via:** `strategy_playbook.json -> KillzoneFilter`

Aan dit punt kunnen alleen nog gevalideerde, actieve limit blocken op The Golden Setup voorbij komen.
*   **Timeshift:** UTC Wordt geforceerd gelinked naar `"America/New_York"` (EST local tijd).
*   **Tijden van validiteit (`start_hour`/`end_hour`):** 00:00 - 23:59. Dit houdt in dat momenteel theorievorming letterlijk rond de klok reageert op setups.
*   **Exceptie blokken (`exclude_windows`):**
    *   **Opening:** Van 09:20 tot 09:40 EST. Alle intents sterven onmiddellijk, geen uitvoering toegestaan wegens spread en cash open liquiditeit manipulatie.
    *   **Lunch:** Van 12:00 tot 13:00 EST. De markt is berucht om wispelturig gedrag en lage liquiditeit in dit uur; we pauzeren nieuwe setups.
    *   **Sluiting/Vast:** Van 15:49 tot 18:00 EST. Geen pre-market of pre-close carry over toegestaan. Limit orders verdwijnen in dit block als sneeuw voor de zon (wat via de `LiveFleetCommander` resulteert in cancel-all).

---

## 5. De Wraak-Trade Blokkade (Loss Cooldown)

**Betrokken Script:** `src/layer3_strategy/modules/loss_cooldown_filter.py`
**Configuratie via:** `strategy_playbook.json -> LossCooldownFilter`

*   **Regel:** Voorkomt zogenaamde revenge-trading. Zodra de bot detecteert dat de vorige trade is afgesloten in een verlies (Stop-Loss geraakt), weigert deze module nieuwe setups goed the keuren gedurende een ingestelde afkoelperiode.
*   In `strategy_playbook.json` staat deze momenteel op **30 minuten** (`cooldown_minutes: 30`). Dit beschermt het account tegen "chop" of tilt.

## 6. De Versheidsfilter

**Betrokken Script:** `src/layer3_strategy/modules/ttl_timeout.py`
**Configuratie via:** `strategy_playbook.json -> TTLTimeout`

*   **Regel:** Setups op de NQ die al lang wachten verkleinen significant de risk/reward ratios naarmate liquiditeit wegsijpelt of poolt. De Hold Level mag ten tijde van evaluatie in minuten vergeleken met nú nooit ouder zijn dan `max_candles_open`.
*   In `strategy_playbook.json` staat deze op **15 minuten** harde cut-off. Als het Hold blok 16 minuten oud wordt voordat we kunnen traden => Cancel en negeer.

---

## 7. Het Broker Vertalingsblok (Rejection As Target)

**Betrokken Script:** `src/layer3_strategy/modules/limit_order_execution.py`
**Configuratie via:** `strategy_playbook.json -> RATLimitOrder` en `execution_config.json`

Als *alles* hier succesvol door resulteert volgt finalisatie van Limit, Stoploss en Takeprofit (OCO Bracket formatie).

De instellingen in het configuratie-bestand worden letterlijk en puur abstract gepompt:
*   **Tekenformaat (`tick_size`):** 0.25 pt (MNQ/NQ specificeert 4 ticks per punt).
*   **Absoluut Entry / Frontrunning (`entry_frontrun_ticks`):** 12 ticks = 3.0 volle index punten. De frontrun baseert de Limit placement op de OPEN van je Hold Level met compensatie in the right way (Short Limit ligt -3.0 punten onder de Open; Long Limit staat +3.0 punten op de body) om volume-fills te waarborgen.
*   **Absolute Profit/Risk Ratio:** Aangedreven door `absolute_sl_points` (14.0 pts / 56 ticks) en `absolute_tp_points` (14.0 pts / 56 ticks). 
*   **Breakeven Shield:** Bevat geavanceerd trade management! Met `breakeven_trigger_rr: 0.5` schuift de broker native de stoploss naar je instapprijs (+ `breakeven_offset_ticks: 2` voor fees) zodra de trade halverwege zijn target is (op +6 punten winst in dit geval). Dit dekt je in tegen plotselinge reversals.

### Samengevat
Als alles slaagt en dit resulteert in output, pakt het script 1 (De FleetCommander) precies dat Entry (met frontrun), dat Stop Loss en die Take Profit, lockt het setup path, en vuurt die 3-traps raket als één geverifieerd Topstep Bracket naar je portfolio voor onmiddellijke afhandeling.
