import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .models import Candle


def load_historical_1m_data(file_path: Path | str) -> List[Candle]:
    """
    Parses a standard OHLCV CSV file and returns a list of immutable Candle objects.
    Expected CSV columns (case-insensitive): time/timestamp, open, high, low, close.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    candles = []
    with open(path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV file is empty or missing headers")

        # Map headers for robust, case-insensitive fetching
        headers = {str(h).strip().lower(): str(h) for h in reader.fieldnames}
        
        time_key = headers.get('time') or headers.get('timestamp') or headers.get('date')
        if not time_key:
            raise ValueError("CSV missing a time/timestamp column")

        for row in reader:
            raw_time = row[time_key].strip()
            
            # Timestamp parsing with multiple format support
            try:
                if raw_time.replace('.', '', 1).isdigit():
                    val = float(raw_time)
                    if val > 1e11:  # Likely milliseconds
                        dt = datetime.fromtimestamp(val / 1000.0, tz=timezone.utc)
                    else:
                        dt = datetime.fromtimestamp(val, tz=timezone.utc)
                else:
                    # Generic ISO parsing
                    dt = datetime.fromisoformat(raw_time.replace('Z', '+00:00'))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Could not parse timestamp '{raw_time}': {e}")

            candle = Candle(
                timestamp=dt,
                open=float(row[headers.get('open', 'open')]),
                high=float(row[headers.get('high', 'high')]),
                low=float(row[headers.get('low', 'low')]),
                close=float(row[headers.get('close', 'close')]),
                volume=float(row.get(headers.get('volume', 'volume'), 0.0))
            )
            candles.append(candle)
            
    # Always guarantee sequential data for the timeline
    candles.sort(key=lambda c: c.timestamp)
    return candles
