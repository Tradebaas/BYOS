import sys, os
from datetime import datetime
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.pipeline_context import PipelineContext

candles = load_historical_1m_data('data/historical/NQ_1min.csv')
theory_state = MarketTheoryState()

playbook_config = ConfigParser.load_playbook('data/playbooks/day_trading_decrypted.json')

# Inject print statements inside ConfirmationHoldLevelTrigger!
import src.layer3_strategy.modules.confirmation_hold_level_trigger as conf_trig
original_process_direction = conf_trig.ConfirmationHoldLevelTrigger.process_direction

class VerboseTrigger(conf_trig.ConfirmationHoldLevelTrigger):
    def process_direction(self, context, is_bullish):
        dir_str = "LONG" if is_bullish else "SHORT"
        
        # Call super or just paste the logic to inject prints safely
        super().process_direction(context, is_bullish)
        
        # We also want to manually duplicate the zone check here so we can print it
        history = context.theory_state.history
        blocks = self.find_blocks(history, max(0, len(history)-1 - 200), is_bullish)
        
        if not blocks: return
        
        active_anchors = []
        locked_until_idx = -1
        for b in blocks:
            b['last_checked_idx'] = b['hc_idx']
            surviving = []
            confirmed = []
            for anchor in active_anchors:
                was_inv = False
                ft = -1
                for k in range(anchor['last_checked_idx'] + 1, b['c1_idx'] + 1):
                    ck = history[k]
                    if is_bullish:
                        if ck.is_bearish and ck.open < anchor['hold'] and ck.close < anchor['hold']:
                            was_inv = True; break
                        if ck.low <= anchor['hold'] and k > locked_until_idx:
                            ft = k
                if was_inv:
                    print(f"[{context.timestamp}] {dir_str} Anchor {history[anchor['c1_idx']].timestamp} INVALIDATED at {history[k].timestamp}")
                    continue
                if ft != -1:
                    confirmed.append({'anchor': anchor, 'b2': b})
                    print(f"[{context.timestamp}] {dir_str} Anchor {history[anchor['c1_idx']].timestamp} TESTED at {history[ft].timestamp} -> CONFIRMED by {history[b['c1_idx']].timestamp}")
                else:
                    anchor['last_checked_idx'] = b['c1_idx']
                    surviving.append(anchor)
            if confirmed:
                best_setup = min(confirmed, key=lambda s: s['anchor']['hold']) if is_bullish else max(confirmed, key=lambda s: s['anchor']['hold'])
                b2 = best_setup['b2']
                hc2 = b2['hc_idx']
                entry = b2['hold']
                
                eval_candles = history[max(0, hc2-200):hc2+1]
                mid = (max(c.high for c in eval_candles) + min(c.low for c in eval_candles))/2
                is_valid = (entry <= mid) if is_bullish else (entry >= mid)
                print(f"[{context.timestamp}] {dir_str} Setups Confirmed. PD Check: {is_valid} (Entry: {entry}, Midpoint: {mid})")
                active_anchors = []
            else:
                surviving.append(b)
                active_anchors = surviving

rule_engine = RuleEngine(playbook_config)
# Replace instance
rule_engine.pipeline_modules[0] = VerboseTrigger({'bias_window_size': 200, 'ttl_candles': 30, 'sl_points': 15.0, 'tp_points': 30.0})

for i, c in enumerate(candles):
    theory_state.process_candle(c)
    if '18:50' <= c.timestamp.strftime('%H:%M') <= '19:15' and c.timestamp.strftime('%Y-%m-%d') == '2026-04-16':
        context = PipelineContext(theory_state=theory_state, timestamp=c.timestamp)
        for module in rule_engine.pipeline_modules:
            module.process(context)
