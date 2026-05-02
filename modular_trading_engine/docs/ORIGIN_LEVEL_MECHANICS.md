# Origin Level Mechanics & State Machine

Dit document is de Single Source of Truth (SSOT) voor de exacte wiskundige en logische definities van Break Levels, Origin Levels, en de state machine die bijhoudt hoe ze promoveren en sterven. Deze logica is gevalideerd in zowel Pine Script (TradingView) als Python (Backtest Simulator).

---

## 1. De Geboorte (Creatie van een Break Level)
Een Break Level is het fundamentele bouwblok. Het representeert een extreme wick voordat de prijs wegbreekt.

**Bearish Break Level (Resistance / Short):**
- **Patroon**: Groen (Hold) -> Rood (Candle 1) -> Rood (Candle 2).
- **Wiskunde**: `close[2] > open[2]` EN `close[1] < open[1]` EN `close[0] < open[0]`.
- **Prijs**: De wick (high) van de *eerste* rode candle (`high[1]`). Dit is het exacte Break Level.

**Bullish Break Level (Support / Long):**
- **Patroon**: Rood (Hold) -> Groen (Candle 1) -> Groen (Candle 2).
- **Wiskunde**: `close[2] < open[2]` EN `close[1] > open[1]` EN `close[0] > open[0]`.
- **Prijs**: De wick (low) van de *eerste* groene candle (`low[1]`).

Zodra dit blok voltooid is, wordt het level opgeslagen in het **geheugen (een gestackte array)**. 
- Initiele status: `tests = 0`
- Separatie-status: `can_be_tested = false`

---

## 2. De Separatie-Regel (De Luchtbel)
Een level mag **nooit** zomaar getest worden als de prijs er nog tegenaan plakt. Er is verplichte separatie nodig. 

**De Logica:**
- Een level mag pas getest worden (`can_be_tested = true`) zodra er minimaal één volledige candle (inclusief wicks) gevormd wordt die het level **niet** raakt.
- **Bearish**: De `high` van de candle moet strikt *onder* het Break Level liggen (`high < lvl.price`).
- **Bullish**: De `low` van de candle moet strikt *boven* het Break Level liggen (`low > lvl.price`).

*Cruciaal Inzicht:* Zelfs de "Candle 2" uit het creatie-blok (de tweede rode candle) kan direct al voor separatie zorgen, zolang zijn wick het level (`high[1]`) niet raakt!

---

## 3. Testen & Promotie (De Aanraking)
Wanneer een level wél mag worden getest (`can_be_tested == true`), scant de machine of de huidige candle wick erdoorheen prikt.

**De Logica:**
- **Bearish Hit**: `high >= lvl.price`
- **Bullish Hit**: `low <= lvl.price`

**Wat gebeurt er bij een hit?**
1. Het aantal tests gaat omhoog: `tests += 1`.
2. Het level wordt **direct** weer gedeactiveerd: `can_be_tested = false`. Het heeft nu wéér een verse luchtbel (separatie) nodig voordat hij een volgende test mag ontvangen.
3. **Promotie**: 
   - Bij `tests == 1` is het een formeel **Tested Break Level**.
   - Bij `tests == 2` promoveert het officieel tot een **Origin Level**.

---

## 4. Invalidatie (De Dood door Hard Close)
Een level kan meerdere tests overleven (wicks die erdoorheen prikken), maar sterft **direct en onmiddellijk** zodra er een Hard Close plaatsvindt over het level heen.

**De Logica:**
- **Bearish (Resistance)**: Sterft als `close > lvl.price`. (De candle body sluit óver het dak).
- **Bullish (Support)**: Sterft als `close < lvl.price`. (De candle body sluit ónder de vloer).

Zodra dit gebeurt, wordt de status `is_dead = true`. Het level stopt met het tellen van tests en doet niet meer mee voor executie (het belandt op het kerkhof).

---

## 5. Het Geheugen (Stacked Levels Tracking)
De engine maakt geen gebruik van één "globale" variabele die steeds overschreven wordt, maar gebruikt een **Stack (Array)**.

- **Oneindig Geheugen**: Elk nieuw Break Level wordt gewoon toegevoegd aan de lijst.
- **Multitasking**: De engine kan probleemloos 5 Resistance levels en 3 Support levels tegelijk monitoren en onafhankelijk van elkaar in de gaten houden.
- **Relevantie**: Bij het openen van een trade zoeken we in het geheugen naar het level dat zich op dát moment precies op de prijs bevindt, exact `tests == 2` aan het doen is, en (bijvoorbeeld) in Discount of Premium zit.

Dit maakt de theorie "Stateless" voor de main loop en elimineert bugs waarbij oude levels per ongeluk nieuwe logica in de war schoppen.

---

## 6. Reference Code Implementation (Waterdichte Logica)

Om 100% uit te sluiten dat er interpretatieverschillen ontstaan tussen Pine Script, Backtest en de Live Bot, is hier de exacte Python implementatie die over elke nieuwe candle iteratie (tick of close) moet draaien.

```python
# State dictionary per level:
# {
#   'price': float, 
#   'dir': 1 (Resistance) of -1 (Support), 
#   'tests': int, 
#   'can_be_tested': bool, 
#   'creation_idx': int, 
#   'is_dead': bool
# }

def update_origin_levels(c, bar_index, levels):
    """
    c: huidige candle dict met 'high', 'low', 'close', 'open'
    bar_index: integer counter van de huidige candle
    levels: list met actieve dictionaries
    """
    for lvl in levels:
        if lvl['is_dead']: 
            continue
        
        hit_occurred = False
        
        if lvl['dir'] == 1:  # Resistance (Bearish Break Level)
            # 1. Hard Close Invalidation Check
            if c['close'] > lvl['price']:
                lvl['is_dead'] = True
            else:
                # 2. Hit Check (mag pas ná de creatie-bar)
                if bar_index > lvl['creation_idx'] and lvl['can_be_tested'] and c['high'] >= lvl['price']:
                    hit_occurred = True
                
                # 3. Update Separatie Luchtbel (voor de VOLGENDE hit check)
                if c['high'] < lvl['price']:
                    lvl['can_be_tested'] = True
                else:
                    lvl['can_be_tested'] = False
                    
        else:  # Support (Bullish Break Level)
            # 1. Hard Close Invalidation Check
            if c['close'] < lvl['price']:
                lvl['is_dead'] = True
            else:
                # 2. Hit Check
                if bar_index > lvl['creation_idx'] and lvl['can_be_tested'] and c['low'] <= lvl['price']:
                    hit_occurred = True
                
                # 3. Update Separatie Luchtbel
                if c['low'] > lvl['price']:
                    lvl['can_be_tested'] = True
                else:
                    lvl['can_be_tested'] = False
                    
        # 4. Verwerk de Test en Promotie
        if hit_occurred:
            lvl['tests'] += 1
            
            # TRADE TRIGGER LOGICA:
            if lvl['tests'] == 2:
                # Hier promoveert hij naar Origin Level!
                # Vuur eventuele live orders af (als Premium/Discount filters ook matchen).
                pass
```

---

## 7. Validatie & Backtest Resultaten (De Look-Ahead Reality Check)

*Laatste Validatie Run: Live Engine Simulator (BacktestSimulator) over NQ dataset (Jan 2026 - Mei 2026).*

Tijdens de definitieve tests zijn eerdere abstracte experimenten verworpen vanwege **Intrabar Look-Ahead Bias**. Abstracte testen gaven ten onrechte positieve resultaten doordat stop-losses op intrabar wicks werden genegeerd. De enige bron van waarheid is de `BacktestSimulator`.

### De Strikte Base Structure (Reverted)
We hebben tijdelijk geëxperimenteerd met een "lossere" definitie voor Break Levels (waarbij alleen een *lower high* op candle 3 werd geëist zonder kleur-restrictie). Echter, de volatiliteit bleek hierdoor te hoog. We zijn daarom succesvol **teruggezet naar de originele strikte 3-candle color block logica**:
- **Bearish Resistance:** Groen (Hold) -> Rood (1) -> Rood (2).
- **Bullish Support:** Rood (Hold) -> Groen (1) -> Groen (2).

Deze strakkere structuur garandeert dat we te maken hebben met een werkelijke momentum omkeer voordat een Origin Level mag worden aangemaakt.

### De Gecorrigeerde Realiteit (NQ 1min data, 120 dagen, Strict Logic)
Bij het "blind" traden van wicks op deze strikte 3-candle blokken met een 1:1.5 Risk/Reward (SL 8, TP 12), zien we de volgende snoeiharde werkelijkheid:
- **Totaal Trades:** 4064
- **Win Rate:** 39.8%
- **Totaal Net PnL (1 NQ contract):** -$3.840
- **Max Drawdown:** $14.880

### Conclusie
Hoewel het strikte 3-candle blok duizenden zwakke wicks eruit filtert en het verlies drastisch beperkt ten opzichte van de "lossere" variant, is de theorie nog steeds licht verliesgevend in een pure limiet-order uitvoering. 
**Volgende logische stappen voor deze strategie vereisen Price Action Confirmatie:** We kunnen niet blind wachten tot een wick geraakt wordt. Net als bij de Golden Setup zal deze strategie uitgebreid moeten worden met ofwel de *Rejection Confirmatie* (wachten op een close en dan pas traden), of een zware *Killzone / Trend alignment filter*.
