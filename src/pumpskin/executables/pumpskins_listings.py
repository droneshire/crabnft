import argparse
import logging
import os
import time

from utils import logger
from pumpskin.listings import post_rarist_listings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rarity", type=float, default=15.0)
    parser.add_argument("--max-price", type=float, default=1.0)
    parser.add_argument(
        "--log-level",
        choices=["INFO", "DEBUG", "ERROR", "NONE"],
        default="INFO",
    )
    log_dir = logger.get_logging_dir("pumpskin")
    parser.add_argument("--log-dir", default=log_dir)

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    logger.setup_log(args.log_level, args.log_dir, "listings")
    post_rarist_listings(args.rarity, args.max_price, True)
