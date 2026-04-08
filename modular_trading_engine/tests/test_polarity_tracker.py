import pytest
from datetime import datetime, timezone
from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer2_theory.polarity_tracker import PolarityTracker, PolarityState

@pytest.fixture
def valid_origin_support():
    return TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.ORIGIN_LEVEL,
        is_bullish=True, # Support level
        price_high=100.0,
        price_low=95.0,
        status="active"
    )

@pytest.fixture
def valid_reverse_resistance():
    return TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.REVERSE_LEVEL,
        is_bullish=False, # Resistance level
        price_high=205.0,
        price_low=200.0,
        status="active"
    )

@pytest.fixture
def invalid_break_level():
    return TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.BREAK_LEVEL,
        is_bullish=True,
        price_high=100.0,
        price_low=95.0,
        status="active"
    )

def test_polarity_tracker_init(valid_origin_support, valid_reverse_resistance, invalid_break_level):
    # Should accept ORIGIN and REVERSE levels
    PolarityTracker(valid_origin_support)
    PolarityTracker(valid_reverse_resistance)
    
    # Should reject others
    with pytest.raises(ValueError):
        PolarityTracker(invalid_break_level)

def test_polarity_tracker_support_lifecycle(valid_origin_support):
    tracker = PolarityTracker(valid_origin_support)
    assert tracker.state == PolarityState.UNKNOWN
    
    # Candle trades above support (no hard close below)
    c1 = Candle(timestamp=1, open=105.0, high=110.0, low=101.0, close=108.0)
    tracker.process_candle(c1)
    
    assert tracker.state == PolarityState.ABOVE_POLARITY
    assert tracker.is_active is True
    
    # Candle pierces but does not hard close
    c2 = Candle(timestamp=2, open=98.0, high=99.0, low=90.0, close=96.0)
    tracker.process_candle(c2)
    assert tracker.state == PolarityState.ABOVE_POLARITY
    assert tracker.is_active is True
    
    # Candle hard closes below support -> polarity broken
    # Hard close logic: Support broken if both open and close are below low (95.0) AND it's a bearish candle
    hc_candle = Candle(timestamp=3, open=94.0, high=98.0, low=90.0, close=91.0)
    tracker.process_candle(hc_candle)
    
    assert tracker.state == PolarityState.BROKEN
    assert tracker.is_active is False

def test_polarity_tracker_resistance_lifecycle(valid_reverse_resistance):
    tracker = PolarityTracker(valid_reverse_resistance)
    
    # Candle trades below resistance
    c1 = Candle(timestamp=1, open=190.0, high=195.0, low=188.0, close=192.0)
    tracker.process_candle(c1)
    
    assert tracker.state == PolarityState.BELOW_POLARITY
    assert tracker.is_active is True
    
    # Hard close above resistance -> polarity broken
    # Resistance broken if both open and close above price_high (205.0), and bullish candle
    hc_candle = Candle(timestamp=2, open=206.0, high=210.0, low=205.5, close=209.0)
    tracker.process_candle(hc_candle)
    
    assert tracker.state == PolarityState.BROKEN
    assert tracker.is_active is False
