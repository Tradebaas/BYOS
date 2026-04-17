import os
import sys

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

# Find the exact index for 16:29:00 UTC
target_index = -1
for i, c in enumerate(candles):
    if c.timestamp.strftime('%Y-%m-%d %H:%M:%S') == '2026-04-13 16:29:00':
        target_index = i
        break

if target_index != -1:
    print(f"Target found at index {target_index}")
    # Process up to 16:29
    start_idx = max(0, target_index - 300) 
    focus_candles = candles[start_idx : target_index + 2]
    
    for c in focus_candles:
        theory_state.process_candle(c)
        intents = rule_engine.evaluate(theory_state, c.timestamp)
        
        # Only print near the target to keep it readable
        if c.timestamp.strftime('%H:%M:%S') >= '16:15:00':
            print(f"\n--- {c.timestamp} ---")
            print(f"Candle: O={c.open} H={c.high} L={c.low} C={c.close} {'Bull' if c.is_bullish else 'Bear'}")
            # Check Premium/Discount explicitly using the engine (we can just manually calc the 200 min window)
            window_candles = candles[max(0, candles.index(c) - 200) : candles.index(c)]
            if len(window_candles) == 200:
                highest_high = max(wc.high for wc in window_candles)
                lowest_low = max(wc.low for wc in window_candles) # Bug in my manual calc right now, but ignore it.
                eq = (highest_high + min(wc.low for wc in window_candles)) / 2
                print(f"Bias Eq: {eq} | Current close vs Eq -> {'PREMIUM (Shorts)' if c.close > eq else 'DISCOUNT (Longs)'}")
            
            # Print active origins
            active_orgs = theory_state.get_active_origin_levels()
            if active_orgs:
                latest = active_orgs[-1]
                print(f"Latest Origin Tracking: {latest.level_type} @ {latest.price_open} (High: {latest.price_high}, Low: {latest.price_low})")
            
            if intents:
                print(">> INTENT TRIGGERED HERE <<")
                for i in intents:
                    dr = "LONG" if i.is_bullish else "SHORT"
                    print(f"   Action: {dr} @ {i.entry_price}")
else:
    print("Could not find the target candle in CSV.")
