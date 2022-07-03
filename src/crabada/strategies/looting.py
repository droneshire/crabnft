import time
import typing as T
from eth_account import Account, messages
from eth_typing import Address
from web3.types import Wei

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.crabada_web3_client import CrabadaWeb3Client
from crabada.factional_advantage import get_faction_adjusted_battle_point
from crabada.profitability import CrabadaTransaction, get_rewards_from_tx_receipt, Result
from crabada.strategies.strategy import GameStage, Strategy
from crabada.types import MineOption, IdleGame, Team, TeamMember
from utils import logger
from utils.config_manager import ConfigManager
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
        config_mgr: ConfigManager,
    ) -> None:
        super().__init__(
            address,
            crabada_w2_client,
            crabada_w3_client,
            config_mgr,
        )

    def start(self, team_id: int, game_id: T.Optional[int] = None) -> CrabadaTransaction:
        logger.print_normal(f"Starting loot")
        signature, expired_time = self._get_loot_signature(game_id, team_id)
        tx_hash = self.crabada_w3.attack(game_id, team_id, expired_time, signature)
        tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)
        gas = wei_to_tus_raw(self.crabada_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        return CrabadaTransaction(
            tx_hash,
            MineOption.LOOT,
            None,
            None,
            tx_receipt["status"] == 1,
            None,
            gas,
            tx_receipt.get("gasUsed", 0.0),
        )

    def close(self, game_id: int) -> T.Dict[T.Any, T.Any]:
        logger.print_normal(f"Loot[{game_id}]: Settling game")
        tx_hash = self.crabada_w3.settle_game(game_id)
        tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)

        gas = wei_to_tus_raw(self.crabada_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        tus, cra = get_rewards_from_tx_receipt(tx_receipt)
        if tus is not None:
            result = self._get_game_result(tus)
        else:
            result = Result.UNKNOWN
        return CrabadaTransaction(
            tx_hash,
            MineOption.LOOT,
            tus,
            cra,
            tx_receipt["status"] == 1,
            result,
            gas,
            tx_receipt.get("gasUsed", 0.0),
        )

    def reinforce(self, game_id: int, crabada_id: int, borrow_price: Wei) -> T.Dict[T.Any, T.Any]:
        logger.print_normal(f"Loot[{game_id}]: reinforcing")
        tx_hash = self.crabada_w3.reinforce_attack(game_id, crabada_id, borrow_price)
        tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)

        gas = wei_to_tus_raw(self.crabada_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        return CrabadaTransaction(
            tx_hash,
            MineOption.LOOT,
            None,
            None,
            tx_receipt["status"] == 1,
            None,
            gas,
            tx_receipt.get("gasUsed", 0.0),
        )

    def should_start(self, team: Team) -> bool:
        return team["looting_point"] > 0

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

    def _get_loot_signature(self, game_id: int, team_id: int) -> (str, int):
        data = self.crabada_w2.get_loot_attack_data(self.address, team_id, game_id)
        return data["signature"], data["expire_time"]

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

        group_id = self.config_mgr.config["game_specific_configs"]["looting_teams"].get(
            team["team_id"], -1
        )
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


class PreferOwnBpCrabs(LootingStrategy):
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
