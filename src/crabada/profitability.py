import typing as T

from utils import logger
from utils.price import Prices

REWARDS_TUS: T.Dict[str, T.Dict[str, float]] = {
    "LOOT": {
        "win": {
            "TUS": 221.7375,
            "CRA": 2.7375,
        },
        "lose": {
            "TUS": 24.3,
            "CRA": 0.3,
        },
    },
    "MINE": {
        "win": {
            "TUS": 303.75,
            "CRA": 3.75,
        },
        "lose": {
            "TUS": 106.3125,
            "CRA": 1.3125,
        },
    },
}
TRANSACTION_PER_GAME: int = 4


def get_expected_tus(game_type: str, prices: Prices, win_percent: float) -> float:
    win_decimal = win_percent / 100.0
    winnings_tus = REWARDS_TUS[game_type.upper()]["win"]["TUS"]
    winnings_cra = REWARDS_TUS[game_type.upper()]["win"]["CRA"]
    winnings_tus += prices.cra_to_tus(winnings_cra)

    losings_tus = REWARDS_TUS[game_type.upper()]["lose"]["TUS"]
    losings_cra = REWARDS_TUS[game_type.upper()]["lose"]["CRA"]
    losings_tus += prices.cra_to_tus(losings_cra)

    return win_decimal * winnings_tus + (1 - win_decimal) * losings_tus


def get_expected_game_profit(
    game_type: str,
    prices: Prices,
    avg_gas_price_avax: float,
    avg_reinforce_tus: float,
    win_percent: float,
    verbose: bool = False,
) -> float:
    revenue_tus = get_expected_tus(game_type, prices, win_percent)
    avg_gas_per_game_avax = avg_gas_price_avax * TRANSACTION_PER_GAME
    avg_gas_per_game_tus = prices.avax_to_tus(avg_gas_per_game_avax)

    reinforcement_per_game_tus = 2 * avg_reinforce_tus

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
    verbose: bool = False,
) -> bool:
    return (
        get_expected_game_profit(
            game_type, prices, avg_gas_price_avax, avg_reinforce_tus, win_percent
        )
        > 0.0
    )


def get_profitability_message(
    prices: Prices,
    avg_gas_avax: float,
    avg_reinforce_tus: float,
    mine_win_percent: float,
    verbose: bool = False,
) -> str:
    PROFIT_HYSTERESIS = 10

    message = f"**Profitability Update**\n"
    message += f"**Avg Tx Gas \U000026FD**: {avg_gas_avax:.5f} AVAX\n"
    message += f"**Avg Mine Win % \U0001F3C6**: {mine_win_percent:.2f}%\n"
    message += f"**Avg Reinforce Cost \U0001F4B0**: {avg_reinforce_tus:.2f} TUS\n\n"

    message += f"**Prices**\n"
    message += (
        f"AVAX: ${prices.avax_usd:.3f}, TUS: ${prices.tus_usd:.3f}, CRA: ${prices.cra_usd:.3f}\n\n"
    )

    for game in ["LOOT", "MINE"]:
        if game == "LOOT":
            win_percent = 100.0 - mine_win_percent
        else:
            win_percent = mine_win_percent
        profit_tus = get_expected_game_profit(
            game, prices, avg_gas_avax, avg_reinforce_tus, win_percent
        )
        is_profitable = is_idle_game_transaction_profitable(
            game, prices, avg_gas_avax, avg_reinforce_tus, win_percent
        )
        profit_emoji = "\U0001F4C8" if is_profitable else "\U0001F4C9"
        profit_usd = prices.tus_usd * profit_tus
        message += (
            f"**{game}**: Expected Profit {profit_tus:.2f} TUS {profit_emoji} (${profit_usd:.2f})\n"
        )

    if verbose:
        logger.print_normal(message)

    return message
