import argparse
import datetime
import getpass


from config_crabada import GMAIL, USERS
from utils import logger
from utils import email
from utils.csv_logger import CsvLogger
from crabada.game_stats import get_daily_stats_message, get_lifetime_stats_file, NULL_STATS
from utils.security import decrypt
from utils.user import get_alias_from_user


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", choices=list(USERS.keys()) + ["ALL"], default="ALL")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--target-date",
        help="date format %m/%d/%Y",
        default=datetime.date.today().strftime("%m/%d/%Y"),
    )
    return parser.parse_args()


def calc_profits() -> None:
    args = parse_args()

    if args.user == "ALL":
        users = list(USERS.keys())
    else:
        users = [args.user]

    if args.dry_run:
        encrypt_password = ""
    else:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")

    aliases = set([get_alias_from_user(u) for u in USERS])

    for user in users:
        alias = get_alias_from_user(user)
        logger.print_ok_blue(f"Daily Stats for {alias.upper()}:")

        alias = get_alias_from_user(user)

        if alias not in aliases:
            continue

        csv_header = ["timestamp"] + [k for k in NULL_STATS.keys()] + ["team_id"]
        csv_file = (
            get_lifetime_stats_file(alias, logger.get_logging_dir("crabada")).split(".")[0] + ".csv"
        )
        csv = CsvLogger(csv_file, csv_header, dry_run=args.dry_run)

        target_date = datetime.datetime.strptime(args.target_date, "%m/%d/%Y").date()
        message = get_daily_stats_message(alias, csv, target_date)

        logger.print_normal(f"{message}")

        if args.dry_run:
            continue

        config = USERS[user]

        if not config["email"] or not config["get_email_updates"]:
            continue

        date_pretty = target_date.strftime("%m/%d/%Y")
        subject = f"\U0001F4C8 Crabada Daily Bot Stats for {date_pretty}"

        email_accounts = []
        for email_account in GMAIL:
            email_password = decrypt(
                str.encode(encrypt_password), email_account["password"]
            ).decode()
            email_accounts.append(
                email.Email(address=email_account["user"], password=email_password)
            )
        try:
            email.send_email(email_accounts, config["email"], subject, message)
            aliases.remove(alias)
        except:
            logger.print_warn(f"Failed to send message to {config['email']}")


if __name__ == "__main__":
    calc_profits()
