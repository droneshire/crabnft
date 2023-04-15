import argparse
import getpass
import json
import logging
import os
import time
import traceback

from twilio.rest import Client
from yaspin import yaspin

from config_admin import GMAIL, TWILIO_CONFIG, USER_CONFIGS_DB, STATS_DB
from config_wyndblast import USERS, USER_GROUPS
from database.account import AccountDb
from database.connect import init_database
from database.models.account import Account
from health_monitor.health_monitor import HealthMonitor
from utils import discord, file_util, logger
from utils.email import Email, get_email_accounts_from_password
from utils.security import decrypt_secret
from wyndblast import types
from wyndblast.cache import get_cache_info
from wyndblast.daily_activities import DailyActivitiesGame
from wyndblast.database.models.user import WyndblastUser
from wyndblast.wynd_bot import WyndBot

TIME_BETWEEN_PLAYERS = 5.0
TIME_BETWEEN_RUNS = 5.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    log_dir = logger.get_logging_dir("")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--human-mode", action="store_true", help="Human mode")
    parser.add_argument(
        "--ignore-utc", action="store_true", help="Ignore the utc time hold"
    )
    parser.add_argument("--quiet", action="store_true", help="Disable alerts")
    parser.add_argument(
        "--log-level",
        choices=["INFO", "DEBUG", "ERROR", "NONE"],
        default="INFO",
    )
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument("--groups", nargs="+", default=USER_GROUPS)
    parser.add_argument("--server-url", default="http://localhost:8080/monitor")
    parser.add_argument(
        "--clean-non-group-user-stats",
        action="store_true",
        help="delete config files that aren't a part of this group. used when running on multiple machines",
    )
    return parser.parse_args()


@yaspin(text="Waiting...")
def wait(wait_time) -> None:
    time.sleep(wait_time)


def run_bot() -> None:
    args = parse_args()

    log_dir = os.path.join(args.log_dir, "wyndblast")
    logger.setup_log(
        args.log_level,
        log_dir,
        f"wynd_{'_'.join([str(i) for i in args.groups])}",
    )

    encrypt_password = ""
    email_accounts = []

    if not args.dry_run:
        encrypt_password = os.getenv("NFT_PWD")
        if not encrypt_password:
            encrypt_password = getpass.getpass(
                prompt="Enter decryption password: "
            )
        email_accounts = get_email_accounts_from_password(
            encrypt_password, GMAIL
        )

    stages_info, account_info, _, _, _ = get_cache_info(log_dir)

    init_database(log_dir, STATS_DB, WyndblastUser)

    db_dir = os.path.join(args.log_dir, "p2e")
    init_database(db_dir, USER_CONFIGS_DB, Account)

    users_db = AccountDb.get_configs_for_game("wyndblast")

    bots = []
    for user, config in USERS.items():
        if config["group"] not in [int(i) for i in args.groups]:
            logger.print_warn(f"Skipping {user} in group {config['group']}...")
            if args.clean_non_group_user_stats:
                clean_up_stats_for_user(log_dir, user)
            continue

        private_key = decrypt_secret(encrypt_password, config["private_key"])
        config["private_key"] = private_key

        bot = WyndBot(
            user,
            config,
            email_accounts,
            encrypt_password,
            log_dir,
            stages_info,
            account_info,
            human_mode=args.human_mode,
            dry_run=args.dry_run,
            ignore_utc_time=args.ignore_utc,
        )
        bot.init()
        bots.append(bot)

    alerts_enabled = not args.quiet and not args.dry_run

    usernames = [b.user for b in bots]
    health_monitor = HealthMonitor(args.server_url, "wyndblast", usernames).run(
        daemon=True
    )

    try:
        while True:
            for bot in bots:
                bot.run()
                logger.print_normal(f"Waiting before next user...")
                wait(TIME_BETWEEN_PLAYERS)
            logger.print_normal(f"Waiting for next round of botting...")
            wait(TIME_BETWEEN_RUNS)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        stop_message = f"Wyndblast Alert \U0001F432\n\n"
        stop_message += f"Wyndblast Bot Stopped \U0000203C\n"
        logger.print_fail(stop_message)
        logger.print_fail(traceback.format_exc())
    finally:
        for bot in bots:
            bot.end()


if __name__ == "__main__":
    run_bot()
