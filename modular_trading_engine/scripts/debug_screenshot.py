import asyncio
from datetime import datetime, timezone
import sys
import os

sys.path.append('..')
from modular_trading_engine.src.layer4_execution.topstep_client import TopstepClient

async def run():
    client = TopstepClient()
    # 2026-04-14 17:30 UTC
    start = int(datetime(2026, 4, 14, 18, 30, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2026, 4, 14, 19, 5, tzinfo=timezone.utc).timestamp())
    
    candles = client.get_historical_data("NQ", start, end)
    print(f"Fetched {len(candles)} candles")
    for c in candles:
        if c.high > 25940 and c.low < 25980:
            print(f"Time: {datetime.fromtimestamp(c.timestamp, tz=timezone.utc)} UTC, Open: {c.open}, High: {c.high}, Low: {c.low}, Close: {c.close}")

if __name__ == '__main__':
    asyncio.run(run())
