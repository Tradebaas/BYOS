import logging
from dataclasses import dataclass
from typing import List, Optional, Dict

logger = logging.getLogger("ZebasCore")

@dataclass
class SetupSignal:
    direction: str # "LONG" or "SHORT"
    entry_price: float
    stop_loss_price: float
    tp1_price: float
    tp2_price: float
    move_to_be: bool
    origin_bar_idx: int
    hold_bar_idx: int
    
class BreakLevel:
    def __init__(self, price: float, is_break_up: bool, creation_bar_idx: int, timestamp: int = 0):
        self.price = price
        self.is_break_up = is_break_up
        self.creation_bar_idx = creation_bar_idx
        self.timestamp = timestamp
        
        self.testCount = 0
        self.waitingOpposite = False
        self.waitingRetest = False
        self.test1Bar = None
        self.originBar = None
        
        self.holdPrice = None
        self.holdValid = False
        self.holdTests = 0
        self.holdExtreme = None
        self.holdBar = None
        self.holdValidBar = None
        self.holdScanStart = None

class ZebasEngine:
    def __init__(self, sl_pts=20.0, tp1_pts=40.0, tp2_pts=40.0, move_to_be=True):
        self.candles = []
        self.breaks: List[BreakLevel] = []
        
        self.sl_pts = sl_pts
        self.tp1_pts = tp1_pts
        self.tp2_pts = tp2_pts
        self.move_to_be = move_to_be
        
        self.best_long_hold = None
        self.best_short_hold = None
        self.active_long_setup: Optional[SetupSignal] = None
        self.active_short_setup: Optional[SetupSignal] = None

    def hard_close(self, price: float, is_break_up: bool, candle) -> bool:
        if is_break_up:
            return candle.is_bullish and candle.open > price and candle.close > price
        else:
            return candle.is_bearish and candle.open < price and candle.close < price

    def process_candle(self, candle):
        self.candles.append(candle)
        bar_index = len(self.candles) - 1
        
        if bar_index < 2:
            return
            
        c0 = self.candles[-1]
        c1 = self.candles[-2]
        c2 = self.candles[-3]
        
        # 1. Break Detection
        new_bullish_break = False
        if c0.is_bullish and c1.is_bullish and c2.is_bearish:
            lvl = BreakLevel(c1.low, False, bar_index - 1, getattr(c1, 'timestamp', 0))
            self.breaks.append(lvl)
            new_bullish_break = True
            logger.info(f"[LADDER] Bullish Break (Support Basis) created at {c1.low}")
            
        new_bearish_break = False
        if c0.is_bearish and c1.is_bearish and c2.is_bullish:
            lvl = BreakLevel(c1.high, True, bar_index - 1, getattr(c1, 'timestamp', 0))
            self.breaks.append(lvl)
            new_bearish_break = True
            logger.info(f"[LADDER] Bearish Break (Resistance Basis) created at {c1.high}")
            
        active_breaks = []
        for lvl in self.breaks:
            if bar_index - lvl.creation_bar_idx > 1000:
                continue # Invalidate and remove (TradingView 1000 bar limit)
                
            if self.hard_close(lvl.price, lvl.is_break_up, c0):
                continue # Invalidate and remove
                
            # De Deur (Pine Script logic)
            # Structure reset
            if (lvl.is_break_up and c0.is_bearish and c1.is_bearish) or \
               (not lvl.is_break_up and c0.is_bullish and c1.is_bullish):
                lvl.waitingOpposite = True
                lvl.waitingRetest = False

            if lvl.waitingOpposite:
                if lvl.is_break_up and c0.is_bullish:
                    lvl.waitingOpposite = False
                    lvl.waitingRetest = True
                elif not lvl.is_break_up and c0.is_bearish:
                    lvl.waitingOpposite = False
                    lvl.waitingRetest = True
                    
            if lvl.waitingRetest and bar_index > lvl.creation_bar_idx + 1:
                # Is het getest bij deze nieuwste actuele candle?
                touched = (c0.high >= lvl.price) if lvl.is_break_up else (c0.low <= lvl.price)
                if touched:
                    lvl.testCount += 1
                    lvl.waitingRetest = False
                    if lvl.testCount == 1:
                        lvl.test1Bar = bar_index
                    logger.info(f"[TEST] Lijn {lvl.price} getest. Totaal tests: {lvl.testCount}")
                        
            if lvl.testCount >= 2 and lvl.originBar is None:
                lvl.originBar = bar_index
                logger.info(f"[ORIGIN] Break Level {lvl.price} gepromoveerd naar ORIGIN LEVEL (De Theoriemuur).")
                
            # 3. Hold Scan
            if lvl.testCount >= 2 and lvl.originBar is not None:
                c_open = None; c_high = None; c_low = None; c_bar = None
                h_open = None; h_high = None; h_low = None; h_bar = None
                h_valid = False; h_tested = False
                h_valid_bar = None
                
                scan_start = lvl.test1Bar if lvl.test1Bar is not None else lvl.originBar
                if lvl.holdScanStart is not None and lvl.holdScanStart > scan_start:
                    scan_start = lvl.holdScanStart
                
                for i in range(scan_start, bar_index + 1):
                    c = self.candles[i]
                    if lvl.is_break_up:
                        if c.is_bullish and c.open < lvl.price:
                            if c_open is None or c.open > c_open:
                                c_open = c.open; c_low = c.low; c_high = c.high; c_bar = i
                                
                        if h_valid:
                            if c.is_bullish and c.open > h_open and c.close > h_open:
                                h_valid = False; h_open = None
                            else:
                                if c.high >= h_open:
                                    h_tested = True
                            if c_open is not None and c.is_bearish and c.open < c_low and c.close < c_low:
                                if h_open is None or c_open > h_open:
                                    h_valid = True; h_tested = False
                                    h_open = c_open; h_low = c_low; h_high = c_high; h_bar = c_bar
                                    h_valid_bar = i
                        else:
                            if c_open is not None and c.is_bearish and c.open < c_low and c.close < c_low:
                                h_valid = True; h_tested = False
                                h_open = c_open; h_low = c_low; h_high = c_high; h_bar = c_bar
                                h_valid_bar = i
                                
                    else:
                        if c.is_bearish and c.open > lvl.price:
                            if c_open is None or c.open < c_open:
                                c_open = c.open; c_low = c.low; c_high = c.high; c_bar = i
                                
                        if h_valid:
                            if c.is_bearish and c.open < h_open and c.close < h_open:
                                h_valid = False; h_open = None
                            else:
                                if c.low <= h_open:
                                    h_tested = True
                            if c_open is not None and c.is_bullish and c.open > c_high and c.close > c_high:
                                if h_open is None or c_open < h_open:
                                    h_valid = True; h_tested = False
                                    h_open = c_open; h_low = c_low; h_high = c_high; h_bar = c_bar
                                    h_valid_bar = i
                        else:
                            if c_open is not None and c.is_bullish and c.open > c_high and c.close > c_high:
                                h_valid = True; h_tested = False
                                h_open = c_open; h_low = c_low; h_high = c_high; h_bar = c_bar
                                h_valid_bar = i
                                
                if h_valid:
                    if h_valid_bar is not None and (bar_index - h_valid_bar) >= 20 and not h_tested:
                        lvl.holdScanStart = bar_index
                        logger.info(f"[EXPIRED] Limit order @ {h_open} geannuleerd na 20 candles ongerept. Zoeken naar nieuwe kandidaat...")
                        lvl.holdValid = False
                        lvl.holdPrice = None
                        lvl.holdValidBar = None
                        continue
                        
                    if not lvl.holdValid:
                        logger.info(f"[HOLD LEVEL] Gevonden en Gevalideerd @ {h_open}")
                    lvl.holdValid = True
                    lvl.holdPrice = h_open
                    lvl.holdTests = 1 if h_tested else 0
                    lvl.holdExtreme = h_high if lvl.is_break_up else h_low
                    lvl.holdBar = h_bar
                    lvl.holdValidBar = h_valid_bar
                else:
                    lvl.holdValid = False
                    lvl.holdPrice = None
                    lvl.holdValidBar = None
                    
            active_breaks.append(lvl)
            
        # Highlander Logic - Find closest Valid Origin Level (max 3 tests)
        active_long_highlander = None
        active_short_highlander = None
        
        for lvl in active_breaks:
            if lvl.originBar is not None and lvl.testCount <= 3: # Max 3 times test of original break level
                if lvl.is_break_up: # Resistance
                    if c0.close < lvl.price:
                        if active_short_highlander is None or lvl.price < active_short_highlander.price:
                            active_short_highlander = lvl
                else: # Support
                    if c0.close > lvl.price:
                        if active_long_highlander is None or lvl.price > active_long_highlander.price:
                            active_long_highlander = lvl
            
        self.breaks = active_breaks
        self._evaluate_setups(c0, active_long_highlander, active_short_highlander)
        
    def _evaluate_setups(self, latest_candle, highlander_long=None, highlander_short=None):
        self.best_long_hold = None
        self.best_short_hold = None
        self.active_long_setup = None
        self.active_short_setup = None
        
        logger.info(f"--- Evaluating setups for candle {latest_candle.timestamp} (close: {latest_candle.close}) ---")
        for lvl in self.breaks:
            if lvl.holdValid and lvl.holdTests == 0 and lvl.originBar is not None:
                origin_extreme = lvl.price 
                
                # Setup is ONLY valid if this level is the Highlander!
                is_valid_highlander = (lvl == highlander_short) if lvl.is_break_up else (lvl == highlander_long)
                
                if not is_valid_highlander:
                    continue # Overslaan, mag niet getrade worden want het is niet de Highlander
                
                logger.info(f"Evaluating Highlander candidate: is_break_up={lvl.is_break_up}, holdPrice={lvl.holdPrice}, close={latest_candle.close}")
                
                if lvl.is_break_up: # Short Setup
                    if latest_candle.close < lvl.holdPrice:
                        if self.best_short_hold is None or lvl.holdPrice < self.best_short_hold:
                            self.best_short_hold = lvl.holdPrice
                            
                            self.active_short_setup = SetupSignal(
                                direction="SHORT",
                                entry_price=lvl.holdPrice,
                                stop_loss_price=lvl.holdPrice + self.sl_pts,
                                tp1_price=lvl.holdPrice - self.tp1_pts,
                                tp2_price=lvl.holdPrice - self.tp2_pts,
                                move_to_be=self.move_to_be,
                                origin_bar_idx=lvl.originBar,
                                hold_bar_idx=lvl.holdBar
                            )
                            logger.info(f"-> Active SHORT setup set at {lvl.holdPrice}")
                    else:
                        logger.info(f"-> Rejected SHORT setup: current close {latest_candle.close} >= holdPrice {lvl.holdPrice}")
                else: # Long Setup
                    if latest_candle.close > lvl.holdPrice:
                        if self.best_long_hold is None or lvl.holdPrice > self.best_long_hold:
                            self.best_long_hold = lvl.holdPrice
                            
                            self.active_long_setup = SetupSignal(
                                direction="LONG",
                                entry_price=lvl.holdPrice,
                                stop_loss_price=lvl.holdPrice - self.sl_pts,
                                tp1_price=lvl.holdPrice + self.tp1_pts,
                                tp2_price=lvl.holdPrice + self.tp2_pts,
                                move_to_be=self.move_to_be,
                                origin_bar_idx=lvl.originBar,
                                hold_bar_idx=lvl.holdBar
                            )
                            logger.info(f"-> Active LONG setup set at {lvl.holdPrice}")
                    else:
                        logger.info(f"-> Rejected LONG setup: current close {latest_candle.close} <= holdPrice {lvl.holdPrice}")

        self.print_state_table()

    def print_state_table(self):
        if not self.breaks:
            return
            
        logger.info("\n" + "="*85)
        logger.info(" ZEBAS THEORIE STRUCTUUR ".center(85, "="))
        logger.info("TYPE    | BREAK PRICE | TESTS | ORIGIN | KANDIDAAT | HARD CLOSE GRENS | LIMIT / STATUS")
        logger.info("-" * 85)
        
        for lvl in self.breaks:
            t_type = "RESIST " if lvl.is_break_up else "SUPPORT"
            b_price = f"{lvl.price:10.2f}"
            tests = str(lvl.testCount).ljust(5)
            origin = "YES   " if lvl.originBar is not None else "NO    "
            
            candidate_price = "n/a       "
            hc_grens = "n/a             "
            limit_status = "Waiting..."
            
            # Identify candidate if origin is active
            if lvl.originBar is not None:
                # The candidate is holdPrice if valid, OR the lowest/highest opposite candle so far if searching
                # We need to expose the cand_open and cand_extreme from the process loop.
                # Actually, if holdValid is True, we have a setup.
                if lvl.holdValid:
                    candidate_price = f"{lvl.holdPrice:10.2f}"
                    hc_grens = "GEVALIDEERD     "
                    if lvl.is_break_up and self.active_short_setup and self.active_short_setup.entry_price == lvl.holdPrice:
                        limit_status = f"LIMIT SELL {lvl.holdPrice}"
                    elif not lvl.is_break_up and self.active_long_setup and self.active_long_setup.entry_price == lvl.holdPrice:
                        limit_status = f"LIMIT BUY {lvl.holdPrice}"
                    else:
                        if lvl.holdTests > 0:
                            limit_status = f"Setup {lvl.holdPrice} (GEVULD/GETEST)"
                        else:
                            limit_status = f"Setup {lvl.holdPrice} (Ongeraakt)"
                else:
                    # Searching for hard close
                    candidate_price = "Zoekt...  "
                    hc_grens = "Wacht op Hard Close"
            else:
                limit_status = "Wacht op Test/Origin"
                
            logger.info(f"{t_type} | {b_price} | {tests} | {origin} | {candidate_price} | {hc_grens} | {limit_status}")
            
        logger.info("="*85 + "\n")

    def get_actionable_setups(self) -> List[SetupSignal]:
        setups = []
        if self.active_long_setup:
            setups.append(self.active_long_setup)
        if self.active_short_setup:
            setups.append(self.active_short_setup)
        return setups

    def get_state(self) -> List[Dict]:
        state_list = []
        for lvl in self.breaks:
            # Filter to only return valid origin-based setups
            if lvl.originBar is None:
                continue
                
            t_type = "RESISTANCE" if lvl.is_break_up else "SUPPORT"
            
            # According to the rules, max 3 tests allowed.
            is_active = lvl.testCount < 3
            
            has_limit = False
            if lvl.holdValid:
                if lvl.is_break_up and self.active_short_setup and self.active_short_setup.entry_price == lvl.holdPrice:
                    has_limit = True
                elif not lvl.is_break_up and self.active_long_setup and self.active_long_setup.entry_price == lvl.holdPrice:
                    has_limit = True
            
            state_list.append({
                "id": str(lvl.creation_bar_idx),
                "timestamp": lvl.timestamp,
                "price": lvl.price,
                "type": t_type,
                "tf": 1,
                "test_count": lvl.testCount,
                "is_origin": True,
                "is_active": is_active,
                "has_limit": has_limit,
                "hold_valid": lvl.holdValid,
                "hold_price": lvl.holdPrice if lvl.holdValid else None,
                "hold_tests": lvl.holdTests,
                "hold_ts": self.candles[lvl.holdBar].timestamp if (lvl.holdValid and lvl.holdBar is not None and lvl.holdBar < len(self.candles)) else None
            })
        return state_list
