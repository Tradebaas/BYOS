import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.rule_engine import RuleEngine

candles = load_historical_1m_data('data/historical/NQ_1min.csv')
theory_state = MarketTheoryState()
playbook_config = ConfigParser.load_playbook("data/playbooks/day_trading_decrypted.json")
rule_engine = RuleEngine(playbook_config)

print("Starting trace...")
for i, c in enumerate(candles):
    theory_state.process_candle(c)
    # Check between 17:20 and 18:10 UTC
    if '17:20' <= c.timestamp.strftime('%H:%M') <= '18:15' and c.timestamp.strftime('%Y-%m-%d') == '2026-04-13':
        intents = rule_engine.evaluate(theory_state, c.timestamp)
        if intents:
            print(f"[{c.timestamp}] Intent emitted: {intents[-1].entry_price}")
print("Trace complete.")
