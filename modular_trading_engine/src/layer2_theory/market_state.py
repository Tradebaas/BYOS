from typing import List
from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer2_theory.reverse_level_tracker import ReverseTracker
from src.layer2_theory.trend_tracker import RangeTrendTracker, TrendLineTracker
from src.layer2_theory.origin_state_machine import OriginTracker
from src.layer2_theory.deep_dive_tracker import detect_deep_dive
from src.layer2_theory.pandoras_box_tracker import ScopeBoxTracker
from src.layer2_theory.polarity_tracker import PolarityTracker

class MarketTheoryState:
    """
    The Global Theory Board (Layer 2 Orchestrator).
    Accepts raw L1 Candles, detects base structures (Hold/Break) using a rolling buffer,
    spawns secondary trackers automatically, and bubbles them through all active trackers.
    Maintains a stateless, queryable unified L2 representation for Layer 3.
    """
    def __init__(self):
        # Candle buffer for base structure detection (Hold uses 2, Break uses 3)
        self.candle_buffer: List[Candle] = []
        
        # Active trackers
        self.reverse_trackers: List[ReverseTracker] = []
        self.range_trend_trackers: List[RangeTrendTracker] = []
        self.origin_trackers: List[OriginTracker] = []
        
        # State tracking for all levels
        self.all_theory_levels: List[TheoryLevel] = []

    def process_candle(self, candle: Candle):
        """
        Pass a new candle through the whole L2 ecosystem sequentially.
        """
        self.candle_buffer.append(candle)
        if len(self.candle_buffer) > 3:
            self.candle_buffer.pop(0)

        # 1. Base Detection
        new_levels = []
        
        curr = self.candle_buffer[-1]

        # Hold Level Detection via Candidates and Hard Close Validation
        # 1. Update candidates
        if curr.is_bullish:
            if getattr(self, 'resistance_candidate', None) is None or curr.high > self.resistance_candidate.high:
                self.resistance_candidate = curr
        elif curr.is_bearish:
            if getattr(self, 'support_candidate', None) is None or curr.low < self.support_candidate.low:
                self.support_candidate = curr

        # 2. Validate candidates via Hard Close
        if getattr(self, 'resistance_candidate', None) is not None:
            # Resistance Hold Level (Bullish candidate validated by Bearish Hard Close under its Low)
            # Only the CLOSE needs to break the low to validate the structure.
            if curr.is_bearish and curr.close < self.resistance_candidate.low:
                new_levels.append(TheoryLevel(
                    timestamp=self.resistance_candidate.timestamp,
                    level_type=LevelType.HOLD_LEVEL,
                    is_bullish=False,
                    price_high=self.resistance_candidate.high,
                    price_low=self.resistance_candidate.low,
                    price_open=self.resistance_candidate.open,
                    status="identified"
                ))
                self.resistance_candidate = None  # Reset after validation

        if getattr(self, 'support_candidate', None) is not None:
            # Support Hold Level (Bearish candidate validated by Bullish Hard Close above its High)
            # Only the CLOSE needs to break the high to validate the structure.
            if curr.is_bullish and curr.close > self.support_candidate.high:
                new_levels.append(TheoryLevel(
                    timestamp=self.support_candidate.timestamp,
                    level_type=LevelType.HOLD_LEVEL,
                    is_bullish=True,
                    price_high=self.support_candidate.high,
                    price_low=self.support_candidate.low,
                    price_open=self.support_candidate.open,
                    status="identified"
                ))
                self.support_candidate = None  # Reset after validation

        # Break Level Detection (needs last 3 candles)
        if len(self.candle_buffer) == 3:
            c1 = self.candle_buffer[0]
            c2 = self.candle_buffer[1]
            c3 = self.candle_buffer[2]
            
            # Top Side Break Level (Bullish -> Bearish -> Bearish)
            if c1.is_bullish and c2.is_bearish and c3.is_bearish:
                new_levels.append(TheoryLevel(
                    timestamp=c2.timestamp,
                    level_type=LevelType.BREAK_LEVEL,
                    is_bullish=False,
                    price_high=c2.high,
                    price_low=c2.high,
                    status="identified"
                ))
            # Bottom Side Break Level (Bearish -> Bullish -> Bullish)
            elif c1.is_bearish and c2.is_bullish and c3.is_bullish:
                new_levels.append(TheoryLevel(
                    timestamp=c2.timestamp,
                    level_type=LevelType.BREAK_LEVEL,
                    is_bullish=True,
                    price_high=c2.low,
                    price_low=c2.low,
                    status="identified"
                ))
            
        # 2. Spawning Secondary Trackers
        for level in new_levels:
            self.all_theory_levels.append(level)
            # When a new valid Hold Level is established, track Reverse and Range escalations
            if level.level_type == LevelType.HOLD_LEVEL:
                self.reverse_trackers.append(ReverseTracker(initial_level=level))
                self.range_trend_trackers.append(RangeTrendTracker(initial_level=level))
            
            # When a new valid Break Level is established, track Origin escalations
            elif level.level_type == LevelType.BREAK_LEVEL:
                self.origin_trackers.append(OriginTracker(initial_level=level))
                
        # 3. Escalation & Tracking for existing trackers
        for tracker in self.reverse_trackers:
            # An origin is considered 'valid' for this Hold Level if the MOST RECENT OriginTracker
            # has completed its 2 tests (creating the Origin Level) AND belongs to the SAME macro structure
            # (e.g., tracking a resistance ceiling Origin for a resistance Hold Level).
            related_origin_valid = any(
                ot.level_data.is_bullish == tracker.level_data.is_bullish and ot.test_count >= 2
                for ot in self.origin_trackers
            )
            tracker.process_candle(candle, origin_is_valid=related_origin_valid)
            
        for tracker in self.range_trend_trackers:
            tracker.process_candle(candle)
            
        for tracker in self.origin_trackers:
            tracker.process_candle(candle)
            
        # 4. Cleanup Memory (Remove dead trackers driven to invalidation by Hard Close)
        self.reverse_trackers = [t for t in self.reverse_trackers if t.is_active]
        self.range_trend_trackers = [t for t in self.range_trend_trackers if t.is_active]
        self.origin_trackers = [t for t in self.origin_trackers if t.is_active]
        
    def get_active_origin_levels(self) -> List[TheoryLevel]:
        """Returns all currently surviving Break Levels & Origin Levels within OriginTrackers."""
        return [t.level_data for t in self.origin_trackers]
        
    def get_active_reverse_levels(self) -> List[TheoryLevel]:
        """Returns all currently surviving Hold Levels & Reverse Levels within ReverseTrackers."""
        return [t.level_data for t in self.reverse_trackers]
        
    def get_active_range_trends(self) -> List[TheoryLevel]:
        """Returns all currently active structural base boundaries from RangeTrendTrackers."""
        return [t.level_data for t in self.range_trend_trackers]
        
    def get_all_active_highlanders(self, is_bullish: bool = None) -> List[TheoryLevel]:
        """
        Retrieves all active base structure boundaries.
        Filters by bullish (Support) or bearish (Resistance) if specified.
        """
        active_levels = self.get_active_origin_levels() + self.get_active_reverse_levels()
        
        if is_bullish is not None:
            active_levels = [l for l in active_levels if l.is_bullish == is_bullish]
            
        return active_levels
