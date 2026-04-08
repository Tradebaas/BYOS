import csv
import pytest
from datetime import datetime, timezone
from pathlib import Path
from pydantic import ValidationError

from src.layer1_data.models import Candle
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer1_data.resampler import resample_candles

def test_candle_immutability():
    candle = Candle(
        timestamp=datetime.now(),
        open=100.0,
        high=110.0,
        low=90.0,
        close=105.0,
        volume=10.0
    )
    assert candle.is_bullish is True
    assert candle.is_bearish is False
    assert candle.body_size == 5.0
    assert candle.top_wick == 5.0
    assert candle.bottom_wick == 10.0
    
    # Verification of Absolute Immutability rule
    with pytest.raises(ValidationError):
        candle.close = 50.0

def test_csv_parser(tmp_path):
    csv_file = tmp_path / "test.csv"
    with open(csv_file, 'w') as f:
        writer = csv.writer(f)
        writer.writerow(["time", "open", "high", "low", "close", "volume"])
        # Support ISO String
        writer.writerow(["2020-01-01T00:00:00Z", "100", "110", "90", "105", "10"])
        # Support UNIX Milliseconds
        writer.writerow(["1577836860000", "105", "115", "100", "95", "20"])
        # Support String with lowercases and different spaces
        writer.writerow([" 2020-01-01T00:02:00 ", "95", "100", "80", "85", "30"])
    
    candles = load_historical_1m_data(csv_file)
    assert len(candles) == 3
    
    # Check first row (ISO)
    assert candles[0].close == 105.0
    assert candles[0].volume == 10.0
    
    # Check second row (Milliseconds conversion)
    assert candles[1].open == 105.0
    assert candles[1].is_bearish is True
    
    # Check third row
    assert candles[2].close == 85.0

def test_resampler():
    # Base TS = Jan 1 2020 00:00:00 UTC = 1577836800
    base_ts = 1577836800
    
    candles = [
        Candle(timestamp=datetime.fromtimestamp(base_ts), open=100, high=105, low=95, close=102, volume=1),          # 00:00
        Candle(timestamp=datetime.fromtimestamp(base_ts + 60), open=102, high=108, low=101, close=107, volume=1),    # 00:01
        Candle(timestamp=datetime.fromtimestamp(base_ts + 120), open=107, high=107, low=90, close=92, volume=1),     # 00:02
        Candle(timestamp=datetime.fromtimestamp(base_ts + 180), open=92, high=95, low=80, close=85, volume=1),       # 00:03
        Candle(timestamp=datetime.fromtimestamp(base_ts + 240), open=85, high=110, low=85, close=109, volume=1),     # 00:04
        # NEXT BUCKET
        Candle(timestamp=datetime.fromtimestamp(base_ts + 300), open=109, high=111, low=100, close=100, volume=5),   # 00:05
    ]
    
    # Re-sample 1-minute to 5-minute chunks
    resampled = resample_candles(candles, 5)
    
    assert len(resampled) == 2
    
    bucket_1 = resampled[0]
    assert bucket_1.timestamp == datetime.fromtimestamp(base_ts)
    assert bucket_1.open == 100
    assert bucket_1.close == 109
    assert bucket_1.high == 110 # Highest from 00:04
    assert bucket_1.low == 80   # Lowest from 00:03
    assert bucket_1.volume == 5
    
    bucket_2 = resampled[1]
    assert bucket_2.timestamp == datetime.fromtimestamp(base_ts + 300)
    assert bucket_2.open == 109
    assert bucket_2.close == 100
    assert bucket_2.high == 111
    assert bucket_2.volume == 5
