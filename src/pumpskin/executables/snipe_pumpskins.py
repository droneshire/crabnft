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
from config_pumpskin import USERS, USER_GROUPS
from utils import discord
from utils import logger
from utils.email import Email, get_email_accounts_from_password
from utils.security import decrypt_secret
from pumpskin.pumpskin_bot import PumpskinBot, ATTRIBUTES_FILE
from pumpskin.pumpskin_web3_client import (
    PumpskinNftWeb3Client,
    PumpskinCollectionWeb3Client,
    PumpskinContractWeb3Client,
)
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    log_dir = logger.get_logging_dir("pumpskin")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--quiet", action="store_true", help="Disable alerts")
    parser.add_argument("--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO")
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument(
        "--rarity-threshold", type=float, default=15.0, help="Rarity percent max threshold"
    )
    return parser.parse_args()


@yaspin(text="Waiting...")
def wait(wait_time) -> None:
    time.sleep(wait_time)


def setup_log(log_level: str, log_dir: str, id_string: str) -> None:
    if log_level == "NONE":
        return

    log_name = (
        time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime(time.time()))
        + f"_pumpskin_{id_string}.log"
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


def snipe() -> None:
    args = parse_args()

    setup_log(args.log_level, args.log_dir, "the_den")

    sorted_rarity = PumpskinBot.calculate_rarity_for_collection()

    sorted_rarity_unminted = {}

    w3: PumpskinNftWeb3Client = (
        PumpskinNftWeb3Client()
        .set_credentials(ADMIN_ADDRESS, "")
        .set_node_uri(AvalancheCWeb3Client.NODE_URL)
        .set_dry_run(False)
    )
    minted = w3.get_total_pumpskins_minted()

    for pumpkin_id, rarities in sorted_rarity.items():
        if pumpkin_id < minted:
            continue

        try:
            rarity_percent = rarities["Overall"]["rarity"] * 100.0
        except:
            logger.print_warn(f"{pumpkin_id}")
            logger.print_normal(f"{json.dumps(rarities, indent=4)}")
            continue

        if rarity_percent > args.rarity_threshold:
            continue

        sorted_rarity_unminted[pumpkin_id] = rarity_percent

    logger.print_normal(f"{json.dumps(sorted_rarity_unminted, indent=4)}")
    logger.print_ok_blue(f"Found {len(sorted_rarity_unminted.keys())} snipe targets")

    target_inx = 0
    last_minted = 0
    mint_targets = sorted(sorted_rarity_unminted.keys(), key=lambda y: int(y))
    target_id = mint_targets[target_inx]

    try:
        while True:
            minted = w3.get_total_pumpskins_minted()

            if minted > target_id:
                target_inx += 1
                target_id = mint_targets[target_inx]

            rarity = sorted_rarity_unminted[target_id]

            if last_minted != minted:
                logger.print_ok_arrow(f"Mint status: {minted} minted")
                rank = list(sorted_rarity_unminted.keys()).index(target_id)
                logger.print_bold(f"Next target: {target_id}, rarity {rarity:.2f}% rank: {rank}")
                last_minted = minted

            if minted + 10 > target_id and str(target_id) in sorted_rarity_unminted:
                logger.print_ok(
                    f"Get ready to mint rare Pumpskin {target_id}, rarity {rarity:.2f}%"
                )

            wait(1.0)
    except KeyboardInterrupt:
        answer = getpass.getpass(prompt="Purchase mint: ")
        if answer in ["Y", "y", "yes", "YES"]:
            answer = getpass.getpass(prompt="Purchase mint: ")
    except Exception as e:
        stop_message = f"Pumpskin Alert \U0001F383\n\n"
        stop_message += f"Pumpskin Sniper Bot Stopped \U0000203C\n"
        if args.quiet and TWILIO_CONFIG["enable_admin_sms"]:
            sms_client = Client(TWILIO_CONFIG["account_sid"], TWILIO_CONFIG["account_auth_token"])
            message = sms_client.messages.create(
                body=stop_message,
                from_=TWILIO_CONFIG["from_sms_number"],
                to=TWILIO_CONFIG["admin_sms_number"],
            )
        logger.print_fail(traceback.format_exc())


if __name__ == "__main__":
    snipe()
