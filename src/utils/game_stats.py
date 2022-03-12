import json
import os
import typing as T

from utils import logger


class GameStats(T.TypedDict):
    tus_gross: float
    cra_net: float
    tus_net: float
    game_wins: int
    game_losses: int
    game_win_percent: float
    commission_tus: float
    tus_reinforcement: float
    avax_gas_usd: float


NULL_GAME_STATS = GameStats(
    tus_gross=0.0,
    cra_net=0.0,
    tus_net=0.0,
    game_wins=0,
    game_losses=0,
    game_win_percent=0.0,
    commission_tus=0.0,
    tus_reinforcement=0.0,
    avax_gas_usd=0.0,
)


def get_lifetime_stats_file(user: str, log_dir: str) -> str:
    return os.path.join(log_dir, user.lower() + "_lifetime_game_bot_stats.json")


def get_game_stats(user: str, log_dir: str) -> T.Dict[str, T.Any]:
    game_stats_file = get_lifetime_stats_file(user, log_dir)
    if not os.path.isfile(game_stats_file):
        return {}
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
