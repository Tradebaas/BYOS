import sys
from modular_trading_engine.src.layer4_execution.auth import fetch_topstepx_jwt
import requests
import asyncio

async def test():
    jwt = await fetch_topstepx_jwt()
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"})
    r = s.post("https://api.topstepx.com/api/Contract/search", json={"live": False, "searchText": "NQ"})
    print(r.json())
asyncio.run(test())
