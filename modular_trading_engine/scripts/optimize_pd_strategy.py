import os
import sys
import itertools
from concurrent.futures import ProcessPoolExecutor

os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.getcwd())

from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data

from datetime import timedelta
print("Loading data for optimization...", flush=True)
candles = load_historical_1m_data('modular_trading_engine/data/historical/NQ_1min.csv')

last_candle_time = candles[-1].timestamp
# 10 trading days = ~14 calendar days
start_time = last_candle_time - timedelta(days=14)
candles = [c for c in candles if c.timestamp >= start_time]
print(f"Data sliced to last 10 trading days: {len(candles)} candles remaining.", flush=True)

class OriginGroup:
    __slots__ = ['type', 'hold_idx', 'hold_open', 'hold_high', 'hold_low', 'break_level', 'confirmed', 'invalidated', 'exhausted']
    def __init__(self, t_type, hold_candle, b1_candle, idx_created):
        self.type = t_type
        self.hold_idx = idx_created - 2
        self.hold_open = hold_candle.open
        self.hold_high = hold_candle.high
        self.hold_low = hold_candle.low
        self.break_level = b1_candle.high if t_type == "SHORT" else b1_candle.low
        self.confirmed = False
        self.invalidated = False
        self.exhausted = False

def run_backtest(params):
    pd_window, sl_points, tp_points, ttl_val, be_ratio, contracts, use_pd = params
    
    # We precalculate high/low arrays for ultra fast sliding window min/max
    # Actually, deque or sliding window is faster but doing simple loop for now
    
    origins = []
    state = "SEARCH"
    alert_bias = None
    alert_origin = None
    alert_start_idx = 0
    
    pending_limit = None
    active_trade = None
    
    wins = 0
    losses = 0
    scratches = 0
    
    # Financials (MNQ Dynamic Contracts)
    point_value = 2.0 * contracts # MNQ is $2.00 per point
    commission = 0.82 * contracts # typical MNQ round trip per contract
    current_equity = 0.0
    peak_equity = 0.0
    max_drawdown = 0.0
    blown_account = False

    
    # Simple arrays to avoid full object access overhead
    candle_highs = [c.high for c in candles]
    candle_lows = [c.low for c in candles]
    candle_closes = [c.close for c in candles]
    candle_opens = [c.open for c in candles]
    candle_ts = [c.timestamp for c in candles]
    candle_is_bullish = [c.is_bullish for c in candles]
    candle_is_bearish = [c.is_bearish for c in candles]
    
    num_candles = len(candles)
    
    for i in range(pd_window, num_candles):
        c_high = candle_highs[i]
        c_low = candle_lows[i]
        c_close = candle_closes[i]
        c_open = candle_opens[i]
        c_bullish = candle_is_bullish[i]
        c_bearish = candle_is_bearish[i]
        
        # Calculate PD if needed
        pd = None
        if state == "SEARCH":
            w_h = max(candle_highs[i-pd_window:i])
            w_l = min(candle_lows[i-pd_window:i])
            eq = (w_h + w_l) / 2.0
            pd = "PREMIUM" if candle_closes[i-1] >= eq else "DISCOUNT"

        if state == "TRADE":
            t_type = active_trade['type']
            
            if be_ratio > 0.0 and not active_trade.get('be_triggered', False):
                if t_type == "SHORT":
                    if (active_trade['entry'] - c_low) >= (tp_points * be_ratio):
                        active_trade['sl'] = active_trade['entry']
                        active_trade['be_triggered'] = True
                else:
                    if (c_high - active_trade['entry']) >= (tp_points * be_ratio):
                        active_trade['sl'] = active_trade['entry']
                        active_trade['be_triggered'] = True

            if t_type == "SHORT":
                if c_high >= active_trade['sl']:
                    if active_trade['sl'] == active_trade['entry']:
                        scratches += 1
                        current_equity -= commission
                    else:
                        losses += 1
                        current_equity -= (sl_points * point_value) + commission
                        
                    # Check MDD
                    mdd = peak_equity - current_equity
                    if mdd > max_drawdown:
                        max_drawdown = mdd
                    if max_drawdown >= 3000.0:
                        blown_account = True
                        
                    state = "SEARCH"
                    active_trade = None
                elif c_low <= active_trade['tp']:
                    wins += 1
                    current_equity += (tp_points * point_value) - commission
                    if current_equity > peak_equity:
                        peak_equity = current_equity
                        
                    state = "SEARCH"
                    active_trade = None
            else:
                if c_low <= active_trade['sl']:
                    if active_trade['sl'] == active_trade['entry']:
                        scratches += 1
                        current_equity -= commission
                    else:
                        losses += 1
                        current_equity -= (sl_points * point_value) + commission
                        
                    mdd = peak_equity - current_equity
                    if mdd > max_drawdown:
                        max_drawdown = mdd
                    if max_drawdown >= 3000.0:
                        blown_account = True

                    state = "SEARCH"
                    active_trade = None
                elif c_high >= active_trade['tp']:
                    wins += 1
                    current_equity += (tp_points * point_value) - commission
                    if current_equity > peak_equity:
                        peak_equity = current_equity
                        
                    state = "SEARCH"
                    active_trade = None
            if state == "TRADE": continue

        if state == "PENDING":
            pending_limit['ttl'] -= 1
            limit_price = pending_limit['price']
            filled = False
            
            if pending_limit['type'] == "SHORT":
                if c_high >= limit_price and c_low <= limit_price: filled = True
                elif c_open > limit_price: filled = True
            else:
                if c_low <= limit_price and c_high >= limit_price: filled = True
                elif c_open < limit_price: filled = True
                
            if filled:
                state = "TRADE"
                active_trade = pending_limit
                pending_limit = None
                active_trade["origin_group"].exhausted = True
                continue
                
            if pending_limit['ttl'] <= 0:
                state = "SEARCH"
                pending_limit = None
            continue

        if i >= 2:
            if candle_is_bullish[i-2] and candle_is_bearish[i-1] and c_bearish:
                origins.append(OriginGroup("SHORT", candles[i-2], candles[i-1], i))
            if candle_is_bearish[i-2] and candle_is_bullish[i-1] and c_bullish:
                origins.append(OriginGroup("LONG", candles[i-2], candles[i-1], i))

        newly_confirmed = []
        for o in origins:
            if not o.confirmed and not o.invalidated:
                if o.type == "SHORT":
                    if c_bearish and c_open < o.hold_low and c_close < o.hold_low:
                        o.confirmed = True
                        newly_confirmed.append(o)
                    elif c_high > o.hold_high:
                        o.invalidated = True
                else:
                    if c_bullish and c_open > o.hold_high and c_close > o.hold_high:
                        o.confirmed = True
                        newly_confirmed.append(o)
                    elif c_low < o.hold_low:
                        o.invalidated = True
                        
        origins = [o for o in origins if not o.invalidated]

        if state == "ALERT":
            invalidated = False
            if alert_bias == "SHORT" and c_high >= alert_origin.break_level: invalidated = True
            if alert_bias == "LONG" and c_low <= alert_origin.break_level: invalidated = True
                
            if invalidated:
                state = "SEARCH"
                alert_origin.invalidated = True
                alert_origin = None
            else:
                for o in newly_confirmed:
                    if o.type == alert_bias and o.hold_idx >= alert_start_idx:
                        state = "PENDING"
                        price = o.hold_open
                        sl = price + sl_points if o.type == "SHORT" else price - sl_points
                        tp = price - tp_points if o.type == "SHORT" else price + tp_points
                        
                        pending_limit = {"type": o.type, "origin_group": o, "entry": price, "price": price, "sl": sl, "tp": tp, "ttl": ttl_val, "be_triggered": False}
                        break

        # NY Killzone check roughly 14:00 to 20:59 UTC
        is_killzone = (14 <= candle_ts[i].hour <= 20)

        if state == "SEARCH" and is_killzone:
            for o in reversed(origins):
                if o.confirmed and not o.invalidated and not o.exhausted:
                    if o.type == "SHORT" and (not use_pd or pd == "PREMIUM"):
                        if c_high >= o.hold_low and c_low <= o.hold_high and c_high < o.break_level:
                            state = "ALERT"
                            alert_bias = "SHORT"
                            alert_origin = o
                            alert_start_idx = i
                            break
                    elif o.type == "LONG" and (not use_pd or pd == "DISCOUNT"):
                        if c_low <= o.hold_high and c_high >= o.hold_low and c_low > o.break_level:
                            state = "ALERT"
                            alert_bias = "LONG"
                            alert_origin = o
                            alert_start_idx = i
                            break
                            
    total_trades = wins + losses + scratches
    winrate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    return {
        "params": params,
        "trades": total_trades,
        "wins": wins,
        "losses": losses,
        "scratches": scratches,
        "winrate": winrate,
        "profit_usd": current_equity,
        "mdd_usd": max_drawdown,
        "blown": blown_account
    }

if __name__ == '__main__':
    # Define micro-grid for final sprint
    pd_windows = [180, 200, 220, 240]
    sls = [22, 25, 28, 30] 
    tps = [40, 50, 60]
    ttls = [8, 10, 12, 15]
    be_ratios = [0.4, 0.5, 0.6] 
    
    grid = []
    for pd_win in pd_windows:
        for sl in sls:
            for tp in tps:
                if sl <= tp:
                    for ttl in ttls:
                        for be in be_ratios:
                            grid.append((pd_win, sl, tp, ttl, be, 15, True))
                    
    print(f"Testing {len(grid)} configurations...", flush=True)
    
    def print_res(res):
        p_pd, p_sl, p_tp, p_ttl, p_be_r, p_c, p_usepd = res['params']
        be_str = f"@{p_be_r*100:.0f}%" if p_be_r > 0 else "OFF  "
        pd_str = f"{p_pd:3}"

        wr = res['winrate']
        trds = res['trades']
        scr = res['scratches']
        pr_usd = res['profit_usd']
        mdd_usd = res['mdd_usd']
        
        status = "✅ PASS"
        if res['blown']: status = "❌ BLOWN"
        elif pr_usd < 6000.0: status = "⚠️ < 6K" 
        
        return f"[{status}] QTY={p_c:2} | PD={pd_str:3} | SL={p_sl:2} | TP={p_tp:2} | TTL={p_ttl:2} | BE={be_str} || WR: {wr:>5.2f}% | TRDS: {trds:>3} (Scr:{scr:>3}) | PNL: ${pr_usd:>7.2f} | MDD: ${mdd_usd:>7.2f}"

    results = []
    with ProcessPoolExecutor() as executor:
        for res in executor.map(run_backtest, grid):
            if res["trades"] > 10: # Reduced trade count filter as dataset is much shorter
                results.append(res)
                print(print_res(res), flush=True)

    survivors = [r for r in results if not r['blown']]
    survivors = [r for r in survivors if r['profit_usd'] >= 6000] # MUST HIT THE METRIC TO BE LISTED
    
    if not survivors:
         print("\nGeen enkele setup haalde de Topstep requirements (>6k PNL, <3k MDD) in deze ronde.")
    else:
        survivors.sort(key=lambda x: x["winrate"], reverse=True)
        print(f"\n--- TOP 10 BY WINRATE (SURVIVED TOPSTEP 3k MDD & HIT 6k TARGET) ---")
        for r in survivors[:10]:
             print(print_res(r))
             
        survivors.sort(key=lambda x: x["profit_usd"], reverse=True)
        print("\n--- TOP 10 BY PNL (SURVIVED TOPSTEP 3k MDD & HIT 6k TARGET) ---")
        for r in survivors[:10]:
             print(print_res(r))

