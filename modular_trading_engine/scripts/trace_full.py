import sys
import os
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.getcwd())

from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
from modular_trading_engine.src.layer2_theory.market_state import MarketTheoryState
from modular_trading_engine.src.layer3_strategy.config_parser import ConfigParser
from modular_trading_engine.src.layer3_strategy.rule_engine import RuleEngine

candles = load_historical_1m_data('modular_trading_engine/data/historical/NQ_1min.csv')
theory_state = MarketTheoryState()
playbook_config = ConfigParser.load_playbook("modular_trading_engine/data/playbooks/day_trading_decrypted.json")
rule_engine = RuleEngine(playbook_config)

for i, c in enumerate(candles):
    if c.timestamp.strftime('%Y-%m-%d') < '2026-04-10':
        continue # skip old
    theory_state.process_candle(c)
    if c.timestamp.strftime('%Y-%m-%d %H') >= '2026-04-13 16':
        intents = rule_engine.evaluate(theory_state, c.timestamp)
        if intents:
            for it in intents:
                print(f"{c.timestamp} -> INTENT: {it.entry_price}")
