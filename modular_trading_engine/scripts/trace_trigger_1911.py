import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.rule_engine import RuleEngine

candles = load_historical_1m_data('data/historical/NQ_1min.csv')
theory_state = MarketTheoryState()
playbook_config = ConfigParser.load_playbook("data/playbooks/day_trading_decrypted.json")
rule_engine = RuleEngine(playbook_config)

print("Tracing exactly at 19:11...")
for i, c in enumerate(candles):
    theory_state.process_candle(c)
    if c.timestamp.strftime('%H:%M') == '19:11' and c.timestamp.strftime('%Y-%m-%d') == '2026-04-13':
        context = PipelineContext(theory_state=theory_state, timestamp=c.timestamp)
        context.active_polarity_is_bullish = False # SHORT
        
        trigger = rule_engine.pipeline_modules[1]
        
        bias_window_size = 200
        history = context.theory_state.history
        current_idx = len(history) - 1
        start_idx = max(0, current_idx - bias_window_size)
        
        blocks = trigger.find_blocks(history, start_idx, False)
        print("--- BLOCKS ---")
        for b in blocks:
             hc_ts = history[b["hc_idx"]].timestamp
             print(f"Block: Hold={b['hold']} Break={b['break']} HC={hc_ts.strftime('%H:%M')} C1={history[b['c1_idx']].timestamp.strftime('%H:%M')}")
             
        trigger.process(context)
        print(f"Intents generated: {len(context.setup_candidates)}")
        for cand in context.setup_candidates:
             print(f"Intent generated: Entry={cand.level_data.price_open}")
        break
