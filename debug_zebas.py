import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from zebas_core import ZebasEngine
from modular_trading_engine.src.layer1_data.models import Candle

# Load historical data
df = pd.read_csv('modular_trading_engine/data/historical/NQ_1min.csv')
df['datetime_utc'] = pd.to_datetime(df['datetime_utc'])
df = df.sort_values('datetime_utc')
# test last 3 days
recent_df = df.tail(60 * 24 * 3).copy()

engine = ZebasEngine()

for _, row in recent_df.iterrows():
    c = Candle(
        timestamp=int(row['datetime_utc'].timestamp() * 1000),
        open=float(row['open']),
        high=float(row['high']),
        low=float(row['low']),
        close=float(row['close']),
        volume=float(row['volume'])
    )
    engine.process_candle(c)

print(f"Final active breaks: {len(engine.breaks)}")
for lvl in engine.breaks:
    print(f"{'RESISTANCE' if lvl.is_break_up else 'SUPPORT'} at {lvl.price:.2f} (Created: {lvl.creation_bar_idx})")
