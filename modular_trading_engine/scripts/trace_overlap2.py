import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
candles = load_historical_1m_data('data/historical/NQ_1min.csv')
for c in candles[-1000:]:
    if c.timestamp.strftime('%H:%M') in ['19:06', '19:07', '19:08', '19:09', '19:10', '19:11']:
        print(f"{c.timestamp.strftime('%H:%M')} | H:{c.high} L:{c.low}")
