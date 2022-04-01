"""
Collect TUS commission from specified bot users
"""
import argparse
import getpass
import json
import logging
import os
import time
import typing as T
from eth_typing import Address
from twilio.rest import Client

from config import TWILIO_CONFIG, USERS
from utils import discord, logger
from utils.game_stats import GameStats, get_game_stats, write_game_stats
from utils.price import Tus
from utils.security import decrypt
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.tus_web3_client import TusWeb3Client

MINIMUM_TUS_TO_TRANSFER = 25
DISCORD_TRANSFER_NOTICE = """\U0000203C  **COURTESY NOTICE**  \U0000203C
Collecting Crabada commission in 30 mins. Please ensure TUS are in wallet.
Confirmation will be sent after successful tx.
snib snib \U0001F980\n"""


def send_sms_message(to_number: str, message: str) -> None:
    sms_client = Client(TWILIO_CONFIG["account_sid"], TWILIO_CONFIG["account_auth_token"])

    message = sms_client.messages.create(
        body=message,
        from_=TWILIO_CONFIG["from_sms_number"],
        to=to_number,
    )


def setup_log(log_level: str, log_dir: str) -> None:
    if log_level == "NONE":
        return

    log_name = (
        time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime(time.time())) + "_tus_transactions.log"
    )
    log_file = os.path.join(log_dir, log_name)
    logging.basicConfig(
        filename=log_file,
        level=logging.getLevelName(log_level),
        format="[%(levelname)s][%(asctime)s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filemode="w",
    )


def send_collection_notice(
    from_users: T.List[str], log_dir: str, encrypt_password: str = "", dry_run: bool = False
) -> None:
    run_all_users = "ALL" in from_users
    for user, config in USERS.items():
        if not run_all_users and user not in from_users:
            continue

        game_stats = get_game_stats(user, log_dir)

        commission_tus = 0.0
        for address, commission in game_stats["commission_tus"].items():
            commission_tus += commission

        private_key = (
            ""
            if not encrypt_password
            else decrypt(str.encode(encrypt_password), config["private_key"]).decode()
        )

        tus_w3 = T.cast(
            TusWeb3Client,
            (
                TusWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(AvalancheCWeb3Client.AVAX_NODE_URL)
                .set_dry_run(dry_run)
            ),
        )

        available_tus = float(tus_w3.get_balance())
        logger.print_ok(f"{user} balance: {available_tus} TUS, commission: {commission_tus} TUS")

        if commission_tus < MINIMUM_TUS_TO_TRANSFER:
            logger.print_warn(f"Skipping transfer of {commission_tus:.2f} from {user} (too small)")
            continue

        if commission_tus > available_tus:
            logger.print_fail(
                f"Skipping transfer of {commission_tus:.2f} from {user}: insufficient funds!"
            )
            continue

        sms_message = f"\U0000203C  COURTESY NOTICE  \U0000203C\n"
        sms_message += f"Hey {user}!\nCollecting Crabada commission in 30 mins.\n"
        sms_message += f"Please ensure {commission_tus:.2f} TUS are in wallet.\n"
        sms_message += f"Confirmation will be sent after successful tx\n"
        sms_message += f"snib snib \U0001F980\n"
        logger.print_ok_blue(sms_message)
        if not dry_run:
            send_sms_message(config["sms_number"], sms_message)

    if not dry_run:
        discord.get_discord_hook("WHALES").send(DISCORD_TRANSFER_NOTICE)


def collect_tus_commission(
    to_user: str,
    from_users: T.List[str],
    log_dir: str,
    encrypt_password: str = "",
    dry_run: bool = False,
) -> None:
    total_stats = {"total_commission_tus": {}}

    run_all_users = "ALL" in from_users
    for user, config in USERS.items():
        if not run_all_users and user not in from_users:
            continue

        if user == to_user:
            continue

        private_key = (
            ""
            if not encrypt_password
            else decrypt(str.encode(encrypt_password), config["private_key"]).decode()
        )

        game_stats = get_game_stats(user, log_dir)

        from_address = config["address"]

        tus_w3 = T.cast(
            TusWeb3Client,
            (
                TusWeb3Client()
                .set_credentials(from_address, private_key)
                .set_node_uri(AvalancheCWeb3Client.AVAX_NODE_URL)
                .set_dry_run(dry_run)
            ),
        )

        commission_tus = 0.0
        for _, commission in game_stats["commission_tus"].items():
            commission_tus += commission
        available_tus = float(tus_w3.get_balance())
        logger.print_ok(
            f"{from_address} balance: {available_tus} TUS, commission: {commission_tus} TUS"
        )

        if commission_tus < MINIMUM_TUS_TO_TRANSFER:
            logger.print_warn(f"Skipping transfer of {commission_tus:.2f} from {user} (too small)")
            continue

        if commission_tus > available_tus:
            logger.print_fail(
                f"Skipping transfer of {commission_tus:.2f} from {user}: insufficient funds!"
            )
            continue

        did_fail = False
        for to_address, commission in game_stats["commission_tus"].items():
            logger.print_bold(
                f"Attempting to send commission of {commission_tus:.2f} TUS from {user} -> {to_address}..."
            )
            tx_hash = tus_w3.transfer_tus(to_address, commission_tus)
            tx_receipt = tus_w3.get_transaction_receipt(tx_hash)

            if tx_receipt["status"] != 1:
                logger.print_fail_arrow(
                    f"Error in tx {commission:.2f} TUS from {from_address}->{to_address}"
                )
                did_fail = True
            else:
                logger.print_ok_arrow(
                    f"Successfully tx {commission:.2f} TUS from {from_address}->{to_address}"
                )
                total_stats["total_commission_tus"][to_address] = (
                    total_stats["total_commission_tus"].get(to_address, 0.0) + commission
                )
                game_stats["commission_tus"][to_address] -= commission
                if not dry_run:
                    write_game_stats(user, log_dir, game_stats)
                logger.print_normal(
                    f"New TUS commission balance: {game_stats['commission_tus']} TUS"
                )

        if not did_fail:
            new_commission = sum([c for _, c in game_stats["commission_tus"].items()])
            sms_message = f"\U0001F980  Commission Collection: \U0001F980\n"
            sms_message += f"Successful tx of {commission_tus:.2f} TUS from {user}\n"
            sms_message += f"Explorer: https://snowtrace.io/address/{from_address}\n\n"
            sms_message += f"New TUS commission balance: {new_commission} TUS\n"
            logger.print_ok_blue(sms_message)
            if not dry_run:
                send_sms_message(config["sms_number"], sms_message)

    logger.print_bold(
        f"Collected {sum([c for _, c in total_stats['total_commission_tus'].items()])} TUS in commission!!!"
    )

    if dry_run:
        return

    stats_file = os.path.join(logger.get_logging_dir(), "commission_lifetime_bot_stats.json")

    if os.path.isfile(stats_file):
        with open(stats_file, "r") as infile:
            old_stats = json.load(infile)
        for address, commission in old_stats["total_commission_tus"].items():
            total_stats["total_commission_tus"][address] += commission
    with open(stats_file, "w") as outfile:
        json.dump(
            total_stats,
            outfile,
            indent=4,
            sort_keys=True,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--send-notice", action="store_true", help="Send out warning SMS that we're collecting!"
    )
    parser.add_argument("--to-user", choices=USERS.keys(), required=True)
    parser.add_argument(
        "--from-users", choices=list(USERS.keys()) + ["ALL"], default="ALL", nargs="+"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-dir", default=logger.get_logging_dir())
    parser.add_argument("--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    setup_log(args.log_level, args.log_dir)

    if isinstance(args.from_users, str):
        from_users = [args.from_users]
    else:
        from_users = args.from_users

    if args.dry_run:
        logger.print_warn(f"DRY RUN ACTIVATED")

    if not args.dry_run:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")
    else:
        encrypt_password = ""

    if args.send_notice:
        logger.print_bold(f"Sending SMS notice that we're collecting in 60 mins!")
        send_collection_notice(from_users, args.log_dir, encrypt_password, args.dry_run)
        return

    logger.print_ok(f"Collecting TUS Commissions from {', '.join(from_users)}")

    collect_tus_commission(
        args.to_user, args.from_users, args.log_dir, encrypt_password, args.dry_run
    )


if __name__ == "__main__":
    main()
