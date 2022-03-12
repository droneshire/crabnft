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
from discord import Webhook, RequestsWebhookAdapter
from twilio.rest import Client

from config import IEX_API_TOKEN, TWILIO_CONFIG, USERS
from crabada.bot import CrabadaMineBot
from crabada.types import GameStats
from utils import logger, security
from utils.price import get_avax_price_usd

AVAX_PRICE_UPDATE_TIME = 60.0
DISCORD_UPDATE_TIME = 60.0 * 60.0 * 12

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/951028752257789972/WBDD5vLKziawAMRkluuLvx_eacNLItLdHHmL8PHKUj1p-q6COHks_11--Mt39l8K1T1I"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    this_dir = os.path.dirname(os.path.realpath(__file__))
    log_dir = os.path.join(os.path.dirname(this_dir), "logs")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument(
        "-l", "--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO"
    )
    parser.add_argument("-f", "--log-dir", default=log_dir)
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

    webhook = Webhook.from_url(DISCORD_WEBHOOK_URL, adapter=RequestsWebhookAdapter())
    encrypt_password = getpass.getpass(prompt="Enter decryption password: ")

    bots = []
    for user, config in USERS.items():
        config["private_key"] = security.decrypt(
            str.encode(encrypt_password), config["private_key"]
        ).decode()
        bots.append(
            CrabadaMineBot(
                user,
                config,
                TWILIO_CONFIG["from_sms_number"],
                sms_client,
                args.log_dir,
                args.dry_run,
            )
        )

    game_stats = GameStats()
    for bot in bots:
        bot.update_avax_price(get_avax_price_usd(IEX_API_TOKEN))

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
    last_discord_update = 0.0

    try:
        while True:
            gross_tus = 0.0
            wins = 0
            losses = 0

            for bot in bots:
                bot.run()

                bot_stats = bot.get_lifetime_stats()
                gross_tus += bot_stats["tus_gross"]
                wins += bot_stats["game_wins"]
                losses += bot_stats["game_losses"]

                now = time.time()
                if now - last_avax_price_update > AVAX_PRICE_UPDATE_TIME:
                    bot.update_avax_price(get_avax_price_usd(IEX_API_TOKEN))
                    last_avax_price_update = now

            if time.time() - last_discord_update > DISCORD_UPDATE_TIME:
                last_discord_update = time.time()
                webhook_text = f"\U0001F980\t**Total TUS mined by bots: {gross_tus:.2f} TUS**\n"
                win_percentage = float(wins) / (wins + losses) * 100.0
                webhook_text += f"\U0001F916\t**Bot win percentage: {win_percentage:.2f}%**\n"
                webhook.send(webhook_text)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        stop_message = f"\U0001F980 Crabada Bot Alert \U0001F980\n\n"
        stop_message += f"Crabada Bot Stopped \U0000203C\n"
        if TWILIO_CONFIG["enable_admin_sms"]:
            stop_message = f"\U0001F980 Crabada Bot Alert \U0001F980\n\n"
            stop_message += f"Crabada Bot Stopped \U0000203C\n"
            message = sms_client.messages.create(
                body=stop_message,
                from_=TWILIO_CONFIG["from_sms_number"],
                to=TWILIO_CONFIG["admin_sms_number"],
            )
        webhook.send(stop_message)
        logger.print_fail(traceback.format_exc())
    finally:
        for bot in bots:
            bot.end()


if __name__ == "__main__":
    run_bot()
