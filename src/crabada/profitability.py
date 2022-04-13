import typing as T

from utils import logger
from utils.price import Prices

NORMALIZED_TIME = 4.0


class Result:
    WIN = "WIN"
    LOSE = "LOSE"
    UNKNOWN = "UNKNOWN"


class Scenarios:
    Loot = "LOOT"
    LootAndSelfReinforce = "LOOT & SELF REINFORCE"
    MineAndReinforce = "MINE & REINFORCE"
    MineTenPercentAndReinforce = "MINE +10% & REINFORCE"
    MineTenPercentAndSelfReinforce = "MINE +10% & SELF REINFORCE"
    MineAndNoReinforce = "MINE & NO REINFORCE"
    MineAndSelfReinforce = "MINE & SELF REINFORCE"
    MineTenPercentAndNoReinforce = "MINE +10% & NO REINFORCE"
    TavernThreeMpCrabs = "TAVERN 3 MP CRABS"


REINFORCE_SCENARIOS = [
    Scenarios.MineAndReinforce,
    Scenarios.MineTenPercentAndReinforce,
    Scenarios.Loot,
    Scenarios.LootAndSelfReinforce,
    Scenarios.MineTenPercentAndSelfReinforce,
    Scenarios.MineAndSelfReinforce,
]

LOOT_SCENARIOS = [
    Scenarios.Loot,
    Scenarios.LootAndSelfReinforce,
]

SELF_REINFORCE_SCENARIOS = [
    Scenarios.LootAndSelfReinforce,
    Scenarios.MineTenPercentAndSelfReinforce,
    Scenarios.MineAndSelfReinforce,
]

REWARDS_TUS: T.Dict[str, T.Dict[str, float]] = {
    Scenarios.Loot: {
        Result.WIN: {
            "TUS": 221.7375,
            "CRA": 2.7375,
        },
        Result.LOSE: {
            "TUS": 24.3,
            "CRA": 0.3,
        },
        "time_normalized": 1.0,
    },
    Scenarios.LootAndSelfReinforce: {
        Result.WIN: {
            "TUS": 221.7375,
            "CRA": 2.7375,
        },
        Result.LOSE: {
            "TUS": 24.3,
            "CRA": 0.3,
        },
        "time_normalized": 1.0,
    },
    Scenarios.MineAndReinforce: {
        Result.WIN: {
            "TUS": 303.75,
            "CRA": 3.75,
        },
        Result.LOSE: {
            "TUS": 106.3125,
            "CRA": 1.3125,
        },
        "time_normalized": 4.0,
    },
    Scenarios.MineAndSelfReinforce: {
        Result.WIN: {
            "TUS": 303.75,
            "CRA": 3.75,
        },
        Result.LOSE: {
            "TUS": 106.3125,
            "CRA": 1.3125,
        },
        "time_normalized": 4.0,
    },
    Scenarios.MineTenPercentAndReinforce: {
        Result.WIN: {
            "TUS": 334.125,
            "CRA": 4.125,
        },
        Result.LOSE: {
            "TUS": 136.6875,
            "CRA": 1.6875,
        },
        "time_normalized": 4.0,
    },
    Scenarios.MineTenPercentAndSelfReinforce: {
        Result.WIN: {
            "TUS": 334.125,
            "CRA": 4.125,
        },
        Result.LOSE: {
            "TUS": 136.6875,
            "CRA": 1.6875,
        },
        "time_normalized": 4.0,
    },
    Scenarios.MineAndNoReinforce: {
        Result.WIN: {
            "TUS": 106.3125,
            "CRA": 1.3125,
        },
        Result.LOSE: {
            "TUS": 106.3125,
            "CRA": 1.3125,
        },
        "time_normalized": 4.0,
    },
    Scenarios.MineTenPercentAndNoReinforce: {
        Result.WIN: {
            "TUS": 136.6875,
            "CRA": 1.6875,
        },
        Result.LOSE: {
            "TUS": 136.6875,
            "CRA": 1.6875,
        },
        "time_normalized": 4.0,
    },
    Scenarios.TavernThreeMpCrabs: {
        Result.WIN: {
            "TUS": 0.0,
            "CRA": 0.0,
        },
        Result.LOSE: {
            "TUS": 0.0,
            "CRA": 0.0,
        },
        "time_normalized": 2.0,
    },
}


def get_expected_tus(game_type: Scenarios, prices: Prices, win_percent: float) -> float:
    win_decimal = win_percent / 100.0
    winnings_tus = REWARDS_TUS[game_type][Result.WIN]["TUS"]
    winnings_cra = REWARDS_TUS[game_type][Result.WIN]["CRA"]
    winnings_tus += prices.cra_to_tus(winnings_cra)

    losings_tus = REWARDS_TUS[game_type][Result.LOSE]["TUS"]
    losings_cra = REWARDS_TUS[game_type][Result.LOSE]["CRA"]
    losings_tus += prices.cra_to_tus(losings_cra)

    return win_decimal * winnings_tus + (1 - win_decimal) * losings_tus


def get_expected_game_profit(
    game_type: str,
    prices: Prices,
    avg_gas_price_avax: float,
    avg_reinforce_tus: float,
    win_percent: float,
    do_reinforce: bool,
    verbose: bool = False,
) -> float:
    revenue_tus = get_expected_tus(game_type, prices, win_percent)
    avg_gas_per_game_avax = avg_gas_price_avax * (4 if do_reinforce else 2)
    avg_gas_per_game_tus = prices.avax_to_tus(avg_gas_per_game_avax)

    reinforcement_per_game_tus = 2.0 * avg_reinforce_tus if do_reinforce else 0.0

    profit_tus = revenue_tus - avg_gas_per_game_tus - reinforcement_per_game_tus
    if verbose:
        logger.print_normal(
            f"[{game_type}]: Revenue: {revenue_tus}, Gas: {avg_gas_per_game_tus}, Reinforce: {reinforcement_per_game_tus}, Profit: {profit_tus}"
        )
    return profit_tus


def is_idle_game_transaction_profitable(
    game_type: str,
    prices: Prices,
    avg_gas_price_avax: float,
    avg_reinforce_tus: float,
    win_percent: float,
    do_reinforce: bool,
    verbose: bool = False,
) -> bool:
    return (
        get_expected_game_profit(
            game_type, prices, avg_gas_price_avax, avg_reinforce_tus, win_percent, do_reinforce
        )
        > 0.0
    )


def get_profitability_message(
    prices: Prices,
    avg_gas_avax: float,
    gas_price_gwei: float,
    avg_reinforce_tus: float,
    mine_win_percent: float,
    verbose: bool = False,
) -> str:
    PROFIT_HYSTERESIS = 10

    message = "**Profitability Update**\n"
    message += "{}\t\t{}\n".format(f"**Avg Tx Gas \U000026FD**:", f"{avg_gas_avax:.5f} AVAX")
    message += "{}\t\t{}\n".format(f"**Avg Gas Price \U000026FD**:", f"{gas_price_gwei:.6f} gwei")
    message += "{}\t{}\n".format(f"**Avg Mining Win % \U0001F3C6**:", f"{mine_win_percent:.2f}%")
    message += "{}\t{}\n".format(
        f"**Avg Looting Win % \U0001F480**:", f"{(100.0 - mine_win_percent):.2f}%"
    )
    message += "{}\t{}\n\n".format(
        f"**Avg Reinforce Cost \U0001F4B0**:", f"{avg_reinforce_tus:.2f} TUS"
    )

    message += f"**Prices**\n"
    message += (
        f"AVAX: ${prices.avax_usd:.3f}, TUS: ${prices.tus_usd:.3f}, CRA: ${prices.cra_usd:.3f}\n\n"
    )

    message += f"**Expected Profit (EP)**\n"
    message += f"*(normalized over a 4 hour window)*\n"

    for game in REWARDS_TUS.keys():
        if game in LOOT_SCENARIOS:
            win_percent = 100.0 - mine_win_percent
        else:
            win_percent = mine_win_percent

        if game == Scenarios.TavernThreeMpCrabs:
            profit_tus = avg_reinforce_tus * 3 - prices.avax_to_tus(avg_gas_avax) / 6
        else:
            do_reinforce = game in REINFORCE_SCENARIOS
            reinforce_tus = avg_reinforce_tus if game not in SELF_REINFORCE_SCENARIOS else 0.0
            profit_tus = get_expected_game_profit(
                game, prices, avg_gas_avax, reinforce_tus, win_percent, do_reinforce
            )

        games_per_4_hrs = NORMALIZED_TIME / REWARDS_TUS[game]["time_normalized"]
        profit_tus_4_hrs = profit_tus * games_per_4_hrs
        profit_usd_4_hrs = prices.tus_usd * profit_tus_4_hrs
        profit_emoji = "\U0001F4C8" if profit_tus_4_hrs > 0.0 else "\U0001F4C9"

        message += "{}\n    {} $TUS,    ${}\n".format(
            f"**{game}**:", f"{profit_tus_4_hrs:.2f}", f"{profit_usd_4_hrs:.2f}"
        )

    if verbose:
        logger.print_normal(message)

    return message
