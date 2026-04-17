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
L2 modules zijn passieve markeringen. Ze genereren géén orders, maar geven de markt mathematisch 'kleur'.

### `TrackPremiumDiscount`
* **Werking:** Bepaalt continu het dynamische "Midden" (50% eq) van de huidige marktfase, gebaseerd op een tijds-venster (bijv. de sessie-top en bodem).
* **Techniek:** Berekent het hoogste en laagste punt over een specifieke terugkijk-range (bijvoorbeeld `{"lookback_minutes": 200}`). Filtert de waarden daarvan en creëert de logische gebieden:
  * Prijs > 50%: **Premium** Zone (Hier mogen we alléén Shorten)
  * Prijs < 50%: **Discount** Zone (Hier mogen we alléén Longen)

### `TrackOriginPools`
* **Werking:** Identificeert specifieke 'Fair Value Gaps' of 'Order Blocks' in de markt en catalogiseert deze als `Origins`.
* **Techniek:** Neemt de laatste x-kaarsjes per tick om onbalans te speuren. Slaat de pool op in de locale geheugen array (`state.active_origins`). Zodra prijs deze later aanraakt, heet dit een `mitigation`. 

---

## 3. Layer 3: Strategy Modules
L3 modules zijn de actieve filters. Zij nemen het gekleurde `MarketState` object van L2 over en beslissen op basis van jouw JSON file of er een trigger en uitvoering plaatsvindt.

### `ConfirmationHoldLevel_Trigger`
Dit is de kloppende hartklep van de DTD_Golden_Setup. 
* **Input Parameters (Playbook):**
  * `bias_filter`: Vereist dit strict Premium/Discount concordantie? (True/False)
  * `min_volume`: Trackt orderbook momentum.
  * `entry_frontrun_ticks`: De unieke frontrun op het _Target Hold Level_.
* **Algoritme Executie-Flow:**
  1. Module scant of er recent (bijv. binnen huidige minuut) een verse candle gesloten is vóór de `OriginPool`.
  2. Indien de sluiting exact in de correcte Premium/Discount kwadrant zit, bepalen we het exacte wiskundige Level dat we willen verdedigen.
  3. **Belangrijkste Berekening:** Er is géén hardcoded wiskunde binnen deze module. Hij respecteert 100% de frontrun offset die jij via je JSON mee geeft.

```json
// Voorbeeld uit strategy_playbook.json
"pipeline": [
  {
    "module_type": "ConfirmationHoldLevelTrigger",
    "params": {
      "bias_window_size": 200
    }
  }
]
```
_In bovenstaand voorbeeld filtert de module uitsluitend trades die goed de huidige sessie-bias vallen._


### `RATLimitOrder_Execution`
Dit is de kluiswachter die het risico afdicht zodra de L3 Trigger groen licht geeft.
* **Functie:** Berekent harde brackets om de `Intent` in te kapselen voor L4.
* **Stop Loss (SL):** Neemt het frontrun entry level als absolute basis, pakt de wiskundige target (bijv. 10 punten absoluut via `absolute_sl_points`), en reserveert het `sl_price` veld. Deze logica is gebouwd met een _absoluut-waarde safeguard_, waardoor de Topstep bracket-offset nooit per ongeluk geïnverteerd bij de API aankomt.
* **Take Profit (TP):** Hetzelfde mechanisme voor return targets (RR).

```json
// Voorbeeld uit strategy_playbook.json
"pipeline": [
  {
    "module_type": "RATLimitOrder",
    "params": {
      "tick_size": 0.25,
      "entry_frontrun_ticks": 4,
      "absolute_sl_points": 10.0,
      "absolute_tp_points": 20.0
    }
  }
]
```

---

## 4. Tick vs Point Architectuur
In `FleetCommander` definiëren we alles rond de NQ-Emini strict in `Ticks` via de JSON bestanden, terwijl de backend Python engine dit naar drijvende komma's `Points` rekent via het `tick_size` profiel.
* **Aanname Engine:** `/NQ` heeft `tick_size: 0.25`.
* **Conversie L3:** `64 ticks SL * 0.25 = 16.0 full points`.

Als een Long Hold Level op `20000.0` gecalculeerd wordt met een `entry_frontrun_ticks = 4`:
* **Entry:** `20000.0 + (4 * 0.25) = 20001.0`
* **SL:** `20001.0 - (64 * 0.25) = 19985.0`
* **TP:** `20001.0 + (80 * 0.25) = 20021.0`

> Dit garandeert dat *elke module onafhankelijk, wiskundig zuiver en identificeerbaar is.* Geen slordige spaghetti, maar strak aangedraaide ratchets.
