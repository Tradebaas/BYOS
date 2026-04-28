import json
import pandas as pd

def analyze():
    print("Loading baseline trades...")
    with open('.tmp_optimize/baseline_trades.json', 'r') as f:
        trades = json.load(f)
        
    df = pd.DataFrame(trades)
    
    # Calculate MFE strictly in points
    # For long: mfe is the max price reached. points = mfe - entry_price
    # For short: mfe is the min price reached (wait, in simulator it tracks min price!). points = entry_price - mfe
    
    # In simulator.py:
    # if intent.is_bullish:
    #     if candle.high > pos.mfe: pos.mfe = candle.high
    # else:
    #     if candle.low < pos.mfe: pos.mfe = candle.low
    
    df['mfe_points'] = df.apply(lambda row: row['mfe'] - row['entry_price'] if row['is_bullish'] else row['entry_price'] - row['mfe'], axis=1)
    
    losses = df[df['win'] == False]
    
    print("\n--- Correct MAE/MFE Analysis on Losses ---")
    print("Losses that hit at least +5pt profit before losing: ", len(losses[losses['mfe_points'] >= 5]))
    print("Losses that hit at least +8pt profit before losing: ", len(losses[losses['mfe_points'] >= 8]))
    print("Losses that hit at least +10pt profit before losing: ", len(losses[losses['mfe_points'] >= 10]))
    print("Losses that hit at least +11pt profit before losing: ", len(losses[losses['mfe_points'] >= 11]))
    
    print("\n--- Why Deep Dive Invalidation failed ---")
    # Evaluate why wins dropped by 131 vs 103 losses
    print("Deep Dive prevents execution by cancelling setup if extreme is breached before limit order.")
    print("The statistics showed it prevents more winners than losers.")

analyze()
