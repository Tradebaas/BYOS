import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
import pandas as pd

from src.layer1_data.providers.dummy_historical import CSVHistoricalProvider
from src.layer3_strategy.rule_engine import ExecutionPipeline
from src.layer4_execution.simulator import BacktestSimulator
from src.layer4_execution.data_vault import DataVault

logging.basicConfig(level=logging.ERROR)

def run_be_backtest():
    with open(".tmp_optimize/strategy_playbook_be.json", "r") as f:
        playbook_config = json.load(f)
        
    vault = DataVault(is_backtest=True)
    simulator = BacktestSimulator(vault)
    pipeline = ExecutionPipeline(playbook_config, simulator)
    
    print("Loading data...")
    provider = CSVHistoricalProvider("data/historical/NQ_1min.csv")
    all_candles = provider.fetch_range(
        datetime(2023, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 12, 31, tzinfo=timezone.utc)
    )
    
    print(f"Executing simulated +10pt BE shield over {len(all_candles)} candidates...")
    success, error = pipeline.evaluate(all_candles)
    if not success:
        print(f"Error during eval: {error}")
        return
        
    trades = vault.trades
    total = len(trades)
    
    # We want to identify the types of closures.
    # We know what TP and original SL was.
    wins = 0
    losses = 0
    scratches = 0
    pnl = 0.0
    
    for t in trades:
        # Check if exit was win, loss, or scratch
        # Target +1 tick offset is 4 ticks -> +1.0 points
        if t.pnl_points >= 11.5:  # Close enough to TP=12
            wins += 1
        elif t.pnl_points <= -11.5:
            losses += 1
        else:
            # Scratch!
            scratches += 1
            
        pnl += float(t.pnl_points)
        
    print("\n--- RESULTS WITH +10pt BE SHIELD (+1 pt offset) ---")
    print(f"Total Trades: {total}")
    print(f"Total Wins (12pt): {wins} ({(wins/total*100):.2f}%)")
    print(f"Total Losses (-12pt): {losses} ({(losses/total*100):.2f}%)")
    print(f"Breakeven Scratches (+1pt): {scratches} ({(scratches/total*100):.2f}%)")
    print(f"Net PnL (Points): {pnl:.2f}")

run_be_backtest()
