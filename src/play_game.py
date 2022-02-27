"""
Starts bots for interacting with the Crabada Dapp P2E game
"""
import argparse
import dotenv
import os
import time
import typing

from config import USERS
from crabada.bot import CrabadaBot

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", help="Dry run")
    return parser.parse_args()

def run_bot() -> None:
    args = parse_args()

    bots = [CrabadaBot(user, config, args.dry_run) for user, config in USERS.items()]

    try:
        for bot in bots:
            print(f"Starting game bot for user {bot.get_user()}...")
            bot.run()
    finally:
        for bot in bots:
            print(f"Ending game bot for user {bot.get_user()}...")
            bot.end()




if __name__ == "main":
    run_bot()
