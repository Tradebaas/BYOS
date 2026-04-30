import pandas as pd
import numpy as np

def main():
    df = pd.read_csv('.tmp_optimize/trades_export.csv')
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    
    # Convert to EST/EDT (America/New_York)
    df['entry_time_est'] = df['entry_time'].dt.tz_convert('America/New_York')
    df['hour'] = df['entry_time_est'].dt.hour
    df['month'] = df['entry_time'].dt.strftime('%Y-%m')
    df['is_jan_feb'] = df['month'].isin(['2026-01', '2026-02'])
    
    print("=== MFE & MAE ANALYSIS ===")
    # Calculate MFE/MAE in points instead of raw price
    # For LONG: MFE = mfe_price - entry_price, MAE = entry_price - mae_price
    # For SHORT: MFE = entry_price - mfe_price, MAE = mae_price - entry_price
    
    df['mfe_points'] = np.where(df['direction'] == 'LONG', df['mfe'] - df['entry_price'], df['entry_price'] - df['mfe'])
    df['mae_points'] = np.where(df['direction'] == 'LONG', df['entry_price'] - df['mae'], df['mae'] - df['entry_price'])
    
    losses = df[df['outcome'] == 'LOSS']
    losses_jan_feb = losses[losses['is_jan_feb']]
    losses_mar_apr = losses[~losses['is_jan_feb']]
    
    print(f"Jan/Feb Average MFE on Losses: {losses_jan_feb['mfe_points'].mean():.2f} pts")
    print(f"Mar/Apr Average MFE on Losses: {losses_mar_apr['mfe_points'].mean():.2f} pts")
    
    wins = df[df['outcome'] == 'WIN']
    wins_jan_feb = wins[wins['is_jan_feb']]
    wins_mar_apr = wins[~wins['is_jan_feb']]
    
    print(f"Jan/Feb Average MAE on Wins: {wins_jan_feb['mae_points'].mean():.2f} pts")
    print(f"Mar/Apr Average MAE on Wins: {wins_mar_apr['mae_points'].mean():.2f} pts")
    
    print("\n=== COOLDOWN ANALYSIS ===")
    df = df.sort_values('entry_time')
    df['time_since_last_trade'] = df['entry_time'].diff().dt.total_seconds() / 60.0
    
    def bin_time(t):
        if pd.isna(t): return 'first'
        if t < 30: return '< 30m'
        if t < 60: return '30m-1hr'
        if t < 120: return '1-2hr'
        if t < 240: return '2-4hr'
        return '> 4hr'
        
    df['time_bin'] = df['time_since_last_trade'].apply(bin_time)
    print(df.groupby('time_bin').apply(lambda x: pd.Series({
        'total': len(x),
        'win_rate': len(x[x['outcome'] == 'WIN']) / len(x),
        'pnl': x['pnl'].sum() * 40
    })))
    
    print("\n=== HOURLY ANALYSIS ACROSS ALL MONTHS (EST/EDT) ===")
    hourly = df.groupby('hour').apply(lambda x: pd.Series({
        'total': len(x),
        'wins': len(x[x['outcome'] == 'WIN']),
        'losses': len(x[x['outcome'] == 'LOSS']),
        'win_rate': len(x[x['outcome'] == 'WIN']) / len(x),
        'pnl': x['pnl'].sum() * 40
    })).sort_index()
    print(hourly)
    
if __name__ == "__main__":
    main()
