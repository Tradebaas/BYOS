import pytest
from datetime import datetime, timezone
from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer2_theory.reverse_level_tracker import ReverseTracker

@pytest.fixture
def base_hold_level():
    return TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.HOLD_LEVEL,
        is_bullish=True, # Support level
        price_high=100.0,
        price_low=95.0,
        status="active"
    )

def test_reverse_tracker_requires_hold_level():
    bad_level = TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.BREAK_LEVEL,
        is_bullish=True,
        price_high=100.0,
        price_low=95.0,
        status="active"
    )
    with pytest.raises(ValueError):
        ReverseTracker(bad_level)

def test_reverse_tracker_escalation(base_hold_level):
    tracker = ReverseTracker(base_hold_level)
    assert tracker.hits == 0
    assert tracker.level_data.level_type == LevelType.HOLD_LEVEL
    
    # 1. Separation candle (does not hit the support of 100.0-95.0)
    c1 = Candle(timestamp=1, open=105.0, high=110.0, low=101.0, close=108.0)
    tracker.process_candle(c1)
    assert tracker.hits == 0
    
    # 2. Hit candle (low touches 98.0)
    c2 = Candle(timestamp=2, open=108.0, high=109.0, low=98.0, close=100.0)
    tracker.process_candle(c2)
    assert tracker.hits == 1
    assert tracker.level_data.level_type == LevelType.HOLD_LEVEL
    
    # 3. Hit without separation (should be ignored for escalation)
    c3 = Candle(timestamp=3, open=100.0, high=102.0, low=99.0, close=101.0)
    tracker.process_candle(c3)
    assert tracker.hits == 1
    
    # 4. Another Separation candle
    c4 = Candle(timestamp=4, open=101.0, high=105.0, low=102.0, close=104.0)
    tracker.process_candle(c4)
    assert tracker.hits == 1
    
    # 5. Second Independent Hit
    c5 = Candle(timestamp=5, open=104.0, high=104.0, low=99.5, close=102.0)
    tracker.process_candle(c5)
    assert tracker.hits == 2
    assert tracker.level_data.level_type == LevelType.REVERSE_LEVEL

def test_reverse_tracker_hard_close_invalidation(base_hold_level):
    tracker = ReverseTracker(base_hold_level)
    
    # Hard close for bullish (support) means closing BELOW the price_low (95.0)
    # Both open and close must be < 95.0
    hc_candle = Candle(timestamp=6, open=94.0, high=99.0, low=90.0, close=91.0)
    
    tracker.process_candle(hc_candle)
    
    assert tracker.is_active is False
    assert tracker.level_data.status == "invalidated"

    # Further candles should be ignored
    c_ignore = Candle(timestamp=7, open=105.0, high=110.0, low=101.0, close=108.0)
    tracker.process_candle(c_ignore)
    assert tracker.is_active is False 
