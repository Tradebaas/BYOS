import asyncio
import pandas as pd
import sys
import logging
from datetime import datetime

sys.path.append('.')
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer3_strategy.config_parser import ConfigParser

# Build logic just like rule_engine loading playbooks
async def run_diag():
    print("Loading CSV Data...")
    db_file = "data/historical/NQ_1min.csv"
    history = load_historical_1m_data(db_file)
    
    # Take last 2000 candles to simulate recent period (from yesterday evening to now)
    eval_history = history[-2000:]
    
    print(f"Candles loaded: {len(eval_history)}. From {eval_history[0].timestamp} to {eval_history[-1].timestamp}")
    
    playbook = ConfigParser.load_playbook('data/playbooks/day_trading_decrypted.json')
    engine = RuleEngine(playbook)

    
    print("\n--- Sweeping last 2000 candles minute by minute ---")
    intents_caught = 0
    blocks_caught = 0
    
    for i in range(1000, len(eval_history)):
        state = MarketTheoryState()
        state.history = eval_history[:i+1] # Feed it chunk by chunk
        intents = engine.evaluate(
            theory_state=state,
            timestamp=state.history[-1].timestamp
        )
        
        # We don't have access to context unless we hook it, but we can just check returned intents.
        # Wait, the intents are returned, so we can just check len(intents)
        if len(intents) > 0:
            for it in intents:
                print(f"[INTENT] Generated order at {state.history[-1].timestamp}: Bullish={it.is_bullish} | Entry={it.entry_price}")
                intents_caught += 1

    print(f"\nDone! Found {blocks_caught} raw geometric setups and generated {intents_caught} Order Intents.")

if __name__ == '__main__':
    asyncio.run(run_diag())
