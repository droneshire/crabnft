import argparse
import getpass
import logging
import os
import time
import traceback
from twilio.rest import Client
from yaspin import yaspin

from config_admin import GMAIL, TWILIO_CONFIG
from config_pumpskin import USERS, USER_GROUPS
from utils import discord
from utils import logger
from utils.email import Email, get_email_accounts_from_password
from utils.security import decrypt_secret
from pumpskin.pumpskin_bot import PumpskinBot

TIME_BETWEEN_PLAYERS = 10.0
TIME_BETWEEN_RUNS = 60.0
TOTALS_UPDATE_TIME = 60.0 * 60.0 * 12


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    log_dir = logger.get_logging_dir("pumpskin")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--update-config", action="store_true", help="Update config from source")
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


@yaspin(text="Waiting...")
def wait(wait_time) -> None:
    time.sleep(wait_time)


def run_bot() -> None:
    args = parse_args()

    setup_log(args.log_level, args.log_dir, "the_den")

    encrypt_password = ""
    email_accounts = []

    alerts_enabled = not args.quiet and not args.dry_run

    if not args.dry_run:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")
        email_accounts = get_email_accounts_from_password(encrypt_password, GMAIL)

    bots = []
    for user, config in USERS.items():
        private_key = decrypt_secret(encrypt_password, config["private_key"])
        config["private_key"] = private_key

        bot = PumpskinBot(
            user,
            config,
            email_accounts,
            encrypt_password,
            args.log_dir,
            dry_run=args.dry_run,
            update_config=args.update_config,
        )
        bot.init()
        bots.append(bot)

    last_totals_update = 0.0

    try:
        while True:
            for bot in bots:
                bot.run()
                logger.print_normal(f"Waiting before next user...")
                wait(TIME_BETWEEN_PLAYERS)
            logger.print_normal(f"Waiting for next round of botting...")
            wait(TIME_BETWEEN_RUNS)

            now = time.time()
            if now - last_totals_update > TOTALS_UPDATE_TIME:
                last_totals_update = now
                total_levels = 0
                total_ppie = 0.0
                total_potn = 0.0
                total_gas = 0.0
                total_pumps = 0
                total_avax_profits = 0.0
                total_lp_potn = 0.0
                total_lp_ppie = 0.0
                for bot in bots:
                    total_levels += bot.stats_logger.lifetime_stats["levels"]
                    total_ppie += bot.stats_logger.lifetime_stats["ppie"]
                    total_potn += bot.stats_logger.lifetime_stats["potn"]
                    total_gas += bot.stats_logger.lifetime_stats["avax_gas"]
                    total_avax_profits += bot.stats_logger.lifetime_stats["avax_profits"]
                    total_lp_potn += bot.stats_logger.lifetime_stats["potn_lp_tokens"]
                    total_lp_ppie += bot.stats_logger.lifetime_stats["ppie_lp_tokens"]
                    total_pumps += len(bot.get_pumpskin_ids())

                message = "\U0001F383\U0001F383 **Totals** \U0001F383\U0001F383\n"
                message += f"**Total Users:** `{len(bots)}`\n"
                message += f"**Total Pumpskins:** `{total_pumps}`\n"
                message += f"**Total Levels Upgraded:** `{total_levels}`\n"
                message += f"**Total $PPIE Claimed:** `{total_ppie:.2f}`\n"
                message += f"**Total $POTN Claimed:** `{total_potn:.2f}`\n"
                message += f"**Total AVAX Profits Swapped:** `{total_avax_profits:.3f}`\n"
                message += f"**Total $POTN LP Purchased:** `{total_lp_potn:.2f}`\n"
                message += f"**Total $PPIE LP Purchased:** `{total_lp_ppie:.2f}`\n"
                message += f"**Total Gas Spent:** `{total_gas:.2f}`\n"
                logger.print_bold(f"{message}")
                discord.get_discord_hook("PUMPSKIN_ACTIVITY").send(message)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        stop_message = f"Pumpskin Alert \U0001F383\n\n"
        stop_message += f"Pumpskin Bot Stopped \U0000203C\n"
        if alerts_enabled and TWILIO_CONFIG["enable_admin_sms"]:
            sms_client = Client(TWILIO_CONFIG["account_sid"], TWILIO_CONFIG["account_auth_token"])
            message = sms_client.messages.create(
                body=stop_message,
                from_=TWILIO_CONFIG["from_sms_number"],
                to=TWILIO_CONFIG["admin_sms_number"],
            )
        if alerts_enabled:
            stop_message += "Please manually attend your pumpskins until we're back up"
            try:
                discord.get_discord_hook("PUMPSKIN_UPDATES").send(stop_message)
            except:
                pass
        logger.print_fail(traceback.format_exc())
    finally:
        for bot in bots:
            bot.end()


if __name__ == "__main__":
    run_bot()
