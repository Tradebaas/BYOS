import pytest
from datetime import datetime, timezone
from src.layer1_data.models import Candle
from src.layer2_theory.market_state import MarketTheoryState
from src.layer2_theory.models import LevelType

def test_market_state_lifecycle():
    state = MarketTheoryState()
    
    assert len(state.get_active_origin_levels()) == 0
    assert len(state.get_active_reverse_levels()) == 0
    
    # 1. Provide candles that form a Hold Level (Support) structure
    # A bullish hold level forms when we have a low that is not broken by the next candle's body
    # Wait, the exact HoldLevelDetector logic in tests:
    # Need 2 candles. 
    # Candle 1: bearish (open > close). Low is 100.
    # Candle 2: bullish (close > open). Low is 102. 
    # Let's just use existing mocked detector logic or full L1 data.
    
    c1 = Candle(timestamp=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc), open=110.0, high=115.0, low=100.0, close=105.0)
    c2 = Candle(timestamp=datetime(2026, 1, 1, 10, 1, tzinfo=timezone.utc), open=105.0, high=112.0, low=102.0, close=110.0)
    
    state.process_candle(c1)
    state.process_candle(c2)
    
    # Should have a bullish Hold Level and thus a reverse tracker and range tracker spawned
    active_reverses = state.get_active_reverse_levels()
    assert len(active_reverses) == 1
    assert active_reverses[0].level_type == LevelType.HOLD_LEVEL
    assert active_reverses[0].is_bullish is True
    
    # Range trends should also be tracked
    assert len(state.get_active_range_trends()) == 1
    
    # No Break Levels formed yet (Break needs a specific structure of 2 identical direction candles usually, or whatever is in break_level_detector.py)
    # Check origin tracker is 0 for safety but depending on actual detector logic it might spawn one. Let's assume none for now based on standard tests.
    
    # Now simulate a Hard Close invalidation for the bullish Hold Level
    # Back of wall is the low: 100.0 from c1 (actually, the hold level low)
    # Let's say back_of_wall is 100.0. A hard close is open < 100 and close < 100 and is_bearish.
    c_invalid = Candle(timestamp=datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc), open=98.0, high=99.0, low=90.0, close=95.0)
    
    state.process_candle(c_invalid)
    
    # Cleanup should have occurred within process_candle for the bullish tracker
    # However, c2 (bullish) followed by c_invalid (bearish) just spawned a NEW Resistance (bearish) level.
    active_reverses = state.get_active_reverse_levels()
    bullish_reverses = [l for l in active_reverses if l.is_bullish]
    assert len(bullish_reverses) == 0
    # The new bearish level means there is now 1 active range trend tracker (bearish)
    assert len(state.get_active_range_trends()) == 1
    
    # And 1 bearish highlander
    highlanders = state.get_all_active_highlanders()
    assert len(highlanders) == 1
    assert highlanders[0].is_bullish is False

def test_market_state_get_highlanders():
    state = MarketTheoryState()
    
    # Simply test the getter logic when empty
    bull_high = state.get_all_active_highlanders(is_bullish=True)
    bear_high = state.get_all_active_highlanders(is_bullish=False)
    assert len(bull_high) == 0
    assert len(bear_high) == 0
