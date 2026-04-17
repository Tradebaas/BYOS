import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer3_strategy.pipeline import StrategyPipeline
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.config_parser import load_pipeline_config
candles = load_historical_1m_data('data/historical/NQ_1min.csv')

theory_state = MarketTheoryState()
history = candles[-1000:]
theory_state.history = history

pipeline = StrategyPipeline(load_pipeline_config('data/playbooks/day_trading_decrypted.json'))

context = pipeline.process(theory_state)
print(f"Active Polarity (Bias): {context.active_polarity_is_bullish}")
if context.setup_candidates:
    for c in context.setup_candidates:
        print(f"CANDIDATE FOUND: {c.level_data.price_open} ({c.level_data.is_bullish})")
else:
    print("No valid intents triggered this candle.")
