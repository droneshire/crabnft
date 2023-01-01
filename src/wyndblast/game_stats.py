import copy
import deepdiff
import json
import typing as T

from utils import logger
from utils.game_stats import LifetimeGameStatsLogger
from wyndblast import types


class PveStats(T.TypedDict):
    levels_completed: T.List[str]
    account_exp: int
    unclaimed_chro: float
    claimed_chro: float


class LifetimeStats(T.TypedDict):
    chro: float
    wams: float
    elemental_stones: types.ElementalStones
    stage_1: T.Dict[str, float]
    stage_2: T.Dict[str, float]
    stage_3: T.Dict[str, float]
    commission_chro: T.Dict[str, float]
    avax_gas: float
    pve_game: T.Dict[str, PveStats]


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
    "pve_game": {},
}


class WyndblastLifetimeGameStatsLogger(LifetimeGameStatsLogger):
    def __init__(
        self,
        user: str,
        log_dir: str,
        backup_stats: T.Dict[T.Any, T.Any],
        address: str,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        super().__init__(user, NULL_GAME_STATS, log_dir, backup_stats, dry_run, verbose)

    def delta_game_stats(
        self,
        user_a_stats: LifetimeStats,
        user_b_stats: LifetimeStats,
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
            for address, pve_stat in user_a_stats[item].items():
                diffed_stats[item][address] = {}
                for stat, value in user_a_stats[item][address].items():
                    diffed_stats[item][address][stat] = value

            for address, pve_stat in user_b_stats[item].items():
                for stat, value in user_b_stats[item][address].items():
                    if stat == "levels_completed":
                        levels = user_b_stats[item][address][stat]
                        diffed_stats[item][address][stat] = [
                            b for b in set(levels) if b not in diffed_stats[item][address][stat]
                        ]
                    else:
                        diffed_stats[item][address][stat] -= value

        if self.verbose:
            logger.print_bold("Subtracting game stats:")
            logger.print_normal(json.dumps(diffed_stats, indent=4))
        return diffed_stats

    def merge_game_stats(
        self, user_a_stats: LifetimeStats, user_b_stats: LifetimeStats, log_dir: str
    ) -> LifetimeStats:
        diff = deepdiff.DeepDiff(user_a_stats, user_b_stats)
        if not diff:
            return user_a_stats

        merged_stats = copy.deepcopy(NULL_GAME_STATS)

        if self.verbose:
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
            for address, pve_stat in user_a_stats[item].items():
                merged_stats[item][address] = {}
                for stat, value in user_a_stats[item][address].items():
                    if isinstance(value, list):
                        merged_stats[item][address][stat] = list(set(value))
                    else:
                        merged_stats[item][address][stat] = value

            for address, pve_stat in user_b_stats[item].items():
                if address not in merged_stats[item]:
                    merged_stats[item][address] = {}

                for stat, value in user_b_stats[item][address].items():
                    if isinstance(value, list):
                        if stat not in merged_stats[item][address]:
                            merged_stats[item][address][stat] = []

                        value_set = set(value)
                        merged_set = set(merged_stats[item][address][stat])
                        if merged_set:
                            value_set = value_set.union(merged_set)
                        merged_stats[item][address][stat].extend(list(value_set))
                    else:
                        merged_stats[item][address][stat] = (
                            merged_stats[item][address].get(stat, 0) + value
                        )

        if self.verbose:
            logger.print_bold("Merging game stats:")
            logger.print_normal(json.dumps(merged_stats, indent=4))
        return merged_stats
