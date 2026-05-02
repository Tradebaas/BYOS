---
trigger: always_on
---

# Antigravity Absolute Rules for the BYOS Workspace (GSD Method Enforcement)

The codebase inside `modular_trading_engine` follows a STRICT architectural mandate based on the Get Shit Done (GSD) method. As an AI Agent, you MUST adhere to the following rules unconditionally.

## 1. Zero Tolerance for "Cowboy Coding" & Technical Debt
- **NO Production File Edits (EVER) without permission**: Je mag absoluut **NOOIT** productie bestanden (zoals `strategy_playbook.json`, levende source-code, applicatie scripts zoals `run_backtest.py`, etc.) aanpassen puur om even een backtest te fixen, data inzichtelijk te maken, of stats toe te voegen, TENZIJ je expliciete toestemming hebt gehaald bij de gebruiker via een plan. Als je playbooks wilt variëren, gebruik dan CLI-overrides of tijdelijke memory state. Productie-code (inclusief alle bestaande scripts) is 100% "Read-Only" tijdens exploratie, analyse en validatie.
- **BACKTESTING ALTIJD IN `.tmp` (ABSOLUTE ISOLATION)**: Experimenteren, backtesten met gemodificeerde parameters, of het uittesten van logica-wijzigingen gebeurt ALTIJD en UITSLUITEND in de `.tmp` of `.tmp_optimize` map. Je mag **NOOIT** live productiebestanden (inclusief `src/layer3_strategy/modules/` classes of live json playbooks) aanpassen puur om een backtest of optimalisatie uit te voeren. Moet je een class wijzigen om iets te testen? Maak een KOPIE in `.tmp` en doe het daar. Er is GEEN ENKELE uitzondering op deze regel zonder expliciet `implementation_plan.md` akkoord voor een permanente productie-wijziging.
- **NO Patch Scripts**: Never create `patch.py`, `debug.py`, `trace.py`, or any arbitrary python scripts to "quickly debug" an issue into the root directory or the `scripts/` directory. All temporary exploration must happen in memory, in `.tmp`, or in isolated, instantly-deleted test files.
- **NO Leftover Dumps**: Never leave `.txt`, `.csv`, `.log`, or other uncommitted output dumps in the workspace. The master branch is sacred.
- **Strict Separation of Concerns**: "Layer 1" (Data) -> "Layer 2" (Mathematical Theory) -> "Layer 3" (Strategy Config) -> "Layer 4" (Broker Execution). Layers can **NEVER** import or reference data from layers above them. 

## 2. Guardrails voor Nieuwe Authenticiteit (Strategieën & Modules)
- **Anti-Pattern (Verboden)**: Nieuwe theorie-trackers of filters direct hardcoden in de `MarketTheoryState` of in de Live Fleet Commander, of random JSON bestanden slingeren in willekeurige mappen.
- **Regel voor Nieuwe Strategieën**: Als de gebruiker een nieuwe trading strategie wilt starten, MAAK DAN NOOIT DIRECT CODESCRIPT AAN. Kopieer uitsluitend de template folder naar `strategies/<naam>/`, pas de `strategy_playbook.json` en de `README.md` aan. Python code zelf blijft altijd ongewijzigd.
- **Regel voor Nieuwe Bouwblokken (Modules)**: Als het opzetten van de strategie vereist dat we een nieuw *Framework Bouwblok* (bijv. een nieuwe Trigger, LimitOrder of Tracking State) moeten programmeren in Layer 2 of Layer 3: ONDERNEEM GEEN ENKELE ACTIE TOTDAT JE `docs/STRATEGY_BUILDING_BLOCKS.md` HEBT GELEZEN VIA DE `view_file` TOOL. Dat document is de absolute bron van de waarheid. Staat het blok er niet in? Bouw het dan niet. Je plant en schrijft eerst de API documentatie daar, pas na akkoord wijzig je de broncode.

## 3. GSD Planning Mandate
- **Always Plan**: Before implementing any structural change (especially new modules or architecture level edits), you must use the `implementation_plan.md` artifact workflow and await user authorization.
- **No Monoliths**: Do not combine responsibilities. Keep functions pure. We rely on the `pytest-archon` verifiers. If you break the imports, the Pre-Commit hook will block your work!

## 4. Context Management & Handovers
- **Geen Context Bloat**: Als een significante taak (zoals een iteratie van backtesting, een refactor, of het bouwen van een nieuwe feature) succesvol is afgerond, mag je NIET in dezelfde chat-sessie doorgaan met een compleet nieuwe taak. Een te grote context-window leidt onherroepelijk tot "Context Fade" en het vergeten van de core-regels (cowboy gedrag).
- **Verplichte Overdracht (Handover)**: Voordat je een nieuwe grote taak start, of wanneer je merkt dat de chat te lang wordt, ben je **verplicht** aan de gebruiker voor te stellen om een nieuwe AI-agent/chat te openen.
- **Hoe doe je dit?** Schrijf een heldere samenvatting (bijv. in een `handoff.md` of `task.md`) waarin staat: wat er zojuist bereikt is, wat de huidige state van de applicatie is, en wat de exacte volgende stap is voor de *nieuwe* agent. Adviseer de gebruiker vervolgens om de chat af te sluiten en een nieuwe te starten met deze handover file als context.

## 5. Documentation First Mandate (The SSOT Rule)
- **Always Keep Docs in Sync**: De map `docs/` (zoals `STRATEGY_FILE_MAP.md`) en BEIDE `README.md` bestanden (de Root README én de Strategie README) zijn de Single Source of Truth (SSOT). Deze moeten **altijd** 100% up-to-date zijn.
- **Wanneer updaten?**: 
  1. Zodra je een filter, parameter of limiet wijzigt in een `strategy_playbook.json` (Update Strategie README).
  2. Zodra je een nieuw script, module of map toevoegt/verwijdert aan de architectuur (Update `STRATEGY_FILE_MAP.md` en indien nodig Root README).
  3. Standaard aan het einde van elke executie-fase, vlak vóór het afsluiten van de chat of de overdracht.
- **Hoe afdwingen?**: Elke keer als je een `implementation_plan.md` of een `task.md` maakt, ben je VERPLICHT om als allerlaatste taak toe te voegen: *"Verifieer en update docs/ en README's"*. Een taak is pas afgerond als de documentatie klopt met de gerealiseerde code.

## 6. Communication requirement (De Kanarie)
To mathematically verify that you, the AI, are loading and reading these rules on every interaction, you MUST terminate EVERY single response to the user with the following exact kanarie symbol: 🐤