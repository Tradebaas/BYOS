# Engineering & Coding Standards Blueprint

Om te garanderen dat dit modulaire trading framework nooit vervalt in "Spaghetti Code" of "Tech Debt" — vooral wanneer het wordt doorontwikkeld door of in samenwerking met AI-modellen — hanteren we absolute, onbreekbare codestandaarden. 

AI-developers (LLMs) raken snel in de war bij bestanden van 500+ regels met verweven afhankelijkheden (God Classes/Spaghetti). Dit project elimineert dat risico vanaf dag één door een meedogenloze naleving van *Separation of Concerns* en *Clean Code* principes af te dwingen.

---

## 1. File & Function Limits (De Core AI-Protectie Regels)

Grote bestanden leiden direct tot model-hallucinaties en onbedoelde neveneffecten bij kleine revisies. Deze regels vangen dat af.
1.  **Max Lijnen per Bestand (150 Regels):** Een bestand in Laag 2 of Laag 3 (Theorie & Strategy) mag **absoluut niet groter zijn dan 100 tot maximaal 150 regels**. Zodra een module dreigt te groeien, betekent dit dat we principes overlappen en móét de file logisch opgesplitst worden (bijv. in sub-modules). De API/Orchestrator in Laag 4 kan complexer zijn, maar wordt evengoed opgesplitst (routers, state managers apart).
2.  **Max Lijnen per Functie (30 Regels):** Een individuele theorie-functie (zoals de controles in `hard_close.py` of `origin_locator.py`) is maximaal **30 tot 40 regels** lang. 
3.  **Flat Hierarchy & Compositie:** Vermijd gigantische OOP Class Inheritance bomen (`class StrategyBase -> class CCTA -> class ActiveRunner` etc). Dit verbreekt transparantie. We gebruiken in plaats daarvan functionele datatransformaties (Data Input > Pure Functions > Data Output) en geïsoleerde componenten. 

## 2. Stateless Core Modules (Laag 2 Isolatie)

Elke wiskundige bouwsteen uit Laag 2 (die de definities handhaaft) kent uitsluitend Pure Wiskunde.
1.  **Immutability:** OHLCV-data en theoriestaten stromen deze datalaag in. Ze muteren *nooit* de input arrays direct. Ze retourneren uitsluitend nieuwe, heldere states (bijv. `{is_hard_close: True, level_invalidated: True}`).
2.  **Volledig Geïsoleerd:** Een `hold_level.py` module praat nooit met de database, bevat nul broker-logica, kent geen PnL en print geen logging anders dan lokale developer-debug traces. Dit is puur een wiskundige lens op ruwe data.

## 3. Configuration & Variabelen (Laag 3 Playbooks)

Een wilde groei aan "hardcoded" wiskundige constanten is funest voor backtesting of AI-optimalisatie.
1.  **Zero Hardcoding:** Strategische variabelen — zoals `max_origin_tests`, `sl_distance_ticks`, of Timeframes — worden NOOIT keihard halverwege een `.py` file gedefinieerd. 
2.  **Centralised Data Source:** Alles wat de strategie definieert is volledig afhankelijk van het JSON Playbook (gedefinieerd in `STRATEGY_SCHEMA_BLUEPRINT.md`). De module is slechts de "uitvoerder" van deze JSON.
3.  **Strict Type Hinting:** Python's Type Hinting (`-> dict`, `: int`) en sterke validatie via bijv. `Pydantic` worden verplicht gebruikt. Als het playbook "1 test" vraagt (Integer), crasht de app netjes tijdens de configuratie-loading fase als daar per ongeluk een String staat, in plaats van live in een trade de code op te hangen.

## 4. De AI Committment Regel

Om technische schuld via AI-iteraties te voorkomen, geldt bij elke prompt:
1. **Targeted Surgery:** Herschrijf NOOIT een volledig bestand als slechts een detail van wiskunde (zoals de `lowest untested red candle` parameter) aangepast dient te worden. De module is minuscuul; hou de operatie chirurgisch.
2. **Begrijp de Interfacelaag:** Begrijp dat de Output van Laag 2 de Input is van Laag 3. Verander nooit de return types (bijv. van een Dictionary naar een Float) zonder dat de gehele keten dit accepteert.

## 5. Testvereisten & Verification

Bij de vertaalslag naar code worden de abstracte wiskundes altijd als eerste getest in Laag 2, middels MOCKS (nep grafieken/candle data). Zo kunnen we bij voorbaat testen of `Origin Level` daadwerkelijk genegeerd (vergeten) wordt nadat `Hard Close` doorbroken werd in de gesimuleerde candle set vóórdat de execute chain gebouwd is.
