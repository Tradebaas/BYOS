from datetime import datetime
import pytest
from src.layer3_strategy.models import OrderIntent
from src.layer4_execution.models_broker import TopstepCredentials
from src.layer4_execution.topstep_client import TopstepClient

def test_long_oco_ticks_formatting():
    """
    Test that a LONG order (Bullish) correct converts taking:
    SL distance as NEGATIVE ticks
    TP distance as POSITIVE ticks
    """
    client = TopstepClient(credentials=TopstepCredentials(account_id=123, jwt_token="xyz"))
    
    intent = OrderIntent(
        timestamp=datetime.now(),
        is_bullish=True, # Long
        entry_price=15000.0,
        stop_loss=14990.0,   # 10 pts below = -40 ticks
        take_profit=15015.0, # 15 pts above = +60 ticks
        strategy_id="TEST",
        theory_reference_ts=0.0
    )
    
    payload = client._build_payload(intent, contract_id="CON.1", size=1)
    
    assert payload["side"] == 0 # 0 is Buy
    assert payload["contractId"] == "CON.1"
    assert payload["limitPrice"] == 15000.0
    
    # Verify strict math ticks
    assert payload["stopLossBracket"]["ticks"] == -40
    assert payload["takeProfitBracket"]["ticks"] == 60


def test_short_oco_ticks_formatting():
    """
    Test that a SHORT order (Bearish) correct converts taking:
    SL distance as POSITIVE ticks (because SL is ABOVE entry for short)
    TP distance as NEGATIVE ticks (because TP is BELOW entry for short)
    """
    client = TopstepClient(credentials=TopstepCredentials(account_id=123, jwt_token="xyz"))
    
    intent = OrderIntent(
        timestamp=datetime.now(),
        is_bullish=False, # Short
        entry_price=15000.0,
        stop_loss=15010.0,   # 10 pts above = +40 ticks
        take_profit=14985.0, # 15 pts below = -60 ticks
        strategy_id="TEST",
        theory_reference_ts=0.0
    )
    
    payload = client._build_payload(intent, contract_id="CON.1", size=1)
    
    assert payload["side"] == 1 # 1 is Sell
    assert payload["limitPrice"] == 15000.0
    
    # Verify strict math ticks
    assert payload["stopLossBracket"]["ticks"] == 40
    assert payload["takeProfitBracket"]["ticks"] == -60


def test_decimal_rounding_ticks():
    """
    Ensure the tick formula correctly maps 0.25 tick boundaries.
    """
    client = TopstepClient(credentials=TopstepCredentials(account_id=123, jwt_token="xyz"))
    
    intent = OrderIntent(
        timestamp=datetime.now(),
        is_bullish=True,
        entry_price=15000.0,
        stop_loss=14998.25, # 1.75 pts below = -7 ticks
        take_profit=15002.50, # 2.5 pts above = 10 ticks
        strategy_id="TEST",
        theory_reference_ts=0.0
    )
    payload = client._build_payload(intent, contract_id="CON.1", size=1)
    
    assert payload["stopLossBracket"]["ticks"] == -7
    assert payload["takeProfitBracket"]["ticks"] == 10
