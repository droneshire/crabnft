import argparse
import json
import logging
import os
import time

from mechavax.monitor import MechMonitor
from utils import logger


GUILD_WALLET_ADDRESS = "0xA3270d8bF65039680cdC9f61f83578c85ca9ad47"
STATS_INTERVAL = 60.0 * 60.0

GUILD_WALLET_MAPPING = {
    "0xB45ef8Aec53d763E7B18a01f1C43BE2825Bd3b36": "Star Fox",
    "0x9B258494A49837dFE0d8874170dB82FE1e638552": "Off Regularly",
    "0x5Bf93365bbf06DDE2669B2633E50fCFb3f6f8e1C": "Blue Digger",
    "0xD5f769CbC89773775792Def99ece766Ed65BC2c2": "Almugu",
    "0xBe8CFD634Ab8D91BA391D3A22D3E1D452c0A43cb": "Nft Cashflow",
    "0xf17668Ff22c63E63475D5f7DbDf7585D51E52c76": "Primata",
    "0x26930eb38E475ba24F36d6403271927b95836caa": "Secret Smoothies",
}


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

    monitor = MechMonitor(args.address, GUILD_WALLET_MAPPING, "MECHAVAX_BOT", STATS_INTERVAL)
    monitor.run()


if __name__ == "__main__":
    run_bot()
