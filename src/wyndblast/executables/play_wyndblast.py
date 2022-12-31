import argparse
import getpass
import json
import logging
import os
import time
import traceback
from twilio.rest import Client
from yaspin import yaspin

from config_admin import GMAIL, TWILIO_CONFIG
from config_wyndblast import USERS, USER_GROUPS
from health_monitor.health_monitor import HealthMonitor
from utils import discord
from utils import logger
from utils.email import Email, get_email_accounts_from_password
from utils.security import decrypt_secret
from wyndblast import types
from wyndblast.daily_activities import DailyActivitiesGame
from wyndblast.pve_google_storage_web2_client import PveGoogleStorageWeb2Client
from wyndblast.wynd_bot import WyndBot
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client

TIME_BETWEEN_PLAYERS = 5.0
TIME_BETWEEN_RUNS = 60.0 * 5.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    log_dir = logger.get_logging_dir("wyndblast")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--human-mode", action="store_true", help="Human mode")
    parser.add_argument("--ignore-utc", action="store_true", help="Ignore the utc time hold")
    parser.add_argument("--quiet", action="store_true", help="Disable alerts")
    parser.add_argument("--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO")
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument("--groups", nargs="+", default=USER_GROUPS)
    parser.add_argument("--server-url", default="http://localhost:8080/monitor")
    parser.add_argument(
        "--clean-non-group-user-stats",
        action="store_true",
        help="delete config files that aren't a part of this group. used when running on multiple machines",
    )
    return parser.parse_args()


def setup_log(log_level: str, log_dir: str, id_string: str) -> None:
    if log_level == "NONE":
        return

    log_name = (
        time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime(time.time()))
        + f"_wyndblast_{id_string}.log"
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


@yaspin(text="Waiting...")
def wait(wait_time) -> None:
    time.sleep(wait_time)


def run_bot() -> None:
    args = parse_args()

    setup_log(args.log_level, args.log_dir, f"wynd_{'_'.join([str(i) for i in args.groups])}")

    encrypt_password = ""
    email_accounts = []

    if not args.dry_run:
        encrypt_password = os.getenv("NFT_PWD")
        if not encrypt_password:
            encrypt_password = getpass.getpass(prompt="Enter decryption password: ")
        email_accounts = get_email_accounts_from_password(encrypt_password, GMAIL)

    google_w2: PveGoogleStorageWeb2Client = PveGoogleStorageWeb2Client(
        "",
        "",
        WyndblastWeb2Client.GOOGLE_STORAGE_URL,
        dry_run=False,
    )

    stages_info_file = os.path.join(args.log_dir, "stages_info.json")
    if os.path.isfile(stages_info_file):
        with open(stages_info_file) as infile:
            stages_info: T.List[types.LevelsInformation] = json.load(infile)["data"]
    else:
        logger.print_normal("Caching stages info...")
        stages_info: T.List[types.LevelsInformation] = google_w2.get_level_data()
        with open(stages_info_file, "w") as outfile:
            data = {"data": stages_info}
            json.dump(data, outfile, indent=4)

    account_info_file = os.path.join(args.log_dir, "account_info.json")
    if os.path.isfile(account_info_file):
        with open(account_info_file) as infile:
            account_info: T.List[types.AccountLevels] = json.load(infile)["data"]
    else:
        logger.print_normal("Caching account info...")
        account_info: T.List[types.AccountLevels] = google_w2.get_account_stats()
        with open(account_info_file, "w") as outfile:
            data = {"data": account_info}
            json.dump(data, outfile, indent=4)

    bots = []
    for user, config in USERS.items():
        if config["group"] not in [int(i) for i in args.groups]:
            logger.print_warn(f"Skipping {user} in group {config['group']}...")
            if args.clean_non_group_user_stats:
                clean_up_stats_for_user(args.log_dir, user)
            continue

        private_key = decrypt_secret(encrypt_password, config["private_key"])
        config["private_key"] = private_key

        bot = WyndBot(
            user,
            config,
            email_accounts,
            encrypt_password,
            args.log_dir,
            stages_info,
            account_info,
            human_mode=args.human_mode,
            dry_run=args.dry_run,
            ignore_utc_time=args.ignore_utc,
        )
        bot.init()
        bots.append(bot)

    alerts_enabled = not args.quiet and not args.dry_run

    health_monitor = HealthMonitor(args.server_url, "wyndblast", USERS).run(daemon=True)

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
        if alerts_enabled and TWILIO_CONFIG["enable_admin_sms"]:
            sms_client = Client(TWILIO_CONFIG["account_sid"], TWILIO_CONFIG["account_auth_token"])
            message = sms_client.messages.create(
                body=stop_message,
                from_=TWILIO_CONFIG["from_sms_number"],
                to=TWILIO_CONFIG["admin_sms_number"],
            )
        if alerts_enabled:
            stop_message += "Please manually attend your wynds until we're back up"
            try:
                discord.get_discord_hook("WYNDBLAST_UPDATES").send(stop_message)
            except:
                pass
        logger.print_fail(traceback.format_exc())
    finally:
        for bot in bots:
            bot.end()


if __name__ == "__main__":
    run_bot()
