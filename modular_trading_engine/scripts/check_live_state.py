import os
import sys

os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.getcwd())

from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
from modular_trading_engine.src.layer2_theory.market_state import MarketTheoryState
from modular_trading_engine.src.layer3_strategy.config_parser import ConfigParser
from modular_trading_engine.src.layer3_strategy.rule_engine import RuleEngine

print("Loading latest data...")
candles = load_historical_1m_data('modular_trading_engine/data/historical/NQ_1min.csv')

theory_state = MarketTheoryState()
playbook_config = ConfigParser.load_playbook("modular_trading_engine/data/playbooks/day_trading_decrypted.json")
rule_engine = RuleEngine(playbook_config)

recent_candles = candles[-500:]
for c in recent_candles:
    theory_state.process_candle(c)

print(f"\n--- STATE AT {recent_candles[-1].timestamp} ---")
print(f"Current Price: {recent_candles[-1].close}")

active_origin = theory_state.active_origin
if active_origin:
    print(f"\nACTIVE ORIGIN CANDIDATE: Type={active_origin.type}, Target/Hold={active_origin.hold_line_open}")
    print(f"  > Confirmed: {active_origin.is_confirmed}")
    print(f"  > Tests so far: {active_origin.test_count}")
    print(f"  > Invalidated: {active_origin.is_invalidated}")
else:
    print("\nNo strictly active Origin Level being tracked.")

intents = rule_engine.evaluate(theory_state, recent_candles[-1].timestamp)
if intents:
    print("\nWE HAVE A SETUP!")
    for i in intents:
        dr = "LONG" if i.is_bullish else "SHORT"
        print(f"Intent -> {dr} | Limit @ {i.entry_price} | SL @ {i.stop_loss} | TP @ {i.take_profit}")
else:
    print("\nNo order intent generated yet (waiting for correct price touch or confirmation).")
