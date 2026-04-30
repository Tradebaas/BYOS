import sys
import os
import pandas as pd
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.layer3_strategy.pipeline_engine import PipelineEngine
from src.layer1_data.tick_loader import NQCSVTickLoader
from src.layer1_data.backtest_streamer import BacktestStreamer
from src.layer4_execution.simulator import SimulatedExecutionVault

def main():
    print("Starting backtest for analysis...")
    engine = PipelineEngine(".tmp_optimize/playbook_profile2.json")
    loader = NQCSVTickLoader("data/backtest/candles/NQ_1min.csv")
    ticks = loader.get_historical_ticks(datetime.min.replace(tzinfo=timezone.utc), datetime.now(timezone.utc))
    streamer = BacktestStreamer(ticks)
    vault = SimulatedExecutionVault()
    
    streamer.register_tick_callback(engine.on_tick)
    engine.register_order_callback(vault.on_order)
    streamer.register_tick_callback(vault.on_tick)
    
    streamer.run()
    
    trades = vault.trades
    
    data = []
    for t in trades:
        entry_time = getattr(t, 'entry_time', None)
        if not entry_time: continue
        
        pnl = t.pnl_points
        if pnl > 5: outcome = 'WIN'
        elif pnl > -5: outcome = 'BE'
        else: outcome = 'LOSS'
        
        data.append({
            'entry_time': entry_time,
            'month': entry_time.strftime('%Y-%m'),
            'hour': entry_time.hour, # UTC hour
            'day_of_week': entry_time.strftime('%A'),
            'pnl': pnl,
            'outcome': outcome,
            'direction': t.direction.name
        })
        
    df = pd.DataFrame(data)
    df.to_csv('.tmp_optimize/trades_analysis.csv', index=False)
    
    # Run some basic analysis
    print("\n--- PERFORMANCE BY HOUR (UTC) ---")
    hour_stats = df.groupby(['hour', 'outcome']).size().unstack(fill_value=0)
    hour_stats['Total'] = hour_stats.sum(axis=1)
    if 'WIN' in hour_stats and 'LOSS' in hour_stats:
        hour_stats['WinRate'] = hour_stats['WIN'] / hour_stats['Total']
    print(hour_stats)
    
    print("\n--- PERFORMANCE BY MONTH ---")
    month_stats = df.groupby(['month', 'outcome']).size().unstack(fill_value=0)
    month_stats['Total'] = month_stats.sum(axis=1)
    if 'WIN' in month_stats and 'LOSS' in month_stats:
        month_stats['WinRate'] = month_stats['WIN'] / month_stats['Total']
    print(month_stats)
    
    print("\n--- PERFORMANCE BY DAY OF WEEK ---")
    dow_stats = df.groupby(['day_of_week', 'outcome']).size().unstack(fill_value=0)
    dow_stats['Total'] = dow_stats.sum(axis=1)
    if 'WIN' in dow_stats and 'LOSS' in dow_stats:
        dow_stats['WinRate'] = dow_stats['WIN'] / dow_stats['Total']
    print(dow_stats)
    
    # Calculate consecutive losses
    print("\n--- MAX CONSECUTIVE LOSSES PER MONTH ---")
    for month in df['month'].unique():
        m_df = df[df['month'] == month]
        max_cons_losses = 0
        current_cons_losses = 0
        for out in m_df['outcome']:
            if out == 'LOSS':
                current_cons_losses += 1
                if current_cons_losses > max_cons_losses:
                    max_cons_losses = current_cons_losses
            elif out == 'WIN':
                current_cons_losses = 0
            # If BE, we don't reset consecutive losses, or do we? Let's reset it because it's not a loss.
            elif out == 'BE':
                current_cons_losses = 0
        print(f"{month}: {max_cons_losses}")

if __name__ == "__main__":
    main()
