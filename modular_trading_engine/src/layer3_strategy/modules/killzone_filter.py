from datetime import datetime, time
import zoneinfo
from src.layer3_strategy.modules.base import BaseStrategyModule
from src.layer3_strategy.pipeline_context import PipelineContext

class KillzoneFilter(BaseStrategyModule):
    """
    Clears all execution intents if the pipeline context timestamp is outside the configured RTH killzone.
    Default killzone: 09:30 to 16:00 EST.
    """
    def process(self, context: PipelineContext) -> None:
        if not context.setup_candidates:
            return
            
        start_hour = self.params.get('start_hour', 9)
        start_minute = self.params.get('start_minute', 30)
        end_hour = self.params.get('end_hour', 16)
        end_minute = self.params.get('end_minute', 0)
        timezone_str = self.params.get('timezone', 'America/New_York')
        
        try:
            tz = zoneinfo.ZoneInfo(timezone_str)
        except zoneinfo.ZoneInfoNotFoundError:
            tz = zoneinfo.ZoneInfo('America/New_York')
            
        # Convert context timestamp (usually UTC) to the target timezone
        # If the timestamp is naive, assume UTC
        ctx_time = context.timestamp
        if ctx_time.tzinfo is None:
            ctx_time = ctx_time.replace(tzinfo=zoneinfo.ZoneInfo('UTC'))
            
        local_time = ctx_time.astimezone(tz).time()
        
        start_time = time(start_hour, start_minute)
        end_time = time(end_hour, end_minute)
        
        # 1. Check if local_time is strictly within RTH
        is_valid = start_time <= local_time <= end_time
        
        # 2. Check exclusion windows
        exclude_windows = self.params.get('exclude_windows', [])
        for window in exclude_windows:
            ex_start = time(window.get('start_hour', 0), window.get('start_minute', 0))
            ex_end = time(window.get('end_hour', 23), window.get('end_minute', 59))
            if ex_start <= local_time <= ex_end:
                is_valid = False
                break
        
        if not is_valid:
            # Clear out the candidates so nothing passes to the LimitOrder layer
            context.setup_candidates = []
            
