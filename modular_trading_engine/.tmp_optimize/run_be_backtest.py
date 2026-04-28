import os
import sys
import pandas as pd
import json

from src.layer1_data.models import Candle
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.playbook_schema import PlaybookConfig
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer4_execution.simulator import BacktestSimulator
from src.layer4_execution.data_vault import DataVault

def load_candles():
    print("Loading 3 months NQ historical data...")
    df = pd.read_csv("data/historical/NQ_1min.csv")
    df['timestamp'] = pd.to_datetime(df['datetime_utc'])
    
    candles = []
    for row in df.itertuples():
        c = Candle(
            timestamp=row.timestamp,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume
        )
        candles.append(c)
    return candles

def run_be_backtest():
    candles = load_candles()
    with open(".tmp_optimize/strategy_playbook_be.json", "r") as f:
        config = json.load(f)

    print("Initializing Pipeline...")
    state = MarketTheoryState()
    cfg = PlaybookConfig(**config)
    engine = RuleEngine(cfg)
    vault = DataVault()
    simulator = BacktestSimulator(vault)

    print(f"Running simulation over {len(candles)} candles...")
    for c in candles:
        # L2 Theory
        state.process_candle(c)
        
        # L3 Strategy
        intents = engine.evaluate(state, c.timestamp)
        for intent in intents:
            simulator.stage_order(intent)
            
        # L4 Execution
        simulator.process_candle(c)

    print("Simulation complete! Fetching results...")
    trades = vault.trades
    
    if not trades:
        print("No trades executed.")
        return

    wins = [t for t in trades if t.win]
    losses = [t for t in trades if not t.win]
    total_pnl = sum(t.pnl_points for t in trades)
    
    print("\n--- RESULTS WITH BE SHIELD (+15pt) & 1 tick offset ---")
    print(f"Total Trades: {len(trades)}")
    print(f"Wins: {len(wins)}")
    print(f"Losses: {len(losses)}")
    print(f"Winrate: {len(wins)/len(trades)*100:.2f}%")
    print(f"Total PnL Points: {total_pnl:.1f}")

if __name__ == "__main__":
    run_be_backtest()
