"""
Starts bots for interacting with the Crabada Dapp P2E game
"""
import argparse
import logging
import os
import sys
import time
from twilio.rest import Client

from config import TWILIO_CONFIG, USERS
from crabada.bot import CrabadaBot
from utils import logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    this_dir = os.path.dirname(os.path.realpath(__file__))
    log_dir = os.path.join(os.path.dirname(this_dir), "logs")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument(
        "-l", "--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO"
    )
    parser.add_argument("-f", "--log-dir", default=log_dir)
    return parser.parse_args()


def setup_log(log_level: str, log_dir: str) -> None:
    if log_level == "NONE":
        return

    log_name = time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime(time.time())) + "_crabada.log"
    log_file = os.path.join(log_dir, log_name)
    logging.basicConfig(
        filename=log_file,
        level=logging.getLevelName(log_level),
        format="[%(levelname)s][%(asctime)s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filemode="w",
    )


def run_bot() -> None:
    args = parse_args()

    setup_log(args.log_level, args.log_dir)

    sms_client = Client(TWILIO_CONFIG["account_sid"], TWILIO_CONFIG["account_auth_token"])

    bots = [
        CrabadaBot(
            user,
            config,
            TWILIO_CONFIG["from_sms_number"],
            TWILIO_CONFIG["admin_sms_number"],
            sms_client,
            args.log_dir,
            args.dry_run,
        )
        for user, config in USERS.items()
    ]

    try:
        for bot in bots:
            bot.run()
    finally:
        for bot in bots:
            bot.end()


if __name__ == "__main__":
    run_bot()
