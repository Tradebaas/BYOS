import pytest
from datetime import datetime, timezone

from src.layer1_data.models import Candle
from src.layer3_strategy.models import OrderIntent
from src.layer4_execution.data_vault import DataVault
from src.layer4_execution.simulator import BacktestSimulator

def build_candle(o: float, h: float, l: float, c: float) -> Candle:
    return Candle(timestamp=datetime.now(timezone.utc), open=o, high=h, low=l, close=c, volume=1.0)


def test_vault_statistical_aggregation():
    vault = DataVault()
    assert vault.generate_summary()['total_trades'] == 0


def test_simulator_limit_fill_and_tp():
    vault = DataVault()
    sim = BacktestSimulator(vault)
    
    intent = OrderIntent(
        timestamp=datetime.now(timezone.utc),
        is_bullish=True,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit=120.0,
        strategy_id="TEST_01",
        theory_reference_ts=0.0
    )
    sim.stage_order(intent)
    
    # 1. Price misses entry entirely
    sim.process_candle(build_candle(110, 115, 105, 108))
    assert sim.pending_intent is not None
    assert sim.active_pos is None
    
    # 2. Limit gets hit (Low = 95, meaning our 100.0 bid was taken)
    sim.process_candle(build_candle(105, 110, 95, 102))
    assert sim.pending_intent is None
    assert sim.active_pos is not None
    # Verify MAE/MFE update on the same candle that triggered the fill
    assert sim.active_pos.mfe == 110.0
    assert sim.active_pos.mae == 95.0
    
    # 3. Pullback pushing MAE lower, but not hitting SL (90.0)
    sim.process_candle(build_candle(102, 105, 92, 98))
    assert sim.active_pos.mae == 92.0
    
    # 4. Target hits (High = 125, beating our 120.0 Take Profit limit)
    sim.process_candle(build_candle(98, 125, 95, 120))
    
    assert sim.active_pos is None # Closed
    assert len(vault.trades) == 1
    
    trade = vault.trades[0]
    assert trade.win is True
    assert trade.pnl_points == 20.0
    assert trade.mfe == 125.0
    assert trade.mae == 92.0


def test_simulator_gray_candle_worst_case():
    """
    Ensures that if a 1M candle is so massive that it hits both the SL and TP, 
    the simulator strictly forces it to evaluate as a Loss (Defensive constraint).
    """
    vault = DataVault()
    sim = BacktestSimulator(vault)
    
    intent = OrderIntent(
        timestamp=datetime.now(timezone.utc),
        is_bullish=False, # Short Limit!
        entry_price=100.0,
        stop_loss=110.0,
        take_profit=90.0,
        strategy_id="GRAY",
        theory_reference_ts=0.0
    )
    sim.stage_order(intent)
    
    # Fill Short at exactly 100.0 Ask
    sim.process_candle(build_candle(95, 100, 95, 98))
    assert sim.active_pos is not None
    
    # Process "Gray Candle" -> Huge wick that travels from 80 to 120. 
    # Hits both TP (90.0) and SL (110.0)
    sim.process_candle(build_candle(98, 120, 80, 98))
    
    # Must evaluate as a strict LOSS
    assert len(vault.trades) == 1
    trade = vault.trades[0]
    assert trade.win is False
    assert trade.pnl_points == -10.0
