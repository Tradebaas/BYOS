import pytest
from datetime import datetime, timezone, timedelta
from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer2_theory.trend_tracker import TrendLineTracker, RangeTrendTracker

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

def test_range_trend_tracker_hits_and_invalidation(base_hold_level):
    tracker = RangeTrendTracker(base_hold_level)
    assert tracker.hits == 0
    assert tracker.is_active is True
    
    # Hit
    c1 = Candle(timestamp=datetime(2026, 1, 1, 10, 1, tzinfo=timezone.utc), open=105.0, high=109.0, low=98.0, close=100.0)
    tracker.process_candle(c1)
    assert tracker.hits == 1
    
    # Separation
    c2 = Candle(timestamp=datetime(2026, 1, 1, 10, 2, tzinfo=timezone.utc), open=100.0, high=105.0, low=101.0, close=104.0)
    tracker.process_candle(c2)
    assert tracker.hits == 1
    
    # Hit
    c3 = Candle(timestamp=datetime(2026, 1, 1, 10, 3, tzinfo=timezone.utc), open=104.0, high=104.0, low=99.5, close=102.0)
    tracker.process_candle(c3)
    assert tracker.hits == 2
    
    # Hard Close Invalidation
    c4 = Candle(timestamp=datetime(2026, 1, 1, 10, 4, tzinfo=timezone.utc), open=94.0, high=94.5, low=90.0, close=91.0)
    tracker.process_candle(c4)
    assert tracker.is_active is False

def test_trend_line_tracker_support_diagonal():
    t1 = datetime(2026, 1, 1, 10, 0, 10, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 10, 0, 20, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 1, 10, 0, 30, tzinfo=timezone.utc)
    t4 = datetime(2026, 1, 1, 10, 0, 40, tzinfo=timezone.utc)
    
    # Slope = (110 - 100) / 10s = 1.0 per sec
    tracker = TrendLineTracker(point1=(t1, 100.0), point2=(t2, 110.0), is_support=True)
    
    assert tracker.slope == 1.0
    
    # At t3, expected line price is: 100 + 1.0 * 20 = 120.0
    assert tracker.get_price_at_timestamp(t3) == 120.0
    
    # Process candle at t3 that bounces off the trendline (low is 120.5)
    c1 = Candle(timestamp=t3, open=125.0, high=126.0, low=120.5, close=124.0)
    tracker.process_candle(c1)
    assert tracker.is_active is True
    
    # Hard close below trendline at t4 (line should be at 130.0)
    # Support hard close means both open and close < 130.0, and candle is bearish
    hc_candle = Candle(timestamp=t4, open=129.0, high=135.0, low=120.0, close=125.0)
    tracker.process_candle(hc_candle)
    assert tracker.is_active is False

def test_trend_line_tracker_resistance_diagonal():
    t1 = datetime(2026, 1, 1, 10, 0, 10, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 10, 0, 20, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 1, 10, 0, 30, tzinfo=timezone.utc)
    
    # Point 1: 200, Point 2: 190 (downward trending resistance line)
    # Slope = (190 - 200) / 10s = -1.0 per sec
    tracker = TrendLineTracker(point1=(t1, 200.0), point2=(t2, 190.0), is_support=False)
    
    assert tracker.slope == -1.0
    
    # At t3, expected line price is: 200 + (-1.0) * 20 = 180.0
    
    # Hard close above trendline at t3
    # Resistance hard close means both open and close > 180.0, and candle is bullish
    hc_candle = Candle(timestamp=t3, open=181.0, high=190.0, low=170.0, close=185.0)
    tracker.process_candle(hc_candle)
    assert tracker.is_active is False
