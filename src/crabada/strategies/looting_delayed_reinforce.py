import typing as T
from eth_typing import Address

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.crabada_web3_client import CrabadaWeb3Client
from crabada.strategies.looting import LootingStrategy
from crabada.types import IdleGame, Team, TeamMember
from utils import logger
from crabada.config_manager import ConfigManager
from utils.general import get_pretty_seconds


class LootingDelayReinforcementStrategy(LootingStrategy):
    MAX_TIME_REMAINING_DELTA = 60.0 * 3
    DELAY_BEFORE_REINFORCING = 60.0 * 3

    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        config_mgr: ConfigManager,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            config_mgr,
        )

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        if not super().should_reinforce(mine):
            return False

        if self.crabada_w2.loot_past_settle_time(mine):
            return True

        time_remaining = self.crabada_w2.get_remaining_time_for_action(mine)
        if time_remaining < self.MAX_TIME_REMAINING_DELTA:
            return True

        if super().have_reinforced_at_least_once(mine):
            return True

        time_since_last_action = self.crabada_w2.get_time_since_last_action(mine)
        if time_since_last_action > self.DELAY_BEFORE_REINFORCING:
            return True

        time_till_action = self.DELAY_BEFORE_REINFORCING - time_since_last_action
        time_till_end_loot = self.crabada_w2.get_remaining_loot_time(mine)

        time_left_pretty = get_pretty_seconds(int(min(time_till_action, time_till_end_loot)))

        logger.print_warn(
            f"Loot[{mine['game_id']}]:Not reinforcing for {time_left_pretty} due to delay strategy"
        )
        return False


class PreferOtherBpCrabsAndDelayReinforcement(LootingDelayReinforcementStrategy):
    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        config_mgr: ConfigManager,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            config_mgr,
        )

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame, reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        self.reinforcement_search_backoff = reinforcement_search_backoff
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=False)

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        return super().should_reinforce(mine)


class PreferOwnBpCrabsAndDelayReinforcement(LootingDelayReinforcementStrategy):
    def __init__(
        self,
        address: Address,
        crabada_w2_client: CrabadaWeb2Client,
        crabada_w3_client: CrabadaWeb3Client,
        config_mgr: ConfigManager,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            config_mgr,
        )

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame, reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        self.reinforcement_search_backoff = reinforcement_search_backoff
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=True)

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        return super().should_reinforce(mine)
