import os
import sys
from datetime import timedelta

# Add path so we can import internal modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.layer1_data.csv_parser import load_historical_1m_data

def test_grouped_levels():
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'historical', 'NQ_1min.csv')
    print(f"Loading data from {csv_path}...")
    
    # Parse the CSV data
    all_candles = load_historical_1m_data(csv_path)
    
    if not all_candles:
        print("No candles loaded.")
        return
        
    print(f"Loaded {len(all_candles)} candles. Filtering for the last 1 day...")
    
    # Get the last 1 day of data
    last_timestamp = all_candles[-1].timestamp
    one_day_ago = last_timestamp - timedelta(days=1)
    
    recent_candles = [c for c in all_candles if c.timestamp >= one_day_ago]
    print(f"Filtered to {len(recent_candles)} candles in the last 24 hours.")
    
    results = []
    
    # We need at least 3 candles to find Green, Red, Red or Red, Green, Green
    for i in range(2, len(recent_candles)):
        c2 = recent_candles[i-2] # Vroegste
        c1 = recent_candles[i-1] # Middelste
        c0 = recent_candles[i]   # Nieuwste
        
        # Hard Close logic helper
        def get_hard_close(start_idx, is_bullish_break, level):
            for j in range(start_idx + 1, len(recent_candles)):
                cj = recent_candles[j]
                if is_bullish_break:
                    # Bullish break (Bottom) -> Hard close is a Bearish candle closing below Low of Groen(1)
                    if cj.is_bearish and cj.close < level:
                        return cj
                else:
                    # Bearish break (Top) -> Hard close is a Bullish candle closing above High of Rood(1)
                    if cj.is_bullish and cj.close > level:
                        return cj
            return None

        # Check Bearish Break (Top Side): Groen -> Rood -> Rood
        if c2.is_bullish and c1.is_bearish and c0.is_bearish:
            hc_candle = get_hard_close(i, False, c1.high)
            results.append({
                'type': 'BEARISH_BREAK (Top)',
                'trigger_time': c0.timestamp,
                'groen_1_time': c2.timestamp,
                'rood_1_time': c1.timestamp,
                'rood_1_high': c1.high,
                'groen_1_open': c2.open,
                'groen_1_low': c2.low,
                'hard_close_time': hc_candle.timestamp if hc_candle else None,
                'hard_close_close': hc_candle.close if hc_candle else None
            })
            
        # Check Bullish Break (Bottom Side): Rood -> Groen -> Groen
        if c2.is_bearish and c1.is_bullish and c0.is_bullish:
            hc_candle = get_hard_close(i, True, c1.low)
            results.append({
                'type': 'BULLISH_BREAK (Bottom)',
                'trigger_time': c0.timestamp,
                'rood_1_time': c2.timestamp,
                'groen_1_time': c1.timestamp,
                'groen_1_low': c1.low,
                'rood_1_open': c2.open,
                'rood_1_high': c2.high,
                'hard_close_time': hc_candle.timestamp if hc_candle else None,
                'hard_close_close': hc_candle.close if hc_candle else None
            })
            
    print(f"\nTotaal gevonden groepen: {len(results)}\n")
    
    # Show the last 2 results
    last_results = results[-2:]
    for idx, r in enumerate(last_results):
        print(f"--- MATCH {idx + 1} ---")
        if r['type'] == 'BEARISH_BREAK (Top)':
            print(f"Type:         {r['type']}")
            print(f"Triggered at: {r['trigger_time']} (De tweede Rode candle)")
            print(f"Groen(1) Tijd:{r['groen_1_time']}")
            print(f"Rood(1)  Tijd:{r['rood_1_time']}")
            print(f"-> Rood(1) HIGH : {r['rood_1_high']}")
            print(f"-> Groen(1) OPEN: {r['groen_1_open']}")
            print(f"-> Groen(1) LOW : {r['groen_1_low']}")
        else:
            print(f"Type:         {r['type']}")
            print(f"Triggered at: {r['trigger_time']} (De tweede Groene candle)")
            print(f"Rood(1) Tijd: {r['rood_1_time']}")
            print(f"Groen(1) Tijd:{r['groen_1_time']}")
            print(f"-> Groen(1) LOW : {r['groen_1_low']}")
            print(f"-> Rood(1) OPEN : {r['rood_1_open']}")
            print(f"-> Rood(1) HIGH : {r['rood_1_high']}")
        print()

if __name__ == "__main__":
    test_grouped_levels()
