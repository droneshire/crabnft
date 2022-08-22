"""
Collect commission from specified bot users
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

from config_crabada import GAME_BOT_STRING, GMAIL, TWILIO_CONFIG, USERS
from utils import discord, email, logger
from utils.commissions import GameCollection, COMMISSION_GAMES
from utils.price import is_gas_too_high
from utils.price import Tus
from utils.security import decrypt
from utils.user import get_alias_from_user

MAX_COLLECTION_GAS_GWEI = 25000
DISCORD_TRANSFER_NOTICE = """\U0000203C  **COURTESY NOTICE**  \U0000203C
@here, collecting commission shortly. Please ensure tokens are in wallet.
Confirmation will be sent after successful tx.
\n"""
COMMISSION_SUBJECT = """{GAME_BOT_STRING}: Commission Collection"""


def send_sms_message(encrypt_password: str, to_email: str, to_number: str, message: str) -> None:
    sms_client = Client(TWILIO_CONFIG["account_sid"], TWILIO_CONFIG["account_auth_token"])

    try:
        if to_number:
            sms_client.messages.create(
                body=message,
                from_=TWILIO_CONFIG["from_sms_number"],
                to=to_number,
            )
    except:
        logger.print_warn(f"Failed to send sms message to {to_number}")

    try:
        email_accounts = []
        for email_account in GMAIL:
            email_password = decrypt(
                str.encode(encrypt_password), email_account["password"]
            ).decode()
            email_accounts.append(
                email.Email(address=email_account["user"], password=email_password)
            )
        if to_email:
            email.send_email(email_accounts, to_email, COMMISSION_SUBJECT, message)
    except:
        logger.print_warn(f"Failed to send email message to {to_email}")


def setup_log(log_level: str, log_dir: str) -> None:
    if log_level == "NONE":
        return

    log_name = (
        time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime(time.time())) + "_tus_transactions.log"
    )

    log_dir = os.path.join(log_dir, "collections")
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


def send_collection_notice(
    from_users: T.List[str],
    log_dir: str,
    game: GameCollection,
    encrypt_password: str = "",
    dry_run: bool = False,
) -> None:
    run_all_users = "ALL" in from_users

    aliases = set([get_alias_from_user(u) for u in USERS])

    total_tus = 0
    for user, config in USERS.items():
        if not run_all_users and user not in from_users:
            continue

        alias = get_alias_from_user(user)

        if alias not in aliases:
            logger.print_normal(f"Multi-wallet, skipping {user} b/c we already sent notice")
            continue

        token = game(user, config, log_dir, dry_run=dry_run)
        game_stats_commission = token.commission

        commission_token = 0.0
        for address, commission in game_stats_commission.items():
            commission_token += commission

        private_key = (
            ""
            if not encrypt_password
            else decrypt(str.encode(encrypt_password), config["private_key"]).decode()
        )

        token_w3 = token.client

        available_tus = float(token_w3.get_balance())
        logger.print_ok(
            f"{alias} balance: {available_tus} {token}, commission: {commission_token} {token}"
        )

        if commission_token < token.min_amount_to_transfer:
            logger.print_warn(
                f"Skipping transfer of {commission_token:.2f} from {alias} (too small)"
            )
            continue

        if commission_token > available_tus:
            logger.print_fail(f"WARNING: {commission_token:.2f} from {alias}: insufficient funds!")

        total_tus += commission_token
        message = f"\U0000203C  COURTESY NOTICE  \U0000203C\n"
        message += f"Hey {alias}!\nCollecting Crabada commission at next low gas period.\n"
        message += f"Please ensure {commission_token:.2f} {token} are in wallet.\n"
        message += f"Confirmation will be sent after successful tx\n"
        message += f"snib snib \U0001F980\n"
        logger.print_ok_blue(message)
        if not dry_run:
            send_sms_message(encrypt_password, config["email"], config["sms_number"], message)

        aliases.remove(alias)

    logger.print_bold(f"Projected to collect {total_tus:.2f} {token} in commission")

    if not dry_run and run_all_users:
        discord.get_discord_hook("CRABADA_HOLDERS").send(DISCORD_TRANSFER_NOTICE)


def collect_commission(
    to_user: str,
    from_users: T.List[str],
    log_dir: str,
    game: GameCollection,
    encrypt_password: str = "",
    dry_run: bool = False,
) -> None:
    totals_key = f"total_commission_{token.lower()}"
    total_stats = {totals_key: {}}

    run_all_users = "ALL" in from_users

    aliases = set([get_alias_from_user(u) for u in USERS])
    failed_to_collect = []

    for user, config in USERS.items():
        if not run_all_users and user not in from_users:
            continue

        if user == to_user:
            continue

        alias = get_alias_from_user(user)

        if alias not in aliases:
            logger.print_normal(f"Multi-wallet, skipping {user} b/c we already collected")
            continue

        private_key = (
            ""
            if not encrypt_password
            else decrypt(str.encode(encrypt_password), config["private_key"]).decode()
        )

        token = game(user, config, log_dir, dry_run=dry_run)
        game_stats_commission = token.commission

        from_address = config["address"]

        token_w3 = token.client

        commission_token = 0.0
        for _, commission in game_stats_commission.items():
            commission_token += commission
        available_tus = float(token_w3.get_balance())
        logger.print_ok(
            f"{from_address} balance: {available_tus} {token}, commission: {commission_token} {token}"
        )

        if commission_token < token.min_amount_to_transfer:
            logger.print_warn(
                f"Skipping transfer of {commission_token:.2f} from {alias} (too small)"
            )
            continue

        if commission_token > available_tus:
            logger.print_fail(
                f"Skipping transfer of {commission_token:.2f} from {alias}: insufficient funds!"
            )
            failed_to_collect.append(alias)
            continue

        if is_gas_too_high(
            gas_price_gwei=token_w3.get_gas_price(), max_price_gwei=MAX_COLLECTION_GAS_GWEI
        ):
            logger.print_fail_arrow(
                f"Skipping transfer of {commission_token:.2f} from {alias}: gas too high!!!"
            )
            continue

        did_fail = True
        tx_hashes = []
        for to_address, commission in game_stats_commission.items():
            logger.print_bold(
                f"Attempting to send commission of {commission_token:.2f} {token} from {alias} -> {to_address}..."
            )
            try:
                tx_hash = token_w3.transfer_tus(to_address, commission)
                tx_hashes.append(tx_hash)
            except:
                logger.print_fail(f"Failed to collect from {alias}")
                failed_to_collect.append(alias)
                continue

            for i in range(5):
                try:
                    tx_receipt = token_w3.get_transaction_receipt(tx_hash)
                    break
                except:
                    if i >= 4:
                        failed_to_collect.append(alias)
                        logger.print_fail(f"Failed to get tx receipt for hash: {tx_hash}")
                    else:
                        logger.print_warn(
                            f"Failed to get tx receipt for hash: {tx_hash}. Retrying..."
                        )
                        time.sleep(i * 1.0)

            if tx_receipt.get("status", 0) != 1:
                logger.print_fail_arrow(
                    f"Error in tx {commission:.2f} {token} from {from_address}->{to_address}"
                )
                failed_to_collect.append(alias)
            else:
                did_fail = False
                logger.print_ok_arrow(
                    f"Successfully tx {commission:.2f} {token} from {from_address}->{to_address}"
                )
                total_stats[totals_key][to_address] = (
                    total_stats[totals_key].get(to_address, 0.0) + commission
                )
                game_stats_commission[to_address] -= commission
                if not dry_run:
                    token.stats_logger.write_game_stats(game_stats)
                logger.print_normal(
                    f"New {token} commission balance: {game_stats_commission} {token}"
                )

        if not did_fail:
            new_commission = sum([c for _, c in game_stats_commission.items()])
            message = f"\U0000203C  Commission Collection: \U0000203C\n"
            message += f"Successful tx of {commission_token:.2f} {token} from {alias}\n"
            transactions = "\n\t".join([f"{token.explorer_url}/{t}" for t in tx_hashes])
            message += f"Explorer: {transactions}\n\n"
            message += f"New {token} commission balance: {new_commission} {token}\n"
            logger.print_ok_blue(message)
            if not dry_run:
                send_sms_message(encrypt_password, config["email"], config["sms_number"], message)

    logger.print_bold(
        f"Collected {sum([c for _, c in total_stats[totals_key].items()])} {token} in commission!!!"
    )
    logger.print_warn(f"Failed to collect from the following users: {', '.join(failed_to_collect)}")

    if dry_run:
        return

    stats_file = token.lifetime_stats_file

    if os.path.isfile(stats_file):
        with open(stats_file, "r") as infile:
            old_stats = json.load(infile)
        for address, commission in old_stats[totals_key].items():
            total_stats[totals_key][address] = (
                total_stats[totals_key].get(address, 0.0) + commission
            )
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
    parser.add_argument("--log-dir", default=logger.get_logging_dir("crabada"))
    parser.add_argument("--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO")
    parser.add_argument(
        "--game", choices=list(COMMISSION_GAMES.keys()), help="Token to collect commission with"
    )
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

    game_commission = COMMISSION_GAMES[args.game]

    if args.send_notice:
        logger.print_bold(f"Sending SMS notice that we're collecting when gas is low!")
        send_collection_notice(
            from_users, args.log_dir, game_commission, encrypt_password, args.dry_run
        )
        return

    logger.print_ok(f"Collecting {token} Commissions from {', '.join(from_users)}")

    collect_commission(
        args.to_user, args.from_users, args.log_dir, game_commission, encrypt_password, args.dry_run
    )


if __name__ == "__main__":
    main()
