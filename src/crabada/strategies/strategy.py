import math
import time
import typing as T
from eth_typing import Address
from web3.types import Wei

from crabada.config_manager import ConfigManager
from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.crabada_web3_client import CrabadaWeb3Client
from crabada.profitability import CrabadaTransaction, GameStage, REWARDS_TUS, Result, Scenarios
from crabada.types import IdleGame, Team, TeamMember
from utils import logger
from utils.price import Tus, wei_to_cra_raw, wei_to_tus_raw


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
        config_mgr: ConfigManager,
    ) -> None:
        self.config_mgr = config_mgr
        self.address = address
        self.crabada_w2 = crabada_w2_client
        self.crabada_w3 = crabada_w3_client

        self.reinforcement_search_backoff = 0
        self.time_since_last_attack = None  # T.Optional[float]

        self.reinforce_time_cache = {
            c: 0.0
            for c in self.config_mgr.config["game_specific_configs"]["reinforcing_crabs"].keys()
        }

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame, reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        raise NotImplementedError

    def should_start(self, team: Team) -> bool:
        return True

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        raise NotImplementedError

    def start(self, team_id: int) -> CrabadaTransaction:
        raise NotImplementedError

    def close(self, game_id: int) -> CrabadaTransaction:
        raise NotImplementedError

    def reinforce(self, game_id: int, crabada_id: int, borrow_price: Wei) -> CrabadaTransaction:
        raise NotImplementedError

    def get_backoff_margin(self) -> int:
        return 0

    def get_gas_margin(self, game_stage: GameStage, mine: T.Optional[IdleGame] = None) -> int:
        if game_stage == GameStage.START:
            return 10
        elif game_stage == GameStage.CLOSE:
            return 10
        elif game_stage == GameStage.REINFORCE:
            return 25 if self.have_reinforced_at_least_once(mine) else 0
        else:
            return 0

    def have_reinforced_at_least_once(self, mine: IdleGame) -> bool:
        raise NotImplementedError

    def _use_bp_reinforcement(
        self, mine: IdleGame, group_id: int, use_own_crabs: bool = False
    ) -> T.Optional[TeamMember]:
        reinforcement_crab = None
        allowed_reinforcing_crabs = [
            c
            for c, v in self.config_mgr.config["game_specific_configs"]["reinforcing_crabs"].items()
            if v == group_id
        ]

        now = time.time()
        available_reinforcing_crabs = []

        for crab in allowed_reinforcing_crabs:
            if crab not in self.reinforce_time_cache:
                self.reinforce_time_cache[crab] = 0.0
                available_reinforcing_crabs.append(crab)
            elif now - self.reinforce_time_cache[crab] > self.REINFORCEMENT_REUSE_WINDOW:
                available_reinforcing_crabs.append(crab)

        logger.print_normal(f"Mine[{mine['game_id']}]: using highest bp")
        if self.config_mgr.config["game_specific_configs"]["reinforcing_crabs"]:
            logger.print_normal(
                f"Total reinforcements: {self.config_mgr.config['reinforcing_crabs'].keys()}"
            )

        if use_own_crabs:
            allowed_crabs_str = ", ".join([str(c) for c in available_reinforcing_crabs])
            logger.print_normal(
                f"Checking from approved reinforcements {allowed_crabs_str} from group {group_id}"
            )
            reinforcement_crab = self.crabada_w2.get_my_best_bp_crab_for_lending(
                self.address, available_reinforcing_crabs
            )
            logger.print_normal(f"Own reinforcement result: {reinforcement_crab}")

        if (
            reinforcement_crab is not None
            and reinforcement_crab["crabada_id"] in available_reinforcing_crabs
            and now - self.reinforce_time_cache[reinforcement_crab["crabada_id"]]
            > self.REINFORCEMENT_REUSE_WINDOW
        ):
            self.reinforce_time_cache[reinforcement_crab["crabada_id"]] = now
            logger.print_bold(f"Mine[{mine['game_id']}]: using our own crab to reinforce!")
        else:
            reinforcement_crab = self.crabada_w2.get_best_high_bp_crab_for_lending(
                mine,
                self.config_mgr.config["game_specific_configs"]["max_reinforcement_price_tus"],
                self.reinforcement_search_backoff,
            )

        return reinforcement_crab

    def _use_mp_reinforcement(
        self, mine: IdleGame, group_id: int, use_own_crabs: bool = False
    ) -> T.Optional[TeamMember]:
        reinforcement_crab = None

        allowed_reinforcing_crabs = [
            c
            for c, v in self.config_mgr.config["game_specific_configs"]["reinforcing_crabs"].items()
            if v == group_id
        ]

        now = time.time()
        available_reinforcing_crabs = []

        for crab in allowed_reinforcing_crabs:
            if crab not in self.reinforce_time_cache:
                self.reinforce_time_cache[crab] = 0.0
                available_reinforcing_crabs.append(crab)
            elif now - self.reinforce_time_cache[crab] > self.REINFORCEMENT_REUSE_WINDOW:
                available_reinforcing_crabs.append(crab)

        logger.print_normal(f"Mine[{mine['game_id']}]: using highest mp")
        if self.config_mgr.config["game_specific_configs"]["reinforcing_crabs"]:
            logger.print_normal(
                f"Total reinforcements: {self.config_mgr.config['reinforcing_crabs'].keys()}"
            )

        if use_own_crabs:
            allowed_crabs_str = ", ".join([str(c) for c in available_reinforcing_crabs])
            logger.print_normal(
                f"Checking from approved reinforcements {allowed_crabs_str} from group {group_id}"
            )
            reinforcement_crab = self.crabada_w2.get_my_best_mp_crab_for_lending(
                self.address, available_reinforcing_crabs
            )
            logger.print_normal(f"Own reinforcement result: {reinforcement_crab}")

        now = time.time()
        if (
            reinforcement_crab is not None
            and reinforcement_crab["crabada_id"] in available_reinforcing_crabs
            and now - self.reinforce_time_cache[reinforcement_crab["crabada_id"]]
            > self.REINFORCEMENT_REUSE_WINDOW
        ):
            self.reinforce_time_cache[reinforcement_crab["crabada_id"]] = now
            logger.print_bold(f"Mine[{mine['game_id']}]: using our own crab to reinforce!")
        else:
            reinforcement_crab = self.crabada_w2.get_best_high_mp_crab_for_lending(
                mine,
                self.config_mgr.config["game_specific_configs"]["max_reinforcement_price_tus"],
                self.reinforcement_search_backoff,
            )

        return reinforcement_crab

    @staticmethod
    def _get_game_result(tus: float) -> Result:
        for reward_type, scenario in REWARDS_TUS.items():
            # auto lose/no reinforce the win == lose, skip these for saying its a win
            if math.isclose(scenario[Result.WIN]["TUS"], scenario[Result.LOSE]["TUS"], abs_tol=1.0):
                continue
            if math.isclose(scenario[Result.WIN]["TUS"], tus, abs_tol=1.0):
                logger.print_normal(f"Detected WIN result for {reward_type}")
                return Result.WIN
        return Result.LOSE
