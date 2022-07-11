import typing as T
from eth_typing import Address
from web3.types import Wei

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.crabada_web3_client import CrabadaWeb3Client
from crabada.factional_advantage import get_faction_adjusted_battle_point
from crabada.profitability import CrabadaTransaction, get_rewards_from_tx_receipt, Result
from crabada.strategies.strategy import Strategy
from crabada.types import CrabForLending, IdleGame, MineOption, Team, TeamMember
from utils import logger
from utils.config_manager import ConfigManager
from utils.price import wei_to_tus_raw


class MiningStrategy(Strategy):
    """
    Base class for mining strategies
    """

    MAX_BP_DELTA = 3
    MIN_MINE_POINT = 60

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
        tx_hash = self.crabada_w3.start_game(team_id)
        tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)

        if tx_receipt.get("status", 0) != 1:
            try:
                logger.print_fail(tx_receipt)
            except:
                pass

        gas = wei_to_tus_raw(self.crabada_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        return CrabadaTransaction(
            tx_hash,
            MineOption.MINE,
            None,
            None,
            tx_receipt.get("status", 0) == 1,
            None,
            gas,
            tx_receipt.get("gasUsed", 0.0),
        )

    def close(self, game_id: int) -> CrabadaTransaction:
        logger.print_normal(f"Mine[{game_id}]: Closing game")
        tx_hash = self.crabada_w3.close_game(game_id)
        tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)

        if tx_receipt.get("status", 0) != 1:
            try:
                logger.print_fail(tx_receipt)
            except:
                pass

        gas = wei_to_tus_raw(self.crabada_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        tus, cra = get_rewards_from_tx_receipt(tx_receipt)
        if tus is not None:
            result = self._get_game_result(tus)
        else:
            result = Result.UNKNOWN
        return CrabadaTransaction(
            tx_hash,
            MineOption.MINE,
            tus,
            cra,
            tx_receipt.get("status", 0) == 1,
            result,
            gas,
            tx_receipt.get("gasUsed", 0.0),
        )

    def reinforce(self, game_id: int, crabada_id: int, borrow_price: Wei) -> CrabadaTransaction:
        logger.print_normal(f"Mine[{game_id}]: reinforcing")
        tx_hash = self.crabada_w3.reinforce_defense(game_id, crabada_id, borrow_price)
        tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)

        if tx_receipt.get("status", 0) != 1:
            try:
                logger.print_fail(tx_receipt)
            except:
                pass

        gas = wei_to_tus_raw(self.crabada_w3.get_gas_cost_of_transaction_wei(tx_receipt))

        return CrabadaTransaction(
            tx_hash,
            MineOption.MINE,
            None,
            None,
            tx_receipt.get("status", 0) == 1,
            None,
            gas,
            tx_receipt.get("gasUsed", 0.0),
        )

    def should_reinforce(self, mine: IdleGame, verbose=True) -> bool:
        return self.crabada_w2.mine_needs_reinforcement(mine)

    def have_reinforced_at_least_once(self, mine: IdleGame) -> bool:
        return self.crabada_w2.get_num_mine_reinforcements(mine) >= 1

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
        attack_battle_point = get_faction_adjusted_battle_point(
            mine, is_looting=True, verbose=False
        )
        if defense_battle_point >= attack_battle_point:
            logger.print_normal(f"Mine[{mine['game_id']}]: not reinforcing since we're winning!")
            return None

        group_id = self.config_mgr.config["game_specific_configs"]["mining_teams"].get(
            team["team_id"], -1
        )
        if attack_battle_point - defense_battle_point < self.MAX_BP_DELTA:
            reinforcement_crab = super()._use_bp_reinforcement(
                mine, group_id, use_own_crabs=use_own_crabs
            )
        else:
            reinforcement_crab = super()._use_mp_reinforcement(
                mine, group_id, use_own_crabs=use_own_crabs
            )

        if reinforcement_crab is None:
            logger.print_fail(f"Mine[{mine['game_id']}]: Could not find suitable reinforcement!")
            return None

        if (
            not self.have_reinforced_at_least_once(mine)
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


class PreferOwnMpCrabs(MiningStrategy):
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
