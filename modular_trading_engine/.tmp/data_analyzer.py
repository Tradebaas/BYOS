import pandas as pd
import numpy as np

def main():
    df = pd.read_csv('.tmp_optimize/trades_export.csv')
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['hour'] = df['entry_time'].dt.hour
    df['day_of_week'] = df['entry_time'].dt.day_name()
    df['month'] = df['entry_time'].dt.strftime('%Y-%m')
    
    # 1. Compare January & February with March & April
    jan_feb = df[df['month'].isin(['2026-01', '2026-02'])]
    mar_apr = df[df['month'].isin(['2026-03', '2026-04'])]
    
    def analyze_period(period_df, name):
        print(f"\n{'='*40}")
        print(f"ANALYSIS FOR: {name}")
        print(f"{'='*40}")
        if len(period_df) == 0:
            print("No data.")
            return
            
        wins = len(period_df[period_df['outcome'] == 'WIN'])
        bes = len(period_df[period_df['outcome'] == 'BE'])
        losses = len(period_df[period_df['outcome'] == 'LOSS'])
        total = len(period_df)
        win_rate = wins / total
        
        print(f"Total Trades: {total}")
        print(f"Wins: {wins} ({win_rate:.1%})")
        print(f"BEs: {bes} ({bes/total:.1%})")
        print(f"Losses: {losses} ({losses/total:.1%})")
        
        # Analyze by hour
        print("\n--- By Hour (UTC) ---")
        hour_grouped = period_df.groupby('hour').apply(lambda x: pd.Series({
            'total': len(x),
            'win_rate': len(x[x['outcome'] == 'WIN']) / len(x) if len(x) > 0 else 0,
            'losses': len(x[x['outcome'] == 'LOSS'])
        }))
        print(hour_grouped.sort_values('win_rate', ascending=False))
        
        # Analyze by direction
        print("\n--- By Direction ---")
        dir_grouped = period_df.groupby('direction').apply(lambda x: pd.Series({
            'total': len(x),
            'win_rate': len(x[x['outcome'] == 'WIN']) / len(x) if len(x) > 0 else 0,
            'losses': len(x[x['outcome'] == 'LOSS'])
        }))
        print(dir_grouped)
        
        # Analyze consecutive losses
        max_cons_losses = 0
        curr_cons = 0
        for outcome in period_df.sort_values('entry_time')['outcome']:
            if outcome == 'LOSS':
                curr_cons += 1
                if curr_cons > max_cons_losses: max_cons_losses = curr_cons
            elif outcome == 'WIN' or outcome == 'BE':
                curr_cons = 0
        print(f"\nMax Consecutive Losses: {max_cons_losses}")
        
    analyze_period(jan_feb, "Jan & Feb (Poor Performance)")
    analyze_period(mar_apr, "Mar & Apr (Good Performance)")
    
if __name__ == "__main__":
    main()
