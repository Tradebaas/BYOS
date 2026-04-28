import json
import pandas as pd

def analyze_breakeven():
    print("Loading baseline trades...")
    with open('.tmp_optimize/baseline_trades.json', 'r') as f:
        trades = json.load(f)
        
    df = pd.DataFrame(trades)
    
    # Calculate relative MFE and MAE
    # For longs: MFE is max price reached (highest), MAE is min price (lowest)
    # For shorts: MFE is min price reached (lowest), MAE is max price (highest)
    df['rel_mfe'] = df.apply(lambda row: (row['mfe'] - row['entry_price']) if row['is_bullish'] else (row['entry_price'] - row['mfe']), axis=1)
    df['rel_mae'] = df.apply(lambda row: (row['entry_price'] - row['mae']) if row['is_bullish'] else (row['mae'] - row['entry_price']), axis=1)
    
    initial_wins = df['win'].sum()
    initial_losses = len(df) - initial_wins
    initial_winrate = initial_wins / len(df) * 100
    
    print(f"--- Original Stats ---")
    print(f"Total Trades: {len(df)}")
    print(f"Wins: {initial_wins}")
    print(f"Losses: {initial_losses}")
    print(f"Win Rate: {initial_winrate:.2f}%")
    
    print("\n--- Testing Breakeven Shield ---")
    # A breakeven shield sets the stop loss to Entry Price once MFE hits X points.
    # If the trade would have won, does it hit Breakeven first?
    # Because we don't have 1-second data here, we have to assume: if the candle that hit the MFE > MFE_Trigger, 
    # did it hit MAE < 0 (i.e., went against us)? We rely on MAE. 
    # Wait, MFE and MAE are over the whole trade. If a trade won, and its MAE < 0 (went against us below entry), 
    # AND its MFE is huge, we don't know which came first. Unless we assume that for winners, MAE happens before TP.
    # But actually, if we want to add a Breakeven rule, any trade (win or loss) that reaches +10 pts 
    # and then comes back to entry will be stopped out at 0.
    # In backtest simulation this is easier. But just looking at MFE:
    
    for trigger in [6, 8, 10, 12, 15]:
        saved_losses = df[(df['win'] == False) & (df['rel_mfe'] >= trigger)]
        # Are there winners that hit 0 (breakeven) after hitting +trigger? We can't know the exact path from MFE/MAE alone,
        # but if MAE <= 0, and they won, they might have hit BE. However, most likely the MAE happens BEFORE the huge MFE.
        # But let's look at the saved losses!
        print(f"\nBE Trigger @ +{trigger} pts:")
        print(f"  Losses that would scratch (BE): {len(saved_losses)}")
        
        # Approximate new win rate (Wins / (Total - BE_scratches))
        # because BE is a scratch, neither win nor loss.
        new_total = len(df) - len(saved_losses)
        new_winrate = initial_wins / new_total * 100 if new_total > 0 else 0
        print(f"  Approximate New Win Rate: {new_winrate:.2f}% (Assuming no winners are stopped out)")

analyze_breakeven()
