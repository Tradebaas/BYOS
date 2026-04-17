import pandas as pd

df = pd.read_csv("data/historical/NQ_1min.csv")
df['is_bull'] = df['close'] >= df['open']
df['is_bear'] = df['close'] < df['open']

count = 0
for i in range(1, len(df)):
    prev = df.iloc[i-1]
    curr = df.iloc[i]
    if curr['is_bull'] and curr['open'] > prev['high'] and curr['close'] > prev['high']:
        count += 1
    if curr['is_bear'] and curr['open'] < prev['low'] and curr['close'] < prev['low']:
        count += 1
        
print(f"Total hard close follow-throughs (immediate): {count}")
