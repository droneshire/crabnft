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
    parser.add_argument("--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO")
    log_dir = logger.get_logging_dir("pumpskin")
    parser.add_argument("--log-dir", default=log_dir)

    return parser.parse_args()


def setup_log(log_level: str, log_dir: str, id_string: str) -> None:
    if log_level == "NONE":
        return

    log_name = (
        time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime(time.time()))
        + f"_pumpskin_listing_{id_string}.log"
    )

    log_dir = os.path.join(log_dir, "bot")

    if not os.path.isdir(log_dir):
        os.mkdir(log_dir)

    log_file = os.path.join(log_dir, log_name)

    logging.basicConfig(
        filename=log_file,
        level=logging.getLevelName(log_level),
        format="[%(levelname)s][%(asctime)s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filemode="w",
    )


if __name__ == "__main__":
    args = parse_args()
    setup_log(args.log_level, args.log_dir, "listings")
    post_rarist_listings(args.rarity, args.max_price, True)
