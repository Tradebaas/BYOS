# DTD Golden Setup Strategy

Deze map fungeert als een geïsoleerde "Strategy Container" voor de **Day Trading Decrypted (DTD) Topstep Golden Setup**.

### ⚙️ Container Eigenschappen
Deze specifieke strategie is afgesteld op The Golden Setup markttheorie. Het algoritme speurt naar "Confirmation Hold Level" formaties over de laatste 200 minuten en vuurt uitsluitend limiet-orders af als we ons in een sterke Premium/Discount zone begeven.

### 📐 Huidige Wiskunde (uit JSON playbooks)
* **Markt:** `/NQ`
* **Frontrun:** `4 Ticks` (Exact 1 vol punt frontrun ten opzichte van het Hold Level. Op de achtergrond exclusief afgehandeld door de RATLimitOrder pipeline om dubbele frontruns te voorkomen).
* **Stop Loss (SL):** `64 Ticks` (16 Punten)
* **Take Profit (TP):** `80 Ticks` (20 Punten)
* **Break-Even Logic:** Automatisch BE uitschakeld in de Live Fleet Commander momenteel.
* **Volume Filter:** Setup wordt pas geldig bevonden als er > 0 markttractie is rond de pool.

### 🚀 Hoe te draaien?
De `LiveFleetCommander` laadt deze strategie tegenwoordig **standaard** in als je hem start zonder opgave.

Om hem handmatig af te dwingen of in combinatie met een andere strategie te draaien:
```bash
PYTHONPATH=. ./venv/bin/python3 src/layer4_execution/live_fleet_commander.py --strategy dtd_golden_setup
```

*(Zorg dat je `execution_config.json` is voorzien van een geldig `account_id` voordat je de bot ontgrendelt)*.
