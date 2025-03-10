import argparse

from config_admin import IEX_API_TOKEN, COINMARKETCAP_API_TOKEN
from config_crabada import USERS
from crabada.profitability import (
    get_profitability_message,
    STATIC_WIN_PERCENTAGES,
)
from crabada.game_stats import CrabadaLifetimeGameStatsLogger
from crabada.types import MineOption
from utils import logger
from utils.general import dict_sum
from utils.price import get_avax_price_usd, get_token_price_usd, Prices
from utils.user import get_alias_from_user


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--avg-gas-tus", type=float, default=2.03)
    parser.add_argument("--avg-reinforce-tus", type=float, default=14.0)
    parser.add_argument("--commission-percent", type=float, default=10.0)
    parser.add_argument(
        "--gas-price-gwei",
        type=float,
        default=STATIC_WIN_PERCENTAGES[MineOption.MINE],
    )
    parser.add_argument(
        "--user", choices=list(USERS.keys()) + ["ALL"], required=False
    )
    parser.add_argument(
        "--mine-win-percent",
        type=float,
        default=STATIC_WIN_PERCENTAGES[MineOption.MINE],
    )
    parser.add_argument(
        "--loot-win-percent",
        type=float,
        default=STATIC_WIN_PERCENTAGES[MineOption.LOOT],
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def calc_profits() -> None:
    args = parse_args()

    prices = Prices(
        get_avax_price_usd(IEX_API_TOKEN, dry_run=args.dry_run),
        get_token_price_usd(
            COINMARKETCAP_API_TOKEN, "TUS", dry_run=args.dry_run
        ),
        get_token_price_usd(
            COINMARKETCAP_API_TOKEN, "CRA", dry_run=args.dry_run
        ),
    )

    users = []
    if not args.user:
        win_percentages = {
            MineOption.MINE: args.mine_win_percent,
            MineOption.LOOT: args.loot_win_percent,
        }
        commission_percent = args.commission_percent
        get_profitability_message(
            prices,
            args.avg_gas_tus,
            args.gas_price_gwei,
            args.avg_reinforce_tus,
            win_percentages,
            commission_percent=commission_percent,
            verbose=True,
            use_static_percents=False,
            log_stats=False,
        )
        return

    if args.user == "ALL":
        users = list(USERS.keys())
    else:
        users = [args.user]

    for user in users:
        alias = get_alias_from_user(user)
        logger.print_ok_blue(f"Profitability Analysis for {alias.upper()}:")

        stats = CrabadaLifetimeGameStatsLogger(
            user, logger.get_logging_dir("crabada"), {}, dry_run=args.dry_run
        ).get_game_stats()

        win_percentages = {
            MineOption.MINE: stats[MineOption.MINE]["game_win_percent"],
            MineOption.LOOT: stats[MineOption.LOOT]["game_win_percent"],
        }

        commission_percent = dict_sum(
            USERS[user]["commission_percent_per_mine"]
        )

        get_profitability_message(
            prices,
            args.avg_gas_tus,
            args.gas_price_gwei,
            args.avg_reinforce_tus,
            win_percentages,
            commission_percent=commission_percent,
            verbose=True,
            use_static_percents=False,
        )


if __name__ == "__main__":
    calc_profits()
