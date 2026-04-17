import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data

print("Loading historical data...")
candles = load_historical_1m_data('modular_trading_engine/data/historical/NQ_1min.csv')
print(f"Loaded {len(candles)} candles.")

class OriginGroup:
    def __init__(self, t_type, hold_candle, b1_candle, idx_created):
        self.type = t_type
        self.hold_idx = idx_created - 2
        
        self.hold_ts = hold_candle.timestamp
        self.break_ts = b1_candle.timestamp
        self.hard_close_ts = None
        
        self.hold_open = hold_candle.open
        self.hold_high = hold_candle.high
        self.hold_low = hold_candle.low
        
        if t_type == "SHORT":
            self.break_level = b1_candle.high
        else:
            self.break_level = b1_candle.low
            
        self.confirmed = False
        self.invalidated = False

origins = []
state = "SEARCH"
alert_bias = None
alert_origin = None
alert_start_idx = 0
alert_ts = None
alert_eq = 0.0

pending_limit = None
active_trade = None

stats = {
    "activations": 0,
    "limits_placed": 0,
    "limits_expired": 0,
    "trades_entered": 0,
    "wins": 0,
    "losses": 0
}

completed_trades = []

def get_pd(idx):
    if idx < 500:
        return None
    window = candles[idx-500:idx]
    max_h = max(c.high for c in window)
    min_l = min(c.low for c in window)
    eq = (max_h + min_l) / 2
    if candles[idx-1].close >= eq:
        return "PREMIUM"
    else:
        return "DISCOUNT"

for i in range(500, len(candles)):
    cj = candles[i]
    pd = get_pd(i)
    
    # 1. Evaluate open trades
    if state == "TRADE":
        if active_trade['type'] == "SHORT":
            if cj.high >= active_trade['sl']:
                stats["losses"] += 1
                state = "SEARCH"
                active_trade = None
            elif cj.low <= active_trade['tp']:
                stats["wins"] += 1
                state = "SEARCH"
                active_trade = None
        else:
            if cj.low <= active_trade['sl']:
                stats["losses"] += 1
                state = "SEARCH"
                active_trade = None
            elif cj.high >= active_trade['tp']:
                stats["wins"] += 1
                state = "SEARCH"
                active_trade = None
        
        if state == "TRADE":
            continue
            
    # 2. Evaluate pending limit
    if state == "PENDING":
        pending_limit['ttl'] -= 1
        
        filled = False
        limit_price = pending_limit['price']
        
        if pending_limit['type'] == "SHORT":
            if cj.high >= limit_price and cj.low <= limit_price:
                filled = True
            elif cj.open > limit_price:
                filled = True
        else:
            if cj.low <= limit_price and cj.high >= limit_price:
                filled = True
            elif cj.open < limit_price:
                filled = True
                
        if filled:
            state = "TRADE"
            stats["trades_entered"] += 1
            active_trade = pending_limit
            pending_limit = None
            
            # Record it
            completed_trades.append({
                'entered_ts': cj.timestamp,
                'trade': active_trade
            })
            continue
            
        if pending_limit and pending_limit['ttl'] <= 0:
            stats["limits_expired"] += 1
            state = "SEARCH"
            pending_limit = None
            
        continue
        
    # 3. Form new Origins
    if i >= 2:
        c2, c1, c0 = candles[i-2], candles[i-1], candles[i]
        if c2.is_bullish and c1.is_bearish and c0.is_bearish:
            origins.append(OriginGroup("SHORT", c2, c1, i))
        if c2.is_bearish and c1.is_bullish and c0.is_bullish:
            origins.append(OriginGroup("LONG", c2, c1, i))
            
    # 4. Check Hard Closes
    newly_confirmed = []
    for o in origins:
        if not o.confirmed and not o.invalidated:
            if o.type == "SHORT":
                if cj.is_bearish and cj.open < o.hold_low and cj.close < o.hold_low:
                    o.confirmed = True
                    o.hard_close_ts = cj.timestamp
                    newly_confirmed.append(o)
                elif cj.high > o.hold_high:
                    o.invalidated = True
            else:
                if cj.is_bullish and cj.open > o.hold_high and cj.close > o.hold_high:
                    o.confirmed = True
                    o.hard_close_ts = cj.timestamp
                    newly_confirmed.append(o)
                elif cj.low < o.hold_low:
                    o.invalidated = True
                    
    origins = [o for o in origins if not o.invalidated]
    
    # 5. ALERT state logic
    if state == "ALERT":
        invalidated_alert = False
        if alert_bias == "SHORT":
            if cj.high >= alert_origin.break_level:
                invalidated_alert = True
        else:
            if cj.low <= alert_origin.break_level:
                invalidated_alert = True
                
        if invalidated_alert:
            state = "SEARCH"
            alert_origin.invalidated = True
            alert_origin = None
        else:
            for o in newly_confirmed:
                if o.type == alert_bias and o.hold_idx >= alert_start_idx:
                    state = "PENDING"
                    stats["limits_placed"] += 1
                    
                    price = o.hold_open
                    if o.type == "SHORT":
                        sl = price + 10.0
                        tp = price - 20.0
                    else:
                        sl = price - 10.0
                        tp = price + 20.0
                        
                    pending_limit = {
                        "type": o.type,
                        "origin_group": o, 
                        "price": price,
                        "sl": sl,
                        "tp": tp,
                        "ttl": 25
                    }
                    break

    # 6. SEARCH logic
    if state == "SEARCH":
        for o in reversed(origins):
            if o.confirmed and not o.invalidated:
                if o.type == "SHORT" and pd == "PREMIUM":
                    if cj.high >= o.hold_low and cj.low <= o.hold_high:
                        if cj.high < o.break_level:
                            state = "ALERT"
                            alert_bias = "SHORT"
                            alert_origin = o
                            alert_start_idx = i
                            stats["activations"] += 1
                            break
                            
                elif o.type == "LONG" and pd == "DISCOUNT":
                    if cj.low <= o.hold_high and cj.high >= o.hold_low:
                        if cj.low > o.break_level:
                            state = "ALERT"
                            alert_bias = "LONG"
                            alert_origin = o
                            alert_start_idx = i
                            stats["activations"] += 1
                            break

print("--- Backtest Statistics ---")
for k, v in stats.items():
    print(f"{k}: {v}")
    
winrate = 0 if (stats['wins'] + stats['losses']) == 0 else stats['wins'] / (stats['wins'] + stats['losses']) * 100
print(f"Winrate: {winrate:.2f}%")

print("\n--- LAATSTE 3 EXECUTIONS ---")
for t in completed_trades[-3:]:
    o = t['trade']['origin_group']
    print(f"\n[{t['trade']['type']} TRADE]")
    print(f" Hold Level TS:     {o.hold_ts}")
    print(f" Break Candle TS:   {o.break_ts}")
    print(f" Hard Close TS:     {o.hard_close_ts}")
    print(f" Limit Executed TS: {t['entered_ts']}")
    print(f"  > Entry Price (Open of Hold): {t['trade']['price']:.2f}")
    print(f"  > Stop Loss: {t['trade']['sl']:.2f}")
    print(f"  > Take Profit: {t['trade']['tp']:.2f}")
    print(f"  > Alert TS (P/D Check): {t['trade']['alert_ts']} (Eq: {t['trade']['alert_eq']:.2f})")
