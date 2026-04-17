import sys
sys.path.append('.')
from src.layer1_data.models import Candle
from zebas_core import ZebasEngine
from datetime import datetime

engine = ZebasEngine()
# Mock creating a hold level setup and advancing past 20 candles!

# ... we need to construct candles to trigger a setup.
