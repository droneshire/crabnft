import copy
import deepdiff
import json
import typing as T

from utils import logger
from utils.game_stats import LifetimeGameStatsLogger
from wyndblast import types


class PveStats(T.TypedDict):
    levels_completed: T.List[str]
    quests_completed: T.List[str]
    account_exp: int


class LifetimeStats(T.TypedDict):
    chro: float
    wams: float
    elemental_stones: types.ElementalStones
    stage_1: T.Dict[str, float]
    stage_2: T.Dict[str, float]
    stage_3: T.Dict[str, float]
    commission_chro: T.Dict[str, float]
    avax_gas: float
    pve_game: PveStats


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
    "commission_chro": {},
    "avax_gas": 0.0,
    "pve_game": {
        "levels_completed": [],
        "quests_completed": [],
        "account_exp": 0,
    },
}


class WyndblastLifetimeGameStatsLogger(LifetimeGameStatsLogger):
    def __init__(
        self,
        user: str,
        log_dir: str,
        backup_stats: T.Dict[T.Any, T.Any],
        dry_run: bool = False,
        verbose: bool = False,
    ):
        super().__init__(user, NULL_GAME_STATS, log_dir, backup_stats, dry_run, verbose)

    def delta_game_stats(
        self,
        user_a_stats: LifetimeStats,
        user_b_stats: LifetimeStats,
        verbose: bool = False,
    ) -> LifetimeStats:
        diff = deepdiff.DeepDiff(user_a_stats, user_b_stats)
        if not diff:
            return copy.deepcopy(NULL_GAME_STATS)

        diffed_stats = copy.deepcopy(NULL_GAME_STATS)

        for item in ["avax_gas", "gas_tus", "chro", "wams"]:
            if item not in user_a_stats and item not in user_b_stats:
                diffed_stats[item] = 0.0
            elif item not in user_a_stats:
                diffed_stats[item] = user_b_stats[item]
            elif item not in user_b_stats:
                diffed_stats[item] = user_a_stats[item]
            else:
                diffed_stats[item] = user_a_stats[item] - user_b_stats[item]

        for item in ["commission_chro", "elemental_stones", "stage_1", "stage_2", "stage_3"]:
            for k, v in user_a_stats[item].items():
                diffed_stats[item][k] = v

            for k, v in user_b_stats[item].items():
                diffed_stats[item][k] = diffed_stats[item].get(k, 0.0) - v

        for item in ["pve_game"]:
            for k, v in user_a_stats[item].items():
                if k == "account_exp":
                    diffed_stats[item][k] = v

            for k, v in user_b_stats[item].items():
                if k == "account_exp":
                    diffed_stats[item][k] = diffed_stats[item].get(k, 0.0) - v

            for k in ["levels_completed", "quests_completed"]:
                new_set = set(user_a_stats[item].get(k, []))
                for b in user_b_stats[item].get(k, []):
                    new_set.add(b)
                diffed_stats[item][k] = list(new_set)

        if verbose:
            logger.print_bold("Subtracting game stats:")
            logger.print_normal(json.dumps(diffed_stats, indent=4))
        return diffed_stats

    def merge_game_stats(
        self, user_a_stats: LifetimeStats, user_b_stats: LifetimeStats, log_dir: str, verbose
    ) -> LifetimeStats:
        diff = deepdiff.DeepDiff(user_a_stats, user_b_stats)
        if not diff:
            return user_a_stats

        merged_stats = copy.deepcopy(NULL_GAME_STATS)

        if verbose:
            logger.print_bold("Merge inputs:")
            logger.print_ok_blue_arrow("A:")
            logger.print_normal(json.dumps(user_a_stats, indent=4))
            logger.print_ok_blue_arrow("B:")
            logger.print_normal(json.dumps(user_b_stats, indent=4))

        for item in ["avax_gas", "gas_tus", "chro", "wams"]:
            merged_stats[item] = merged_stats.get(item, 0.0) + user_a_stats.get(item, 0.0)
            merged_stats[item] = merged_stats.get(item, 0.0) + user_b_stats.get(item, 0.0)

        for item in [
            "commission_chro",
            "elemental_stones",
            "stage_1",
            "stage_2",
            "stage_3",
        ]:
            for k, v in user_a_stats.get(item, {}).items():
                merged_stats[item][k] = merged_stats[item].get(k, 0.0) + v

            for k, v in user_b_stats.get(item, {}).items():
                merged_stats[item][k] = merged_stats[item].get(k, 0.0) + v

        for item in ["pve_game"]:
            for k, v in user_a_stats.get(item, {}).items():
                if isinstance(v, list):
                    merged_set = set(merged_stats[item].get(k, []))
                    for i in v:
                        merged_set.add(i)
                    merged_stats[item][k] = list(merged_set)
                else:
                    merged_stats[item][k] = merged_stats[item].get(k, 0.0) + v

            for k, v in user_b_stats.get(item, {}).items():
                if isinstance(v, list):
                    merged_set = set(merged_stats[item].get(k, []))
                    for i in v:
                        merged_set.add(i)
                    merged_stats[item][k] = list(merged_set)
                else:
                    merged_stats[item][k] = merged_stats[item].get(k, 0.0) + v
        if verbose:
            logger.print_bold("Merging game stats:")
            logger.print_normal(json.dumps(merged_stats, indent=4))
        return merged_stats
