import typing as T

from utils import logger
from utils.price import Prices

REWARDS_TUS: T.Dict[str, T.Dict[str, float]] = {
    "LOOT": {
        "win": 221.8097276,
        "lose": 27.29965878,
    },
    "MINE": {
        "win": 341.2457348,
        "lose": 117.6237133,
    },
}
TRANSACTION_PER_GAME: int = 4


def get_expected_tus(game_type: str, win_percent: float) -> float:
    win_decimal = win_percent / 100.0
    return win_decimal * (REWARDS_TUS[game_type.upper()]["win"]) + (1 - win_decimal) * (
        REWARDS_TUS[game_type.upper()]["lose"]
    )


def get_expected_game_profit(
    game_type: str,
    prices: Prices,
    avg_gas_price_avax: float,
    avg_reinforce_tus: float,
    win_percent: float,
    verbose: bool = False,
) -> float:
    revenue_tus = get_expected_tus(game_type, win_percent)
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
