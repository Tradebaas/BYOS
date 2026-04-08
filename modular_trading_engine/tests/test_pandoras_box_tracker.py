import pytest
from datetime import datetime, timezone
from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer2_theory.pandoras_box_tracker import ScopeBoxTracker, PandoraState

@pytest.fixture
def floor_level():
    return TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.HOLD_LEVEL,
        is_bullish=True, # Support level / floor
        price_high=100.0,
        price_low=95.0,
        status="active"
    )

@pytest.fixture
def ceiling_level():
    return TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.HOLD_LEVEL,
        is_bullish=False, # Resistance level / ceiling
        price_high=205.0,
        price_low=200.0,
        status="active"
    )

def test_scope_box_tracker_validation(floor_level, ceiling_level):
    # Must accept valid bullish floor and bearish ceiling
    ScopeBoxTracker(floor_level, ceiling_level)
    
    # Must reject if ceiling is passed as floor
    with pytest.raises(ValueError):
        ScopeBoxTracker(ceiling_level, floor_level)

def test_scope_box_stays_inside(floor_level, ceiling_level):
    tracker = ScopeBoxTracker(floor_level, ceiling_level)
    assert tracker.state == PandoraState.INSIDE_PANDORA
    
    # Candle bounces between 95 and 205
    c1 = Candle(timestamp=1, open=150.0, high=190.0, low=100.0, close=160.0)
    tracker.process_candle(c1)
    
    assert tracker.is_active is True
    assert tracker.state == PandoraState.INSIDE_PANDORA

def test_scope_box_escapes_up(floor_level, ceiling_level):
    tracker = ScopeBoxTracker(floor_level, ceiling_level)
    
    # Hard close above ceiling (high is 205.0)
    # Both open and close must be > 205.0, and candle bullish
    hc_candle = Candle(timestamp=1, open=206.0, high=210.0, low=205.5, close=209.0)
    tracker.process_candle(hc_candle)
    
    assert tracker.is_active is False
    assert tracker.state == PandoraState.ESCAPED_UP

def test_scope_box_escapes_down(floor_level, ceiling_level):
    tracker = ScopeBoxTracker(floor_level, ceiling_level)
    
    # Hard close below floor (low is 95.0)
    # Both open and close must be < 95.0, and candle bearish
    hc_candle = Candle(timestamp=1, open=94.0, high=95.0, low=90.0, close=91.0)
    tracker.process_candle(hc_candle)
    
    assert tracker.is_active is False
    assert tracker.state == PandoraState.ESCAPED_DOWN
