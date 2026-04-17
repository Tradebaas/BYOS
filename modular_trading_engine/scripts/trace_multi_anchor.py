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
rule_engine = RuleEngine(playbook_config)

print("Starting execution pipeline trace for 2026-04-16 18:30 -> 19:15...")

for i, c in enumerate(candles):
    theory_state.process_candle(c)
    if c.timestamp.strftime('%Y-%m-%d') == '2026-04-16':
        time_str = c.timestamp.strftime('%H:%M')
        if '18:30' <= time_str <= '19:15':
            context = PipelineContext(theory_state=theory_state, timestamp=c.timestamp)
            for module in rule_engine.pipeline_modules:
                module.process(context)
            if context.intents:
                print(f"[{c.timestamp}] !! INTENT FIRED !! {len(context.intents)} intents.")
                for intent in context.intents:
                    print(f"    -> {intent.direction.upper()} @ {intent.entry_price} (SL: {intent.stop_loss}, TP: {intent.take_profit})")
            elif context.setup_candidates:
                print(f"[{c.timestamp}] Candidate staged but blocked by downstream (Killzone/TTL/RAT): {len(context.setup_candidates)}")
