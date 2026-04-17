import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
candles = load_historical_1m_data('data/historical/NQ_1min.csv')
from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer2_theory.market_state import MarketTheoryState

trigger = ConfirmationHoldLevelTrigger(params={"bias_window_size": 200, "ttl_candles": 30, "sl_points": 10.0, "tp_points": 20.0})

history = candles[-1000:]
theory_state = MarketTheoryState()
theory_state.history = history
context = PipelineContext(history[-1].timestamp, theory_state)
context.active_polarity_is_bullish = False

trigger.process(context)
print(f"SHORT INTENTS TRIGGERED AT CURRENT LIVE EDGE: {len(context.setup_candidates)}")
context.setup_candidates = []
context.active_polarity_is_bullish = True
trigger.process(context)
print(f"LONG INTENTS TRIGGERED AT CURRENT LIVE EDGE: {len(context.setup_candidates)}")
