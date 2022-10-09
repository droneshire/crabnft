import argparse
import getpass
import logging
import os
import time
import traceback
from twilio.rest import Client
from yaspin import yaspin

from config_wyndblast import GMAIL, USERS, USER_GROUPS
from utils import discord
from utils import logger
from utils.email import Email, get_email_accounts_from_password
from utils.security import decrypt_secret
from wyndblast.daily_activities import DailyActivitiesGame
from wyndblast.wynd_bot import WyndBot
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client

TIME_BETWEEN_PLAYERS = 60.0
TIME_BETWEEN_RUNS = 3.0 * 60.0 * 60.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    log_dir = logger.get_logging_dir("wyndblast")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--quiet", action="store_true", help="Disable alerts")
    parser.add_argument("--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO")
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument("--groups", nargs="+", default=USER_GROUPS)
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

    setup_log(args.log_level, args.log_dir, "daily")

    encrypt_password = ""
    email_accounts = []

    if not args.dry_run:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")
        email_accounts = get_email_accounts_from_password(encrypt_password, GMAIL)

    bots = []
    for user, config in USERS.items():
        private_key = decrypt_secret(encrypt_password, config["private_key"])
        config["private_key"] = private_key

        bot = WyndBot(
            user,
            config,
            email_accounts,
            encrypt_password,
            args.log_dir,
            dry_run=args.dry_run,
        )
        bot.init()
        bots.append(bot)

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
