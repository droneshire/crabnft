import math
import typing as T

from utils import logger
from utils.config_types import UserConfig
from pumpskin.types import ALL_CATEGORIES, Category, Tokens
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


class TokenAllocator:
    def __init__(
        self,
        token: Tokens,
        token_w3: AvalancheCWeb3Client,
        config: UserConfig,
        verbose: bool = False,
    ):
        self.config = config
        self.verbose = verbose

        self.use_full_balance = config["game_specific_configs"]["use_full_available_balances"]

        self.token_w3 = token_w3

        percent_profit = (
            config["game_specific_configs"][f"percent_{token.lower()}_profit_convert"] / 100.0
        )
        percent_hold = config["game_specific_configs"][f"percent_{token.lower()}_hold"] / 100.0
        percent_levelling = (
            config["game_specific_configs"][f"percent_{token.lower()}_levelling"] / 100.0
        )
        percent_lp = config["game_specific_configs"][f"percent_{token.lower()}_lp"] / 100.0

        self.percents = {
            Category.PROFIT: percent_profit,
            Category.HOLD: percent_hold,
            Category.LEVELLING: percent_levelling,
            Category.LP: percent_lp,
        }
        assert sum(self.percents.values()) <= 1.0, "Percents exceed 100%"

        self.allocations = {
            Category.PROFIT: 0.0,
            Category.HOLD: 0.0,
            Category.LEVELLING: 0.0,
            Category.LP: 0.0,
        }

    def maybe_update_full_balance(self) -> None:
        if not self.use_full_balance:
            logger.print_warn(f"Not updating balances since we are using full balance")
            return

        if self.verbose:
            logger.print_normal(f"Reallocating from {category}")

        amount = self.token_w3.get_balance()
        for category in ALL_CATEGORIES:
            self._add(category, amount)

    def reallocate(self, from_category: Category) -> None:
        if self.verbose:
            logger.print_normal(f"Reallocating from {category}")

        for category in ALL_CATEGORIES:
            if category == from_category:
                continue
            self._add(category, self.allocations[from_category])

        self.reset(from_category)

    def get_amount(self, category: Category) -> float:
        if self.use_full_balance:
            amount = self.token_w3.get_balance()
        else:
            amount = min(self.token_w3.get_balance(), self.allocations[category])

        if self.verbose:
            logger.print_normal(f"Getting {category}: {amount:.2f}")
        return amount

    def get_total(self) -> float:
        amount = 0.0
        for category in ALL_CATEGORIES:
            amount += self.get_amount(category)

        if self.verbose:
            logger.print_normal(f"Total available: {amount:.2f}")
        return amount

    def set_amount(self, category: Category, amount: float) -> None:
        if self.verbose:
            logger.print_normal(f"Setting allocatoin category {category} to {amount:.2f}")
        self.allocations[category] = amount

    def reset(self, category: Category) -> None:
        if self.verbose:
            logger.print_normal(f"Reseting allocation category: {category}")
        self.set_amount(category, 0.0)

    def maybe_add(self, amount: float) -> None:
        if self.use_full_balance:
            if self.verbose:
                logger.print_normal(f"Tried to add but we're using full balance so ignoring")
            return

        for category in ALL_CATEGORIES:
            self._add(category, amount)

    def maybe_subtract(self, amount: float, category: Category) -> None:
        if self.use_full_balance:
            if self.verbose:
                logger.print_normal(f"Tried to subtract but we're using full balance so ignoring")
            return

        if self.verbose:
            logger.print_normal(f"Subtracting {amount:.2f} from {category}")

        self.allocations[category] = max(0.0, self.allocations[category] - amount)

    def update_percent(
        self, category: Category, percent: float, to_categories: T.List[Category] = ALL_CATEGORIES
    ) -> None:
        # update category percent and distribute the delta in percent
        # among the rest of the categories
        percent_before = self.percents[category]
        self.percents[category] = percent

        delta_per_category = (percent_before - percent) / (len(self.percents.keys()) - 1)

        if self.verbose:
            logger.print_normal(
                f"Updating {category} % from {percent_before * 100.0:.2f} to {percent * 100.0:.2f}%"
            )

        for other_category in to_categories:
            if other_category == category:
                continue
            self.percents[category] += delta_per_category

        assert sum(self.percents.values()) <= 1.0, "Percents exceed 100%"

    def _add(self, category: Category, amount: float) -> None:
        category_amount = self.percents[category] * amount
        if self.verbose:
            logger.print_normal(f"Adding {category_amount:.2f} to {category}")
        self.allocations[category] += category_amount


class PpieAllocator(TokenAllocator):
    def __init__(self, token_w3: AvalancheCWeb3Client, config: UserConfig, verbose: bool = False):
        super().__init__(Tokens.PPIE, token_w3, config, verbose)


class PotnAllocator(TokenAllocator):
    def __init__(self, token_w3: AvalancheCWeb3Client, config: UserConfig, verbose: bool = False):
        super().__init__(Tokens.POTN, token_w3, config, verbose)
