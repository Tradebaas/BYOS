# CCTA Terminology to Code Mapping

Dit document definieert de 1-op-1 mapping tussen de theorie in `DAY_TRADING_DECRYPTED.md` en de modulaire code-implementatie. Dit vormt de brug tussen de binaire, mechanische definities en herbruikbare, geïsoleerde code-modules (Lego-blokjes). Alles in dit document blijft binnen de toegestane CCTA terminologie.

Voor de theorie-componenten die we machinaal willen verwerken, voegt dit document conceptuele pseudo-code/basis-implementaties toe. Hierdoor is direct zichtbaar en verifieerbaar hoe theorie wordt omgezet in machinale wiskunde.

---

## 1. Core Levels (De Fundering)

Deze elementen vormen de basis van de chart.

| Term uit Theorie | Definitie in Code / Logica | Voorgestelde Module / Class |
| :--- | :--- | :--- |
| **Deepest Point** | De absolute wick high/low van een V-shape of A-shape in price action. Dient als anker. | `dataclass Point(price, timestamp)` |
| **Data Point** | De price action actie zelf. Wordt een abstractie in code om niveau's te bepalen. | `DataPointAnalyzer` |
| **Hold Level** | De body close (hoogste groene body / laagste rode body) behorend bij een Deepest Point. Enige vereiste in de engine: Een `Hold Level` is onafhankelijk *untested* of *tested*. | `class HoldLevel` (State: Untested, Tested, Hard Closed) |
| **Break Level** | De wick van de start-candle van een *consecutive run* (2 of meer candles in dezelfde richting). | `class BreakLevel` |
| **Hard Close** | Een conditiewaarde: sluit de body van de huidige candle over een level heen? Zo ja, the level is overwritten. Zorgt voor removal van oude levels. | `def is_hard_closed(level, current_candle)` -> bool |
| **Tested** | Een absolute binaire status: `True` of `False`. Wordt getriggerd zodra prijs exact het level raakt. | Level property: `self.is_tested` |

> ⚠️ **LET OP: ONDERSTAANDE CODE ZIJN PUUR EN ALLEEN GENERIEKE VOORBEELDEN**
> De Python-blokken hieronder zijn ruwe abstracties. Ze dienen **uitsluitend ter illustratie** om de brug te slaan tussen theorie en wiskundige logica. De modulaire *Core Domain Building Blocks* zullen **0,0 strategie-variabelen** bevatten. Alles wordt 100% generiek en abstract; eventuele variabelen (zoals ticks, tijden of offsets) komen uitsluitend uit de externe Strategy JSON Playbooks (Laag 3).

### 🛠️ Voorbeeld: Wiskundige Implementatie:

**1. Break Level (De Oorsprong)**: Hoe het Break Level wordt ingesteld op de grafiek.
```python
# Concept code -> `process_candle()`
# Bullish Break: Red -> Green -> Green (Consecutive Run down->up)
if c0.is_bullish and c1.is_bullish and c2.is_bearish:
    # lvl = BreakLevel(diepste punt wick, is_break_up=False, index) 
    lvl = BreakLevel(c1.low, False, bar_index - 1, getattr(c1, 'timestamp', 0))
    self.breaks.append(lvl)

# Bearish Break: Green -> Red -> Red (Consecutive Run up->down)
if c0.is_bearish and c1.is_bearish and c2.is_bullish:
    # Maakt een Break Level aan op de absolute High.
    lvl = BreakLevel(c1.high, True, bar_index - 1, getattr(c1, 'timestamp', 0))
    self.breaks.append(lvl)
```
*Beschrijving: Controleert EXACT op de theorie dat er sprake moet zijn van 2 consecutive kaarsen om een Break Level op het kantelpunt te ankeren.*

**2. Hard Close (Invalidatie grens)**: Hoe de engine weet of een level stuk is gegaan.
```python
# Concept code -> `hard_close()`
def hard_close(self, price: float, is_break_up: bool, candle) -> bool:
    if is_break_up: # Resistance (is_break_up = True)
        # Invalidatie: Volledige body moet aan de 'verkeerde' kant sluiten
        return candle.is_bullish and candle.open > price
    else: # Support (is_break_up = False)
        return candle.is_bearish and candle.open < price
```
*Beschrijving: Wiskundige handhaving dat alléén de Body Close boven de grens telt. Een wick ("Deep Dive") veroorzaakt hier dus nog geen invalidatie!*

**3. Test Count Separatie (Onafhankelijk raken)**:
```python
# Binnen de loop over actieve Break/Origin levels
if lvl.waitingRetest:
    # Heeft de wick van de kaars het level exact of dieper geraakt?
    touched = (c0.high >= lvl.price) if lvl.is_break_up else (c0.low <= lvl.price)
    if touched:
        lvl.testCount += 1
        lvl.waitingRetest = False 
        # Zodra geraakt, MOET wachten op de tegenstelde candle ('waitingOpposite') 
        # voordat een volgende test meetelt. Dit waarborgt onafhankelijke tests.
```

---

## 2. Polarity Levels (Geteste Levels met Tijdsframe Elevatie)

| Term uit Theorie | Definitie in Code / Logica | Voorgestelde Module / Class |
| :--- | :--- | :--- |
| **Origin Level** | Een `Break Level` dat twee keer onafhankelijk is getest (met separatie daartussen). | `class OriginTracker` |
| **Reverse Level** | Een `Hold Level` dat twee keer onafhankelijk is getest. | `class ReverseTracker` |
| **Deep Dive** | Een wiskundige term voor het wel kruisen maar niet 'hard closen' van een level. Het test-contact doorboort, maar invalideert niet. | `class TestEvent` (met modifier property) |
| **Polarity State** | De binaire verschuiving wanneer de theorie stelt dat het omkeert na een valid invalidation. | `class PolarityTracker` |
| **Pandora's Box** | De ingesloten status tussen twee Actieve Hold Levels (top en bottom) zonder theorie bias. | `class ScopeBoxTracker` |
| **Range Trends** | Een Hold level hit multiple times while satisfying Break level criteria. | `class RangeTrendTracker` |
| **Trends** | Diagonale levels connecting two or more Hold/Break level points. | `class TrendLineTracker` |


### 🛠️ Voorbeeld: Wiskundige Implementatie:

**Origin Level Elevatie**:
```python
# Zodra een Break Level minimaal 2 onafhankelijke tests incasseert, 
# promoveert het tot Origin Level.
if lvl.testCount >= 2 and lvl.originBar is None:
    lvl.originBar = bar_index # Zet het startpunt vast vanaf waar we setup kandidaten gaan zoeken
```
*Beschrijving: De code forceert strak dat theorie niet mag reageren op 0 of 1 test. Pas na testCount == 2 promoveert het object.*

---

## 3. Entry Structuur: De Hold Level Kandidaat Zoektocht

| Term uit Theorie | Definitie in Code / Logica | Voorgestelde Module / Class |
| :--- | :--- | :--- |
| **Hold Level Kandidaat** | Voor een Resistance (Bearish) setup: De meest hoge ongeteste GROENE (bullish) candle tussen het Break Level (Origin creatiepunt) en nu. Voor een Support (Bullish) setup: De meest lage ongeteste RODE (bearish) candle. Zodra er een hogere/lagere kandidaat vormt, wordt dit de nieuwe kandidaat, mits het Origin Level geldig blijft. | `class HoldLevelFinder` |

### 🛠️ Abstractie Implementatie Code:

**De zoektocht naar het Target (Voorbeeld voor Short/Resistance Setups richting een Origin Level)**:
```python
if lvl.testCount >= 2 and lvl.originBar is not None:
    # Stap A: Kandidaat Zoeken
    # Voor een resistance Origin Level zoeken we de hoogste GROENE (bullish) kaars 
    # die ontstond ná de formatie van het Origin Level (originBar), maar waarvan de OPEN nog net
    # onder het Origin Level is gebleven.
    for i in range(lvl.originBar, bar_index + 1):
        c = self.candles[i]
        limit_status
        if c.is_bullish and c.open < lvl.price:
            if c_open is None or c.open > c_open:
                # Strengste kandidaat gevonden (meest gunstige positie)
                c_open = c.open; c_low = c.low; c_high = c.high; c_bar = i
                
    # Stap B: De Hard Close (Definitieve Validatie van de Hold Level Kandidaat)
    if not h_valid:
        # Een RODE kaars sluit onder de LOW van de laatst gevonden Groene Kandidaat.
        if c_open is not None and c.is_bearish and c.open < c_low and c.close < c_low:
            h_valid = True; # Kandidaat gepromoveerd naar Actief Hold Level
            h_open = c_open; h_low = c_low # Data opgeslagen voor Limit Order generatie
```
*Beschrijving: Dit kwantificeert exact the theorie "Laatste push omhoog voordat het weerdrukt, mits een Hard Close plaatsvindt onder dat body niveau". Dit stelt het exacte entry niveau (Target) veilig vast in `h_open`.*

---

*Opmerking: Toekomstige theorie elementen zoals Range Logic (Pandora's box, RATs, Trails) worden in de nieuwe modulaire architectuur op exact dezelfde binaire manier uitgeschreven in het nieuwe `src/engine/modules` domein, volkomen geïsoleerd ontworpen.*
