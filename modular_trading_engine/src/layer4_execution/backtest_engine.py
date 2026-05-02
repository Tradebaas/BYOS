import logging
from datetime import datetime, timezone
import pandas as pd
from typing import Dict, Any

from src.layer1_data.models import Candle
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer4_execution.data_vault import DataVault
from src.layer4_execution.simulator import BacktestSimulator

def format_color(pnl: float) -> str:
    return "🟢" if pnl >= 0 else "🔴"

class BacktestSession:
    """
    Standardized offline backtest execution session.
    Provides a guaranteed 1-by-1 candle loop mirroring the LiveFleetCommander architecture.
    """
    def __init__(self, playbook_path: str = None, playbook_dict: dict = None):
        if playbook_dict is not None:
            self.cfg = ConfigParser.load_playbook_from_dict(playbook_dict) if hasattr(ConfigParser, 'load_playbook_from_dict') else None
            if not self.cfg:
                import json
                temp_path = '.tmp/temp_playbook.json'
                with open(temp_path, 'w') as f:
                    json.dump(playbook_dict, f)
                self.cfg = ConfigParser.load_playbook(temp_path)
        elif playbook_path is not None:
            self.cfg = ConfigParser.load_playbook(playbook_path)
        else:
            raise ValueError("Must provide either playbook_path or playbook_dict")
            
        self.engine = RuleEngine(self.cfg)
        self.vault = DataVault()
        
        # Load instrument defaults from the strategy global settings
        self.multiplier = self.cfg.global_settings.multiplier
        self.position_size = self.cfg.global_settings.position_size
        self.instrument = self.cfg.global_settings.instrument
        self.commission = self.cfg.global_settings.commission
        
        self.sim = BacktestSimulator(self.vault, commission_per_contract=self.commission, position_size=self.position_size)
        self.state = MarketTheoryState()

    def run(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Executes the backtest strictly sequentially over the provided DataFrame.
        Returns a dictionary containing all relevant statistics.
        """
        last_ordered_setup_price = None
        last_ordered_setup_direction = None
        last_trade_count = 0
        
        for i, row in df.iterrows():
            c = Candle(
                timestamp=row['datetime'],
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume']
            )
            
            self.sim.process_candle(c)
            self.state.process_candle(c)
            
            # Determine if a trade was closed in the previous cycle
            current_trade_count = len(self.vault.trades)
            last_trade_result = None
            last_trade_is_bullish = None
            
            if current_trade_count > last_trade_count:
                last_closed_trade = self.vault.trades[-1]
                last_trade_result = last_closed_trade.pnl_points
                last_trade_is_bullish = last_closed_trade.is_bullish
                last_trade_count = current_trade_count
                
            # Manage Active Positions - skip new entries if we have a position
            if hasattr(self.sim, 'active_pos') and self.sim.active_pos is not None:
                 continue
                 
            # Evaluate Rule Engine Intents
            intents = self.engine.evaluate(self.state, c.timestamp, last_trade_result=last_trade_result, last_trade_is_bullish=last_trade_is_bullish)
            active_intent = intents[-1] if intents else None
            current_setup_price = active_intent.entry_price if active_intent else None
            
            # Check for Pending Entries
            if self.sim.pending_intent is not None:
                if not active_intent or current_setup_price != self.sim.pending_intent.entry_price:
                    self.sim.cancel_all()
                    if active_intent:
                        last_ordered_setup_price = None
                continue
                
            # Place native brackets
            if active_intent:
                if active_intent.entry_price == last_ordered_setup_price and active_intent.is_bullish == last_ordered_setup_direction:
                    continue
                    
                self.sim.stage_order(active_intent)
                last_ordered_setup_price = active_intent.entry_price
                last_ordered_setup_direction = active_intent.is_bullish
                
        return self._generate_report()
        
    def _generate_report(self) -> Dict[str, Any]:
        daily_stats = {}
        total_commissions = 0.0
        conflicts = 0
        same_minute_exits = 0
        
        for t in self.vault.trades:
            ts = getattr(t, 'exit_time', getattr(t, 'entry_time', None))
            if ts is None:
                 continue
                 
            # Check if entry and exit happened in the exact same 1-minute candle
            if getattr(t, 'entry_time', None) == getattr(t, 'exit_time', None):
                same_minute_exits += 1
            
            day_str = ts.strftime('%Y-%m-%d')
            if day_str not in daily_stats:
                daily_stats[day_str] = {'trades': 0, 'wins': 0, 'losses': 0, 'net_pnl_usd': 0.0}
                
            daily_stats[day_str]['trades'] += 1
            
            trade_usd_pnl = (t.pnl_points * self.multiplier * self.position_size)
            daily_stats[day_str]['net_pnl_usd'] += trade_usd_pnl
            
            is_win = getattr(t, 'win', t.pnl_points > 0)
            if is_win:
                daily_stats[day_str]['wins'] += 1
            else:
                daily_stats[day_str]['losses'] += 1
                
            total_commissions += t.commission_usd
            if t.same_candle_conflict:
                conflicts += 1

        total_trades = sum(d['trades'] for d in daily_stats.values())
        total_wins = sum(d['wins'] for d in daily_stats.values())
        total_net_raw = sum(d['net_pnl_usd'] for d in daily_stats.values())
        
        total_net_after_fees = total_net_raw - total_commissions
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        daily_pnls = [d['net_pnl_usd'] for d in daily_stats.values()]
        worst_day_pnl = min(daily_pnls) if daily_pnls else 0
        
        # Max drawdown from trade-by-trade cumulative PnL (including fees iteratively)
        cumulative_pnl = 0
        peak = 0
        max_drawdown = 0
        
        sorted_trades = sorted(self.vault.trades, key=lambda t: getattr(t, 'exit_time', getattr(t, 'entry_time', datetime.min.replace(tzinfo=timezone.utc))))
        
        for t in sorted_trades:
            cumulative_pnl += (t.pnl_points * self.multiplier * self.position_size) - t.commission_usd
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            drawdown = peak - cumulative_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                
        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "total_net_raw_usd": total_net_raw,
            "total_commissions_usd": total_commissions,
            "total_net_after_fees_usd": total_net_after_fees,
            "worst_day_pnl_usd": worst_day_pnl,
            "max_drawdown_usd": max_drawdown,
            "same_candle_conflicts": conflicts,
            "same_minute_exits": same_minute_exits,
            "daily_stats": daily_stats,
            "trades": sorted_trades
        }

    def print_report(self, report: Dict[str, Any]) -> None:
        logging.info("\n| Date | Total Trades | Wins | Losses | Net PnL (Raw) |")
        logging.info("|---|---|---|---|---|")
        daily_stats = report["daily_stats"]
        for day in sorted(daily_stats.keys()):
            stats = daily_stats[day]
            net = stats['net_pnl_usd']
            color = format_color(net)
            logging.info(f"| {day} | {stats['trades']} | {stats['wins']} | {stats['losses']} | {color} ${net:.2f} |")

        logging.info("\n==============================================")
        logging.info(f"📈 SIMULATIE RAPPORT ({self.instrument} - {self.position_size} Contract{'s' if self.position_size > 1 else ''} @ ${self.multiplier}/pt | Fee: ${self.commission}/ct)")
        logging.info("==============================================")
        logging.info(f"Totaal Aantal Trades: {report['total_trades']}")
        logging.info(f"Win Rate:             {report['win_rate']:.1f}%")
        logging.info(f"Totaal Bruto PnL:     ${report['total_net_raw_usd']:.2f}")
        logging.info(f"Totaal Commissies:    ${report['total_commissions_usd']:.2f}")
        logging.info(f"Netto PnL (na fees):  {format_color(report['total_net_after_fees_usd'])} ${report['total_net_after_fees_usd']:.2f}")
        logging.info(f"Slechtste Dag PnL:    🔴 ${report['worst_day_pnl_usd']:.2f}")
        logging.info(f"Max Drawdown:         🔴 ${report['max_drawdown_usd']:.2f}")
        logging.info("----------------------------------------------")
        logging.info(f"Intra-bar Exits (Entry & Exit zelfde minuut): {report['same_minute_exits']}")
        logging.info(f"Pessimistic conflicten (Beide SL/TP geraakt): {report['same_candle_conflicts']} (Force Loss)")
        logging.info("==============================================\n")
