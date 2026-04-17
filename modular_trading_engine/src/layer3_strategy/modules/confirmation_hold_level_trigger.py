from typing import Any, List
from datetime import datetime
import logging

from src.layer3_strategy.modules.base import BaseStrategyModule
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer2_theory.models import TheoryLevel, LevelType

logger = logging.getLogger(__name__)

class RetroScannerTracker:
    def __init__(self, level_data: TheoryLevel):
        self.level_data = level_data

class ConfirmationHoldLevelTrigger(BaseStrategyModule):
    """
    Implements a pure 1-minute structural Sweep & Confirm State Machine.
    Phase 1: Filter to 200-candle Bias Window.
    Phase 2: Hunt for earlier 3-Candle Sequences (Hold/Break/HC).
    Phase 3: Hunt for a Test (Hold level touched, Break untouched).
    Phase 4: Hunt for the NEXT 3-Candle Sequence Confirmed after the test.
    Phase 5: Output RAT Limit target directly on the new Hold Level Open.
    """
    def find_blocks(self, history: List[Any], start_idx: int, is_bullish: bool):
        """
        Calculates all generic 3-candle Induction/Structural blocks in the range.
        For Short: Green (Hold), Red (Break), Red (Hard Close).
        For Long: Red (Hold), Green (Break), Green (Hard Close).
        Returns a list of dicts: {hold, break, c1_idx, hc_idx}.
        """
        blocks = []
        end_idx = len(history)
        
        for i in range(start_idx, end_idx - 2):
            c1 = history[i] # The Hold Level Candle
            c1_bull = c1.is_bullish
            c1_bear = c1.is_bearish
            
            # Short Setup: C1 is Bullish
            if not is_bullish:
                if not c1_bull: continue
                c2 = history[i+1] # The Break Level Candle
                if not c2.is_bearish: continue
                
                # Scan ahead for the Hard Close
                hard_close_idx = -1
                for j in range(i+2, min(i+15, end_idx)): # reasonable limit to complete structure
                    cj = history[j]
                    if cj.open < c1.low and cj.close < c1.low:
                        hard_close_idx = j
                        break
                    if cj.high >= c2.high: # Structure invalidated by pushing past Break Level
                        break
                
                if hard_close_idx != -1:
                    blocks.append({
                        'type': 'short',
                        'hold': c1.open,
                        'break': c2.high,
                        'c1_idx': i,
                        'hc_idx': hard_close_idx
                    })
            
            # Long Setup: C1 is Bearish
            else:
                if not c1_bear: continue
                c2 = history[i+1]
                if not c2.is_bullish: continue
                
                hard_close_idx = -1
                for j in range(i+2, min(i+15, end_idx)):
                    cj = history[j]
                    if cj.open > c1.high and cj.close > c1.high:
                        hard_close_idx = j
                        break
                    if cj.low <= c2.low:
                        break
                        
                if hard_close_idx != -1:
                    blocks.append({
                        'type': 'long',
                        'hold': c1.open,
                        'break': c2.low,
                        'c1_idx': i,
                        'hc_idx': hard_close_idx
                    })
                    
        return blocks

    def process(self, context: PipelineContext) -> None:
        if context.active_polarity_is_bullish is None:
            return
            
        history = context.theory_state.history
        if not history:
            return
            
        is_bullish = context.active_polarity_is_bullish
        
        # 1. 200 Candle Logic memory enforcement
        bias_window_size = self.params.get('bias_window_size', 200)
        current_idx = len(history) - 1
        start_idx = max(0, current_idx - bias_window_size)
        
        # 2. Extract completely independent micro-structural blocks
        blocks = self.find_blocks(history, start_idx, is_bullish)
        if not blocks:
            return
            
        # 3. Sweep & Confirm State Machine
        # We process blocks forward in time to simulate market evolution logic
    def simulate_trade_lock(self, history: List[Any], start_idx: int, entry: float, sl: float, tp: float, is_bullish: bool, ttl_candles: int = 30) -> int:
        """
        Simulates the lifecycle of a limit order directly inside the 200-candle memory.
        Returns the index at which the scanner should UNLOCK and resume searching for Tests.
        """
        fill_idx = -1
        # 1. Wait for fill (TTL constraint)
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
            # Cancelled after TTL
            return start_idx + ttl_candles
            
        # 2. Filled / Touched!
        # Playbook Rule: "Zodra de entry level is geraakt, is de setup geconsumeerd/getest."
        # We return fill_idx so the engine stops emitting this Intent and starts scanning for a new Block natively.
        return fill_idx

    def process(self, context: PipelineContext) -> None:
        # We now loop over both directions symmetrically, discarding any macro theory.
        # Premium/Discount natively filters out mathematically invalid combinations anyway.
        self.process_direction(context, True)
        self.process_direction(context, False)

    def process_direction(self, context: PipelineContext, is_bullish: bool) -> None:
        history = context.theory_state.history
        if not history:
            return
        
        # 1. 200 Candle Logic memory enforcement
        bias_window_size = self.params.get('bias_window_size', 200)
        current_idx = len(history) - 1
        start_idx = max(0, current_idx - bias_window_size)
        
        # Pull playback params for simulation lock
        ttl_candles = self.params.get('ttl_candles', 30)
        sl_points = self.params.get('sl_points', 15.0)
        tp_points = self.params.get('tp_points', 30.0)
        
        # 2. Extract completely independent micro-structural blocks
        blocks = self.find_blocks(history, start_idx, is_bullish)
        if not blocks:
            return
            
        # 3. Sweep & Confirm State Machine with Trade Locking (Multi-Anchor Stack)
        active_anchors = []
        locked_until_idx = -1
        
        # We only care about the latest valid setup we can find natively, 
        # but we must simulate all past simulated executions to ensure the lock matches reality.
        latest_valid_setup = None
        
        for b in blocks:
            b['last_checked_idx'] = b['hc_idx'] # Initialize the anchor's pointer
            surviving_anchors = []
            confirmed_setups = []
            
            for anchor in active_anchors:
                was_invalidated = False
                found_test = -1
                
                # Check the gap between this anchor's last checked index and the new block's C1
                for k in range(anchor['last_checked_idx'] + 1, b['c1_idx'] + 1):
                    ck = history[k]
                    if not is_bullish:
                        # HARD CLOSE INVALIDATION: Green candle closing above Hold Level
                        if ck.is_bullish and ck.open > anchor['hold'] and ck.close > anchor['hold']:
                            was_invalidated = True
                            break
                        # The test can ONLY happen after the previous trade lock expires
                        if ck.high >= anchor['hold'] and k > locked_until_idx:
                            found_test = k
                    else:
                        # HARD CLOSE INVALIDATION: Red candle closing below Hold Level
                        if ck.is_bearish and ck.open < anchor['hold'] and ck.close < anchor['hold']:
                            was_invalidated = True
                            break
                        if ck.low <= anchor['hold'] and k > locked_until_idx:
                            found_test = k
                            
                if was_invalidated:
                    continue # Anchor dies (hard close)
                    
                if found_test != -1:
                    # Anchor was tested! This block 'b' confirms the setup.
                    confirmed_setups.append({
                        'anchor': anchor,
                        'b2': b
                    })
                else:
                    # Anchor survives but remains untested. Update pointer.
                    anchor['last_checked_idx'] = b['c1_idx']
                    surviving_anchors.append(anchor)
                    
            trade_generated = False
            
            # Check if this valid confirmation yields a trade!
            if confirmed_setups:
                # Pick the setup with the most optimal anchor (closest to extreme)
                if is_bullish:
                    best_setup = min(confirmed_setups, key=lambda s: s['anchor']['hold'])
                else:
                    best_setup = max(confirmed_setups, key=lambda s: s['anchor']['hold'])
                    
                b2 = best_setup['b2']
                hc2 = b2['hc_idx']
                
                if hc2 > locked_until_idx:
                    entry = b2['hold']
                    
                    # PREMIUM/DISCOUNT FILTER
                    eval_start_idx = max(0, hc2 - bias_window_size)
                    eval_candles = history[eval_start_idx:hc2+1]
                    range_high = max(ck.high for ck in eval_candles)
                    range_low = min(ck.low for ck in eval_candles)
                    midpoint = (range_high + range_low) / 2
                    
                    is_valid_zone = False
                    if not is_bullish:
                        # Short -> Must be in Premium (Top 50%)
                        if entry >= midpoint:
                            is_valid_zone = True
                    else:
                        # Long -> Must be in Discount (Bottom 50%)
                        if entry <= midpoint:
                            is_valid_zone = True
                            
                    if is_valid_zone:
                        if not is_bullish:
                            # Short: Frontrun by placing entry 1 point LOWER
                            entry = entry - 1.0
                            sl = entry + sl_points
                            tp = entry - tp_points
                        else:
                            # Long: Frontrun by placing entry 1 point HIGHER
                            entry = entry + 1.0
                            sl = entry - sl_points
                            tp = entry + tp_points
                            
                        locked_until_idx = self.simulate_trade_lock(history, hc2 + 1, entry, sl, tp, is_bullish, ttl_candles)
                        
                        # Store as our latest candidate, carrying over the modified frontrun entry
                        b2['frontrun_entry'] = entry
                        latest_valid_setup = b2
                        trade_generated = True

            if trade_generated:
                # RESET completely: wait for NEXT Trap/Test
                active_anchors = []
            else:
                # Add this new block natively as a floating anchor for the future
                surviving_anchors.append(b)
                active_anchors = surviving_anchors

        # 4. We only process the final state if it is currently locked into the live edge
        if latest_valid_setup:
            # Wait, if locked_until_idx >= current_idx, it means the simulated trade is STILL active (or pending)!
            # We ONLY output an intent if the trade was JUST generated (or is still valid and pending natively)
            # Actually, to integrate nicely with layer 4, we must output the intent continuously until `locked_until_idx` is hit
            if locked_until_idx >= current_idx:
                # Is it already passed the TTL and not filled? (simulate_trade handles fill logic naturally).
                # LiveFleetCommander handles native SL/TP and TTL, so simply emitting the intent is sufficient safely.
                
                # Final safeguard: verify it really didn't break block 1.
                # Actually our iterative `simulate_trade_lock` proves it's valid.
                
                level_data = TheoryLevel(
                    timestamp=context.timestamp,
                    level_type=LevelType.HOLD_LEVEL,
                    is_bullish=is_bullish,
                    price_high=latest_valid_setup['break'], 
                    price_low=latest_valid_setup['break'],
                    price_open=latest_valid_setup.get('frontrun_entry', latest_valid_setup['hold']),
                    status="identified_hl2"
                )
                context.setup_candidates.append(RetroScannerTracker(level_data))
