import json
import pandas as pd
import numpy as np
from datetime import timedelta

def load_candles():
    df = pd.read_csv("data/historical/NQ_1min.csv")
    df['timestamp'] = pd.to_datetime(df['datetime_utc'])
    df = df.sort_values('timestamp')
    df.set_index('timestamp', inplace=True)
    return df

def analyze():
    print("Loading baseline trades...")
    with open('.tmp_optimize/baseline_trades.json', 'r') as f:
        trades = json.load(f)
        
    df_trades = pd.DataFrame(trades)
    df_trades['entry_time'] = pd.to_datetime(df_trades['entry_time'])
    
    df_candles = load_candles()
    
    metrics = []
    
    for i, row in df_trades.iterrows():
        entry_time = row['entry_time']
        direction = 1 if row['is_bullish'] else -1
        win = row['win']
        
        # Get last 60 minutes before entry
        start_time = entry_time - timedelta(minutes=60)
        recent_history = df_candles.loc[start_time:entry_time]
        
        if recent_history.empty:
            continue
            
        # Calculate ATR (Average True Range) approximation over 60 candles
        highs = recent_history['high']
        lows = recent_history['low']
        atr = (highs - lows).mean()
        
        # Calculate speed of approach (how many candles from peak to entry)
        if direction == 1:
            # Long entry => How fast did we drop into the limit order?
            peak_price = recent_history['high'].max()
            peak_time = recent_history['high'].idxmax()
            drop = peak_price - row['entry_price']
            drop_time = (entry_time - peak_time).total_seconds() / 60.0
            speed = drop / drop_time if drop_time > 0 else 0
            
            # Check price momentum right before
            last_5 = recent_history.tail(5)
            momentum_5m = row['entry_price'] - last_5['open'].iloc[0]
        else:
            # Short entry => How fast did we rally into the limit order?
            trough_price = recent_history['low'].min()
            trough_time = recent_history['low'].idxmin()
            rally = row['entry_price'] - trough_price
            rally_time = (entry_time - trough_time).total_seconds() / 60.0
            speed = rally / rally_time if rally_time > 0 else 0
            
            last_5 = recent_history.tail(5)
            momentum_5m = last_5['open'].iloc[0] - row['entry_price']
            
        metrics.append({
            'win': win,
            'direction': 'Long' if direction == 1 else 'Short',
            'atr': atr,
            'speed': speed,
            'momentum_5m': momentum_5m,
            'hour': entry_time.hour
        })
        
    df_metrics = pd.DataFrame(metrics)
    
    print("\n--- Structural Analysis ---")
    print(df_metrics.groupby('win').mean(numeric_only=True))
    
    # Bucket by speed
    df_metrics['speed_bucket'] = pd.qcut(df_metrics['speed'].rank(method='first'), q=4, labels=['Q1_Slowest', 'Q2', 'Q3', 'Q4_Fastest'])
    print("\nWinrate by speed of approach (points per min drop/rally into limit order):")
    speed_stats = df_metrics.groupby('speed_bucket').agg(Total=('win', 'count'), Wins=('win', 'sum'))
    speed_stats['Losses'] = speed_stats['Total'] - speed_stats['Wins']
    speed_stats['WinRate'] = speed_stats['Wins'] / speed_stats['Total'] * 100
    print(speed_stats)
    
    # Bucket by ATR
    df_metrics['atr_bucket'] = pd.qcut(df_metrics['atr'].rank(method='first'), q=4, labels=['Q1_LowestVol', 'Q2', 'Q3', 'Q4_HighestVol'])
    print("\nWinrate by ATR (Market Volatility):")
    atr_stats = df_metrics.groupby('atr_bucket').agg(Total=('win', 'count'), Wins=('win', 'sum'))
    atr_stats['Losses'] = atr_stats['Total'] - atr_stats['Wins']
    atr_stats['WinRate'] = atr_stats['Wins'] / atr_stats['Total'] * 100
    print(atr_stats)
    
    # Bucket by 5m immediate counter momentum
    # Negative momentum means it was crashing hard into the level
    df_metrics['counter_momentum_5m'] = -df_metrics['momentum_5m'] # How hard it crashed/squeezed into entry
    df_metrics['momentum_bucket'] = pd.qcut(df_metrics['counter_momentum_5m'].rank(method='first'), q=4, labels=['Soft_Approach', 'Med_Approach', 'Hard_Crash', 'Extreme_Crash'])
    print("\nWinrate by 5m Counter-Momentum (Crash into level):")
    mom_stats = df_metrics.groupby('momentum_bucket').agg(Total=('win', 'count'), Wins=('win', 'sum'))
    mom_stats['WinRate'] = mom_stats['Wins'] / mom_stats['Total'] * 100
    print(mom_stats)
    
    print("\nAsia & Transition Killzone filtering check:")
    killzone_hours = [19, 20, 23, 0, 11]
    filtered_df = df_metrics[~df_metrics['hour'].isin(killzone_hours)]
    print(f"Total original trades: {len(df_metrics)} (Wins: {df_metrics['win'].sum()})")
    print(f"Total filtered trades: {len(filtered_df)} (Wins: {filtered_df['win'].sum()})")
    print(f"Filtered Win Rate: {filtered_df['win'].sum() / len(filtered_df) * 100:.2f}%")

analyze()
