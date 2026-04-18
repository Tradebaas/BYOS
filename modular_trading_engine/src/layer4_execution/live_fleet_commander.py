import os
import sys
import csv
import time
import json
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

# Fix relative paths so it can find BYOS root modules
root_dir = str(Path(__file__).parent.parent.parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from modular_trading_engine.src.layer1_data.models import Candle
from modular_trading_engine.src.layer3_strategy.models import OrderIntent
from modular_trading_engine.src.layer4_execution.models_broker import TopstepCredentials
from modular_trading_engine.src.layer4_execution.topstep_client import TopstepClient
from modular_trading_engine.src.layer4_execution.auth import fetch_topstepx_jwt
from modular_trading_engine.src.layer2_theory.market_state import MarketTheoryState
from modular_trading_engine.src.layer3_strategy.config_parser import ConfigParser
from modular_trading_engine.src.layer3_strategy.rule_engine import RuleEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("FleetCommander")

CONFIG_FILE = Path(__file__).parent.parent.parent / "execution_config.json"

class AccountManager:
    def __init__(self, config: dict, client: TopstepClient, theory_state: MarketTheoryState, rule_engine: RuleEngine, global_settings: dict):
        self.config = config
        self.client = client
        self.theory_state = theory_state
        self.rule_engine = rule_engine
        self.global_settings = global_settings
        self.account_id = config.get("account_id")
        self.symbol = config.get("symbol", "MNQ")
        self.order_size = config.get("order_size", 1)
        
        self.is_active = config.get("is_active", False)
        self.max_positions = config.get("max_positions", 1)
        
        # State tracking
        self.placed_entry_orders = [] # keep track of pending limit orders
        self.last_ordered_setup_price = None
        self.last_ordered_setup_direction = None
        
    async def get_positions_and_orders(self):
        """
        Polls Topstep API directly to bypass reliance on local state.
        This provides durability against sleep/wake cycles.
        """
        try:
            # We directly use the session from the unmodified client
            pos_response = self.client._session.get(f"https://userapi.topstepx.com/Position?accountId={self.account_id}")
            orders_response = self.client._session.get(f"https://userapi.topstepx.com/Order?accountId={self.account_id}")
            
            positions = pos_response.json() if pos_response.ok else []
            orders = orders_response.json() if orders_response.ok else []
            
            # Filter for this specific account
            # ProjectX API returns lists of objects. Often they have an "accountId" field.
            if isinstance(positions, list):
                my_positions = [p for p in positions if p.get("accountId") == self.account_id]
            else:
                my_positions = []
                
            if isinstance(orders, list):
                my_orders = [o for o in orders if o.get("accountId") == self.account_id]
            else:
                my_orders = []
                
            return my_positions, my_orders
        except Exception as e:
            logger.error(f"Failed to fetch state for account {self.account_id}: {e}")
            return [], []

    async def _manage_breakeven(self, positions, orders):
        """
        Break-Even Poller:
        Checks if TP1 was filled (e.g. position size went from 4 to 2).
        If yes, and SL is not at BE, modify the SL.
        As the API modification endpoint isn't fully defined in legacy client,
        we outline the logic to PUT /api/Order/ or cancel/flatten.
        """
        # TODO: Implement exact REST payload for moving SL based on Topstep capabilities.
        # Topstep API typically handles order replacement/modification via PUT /api/Order
        pass

    async def execute_cycle(self, latest_candle: Candle):
        if not self.is_active:
            return

        # 1. Resync State
        positions, orders = await self.get_positions_and_orders()
        
        # Determine if we have an active position for the traded symbol
        # Topstep positions typically show 'netSize' != 0
        active_pos = None
        for p in positions:
            if p.get("positionSize", 0) != 0 and self.symbol in p.get("symbolName", ""):
                active_pos = p
                break
                
        # 2. Break-Even Management on active positions
        if active_pos:
            size_remaining = abs(active_pos.get("positionSize", 0))
            # If we had 4 contracts originally and now have 2, TP1 hit!
            if size_remaining == 2:
                # We need to move SL to BE
                await self._manage_breakeven(positions, orders)
                
            # If we are in a position, we do not place new entries.
            return
            
        # 3. Check for Pending Entries
        # If we have any un-triggered limit orders, we check if they are still valid or need cancelling.
        # But per the plan, 1 active position lock also covers pending limits.
        # We assume if we have working limits, we shouldn't place more.
        working_entry_orders = [o for o in orders if o.get("status") in [1, "Working", "Pending"] and o.get("type", 1) == 1 and not o.get("isStop")]

        # Evaluate rule engine intents
        intents = self.rule_engine.evaluate(theory_state=self.theory_state, timestamp=latest_candle.timestamp)
        
        active_intent = intents[-1] if intents else None
        current_setup_price = active_intent.entry_price if active_intent else None

        # 3. Check for Pending Entries & Handle Cancellation
        if len(working_entry_orders) > 0:
            prices = [o.get("limitPrice") for o in working_entry_orders]
            
            # If there's no active setup, or the API limit price doesn't match the active engine setup:
            if not active_intent or current_setup_price not in prices:
                logger.info(f"Account {self.account_id}: Working orders out of sync with engine (TTL cleanup or setup shift). Executing CancelAll...")
                success = self.client.cancel_all_orders(self.symbol)
                logger.info(f"CancelAll Response: {success}")
                # Clear deduplication state so the new setup can fire on the next cycle
                if active_intent:
                    self.last_ordered_setup_price = None
                
            return # Let the next cycle read the clean API state before firing new orders

        if active_intent:
            direction = "LONG" if active_intent.is_bullish else "SHORT"
            logger.debug(f"DEBUG: Setup price={active_intent.entry_price}, Last ordered={self.last_ordered_setup_price}")
            # Prevent infinite order spam if account is ineligible/rejecting
            if active_intent.entry_price == self.last_ordered_setup_price and active_intent.is_bullish == self.last_ordered_setup_direction:
                return
                
            logger.info(f"Account {self.account_id}: Detected Setup! {direction} at {active_intent.entry_price} (SL: {active_intent.stop_loss}, TP: {active_intent.take_profit})")
            
            if self.global_settings.get("dry_run_mode", True):
                logger.info(f"DRY RUN MODE: Skipping live execution for {direction}")
                return
                
            # 5. Place Native Brackets
            logger.info(f"Account {self.account_id}: Placing Golden Standard bracket for {self.order_size} {self.symbol}...")
            resp = self.client.execute_intent(active_intent, base_symbol=self.symbol, size=self.order_size)
            logger.info(f"Bracket Response: {resp}")
            
            # Lock the setup to prevent spam
            self.last_ordered_setup_price = active_intent.entry_price
            self.last_ordered_setup_direction = active_intent.is_bullish


class LiveFleetCommander:
    def __init__(self, strategy_name=None):
        self.strategy_name = strategy_name or "dtd_golden_setup"
        self.accounts = []
        self.global_settings = {}
        # Strategy specific execution
        self.theory_state = MarketTheoryState()
        self.rule_engine = None
        self.data_client = None
        self.log_queue = asyncio.Queue()

    async def _csv_queue_worker(self, csv_path: Path):
        """Background worker to write log entries sequentially without blocking the async loop."""
        while True:
            row = await self.log_queue.get()
            if row is None:
                self.log_queue.task_done()
                break
                
            batch = [row]
            while not self.log_queue.empty():
                try:
                    next_row = self.log_queue.get_nowait()
                    if next_row is None:
                        # Re-enqueue the sentinel so future iterations gracefully stop if multiple calls.
                        self.log_queue.put_nowait(None)
                        break
                    batch.append(next_row)
                except asyncio.QueueEmpty:
                    break
                    
            def _write_batch():
                with open(csv_path, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(batch)
                    
            await asyncio.to_thread(_write_batch)
            for _ in batch:
                self.log_queue.task_done()

    def load_config(self):
        try:
            if self.strategy_name:
                config_path = Path(root_dir) / "modular_trading_engine" / "strategies" / self.strategy_name / "execution_config.json"
            else:
                config_path = Path(root_dir) / "modular_trading_engine" / "execution_config.json"
                
            with open(config_path, "r") as f:
                data = json.load(f)
                self.global_settings = data.get("global_settings", {})
                return data.get("accounts", [])
        except Exception as e:
            logger.error(f"Failed to load execution_config.json: {e}")
            return []

    async def initialize(self):
        logger.info("Initializing Live Fleet Commander...")
        accounts_conf = self.load_config()
        
        jwt_token = await fetch_topstepx_jwt()
        if not jwt_token:
            logger.error("Failed to acquire JWT token. Aborting execution.")
            return False
            
        for acc in accounts_conf:
            creds = TopstepCredentials(account_id=acc["account_id"], jwt_token=jwt_token)
            client = TopstepClient(credentials=creds, tick_size=0.25)
            
            # The first client acts as the central data provider
            if not self.data_client:
                self.data_client = client
                
            if not self.rule_engine:
                if self.strategy_name:
                    playbook_path = Path(root_dir) / "modular_trading_engine" / "strategies" / self.strategy_name / "strategy_playbook.json"
                else:
                    playbook_path = Path(root_dir) / "modular_trading_engine" / "data" / "playbooks" / "day_trading_decrypted.json"
                
                playbook_config = ConfigParser.load_playbook(str(playbook_path))
                self.rule_engine = RuleEngine(playbook_config)
                
            manager = AccountManager(
                config=acc,
                client=client,
                theory_state=self.theory_state,
                rule_engine=self.rule_engine,
                global_settings=self.global_settings
            )
            self.accounts.append(manager)
            
        return True

    async def run_forever(self):
        # 1. Warm-up phase (Local CSV -> API Gap Sync)
        logger.info("Fleet Commander: Warming up internal TheoryEngine from historical DB...")
        csv_path = Path(root_dir) / "modular_trading_engine" / "data" / "historical" / "NQ_1min.csv"
        
        # Start background CSV worker to decouple I/O bottlenecks
        asyncio.create_task(self._csv_queue_worker(csv_path))
        
        last_processed_timestamp = None
        
        if csv_path.exists():
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    timestamp_ms = int(row['timestamp_ms'])
                    dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
                    c = Candle(
                        timestamp=dt,
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=float(row['volume'])
                    )
                    self.theory_state.process_candle(c)
                    last_processed_timestamp = c.timestamp
                    count += 1
            logger.info(f"Loaded {count} candles from local DB. Latest timestamp: {last_processed_timestamp}")
        else:
            logger.warning("No local CSV found. Starting from scratch!")
        
        # Determine gap
        now_sec = int(time.time())
        
        if last_processed_timestamp:
            last_sec = int(last_processed_timestamp.timestamp())
            
            if now_sec - last_sec > 60:
                logger.info(f"Syncing gap of {now_sec - last_sec} seconds from Topstep API...")
                gap_bars = self.data_client.fetch_historical_bars_range(from_sec=last_sec, to_sec=now_sec, symbol="/NQ", resolution="1")
                
                with open(csv_path, 'a', newline='') as f: # append mode
                    writer = csv.writer(f)
                    current_minute = datetime.now(timezone.utc).replace(second=0, microsecond=0)
                    for b in gap_bars:
                        # Append only strictly newer candles AND only if they are fully closed
                        if b.timestamp > last_processed_timestamp and b.timestamp < current_minute:
                            self.theory_state.process_candle(b)
                            timestamp_ms = int(b.timestamp.timestamp() * 1000)
                            dt_str = b.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                            # Schema: timestamp_ms,datetime_utc,open,high,low,close,volume,trade_count
                            writer.writerow([timestamp_ms, dt_str, b.open, b.high, b.low, b.close, b.volume, 0])
                            last_processed_timestamp = b.timestamp
                logger.info("Successfully patched historical data gap and synchronized TheoryEngine.")
            else:
                logger.info("Local DB is fully up-to-date. No gap sync needed.")
        else:
            # If no CSV exists, just fetch the last 2000 minutes as fallback
            gap_bars = self.data_client.fetch_historical_bars(symbol="/NQ", resolution="1", lookback_mins=2000)
            # Create the CSV with header
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp_ms","datetime_utc","open","high","low","close","volume","trade_count"])
                for b in gap_bars:
                    self.theory_state.process_candle(b)
                    timestamp_ms = int(b.timestamp.timestamp() * 1000)
                    dt_str = b.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    writer.writerow([timestamp_ms, dt_str, b.open, b.high, b.low, b.close, b.volume, 0])
                    last_processed_timestamp = b.timestamp
            logger.info("Created new local DB with initial fallback data.")
            

        interval = self.global_settings.get("poll_interval_sec", 1)
        logger.info(f"Entering continuous live loop (Interval: {interval}s)...")
        
        while True:
            try:
                # Polling for live candles
                recent_bars = self.data_client.fetch_historical_bars(symbol="/NQ", resolution="1", lookback_mins=5)
                
                # We ONLY process completely closed candles to prevent 'ghost ticks' 
                # from permanently cementing a fake candle in the TheoryEngine state.
                current_minute = datetime.now(timezone.utc).replace(second=0, microsecond=0)
                
                new_bars = [
                    b for b in recent_bars 
                    if (last_processed_timestamp is None or b.timestamp > last_processed_timestamp) 
                    and b.timestamp < current_minute
                ]
                
                if new_bars:
                    for bar in new_bars:
                        self.theory_state.process_candle(bar)
                        
                        # Log live candles linearly to CSV without blocking
                        timestamp_ms = int(bar.timestamp.timestamp() * 1000)
                        dt_str = bar.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                        self.log_queue.put_nowait([timestamp_ms, dt_str, bar.open, bar.high, bar.low, bar.close, bar.volume, 0])
                        
                        last_processed_timestamp = bar.timestamp
                        
                        active_orgs_raw = self.theory_state.get_active_origin_levels()
                        
                        # Filter explicitly to the strategy's 200-candle bias window
                        history_len = len(self.theory_state.history)
                        if history_len > 0:
                            cutoff_ts = self.theory_state.history[max(0, history_len - 200)].timestamp
                            active_orgs = [o for o in active_orgs_raw if o.timestamp >= cutoff_ts]
                        else:
                            active_orgs = []
                            
                        org_info = f"Tracked Origins (200-Window): {len(active_orgs)}"
                        logger.info(f"❤️ Heartbeat | Processed candle {dt_str} UTC | Price: {bar.close} | {org_info}")
                        
                        # Run Strategy Checks
                        for acc in self.accounts:
                            await acc.execute_cycle(bar)
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in main orchestration loop: {e}")
                await asyncio.sleep(5) # Delay on error before retry

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Live Fleet Commander Orchestrator')
    parser.add_argument('--strategy', type=str, help='Name of the strategy pod (e.g., dtd_golden_setup)', default=None)
    args = parser.parse_args()

    commander = LiveFleetCommander(strategy_name=args.strategy)
    asyncio.run(commander.initialize())
    try:
        asyncio.run(commander.run_forever())
    except KeyboardInterrupt:
        logger.info("Fleet Commander terminated by user.")
