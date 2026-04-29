import pytest
from datetime import datetime, timezone
from src.layer1_data.models import Candle
from src.layer3_strategy.models import OrderIntent
from src.layer4_execution.simulator import BacktestSimulator
from src.layer4_execution.data_vault import DataVault

def test_simulator_breakeven_trigger_bullish():
    vault = DataVault()
    sim = BacktestSimulator(vault)
    
    ts = datetime(2023, 1, 1, 10, 0, tzinfo=timezone.utc)
    
    # 1. Intent setup: Buy at 100, SL at 90, TP at 120
    # Breakeven trigger at 110, breakeven target at 100
    intent = OrderIntent(
        timestamp=ts,
        is_bullish=True,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit=120.0,
        strategy_id="test_be",
        theory_reference_ts=ts.timestamp(),
        breakeven_trigger_price=110.0,
        breakeven_target_price=100.0
    )
    
    sim.stage_order(intent)
    
    # 2. Fill order: Candle drops to 95 and closes at 105 (filled at 100)
    c1 = Candle(timestamp=ts, open=110.0, high=110.0, low=95.0, close=105.0, volume=100)
    sim.process_candle(c1)
    
    assert sim.active_pos is not None
    assert sim.active_pos.intent.entry_price == 100.0
    assert sim.active_pos.current_stop_loss == 90.0
    assert not sim.active_pos.breakeven_activated
    
    # 3. Trigger Breakeven: Candle goes to 111 (hits trigger 110), closes at 108
    c2 = Candle(timestamp=ts, open=105.0, high=111.0, low=105.0, close=108.0, volume=100)
    sim.process_candle(c2)
    
    assert sim.active_pos is not None
    assert sim.active_pos.breakeven_activated
    assert sim.active_pos.current_stop_loss == 100.0
    
    # 4. Hit Breakeven SL: Candle drops to 99, closes at 100. Stop loss (now 100.0) is hit.
    c3 = Candle(timestamp=ts, open=108.0, high=108.0, low=99.0, close=100.0, volume=100)
    sim.process_candle(c3)
    
    assert sim.active_pos is None
    assert len(vault.trades) == 1
    
    trade = vault.trades[0]
    assert trade.pnl_points == 0.0
    assert trade.win is False  # A breakeven is technically not a win
    assert trade.stop_loss == 100.0

def test_simulator_breakeven_trigger_bearish():
    vault = DataVault()
    sim = BacktestSimulator(vault)
    
    ts = datetime(2023, 1, 1, 10, 0, tzinfo=timezone.utc)
    
    # 1. Intent setup: Sell at 100, SL at 110, TP at 80
    # Breakeven trigger at 90, breakeven target at 100
    intent = OrderIntent(
        timestamp=ts,
        is_bullish=False,
        entry_price=100.0,
        stop_loss=110.0,
        take_profit=80.0,
        strategy_id="test_be",
        theory_reference_ts=ts.timestamp(),
        breakeven_trigger_price=90.0,
        breakeven_target_price=100.0
    )
    
    sim.stage_order(intent)
    
    # 2. Fill order: Candle goes to 105 and closes at 95 (filled at 100)
    c1 = Candle(timestamp=ts, open=90.0, high=105.0, low=90.0, close=95.0, volume=100)
    sim.process_candle(c1)
    
    assert sim.active_pos is not None
    assert sim.active_pos.intent.entry_price == 100.0
    assert sim.active_pos.current_stop_loss == 110.0
    assert not sim.active_pos.breakeven_activated
    
    # 3. Trigger Breakeven: Candle goes to 89 (hits trigger 90), closes at 92
    c2 = Candle(timestamp=ts, open=95.0, high=95.0, low=89.0, close=92.0, volume=100)
    sim.process_candle(c2)
    
    assert sim.active_pos is not None
    assert sim.active_pos.breakeven_activated
    assert sim.active_pos.current_stop_loss == 100.0
    
    # 4. Hit Breakeven SL: Candle rises to 101, closes at 100. Stop loss (now 100.0) is hit.
    c3 = Candle(timestamp=ts, open=92.0, high=101.0, low=92.0, close=100.0, volume=100)
    sim.process_candle(c3)
    
    assert sim.active_pos is None
    assert len(vault.trades) == 1
    
    trade = vault.trades[0]
    assert trade.pnl_points == 0.0
    assert trade.win is False
    assert trade.stop_loss == 100.0
