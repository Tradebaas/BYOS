# BYOS - Build Your Own System (Topstep Edition)

Welkom in het `BYOS` (Build Your Own System) project. Dit is het definitieve, stand-alone back-end framework voor het geautomatiseerd handelen van derivaten (NQ E-mini) via de TopstepX infrastructuur.

De software is ontworpen als een meedogenloze 'silent executor', gedreven door de GSD-methodiek (Get Shit Done). Geen toeters, geen bellen, alleen 100% stabiele, asynchrone node-naar-node PnL generatie.

## 🏗 Architectuur Overzicht

Het systeem is verdeeld in 4 strikt gescheiden lagen (Layers) in de `modular_trading_engine/` folder:

1. **Layer 1 (Data):** Verbindt asynchroon met de broker websockets en onderhoudt lokale, historische tick-archieven. Single Source of Truth voor prijsactie.
2. **Layer 2 (Theorie):** De Wiskunde-afdeling. Geen meningen, alleen rekensommen. Construeert en volgt concepten zoals Range-Boxes, Local Tops/Bottoms, en abstracte Hold Levels.
3. **Layer 3 (Strategie):** Het Inlichtingenbureau. Pakt theorieën, filtert ze genadeloos via JSON "Strategy Playbooks", berekent Premium/Discount zones en definieert harde instap-acties, met stricte Risk/Reward targets.
4. **Layer 4 (Executie):** De "Fleet Commander". Het uitsluitend operationele brein. Plaatst Limit/Stop braket-orders op TopstepX, respecteert platform lock-outs (zoals killzones), en beheert account-limieten en PnL doelen.

## 🚀 De GSD Architectuur Filosofie

*   **Puur Modulair:** Layers mogen NOOIT informatie "omhoog" lekken of imports kruisen. Data (Laag 1) weet niets over Strategie (Laag 3). Executie (Laag 4) kent de theorie (Laag 2) alleen via signalen.
*   **Geen "Cowboy Coding":** Er zijn geen patch-scripts, geen losse `run.py` wild-west taferelen in de root. Wil je wiskunde testen? Gebruik ge-isoleerde files of PyTest. 
*   **Strict JSON Configuration:** Strategieën worden uitsluitend beheerd en geconfigureerd vanuit JSON Playbooks en de lokale omgeving (geen hardcoded parameters in de engine classes).
*   **TopstepX First:** Volledig ingeregeld voor de idiosyncratische ProjectX / Topstep Web API calls via headless/JWT authorisatie en strikte (server-side) OCO bracket implementaties.

## 🛠️ Snel Starten

1. Installeer afhankelijkheden in je virtual environment (zie root requirements).
2. Navigeer naar `modular_trading_engine/`. 
3. Raadpleeg `docs/LIVE_BOT_ARCHITECTURE.md` voor de commando referentie.
4. Activeer je virtuele omgeving en lanceer het schip via layer4 `live_fleet_commander.py`.

---

> *"This engine builds discipline, mathematically enforcing what human psychology inevitably fails to respect."*
