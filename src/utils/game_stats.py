import json
import os
import typing as T
from eth_typing import Address

from utils import logger


class GameStats(T.TypedDict):
    reinforce1: float
    reinforce2: float
    gas_start: float
    gas_reinforce1: float
    gas_reinforce2: float
    gas_close: float
    game_type: T.Literal["MINE", "LOOT"]
    reward_tus: float
    reward_cra: float
    avax_usd: float
    tus_usd: float
    cra_usd: float
    commission_tus: float
    outcome: T.Literal["WIN", "LOSE"]


class MineLootGameStats(T.TypedDict):
    tus_gross: T.Dict[str, float]
    cra_net: T.Dict[str, float]
    tus_net: T.Dict[str, float]
    cra_gross: T.Dict[str, float]
    game_wins: T.Dict[str, float]
    game_losses: T.Dict[str, float]
    game_win_percent: T.Dict[str, float]
    tus_reinforcement: T.Dict[str, float]


class LifetimeGameStats(T.TypedDict):
    commission_tus: float
    avax_gas_usd: float
    MINE: MineLootGameStats
    LOOT: MineLootGameStats


NULL_GAME_STATS = LifetimeGameStats(
    MINE=MineLootGameStats(
        cra_gross=0.0,
        tus_gross=0.0,
        cra_net=0.0,
        tus_net=0.0,
        game_wins=0.0,
        game_losses=0.0,
        game_win_percent=0.0,
        tus_reinforcement=0.0,
    ),
    LOOT=MineLootGameStats(
        cra_gross=0.0,
        tus_gross=0.0,
        cra_net=0.0,
        tus_net=0.0,
        game_wins=0,
        game_losses=0,
        game_win_percent=0.0,
        tus_reinforcement=0.0,
    ),
    commission_tus=dict(),
    avax_gas_usd=0.0,
)


def update_lifetime_stats_format(game_stats: LifetimeGameStats) -> LifetimeGameStats:
    new_game_stats = LifetimeGameStats()
    new_game_stats["MINE"] = MineLootGameStats()
    new_game_stats["LOOT"] = MineLootGameStats()

    if "MINE" in game_stats or "LOOT" in game_stats:
        return game_stats

    for k, v in game_stats.items():
        if k in ["commission_tus", "avax_gas_usd"]:
            new_game_stats[k] = v
        elif k not in NULL_GAME_STATS["MINE"].keys():
            continue
        elif isinstance(v, (float, int)):
            new_game_stats["MINE"][k] = v
            new_game_stats["LOOT"][k] = 0.0
        else:
            return game_stats
    logger.print_normal(f"Old:\n{json.dumps(game_stats, indent=4)}")
    logger.print_bold(f"New:\n{json.dumps(new_game_stats, indent=4)}")
    return new_game_stats


def get_lifetime_stats_file(user: str, log_dir: str) -> str:
    return os.path.join(log_dir, user.lower() + "_lifetime_game_bot_stats.json")


def get_game_stats(user: str, log_dir: str) -> T.Dict[str, T.Any]:
    game_stats_file = get_lifetime_stats_file(user, log_dir)
    if not os.path.isfile(game_stats_file):
        return NULL_GAME_STATS
    with open(game_stats_file, "r") as infile:
        return json.load(infile)


def write_game_stats(user: str, log_dir: str, game_stats: LifetimeGameStats) -> None:
    game_stats_file = get_lifetime_stats_file(user, log_dir)
    with open(game_stats_file, "w") as outfile:
        json.dump(
            game_stats,
            outfile,
            indent=4,
            sort_keys=True,
        )
