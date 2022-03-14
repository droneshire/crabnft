import typing as T
from eth_typing import Address

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.factional_advantage import get_faction_adjusted_battle_point
from crabada.strategies.reinforcement import ReinforcementStrategy
from crabada.types import IdleGame, Team, TeamMember
from utils import logger
from utils.price import Tus


def have_reinforced_loot_at_least_once(crabada_w2: CrabadaWeb2Client, team: Team) -> bool:
    mine = crabada_w2.get_mine(team["game_id"])
    if mine is None:
        return False

    process = mine["process"]
    return "reinforce-defense" in [p["action"] for p in process]


class LootingStrategy(ReinforcementStrategy):
    """
    Base class for looting strategies
    """

    MAX_BP_DELTA = 3
    MIN_MINE_POINT = 70

    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        reinforcing_crabs: T.List[TeamMember],
        max_reinforcement_price_tus: Tus,
    ) -> None:
        super().__init__(address, crabada_w2_client, reinforcing_crabs, max_reinforcement_price_tus)

    def get_reinforcement_crab(self, team: Team, mine: IdleGame()) -> T.Optional[TeamMember]:
        raise NotImplementedError

    def _get_best_mine_reinforcement(
        self, team: Team, mine: IdleGame, use_own_crabs: bool = False
    ) -> T.Optional[TeamMember]:
        reinforcement_crab = None

        defense_battle_point = get_faction_adjusted_battle_point(team, mine, verbose=True)
        if defense_battle_point >= mine["attack_point"]:
            logger.print_normal(
                f"Mine[{mine['game_id']}]: not reinforcing since we've already won!"
            )
            return None

        if mine["attack_point"] - defense_battle_point < self.MAX_BP_DELTA:
            reinforcement_crab = super()._use_bp_reinforcement(mine, use_own_crabs=use_own_crabs)
        else:
            reinforcement_crab = super()._use_mp_reinforcement(mine, use_own_crabs=use_own_crabs)

        if reinforcement_crab is None:
            logger.print_fail(f"Mine[{mine['game_id']}]: Could not find suitable reinforcement!")
            return None

        if (
            not have_reinforced_mine_at_least_once(self.crabada_w2, team)
            and reinforcement_crab["mine_point"] < self.MIN_MINE_POINT
        ):
            logger.print_warn(
                f"Mine[{mine['game_id']}]: not reinforcing due to lack of high mp crabs"
            )
            return None

        return reinforcement_crab


class PreferOtherMpCrabs(MiningStrategy):
    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        reinforcing_crabs: T.List[TeamMember],
        max_reinforcement_price_tus: Tus,
    ) -> None:
        super().__init__(address, crabada_w2_client, reinforcing_crabs, max_reinforcement_price_tus)

    def get_reinforcement_crab(self, team: Team, mine: IdleGame()) -> T.Optional[TeamMember]:
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=False)


class PreferOwnMpCrabs(MiningStrategy):
    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        reinforcing_crabs: T.List[TeamMember],
        max_reinforcement_price_tus: Tus,
    ) -> None:
        super().__init__(address, crabada_w2_client, reinforcing_crabs, max_reinforcement_price_tus)

    def get_reinforcement_crab(self, team: Team, mine: IdleGame()) -> T.Optional[TeamMember]:
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=True)
