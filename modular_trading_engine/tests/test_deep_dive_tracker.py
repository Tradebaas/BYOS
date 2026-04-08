import pytest
from datetime import datetime, timezone
from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer2_theory.deep_dive_tracker import detect_deep_dive

@pytest.fixture
def support_level():
    return TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.HOLD_LEVEL,
        is_bullish=True, # Support level
        price_high=100.0,
        price_low=95.0,
        status="active"
    )

@pytest.fixture
def resistance_level():
    return TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.ORIGIN_LEVEL,
        is_bullish=False, # Resistance level
        price_high=205.0,
        price_low=200.0,
        status="active"
    )

def test_deep_dive_support_pierce_no_hard_close(support_level):
    # Support low is 95.0
    # Candle low is 90.0, so it pierces.
    # It closes at 96.0, which is > 95.0, so NO hard close.
    c = Candle(timestamp=1, open=98.0, high=99.0, low=90.0, close=96.0)
    assert detect_deep_dive(support_level, c) is True

def test_deep_dive_support_no_pierce(support_level):
    # Doesn't pierce 95.0 at all
    c = Candle(timestamp=1, open=98.0, high=99.0, low=95.1, close=96.0)
    assert detect_deep_dive(support_level, c) is False

def test_deep_dive_support_hard_close(support_level):
    # Pierces and also hard closes (open and close < 95.0, bearish candle)
    c = Candle(timestamp=1, open=94.0, high=94.5, low=90.0, close=91.0)
    # This is a hard close, so it should NOT be classified as just a deep dive.
    assert detect_deep_dive(support_level, c) is False

def test_deep_dive_resistance_pierce_no_hard_close(resistance_level):
    # Resistance high is 205.0
    # Candle high is 210.0, so it pierces.
    # It closes at 203.0, which is < 205.0, so NO hard close.
    c = Candle(timestamp=1, open=200.0, high=210.0, low=199.0, close=203.0)
    assert detect_deep_dive(resistance_level, c) is True

def test_deep_dive_resistance_hard_close(resistance_level):
    # Pierces and hard closes (open and close > 205.0, bullish candle)
    c = Candle(timestamp=1, open=206.0, high=210.0, low=205.5, close=209.0)
    assert detect_deep_dive(resistance_level, c) is False
