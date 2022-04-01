"""
Starts bots for interacting with the Crabada Dapp P2E game
"""
import argparse
import getpass
import json
import logging
import os
import requests
import sys
import time
import traceback
from twilio.rest import Client

from config import COINMARKETCAP_API_TOKEN, GMAIL, IEX_API_TOKEN, TWILIO_CONFIG, USERS
from crabada.bot import CrabadaMineBot
from utils import discord, email, logger, security
from utils.game_stats import GameStats
from utils.price import get_avax_price_usd, get_token_price_usd

PRICE_UPDATE_TIME = 30.0
DISCORD_UPDATE_TIME = 60.0 * 60.0 * 6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    log_dir = logger.get_logging_dir()
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--quiet", action="store_true", help="Disable alerts")
    parser.add_argument("--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO")
    parser.add_argument("--log-dir", default=log_dir)
    return parser.parse_args()


def setup_log(log_level: str, log_dir: str) -> None:
    if log_level == "NONE":
        return

    log_name = time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime(time.time())) + "_crabada.log"
    log_file = os.path.join(log_dir, log_name)
    logging.basicConfig(
        filename=log_file,
        level=logging.getLevelName(log_level),
        format="[%(levelname)s][%(asctime)s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filemode="w",
    )


def run_bot() -> None:
    args = parse_args()

    setup_log(args.log_level, args.log_dir)

    sms_client = Client(TWILIO_CONFIG["account_sid"], TWILIO_CONFIG["account_auth_token"])

    webhooks = {
        "WHALES": discord.get_discord_hook("WHALES"),
        "CARTEL": discord.get_discord_hook("CARTEL"),
    }

    encrypt_password = ""
    email_password = ""
    if not args.dry_run:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")
        email_password = security.decrypt(str.encode(encrypt_password), GMAIL["password"]).decode()

    email_account = email.Email(address=GMAIL["user"], password=email_password)

    bots = []
    for user, config in USERS.items():
        private_key = (
            ""
            if not encrypt_password
            else security.decrypt(str.encode(encrypt_password), config["private_key"]).decode()
        )
        config["private_key"] = private_key

        bots.append(
            CrabadaMineBot(
                user,
                config,
                TWILIO_CONFIG["from_sms_number"],
                sms_client,
                email_account,
                args.log_dir,
                args.dry_run,
            )
        )

    game_stats = GameStats()
    for bot in bots:
        bot.update_prices(
            get_avax_price_usd(IEX_API_TOKEN),
            get_token_price_usd(COINMARKETCAP_API_TOKEN, "TUS"),
            get_token_price_usd(COINMARKETCAP_API_TOKEN, "CRA"),
        )

        logger.print_bold(f"Starting game bot for user {bot.user}...")
        bot_stats = bot.get_lifetime_stats()
        game_stats["commission_tus"] = (
            game_stats.get("commission_tus", 0.0) + bot_stats["commission_tus"]
        )
        game_stats["tus_gross"] = game_stats.get("tus_gross", 0.0) + bot_stats["tus_gross"]

    logger.print_bold(
        f"Mined TUS: {game_stats['tus_gross']}TUS Commission TUS: {game_stats['commission_tus']}TUS"
    )
    logger.print_normal("\n")

    last_avax_price_update = 0.0
    last_discord_update = time.time()

    alerts_enabled = not args.quiet and not args.dry_run
    reinforcement_backoff = 0
    try:
        while True:
            gross_tus = 0.0
            wins = 0
            losses = 0

            for bot in bots:
                bot.set_backoff(reinforcement_backoff)
                bot.run()
                reinforcement_backoff = bot.get_backoff()

                bot_stats = bot.get_lifetime_stats()
                gross_tus += bot_stats["tus_gross"]
                wins += bot_stats["game_wins"]
                losses += bot_stats["game_losses"]

                now = time.time()
                if now - last_avax_price_update > PRICE_UPDATE_TIME:
                    bot.update_prices(
                        get_avax_price_usd(IEX_API_TOKEN),
                        get_token_price_usd(COINMARKETCAP_API_TOKEN, "TUS"),
                        get_token_price_usd(COINMARKETCAP_API_TOKEN, "CRA"),
                    )
                    last_avax_price_update = now

            if alerts_enabled and time.time() - last_discord_update > DISCORD_UPDATE_TIME:
                last_discord_update = time.time()
                webhook_text = f"\U0001F980\t**Total TUS mined by bot: {int(gross_tus):,} TUS**\n"
                win_percentage = float(wins) / (wins + losses) * 100.0
                webhook_text += f"\U0001F916\t**Bot win percentage: {win_percentage:.2f}%**\n"
                for channel in webhook.keys():
                    webhook[channel].send(webhook_text)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        stop_message = f"\U0001F980 Crabada Bot Alert \U0001F980\n\n"
        stop_message += f"Crabada Bot Stopped \U0000203C\n"
        if alerts_enabled and TWILIO_CONFIG["enable_admin_sms"]:
            stop_message = f"\U0001F980 Crabada Bot Alert \U0001F980\n\n"
            stop_message += f"Crabada Bot Stopped \U0000203C\n"
            message = sms_client.messages.create(
                body=stop_message,
                from_=TWILIO_CONFIG["from_sms_number"],
                to=TWILIO_CONFIG["admin_sms_number"],
            )
        if alerts_enabled:
            stop_message += "Please manually attend your mines until we're back up"
            webhook["WHALES"].send(stop_message)
        logger.print_fail(traceback.format_exc())
    finally:
        for bot in bots:
            bot.end()


if __name__ == "__main__":
    run_bot()
