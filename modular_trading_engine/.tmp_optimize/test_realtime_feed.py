"""
Live Integration Test for TopstepX SignalR Real-Time Feed

This script:
1. Fetches a fresh JWT via the existing headless auth (auth.py)
2. Resolves the active NQ contract ID via the existing REST client
3. Connects to the TopstepX Market Hub via SignalR
4. Listens for 30 seconds, printing every tick and quote
5. Prints a summary and disconnects

Run from BYOS root:
    python -m modular_trading_engine..tmp_optimize.test_realtime_feed

Or directly:
    python modular_trading_engine/.tmp_optimize/test_realtime_feed.py
"""

import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone

# Setup paths — we need both BYOS root and modular_trading_engine on sys.path
# because topstep_client.py uses 'from src.layer1_data.models import Candle'
root_dir = str(Path(__file__).parent.parent.parent)
engine_dir = str(Path(__file__).parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if engine_dir not in sys.path:
    sys.path.insert(0, engine_dir)

from modular_trading_engine.src.layer4_execution.auth import fetch_topstepx_jwt
from modular_trading_engine.src.layer4_execution.models_broker import TopstepCredentials
from modular_trading_engine.src.layer4_execution.topstep_client import TopstepClient
from modular_trading_engine.src.layer4_execution.topstep_realtime import (
    TopstepRealtimeClient,
    TickBuffer,
    Tick,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("RealtimeTest")

# Suppress noisy libraries
logging.getLogger("pysignalr").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)

# ── Test Configuration ────────────────────────────────────────────────
TEST_DURATION_SEC = 30     # How long to listen
PRINT_EVERY_N_TICKS = 1    # Print every Nth tick (1 = all, 10 = every 10th)
ENABLE_DEPTH = False        # DOM depth off by default (too chatty for test)


def on_tick_received(tick: Tick) -> None:
    """Callback fired on every tick for live console output."""
    global tick_print_counter
    tick_print_counter += 1
    
    if tick_print_counter % PRINT_EVERY_N_TICKS == 0:
        side_emoji = "🟢" if tick.side == "BUY" else "🔴"
        ts_str = tick.timestamp.strftime("%H:%M:%S.%f")[:-3]
        print(f"  {side_emoji} TICK | {ts_str} | {tick.price:>10.2f} | {tick.side:<4} | vol={tick.volume}")


tick_print_counter = 0


async def main():
    global tick_print_counter
    
    print("=" * 70)
    print("  TopstepX SignalR Real-Time Feed — Live Integration Test")
    print("=" * 70)
    print()
    
    # ── Step 1: Acquire JWT ───────────────────────────────────────────
    print("📡 Step 1: Acquiring JWT token via headless auth...")
    jwt_token = await fetch_topstepx_jwt()
    
    if not jwt_token:
        print("❌ FAILED: Could not acquire JWT token. Aborting.")
        return
    
    print(f"   ✅ JWT acquired (length: {len(jwt_token)} chars)")
    print()
    
    # ── Step 2: Resolve Contract ID ───────────────────────────────────
    print("📡 Step 2: Resolving active NQ contract ID...")
    
    # We need a dummy account_id just to use the client's contract resolver
    # The contract search endpoint doesn't require a specific account
    creds = TopstepCredentials(account_id=0, jwt_token=jwt_token)
    rest_client = TopstepClient(credentials=creds)
    contract_id = rest_client._get_active_contract("NQ")
    
    if not contract_id:
        print("❌ FAILED: Could not resolve active NQ contract. Aborting.")
        return
    
    print(f"   ✅ Active contract: {contract_id}")
    print()
    
    # ── Step 3: Connect SignalR and listen ─────────────────────────────
    print(f"📡 Step 3: Connecting to Market Hub ({TEST_DURATION_SEC}s test)...")
    print(f"   DOM Depth: {'enabled' if ENABLE_DEPTH else 'disabled'}")
    print()
    print("-" * 70)
    
    buffer = TickBuffer()
    client = TopstepRealtimeClient(
        jwt_token=jwt_token,
        contract_id=contract_id,
        buffer=buffer,
        enable_depth=ENABLE_DEPTH,
        on_tick_callback=on_tick_received,
    )
    
    start_time = datetime.now(timezone.utc)
    
    # Run the client with a timeout
    try:
        # Start client in background task
        feed_task = asyncio.create_task(client.start())
        
        # Wait for connection (max 15s)
        for _ in range(30):
            if client.is_connected:
                break
            await asyncio.sleep(0.5)
        
        if not client.is_connected:
            print("❌ FAILED: Could not establish SignalR connection within 15s")
            feed_task.cancel()
            return
        
        # Listen for TEST_DURATION_SEC seconds
        print(f"\n  🎧 Listening for {TEST_DURATION_SEC} seconds...\n")
        
        # Print periodic stats
        for elapsed in range(TEST_DURATION_SEC):
            await asyncio.sleep(1)
            
            if elapsed > 0 and elapsed % 10 == 0:
                stats = buffer.stats()
                print(f"\n  📊 [{elapsed}s] Ticks: {stats['tick_count']} | "
                      f"Quotes: {stats['quote_count']} | "
                      f"Price: {stats['latest_price']:.2f} | "
                      f"Spread: {stats['spread']:.2f}\n")
        
        # Done listening
        print("-" * 70)
        
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"❌ Error during test: {e}")
    finally:
        # Clean shutdown
        await client.stop()
        feed_task.cancel()
        try:
            await feed_task
        except (asyncio.CancelledError, Exception):
            pass
    
    # ── Step 4: Print Summary ─────────────────────────────────────────
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    stats = buffer.stats()
    
    print()
    print("=" * 70)
    print("  TEST RESULTS")
    print("=" * 70)
    print(f"  Duration:       {duration:.1f}s")
    print(f"  Ticks received: {stats['tick_count']}")
    print(f"  Quotes received:{stats['quote_count']}")
    print(f"  Ticks/second:   {stats['tick_count'] / max(duration, 1):.1f}")
    print(f"  Latest price:   {stats['latest_price']:.2f}")
    print(f"  Latest bid:     {stats['latest_bid']:.2f}")
    print(f"  Latest ask:     {stats['latest_ask']:.2f}")
    print(f"  Spread:         {stats['spread']:.2f}")
    print(f"  Buffer usage:   {stats['buffer_ticks']}/{buffer._ticks.maxlen} ticks")
    print("=" * 70)
    
    if stats['tick_count'] > 0:
        print("\n  ✅ TEST PASSED — Real-time feed is operational!")
        
        # Show last 5 ticks
        recent = buffer.latest_ticks(5)
        if recent:
            print("\n  Last 5 ticks:")
            for t in recent:
                side_emoji = "🟢" if t.side == "BUY" else "🔴"
                print(f"    {side_emoji} {t.timestamp.strftime('%H:%M:%S')} | {t.price:.2f} | {t.side} | vol={t.volume}")
    else:
        print("\n  ⚠️  No ticks received — market may be closed or auth expired")
        print("     NQ futures trade Sun 6pm - Fri 5pm ET (with daily halt 5:00-6:00pm ET)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n  Interrupted by user.")
