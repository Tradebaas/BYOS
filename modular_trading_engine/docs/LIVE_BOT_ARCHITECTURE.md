# Live Trading Bot Execution Architecture
*Documentatie over de kloppende hartkleppen van de "Fleet Commander" — de live terminal executie bot.*

Dit document dient als referentie over hoe de Python architectuur realtime marktlezen, strategie-berekening en broker-koppeling uitvoert, zónder ruis van oude web-dashboards of simulaties. Alles is modulair, geïsoleerd ("Containerized") en draait exclusief vanuit de terminal.

---

## 🚀 Layer 4: De "Aansturing" (Executie Machine)
*De fysieke connectie met de TopstepX backend en tijd-synchronisatie.*

1. **`src/layer4_execution/live_fleet_commander.py`**
   * **Rol: De Kapitein.** Het absolute hoofdkwartier. Opgestart via de terminal. Het script laadt eerst historische data uit CSV's in om theorie-structuren te ontdekken ('Warming up'), synct eventuele data-gaps via de REST API, waarna hij naadloos overvloeit in zijn "Live Loop". Het ophaalinterval van data gebruikt nu gerandomiseerde polling (bijv. basisinterval + `random.uniform(0.1, 0.7)`) om bot-detectie op ritmische patronen te vermijden. Elke iteratie leest hij theorie, berekent signalen via Layer 3 en plaatst/verplaatst fysieke orders.

2. **`src/layer4_execution/topstep_client.py` & `auth.py`**
   * **Rol: De Brug / De Tolk.** Vertaalt Python commando's (Intents) naar cryptische ProjectX REST API payloads. Gebruikt `curl_cffi` (impersonate="chrome120") in plaats van standaard requests voor TLS-fingerprint spoofing.
   * Lost automatische contract-rollovers op (leest op de achtergrond het meest courante symbol uit `/NQ`).
   * Zorgt dat `auth.py` onzichtbaar een Headless Browser start om de JWT sessie-tokens te intercepteren voor de broker, waarbij de invulsnelheid van velden via random pauzes is getweakt om menselijke typsnelheid na te bootsen.

3. **`src/layer4_execution/topstep_realtime.py`**
   * **Rol: De Tick Feed.** Verbindt via SignalR WebSocket met de TopstepX Market Hub voor real-time tick-data (trades + quotes).
   * Bevat `TopstepRealtimeClient` (de connection manager) en `TickBuffer` (ringbuffer voor de meest recente ticks).
   * Push-based stream: **geen rate-limit** op de WebSocket. De REST API kent wel een limiet van 50 req/30 sec voor historische data.

---

## ⚙️ Layer 3: Het Handelsbrein (Playbook Strategie)
*Het configuratiehart, volledig ingekapseld in Strategie-Containers.*

4. **`strategies/<strategy_naam>/strategy_playbook.json`**
   * **Rol: Het Receptenboek.** De kern van een modulaire container. Bevat geen code, maar bepaalt letterlijk welke Layer-3 modules, in welke volgorde, met welke specificaties (aantal ticks SL, frontruns, etc.) geactiveerd worden.
5. **`strategies/<strategy_naam>/execution_config.json`**
   * **Rol: Account Mapping.** Bepaalt op exact welk live account-ID op je broker of prop-firm (bijv. account nummer XYZ) de gedefinieerde playbooks mogen vuren.
6. **`src/layer3_strategy/rule_engine.py`**
   * **Rol: De Transportband.** Het mechanisme dat de bovengenoemde JSON "Containers" pakt, ze inleest in de dynamische Python parser en ze in een sequentiële Pipeline giet ter evaluatie.
7. **`src/layer3_strategy/modules/`** *(Alle losse sub-calculatie blokken)*
   * **Bevat modules zoals:** `confirmation_hold_level_trigger.py` en `limit_order_execution.py`.
   * Zie [STRATEGY_BUILDING_BLOCKS.md](STRATEGY_BUILDING_BLOCKS.md) voor de diepgaande technische calculaties van deze modules.

---

## 📚 Layer 1 & 2: Datacenter en Type Declaraties
*Passieve data-infrastructuur en rauwe theorie detectie.*

8. **`src/layer2_theory/market_state.py`**
   * **Rol: De Pijpleiding Data-Cache.** Deze module ontgint continu kaarsen (`history`) en onthoudt welke marktfases zojuist verstreken zijn (Premium of Discount iteraties) en slaat specifieke originpools op in `active_origins`.
9. **`src/layer1_data/` Models & Parsers**
   * **Rol: Enveloppen (Dataclasses).** Definieert dat abstracties zoals een `Candle` steevast de attributen `timestamp, o, h, l, c, vol` bevatten. Dit dwingt blind datatransport af tussen alle lagen, zonder dictionary chaos.
   * Bevat de robuuste `csv_parser.py` voor het inladen van pre-bestaande database records om de bot mee op te warmen voordat de Live Loop overneemt.

---

## 🛠️ Live Utilities

Live hulpscripts staan geïsoleerd in `scripts/live/`:

| Script | Doel |
|---|---|
| `scripts/live/get_topstep_accounts.py` | Haal JWT op en toon beschikbare TopstepX accounts |

De Live Bot zelf wordt gestart via de georkestreerde script runner in `scripts/live/`.

```bash
# Start de Live Bot:
cd modular_trading_engine
PYTHONPATH=. venv/bin/python scripts/live/run_live_bot.py

# Check accounts:
PYTHONPATH=. venv/bin/python scripts/live/get_topstep_accounts.py
```

> **Zie ook:** [BACKTEST_ARCHITECTURE.md](BACKTEST_ARCHITECTURE.md) voor de offline backtest-tegenhanger van deze Live Bot.

---

*Laatst bijgewerkt: 28 april 2026 — Toevoeging stealth features (curl_cffi, human-typing, random-polling) & correctie startup script.*
