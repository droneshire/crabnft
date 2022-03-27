import time
import typing as T
from eth_typing import Address
from web3.types import Wei

from crabada.types import IdleGame, Team, TeamMember
from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.crabada_web3_client import CrabadaWeb3Client
from utils import logger
from utils.config_types import UserConfig
from utils.price import Tus


class Strategy:
    # time window to make sure we don't attempt to reuse crabs
    # before the api updates. keep it small in case we fail to actually
    # use as reinforcement due to blockchain failure
    REINFORCEMENT_REUSE_WINDOW = 20.0

    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        config: UserConfig,
    ) -> None:
        self.config = config
        self.address = address
        self.crabada_w2 = crabada_w2_client
        self.crabada_w3 = crabada_w3_client

        self.max_reinforcement_price_tus = self.config["max_reinforcement_price_tus"]
        self.reinforcing_crabs = self.config["reinforcing_crabs"]
        self.reinforcement_search_backoff = 0
        self.time_since_last_attack = None  # T.Optional[float]

        self.reinforce_time_cache = {c: time.time() for c in reinforcing_crabs.keys()}

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame, reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        raise NotImplementedError

    def should_start(self, team: Team) -> bool:
        return True

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        raise NotImplementedError

    def start(self, team_id: int) -> T.Any:
        raise NotImplementedError

    def close(self, game_id: int) -> T.Any:
        raise NotImplementedError

    def reinforce(self, game_id: int, crabada_id: int, borrow_price: Wei) -> T.Any:
        raise NotImplementedError

    def _use_bp_reinforcement(
        self, mine: IdleGame, use_own_crabs: bool = False
    ) -> T.Optional[TeamMember]:
        reinforcement_crab = None
        allowed_reinforcing_crabs = self.reinforcing_crabs.keys()

        logger.print_normal(f"Mine[{mine['game_id']}]: using highest bp")

        if use_own_crabs:
            allowed_crabs_str = ", ".join([str(c) for c in allowed_reinforcing_crabs])
            logger.print_normal(f"Checking from approved reinforcements {allowed_crabs_str}")
            reinforcement_crab = self.crabada_w2.get_my_best_bp_crab_for_lending(self.address)

        now = time.time()
        if (
            reinforcement_crab is not None
            and reinforcement_crab["crabada_id"] in allowed_reinforcing_crabs
            and now - self.reinforce_time_cache[reinforcement_crab["crabada_id"]]
            > self.REINFORCEMENT_REUSE_WINDOW
        ):
            self.reinforce_time_cache[reinforcement_crab["crabada_id"]] = now
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
        allowed_reinforcing_crabs = self.reinforcing_crabs.keys()

        logger.print_normal(f"Mine[{mine['game_id']}]: using highest mp")

        if use_own_crabs:
            allowed_crabs_str = ", ".join([str(c) for c in allowed_reinforcing_crabs])
            logger.print_normal(f"Checking from approved reinforcements {allowed_crabs_str}")
            reinforcement_crab = self.crabada_w2.get_my_best_mp_crab_for_lending(self.address)

        now = time.time()
        if (
            reinforcement_crab is not None
            and reinforcement_crab["crabada_id"] in allowed_reinforcing_crabs
            and now - self.reinforce_time_cache[reinforcement_crab["crabada_id"]]
            > self.REINFORCEMENT_REUSE_WINDOW
        ):
            self.reinforce_time_cache[reinforcement_crab["crabada_id"]] = now
            logger.print_bold(f"Mine[{mine['game_id']}]: using our own crab to reinforce!")
        else:
            reinforcement_crab = self.crabada_w2.get_best_high_mp_crab_for_lending(
                self.max_reinforcement_price_tus, self.reinforcement_search_backoff
            )

        return reinforcement_crab
