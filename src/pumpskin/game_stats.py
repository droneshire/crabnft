import copy
import deepdiff
import json
import typing as T

from utils import logger
from utils.game_stats import LifetimeGameStatsLogger
from pumpskin.allocator import TokenAllocator
from pumpskin.types import Category, Tokens, ALL_CATEGORIES


class LifetimeStats(T.TypedDict):
    potn: float
    ppie: float
    levels: int
    commission_ppie: T.Dict[str, float]
    avax_gas: float
    avax_profits: float
    ppie_lp_tokens: float
    potn_lp_tokens: float
    allocations: T.Dict[str, T.Dict[str, float]]


NULL_GAME_STATS = {
    "potn": 0.0,
    "ppie": 0.0,
    "levels": 0,
    "commission_ppie": {},
    "avax_gas": 0.0,
    "avax_profits": 0.0,
    "ppie_lp_tokens": 0.0,
    "potn_lp_tokens": 0.0,
    "allocations": {
        Tokens.PPIE: {
            Category.HOLD: 0.0,
            Category.LEVELLING: 0.0,
            Category.LP: 0.0,
            Category.PROFIT: 0.0,
        },
        Tokens.POTN: {
            Category.HOLD: 0.0,
            Category.LEVELLING: 0.0,
            Category.LP: 0.0,
            Category.PROFIT: 0.0,
        },
    },
}


class PumpskinLifetimeGameStatsLogger(LifetimeGameStatsLogger):
    def __init__(
        self,
        user: str,
        log_dir: str,
        backup_stats: T.Dict[T.Any, T.Any],
        allocator: TokenAllocator,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        super().__init__(
            user, NULL_GAME_STATS, log_dir, backup_stats, dry_run, verbose
        )
        self.allocator = allocator
        self._migrate_new_stats()

    def _migrate_new_stats(self) -> None:
        for k in ["ppie_lp_tokens", "ppie_lp_tokens", "avax_profits"]:
            if k not in self.lifetime_stats:
                self.lifetime_stats[k] = NULL_GAME_STATS[k]

        if "amounts_available" in self.lifetime_stats:
            for token in [Tokens.PPIE, Tokens.POTN]:
                self.allocator[token].maybe_add(
                    self.lifetime_stats["amounts_available"][token.lower()]
                )
            del self.lifetime_stats["amounts_available"]

        if "allocations" in self.lifetime_stats:
            for token in [Tokens.PPIE, Tokens.POTN]:
                for category in ALL_CATEGORIES:
                    self.allocator[token].set_amount(
                        category,
                        self.lifetime_stats["allocations"][token][category],
                    )
        else:
            self.lifetime_stats["allocations"] = NULL_GAME_STATS["allocations"]

        self.last_lifetime_stats = copy.deepcopy(self.lifetime_stats)

    def save_allocations_to_stats(self) -> None:
        for token in [Tokens.PPIE, Tokens.POTN]:
            for category in ALL_CATEGORIES:
                self.lifetime_stats["allocations"][token][
                    category
                ] = self.allocator[token].get_amount(category)

    def delta_game_stats(
        self,
        user_a_stats: LifetimeStats,
        user_b_stats: LifetimeStats,
    ) -> LifetimeStats:
        diff = deepdiff.DeepDiff(user_a_stats, user_b_stats)
        if not diff:
            return copy.deepcopy(NULL_GAME_STATS)

        diffed_stats = copy.deepcopy(NULL_GAME_STATS)

        for item in [
            "avax_gas",
            "ppie",
            "potn",
            "levels",
            "avax_profits",
            "potn_lp_tokens",
            "ppie_lp_tokens",
        ]:
            if item not in user_a_stats and item not in user_b_stats:
                diffed_stats[item] = 0.0
            elif item not in user_a_stats:
                diffed_stats[item] = user_b_stats[item]
            elif item not in user_b_stats:
                diffed_stats[item] = user_a_stats[item]
            else:
                diffed_stats[item] = user_a_stats[item] - user_b_stats[item]

        for item in ["commission_ppie"]:
            for k, v in user_a_stats[item].items():
                diffed_stats[item][k] = v

            for k, v in user_b_stats[item].items():
                diffed_stats[item][k] = diffed_stats[item].get(k, 0.0) - v

        for item in ["allocations"]:
            for token in [Tokens.POTN, Tokens.PPIE]:
                for k, v in user_a_stats[item][token].items():
                    diffed_stats[item][token][k] = v

                for k, v in user_b_stats[item][token].items():
                    diffed_stats[item][token][k] = (
                        diffed_stats[item][token].get(k, 0.0) - v
                    )
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

        for item in [
            "avax_gas",
            "ppie",
            "potn",
            "levels",
            "avax_profits",
            "potn_lp_tokens",
            "ppie_lp_tokens",
        ]:
            merged_stats[item] = merged_stats.get(item, 0.0) + user_a_stats.get(
                item, 0.0
            )
            merged_stats[item] = merged_stats.get(item, 0.0) + user_b_stats.get(
                item, 0.0
            )

        for item in ["commission_ppie"]:
            for k, v in user_a_stats.get(item, {}).items():
                merged_stats[item][k] = merged_stats[item].get(k, 0.0) + v

            for k, v in user_b_stats.get(item, {}).items():
                merged_stats[item][k] = merged_stats[item].get(k, 0.0) + v

        for item in ["allocations"]:
            for token in [Tokens.POTN, Tokens.PPIE]:
                for k, v in user_a_stats.get(item, {}).get(token, {}).items():
                    merged_stats[item][token][k] = (
                        merged_stats[item][token].get(k, 0.0) + v
                    )
                for k, v in user_b_stats.get(item, {}).get(token, {}).items():
                    merged_stats[item][token][k] = (
                        merged_stats[item][token].get(k, 0.0) + v
                    )

        if self.verbose:
            logger.print_bold("Merging game stats:")
            logger.print_normal(json.dumps(merged_stats, indent=4))
        return merged_stats
