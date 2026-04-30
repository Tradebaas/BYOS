# BYOS DTD Golden Setup — Actieve Bestanden vs. Inactieve Bestanden

Dit document beschrijft exact welke bestanden de **DTD Golden Setup** strategie daadwerkelijk gebruikt tijdens live executie binnen het BYOS (TopstepX) ecosysteem, en welke bestanden je veilig kunt negeren of die puur voor monitoring/logging zijn.

---

## De Executie-Flow (TopstepX)

Wanneer een candle binnenkomt, is dit het exacte pad:

```
Candle binnenkomt (Realtime / Historical REST)
    │
    ▼
MarketTheoryState.process_candle()        ← Layer 2: detecteert Hold/Break Levels
    │
    ▼
RuleEngine.evaluate()                     ← Layer 3: past playbook pipeline toe
    │
    ├── ConfirmationHoldLevelTrigger       ← Sweep & Confirm: Test Blok → Executie Blok → Entry
    ├── KillzoneFilter                     ← Blokkeert trades buiten handelsuren
    ├── LossCooldownFilter                 ← Blokkeert trades na een verlies (bijv. 30 min cooldown)
    ├── TTLTimeout                         ← Cancelt setups o.b.v. level "houdbaarheidsdatum"
    └── RATLimitOrder                      ← Berekent entry, absolute SL & TP
    │
    ▼
OrderIntent                               ← Layer 3 output: "plaats LONG @ 21450, SL 21438, TP 21462"
    │
    ▼
TopstepClient.place_oso_order()           ← Layer 4: stuurt de native server-side OSO/OCO order naar TopstepX
```

---

## ✅ ACTIEVE BESTANDEN (Noodzakelijk)

### Layer 1 — Data
| Bestand | Rol |
|---|---|
| `src/layer1_data/models.py` | `Candle` Pydantic model — de universele data-eenheid |
| `src/layer1_data/csv_parser.py` | Leest historische CSV voor warm-up / backtests |
| `src/layer1_data/resampler.py` | Resamplet basiscandles naar hogere timeframes |

### Layer 2 — Theory (Wiskunde)
| Bestand | Rol |
|---|---|
| `src/layer2_theory/models.py` | Definiëert states (`TheoryLevel`, `LevelType`, etc.) |
| `src/layer2_theory/market_state.py` | **De kern-orchestrator**. Ontvangt candles en beheert theoriestaten |
| `src/layer2_theory/hold_level_detector.py` | Hold Level detectie (kandidaat + hard close validatie) |
| `src/layer2_theory/break_level_detector.py` | Break Level detectie |
| `src/layer2_theory/hard_close.py` | De fundamentele `is_hard_close()` logica |
| `src/layer2_theory/tested_state.py` | Logica voor het bepalen of levels 'getest' zijn |

### Layer 3 — Strategy
| Bestand | Rol |
|---|---|
| `src/layer3_strategy/models.py` | `OrderIntent` — de blauwdruk voor de executielaag |
| `src/layer3_strategy/config_parser.py` | Laadt en parsed JSON playbooks |
| `src/layer3_strategy/playbook_schema.py` | Validatie van JSON playbooks |
| `src/layer3_strategy/rule_engine.py` | Verwerkt data door de modules pijplijn |
| `src/layer3_strategy/pipeline_context.py` | Gedeelde state doorgegeven tussen modules |
| `src/layer3_strategy/modules/base.py` | Abstract Base Class voor alle modules |
| `src/layer3_strategy/modules/confirmation_hold_level_trigger.py` | **⭐ HET HART** — Sweep & Confirm trigger logica |
| `src/layer3_strategy/modules/killzone_filter.py` | Tijdfilters (blokkades op openingstijden) |
| `src/layer3_strategy/modules/loss_cooldown_filter.py` | Voorkomt revenge-trading met een afkoelperiode na SL |
| `src/layer3_strategy/modules/ttl_timeout.py` | Controleert de 'versheid' van het theorie-level |
| `src/layer3_strategy/modules/limit_order_execution.py` | Plaatst limieten (RATLimitOrder) rond theorie levels |

### Layer 4 — Execution (TopstepX)
| Bestand | Rol |
|---|---|
| `src/layer4_execution/live_fleet_commander.py` | Hoofd orchestrator, start de loop en beheert de status |
| `src/layer4_execution/auth.py` | Beheert Playwright/Headless login via Firebase/Cognito |
| `src/layer4_execution/topstep_client.py` | API Wrapper voor het ophalen van REST data en plaatsen van orders |
| `src/layer4_execution/topstep_realtime.py` | Beheert SignalR WebSocket verbinding voor realtime updates |
| `src/layer4_execution/models_broker.py` | Pydantic mapping van API responses |
| `src/layer4_execution/trade_ledger.py` | Logt afgeronde trades in CSV format |
| `src/layer4_execution/data_vault.py` | Cache-mechanisme voor account en instrument data |
| `src/layer4_execution/simulator.py` | Offline backtesting simulator |

### Config
| Bestand | Rol |
|---|---|
| `strategies/dtd_golden_setup/strategy_playbook.json` | De exacte pipeline en hyperparameters |
| `strategies/dtd_golden_setup/execution_config.json` | Live uitvoeringsinstellingen, Account IDs, Instrument ID |
| `data/backtest/candles/NQ_1min.csv` | De opgebouwde historical Data Lake voor backtesting en warmup |

---

## ⏸️ INACTIEVE BESTANDEN

### Layer 2
| Bestand | Reden |
|---|---|
| `src/layer2_theory/origin_state_machine.py` | Trackt Origin Levels. **Wordt NERGENS in Layer 3 gebruikt voor executie.** Uitsluitend aanwezig voor Heartbeat statistieken. |

---

## Waarom dit belangrijk is
Het isoleren van bestanden (vooral de `origin_state_machine`) voorkomt verwarring tijdens debugging. Als trades niet plaatsen zoals verwacht, hoef je uitsluitend te zoeken in Layer 3 modules, en kun je Origin trackers en inactieve concepten negeren.
