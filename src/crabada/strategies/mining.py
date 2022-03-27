import typing as T
from eth_typing import Address
from eth_typing.encoding import HexStr
from web3.types import Wei

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.crabada_web3_client import CrabadaWeb3Client
from crabada.factional_advantage import get_faction_adjusted_battle_point
from crabada.strategies.strategy import Strategy
from crabada.types import CrabForLending, IdleGame, Team, TeamMember
from utils import logger
from utils.general import get_pretty_seconds
from utils.price import Tus


class MiningStrategy(Strategy):
    """
    Base class for mining strategies
    """

    MAX_BP_DELTA = 3
    MIN_MINE_POINT = 66

    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        config: UserConfig,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            config,
        )

    def start(self, team_id: int) -> T.Any:
        tx_hash = self.crabada_w3.start_game(team_id)
        return self.crabada_w3.get_transaction_receipt(tx_hash)

    def close(self, game_id: int) -> T.Any:
        logger.print_normal(f"Mine[{game_id}]: Closing game")
        tx_hash = self.crabada_w3.close_game(game_id)
        return self.crabada_w3.get_transaction_receipt(tx_hash)

    def reinforce(self, game_id: int, crabada_id: int, borrow_price: Wei) -> T.Any:
        logger.print_normal(f"Mine[{game_id}]: reinforcing")
        tx_hash = self.crabada_w3.reinforce_defense(game_id, crabada_id, borrow_price)
        return self.crabada_w3.get_transaction_receipt(tx_hash)

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        return self.crabada_w2.mine_needs_reinforcement(mine)

    def _have_reinforced_at_least_once(self, mine: IdleGame) -> bool:
        return self.crabada_w2.get_num_mine_reinforcements(mine) > 1

    def _get_best_mine_reinforcement(
        self, team: Team, mine: IdleGame, use_own_crabs: bool = False
    ) -> T.Optional[TeamMember]:
        reinforcement_crab = None

        logger.print_normal(
            f"Mine[{mine['game_id']}]: using reinforcement strategy of {self.__class__.__name__}"
        )

        defense_battle_point = get_faction_adjusted_battle_point(
            mine, is_looting=False, verbose=True
        )
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
            not self._have_reinforced_at_least_once(mine)
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
        crabada_w3_client: CrabadaWeb3Client,
        config: UserConfig,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            config,
        )

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame, reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        self.reinforcement_search_backoff = reinforcement_search_backoff
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=False)


class PreferOwnMpCrabs(MiningStrategy):
    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        config: UserConfig,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            config,
        )

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame, reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        self.reinforcement_search_backoff = reinforcement_search_backoff
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=True)


class ScatteredReinforcement(MiningStrategy):
    MIN_TIME_BETWEEN_MINES = 60.0 * 30.5

    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        config: UserConfig,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            config,
        )

    def should_start(self, team: Team) -> bool:
        mine_group = self.config["mining_teams"].get(team["team_id"], -1)

        if mine_group == -1:
            return True

        mines = []
        for open_mine in self.crabada_w2.list_my_open_mines(user_address):
            group = self.config["mining_teams"].get(open_mine["team_id"], -1)
            if group == mine_group:
                mines.append(open_mine)

        if not mines:
            return True

        now = time.time()
        last_mine_start = 0
        for mine in mines:
            last_mine_start = max(last_mine_start, mine.get("start_time", now))

        if now - last_mine_start > self.MIN_TIME_BETWEEN_MINES:
            return True

        time_before_start_formatted = get_pretty_seconds(
            int(last_mine_start + self.MIN_TIME_BETWEEN_MINES - now)
        )
        logger.print_normal(
            f"Waiting to start mine for {team['team_id']} in {time_before_start_formatted}"
        )
        return False

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame, reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        self.reinforcement_search_backoff = reinforcement_search_backoff
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=True)


class DelayReinforcementStrategy(MiningStrategy):
    MAX_TIME_REMAINING_DELTA = 60.0 * 3
    DELAY_BEFORE_REINFORCING = 60.0 * 19

    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        config: UserConfig,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            config,
        )

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        if not self.crabada_w2.mine_needs_reinforcement(mine):
            return False

        time_remaining = self.crabada_w2.get_remaining_time_for_action(mine)
        if time_remaining < self.MAX_TIME_REMAINING_DELTA:
            return True

        if super()._have_reinforced_at_least_once(mine):
            return True

        time_since_last_action = self.crabada_w2.get_time_since_last_action(mine)
        if time_since_last_action > self.DELAY_BEFORE_REINFORCING:
            return True

        time_till_action_pretty = get_pretty_seconds(
            int(self.DELAY_BEFORE_REINFORCING - time_since_last_action)
        )
        logger.print_warn(
            f"Mine[{mine['game_id']}]:Not reinforcing for {time_till_action_pretty} due to delay strategy"
        )
        return False


class PreferOtherMpCrabsAndDelayReinforcement(DelayReinforcementStrategy):
    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        config: UserConfig,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            config,
        )

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame, reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        self.reinforcement_search_backoff = reinforcement_search_backoff
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=False)


class PreferOwnMpCrabsAndDelayReinforcement(DelayReinforcementStrategy):
    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        config: UserConfig,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            config,
        )

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame, reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        self.reinforcement_search_backoff = reinforcement_search_backoff
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=True)
