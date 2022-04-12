import time
import typing as T
from eth_typing import Address

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.crabada_web3_client import CrabadaWeb3Client
from crabada.strategies.mining import MiningStrategy
from crabada.strategies.mining_delayed_reinforce import MiningDelayReinforcementStrategy
from crabada.strategies.strategy import GameStage
from crabada.types import IdleGame, Team, TeamMember
from utils import logger
from utils.config_types import UserConfig
from utils.general import get_pretty_seconds


class ScatteredReinforcement(MiningStrategy):
    MIN_TIME_BETWEEN_MINES = 60.0 * 31.0

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

    def get_gas_margin(self, game_stage: GameStage, mine: T.Optional[IdleGame] = None) -> int:
        if game_stage == GameStage.START:
            return 30
        elif game_stage == GameStage.CLOSE:
            return 30
        elif game_stage == GameStage.REINFORCE:
            if mine is None:
                return 0
            else:
                return 30 if self.have_reinforced_at_least_once(mine) else 0
        else:
            return 0

    def _get_mine_per_group(self, mine_group: int) -> T.List[IdleGame]:
        mines = []
        for open_mine in self.crabada_w2.list_my_open_mines(self.config["address"]):
            group = self.config["mining_teams"].get(open_mine["team_id"], -1)
            if group == mine_group:
                mines.append(open_mine)
        return mines

    def should_start(self, team: Team) -> bool:
        mine_group = self.config["mining_teams"].get(team["team_id"], -1)

        if mine_group == -1:
            return True

        mines = self._get_mine_per_group(mine_group)

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
            f"Waiting to start mine for {team['team_id']} (group {mine_group}) in {time_before_start_formatted}"
        )
        return False

    def get_reinforcement_crab(
        self, team: Team, mine: IdleGame, reinforcement_search_backoff: int = 0
    ) -> T.Optional[TeamMember]:
        self.reinforcement_search_backoff = reinforcement_search_backoff
        return super()._get_best_mine_reinforcement(team, mine, use_own_crabs=True)


class ScatteredDelayReinforcement(ScatteredReinforcement):
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

        mines = self._get_mine_per_group(mine_group)

        if not mines:
            return True

        now = time.time()
        last_mine_start = 0
        for mine in mines:
            last_mine_start = max(last_mine_start, mine.get("start_time", now))

        if (
            now - last_mine_start
            > self.MIN_TIME_BETWEEN_MINES
            - MiningDelayReinforcementStrategy.DELAY_BEFORE_REINFORCING
        ):
            return True

        time_before_start_formatted = get_pretty_seconds(
            int(
                last_mine_start
                + self.MIN_TIME_BETWEEN_MINES
                - MiningDelayReinforcementStrategy.DELAY_BEFORE_REINFORCING
                - now
            )
        )
        logger.print_normal(
            f"Waiting to start mine for {team['team_id']} (group {mine_group}) in {time_before_start_formatted}"
        )
        return False
