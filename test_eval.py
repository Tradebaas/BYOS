import sys
import logging
from datetime import datetime, timezone
import csv
from zebas_core import ZebasEngine
from modular_trading_engine.src.layer1_data.models import Candle

logging.basicConfig(level=logging.INFO)

engine = ZebasEngine(sl_pts=10.0, tp1_pts=5.0, tp2_pts=40.0, move_to_be=True)
csv_path = "modular_trading_engine/data/historical/NQ_1min.csv"

bars = []
with open(csv_path, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        timestamp_ms = int(row['timestamp_ms'])
        dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
        c = Candle(
            timestamp=dt,
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume'])
        )
        bars.append(c)

for b in bars:
    engine.process_candle(b)
