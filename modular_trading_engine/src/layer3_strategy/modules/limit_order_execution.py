from src.layer3_strategy.modules.base import BaseStrategyModule
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer3_strategy.models import OrderIntent
import logging

class RATLimitOrder(BaseStrategyModule):
    """
    Rejection As Target (RAT) Execution Module.
    Transforms remaining filtered mathematical candidates into strict OrderIntents.
    """
    def process(self, context: PipelineContext) -> None:
        tick = self.params.get('tick_size', 0.25)
        front = self.params.get('entry_frontrun_ticks', 0)
        pad = self.params.get('stop_loss_padding_ticks', 0)
        rr = self.params.get('take_profit_rr', 2.0)
        
        breakeven_trigger_rr = self.params.get('breakeven_trigger_rr')
        breakeven_offset_ticks = self.params.get('breakeven_offset_ticks', 0)
        max_stop_loss_points = self.params.get('max_stop_loss_points')
        
        # Strategy ID gets injected normally by the factory, fallback if missing
        strategy_id = self.params.get('strategy_id', 'Unknown-Strategy')
        
        absolute_sl_points = self.params.get('absolute_sl_points')
        absolute_tp_points = self.params.get('absolute_tp_points')
        entry_price_type = self.params.get('entry_price_type', 'open') # 'open' or 'wick'
        
        for tracker in context.setup_candidates:
            level = tracker.level_data
            if level.is_bullish:
                # LONG SETUP
                if entry_price_type == 'wick':
                    entry_price = level.price_low + (front * tick)
                else:
                    entry_price = level.price_open + (front * tick)
                
                if absolute_sl_points is not None and absolute_tp_points is not None:
                    risk = absolute_sl_points
                    stop_loss = entry_price - absolute_sl_points
                    take_profit = entry_price + absolute_tp_points
                else:
                    stop_loss = level.price_low - (pad * tick)
                    risk = entry_price - stop_loss
                    if risk <= 0:
                        continue
                    if max_stop_loss_points is not None and risk > max_stop_loss_points:
                        risk = max_stop_loss_points
                        stop_loss = entry_price - risk
                    take_profit = entry_price + (risk * rr)
                
                breakeven_trigger = None
                breakeven_target = None
                breakeven_trigger_points = self.params.get('breakeven_trigger_points')
                breakeven_target_points = self.params.get('breakeven_target_points', 0.0)
                
                if breakeven_trigger_points is not None:
                    breakeven_trigger = entry_price + breakeven_trigger_points
                    breakeven_target = entry_price + breakeven_target_points
                elif breakeven_trigger_rr is not None:
                    trigger_dist = (take_profit - entry_price) * breakeven_trigger_rr
                    breakeven_trigger = entry_price + trigger_dist
                    breakeven_target = entry_price + (breakeven_offset_ticks * tick)
            else:
                # SHORT SETUP
                if entry_price_type == 'wick':
                    entry_price = level.price_high - (front * tick)
                else:
                    entry_price = level.price_open - (front * tick)
                
                if absolute_sl_points is not None and absolute_tp_points is not None:
                    risk = absolute_sl_points
                    stop_loss = entry_price + absolute_sl_points
                    take_profit = entry_price - absolute_tp_points
                else:
                    stop_loss = level.price_high + (pad * tick)
                    risk = stop_loss - entry_price
                    if risk <= 0:
                        continue
                    if max_stop_loss_points is not None and risk > max_stop_loss_points:
                        risk = max_stop_loss_points
                        stop_loss = entry_price + risk
                    take_profit = entry_price - (risk * rr)
                
                breakeven_trigger = None
                breakeven_target = None
                breakeven_trigger_points = self.params.get('breakeven_trigger_points')
                breakeven_target_points = self.params.get('breakeven_target_points', 0.0)
                
                if breakeven_trigger_points is not None:
                    breakeven_trigger = entry_price - breakeven_trigger_points
                    breakeven_target = entry_price - breakeven_target_points
                elif breakeven_trigger_rr is not None:
                    trigger_dist = (entry_price - take_profit) * breakeven_trigger_rr
                    breakeven_trigger = entry_price - trigger_dist
                    breakeven_target = entry_price - (breakeven_offset_ticks * tick)
                    
            intent = OrderIntent(
                timestamp=context.timestamp,
                is_bullish=level.is_bullish,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy_id=strategy_id,
                theory_reference_ts=level.timestamp.timestamp(),
                breakeven_trigger_price=breakeven_trigger,
                breakeven_target_price=breakeven_target
            )
            logging.debug(f"[{context.timestamp}] Generated {'Long' if level.is_bullish else 'Short'} intent: ep={entry_price} sl={stop_loss} tp={take_profit} ts={level.timestamp}")
            context.intents.append(intent)
