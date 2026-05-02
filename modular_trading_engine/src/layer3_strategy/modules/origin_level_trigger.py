import logging
from typing import List, Any
from src.layer3_strategy.modules.base import BaseStrategyModule
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer2_theory.models import TheoryLevel, LevelType

logger = logging.getLogger(__name__)

class RetroScannerTrackerWrapper:
    """
    Wrapper to match the interface expected by RATLimitOrder.
    RATLimitOrder expects objects with a .level_data attribute containing a TheoryLevel.
    """
    def __init__(self, level_data: TheoryLevel):
        self.level_data = level_data

class OriginLevelTrigger(BaseStrategyModule):
    """
    Scans the MarketTheoryState for Break Levels that have exactly 1 test
    and are 'waiting_retest' (which means the level has separated/formed an air bubble).
    These are the textbook 'Origin Levels' ready for entry on Test 2.
    """
    def process(self, context: PipelineContext) -> None:
        history = context.theory_state.history
        if not history:
            return
            
        trackers = context.theory_state.origin_trackers
        
        # Premium/Discount Filtering logic (Optional, default 0 means disabled)
        pd_window_size = self.params.get('premium_discount_window_size', 0)
        current_idx = len(history) - 1
        
        midpoint = None
        if pd_window_size > 0:
            eval_start_idx = max(0, current_idx - pd_window_size)
            eval_candles = history[eval_start_idx:current_idx+1]
            if eval_candles:
                range_high = max(ck.high for ck in eval_candles)
                range_low = min(ck.low for ck in eval_candles)
                midpoint = (range_high + range_low) / 2
        
        for tracker in trackers:
            # We strictly want ORIGIN Break Levels that are on exactly 1 test and waiting for their 2nd touch.
            if tracker.level_data.level_type != LevelType.ORIGIN_BREAK_LEVEL:
                continue
                
            if tracker.level_data.status == "invalidated":
                continue
                
            if tracker.test_count == 1 and tracker.can_be_tested:
                lvl = tracker.level_data
                
                # Evaluate Premium / Discount Filter if enabled
                if midpoint is not None:
                    current_close = history[-1].close
                    if lvl.is_bullish:
                        # Long setup: we only buy in Discount (current close below midpoint)
                        if current_close > midpoint:
                            continue
                    else:
                        # Short setup: we only sell in Premium (current close above midpoint)
                        if current_close < midpoint:
                            continue
                            
                # If we passed filters, emit a candidate for RATLimitOrder.
                # Notice we use the EXACT boundaries from the theory level.
                context.setup_candidates.append(RetroScannerTrackerWrapper(lvl))
