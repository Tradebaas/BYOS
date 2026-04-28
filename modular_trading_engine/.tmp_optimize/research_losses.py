import json
import pandas as pd
import numpy as np

def analyze():
    print("Loading baseline trades...")
    with open('.tmp_optimize/baseline_trades.json', 'r') as f:
        trades = json.load(f)
        
    df = pd.DataFrame(trades)
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    df['duration'] = (df['exit_time'] - df['entry_time']).dt.total_seconds() / 60.0
    
    wins = df[df['win'] == True]
    losses = df[df['win'] == False]
    
    print(f"Total Trades: {len(df)}")
    print(f"Wins: {len(wins)}, Losses: {len(losses)}, Winrate: {len(wins)/len(df)*100:.2f}%")
    print(f"Total PnL: {df['pnl_points'].sum():.2f}")
    
    print("\n--- MAE/MFE Analysis on Losses ---")
    print("Losses that hit at least +5pt profit before losing: ", len(losses[losses['mfe'] >= 5]))
    print("Losses that hit at least +8pt profit before losing: ", len(losses[losses['mfe'] >= 8]))
    print("Losses that hit at least +10pt profit before losing: ", len(losses[losses['mfe'] >= 10]))
    
    print("\n--- Trade Duration Analysis ---")
    print(f"Avg Duration (Wins): {wins['duration'].mean():.1f} min")
    print(f"Avg Duration (Losses): {losses['duration'].mean():.1f} min")
    
    # Calculate how many losses and wins happen within first X minutes
    for m in [5, 10, 15, 30]:
        print(f"Wins closed in <{m}m: {len(wins[wins['duration'] < m])}")
        print(f"Losses closed in <{m}m: {len(losses[losses['duration'] < m])}")
        
    print("\n--- Time of Day (EST) Analysis ---")
    # Using entry time to find worst performing hours
    # NQ trades 24/5, killzones play a role
    df['hour'] = df['entry_time'].dt.tz_localize('UTC').dt.tz_convert('America/New_York').dt.hour
    hourly_stats = []
    for h in sorted(df['hour'].unique()):
        hdf = df[df['hour'] == h]
        h_wins = len(hdf[hdf['win'] == True])
        h_losses = len(hdf[hdf['win'] == False])
        h_wr = h_wins / max(1, len(hdf)) * 100
        h_pnl = hdf['pnl_points'].sum()
        hourly_stats.append((h, len(hdf), h_wins, h_losses, h_wr, h_pnl))
        
    hourly_df = pd.DataFrame(hourly_stats, columns=['Hour', 'Total', 'Wins', 'Losses', 'WinRate', 'PnL'])
    print(hourly_df.to_string(index=False))

analyze()
