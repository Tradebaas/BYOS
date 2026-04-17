import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger
from src.layer2_theory.models import LevelType

candles = load_historical_1m_data('data/historical/NQ_1min.csv')
theory_state = MarketTheoryState()

print("Starting debug trace...")
trigger = ConfirmationHoldLevelTrigger(params={'bias_window_size': 200})
for i, c in enumerate(candles):
    theory_state.process_candle(c)
    if '17:30' <= c.timestamp.strftime('%H:%M') <= '18:10' and c.timestamp.strftime('%Y-%m-%d') == '2026-04-13':
        context = PipelineContext(theory_state=theory_state, timestamp=c.timestamp)
        context.active_polarity_is_bullish = False # SHORT
        
        # Manually trace process
        history = theory_state.history
        bias_window_size = 200
        current_idx = len(history) - 1
        cutoff_idx = max(0, current_idx - bias_window_size)
        cutoff_timestamp = history[cutoff_idx].timestamp
        
        tradable_trackers = []
        for ot in context.theory_state.origin_trackers:
            if ot.is_active and ot.level_data.level_type == LevelType.ORIGIN_LEVEL:
                if ot.level_data.is_bullish == False:
                    if ot.level_data.timestamp >= cutoff_timestamp:
                        tradable_trackers.append(ot)
                        
        if not tradable_trackers:
            print(f"[{c.timestamp}] NO TRADABLE TRACKERS")
            continue
            
        print(f"[{c.timestamp}] Active tracker: {tradable_trackers[-1].level_data.timestamp}")
