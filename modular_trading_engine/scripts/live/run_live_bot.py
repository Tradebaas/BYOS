import os
import sys
import argparse
import asyncio
import logging
from pathlib import Path

# Ensure engine root is on sys.path (works from any CWD)
_engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _engine_root not in sys.path:
    sys.path.insert(0, _engine_root)
os.chdir(_engine_root)  # So relative paths like 'data/' and 'strategies/' resolve

from src.layer4_execution.live_fleet_commander import LiveFleetCommander

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("LiveBotRunner")

def main():
    parser = argparse.ArgumentParser(description='Live Fleet Commander Orchestrator')
    parser.add_argument('--strategy', type=str, help='Name of the strategy pod (e.g., dtd_golden_setup)', default=None)
    args = parser.parse_args()

    commander = LiveFleetCommander(strategy_name=args.strategy)
    
    # Run the initialization
    init_success = asyncio.run(commander.initialize())
    if not init_success:
        logger.error("Initialization failed. Exiting.")
        sys.exit(1)
        
    try:
        asyncio.run(commander.run_forever())
    except KeyboardInterrupt:
        logger.info("Fleet Commander terminated by user.")

if __name__ == "__main__":
    main()
