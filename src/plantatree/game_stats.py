import copy
import deepdiff
import json
import typing as T

from utils import logger
from utils.game_stats import LifetimeGameStatsLogger


class LifetimeStats(T.TypedDict):
    harvests: int
    replants: int
    avax_harvested: float
    commission_avax: T.Dict[str, float]
    avax_gas: float


NULL_GAME_STATS = {
    "harvests": 0,
    "replants": 0,
    "avax_harvested": 0.0,
    "commission_avax": {},
    "avax_gas": 0.0,
}


class PatLifetimeGameStatsLogger(LifetimeGameStatsLogger):
    def __init__(
        self,
        user: str,
        log_dir: str,
        backup_stats: T.Dict[T.Any, T.Any],
        dry_run: bool = False,
        verbose: bool = False,
    ):
        super().__init__(
            user, NULL_GAME_STATS, log_dir, backup_stats, dry_run, verbose
        )

    def delta_game_stats(
        self,
        user_a_stats: LifetimeStats,
        user_b_stats: LifetimeStats,
    ) -> LifetimeStats:
        diff = deepdiff.DeepDiff(user_a_stats, user_b_stats)
        if not diff:
            return copy.deepcopy(NULL_GAME_STATS)

        diffed_stats = copy.deepcopy(NULL_GAME_STATS)

        for item in ["avax_gas", "harvests", "replants", "avax_harvested"]:
            if item not in user_a_stats and item not in user_b_stats:
                diffed_stats[item] = 0.0
            elif item not in user_a_stats:
                diffed_stats[item] = user_b_stats[item]
            elif item not in user_b_stats:
                diffed_stats[item] = user_a_stats[item]
            else:
                diffed_stats[item] = user_a_stats[item] - user_b_stats[item]

        for item in ["commission_avax"]:
            for k, v in user_a_stats[item].items():
                diffed_stats[item][k] = v

            for k, v in user_b_stats[item].items():
                diffed_stats[item][k] = diffed_stats[item].get(k, 0.0) - v

        if self.verbose:
            logger.print_bold("Subtracting game stats:")
            logger.print_normal(json.dumps(diffed_stats, indent=4))
        return diffed_stats

    def merge_game_stats(
        self,
        user_a_stats: LifetimeStats,
        user_b_stats: LifetimeStats,
        log_dir: str,
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

        for item in ["avax_gas", "harvests", "replants", "avax_harvested"]:
            merged_stats[item] = merged_stats.get(item, 0.0) + user_a_stats.get(
                item, 0.0
            )
            merged_stats[item] = merged_stats.get(item, 0.0) + user_b_stats.get(
                item, 0.0
            )

        for item in ["commission_avax"]:
            for k, v in user_a_stats.get(item, {}).items():
                merged_stats[item][k] = merged_stats[item].get(k, 0.0) + v

            for k, v in user_b_stats.get(item, {}).items():
                merged_stats[item][k] = merged_stats[item].get(k, 0.0) + v

        if self.verbose:
            logger.print_bold("Merging game stats:")
            logger.print_normal(json.dumps(merged_stats, indent=4))
        return merged_stats
