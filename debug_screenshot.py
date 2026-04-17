import asyncio
from datetime import datetime
from modular_trading_engine.src.layer4_execution.topstep_client import TopstepClient
from modular_trading_engine.src.layer1_data.models import Candle

async def run():
    client = TopstepClient(is_paper=False)
    # 2026-04-14 17:30 UTC = 1776187800
    start = int(datetime(2026, 4, 14, 17, 30).timestamp())
    end = int(datetime(2026, 4, 14, 19, 00).timestamp())
    
    candles = client.get_historical_data("NQ", start, end)
    print(f"Fetched {len(candles)} candles")
    for c in candles:
        # We are looking for high around 25969, and open around 25964 
        if c.high > 25950 and c.low < 25980:
            print(f"{datetime.fromtimestamp(c.timestamp)}: O:{c.open} H:{c.high} L:{c.low} C:{c.close}")

asyncio.run(run())
