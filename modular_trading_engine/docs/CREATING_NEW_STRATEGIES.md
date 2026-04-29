# Creating New Strategies

De strakke architectuur van de `FleetCommander` stelt je in staat om een nieuwe theorie of setup aan de codebase toe te voegen, zónder de back-end live bot the vernachelen.
Alles omtrent een handelsstrategie is namelijk **'Containerized'**. Eén mapje beheert álles voor die bot-instance.

Deze tutorial neemt je binnen 3 minuten mee in het klonen en lanceren van een gloednieuwe handelsstrategie.

---

## Stap 1: Dupliceer een Base Container
Klonen is de veiligste manier om the starten. We gebruiken een bestaande container (bijvoorbeeld je template strategie) als solide fundering. 

1. Navigeer in je Bestandsbeheer / IDE naar `modular_trading_engine/strategies/`.
2. Kopieer de map van een bestaande strategie en plak deze onder een nieuwe naam. Bijvoorbeeld:
   `strategies/nq_session_sweep/`

---

## Stap 2: Definieer de Regels (`strategy_playbook.json`)
Open in je nieuwe map het `strategy_playbook.json` bestand. Hierin geef jij de nieuwe theorie vorm.

* Wijzig de `"id"` en `"description"` zodat deze correct reflecteren in je logboek.
* Bepaal de trigger module. Wil je ditmaal meer of minder filteren op de Bias? (bijv. `bias_window_size` veranderen in de instellingen).
* Bepaal de Risk-Reward executie (`RATLimitOrder`). Een kleine scalp sessie? Zet je absolute Stop Loss (`absolute_sl_points`) op `10.0` en Take profit op `10.0`. Frontruns zet je onder `entry_frontrun_ticks`.

*Voorbeeld:*
```json
{
  "strategy_id": "NQ-Session-Sweep-Setup",
  "pipeline": [
    {
      "module_type": "ConfirmationHoldLevelTrigger",
      "params": {
        "bias_window_size": 200
      }
    },
    {
      "module_type": "RATLimitOrder",
      "params": {
        "tick_size": 0.25,
        "entry_frontrun_ticks": 6,
        "absolute_sl_points": 10.0,
        "absolute_tp_points": 10.0
      }
    }
  ]
}
```

---

## Stap 3: Beheer je Accounts (`execution_config.json`)
Je wilt wellicht de zware en bewezen baseline strategie op je `Hoofd Account` laten lopen, en deze experimentele agressieve strategie op je `Test Account`.

Open de `execution_config.json` binnen je nieuwe map.
Zorg dat je `accounts` correct zijn ingesteld. Bepaal via `"is_active": true / false` of deze specifieke strategie naar dít account mag verbinden.

> Let héél goed op dat `"strategies": ["NQ-Session-Sweep-Setup"]` een letterlijke match is met het `id` veld dat je zojuist in STAP 2 hebt aangemaakt! Dit is het slot van de kluisdeur.

---

## Stap 4: Vuur de Fleet Commander af!
Je bent klaar. Er was géén line Python-code nodig om dit te bouwen.
Lanceer de Live Bot als volgt via in de terminal:

```bash
cd modular_trading_engine
PYTHONPATH=. ./venv/bin/python3 src/layer4_execution/live_fleet_commander.py --strategy nq_session_sweep
```

*(Merk op dat je `--strategy {naam_van_de_map}` in geeft! De engine nestelt zich vervolgens zelf in dít mapje om de configuraties op the slokken).*

💡 **Pro-Tip**: Je kunt nu zonder problemen twee terminalvensters naast elkaar draaien in je IDE. Eentje start de eerste base strategie, de andere start de NQ Session Sweep. De "Fleet" van Commanders handelt parallel aan elkaar, elk gedreven door zijn eigen strikt gescheiden theorie en account instellingen!

---

## Stap 5: Valideer met de Backtester (Aanbevolen)
Voordat je live gaat, draai je de strategie eerst door de offline simulator om de verwachte PnL en Win-Rate te valideren:

```bash
cd modular_trading_engine
python3 scripts/backtest/run_backtest.py --strategy nq_session_sweep --days 30
```

De backtester gebruikt exact dezelfde Layer 2 & 3 logica als de Live Bot — alleen Layer 4 (de broker) wordt vervangen door een lokale fast-forward simulator. Zie [BACKTEST_ARCHITECTURE.md](BACKTEST_ARCHITECTURE.md) voor de volledige documentatie.

> **Regel:** Experimenteer nooit blind met productie-accounts. Valideer eerst offline, draai eventueel tick-data replay voor nauwkeurigheid, en ga pas live wanneer de cijfers kloppen.
