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
        use_full_balance: bool,
        verbose: bool = False,
    ):
        self.config = config
        self.verbose = verbose

        self.use_full_balance = use_full_balance

        self.token = token
        self.token_w3 = token_w3

        percent_profit = (
            config["game_specific_configs"][f"percent_{token.lower()}_profit_convert"] / 100.0
        )
        percent_hold = config["game_specific_configs"][f"percent_{token.lower()}_hold"] / 100.0
        percent_levelling = (
            config["game_specific_configs"][f"percent_{token.lower()}_levelling"] / 100.0
        )
        percent_lp = config["game_specific_configs"][f"percent_{token.lower()}_lp"] / 100.0

        self._percents = {
            Category.PROFIT: percent_profit,
            Category.HOLD: percent_hold,
            Category.LEVELLING: percent_levelling,
            Category.LP: percent_lp,
        }
        assert sum(self._percents.values()) <= 1.0, "Percents exceed 100%"

        self._allocations = {
            Category.PROFIT: 0.0,
            Category.HOLD: 0.0,
            Category.LEVELLING: 0.0,
            Category.LP: 0.0,
        }

    @property
    def percents(self, category: Category) -> float:
        return self._percents[category]

    @property
    def allocations(self, category: Category) -> float:
        return self._allocations[category]

    def maybe_update_full_balance(self) -> None:
        if not self.use_full_balance:
            logger.print_warn(
                f"Not updating {self.token} balances since we are not using full balance"
            )
            return

        amount = self.token_w3.get_balance()

        if self.verbose:
            logger.print_normal(f"Updating using full balance of {amount:.2f} {self.token}")

        for category in ALL_CATEGORIES:
            self._add(category, amount)

    def reallocate(self, from_category: Category) -> None:
        if self.verbose:
            logger.print_normal(f"Reallocating {self.token} from {from_category}")

        for category in ALL_CATEGORIES:
            if category == from_category:
                continue
            self._add(category, self._allocations[from_category])

        self.reset(from_category)

    def get_amount(self, category: Category) -> float:
        if self.use_full_balance:
            amount = self.token_w3.get_balance() * self._percents[category]
        else:
            amount = min(
                self.token_w3.get_balance() * self._percents[category], self._allocations[category]
            )

        if self.verbose:
            logger.print_normal(
                f"{self.use_full_balance} Getting {category}: {amount:.2f} {self.token}"
            )
        return amount

    def get_total(self) -> float:
        if self.use_full_balance:
            return self.token_w3.get_balance()

        amount = 0.0
        for category in ALL_CATEGORIES:
            amount += self.get_amount(category)

        if self.verbose:
            logger.print_normal(f"Total available: {amount:.2f} {self.token}")
        return amount

    def set_amount(self, category: Category, amount: float) -> None:
        actual_amount = min(self.token_w3.get_balance(), amount)
        if self.verbose:
            logger.print_normal(
                f"Setting allocation category {category} to {actual_amount:.2f} {self.token}"
            )
        self._allocations[category] = actual_amount

    def reset(self, category: Category) -> None:
        if self.verbose:
            logger.print_normal(f"Reseting {self.token} allocation category: {category}")
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
            logger.print_normal(f"Subtracting {amount:.2f} {self.token} from {category}")

        self._allocations[category] = max(0.0, self._allocations[category] - amount)

    def update_percent(
        self, category: Category, percent: float, to_categories: T.List[Category] = ALL_CATEGORIES
    ) -> None:
        # update category percent and distribute the delta in percent
        # among the rest of the categories
        percent_before = self._percents[category]
        self._percents[category] = percent

        delta_per_category = (percent_before - percent) / (len(self._percents.keys()) - 1)

        if self.verbose:
            logger.print_normal(
                f"Updating {self.token} {category} % from {percent_before * 100.0:.2f} to {percent * 100.0:.2f}%"
            )

        for other_category in to_categories:
            if other_category == category:
                continue
            self._percents[category] += delta_per_category

        assert sum(self._percents.values()) <= 1.0, "Percents exceed 100%"

    def is_hold_only(self) -> bool:
        total = 0.0
        for category in ALL_CATEGORIES:
            if category == Category.HOLD:
                continue
            total += self._percents[category]
        return math.isclose(total, 0.0, abs_tol=0.1)

    def _add(self, category: Category, amount: float) -> None:
        category_amount = max(0.0, self._percents[category] * amount)
        if self.verbose:
            logger.print_normal(
                f" {self.token} allocator: Adding {(self._percents[category] * 100.0):.2f}% of {amount:.2f} -> {category_amount:.2f} to {category}"
            )
        self._allocations[category] += category_amount


class PpieAllocator(TokenAllocator):
    def __init__(
        self,
        token_w3: AvalancheCWeb3Client,
        config: UserConfig,
        use_full_balance: bool,
        verbose: bool = True,
    ):
        super().__init__(Tokens.PPIE, token_w3, config, use_full_balance, verbose)


class PotnAllocator(TokenAllocator):
    def __init__(
        self,
        token_w3: AvalancheCWeb3Client,
        config: UserConfig,
        use_full_balance: bool,
        verbose: bool = True,
    ):
        super().__init__(Tokens.POTN, token_w3, config, use_full_balance, verbose)
