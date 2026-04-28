import json
from src.layer4_execution.data_vault import TradeRecord
from run_baseline_backtest import load_candles, run_be_backtest

# We need to hack run_be_backtest to return vault.trades instead of just printing
import run_baseline_backtest
import types

def new_run():
    candles = run_baseline_backtest.load_candles()
    import json
    with open("strategies/dtd_golden_setup/strategy_playbook.json", "r") as f:
        config = json.load(f)

    from src.layer2_theory.market_state import MarketTheoryState
    from src.layer3_strategy.playbook_schema import PlaybookConfig
    from src.layer3_strategy.rule_engine import RuleEngine
    from src.layer4_execution.simulator import BacktestSimulator
    from src.layer4_execution.data_vault import DataVault

    state = MarketTheoryState()
    cfg = PlaybookConfig(**config)
    engine = RuleEngine(cfg)
    vault = DataVault()
    simulator = BacktestSimulator(vault)

    for c in candles:
        state.process_candle(c)
        intents = engine.evaluate(state, c.timestamp)
        for intent in intents:
            simulator.stage_order(intent)
        simulator.process_candle(c)

    with open('.tmp_optimize/baseline_trades.json', 'w') as f:
        json.dump([t.model_dump(mode='json') for t in vault.trades], f, indent=2)

new_run()
