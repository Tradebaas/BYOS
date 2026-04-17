import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer3_strategy.pipeline_context import PipelineContext

candles = load_historical_1m_data('data/historical/NQ_1min.csv')
theory_state = MarketTheoryState()
playbook_config = ConfigParser.load_playbook("data/playbooks/day_trading_decrypted.json")
rule_engine = RuleEngine(playbook_config)

print("Searching for evaluated intents since yesterday evening...")
for i, c in enumerate(candles):
    theory_state.process_candle(c)
    # Check since 18:50 UTC (20:50 local timestamp)
    if c.timestamp.strftime('%Y-%m-%d %H:%M') >= '2026-04-13 18:50':
        intents = rule_engine.evaluate(theory_state, c.timestamp)
        if intents:
            for intent in intents:
                print(f"[{c.timestamp}] Detected Setup! Direction: {'LONG' if intent.is_bullish else 'SHORT'} at {intent.entry_price} (SL: {intent.stop_loss}, TP: {intent.take_profit})")
print("Check complete.")
