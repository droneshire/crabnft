"""
Starts bots for interacting with the Crabada Dapp P2E game
"""
import argparse
import copy
import getpass
import json
import logging
import os
import requests
import sys
import time
import traceback
import typing as T
from discord import Webhook
from twilio.rest import Client

from config import COINMARKETCAP_API_TOKEN, GMAIL, USER_GROUPS, IEX_API_TOKEN, TWILIO_CONFIG, USERS
from crabada.bot import CrabadaMineBot
from crabada.profitability import get_profitability_message
from utils import discord, email, logger, price, security
from utils.game_stats import LifetimeGameStats
from utils.general import dict_sum, get_pretty_seconds
from utils.math import Average
from utils.price import get_avax_price_usd, get_token_price_usd

PRICE_UPDATE_TIME = 60.0 * 30.0
DISCORD_UPDATE_TIME = 60.0 * 60.0 * 3
PROFITABILITY_UPDATE_TIME = 60.0 * 10.0
GAS_DOWNSAMPLE_COUNT = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    log_dir = logger.get_logging_dir()
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--quiet", action="store_true", help="Disable alerts")
    parser.add_argument("--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO")
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument("--groups", nargs="+", default=USER_GROUPS)
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


def get_users_teams() -> T.Tuple[int, int]:
    total_users = len(USERS.keys())
    total_teams = sum(
        [len(v["mining_teams"].keys()) + len(v["looting_teams"]) for _, v in USERS.items()]
    )
    return (total_users, total_teams)


def run_bot() -> None:
    args = parse_args()

    setup_log(args.log_level, args.log_dir)

    sms_client = Client(TWILIO_CONFIG["account_sid"], TWILIO_CONFIG["account_auth_token"])

    webhooks = {
        "HOLDERS": discord.get_discord_hook("HOLDERS"),
        "UPDATES": discord.get_discord_hook("UPDATES"),
        "LOOT_SNIPE": discord.get_discord_hook("LOOT_SNIPE"),
    }

    encrypt_password = ""
    email_password = ""
    if not args.dry_run:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")
        email_password = security.decrypt(str.encode(encrypt_password), GMAIL["password"]).decode()

    email_account = email.Email(address=GMAIL["user"], password=email_password)

    bots = []
    for user, config in USERS.items():
        if config["group"] not in [int(i) for i in args.groups]:
            logger.print_warn(f"Skipping {user} in group {config['group']}...")
            continue

        crabada_key = (
            ""
            if not encrypt_password
            else security.decrypt(str.encode(encrypt_password), config["crabada_key"]).decode()
        )
        config["crabada_key"] = crabada_key

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

    total_commission_tus = 0.0
    total_tus = 0.0
    prices = price.Prices(
        get_avax_price_usd(IEX_API_TOKEN, dry_run=args.dry_run),
        get_token_price_usd(COINMARKETCAP_API_TOKEN, "TUS", dry_run=args.dry_run),
        get_token_price_usd(COINMARKETCAP_API_TOKEN, "CRA", dry_run=args.dry_run),
    )

    for bot in bots:
        bot.update_prices(prices.avax_usd, prices.tus_usd, prices.cra_usd)
        logger.print_bold(f"Starting game bot for user {bot.user}...")
        bot_stats = bot.get_lifetime_stats()
        total_commission_tus += dict_sum(bot_stats["commission_tus"])
        for k in ["MINE", "LOOT"]:
            total_tus += bot_stats[k]["tus_gross"]

    logger.print_bold(f"Mined TUS: {total_tus} TUS Commission TUS: {total_commission_tus} TUS")
    total_users, total_teams = get_users_teams()
    logger.print_bold(f"Users: {total_users}, Teams: {total_teams}")
    logger.print_normal("\n")

    last_price_update = 0.0
    last_discord_update = time.time()
    last_profitability_update = time.time()
    downsample_count = 0
    avg_gas_avax = Average(0.1)
    avg_reinforce_tus = Average(17.0)
    avg_gas_gwei = Average(100.0)

    alerts_enabled = not args.quiet and not args.dry_run
    reinforcement_backoff = 0

    try:
        while True:
            gross_tus = 0.0
            totals = {"MINE": {"wins": 0, "losses": 0}, "LOOT": {"wins": 0, "losses": 0}}

            start_of_loop = time.time()

            for bot in bots:
                bot.set_backoff(reinforcement_backoff)
                bot.run()
                avg_gas_avax.update(bot.get_avg_gas_avax())
                avg_reinforce_tus.update(bot.get_avg_reinforce_tus())
                avg_gas_gwei.update(bot.get_avg_gas_gwei())
                reinforcement_backoff = bot.get_backoff()

                bot_stats = bot.get_lifetime_stats()
                for k in totals.keys():
                    gross_tus += bot_stats[k]["tus_gross"]
                    if bot.get_config()["should_reinforce"]:
                        totals[k]["wins"] += bot_stats[k]["game_wins"]
                        totals[k]["losses"] += bot_stats[k]["game_losses"]

                now = time.time()
                if now - last_price_update > PRICE_UPDATE_TIME:
                    prices.update(
                        get_avax_price_usd(IEX_API_TOKEN),
                        get_token_price_usd(COINMARKETCAP_API_TOKEN, "TUS"),
                        get_token_price_usd(COINMARKETCAP_API_TOKEN, "CRA"),
                    )
                    bot.update_prices(prices.avax_usd, prices.tus_usd, prices.cra_usd)
                    last_price_update = now

            logger.print_bold(
                f"Took {get_pretty_seconds(int(time.time() - start_of_loop))} to get through all {len(USERS.keys())} players"
            )
            win_percentages = {}
            for k in totals.keys():
                if totals[k].get("wins", 0) == 0 and totals[k].get("losses", 0) == 0:
                    win_percentages[k] = 0.0
                else:
                    win_percentages[k] = (
                        float(totals[k]["wins"]) / (totals[k]["wins"] + totals[k]["losses"]) * 100.0
                    )
            profitability_message = get_profitability_message(
                prices,
                avg_gas_avax.get_avg(),
                avg_gas_gwei.get_avg(),
                avg_reinforce_tus.get_avg(),
                win_percentages,
                commission_percent=0.0,
                verbose=True,
                use_static_percents=True,
            )

            now = time.time()
            if alerts_enabled and now - last_profitability_update > PROFITABILITY_UPDATE_TIME:
                last_profitability_update = now
                webhooks["UPDATES"].send(profitability_message)

            if alerts_enabled and now - last_discord_update > DISCORD_UPDATE_TIME:
                last_discord_update = now
                groups = ", ".join(args.groups)
                webhook_text = f"\U0001F980\t**Total TUS mined by groups {groups} bot: {int(gross_tus):,} TUS**\n"
                for k in totals.keys():
                    webhook_text += f"\U0001F916\t**Bot {k.lower()} win percentage: {win_percentages[k]:.2f}%**\n"
                total_users, total_teams = get_users_teams()
                webhook_text += f"**Users: {total_users} Teams: {total_teams}**\n"
                webhooks["HOLDERS"].send(webhook_text)

            downsample_count += 1
            if downsample_count > GAS_DOWNSAMPLE_COUNT:
                downsample_count = 0
                avg_gas_avax.reset(avg_gas_avax.get_avg())
                avg_gas_gwei.reset(avg_gas_gwei.get_avg())

    except KeyboardInterrupt:
        pass
    except Exception as e:
        stop_message = f"\U0001F980 Crabada Bot Alert \U0001F980\n\n"
        stop_message += f"@Cashflow Crabada Bot Stopped \U0000203C\n"
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
            webhooks["HOLDERS"].send(stop_message)
        logger.print_fail(traceback.format_exc())
    finally:
        for bot in bots:
            bot.end()


if __name__ == "__main__":
    run_bot()
