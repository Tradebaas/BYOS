from typing import List

from .models import Candle


def resample_candles(candles: List[Candle], timeframe_minutes: int) -> List[Candle]:
    """
    Wiskundig puur transformatie-mechanisme om een lagere resolutie op te schalen.
    Groepereert lijsten van Candle objecten naar een hoger timeframe.
    """
    if not candles:
        return []
    
    if timeframe_minutes <= 1:
        return candles

    resampled = []
    current_bucket_start = None
    current_candles = []

    for c in candles:
        # Bereken de statische starttijd van het blok (in UNIX epoch seconden)
        # Bv. timeframe = 5 (300s). Een epoch van 1201 > wordt 1200.
        epoch = c.timestamp.timestamp()
        tf_seconds = timeframe_minutes * 60
        bucket_epoch = (epoch // tf_seconds) * tf_seconds
        
        if current_bucket_start is None:
            current_bucket_start = bucket_epoch
            
        if bucket_epoch == current_bucket_start:
            current_candles.append(c)
        else:
            # Finaliseer vorig blok
            resampled.append(_build_resampled_candle(current_candles))
            # Start nieuw blok
            current_bucket_start = bucket_epoch
            current_candles = [c]
            
    # Voeg het laatste blok toe
    if current_candles:
        resampled.append(_build_resampled_candle(current_candles))
        
    return resampled


def _build_resampled_candle(bucket: List[Candle]) -> Candle:
    """
    Interne helper operatie om een array met candles plat te slaan tot één representatieve candle.
    """
    first = bucket[0]
    last = bucket[-1]
    
    _high = max(c.high for c in bucket)
    _low = min(c.low for c in bucket)
    _vol = sum(c.volume for c in bucket)
    
    return Candle(
        timestamp=first.timestamp,
        open=first.open,
        high=_high,
        low=_low,
        close=last.close,
        volume=_vol
    )
