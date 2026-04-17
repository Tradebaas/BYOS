import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger

candles = load_historical_1m_data('data/historical/NQ_1min.csv')

def test_blocks():
    history = candles[-1000:]
    trigger = ConfirmationHoldLevelTrigger(params={})
    is_bullish = False
    blocks = trigger.find_blocks(history, 0, is_bullish)
    for b in blocks:
        hc_ts = history[b["hc_idx"]].timestamp
        c1_ts = history[b["c1_idx"]].timestamp
        if "19:00" <= hc_ts.strftime("%H:%M") <= "19:20":
            print(f"Block: {c1_ts.strftime('%H:%M')} Hold={b['hold']} Break={b['break']} HC={hc_ts.strftime('%H:%M')}")
            
test_blocks()
