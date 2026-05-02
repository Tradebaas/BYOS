import logging
from typing import List, Any
from src.layer3_strategy.modules.base import BaseStrategyModule
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer2_theory.models import TheoryLevel, LevelType

logger = logging.getLogger(__name__)

class RetroScannerTrackerWrapper:
    def __init__(self, level_data: TheoryLevel):
        self.level_data = level_data

class OriginHoldLevelTrigger(BaseStrategyModule):
    """
    Scans for valid Origin Levels (test_count >= 2) that are rejected by a fresh Hold Level structure.
    A Hold Level structure is a 3-candle sequence (e.g., Green, Red, Red for short) validated by a Hard Close.
    If the Hold Level forms within 'origin_proximity_points' of the Origin Level, a limit order intent
    is emitted on the Open of the Hold Level.
    """
    def find_blocks(self, history: List[Any], start_idx: int, is_bullish: bool):
        """
        Calculates all generic 3-candle Induction/Structural blocks in the range.
        For Short: Green (Hold), Red (Break), Red (Hard Close).
        For Long: Red (Hold), Green (Break), Green (Hard Close).
        """
        blocks = []
        end_idx = len(history)
        
        for i in range(start_idx, end_idx - 2):
            c1 = history[i] # The Hold Level Candle
            
            if not is_bullish:
                if not c1.is_bullish: continue
                c2 = history[i+1]
                if not c2.is_bearish: continue
                c3 = history[i+2]
                if not c3.is_bearish: continue
                
                # Scan ahead for the Hard Close
                hard_close_idx = -1
                for j in range(i+2, min(i+15, end_idx)):
                    cj = history[j]
                    if cj.is_bearish and cj.open < c1.low and cj.close < c1.low:
                        hard_close_idx = j
                        break
                    if cj.high >= c2.high: # Structure invalidated by pushing past Break Level
                        break
                
                if hard_close_idx != -1:
                    block_high = max(history[k].high for k in range(i, hard_close_idx + 1))
                    blocks.append({
                        'type': 'short',
                        'hold_front': c1.low,
                        'hold_back': c1.high,
                        'hold_entry': c1.open,
                        'break': c2.high,
                        'block_extreme': block_high,
                        'c1_idx': i,
                        'hc_idx': hard_close_idx
                    })
            else:
                if not c1.is_bearish: continue
                c2 = history[i+1]
                if not c2.is_bullish: continue
                c3 = history[i+2]
                if not c3.is_bullish: continue
                
                hard_close_idx = -1
                for j in range(i+2, min(i+15, end_idx)):
                    cj = history[j]
                    if cj.is_bullish and cj.open > c1.high and cj.close > c1.high:
                        hard_close_idx = j
                        break
                    if cj.low <= c2.low:
                        break
                        
                if hard_close_idx != -1:
                    block_low = min(history[k].low for k in range(i, hard_close_idx + 1))
                    blocks.append({
                        'type': 'long',
                        'hold_front': c1.high,
                        'hold_back': c1.low,
                        'hold_entry': c1.open,
                        'break': c2.low,
                        'block_extreme': block_low,
                        'c1_idx': i,
                        'hc_idx': hard_close_idx
                    })
                    
        return blocks

    def simulate_trade_lock(self, history: List[Any], start_idx: int, entry: float, sl: float, tp: float, is_bullish: bool, ttl_candles: int = 30) -> int:
        fill_idx = -1
        for k in range(start_idx, min(start_idx + ttl_candles, len(history))):
            ck = history[k]
            if not is_bullish:
                if ck.high >= entry:
                    fill_idx = k
                    break
            else:
                if ck.low <= entry:
                    fill_idx = k
                    break
        
        if fill_idx == -1:
            return start_idx + ttl_candles
        return fill_idx

    def process(self, context: PipelineContext) -> None:
        self.process_direction(context, True)
        self.process_direction(context, False)

    def process_direction(self, context: PipelineContext, is_bullish: bool) -> None:
        history = context.theory_state.history
        if not history:
            return
            
        trackers = context.theory_state.origin_trackers
        
        bias_window_size = self.params.get('bias_window_size', 200)
        current_idx = len(history) - 1
        start_idx = max(0, current_idx - bias_window_size)
        
        ttl_candles = self.params.get('ttl_candles', 30)
        sl_points = self.params.get('sl_points', 8.0)
        tp_points = self.params.get('tp_points', 12.0)
        proximity_points = self.params.get('origin_proximity_points', 3.0)
        pd_window_size = self.params.get('premium_discount_window_size', 300)
        
        blocks = self.find_blocks(history, start_idx, is_bullish)
        if not blocks:
            return
            
        # We only care about active Origin Levels of the appropriate direction
        active_origins = []
        for t in trackers:
            if t.level_data.level_type == LevelType.ORIGIN_LEVEL and not t.level_data.status == "invalidated":
                if t.level_data.is_bullish == is_bullish:
                    active_origins.append(t.level_data)
                    
        if not active_origins:
            return

        locked_until_idx = -1
        latest_valid_setup = None
        
        # Determine valid blocks by matching with an active origin level
        valid_blocks = []
        for b in blocks:
            matched_origin = False
            for origin in active_origins:
                # Proximity check
                dist = abs(b['block_extreme'] - origin.price_high) if not is_bullish else abs(b['block_extreme'] - origin.price_low)
                if dist <= proximity_points:
                    matched_origin = True
                    break
            
            if matched_origin:
                valid_blocks.append(b)
                
        # Simulate execution logic for PD and TTL
        for b in valid_blocks:
            hc2 = b['hc_idx']
            if hc2 > locked_until_idx:
                entry = b['hold_entry']
                
                # PREMIUM/DISCOUNT FILTER
                is_valid_zone = False
                if pd_window_size == 0:
                    is_valid_zone = True
                else:
                    eval_start_idx = max(0, hc2 - pd_window_size)
                    eval_candles = history[eval_start_idx:hc2+1]
                    range_high = max(ck.high for ck in eval_candles)
                    range_low = min(ck.low for ck in eval_candles)
                    midpoint = (range_high + range_low) / 2
                    
                    if not is_bullish:
                        if entry >= midpoint:
                            is_valid_zone = True
                    else:
                        if entry <= midpoint:
                            is_valid_zone = True
                            
                if is_valid_zone:
                    sim_frontrun = self.params.get('sim_frontrun_points', 0.0)
                    if not is_bullish:
                        sim_entry = entry - sim_frontrun
                        sl = sim_entry + sl_points
                        tp = sim_entry - tp_points
                    else:
                        sim_entry = entry + sim_frontrun
                        sl = sim_entry - sl_points
                        tp = sim_entry + tp_points
                        
                    locked_until_idx = self.simulate_trade_lock(history, hc2 + 1, sim_entry, sl, tp, is_bullish, ttl_candles)
                    latest_valid_setup = b

        if latest_valid_setup:
            if locked_until_idx >= current_idx:
                level_data = TheoryLevel(
                    timestamp=history[latest_valid_setup['hc_idx']].timestamp,
                    level_type=LevelType.HOLD_LEVEL,
                    is_bullish=is_bullish,
                    price_high=latest_valid_setup['break'], 
                    price_low=latest_valid_setup['break'],
                    price_open=latest_valid_setup['hold_entry'],
                    status="identified_origin_hold"
                )
                context.setup_candidates.append(RetroScannerTrackerWrapper(level_data))
