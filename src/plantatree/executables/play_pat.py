import argparse
import copy
import getpass
import json
import logging
import os
import time
import traceback
from twilio.rest import Client
from yaspin import yaspin

from config_admin import ADMIN_ADDRESS, GMAIL, TWILIO_CONFIG
from config_pat import USERS
from utils import discord
from utils import logger
from utils.email import Email, get_email_accounts_from_password
from utils.security import decrypt_secret
from plantatree.pat_web3_client import PlantATreeWeb3Client
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client

MINT_MARGIN = 100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    log_dir = logger.get_logging_dir("pat")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--quiet", action="store_true", help="Disable alerts")
    parser.add_argument("--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO")
    parser.add_argument("--log-dir", default=log_dir)

    return parser.parse_args()


@yaspin(text="Waiting...")
def wait(wait_time) -> None:
    time.sleep(wait_time)


def setup_log(log_level: str, log_dir: str, id_string: str) -> None:
    if log_level == "NONE":
        return

    log_name = (
        time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime(time.time())) + f"_pat_{id_string}.log"
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


def harvester() -> None:
    args = parse_args()

    setup_log(args.log_level, args.log_dir, "mining")

    encrypt_password = ""
    private_key = ""
    email_accounts = []

    if not args.dry_run:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")
        email_accounts = get_email_accounts_from_password(encrypt_password, GMAIL)

    for user, config in USERS.item():
        address = config["address"]
        private_key = decrypt_secret(encrypt_password, config["private_key"])


if __name__ == "__main__":
    snipe()
