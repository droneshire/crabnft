import copy
import deepdiff
import json
import typing as T

from utils import logger
from utils.game_stats import LifetimeGameStatsLogger
from wyndblast import types

class LifetimeStats(T.TypedDict):
    chro: float
    wams: float
    elemental_stones: types.ElementalStones
    stage_1: T.Dict[str, int]
    stage_2: T.Dict[str, int]
    stage_3: T.Dict[str, int]
    commission_tus=dict(),
    avax_gas_usd=0.0,
    gas_tus=0.0,


NULL_GAME_STATS = {
    "chro": 0.0,
    "wams": 0.0,
    "elemental_stones": {
        "Fire": 0,
        "Wind": 0,
        "Earth": 0,
        "Light": 0,
        "Darkness": 0,
        "Water": 0,
        "elemental_stones_qty": 0,
    },
    "stage_1": {
        "wins": 0,
        "losses": 0,
    },
    "stage_2": {
        "wins": 0,
        "losses": 0,
    },
    "stage_3": {
        "wins": 0,
        "losses": 0,
    },
    "commission_tus": {},
    "avax_gas": 0.0,
    "gas_tus": 0.0,
}

class WyndblastLifetimeGameStatsLogger(LifetimeGameStatsLogger):
    def __init__(
        self,
        user: str,
        null_game_stats: T.Dict[T.Any, T.Any],
        log_dir: str,
        backup_stats: T.Dict[T.Any, T.Any],
        dry_run: bool = False,
        verbose: bool = False,
    ):
        super().__init__(user, null_game_stats, log_dir, backup_stats, dry_run, verbose)

    def merge_game_stats(
        self, user_a_stats: str, user_b_stats: str, log_dir: str, verbose
    ) -> LifetimeGameStats:
        diff = deepdiff.DeepDiff(user_a_stats, user_b_stats)
        if not diff:
            return user_a_stats

        merged_stats = copy.deepcopy(NULL_GAME_STATS)

        for item in ["avax_gas", "gas_tus", "chro", "wams"]:
            merged_stats[item] = merged_stats.get(item, 0.0) + user_a_stats.get(item, 0.0)
            merged_stats[item] = merged_stats.get(item, 0.0) + user_b_stats.get(item, 0.0)

        for item in ["commission_tus", "elemental_stones", "stage_1", "stage_2", "stage_3"]:
            for k, v in user_a_stats.get(item, {}).items():
                merged_stats[item][k] = merged_stats[item].get(k, 0.0) + v

            for k, v in user_b_stats.get(item, {}).items():
                merged_stats[item][k] = merged_stats[item].get(k, 0.0) + v

        if verbose:
            logger.print_bold("Merging game stats:")
            logger.print_normal(json.dumps(merged_stats, indent=4))
        return merged_stats
