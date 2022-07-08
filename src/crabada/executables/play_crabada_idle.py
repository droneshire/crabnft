"""
Starts bots for interacting with the Crabada Dapp P2E game
"""
import argparse
import getpass
import logging
import os
import time
import traceback
import typing as T
from discord import Webhook
from twilio.rest import Client

from config_crabada import (
    COINMARKETCAP_API_TOKEN,
    GAME_BOT_STRING,
    GMAIL,
    USER_GROUPS,
    IEX_API_TOKEN,
    TWILIO_CONFIG,
    USERS,
)
from crabada.bot import CrabadaMineBot
from crabada.game_stats import LifetimeGameStats
from crabada.profitability import get_profitability_message
from crabada.types import MineOption
from utils import discord, logger, security
from utils.circuit_breaker import CircuitBreaker
from utils.email import get_email_accounts_from_password
from utils.general import dict_sum
from utils.math import Average
from utils.price import DEFAULT_GAS_USED, get_avax_price_usd, get_token_price_usd, Prices

PRICE_UPDATE_TIME = 60.0 * 60.0
BOT_TOTALS_UPDATE = 60.0 * 5
PROFITABILITY_UPDATE_TIME = 60.0 * 10.0
GAS_DOWNSAMPLE_COUNT = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    log_dir = logger.get_logging_dir("crabada")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--use-proxy", action="store_true", help="Use proxy if available")
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
        + f"_crabada_{id_string}.log"
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


def get_users_teams() -> T.Tuple[int, int]:
    total_users = len(USERS.keys())
    total_teams = sum(
        [
            len(v["game_specific_configs"]["mining_teams"].keys())
            + len(v["game_specific_configs"]["looting_teams"])
            for _, v in USERS.items()
        ]
    )
    return (total_users, total_teams)


def handle_subscription_posts(
    prices: Prices, avg_gas_tus: float, gas_price_gwei: float, avg_reinforce_tus: float
) -> None:
    subscriptions = {
        "HEYA_SUBSCRIPTION": {
            "hook": discord.get_discord_hook("HEYA_SUBSCRIPTION"),
            "win_percentages": {
                MineOption.MINE: 40.0,
                MineOption.LOOT: 80.0,
            },
        }
    }
    for subscription, details in subscriptions.items():
        logger.print_normal(f"Sending subscription profitability update to {subscription}")
        message = get_profitability_message(
            prices,
            avg_gas_tus,
            gas_price_gwei,
            avg_reinforce_tus,
            details["win_percentages"],
            use_static_percents=False,
            log_stats=False,
            verbose=True,
        )
        details["hook"].send(message)


def run_bot() -> None:
    args = parse_args()

    if len(args.groups) == 0:
        id_string = ""
    elif len(args.groups) == 1:
        id_string = str(args.groups[0])
    else:
        id_string = "_".join([str(g) for g in args.groups])
    setup_log(args.log_level, args.log_dir, id_string)

    sms_client = Client(TWILIO_CONFIG["account_sid"], TWILIO_CONFIG["account_auth_token"])

    webhooks = {
        "CRABADA_HOLDERS": discord.get_discord_hook("CRABADA_HOLDERS"),
        "CRABADA_UPDATES": discord.get_discord_hook("CRABADA_UPDATES"),
        "LOOT_SNIPE": discord.get_discord_hook("LOOT_SNIPE"),
    }

    encrypt_password = ""
    email_accounts = []

    if not args.dry_run:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")
        email_accounts = get_email_accounts_from_password(encrypt_password, GMAIL)

    bots = []
    for user, config in USERS.items():
        if config["group"] not in [int(i) for i in args.groups]:
            logger.print_warn(f"Skipping {user} in group {config['group']}...")
            continue

        config["private_key"] = security.decrypt_secret(encrypt_password, config["private_key"])

        bots.append(
            CrabadaMineBot(
                user,
                config,
                TWILIO_CONFIG["from_sms_number"],
                sms_client,
                email_accounts,
                encrypt_password,
                args.log_dir,
                args.dry_run,
                args.use_proxy,
            )
        )

    total_commission_tus = 0.0
    total_tus = 0.0
    prices = Prices(
        get_avax_price_usd(IEX_API_TOKEN, dry_run=args.dry_run),
        get_token_price_usd(COINMARKETCAP_API_TOKEN, "TUS", dry_run=args.dry_run),
        get_token_price_usd(COINMARKETCAP_API_TOKEN, "CRA", dry_run=args.dry_run),
    )

    for bot in bots:
        bot.update_prices(prices.avax_usd, prices.tus_usd, prices.cra_usd)
        logger.print_bold(f"Starting game bot for user {bot.user}...")
        bot_stats = bot.get_lifetime_stats()
        total_commission_tus += dict_sum(bot_stats["commission_tus"])
        for k in [MineOption.MINE, MineOption.LOOT]:
            total_tus += bot_stats[k]["tus_gross"]

    logger.print_bold(f"Mined TUS: {total_tus} TUS Commission TUS: {total_commission_tus} TUS")
    total_users, total_teams = get_users_teams()
    logger.print_bold(f"Users: {total_users}, Teams: {total_teams}")
    logger.print_normal("\n")

    last_price_update = 0.0
    last_discord_update = time.time()
    last_profitability_update = time.time()
    avg_gas_tus = Average(DEFAULT_GAS_USED)
    avg_reinforce_tus = Average(9.0)
    avg_gas_gwei = Average(50.0)

    alerts_enabled = not args.quiet and not args.dry_run
    reinforcement_backoff = 0

    # assume only group 1 can post updates
    should_post_updates = 1 in [int(i) for i in args.groups]
    group_backoff_adjustment = int(args.groups[0]) if len(args.groups) == 1 else 0

    circuit_breaker = CircuitBreaker(min_delta=60.0 * 5.0, backoff=80.0)

    try:
        while True:
            gross_tus = 0.0
            totals = {
                MineOption.MINE: {"wins": 0, "losses": 0},
                MineOption.LOOT: {"wins": 0, "losses": 0},
            }

            circuit_breaker.start()

            for bot in bots:
                bot.set_backoff(reinforcement_backoff)
                bot.run()
                avg_gas_tus.update(bot.get_avg_gas_tus())
                avg_reinforce_tus.update(bot.get_avg_reinforce_tus())
                avg_gas_gwei.update(bot.get_avg_gas_gwei())
                reinforcement_backoff = bot.get_backoff()

                bot_stats = bot.get_lifetime_stats()
                for k in totals.keys():
                    gross_tus += bot_stats[k]["tus_gross"]
                    if bot.get_config()["game_specific_configs"]["should_reinforce"]:
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

            circuit_breaker.end()

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
                avg_gas_tus.get_avg(),
                avg_gas_gwei.get_avg(),
                avg_reinforce_tus.get_avg(),
                win_percentages,
                commission_percent=0.0,
                verbose=True,
                use_static_percents=True,
                log_stats=True,
                group=id_string,
            )

            if now - last_discord_update > BOT_TOTALS_UPDATE:
                last_discord_update = now
                groups = ", ".join([str(g) for g in args.groups])
                message = f"{GAME_BOT_STRING}\t**Total TUS mined by groups {groups} bot: {int(gross_tus):,} TUS**\n"
                for k in totals.keys():
                    message += f"\U0001F916\t**Bot {k.lower()} win percentage: {win_percentages[k]:.2f}%**\n"
                total_users, total_teams = get_users_teams()
                message += f"**Users: {total_users} Teams: {total_teams}**\n"
                logger.print_normal(message)

            if not should_post_updates:
                continue

            now = time.time()
            if alerts_enabled and now - last_profitability_update > PROFITABILITY_UPDATE_TIME:
                last_profitability_update = now
                # try:
                #     webhooks["CRABADA_UPDATES"].send(profitability_message)
                # except:
                #     logger.print_fail(f"Failed to post to discord hook")

                handle_subscription_posts(
                    prices,
                    avg_gas_tus.get_avg(),
                    avg_gas_gwei.get_avg(),
                    avg_reinforce_tus.get_avg(),
                )

            if avg_gas_tus.count > GAS_DOWNSAMPLE_COUNT:
                avg_gas_tus_val = avg_gas_tus.get_avg()
                avg_gas_gwei_val = avg_gas_gwei.get_avg()

                if avg_gas_tus_val is not None:
                    avg_gas_tus.reset(avg_gas_tus.get_avg())
                if avg_gas_gwei_val is not None:
                    avg_gas_gwei.reset(avg_gas_gwei.get_avg())

    except KeyboardInterrupt:
        pass
    except Exception as e:
        stop_message = f"{GAME_BOT_STRING} Alert \U0001F980\n\n"
        stop_message += f"@Cashflow Crabada Bot Stopped \U0000203C\n"
        if alerts_enabled and TWILIO_CONFIG["enable_admin_sms"]:
            stop_message = f"{GAME_BOT_STRING} Alert \U0001F980\n\n"
            stop_message += f"Crabada Bot Stopped \U0000203C\n"
            message = sms_client.messages.create(
                body=stop_message,
                from_=TWILIO_CONFIG["from_sms_number"],
                to=TWILIO_CONFIG["admin_sms_number"],
            )
        if alerts_enabled:
            stop_message += "Please manually attend your mines until we're back up"
            try:
                webhooks["CRABADA_HOLDERS"].send(stop_message)
            except:
                pass
        logger.print_fail(traceback.format_exc())
    finally:
        for bot in bots:
            bot.end()


if __name__ == "__main__":
    run_bot()
