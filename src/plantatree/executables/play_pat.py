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

from config_admin import ADMIN_ADDRESS, GMAIL, IEX_API_TOKEN, TWILIO_CONFIG
from config_pat import USERS
from plantatree.pat_bot import PatBot
from utils import discord
from utils import logger
from utils.email import Email, get_email_accounts_from_password
from utils.math import Average
from utils.price import get_avax_price_usd
from utils.security import decrypt_secret

TIME_BETWEEN_PLAYERS = 5.0
TIME_BETWEEN_RUNS = 60.0 * 10.0


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
        encrypt_password = os.getenv("NFT_PWD")
        if not encrypt_password:
            encrypt_password = getpass.getpass(prompt="Enter decryption password: ")
        email_accounts = get_email_accounts_from_password(encrypt_password, GMAIL)

    bots = []
    referral_address = ADMIN_ADDRESS
    for user, config in USERS.items():
        address = config["address"]
        private_key = decrypt_secret(encrypt_password, config["private_key"])
        config["private_key"] = private_key
        bots.append(
            PatBot(
                user,
                config,
                email_accounts,
                encrypt_password,
                referral_address,
                args.log_dir,
                args.dry_run,
            )
        )

    alerts_enabled = not args.quiet and not args.dry_run

    avg_gas_gwei: Average = Average()
    avg_gas_used: Average = Average()

    try:
        while True:
            avax_usd = get_avax_price_usd(IEX_API_TOKEN, args.dry_run)
            avax_usd_value = avax_usd if avax_usd is not None else 0.0
            gas_gwei = avg_gas_gwei.get_avg()
            gas_gwei_value = gas_gwei if gas_gwei else 0
            logger.print_bold(f"AVAX: ${avax_usd_value:.3f}, Gas: {gas_gwei_value}")

            for bot in bots:
                bot.run(avax_usd)
                logger.print_normal(f"Waiting before next user...")
                avg_gas_gwei.update(bot.avg_gas_gwei.get_avg())
                avg_gas_used.update(bot.avg_gas_used.get_avg())
                wait(TIME_BETWEEN_PLAYERS)
            logger.print_normal(f"Waiting for next round of botting...")
            wait(TIME_BETWEEN_RUNS)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        stop_message = f"PAT Alert \U0001F332\n\n"
        stop_message += f"PAT Bot Stopped \U0000203C\n"
        if alerts_enabled and TWILIO_CONFIG["enable_admin_sms"]:
            sms_client = Client(TWILIO_CONFIG["account_sid"], TWILIO_CONFIG["account_auth_token"])
            message = sms_client.messages.create(
                body=stop_message,
                from_=TWILIO_CONFIG["from_sms_number"],
                to=TWILIO_CONFIG["admin_sms_number"],
            )
        if alerts_enabled:
            stop_message += "Please manually attend your trees until we're back up"
            try:
                discord.get_discord_hook("PAT_UPDATES").send(stop_message)
            except:
                pass
        logger.print_fail(traceback.format_exc())
    finally:
        for bot in bots:
            bot.end()


if __name__ == "__main__":
    harvester()
