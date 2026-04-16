# Phase 5: Live Execution & TopStep Golden Ratio Integration

## Beschrijving
Deze fase koppelt de succesvol geteste "Golden Ratio" executie (SL 10, TP1 5, TP2 40, Break-Even op TP1) aan de live broker omgeving via TopstepX Native Brackets. Deze fase waarborgt dat de theorie uit `zebas_core.py` (de 1-op-1 backtest logica) puur blijft, en legt alle complexe account monitoring in één betrouwbare orchestrator laag die robuust is tegen onderbrekingen (bijv. een MacBook die slaapt en ontwaakt).

## Requirements / Doelstellingen
- **Golden Ratio Signalering:** Bestaande theorie blijft intact, `SetupSignal` object stuurt 4 limit orders uit (of instelbare splits) richting TopStep ter grootte van in totaal 4 NQ. 
- **Persistente Achtergrond Service:** De live trader moet een oneindige loop zijn (`while True`) die constant pollt naar theorie-wijzigingen en broker-state via REST/WS. Zodra de applicatie start of ontwaakt (bijv. na sleep mode), moet hij blindelings zijn werkelijke posities pullen uit de TopStep API om de interne state direct correct te synchroniseren.
- **Multi-Account Beheer:** Een configuratie mechanisme (`.env` of `config.json`) waarbij we verschillende TopStep Prop Firm accounts inlezen, aangeven welke strategie ze draaien, én een harde beveiliging integreren: maximaal **1** actieve open positie per account.
- **Topstep Native Break-Even:** We gebruiken geen losse theorie stop-losses in de broker, maar plaatsen bij entry 2 orders, en we schuiven Order 2's StopLoss Native Bracket via de API omhoog naar Entry zodra Order 1 gesloten is met winst.

## GSD Architectuur Plan

### Stap 1: Core Payload Refactor
We passen het `SetupSignal` object (in bijv. `zebas_core.py` en Layer 3) aan, zodat het niet alleen "Entry en TP" stuurt, maar expliciet de gesplitste executie payload (bepaald in de Golden Ratio test) meestuurt naar de orchestrator. De theorie-logica verandert **niet**.

### Stap 2: Configuratie Matrix Opzetten
We creëren een `execution_config.json` binnen `modular_trading_engine/.env`'s invloedssfeer. Hierin staan de accounts:
```json
{
  "accounts": [
    {
      "account_id": "P012345",
      "strategy_profile": "ZEBAS_GOLDEN_4NQ",
      "max_positions": 1,
      "enabled": true
    }
  ]
}
```

### Stap 3: De Live Orchestrator Bouwen (`live_fleet_commander.py`)
We bouwen de service class `TopstepOrchestrator` in `modular_trading_engine/src/execution/`:
- In de `__init__` trekt hij de ongewijzigde `ProjectX` API wrapper erin en laadt hij unieke class instances per *enabled* account.
- In een continue `async` loop, trekt hij 1x per minuut of seconde (afhankelijk van candle data update in MTE) de theoretische state op vanuit Layer 2.
- State-recovery: roept direct `api.get_positions()` aan op start-up en bij fouten. Bevat je 0 posities? Zoek naar entries. 
- Entry Executie: Als het Entry level wordt geraakt en account-posities is `0`, stuurt GSD 2 gelijktijdige API-verzoeken (`place_limit_order` API call) mèt native takeProfit en stopLoss brackets.
- Break-Even Scanner: Loop scant continu openstaande posities en ordermodificatie API calls indien TP1 wegvalt en TP2 als "Runner" blijft leven.

### Stap 4: Unittest & Parity Controle
We draaien een schaduwtest om offline (dry-run) dit orchestrator mechanisme te valideren om te zien of hij niet 2 nullen teveel invult bij quantiteiten, of het verkeerde account kiest. Focus op theorie validatie: The backtest simulator matcht 1:1 met deze live trader logica met 4 NQ (+12.800 PNL bij Max -$800 DD resultaat over laatste 4wkn).
