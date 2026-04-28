import json
import pandas as pd

def analyze_structural_setup():
    with open('.tmp_optimize/baseline_trades.json', 'r') as f:
        trades = json.load(f)
        
    df = pd.DataFrame(trades)
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    
    # 1. Setup Size
    df['setup_size'] = abs(df['entry_price'] - df['stop_loss'])
    
    # 2. Trade Duration (minutes)
    df['duration_mins'] = (df['exit_time'] - df['entry_time']).dt.total_seconds() / 60.0
    
    print("\n--- Structural Analysis: Setup Size ---")
    df['size_bucket'] = pd.qcut(df['setup_size'].rank(method='first'), q=5, labels=['Tiny', 'Small', 'Medium', 'Large', 'Huge'])
    size_stats = df.groupby('size_bucket').agg(Total=('win', 'count'), Wins=('win', 'sum'), AvgSize=('setup_size', 'mean'))
    size_stats['Losses'] = size_stats['Total'] - size_stats['Wins']
    size_stats['WinRate'] = size_stats['Wins'] / size_stats['Total'] * 100
    print(size_stats)
    
    print("\n--- Structural Analysis: Trade Duration ---")
    # For duration, we separate wins and losses to see if losses take much longer
    wins = df[df['win'] == True]
    losses = df[df['win'] == False]
    print(f"Average Duration for WINS: {wins['duration_mins'].mean():.2f} mins")
    print(f"Average Duration for LOSSES: {losses['duration_mins'].mean():.2f} mins")
    print(f"Median Duration for WINS: {wins['duration_mins'].median():.2f} mins")
    print(f"Median Duration for LOSSES: {losses['duration_mins'].median():.2f} mins")
    
    df['duration_bucket'] = pd.cut(df['duration_mins'], bins=[0, 5, 15, 30, 60, 9999], labels=['<5m', '5-15m', '15-30m', '30-60m', '>60m'])
    dur_stats = df.groupby('duration_bucket').agg(Total=('win', 'count'), Wins=('win', 'sum'))
    dur_stats['WinRate'] = dur_stats['Wins'] / dur_stats['Total'] * 100
    print("\nWin Rate by Duration:")
    print(dur_stats)

analyze_structural_setup()
