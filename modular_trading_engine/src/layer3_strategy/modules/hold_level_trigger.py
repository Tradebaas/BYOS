from typing import Any
from src.layer3_strategy.modules.base import BaseStrategyModule
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer2_theory.models import TheoryLevel, LevelType

class RetroScannerTracker:
    def __init__(self, level_data: TheoryLevel):
        self.level_data = level_data

class VirginHoldLevelTrigger(BaseStrategyModule):
    def process(self, context: PipelineContext) -> None:
        # If polarity is blocked (e.g. Highlander limit exceeded), setup_candidates remains empty
        if context.active_polarity_is_bullish is None:
            return
            
        history = context.theory_state.history
        if not history:
            return
            
        # Get active Origin Levels matching polarity
        highlanders = context.theory_state.get_all_active_highlanders(is_bullish=context.active_polarity_is_bullish)
        if not highlanders:
            return
            
        tradable_trackers = []
        max_tests = self.params.get('max_level_tests_allowed', 3)
        from src.layer2_theory.models import LevelType
        for ot in context.theory_state.origin_trackers:
            if ot.is_active and ot.level_data.level_type == LevelType.ORIGIN_LEVEL:
                if ot.level_data.is_bullish == context.active_polarity_is_bullish:
                    if getattr(ot, 'test_count', 0) <= max_tests:
                        tradable_trackers.append(ot)
                        
        if not tradable_trackers:
            return
            
        active_origin_tracker = tradable_trackers[-1] # Strategy: trade on the newest valid Origin
        active_origin = active_origin_tracker.level_data
        
        # Timing rule: We ONLY scan for a valid hold level within a window of max 45 candles
        # starting from the moment of the LAST test on this Origin Level.
        is_acquisition_window = False
        if hasattr(active_origin_tracker, 'test_history') and active_origin_tracker.test_history:
            last_test_ts = active_origin_tracker.test_history[-1][0]
            last_test_idx = None
            
            # Find index of last test
            for i in reversed(range(len(history))):
                if history[i].timestamp == last_test_ts:
                    last_test_idx = i
                    break
            
            if last_test_idx is not None:
                candles_since_test = (len(history) - 1) - last_test_idx
                # We enforce the 45 candle search window, and require at least test 2
                if 0 <= candles_since_test <= 45 and active_origin_tracker.test_count >= 2:
                    is_acquisition_window = True
                    
        if not is_acquisition_window:
            # TTL expired or not yet valid: skip hold level processing for this origin
            return
            
        # Extract the segment of history to scan: from Origin Creation up to Current Candle
        history = context.theory_state.history
        start_idx = 0
        for i, c in enumerate(history):
            if c.timestamp == active_origin.timestamp:
                start_idx = i
                break
                
        # Forward scan matching Pine's state machine
        cand_open, cand_low, cand_high, cand_c = None, None, None, None
        hold_open, hold_low, hold_high, hold_c = None, None, None, None
        hold_valid_state = False
        hold_tested_state = False
        is_break_up = not context.active_polarity_is_bullish  # Pine script: is_break_up=true means Resistance Break (Bearish Origin)
        lvl_price = active_origin.price_high if is_break_up else active_origin.price_low
        
        for i in range(start_idx, len(history) - 1):
            c = history[i]
            is_bull = c.is_bullish
            is_bear = c.is_bearish
            o, h, l, cl = c.open, c.high, c.low, c.close
            
            if is_break_up:
                # Bearish Origin (Resistance)
                if is_bull and o < lvl_price:
                    if cand_open is None or o > cand_open:
                        cand_open, cand_low, cand_high, cand_c = o, l, h, c
                
                if hold_valid_state:
                    if is_bull and o > hold_open and cl > hold_open:
                        hold_valid_state = False
                        hold_tested_state = False
                        hold_open = None
                    else:
                        if h >= hold_low and l <= hold_open:
                            hold_tested_state = True
                            
                    if cand_open is not None and is_bear and o < cand_low and cl < cand_low:
                        if hold_open is None or cand_open > hold_open:
                            hold_valid_state = True
                            hold_tested_state = False
                            hold_open, hold_low, hold_high, hold_c = cand_open, cand_low, cand_high, cand_c
                else:
                    if cand_open is not None and is_bear and o < cand_low and cl < cand_low:
                        hold_valid_state = True
                        hold_tested_state = False
                        hold_open, hold_low, hold_high, hold_c = cand_open, cand_low, cand_high, cand_c
                        
            else:
                # Bullish Origin (Support)
                if is_bear and o > lvl_price:
                    if cand_open is None or o < cand_open:
                        cand_open, cand_low, cand_high, cand_c = o, l, h, c
                
                if hold_valid_state:
                    if is_bear and o < hold_open and cl < hold_open:
                        hold_valid_state = False
                        hold_tested_state = False
                        hold_open = None
                    else:
                        if h >= hold_open and l <= hold_high:
                            hold_tested_state = True
                            
                    if cand_open is not None and is_bull and o > cand_high and cl > cand_high:
                        if hold_open is None or cand_open < hold_open:
                            hold_valid_state = True
                            hold_tested_state = False
                            hold_open, hold_low, hold_high, hold_c = cand_open, cand_low, cand_high, cand_c
                else:
                    if cand_open is not None and is_bull and o > cand_high and cl > cand_high:
                        hold_valid_state = True
                        hold_tested_state = False
                        hold_open, hold_low, hold_high, hold_c = cand_open, cand_low, cand_high, cand_c

        if hold_valid_state and not hold_tested_state and hold_c is not None:
            # We found a valid, untested hold level matching Pine logic.
            level_data = TheoryLevel(
                timestamp=context.timestamp, # Track TTL dynamically from Moment of Acquisition
                level_type=LevelType.HOLD_LEVEL,
                is_bullish=context.active_polarity_is_bullish, # Note: if is_break_up is True -> Support? No, Bearish Resistance
                price_high=hold_high,
                price_low=hold_low,
                price_open=hold_open,
                status="identified"
            )
            context.setup_candidates.append(RetroScannerTracker(level_data))
        elif hold_valid_state and hold_tested_state:
            # print(f"[{context.timestamp}] Hold level found but TESTED")
            pass


