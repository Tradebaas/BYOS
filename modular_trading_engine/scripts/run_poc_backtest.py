import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from typing import List, Optional, Tuple

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.layer1_data.models import Candle
from src.layer2_theory.market_state import MarketTheoryState
from src.layer2_theory.models import LevelType

# --- Types & Models ---
class Order:
    def __init__(self, is_long: bool, limit_price: float, sl_price: float, tp_price: float, ttl_candles: int):
        self.is_long = is_long
        self.limit_price = limit_price
        self.sl_price = sl_price
        self.tp_price = tp_price
        self.ttl_candles = ttl_candles
        self.candles_alive = 0
        self.status = "pending" # pending, filled, canceled, stopped, target
        self.fill_timestamp = None
        self.meta_origin_start = None
        self.meta_origin_price_bounds = None
        self.meta_test_1 = None
        self.meta_test_2 = None
        self.meta_hold_time = None
        self.meta_hold_price_open = None

class VirtualBroker:
    def __init__(self):
        self.active_order: Optional[Order] = None
        self.open_position: Optional[Order] = None
        
        self.trades = []
        self.win_count = 0
        self.loss_count = 0
        self.pnl_ticks = 0

    def tick_prices(self, price_open: float, price_high: float, price_low: float, timestamp: datetime):
        """
        Evaluate if pending limit orders trigger, and if open positions hit TP/SL.
        We evaluate optimistically/pessimistically based on the H/L of the 1m candle.
        """
        # 1. Fill Pending Order?
        if self.active_order and self.active_order.status == "pending":
            o = self.active_order
            triggered = False
            if o.is_long and price_low <= o.limit_price:
                triggered = True
            elif not o.is_long and price_high >= o.limit_price:
                triggered = True

            if triggered:
                o.status = "filled"
                o.fill_timestamp = timestamp
                self.open_position = o
                self.active_order = None

        # 2. Check position for SL / TP
        # Note: If it filled on this exact same candle, it might also immediately hit TP/SL.
        # We process TP/SL checks regardless.
        if self.open_position:
            p = self.open_position
            # For backtesting limitations on 1m, if both hit, we assume SL hit first (pessimistic)
            sl_hit = False
            tp_hit = False
            
            if p.is_long:
                if price_low <= p.sl_price:
                    sl_hit = True
                if price_high >= p.tp_price:
                    tp_hit = True
            else:
                if price_high >= p.sl_price:
                    sl_hit = True
                if price_low <= p.tp_price:
                    tp_hit = True
                    
            if sl_hit:
                p.status = "stopped"
                self.loss_count += 1
                self.pnl_ticks -= abs(p.limit_price - p.sl_price) / 0.25
                self.trades.append(p)
                self.open_position = None
            elif tp_hit:
                p.status = "target"
                self.win_count += 1
                self.pnl_ticks += abs(p.tp_price - p.limit_price) / 0.25
                self.trades.append(p)
                self.open_position = None

    def tick_candle_end(self):
        """Increment TTL for pending orders."""
        if self.active_order and self.active_order.status == "pending":
            self.active_order.candles_alive += 1
            if self.active_order.candles_alive >= self.active_order.ttl_candles:
                self.active_order.status = "canceled"
                self.active_order = None

def get_5m_trend(state_5m: MarketTheoryState) -> Optional[bool]:
    """
    Looks at the 5m MarketTheoryState to determine CCTA trend.
    Based on the last established Break Level.
    Returns True for Bullish, False for Bearish, None if undetermined.
    """
    last_break = None
    for level in reversed(state_5m.all_theory_levels):
        if level.level_type == LevelType.BREAK_LEVEL:
            last_break = level
            break
            
    if last_break:
        return last_break.is_bullish
    return None

# --- CONFIGURATION ---
# 'greedy' : Lowest untested Hold Level for LONG, Highest for SHORT.
# 'closest_time' : Untested Hold Level that was formed closest in time to the Origin Level.
# 'closest_price' : Untested Hold Level that is closest in price to the Origin Level bounds.
HOLD_LEVEL_SELECTION_MODE = 'latest'

def main():
    csv_path = Path(__file__).parent.parent / "data" / "historical" / "NQ_1min.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} not found. Please run build_data_lake.py first.")
        return

    print("Loading data lake...")
    df = pd.read_csv(csv_path)
    # Sort chronologically just in case
    df = df.sort_values("timestamp_ms").reset_index(drop=True)
    print(f"Loaded {len(df)} 1-minute candles.")

    # Convert df to Candle objects
    candles_1m = []
    for _, row in df.iterrows():
        dt = datetime.fromtimestamp(row["timestamp_ms"]/1000.0, tz=timezone.utc)
        c = Candle(
            timestamp=dt,
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"]
        )
        candles_1m.append(c)

    state_1m = MarketTheoryState()
    state_5m = MarketTheoryState()
    broker = VirtualBroker()

    # Buffer for 5m aggregation
    buffer_5m = []

    print("Starting walk-forward backtest...")
    total = len(candles_1m)
    
    for i, curr_c in enumerate(candles_1m):
        # 1. Update Broker prices during the candle
        broker.tick_prices(curr_c.open, curr_c.high, curr_c.low, curr_c.timestamp)
        
        # 2. Feed 1m state
        state_1m.process_candle(curr_c)
        
        # 3. Aggregate and feed 5m state
        buffer_5m.append(curr_c)
        if len(buffer_5m) == 5:
            # Create a 5m candle
            c5 = Candle(
                timestamp=buffer_5m[0].timestamp,
                open=buffer_5m[0].open,
                high=max(c.high for c in buffer_5m),
                low=min(c.low for c in buffer_5m),
                close=buffer_5m[-1].close,
                volume=sum(c.volume for c in buffer_5m)
            )
            state_5m.process_candle(c5)
            buffer_5m.clear()

        # 4. End of candle broker update (TTL)
        broker.tick_candle_end()

        # 5. Execute Strategy Logic
        if broker.open_position:
            # We already have a position, skip looking for new entries
            continue

        # Instead of strict 5m trend, use the most recent Origin Level to dictate direction
        # Find ALL active origin levels
        active_origins = [o for o in state_1m.origin_trackers 
                          if o.is_active 
                          and o.level_data.level_type == LevelType.ORIGIN_LEVEL]
                          
        if not active_origins:
            continue

        # We consider the most recently established valid origin level
        latest_origin_tracker = active_origins[-1]
        trend_bullish = latest_origin_tracker.level_data.is_bullish
        
        # Origin test count filter: 
        # test_count = 2 means the Origin Level is just created (Break tested twice).
        # test_count = 3 means the Origin Level is tested 1x itself.
        if latest_origin_tracker.test_count <= 3:
            # Setup is valid.
            # Filter valid Hold Levels:
            # 1. Must match direction (is_bullish == is_bullish)
            # 2. Must be untested (t.hits == 0)
            # 3. Must be formed AFTER the original Break Level began (t.level_data.timestamp > current_origin.timestamp)
            valid_trackers = [
                t for t in state_1m.reverse_trackers 
                if t.level_data.is_bullish == trend_bullish 
                and t.hits == 0
            ]
            
            if valid_trackers:
                valid_holds = [t.level_data for t in valid_trackers]
                
                if HOLD_LEVEL_SELECTION_MODE == 'greedy':
                    if trend_bullish:
                        selected_hold = min(valid_holds, key=lambda h: h.price_low)
                    else:
                        selected_hold = max(valid_holds, key=lambda h: h.price_high)
                        
                elif HOLD_LEVEL_SELECTION_MODE == 'closest_price':
                    origin_p = latest_origin_tracker.level_data.price_low if trend_bullish else latest_origin_tracker.level_data.price_high
                    if trend_bullish:
                        selected_hold = min(valid_holds, key=lambda h: abs(h.price_high - origin_p))
                    else:
                        selected_hold = min(valid_holds, key=lambda h: abs(h.price_low - origin_p))
                        
                elif HOLD_LEVEL_SELECTION_MODE == 'latest':
                    # Find the Hold Level that was formed most recently (chronologically)
                    selected_hold = max(valid_holds, key=lambda h: h.timestamp)
                    
                elif HOLD_LEVEL_SELECTION_MODE == 'closest_time':
                    origin_t = latest_origin_tracker.level_data.timestamp
                    selected_hold = min(valid_holds, key=lambda h: abs((h.timestamp - origin_t).total_seconds()))
                    
                else:
                    selected_hold = valid_holds[-1] # Fallback
                    
                # Calculate Limit Price (Offset: 2 ticks = 0.50 points)
                # Scan back for the exact candle matching the timestamp to get its open price.
                hold_candle_c1 = next((c for c in reversed(candles_1m[:i+1]) if c.timestamp == selected_hold.timestamp), None)
                if hold_candle_c1:
                    hold_open = hold_candle_c1.open
                    
                    if trend_bullish:
                        limit_price = hold_open + 0.50
                        sl_price = limit_price - 15.0  # 60 ticks
                        tp_price = limit_price + 30.0  # 120 ticks
                    else:
                        limit_price = hold_open - 0.50
                        sl_price = limit_price + 15.0
                        tp_price = limit_price - 30.0
                        
                    # Place order
                    broker.active_order = Order(
                        is_long=trend_bullish,
                        limit_price=limit_price,
                        sl_price=sl_price,
                        tp_price=tp_price,
                        ttl_candles=20
                    )
                    
                    with open("orders_placed.txt", "a") as f:
                        f.write(f"PLACED: {broker.active_order.is_long} at {limit_price} for Origin: {latest_origin_tracker.level_data.timestamp} Hold: {selected_hold.timestamp} Time: {curr_c.timestamp}\n")
                    
                    # Attach metadata for logging
                    broker.active_order.meta_origin_start = latest_origin_tracker.level_data.timestamp
                    broker.active_order.meta_origin_price_bounds = (latest_origin_tracker.level_data.price_low, latest_origin_tracker.level_data.price_high)
                    
                    tests = latest_origin_tracker.test_history
                    if len(tests) > 0:
                        broker.active_order.meta_test_1 = tests[0]
                    if len(tests) > 1:
                        broker.active_order.meta_test_2 = tests[1]
                        
                    broker.active_order.meta_hold_time = selected_hold.timestamp
                    broker.active_order.meta_hold_price_open = hold_candle_c1.open

        # Print progress
        if (i + 1) % 10000 == 0:
            print(f"Processed {i + 1}/{total} candles... Trades: {len(broker.trades)} (W:{broker.win_count} L:{broker.loss_count})")

    # Backtest complete
    print("\n=== Backtest Complete ===")
    print(f"Total Trades : {len(broker.trades)}")
    print(f"Wins         : {broker.win_count}")
    print(f"Losses       : {broker.loss_count}")
    if len(broker.trades) > 0:
        win_rate = broker.win_count / len(broker.trades) * 100
        print(f"Win Rate     : {win_rate:.2f}%")
    print(f"Net PnL (ticks): {broker.pnl_ticks}")
    # 1 tick of MNQ is $0.50
    print(f"Net PnL (USD)  : ${broker.pnl_ticks * 0.50:.2f} (excluding commissions)")
    
    print("\n=== Laatste 3 Trades ===")
    for t in broker.trades[-3:]:
        direction = "LONG" if t.is_long else "SHORT"
        print("--------------------------------------------------")
        print(f"Trade Fill Tijd : {t.fill_timestamp} | Richting: {direction}")
        print(f"Resultaat       : {t.status} (Entry: {t.limit_price} | SL: {t.sl_price} | TP: {t.tp_price})")
        print(f"[Trace] Break L.: Gestart @ {t.meta_origin_start} (Bounds: Low={t.meta_origin_price_bounds[0]}, High={t.meta_origin_price_bounds[1]})")
        
        t1 = t.meta_test_1 if t.meta_test_1 else ("Geen Test 1", "N/A")
        print(f"[Trace] Test 1  : {t1[0]} (Hit Price: {t1[1]})")
        
        t2 = t.meta_test_2 if t.meta_test_2 else ("(Werd Origin op Test 1 want hit_history[0] is creatie, en Test 1 maakt hem Origin in deze poc, of N/A)", "N/A")
        if t.meta_test_2:
             print(f"[Trace] Test 2  : {t2[0]} (Werd origin/Hit Price: {t2[1]})")
             
        print(f"[Trace] Hold L. : Gevormd @ {t.meta_hold_time} (Candle Open Prijs: {t.meta_hold_price_open})")


if __name__ == "__main__":
    main()
