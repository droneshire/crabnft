import typing as T
from eth_typing import Address
from web3.types import Wei

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.crabada_web3_client import CrabadaWeb3Client
from crabada.factional_advantage import get_faction_adjusted_battle_point
from crabada.profitability import REWARDS_TUS, Result
from crabada.strategies.strategy import CrabadaTransaction, GameStage, Strategy
from crabada.types import IdleGame, Team, TeamMember
from utils import logger
from utils.config_types import UserConfig
from utils.price import Tus, wei_to_tus_raw


class LootingStrategy(Strategy):
    """
    Base class for looting strategies
    """

    MIN_LOOT_POINT = 0
    LOOTING_DURATION = 60.0 * 60.0

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

    def start(self, team_id: int) -> CrabadaTransaction:
        return CrabadaTransaction(None, "LOOT", None, None, False, None, 0.0, 0.0, 0.0)

    def close(self, game_id: int) -> T.Dict[T.Any, T.Any]:
        logger.print_normal(f"Loot[{game_id}]: Settling game")
        tx_hash = self.crabada_w3.settle_game(game_id)
        tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)

        avax_gas = wei_to_tus_raw(self.crabada_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        tus, cra = self._get_rewards_from_tx_receipt(tx_receipt)
        if tus is not None:
            result = self._get_game_result(tus)
        else:
            result = Result.UNKNOWN
        return CrabadaTransaction(
            tx_hash,
            "LOOT",
            tus,
            cra,
            tx_receipt["status"] == 1,
            result,
            avax_gas,
            tx_receipt.get("gasUsed", 0.0),
        )

    def reinforce(self, game_id: int, crabada_id: int, borrow_price: Wei) -> T.Dict[T.Any, T.Any]:
        logger.print_normal(f"Loot[{game_id}]: reinforcing")
        tx_hash = self.crabada_w3.reinforce_attack(game_id, crabada_id, borrow_price)
        tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)

        avax_gas = wei_to_tus_raw(self.crabada_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        tus, cra = self._get_rewards_from_tx_receipt(tx_receipt)
        return CrabadaTransaction(
            tx_hash,
            "LOOT",
            tus,
            cra,
            tx_receipt["status"] == 1,
            None,
            avax_gas,
            tx_receipt.get("gasUsed", 0.0),
        )

    def should_reinforce(self, mine) -> bool:
        return self.crabada_w2.loot_needs_reinforcement(mine)

    def have_reinforced_at_least_once(self, mine: IdleGame) -> bool:
        return self.crabada_w2.get_num_loot_reinforcements(mine) >= 1

    def get_backoff_margin(self) -> int:
        return 15

    def get_gas_margin(self, game_stage: GameStage, mine: T.Optional[IdleGame] = None) -> int:
        if game_stage == GameStage.START:
            return 0
        elif game_stage == GameStage.CLOSE:
            return 5
        elif game_stage == GameStage.REINFORCE:
            if mine is None:
                return 0
            else:
                return 40
        else:
            return 0

    def _get_best_mine_reinforcement(
        self, team: Team, mine: IdleGame, use_own_crabs: bool = False
    ) -> T.Optional[TeamMember]:
        reinforcement_crab = None

        logger.print_normal(
            f"Loot[{mine['game_id']}]: using reinforcement strategy of {self.__class__.__name__}"
        )

        attack_battle_point = get_faction_adjusted_battle_point(mine, is_looting=True, verbose=True)
        defense_battle_point = get_faction_adjusted_battle_point(
            mine, is_looting=False, verbose=False
        )
        if attack_battle_point >= defense_battle_point:
            logger.print_normal(f"Loot[{mine['game_id']}]: not reinforcing since we're winning!")
            return None

        group_id = self.config["looting_teams"].get(team["team_id"], -1)
        reinforcement_crab = super()._use_bp_reinforcement(
            mine, group_id, use_own_crabs=use_own_crabs
        )

        if reinforcement_crab is None:
            logger.print_fail(f"Loot[{mine['game_id']}]: Could not find suitable reinforcement!")
            return None

        if (
            not self.have_reinforced_at_least_once(mine)
            and reinforcement_crab["battle_point"] < self.MIN_LOOT_POINT
        ):
            logger.print_warn(
                f"Loot[{mine['game_id']}]: not reinforcing due to lack of high bp crabs"
            )
            return None

        return reinforcement_crab


class PreferOtherBpCrabs(LootingStrategy):
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

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        return super().should_reinforce(mine)


class PreferOwnBpCrabs(LootingStrategy):
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

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        return super().should_reinforce(mine)
