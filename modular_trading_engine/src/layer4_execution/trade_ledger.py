import csv
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("TradeLedger")

class TradeLedger:
    """
    A lightweight, decoupled ledger responsible for recording filled execution trades.
    Does NOT interfere with active strategy evaluation.
    """
    def __init__(self, root_dir: str):
        self.csv_path = Path(root_dir) / "modular_trading_engine" / "data" / "historical" / "trade_ledger.csv"
        self._ensure_csv_exists()

    def _ensure_csv_exists(self):
        if not self.csv_path.exists():
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp_entry",
                    "timestamp_exit",
                    "account_id",
                    "symbol",
                    "direction",
                    "entry_price",
                    "exit_price",
                    "pnl_ticks"
                ])

    def log_closed_trade(self, entry_dt: datetime, exit_dt: datetime, account_id: str, symbol: str,
                         direction: str, entry_price: float, exit_price: float, tick_size: float = 0.25):
        """
        Calculates PnL ticks and appends structured trade directly to historical CSV.
        """
        # Calculate PnL in Ticks
        if direction.upper() == "LONG":
            pnl_ticks = (exit_price - entry_price) / tick_size
        else:
            pnl_ticks = (entry_price - exit_price) / tick_size

        entry_str = entry_dt.strftime("%Y-%m-%d %H:%M:%S")
        exit_str = exit_dt.strftime("%Y-%m-%d %H:%M:%S")

        try:
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    entry_str,
                    exit_str,
                    account_id,
                    symbol,
                    direction,
                    round(entry_price, 2),
                    round(exit_price, 2),
                    round(pnl_ticks, 2)
                ])
            logger.info(f"LEGER: Closed {direction} on {symbol} saved to CSV. PnL {pnl_ticks} ticks.")
        except Exception as e:
            logger.error(f"Failed to write to trade_ledger.csv: {e}")
