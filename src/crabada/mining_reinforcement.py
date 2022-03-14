import typing as T

from crabada.types import IdleGame, Team, TeamMember
from crabada.crabada_web2_client import CrabadaWeb2Client
from utils import logger
from crabada.factional_advantage import get_faction_adjusted_battle_point

class Strategy:
    MAX_BP_DELTA = 3

    def __init__(self, reinforcement_crabs: T.List[TeamMember], max_reinforcement_price_tus: Tus) -> None:
        self.reinforcement_crabs = reinforcement_crabs
        self.max_reinforcement_price_tus = max_reinforcement_price_tus

    def get_reinforcement_crab(self, team: Team, mine: IdleGame(), teams: T.List[Team]) -> T.Optional[TeamMember]:
        raise NotImplementedError

    def _have_reinforced_at_least_once(self, team: Team) -> bool:
        mine = self.crabada_w2.get_mine(team["game_id"])
        if mine is None:
            return False
        return (len(mine.get("defense_team_info", [])) > 3)

    def _get_best_reinforcement_from_tavern(self) -> T.Optional[TeamMember()]:
        reinforcment_crab = None
        if (
            mine["attack_point"] - get_faction_adjusted_battle_point(team, mine)
            < self.MAX_BP_DELTA
        ):
            logger.print_normal(
                f"Mine[{mine['game_id']}]: using reinforcement strategy of highest bp"
            )
            reinforcment_crab = CrabadaWeb2Client.get_best_high_bp_crab_for_lending(
                self.max_reinforcement_price_tus
            )
        else:
            logger.print_normal(
                f"Mine[{mine['game_id']}]: using reinforcement strategy of highest mp"
            )
            reinforcment_crab = self.crabada_w2.get_best_high_mp_crab_for_lending(
                self.max_reinforcement_price_tus
            )

        if reinforcment_crab is None:
            logger.print_fail("Could not find affordable reinforcement!")

        return reinforcment_crab

class PreferMp(Strategy):

    def __init__(self, reinforcement_crabs: T.List[TeamMember], max_reinforcement_price_tus: Tus) -> None:
        super().__init__(reinforcement_crabs, max_reinforcement_price_tus)

    def get_reinforcement_crab(self, team: Team, mine: IdleGame(), teams: T.List[Team]) -> T.Optional[TeamMember]:
        return super()._get_best_reinforcement_from_tavern()


class PreferOwnCrabs(Strategy):

    def __init__(self, reinforcement_crabs: T.List[TeamMember], max_reinforcement_price_tus: Tus) -> None:
        super().__init__(reinforcement_crabs, max_reinforcement_price_tus)
        self.cool_down_expiration = {}

    def get_reinforcement_crab(self, team: Team, mine: IdleGame(), teams: T.List[Team]) -> T.Optional[TeamMember]:
        reinforcment_crab = None

        defense_battle_point = get_faction_adjusted_battle_point(team, mine)
        if defense_battle_point >= mine["attack_point"]:
            logger.print_normal(
                f"Mine[{mine['game_id']}]: not reinforcing since we've already won!"
            )
            return None

        allowed_reinforcement_crabs = [
                c["crabada_id"] for c in self.config["reinforcing_crabs"]
            ]

        if mine["attack_point"] - defense_battle_point < self.MAX_BP_DELTA:
            logger.print_normal(
                f"Mine[{mine['game_id']}]: using reinforcement strategy of highest bp"
            )
            reinforcment_crab = self.crabada_w2.get_my_best_bp_crab_for_lending(self.address)
            if (
                reinforcment_crab is not None
                and reinforcment_crab["crabada_id"] in allowed_reinforcement_crabs
            ):
                logger.print_bold(f"Mine[{mine['game_id']}]: using our own crab to reinforce!")
            else:
                reinforcment_crab = self.crabada_w2.get_best_high_bp_crab_for_lending(
                    self.config["max_reinforcement_price_tus"]
                )
        else:
            logger.print_normal(
                f"Mine[{mine['game_id']}]: using reinforcement strategy of highest mp"
            )
            reinforcment_crab = self.crabada_w2.get_my_best_mp_crab_for_lending(self.address)
            if (
                reinforcment_crab is not None
                and reinforcment_crab["crabada_id"] in allowed_reinforcement_crabs
            ):
                logger.print_bold(f"Mine[{mine['game_id']}]: using our own crab to reinforce!")
            else:
                reinforcment_crab = self.crabada_w2.get_best_high_mp_crab_for_lending(
                    self.config["max_reinforcement_price_tus"])

            if reinforcment_crab is None:
                logger.print_fail(
                    f"Mine[{mine['game_id']}]: Could not find suitable reinforcement!"
                )
                return None

            if (
                not self._have_reinforced_at_least_once(team)
                and reinforcment_crab["mine_point"] < self.MIN_MINE_POINT
            ):
                logger.print_warn(
                    f"Mine[{mine['game_id']}]: not reinforcing due to lack of high mp crabs"
                )
                return None
