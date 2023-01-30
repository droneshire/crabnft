import argparse
import json
import logging
import os
import time

from mechavax.monitor import MechMonitor
from utils import logger


GUILD_WALLET_ADDRESS = "0xA3270d8bF65039680cdC9f61f83578c85ca9ad47"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    log_dir = logger.get_logging_dir("mechavax")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--quiet", action="store_true", help="Disable alerts")
    parser.add_argument("--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO")
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument("--address", default=GUILD_WALLET_ADDRESS)
    return parser.parse_args()


def run_bot() -> None:
    args = parse_args()

    log_dir = os.path.join(args.log_dir, "wyndblast")
    logger.setup_log(args.log_level, log_dir, "mechavax_monitor")

    monitor = MechMonitor(args.address, "MECHAVAX_BOT", 5.0)
    monitor.run()


if __name__ == "__main__":
    run_bot()
