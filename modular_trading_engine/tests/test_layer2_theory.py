import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer2_theory.hard_close import is_hard_close
from src.layer2_theory.tested_state import is_tested, is_deep_dive

def build_candle(o: float, h: float, l: float, c: float) -> float:
    return Candle(timestamp=datetime.now(timezone.utc), open=o, high=h, low=l, close=c, volume=1.0)


def test_theorylevel_immutability():
    level = TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.HOLD_LEVEL,
        is_bullish=True,
        price_high=100.0,
        price_low=90.0,
        status="candidate"
    )
    with pytest.raises(ValidationError):
        level.status = "active"


def test_hard_close_support():
    ref = 100.0 # Example support line
    
    # 1. Wick breaches but body remains above -> False
    assert not is_hard_close(ref, build_candle(105, 110, 95, 102), is_support=True)
    # 2. Open below but close above -> False
    assert not is_hard_close(ref, build_candle(98, 105, 95, 102), is_support=True)
    # 3. Both Open and Close strictly below -> True (True Hard Close)
    assert is_hard_close(ref, build_candle(99, 100, 90, 95), is_support=True)
    # 4. Exact tie (touching the line without crossing both edges) -> False
    assert not is_hard_close(ref, build_candle(100, 100, 90, 100), is_support=True)


def test_hard_close_resistance():
    ref = 100.0 # Example resistance line
    
    # 1. Open and Close above -> True (True Hard Close breaking resistance)
    assert is_hard_close(ref, build_candle(101, 110, 101, 105), is_support=False)
    # 2. Breaches with wick but body below -> False
    assert not is_hard_close(ref, build_candle(95, 105, 90, 98), is_support=False)


def test_tested_state_support():
    support = TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.HOLD_LEVEL,
        is_bullish=True,
        price_high=110.0,
        price_low=100.0,
        status="active"
    )
    
    # Wick touches the very front (exactly 110)
    assert is_tested(support, build_candle(115, 120, 110.0, 115)) is True
    # Wick comes close, misses entirely
    assert is_tested(support, build_candle(115, 120, 110.01, 115)) is False
    # Wick penetrates deep inside
    assert is_tested(support, build_candle(115, 120, 105.0, 115)) is True
    
    # Deep dive penetrating the back (100)
    assert is_deep_dive(support, build_candle(105, 110, 99.9, 105)) is True
    assert is_deep_dive(support, build_candle(105, 110, 100.0, 105)) is False


from src.layer2_theory.hold_level_detector import find_all_support_hold_levels, find_all_resistance_hold_levels

def test_find_all_support_hold_levels():
    base_ts = 1500000000
    candles = [
        Candle(timestamp=datetime.fromtimestamp(base_ts, tz=timezone.utc), open=100, high=105, low=95, close=98),  # Bearish
        Candle(timestamp=datetime.fromtimestamp(base_ts + 60, tz=timezone.utc), open=98, high=102, low=95, close=96),  # Bearish
        Candle(timestamp=datetime.fromtimestamp(base_ts + 120, tz=timezone.utc), open=96, high=103, low=95, close=102),  # Bullish
        Candle(timestamp=datetime.fromtimestamp(base_ts + 180, tz=timezone.utc), open=102, high=106, low=100, close=105),  # Bullish
    ]
    
    levels = find_all_support_hold_levels(candles)
    
    assert len(levels) == 1
    support_hold = levels[0]
    
    assert support_hold.level_type == LevelType.HOLD_LEVEL
    assert support_hold.is_bullish is True
    assert support_hold.timestamp == candles[1].timestamp  # The last bearish candle before bullish
    assert support_hold.price_high == 102.0
    assert support_hold.price_low == 95.0
    assert support_hold.status == "identified"

def test_find_all_resistance_hold_levels():
    base_ts = 1500000000
    candles = [
        Candle(timestamp=datetime.fromtimestamp(base_ts, tz=timezone.utc), open=100, high=105, low=95, close=104),  # Bullish
        Candle(timestamp=datetime.fromtimestamp(base_ts + 60, tz=timezone.utc), open=104, high=108, low=102, close=107),  # Bullish
        Candle(timestamp=datetime.fromtimestamp(base_ts + 120, tz=timezone.utc), open=107, high=108, low=95, close=96),  # Bearish
        Candle(timestamp=datetime.fromtimestamp(base_ts + 180, tz=timezone.utc), open=96, high=98, low=90, close=91),  # Bearish
    ]
    
    levels = find_all_resistance_hold_levels(candles)
    
    assert len(levels) == 1
    resistance_hold = levels[0]
    
    assert resistance_hold.level_type == LevelType.HOLD_LEVEL
    assert resistance_hold.is_bullish is False
    assert resistance_hold.timestamp == candles[1].timestamp  # The last bullish candle before bearish
    assert resistance_hold.price_high == 108.0
    assert resistance_hold.price_low == 102.0
    assert resistance_hold.status == "identified"

from src.layer2_theory.break_level_detector import find_all_top_side_break_levels, find_all_bottom_side_break_levels

def test_find_all_top_side_break_levels():
    base_ts = 1500000000
    candles = [
        Candle(timestamp=datetime.fromtimestamp(base_ts, tz=timezone.utc), open=100, high=105, low=95, close=104),  # Bullish
        Candle(timestamp=datetime.fromtimestamp(base_ts + 60, tz=timezone.utc), open=104, high=108, low=102, close=102),  # Bearish
        Candle(timestamp=datetime.fromtimestamp(base_ts + 120, tz=timezone.utc), open=102, high=105, low=95, close=96),  # Bearish
        Candle(timestamp=datetime.fromtimestamp(base_ts + 180, tz=timezone.utc), open=96, high=98, low=90, close=91),  # Bearish
    ]
    
    levels = find_all_top_side_break_levels(candles)
    
    assert len(levels) == 1
    top_break = levels[0]
    
    assert top_break.level_type == LevelType.BREAK_LEVEL
    assert top_break.is_bullish is False  # Acts as resistance
    assert top_break.timestamp == candles[1].timestamp  # The first bearish candle
    assert top_break.price_high == 108.0
    assert top_break.price_low == 108.0
    assert top_break.status == "identified"

def test_find_all_bottom_side_break_levels():
    base_ts = 1500000000
    candles = [
        Candle(timestamp=datetime.fromtimestamp(base_ts, tz=timezone.utc), open=100, high=105, low=95, close=98),  # Bearish
        Candle(timestamp=datetime.fromtimestamp(base_ts + 60, tz=timezone.utc), open=98, high=102, low=95, close=101),  # Bullish
        Candle(timestamp=datetime.fromtimestamp(base_ts + 120, tz=timezone.utc), open=101, high=107, low=100, close=105),  # Bullish
        Candle(timestamp=datetime.fromtimestamp(base_ts + 180, tz=timezone.utc), open=105, high=110, low=102, close=108),  # Bullish
    ]
    
    levels = find_all_bottom_side_break_levels(candles)
    
    assert len(levels) == 1
    bottom_break = levels[0]
    
    assert bottom_break.level_type == LevelType.BREAK_LEVEL
    assert bottom_break.is_bullish is True  # Acts as support
    assert bottom_break.timestamp == candles[1].timestamp  # The first bullish candle
    assert bottom_break.price_high == 95.0
    assert bottom_break.price_low == 95.0
    assert bottom_break.status == "identified"

from src.layer2_theory.origin_state_machine import OriginTracker

def test_origin_state_machine_escalation_and_invalidation():
    # Setup a Break Level (support)
    base_ts = 1500000000
    break_level = TheoryLevel(
        timestamp=datetime.fromtimestamp(base_ts, tz=timezone.utc),
        level_type=LevelType.BREAK_LEVEL,
        is_bullish=True, # Support wall
        price_high=95.0,
        price_low=95.0,
        status="identified"
    )
    
    tracker = OriginTracker(break_level)
    
    assert tracker.test_count == 0
    assert tracker.waiting_opposite is True
    
    # Test 1: Separation via opposite close (bearish candle closes down)
    c1 = Candle(timestamp=datetime.fromtimestamp(base_ts + 60, tz=timezone.utc), open=100, high=102, low=98, close=96)
    c1._prev_green = False  # Simulating historical
    c1._prev_red = True
    tracker.process_candle(c1)
    
    # Test 2: Actually touching it sets waiting_opposite to False and increments hit if valid
    c2 = Candle(timestamp=datetime.fromtimestamp(base_ts + 120, tz=timezone.utc), open=96, high=100, low=95, close=98)
    tracker.process_candle(c2)
    assert tracker.level_data.level_type == LevelType.BREAK_LEVEL
    
    # Test 6: Hard Close -> Invalidation
    # Breaking support: bodily closing completely below 95.0 AND being bearish.
    c6 = Candle(timestamp=datetime.fromtimestamp(base_ts + 360, tz=timezone.utc), open=94, high=94, low=90, close=92)
    tracker.process_candle(c6)
    assert tracker.is_active is False
    assert tracker.level_data.status == "invalidated"
