import argparse
import getpass
import json
import logging
import os
import time

from config_mechavax import (
    GUILD_WALLET_ADDRESS,
    GUILD_WALLET_MAPPING,
    GUILD_WALLET_PRIVATE_KEY,
)
from health_monitor.health_monitor import HealthMonitor
from mechavax.bot import MechBot
from utils import logger
from utils.security import decrypt_secret


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    log_dir = logger.get_logging_dir("mechavax")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--quiet", action="store_true", help="Disable alerts")
    parser.add_argument(
        "--log-level",
        choices=["INFO", "DEBUG", "ERROR", "NONE"],
        default="INFO",
    )
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument("--address", default=GUILD_WALLET_ADDRESS)
    parser.add_argument("--server-url", default="http://localhost:8080/monitor")
    return parser.parse_args()


def run_bot() -> None:
    args = parse_args()

    log_dir = os.path.join(args.log_dir, "mechavax")
    logger.setup_log(args.log_level, log_dir, "mechavax_monitor")

    health_monitor = HealthMonitor(
        args.server_url, "mechavax", ["Cashflow Cartel Guild"]
    ).run(daemon=True)

    encrypt_password = ""

    if not args.dry_run:
        encrypt_password = os.getenv("NFT_PWD")
        if not encrypt_password:
            encrypt_password = getpass.getpass(
                prompt="Enter decryption password: "
            )

    private_key = decrypt_secret(encrypt_password, GUILD_WALLET_PRIVATE_KEY)

    monitor = MechBot(
        args.address,
        private_key,
        GUILD_WALLET_MAPPING,
        "MECHAVAX_BOT",
        "MECHAVAX_MINT",
    )
    monitor.run()


if __name__ == "__main__":
    run_bot()
