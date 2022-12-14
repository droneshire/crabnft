import argparse
import datetime
import getpass
import os
import tempfile
import time

from config_admin import GMAIL
from config_pumpskin import USERS
from joepegs.joepegs_api import JOEPEGS_ICON_URL, JOEPEGS_URL
from pumpskin.pumpskin_bot import PumpskinBot
from pumpskin.utils import ATTRIBUTES_FILE, PUMPSKIN_ATTRIBUTES
from pumpskin.utils import (
    calc_potn_from_level,
    calculate_rarity_from_query,
    get_json_path,
    calc_ppie_per_day_from_level,
)
from utils import logger
from utils import email
from utils.csv_logger import CsvLogger
from utils.security import decrypt
from utils.user import get_alias_from_user


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", choices=list(USERS.keys()) + ["ALL"], default="ALL")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def create_patch_csv(csv_file: str, bot: PumpskinBot, dry_run: bool = False) -> None:
    logger.print_normal(f"Creating patch stats csv file: {csv_file}...")

    csv_header = ["Pumpskin ID"]
    csv_header.append(f"Level")
    csv_header.append(f"PPIE/Day")
    csv_header.append(f"Level Up Cost")
    for k in PUMPSKIN_ATTRIBUTES.keys():
        csv_header.append(f"{k} trait")
        csv_header.append(f"{k} rarity %")
    csv_header.append(f"Overall Rarity %")
    csv_header.append(f"JoePeg Link")
    csv_header.append(f"NFT Image URL")

    csv = CsvLogger(csv_file, csv_header, dry_run, verbose=False)

    pumpskins = bot.get_pumpskin_ids()

    for pumpskin in pumpskins:
        row = {}
        row["Pumpskin ID"] = pumpskin
        for _ in range(3):
            pumpskin_info: StakedPumpskin = bot.collection_w3.get_staked_pumpskin_info(pumpskin)
            if pumpskin_info:
                break
            time.sleep(3.0)
        row["NFT Image URL"] = bot.pumpskin_w2.get_pumpskin_image(pumpskin)
        level = int(pumpskin_info["kg"] / 100)
        row["Level"] = level
        row["PPIE/Day"] = calc_ppie_per_day_from_level(level)
        row["Level Up Cost"] = calc_potn_from_level(level)
        row["JoePeg Link"] = f"{JOEPEGS_URL}/{pumpskin}"
        pumpskin_rarity = calculate_rarity_from_query(pumpskin, get_json_path(ATTRIBUTES_FILE))

        if not pumpskin_rarity:
            continue

        overall_rarity = 0.0
        for trait, info in pumpskin_rarity.items():
            if trait == "Overall":
                row["Overall Rarity %"] = info["rarity"] * 100.0
                continue
            rarity_percent = info["rarity"] * 100.0
            row[f"{trait} rarity %"] = f"{rarity_percent:.2f}"
            row[f"{trait} trait"] = f"{info['trait']}"
        csv.write(row)


def send_patch_stats() -> None:
    args = parse_args()

    if args.user == "ALL":
        users = list(USERS.keys())
    else:
        users = [args.user]

    if args.dry_run:
        encrypt_password = ""
    else:
        encrypt_password = os.getenv("NFT_PWD")
        if not encrypt_password:
            encrypt_password = getpass.getpass(prompt="Enter decryption password: ")

    aliases = set([get_alias_from_user(u) for u in USERS])

    email_accounts = []
    for email_account in GMAIL:
        email_password = decrypt(str.encode(encrypt_password), email_account["password"]).decode()
        email_accounts.append(email.Email(address=email_account["user"], password=email_password))

    for user in users:
        alias = get_alias_from_user(user)
        logger.print_ok_blue(f"Patch Stats for {alias.upper()}:")

        alias = get_alias_from_user(user)

        if alias not in aliases:
            continue

        config = USERS[user]

        bot = PumpskinBot(
            user,
            config,
            email_accounts,
            encrypt_password,
            "",
            dry_run=args.dry_run,
            quiet=args.quiet,
            update_config=True,
        )

        with tempfile.NamedTemporaryFile(
            suffix=f"{user.lower()}_patch_stats.csv", delete=False
        ) as csv_file:
            create_patch_csv(csv_file.name, bot, dry_run=args.dry_run)

            message = f"Hi {user.upper()},\n"
            message += f"Congrats on your Pumpskin Patch!\n"
            message += f"See attached stats on your Pumpskin Patch!\n"
            message += f"Cheers - Cashflow\n"

            logger.print_normal(f"{message}")

            if args.dry_run:
                continue

            config = USERS[user]

            if not config["email"] or not config["get_email_updates"]:
                continue

            subject = f"\U0001F383 Pumpskin Patch Stats for {alias.upper()}"

            try:
                email.send_email(
                    email_accounts, config["email"], subject, message, attachments=csv_file.name
                )
                aliases.remove(alias)
            except:
                logger.print_warn(f"Failed to send message to {config['email']}")


if __name__ == "__main__":
    send_patch_stats()
