import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer3_strategy.pipeline_context import PipelineContext

candles = load_historical_1m_data('data/historical/NQ_1min.csv')
theory_state = MarketTheoryState()
playbook_config = ConfigParser.load_playbook("data/playbooks/day_trading_decrypted.json")
rule_engine = RuleEngine(playbook_config)

print("Starting debug trace...")
for i, c in enumerate(candles):
    theory_state.process_candle(c)
    if '17:40' <= c.timestamp.strftime('%H:%M') <= '18:10' and c.timestamp.strftime('%Y-%m-%d') == '2026-04-13':
        context = PipelineContext(theory_state=theory_state, timestamp=c.timestamp)
        context.active_polarity_is_bullish = False # SHORT
        
        # Manually trace process of confirmation
        module = rule_engine.pipeline_modules[1] # ConfirmationHoldLevelTrigger
        module.process(context)
        
        if context.setup_candidates:
             print(f"[{c.timestamp}] CANDIDATE GENERATED: {context.setup_candidates[-1].level_data.price_open}")
