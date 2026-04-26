from typing import List
from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer2_theory.origin_state_machine import OriginTracker
from src.layer2_theory.hard_close import is_hard_close

class MarketTheoryState:
    """
    The Global Theory Board (Layer 2 Orchestrator).
    Accepts raw L1 Candles, detects base structures (Hold/Break) using a rolling buffer,
    spawns origin trackers automatically, and maintains history.
    """
    def __init__(self):
        # Full history for retroactive dynamic searches
        self.history: List[Candle] = []

        # Candle buffer for base structure detection
        self.candle_buffer: List[Candle] = []
        
        # Active trackers
        self.origin_trackers: List[OriginTracker] = []
        
        # State tracking for all levels
        self.all_theory_levels: List[TheoryLevel] = []

        # Hold level candidates
        self.resistance_candidate = None
        self.support_candidate = None

    def process_candle(self, candle: Candle):
        """
        Pass a new candle through the whole L2 ecosystem sequentially.
        """
        self.history.append(candle)
        if len(self.history) > 20000:
            self.history.pop(0)

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
        if self.resistance_candidate is not None:
            # Resistance Hold Level (Bullish candidate validated by Bearish Hard Close under its Low)
            if is_hard_close(self.resistance_candidate.low, curr, is_support=True):
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

        if self.support_candidate is not None:
            # Support Hold Level (Bearish candidate validated by Bullish Hard Close above its High)
            if is_hard_close(self.support_candidate.high, curr, is_support=False):
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

        # Break Level Detection (Sequence Based: Bullish=red, green, green / Bearish=green, red, red)
        if len(self.candle_buffer) == 3:
            c1, c2, c3 = self.candle_buffer
            
            # Resistance Break Level (Bearish Break: green, red, red -> take high of red(1))
            if c1.is_bullish and c2.is_bearish and c3.is_bearish:
                new_levels.append(TheoryLevel(
                    timestamp=c2.timestamp,
                    level_type=LevelType.BREAK_LEVEL,
                    is_bullish=False,
                    price_high=c2.high,
                    price_low=c2.high,
                    price_open=c2.open,
                    status="identified"
                ))
            # Support Break Level (Bullish Break: red, green, green -> take low of green(1))
            elif c1.is_bearish and c2.is_bullish and c3.is_bullish:
                new_levels.append(TheoryLevel(
                    timestamp=c2.timestamp,
                    level_type=LevelType.BREAK_LEVEL,
                    is_bullish=True,
                    price_high=c2.low,
                    price_low=c2.low,
                    price_open=c2.open,
                    status="identified"
                ))
            
        # 2. Spawning Secondary Trackers
        for level in new_levels:
            self.all_theory_levels.append(level)
            
            # When a new valid Break Level is established, track Origin escalations
            if level.level_type == LevelType.BREAK_LEVEL:
                self.origin_trackers.append(OriginTracker(initial_level=level))
                
        # Protect memory leakage during prolonged uptime (max history matches self.history constraint)
        if len(self.all_theory_levels) > 20000:
            self.all_theory_levels.pop(0)
                
        # 3. Escalation & Tracking for existing trackers
        for tracker in self.origin_trackers:
            tracker.process_candle(candle)
            
        # 4. Cleanup Memory (Remove dead trackers driven to invalidation by Hard Close)
        self.origin_trackers = [t for t in self.origin_trackers if t.is_active]
        
    def get_active_origin_levels(self) -> List[TheoryLevel]:
        """Returns all currently surviving Break Levels & Origin Levels within OriginTrackers."""
        return [t.level_data for t in self.origin_trackers]
        
    def get_all_active_highlanders(self, is_bullish: bool = None) -> List[TheoryLevel]:
        """
        Retrieves all active base structure boundaries.
        Filters by bullish (Support) or bearish (Resistance) if specified.
        """
        active_levels = self.get_active_origin_levels()
        
        if is_bullish is not None:
            active_levels = [l for l in active_levels if l.is_bullish == is_bullish]
            
        return active_levels
