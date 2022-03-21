import typing as T
from eth_typing import Address

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.crabada_web3_client import CrabadaWeb3Client
from crabada.factional_advantage import get_faction_adjusted_battle_point
from crabada.strategies.strategy import Strategy
from crabada.types import CrabForLending, IdleGame, Team, TeamMember
from utils import logger
from utils.general import get_pretty_seconds
from utils.price import Tus


def have_reinforced_loot_at_least_once(crabada_w2: CrabadaWeb2Client, team: Team) -> bool:
    mine = crabada_w2.get_mine(team["game_id"])
    if mine is None:
        return False

    process = mine.get("process", [])
    return "reinforce-attack" in [p["action"] for p in process]


class LootingStrategy(Strategy):
    """
    Base class for looting strategies
    """

    MIN_LOOT_POINT = 60

    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        reinforcing_crabs: T.List[TeamMember],
        max_reinforcement_price_tus: Tus,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            reinforcing_crabs,
            max_reinforcement_price_tus,
        )

    def close(self) -> T.Callable[[int], HexStr]:
        return self.crabada_w3.settle_game

    def reinforce(self) -> T.Callable[[int, int, CrabForLending], HexStr]:
        return self.crabada_w3.reinforce_attack

    def _get_best_mine_reinforcement(
        self, team: Team, mine: IdleGame, use_own_crabs: bool = False
    ) -> T.Optional[TeamMember]:
        reinforcement_crab = None

        logger.print_normal(
            f"Loot[{mine['game_id']}]: using reinforcement strategy of {self.__class__.__name__}"
        )

        attack_battle_point = get_faction_adjusted_battle_point(team, mine, verbose=True)
        if attack_battle_point >= mine["defense_point"]:
            logger.print_normal(
                f"Loot[{mine['game_id']}]: not reinforcing since we've already won!"
            )
            return None

        reinforcement_crab = super()._use_bp_reinforcement(mine, use_own_crabs=use_own_crabs)

        if reinforcement_crab is None:
            logger.print_fail(f"Loot[{mine['game_id']}]: Could not find suitable reinforcement!")
            return None

        if (
            not have_reinforced_loot_at_least_once(self.crabada_w2, team)
            and reinforcement_crab["battle_point"] < self.MIN_LOOT_POINT
        ):
            logger.print_warn(
                f"Loot[{mine['game_id']}]: not reinforcing due to lack of high bp crabs"
            )
            return None

        return reinforcement_crab


class PreferOtherMpCrabs(LootingStrategy):
    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        reinforcing_crabs: T.List[TeamMember],
        max_reinforcement_price_tus: Tus,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            reinforcing_crabs,
            max_reinforcement_price_tus,
        )

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame(), reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        self.reinforcement_search_backoff = reinforcement_search_backoff
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=False)

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        return True


class PreferOwnMpCrabs(LootingStrategy):
    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        reinforcing_crabs: T.List[TeamMember],
        max_reinforcement_price_tus: Tus,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            reinforcing_crabs,
            max_reinforcement_price_tus,
        )

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame(), reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        self.reinforcement_search_backoff = reinforcement_search_backoff
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=True)

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        return True


class DelayReinforcementStrategy(LootingStrategy):
    MAX_TIME_REMAINING_DELTA = 60.0 * 3
    DELAY_BEFORE_REINFORCING = 60.0 * 19

    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        reinforcing_crabs: T.List[TeamMember],
        max_reinforcement_price_tus: Tus,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            reinforcing_crabs,
            max_reinforcement_price_tus,
        )

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        time_remaining = self.crabada_w2.get_remaining_time_for_action(mine)
        if time_remaining < self.MAX_TIME_REMAINING_DELTA:
            return True

        time_since_last_action = self.crabada_w2.get_time_since_last_action(mine)
        if time_since_last_action > self.DELAY_BEFORE_REINFORCING:
            return True

        time_till_action_pretty = get_pretty_seconds(
            int(self.DELAY_BEFORE_REINFORCING - time_since_last_action)
        )
        logger.print_warn(
            f"Loot[{mine['game_id']}]:Not reinforcing for {time_till_action_pretty} due to delay strategy"
        )
        return False


class PreferOtherMpCrabsAndDelayReinforcement(DelayReinforcementStrategy):
    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        reinforcing_crabs: T.List[TeamMember],
        max_reinforcement_price_tus: Tus,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            reinforcing_crabs,
            max_reinforcement_price_tus,
        )

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame(), reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        self.reinforcement_search_backoff = reinforcement_search_backoff
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=False)

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        return super().should_reinforce(mine)


class PreferOwnMpCrabsAndDelayReinforcement(DelayReinforcementStrategy):
    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        reinforcing_crabs: T.List[TeamMember],
        max_reinforcement_price_tus: Tus,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            reinforcing_crabs,
            max_reinforcement_price_tus,
        )

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame(), reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        self.reinforcement_search_backoff = reinforcement_search_backoff
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=True)

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        return super().should_reinforce(mine)
