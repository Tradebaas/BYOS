import os
import time
import sys
import csv
import logging
import urllib.parse
from datetime import datetime, timezone, timedelta

# Import headless auth and credentials
_engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _engine_root not in sys.path:
    sys.path.insert(0, _engine_root)
os.chdir(_engine_root)
from src.layer4_execution.auth import fetch_topstepx_jwt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LAKE_FILE = "data/backtest/candles/NQ_1min.csv"
symbol = "/NQ"
resolution = "1"
CHART_API_URL = "https://chartapi.topstepx.com/History/v2"

def get_latest_timestamp() -> int:
    """Returns the latest timestamp_ms in the existing CSV, or 0 if it doesn't exist."""
    if not os.path.exists(LAKE_FILE):
        return 0
    try:
        last_ts = 0
        with open(LAKE_FILE, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = int(row['timestamp_ms'])
                if ts > last_ts:
                    last_ts = ts
        return last_ts
    except Exception as e:
        logger.error(f"Error reading CSV header: {e}")
        return 0

def save_bars_to_csv(bars: list, latest_ts: int) -> int:
    """Saves raw bars to CSV, skipping duplicates."""
    file_exists = os.path.exists(LAKE_FILE)
    fieldnames = ['timestamp_ms', 'datetime_utc', 'open', 'high', 'low', 'close', 'volume', 'trade_count']
    
    added_count = 0
    with open(LAKE_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
            
        for b in bars:
            ts_ms = b.get("t", 0)
            if ts_ms <= latest_ts:
                continue # Skip duplicates
                
            dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
            dt_iso = dt.strftime('%Y-%m-%d %H:%M:%S')
            
            writer.writerow({
                'timestamp_ms': ts_ms,
                'datetime_utc': dt_iso,
                'open': b.get("o", 0.0),
                'high': b.get("h", 0.0),
                'low': b.get("l", 0.0),
                'close': b.get("c", 0.0),
                'volume': b.get("v", 0),
                'trade_count': b.get("tv", 0)
            })
            latest_ts = max(latest_ts, ts_ms)
            added_count += 1
            
    return added_count, latest_ts

import requests

async def build_lake():
    # 1. Authenticatie (Headless login)
    logger.info("Verkrijgen van auth token via Headless Chromium...")
    jwt_token = await fetch_topstepx_jwt()
    if not jwt_token:
        logger.error("Kon geen valide interne API bearer token ophalen.")
        return

    # 2. Bereken tijdvenster
    now_sec = int(time.time())
    days_back = 90
    chunk_days = 5
    
    start_time_global = now_sec - (days_back * 24 * 60 * 60)
    
    latest_saved_ts_ms = get_latest_timestamp()
    if latest_saved_ts_ms > 0:
        logger.info(f"Bestaande data gevonden. Laatste opname was: {datetime.fromtimestamp(latest_saved_ts_ms/1000, tz=timezone.utc)}")
        # Start fetching from the last saved point
        start_time_global = int(latest_saved_ts_ms / 1000)
    
    if start_time_global >= now_sec:
        logger.info("Data Lake is up to date!")
        return

    total_added = 0
    current_start = start_time_global

    while current_start < now_sec:
        current_end = current_start + (chunk_days * 24 * 60 * 60)
        if current_end > now_sec:
            current_end = now_sec
            
        logger.info(f"Ophalen periode: {datetime.fromtimestamp(current_start, tz=timezone.utc)} TOT {datetime.fromtimestamp(current_end, tz=timezone.utc)}")
        
        params = {
            "Symbol": symbol,
            "Resolution": resolution,
            "From": current_start,
            "To": current_end
        }
        
        url = f"{CHART_API_URL}?{urllib.parse.urlencode(params)}"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Origin": "https://www.topstepx.com",
            "x-app-type": "web",
            "x-app-version": "1.22.50",
            "Accept": "application/json"
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            bars = data.get("bars", [])
            bars = sorted(bars, key=lambda x: x.get("t", 0))
            logger.info(f"--> Ontvangen {len(bars)} candles.")
            
            if bars:
                added, latest_saved_ts_ms = save_bars_to_csv(bars, latest_saved_ts_ms)
                total_added += added
                logger.info(f"--> {added} toegevoegd aan Data Lake.")
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429: # Rate limit
                logger.warning("Rate limit geraakt, slaap 10 seconden...")
                time.sleep(10)
                continue # Retry same chunk
            else:
                logger.error(f"API Error bij iteratie: {e}")
                time.sleep(5) # Prevent aggressive looping
        except Exception as e:
            logger.error(f"Onverwachte netwerk/parse fout: {e}")
            break
            
        # Time progression
        current_start = current_end
        
        # Kleine slaap tegen overloading (rate limiting)
        time.sleep(0.5)

    logger.info(f"Data Lake update succesvol. Totaal toegevoegd deze sessie: {total_added} candles.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(build_lake())
