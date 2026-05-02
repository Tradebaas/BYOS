# Strategy Building Blocks 

De `FleetCommander` architectuur is gebouwd op robuuste, onafhankelijke blokken. Dit stelt ons in staat om in `json` format exact de specificaties van onze strategie te injecteren, zonder elke keer de engine ("de motor") om te hoeven bouwen.

Deze documentatie beschrijft technisch én logisch de interne werking van de modules die verantwoordelijk zijn voor theorie en executie.

---

## 1. Algemene Pipeline Flow

De architectuur kent 4 primaire lagen, waarvan Lagen 2 en 3 volledig modulair zijn:
1. **Layer 1 (Data):** Ontvangt ruwe WS candles, filtert corrupties en bouwt tijdsframes.
2. **Layer 2 (Theory):** Markeert theorie abstracties in een `MarketState` object (zoals Premium/Discount mapping, origin pool detectie).
3. **Layer 3 (Strategy):** Leest `strategy_playbook.json`, filtert de `MarketState` volgens restricties (bijv. validatie van een setup) en bouwt, indien goedgekeurd, een `Intent`.
4. **Layer 4 (Execution):** Stuurt de `Intent` af op TopstepX (Frontruns, Limit Brackets).

---

## 2. Layer 2: Theory Modules
L2 modules zijn passieve markeringen. Ze genereren géén orders, maar geven de markt mathematisch 'kleur' op basis van pure data.

### `Hold Level & Break Level Detectoren` (via `MarketTheoryState`)
* **Werking:** Analyseert continu de binnenkomende 1-minuut market flow om theorie fundering the leggen.
* **Techniek:** 
  * **Hold Levels:** Slaat wiskundige candidates (bijv. top/bottom wicks) op en valideert deze uitsluitend als er een Hard Close aan de andere kant plaatsvindt. 
  * **Hard Closes (ABSOLUTE REGEL):** Een level is pas wiskundig gemarkeerd als Hard Closed wanneer de candle-body (open én close) er volledig doorheen breekt ÉN de candle-kleur (momentum) matcht met de richting van de uitbraak. Een bearish HC (downward break) vereist absoluut een rode candle (`is_bearish`). Een bullish HC (upward break) vereist absoluut een groene candle (`is_bullish`). **Roep waar mogelijk de centrale `is_hard_close()` methode aan vanuit `src/layer2_theory/hard_close.py`. Waar native inline checks voorkomen, controleer ALTIJD de momentum kleur!**
  * **Break Levels:** Tracked sequentie patronen (bijv. Groen, Rood, Rood) om zuivere breaks the diagnosticeren.

### `OriginStateMachine`
* **Werking:** Neemt de ruwe Break Levels en Hold Levels en begeleidt ze door hun theorie levenscyclus. Promoveert lijnen tot Origins of Reverse Levels via validatietesten.
* **Techniek:** Gebruikt geïsoleerde trackers (State Machines) per lijn. Spot "Deep Dives" (penetratie, maar geen gesloten constructie) en ruimt lijnen hardhandig uit het systeem zodra ze "Hard Closed" worden door theorie invalidatie.

---

## 3. Layer 3: Strategy Modules
L3 modules zijn de actieve filters. Zij nemen het gekleurde theoriegeheugen over en beslissen op basis van jouw JSON playbook of er een trigger en uitvoering plaatsvindt.

### `ConfirmationHoldLevelTrigger`
Dit is de kloppende hartklep van je Setup-Detectie. Het is een 1-minuut Sweep & Confirm scanner.
* **Flow:**  Zoekt over een bias_window (bijv 200 candles) eerst naar een Anchor-Block (Trap), wacht tot prijs die Anchor test, en bevestigt vervolgens het ontstaan van een _nieuw_ Block in die test!
* **Bias Filter (Premium & Discount):** Filtert setups op grote marktbewegingen.
  1. Neemt het hoogste en laagste punt over het meegegeven tijdvenster (bias window).
  2. Berekent het wiskundige midden (50% eq).
  3. Prijs > 50%: **Premium** Zone (Hier keurt hij alléén Short-setups goed).
  4. Prijs < 50%: **Discount** Zone (Hier keurt hij alléén Long-setups goed).
* **Output:** Bij een harde sweep, confirm én Premium/Discount conformering spuugt hij de wiskundige target uit naar de rest van de pipeline.

### `OriginLevelTrigger`
Dit is de gespecialiseerde L3 trigger ontworpen voor de geïsoleerde Origin Scalper strategie.
* **Flow:** Scant de actieve L2 `MarketTheoryState` passief voor levende `OriginTracker` objecten.
* **Filter Logica:** Vuurt exclusief een target (Intent) af naar de pipeline wanneer een Break Level precies één keer getest is (`test_count == 1`) én de luchtbel actief is (`waiting_retest == True`).
* **Premium/Discount:** Beschikt over een optionele `premium_discount_window_size` (standaard uitgeschakeld met 0). Indien aan, dwingt hij de setup af te spelen in de logische macrorichting.
* **Output:** Als aan de stricte logica is voldaan, maakt hij een Target Candidate op de *exacte* rand van het theorie-level voor verdere L4 executie (als limit order).

### `KillzoneFilter`
* **Functie:** Tijdslot-filter. Bepaalt of de tijd van de dag wel is toegestaan om the handelen (bijv. in `America/New_York` timezone). Buiten deze zone sneuvelt iedere opgebouwde theorie direct on the spot.

### `TTLTimeout`
* **Functie:** Tijdslimiet beveiliging (Time To Live). Als een setup tracker overleeft maar na `max_candles_open` (bijv 30 minuten) nóg steeds niet bij z'n target is, wist deze module hem genadeloos uit the pijplijn en triggert hij op de achtergrond orders-cancellations.

### `RATLimitOrder` (Rejection As Target Execution)
Dit is de kluiswachter die het risico afdicht zodra álle voorgaande modules groen licht geven, om in te sluiten voor L4.
* **Functie:** Converteert abstracte niveaus naar harde Topstep intenties o.b.v ticks en parameters in je JSON playbook.
* **Techniek:** Past `entry_frontrun_ticks` toe, en rekent  `absolute_sl_points` en `absolute_tp_points` exact om. Deze logica the gelaagd over het wiskundige level en wekt het `Intent` object op dat the L4 Motor aanvuurt.

---

## 4. Tick vs Point Architectuur
In `FleetCommander` definiëren we alles rond de NQ-Emini strict in `Ticks` via de JSON bestanden, terwijl de backend Python engine dit naar drijvende komma's `Points` rekent via het `tick_size` profiel.
* **Aanname Engine:** `/NQ` heeft `tick_size: 0.25`.
* **Conversie L3:** `48 ticks SL * 0.25 = 12.0 full points`.

Als een Long Hold Level op `20000.0` gecalculeerd wordt met een `entry_frontrun_ticks = 12`:
* **Entry:** `20000.0 + (12 * 0.25) = 20003.0`
* **SL:** `20003.0 - (48 * 0.25) = 19991.0`
* **TP:** `20003.0 + (48 * 0.25) = 20015.0`

> Dit garandeert dat *elke module onafhankelijk, wiskundig zuiver en identificeerbaar is.* Geen slordige spaghetti, maar strak aangedraaide ratchets.
