import json
import os
import typing as T
from eth_typing import Address

from utils import logger


class GameStats(T.TypedDict):
    tus_gross: T.Dict[str, float]
    cra_net: T.Dict[str, float]
    tus_net: T.Dict[str, float]
    cra_gross: T.Dict[str, float]
    game_wins: T.Dict[str, float]
    game_losses: T.Dict[str, float]
    game_win_percent: T.Dict[str, float]
    commission_tus: T.Dict[Address, float]
    tus_reinforcement: T.Dict[str, float]
    avax_gas_usd: float

NULL_GAME_STATS = GameStats(
    cra_gross= {
        "MINE": 0.0,
        "LOOT": 0.0,
    },
    tus_gross={
        "MINE": 0.0,
        "LOOT": 0.0,
    },
    cra_net={
        "MINE": 0.0,
        "LOOT": 0.0,
    },
    tus_net={
        "MINE": 0.0,
        "LOOT": 0.0,
    },
    game_wins={
        "MINE": 0.0,
        "LOOT": 0.0,
    },
    game_losses={
        "MINE": 0.0,
        "LOOT": 0.0,
    },
    game_win_percent={
        "MINE": 0.0,
        "LOOT": 0.0,
    },
    commission_tus=dict(),
    tus_reinforcement={
        "MINE": 0.0,
        "LOOT": 0.0,
    },
    avax_gas_usd=0.0,
)


def get_lifetime_stats_file(user: str, log_dir: str) -> str:
    return os.path.join(log_dir, user.lower() + "_lifetime_game_bot_stats.json")


def get_game_stats(user: str, log_dir: str) -> T.Dict[str, T.Any]:
    game_stats_file = get_lifetime_stats_file(user, log_dir)
    if not os.path.isfile(game_stats_file):
        return NULL_GAME_STATS
    with open(game_stats_file, "r") as infile:
        return json.load(infile)


def write_game_stats(user: str, log_dir: str, game_stats: GameStats) -> None:
    game_stats_file = get_lifetime_stats_file(user, log_dir)
    with open(game_stats_file, "w") as outfile:
        json.dump(
            game_stats,
            outfile,
            indent=4,
            sort_keys=True,
        )
