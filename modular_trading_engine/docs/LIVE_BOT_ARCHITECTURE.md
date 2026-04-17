# Live Trading Bot Schema & Cloning Guide
*Documentatie over de exacte keten van actieve componenten voor de "Day Trading Decrypted" (Fleet Commander) executie.*

Dit document dient als referentie om de momenteel draaiende handelsbot 1-op-1 over te dragen naar een nieuwe repository of een vers sandbox-project. Als je uitsluitend de onderstaande bestanden in exact deze directorystructuur kopieert, en de minimale packages (`requests`, `pandas`) installeert, bezit je feilloos exact dezelfde motor.

---

## 🚀 Layer 4: De "Aansturing" (Executie Machine)
*De fysieke connectie met de buitenwereld, de broker en de klok.*

1. **`src/layer4_execution/live_fleet_commander.py`**
   * **Rol: De Kapitein.** Dit is het hoofdscript dat via de terminal wordt opgestart (`python3 ...live_fleet_commander.py`). Het draait in een eindeloze 10-seconden cyclus (`while True`). Hij leest het live orderboek uit via de broker-client, kijkt of je nog posities open hebt, roept Layer 3 erbij om orders of invalidaties te berekenen, stuurt de SL naar Break-Even, of vuurt het commando af voor het verplaatsen van nieuwe entry-orders.
2. **`src/layer4_execution/topstep_client.py`**
   * **Rol: De Tolk.** De Fleet Commander reageert op "intenties". Deze client vertaalt dat onzichtbaar in een cryptische REST webservice call (JSON-payloads) direct naar de ProjectX-servers van Topstep. Hij lost automatische contract-rollovers op, voorkomt API-spam, beheert absolute ticks polariteiten en regelt de vitale `CancelAll` emergency hooks.

---

## ⚙️ Layer 3: Het Handelsbrein (Playbook Strategie)
*Het configuratiehart en het wiskundig rekenpaneel.*

3. **`data/playbooks/day_trading_decrypted.json`**
   * **Rol: Het Receptenboek.** Geen codebestand, maar de absolute stuurknuppel voor de theorie. Hierin stel je de dynamische paramaters op: de killzone ranges, SL (15 pnt), TP (30 pnt), de Premium/Discount index bias window, hoelang orders open mogen staan, etc.
4. **`src/layer3_strategy/rule_engine.py` (samen met `config_parser.py`)**
   * **Rol: De Transportband.** Het Python systeem dat de json uit het playbook dynamisch inlaadt, en de in dat document genoemde losse modules letterlijk als blokken aan elkaar rijgt tot één sequentiële productielijn (pipeline).  
5. **`src/layer3_strategy/modules/confirmation_hold_level_trigger.py`**
   * **Rol: Jouw Wiskundige Signaleringsmodule.** Het kloppende hart van de logica. Analyseert de C1 en C2 structural blocks, onthoudt zwevende geteste niveaus tegelijkertijd via een *Multi-Anchor Stack*, test op correcte Hard Closes en filtert hard op een geldig Discount entry-level voor Longs en Premium voor Shorts op basis van de historische ranges.
6. **`src/layer3_strategy/modules/killzone_filter.py`**
   * **Rol: De Tijdwaakhond.** Leest de klok van de kaars. Gooit theorie signalen rücksichtslos in de prullenbak wanneer ze binnen pre-market openingstijden of specifiek gedefinieerde settlement exclusion-windows vallen.
7. **`src/layer3_strategy/modules/ttl_timeout.py`**
   * **Rol: De Zandloper (Time-To-Live).** Evalueert per "intentie" hoelang het geleden is sinds het bevestigingsblok definitief gevormd is. Bij de 30-minuten deadline markeert de timeout module de orderwaarde als verlopen (waarmee Layer 4 gealarmeerd wordt om TopstepX te liquideren).
8. **`src/layer3_strategy/modules/limit_order_execution.py`**
   * **Rol: De Vormgever (RAT Submodule).** Als wiskundig de setup is goedgekeurd èn hij buiten de killzone en TTL deadlines valt, transformeert deze scriptmodule de theoretische wens tot een concreet `OrderIntent` doosje door wiskundig de 1-punt tick frontrun, de daadwerkelijke StopLoss, en target winst doelen af te drukken.

---

## 📚 Layer 1 & 2: Datacenter en Type Declaraties
*Passieve infrastructuur componenten op de achtergrond.*

9. **`src/layer2_theory/market_state.py`**
   * **Rol: De Databank.** Wordt constant gevoed met kaarsenstroom van de broker. Het enige wat dit vitaal vereiste script op de achtergrond hoeft te verzetten, is te waken over een schone en stabiele cache van de laatste `2000` minutenkaarsen gesorteerd op rijtje (in list object `history`). Dat vormt de vijver waar de rekenmodules uit deel 3 continu in vissen ter evaluatie.
10. **`src/layer1_data/models.py` & `src/layer4_execution/models_broker.py`**
    * **Rol: De Enveloppen.** Handige Python `dataclasses`. Het installeert formele afspraken en benamingen hoe het uiterlijk van een dataset er überhaupt uit mag zien (Bijvoorbeeld `Candle` bezit de properties `timestamp, o, h, l, c, vol` of `OrderIntent`). Dit format is strikt verplicht om blind en foutloos data te distribueren over de ketting van submodules hierboven. 


---

## ⚠️ Afhankelijkheden & Ontbrekende Imports voor Klonen
*Als je de bovenstaande scripts kopieert naar een leeg nieuw project, loop je tegen missende imports aan. Hier is de handleiding over hoe je daarmee omgaat:*

### Categorie A — Moeten we meenemen (Basisraamwerk van de pipeline)
Deze modellen/classes representeren het datamodel en de ruggengraat van de engine en **moeten** exact gekopieerd (of opnieuw aangelegd) worden:
* **`TheoryLevel` + `LevelType`** *(uit src/layer2_theory/models.py)* — Pydantic model dat een getekend niveau (zoals een confirmation block) inclusief structuur-type representeert. Af te leiden uit de data structuur in `market_state`.
* **`BaseStrategyModule`** *(uit src/layer3_strategy/modules/base.py)* — Abstracte basisklasse voor pijplijnmodules (met een init en de abstracte `process(context)` functie).
* **`PipelineContext`** *(uit src/layer3_strategy/pipeline_context.py)* — Dataklasse die zich gedraagt als "het tasje". Het stroomt van module naar module om variabelen blind door te geven zoals `timestamp`, `setup_candidates`, `intents`, en ruwe theorie-data.
* **`OrderIntent`** *(uit src/layer3_strategy/models.py)* — Pydantic model stempel die de Topstep entry-prijs, limit of stops definieert.
* **`PlaybookConfig`** *(uit src/layer3_strategy/playbook_schema.py)* — De JSON validator structuur (schema) voor de config `day_trading_decrypted.json`.
* **`MODULE_REGISTRY`** *(uit src/layer3_strategy/modules/__init__.py)* — Een simpele dict zoals: `{"ConfirmationHoldLevelTrigger": ConfirmationHoldLevelTrigger}`.
* **`fetch_topstepx_jwt`** *(uit src/layer4_execution/auth.py)* — Losse functie voor het inloggen op TopstepX.

### Categorie B — NIET strikt nodig voor déze strategie ("Dead Weight")
*Bestaande module imports boven in `market_state.py` zoals: `RangeTrendTracker`, `TrendLineTracker`, `OriginTracker`, `detect_deep_dive`, `ScopeBoxTracker` en `PolarityTracker`.*

> [!IMPORTANT]
> **Cruciale observatie:** Onze specifieke `confirmation_hold_level_trigger.py` logica doet momenteel zijn GEHEEL EIGEN block-detectie via zijn interne `find_blocks()` constructie.
> Het maakt dus nergens gebruik van de levels die in `market_state.py` uitgerekend worden door Categorie B trackers!
> 
> **Wat betekent dit?** De strategie leest enkel `context.theory_state.history` (de ruwe lijst met verwerkte kaarsen). Bij het kopiëren en vers opzetten in de nieuwe repository, mag je álle zware reken-trackers en imports uit de `market_state.py` definitie rücksichtsloos verwijderen. Ze draaien nu op de achtergrond geheugen te consumeren, maar onze actuele Fleet Commander strategie vist uitsluitend uit de kale history-lijst! Dit maakt het gekloonde project direct 10x zo "lightweight".
