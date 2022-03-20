import typing as T
from eth_typing import Address

from crabada.types import CrabForLending, IdleGame, Team, TeamMember
from crabada.crabada_web2_client import CrabadaWeb2Client
from utils import logger
from utils.price import Tus


class ReinforcementStrategy:
    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_methods: T.Dict[str, T.Callable],
        reinforcing_crabs: T.List[TeamMember],
        max_reinforcement_price_tus: Tus,
    ) -> None:
        self.reinforcing_crabs = reinforcing_crabs
        self.max_reinforcement_price_tus = max_reinforcement_price_tus
        self.address = address
        self.crabada_w2 = crabada_w2_client
        self.crabada_w3_methods = crabada_w3_methods

        self.reinforcement_search_backoff = 0
        self.time_since_last_attack = None  # T.Optional[float]

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame, reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        raise NotImplementedError

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        raise NotImplementedError

    def _use_bp_reinforcement(
        self, mine: IdleGame, use_own_crabs: bool = False
    ) -> T.Optional[TeamMember]:
        reinforcement_crab = None
        allowed_reinforcing_crabs = [c["crabada_id"] for c in self.reinforcing_crabs]

        logger.print_normal(f"Mine[{mine['game_id']}]: using highest bp")

        if use_own_crabs:
            reinforcement_crab = self.crabada_w2.get_my_best_bp_crab_for_lending(self.address)

        if (
            reinforcement_crab is not None
            and reinforcement_crab["crabada_id"] in allowed_reinforcing_crabs
        ):
            logger.print_bold(f"Mine[{mine['game_id']}]: using our own crab to reinforce!")
        else:
            reinforcement_crab = self.crabada_w2.get_best_high_bp_crab_for_lending(
                self.max_reinforcement_price_tus, self.reinforcement_search_backoff
            )

        return reinforcement_crab

    def _use_mp_reinforcement(
        self, mine: IdleGame, use_own_crabs: bool = False
    ) -> T.Optional[TeamMember]:
        reinforcement_crab = None
        allowed_reinforcing_crabs = [c["crabada_id"] for c in self.reinforcing_crabs]

        logger.print_normal(f"Mine[{mine['game_id']}]: using highest mp")

        if use_own_crabs:
            reinforcement_crab = self.crabada_w2.get_my_best_mp_crab_for_lending(self.address)

        if (
            reinforcement_crab is not None
            and reinforcement_crab["crabada_id"] in allowed_reinforcing_crabs
        ):
            logger.print_bold(f"Mine[{mine['game_id']}]: using our own crab to reinforce!")
        else:
            reinforcement_crab = self.crabada_w2.get_best_high_mp_crab_for_lending(
                self.max_reinforcement_price_tus, self.reinforcement_search_backoff
            )

        return reinforcement_crab
