# Backtest Mandate

## Mandatory Architecture Review
Voorafgaand aan het schrijven, bewerken of uitvoeren van een backtest-script, ben je **verplicht** om het document `modular_trading_engine/docs/BACKTEST_ARCHITECTURE.md` te lezen via de `view_file` tool. 

Dit is essentieel om de architecturale eisen, zoals het vermijden van **Lookahead Bias** en het correct toepassen van de **Synthetic Remainder Candle**, vers in het geheugen te hebben. 

## No Lookahead Bias (The Golden Rule)
- Je mag in backtests **nooit** data van de zojuist gesloten signaal-candle gebruiken om een limit-order binnen diezelfde candle te vullen.
- Executie is uitsluitend toegestaan op **volgende** candles.
- Deze regel is heilig voor 1:1 parity met de live TopstepX engine.

## ABSOLUTE ISOLATION (No Prod Modifications)
- **NOOIT PRODUCTIE CODE AANPASSEN:** Je mag tijdens het opzetten, fixen of runnen van backtests *NOOIT* productiebestanden wijzigen (inclusief `src/`, root-level scripts, of actieve playbooks).
- **ALLES IN `.tmp`:** Backtest-experimenten, tijdelijke scripts (`patch.py`, `tune.py`), en gemodificeerde strategieën of logica moeten UITSLUITEND in de `.tmp` (of `.tmp_optimize`) map worden geplaatst en uitgevoerd. 
- **Waarom?** Om de integriteit van de master codebase (waar de live bot afhankelijk van is) 100% te garanderen. Als je een bestaande class moet aanpassen voor een test, maak je een kopie in `.tmp` en test je het daar.
- Deze regel heeft **geen uitzonderingen**, tenzij de gebruiker expliciet akkoord geeft via een `implementation_plan.md` om een permanente verandering in de codebase door te voeren.
