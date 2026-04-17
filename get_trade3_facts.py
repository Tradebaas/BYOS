import sys, os
sys.path.append(os.path.abspath('.'))
from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
candles = load_historical_1m_data('modular_trading_engine/data/historical/NQ_1min.csv')

class OriginGroup:
    def __init__(self, t_type, hold_candle, b1_candle, idx):
        self.type = t_type
        self.hold_idx = idx - 2
        
        self.hold_ts = hold_candle.timestamp
        self.break_ts = b1_candle.timestamp
        self.hard_close_ts = None
        
        self.hold_open = hold_candle.open
        self.hold_high = hold_candle.high
        self.hold_low = hold_candle.low
        self.break_level = b1_candle.high if t_type == "SHORT" else b1_candle.low
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
completed_trades = []

def get_pd(idx):
    if idx < 500: return None
    window = candles[idx-500:idx]
    eq = (max(c.high for c in window) + min(c.low for c in window)) / 2
    return "PREMIUM" if candles[idx-1].close >= eq else "DISCOUNT", eq

for i in range(500, len(candles)):
    cj = candles[i]
    ts = str(cj.timestamp)
    pd, eq = get_pd(i)
    
    if state == "TRADE":
        t_type = active_trade['type']
        if t_type == "SHORT" and (cj.high >= active_trade['sl'] or cj.low <= active_trade['tp']):
            state = "SEARCH"
            active_trade = None
        elif t_type == "LONG" and (cj.low <= active_trade['sl'] or cj.high >= active_trade['tp']):
            state = "SEARCH"
            active_trade = None
        if state == "TRADE": continue
            
    if state == "PENDING":
        pending_limit['ttl'] -= 1
        limit_price = pending_limit['price']
        filled = False
        if pending_limit['type'] == "SHORT":
            if (cj.high >= limit_price and cj.low <= limit_price) or cj.open > limit_price: filled = True
        else:
            if (cj.low <= limit_price and cj.high >= limit_price) or cj.open < limit_price: filled = True
                
        if filled:
            state = "TRADE"
            active_trade = pending_limit
            pending_limit = None
            completed_trades.append({'entered_ts': cj.timestamp, 'trade': active_trade})
            if "05:52" in ts: # This is trade 3
                print("FOUND TRADE 3!")
                print(f"Trigger Hold TS: {active_trade['origin_group'].hold_ts}")
                print(f"Activation Touch TS: {active_trade['alert_ts']}")
                print(f"Activation Touch PD Status: {active_trade['alert_pd']} (Eq: {active_trade['alert_eq']:.2f})")
            continue
            
        if pending_limit['ttl'] <= 0:
            state = "SEARCH"
            pending_limit = None
        continue
        
    if i >= 2:
        c2, c1, c0 = candles[i-2], candles[i-1], candles[i]
        if c2.is_bullish and c1.is_bearish and c0.is_bearish: origins.append(OriginGroup("SHORT", c2, c1, i))
        if c2.is_bearish and c1.is_bullish and c0.is_bullish: origins.append(OriginGroup("LONG", c2, c1, i))
            
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
    
    if state == "ALERT":
        if (alert_bias == "SHORT" and cj.high >= alert_origin.break_level) or (alert_bias == "LONG" and cj.low <= alert_origin.break_level):
            state = "SEARCH"
            alert_origin.invalidated = True
            alert_origin = None
        else:
            for o in newly_confirmed:
                if o.type == alert_bias and o.hold_idx >= alert_start_idx:
                    state = "PENDING"
                    price = o.hold_open
                    sl = price + 10.0 if o.type == "SHORT" else price - 10.0
                    tp = price - 20.0 if o.type == "SHORT" else price + 20.0
                    pending_limit = {
                        "type": o.type, "origin_group": o, "price": price,
                        "sl": sl, "tp": tp, "ttl": 25,
                        "alert_ts": alert_ts, "alert_pd": alert_pd, "alert_eq": alert_eq
                    }
                    break

    if state == "SEARCH":
        for o in reversed(origins):
            if o.confirmed and not o.invalidated:
                if (o.type == "SHORT" and pd == "PREMIUM" and cj.high >= o.hold_low and cj.low <= o.hold_high and cj.high < o.break_level) or \
                   (o.type == "LONG" and pd == "DISCOUNT" and cj.low <= o.hold_high and cj.high >= o.hold_low and cj.low > o.break_level):
                    state = "ALERT"
                    alert_bias = o.type
                    alert_origin = o
                    alert_start_idx = i
                    alert_ts = cj.timestamp
                    alert_pd = pd
                    alert_eq = eq
                    break
