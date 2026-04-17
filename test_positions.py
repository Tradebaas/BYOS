import sys
from modular_trading_engine.src.layer4_execution.auth import fetch_topstepx_jwt
from modular_trading_engine.src.layer4_execution.topstep_client import TopstepClient
from modular_trading_engine.src.layer4_execution.models_broker import TopstepCredentials
import asyncio

async def test():
    jwt = await fetch_topstepx_jwt()
    # load config
    import json
    with open('modular_trading_engine/execution_config.json', 'r') as f:
        conf = json.load(f)
    print(conf)
    accounts = conf['accounts']
    for acc in accounts:
        creds = TopstepCredentials(account_id=acc['account_id'], jwt_token=jwt)
        client = TopstepClient(creds)
        print("Positions:", client.get_positions())
        print("Orders:", client.get_orders())

asyncio.run(test())
