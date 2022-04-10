import typing as T
import math
import requests
import time

from eth_typing import Address

from crabada.factional_advantage import get_faction_adjusted_battle_point
from crabada.types import Crab, CrabadaClass, CrabForLending, IdleGame, LendingCategories, Team
from utils import logger
from utils.general import first_or_none, n_or_better_or_none, get_pretty_seconds
from utils.price import wei_to_tus, Tus


class CrabadaWeb2Client:
    """
    Access the HTTP endpoints of the Crabada P2E game.

    All endpoints have a 'raw' parameter that you can set to true
    in order to get the full JSON response. By default it is false,
    which means you only get the data contained in the response (a
    list for list endpoints, a dict for specific endpoints)
    """

    BASE_URL = "https://idle-api.crabada.com/public/idle"

    # reinforcement stuff
    N_CRAB_PERCENT = 25.0
    REINFORCE_TIME_WINDOW = 60 * (30 - 1)  # 30 minute window + 1 minute buffer

    # game facts
    TIME_PER_MINING_ACTION = 60.0 * 30
    MIN_LOOT_GAME_TIME = 60.0 * 60.0 * 1

    # api request limits (scale with teams/crabs)
    TEAM_AND_MINE_LIMIT = 50
    CRAB_LIMIT = 75

    MAX_BP_NORMAL_CRAB = 237

    def get_mine(self, mine_id: int, params: T.Dict[str, T.Any] = {}) -> IdleGame:
        """Get information from the given mine"""
        res = self.get_mine_raw(mine_id, params)
        if res:
            return res.get("result", None) or {}
        else:
            return {}

    def get_mine_raw(self, mine_id: int, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = self.BASE_URL + "/mine/" + str(mine_id)
        try:
            return requests.request("GET", url, params=params, timeout=5.0).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

    def list_mines(self, params: T.Dict[str, T.Any] = {}) -> T.List[IdleGame]:
        """
        Get all mines.

        If you want only the open mines, pass status=open in the params.
        If you want only a certain user's mines, use the user_address param.
        """
        res = self.list_mines_raw(params)
        try:
            return res["result"]["data"] or []
        except KeyboardInterrupt:
            raise
        except:
            return []

    def list_my_available_crabs_for_reinforcement(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.List[Crab]:
        res = self.list_crabs_in_game_raw(user_address, params)
        try:
            return [c for c in res["result"]["data"] if c.get("crabada_status", "") == "AVAILABLE"]
        except KeyboardInterrupt:
            raise
        except:
            return []

    def list_can_join_game_raw(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.List[Crab]:
        url = self.BASE_URL + "/crabadas/can-join-team"
        actual_params = {
            "user_address": user_address,
            "page": 1,
            "limit": self.CRAB_LIMIT,
        }
        actual_params.update(params)
        try:
            return requests.request("GET", url, params=actual_params, timeout=5.0).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

    def list_crabs_in_game_raw(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.BASE_URL + "/crabadas/in-game"
        actual_params = {
            "limit": self.CRAB_LIMIT,
            "page": 1,
            "user_address": user_address,
            "order": "desc",
        }
        actual_params.update(params)
        try:
            return requests.request("GET", url, params=actual_params, timeout=5.0).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

    def list_my_mines(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.List[IdleGame]:
        """
        Get all mines that belong to the given user address
        """
        params["user_address"] = user_address
        return self.list_mines(params)

    def list_my_open_mines(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.List[IdleGame]:
        """
        Get all mines that belong to the given user address
        and that are open
        """
        params["user_address"] = user_address
        params["status"] = "open"
        return self.list_mines(params)

    def list_my_open_loots(
        self, looter_address: Address, params: [str, T.Any] = {}
    ) -> T.List[IdleGame]:
        """
        Get all mines that are being looted by the given looter address
        and that are open
        """
        params.pop("user_address", None)
        params["looter_address"] = looter_address
        params["status"] = "open"
        return self.list_mines(params)

    def list_mines_raw(self, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = self.BASE_URL + "/mines"
        actual_params = {
            "limit": self.TEAM_AND_MINE_LIMIT,
            "page": 1,
        }
        actual_params.update(params)
        try:
            return requests.request("GET", url, params=actual_params, timeout=5.0).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

    def get_team(self) -> None:
        raise Exception("The team route does not exit on the server!")

    def list_teams(self, user_address: Address, params: T.Dict[str, T.Any] = {}) -> T.List[Team]:
        """
        Get all teams of a given user address.

        If you want only the available teams, pass is_team_available=1
        in the params.
        It is currently not possible to list all users' teams, you can
        only see the teams of a specific user.
        """
        res = self.list_teams_raw(user_address, params)
        try:
            return res["result"]["data"] or []
        except KeyboardInterrupt:
            raise
        except:
            return []

    def list_available_teams(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.List[Team]:
        """
        Get all available teams of a given user address.
        """
        actual_params = {"is_team_available": 1}
        actual_params.update(params)
        return self.list_teams(user_address, actual_params)

    def list_teams_raw(self, user_address: Address, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = self.BASE_URL + "/teams"
        actual_params = {"limit": self.TEAM_AND_MINE_LIMIT, "page": 1, "user_address": user_address}
        actual_params.update(params)
        try:
            return requests.request("GET", url, params=actual_params, timeout=5.0).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

    def list_high_mp_crabs_for_lending(
        self, params: T.Dict[str, T.Any] = {}
    ) -> T.List[CrabForLending]:
        params["limit"] = 100
        params["orderBy"] = "mine_point"
        params["order"] = "desc"
        return self.list_crabs_for_lending(params)

    def list_high_bp_crabs_for_lending(
        self, params: T.Dict[str, T.Any] = {}
    ) -> T.List[CrabForLending]:
        params["limit"] = 100
        params["orderBy"] = "battle_point"
        params["order"] = "desc"
        return self.list_crabs_for_lending(params)

    def list_crabs_for_lending(self, params: T.Dict[str, T.Any] = {}) -> T.List[CrabForLending]:
        """
        Get all crabs available for lending as reinforcements; you can use
        sortBy and sort parameters, default is orderBy": 'price' and
        "order": 'asc'

        IMPORTANT: The price is expressed as the TUS price multiplied by
        10^18 (like with Weis), which means that price=100000000000000000
        (18 zeros) is just 1 TUS
        """
        res = self.list_crabs_for_lending_raw(params)
        try:
            return res["result"]["data"] or []
        except KeyboardInterrupt:
            raise
        except:
            return []

    def get_num_mine_reinforcements(self, mine: IdleGame) -> int:
        mine = self.get_mine(mine.get("game_id", None))
        if mine is None:
            return 0

        process = mine.get("process", [])
        return len([p for p in process if p["action"] == "reinforce-defense"])

    def get_num_loot_reinforcements(self, mine: IdleGame) -> int:
        mine = self.get_mine(mine.get("game_id", None))
        if mine is None:
            return 0

        process = mine.get("process", [])
        return len([p for p in process if p["action"] == "reinforce-attack"])

    def get_cheapest_best_crab_from_list_for_lending(
        self,
        crabs: T.List[CrabForLending],
        max_tus: Tus,
        reinforcement_search_backoff: int,
        lending_category: LendingCategories,
    ) -> CrabForLending:
        """
        From a list of crabs, pick the one with the best characteristic for the
        cheapest price
        """
        affordable_crabs = [c for c in crabs if wei_to_tus(c.get("price", max_tus)) < max_tus]
        sorted_affordable_crabs = sorted(
            affordable_crabs, key=lambda c: (-c[lending_category], c.get("price", max_tus))
        )
        if len(affordable_crabs) < 25:
            nth_crab = len(affordable_crabs) - 1
        else:
            nth_crab = int(math.ceil(self.N_CRAB_PERCENT / 100.0 * len(affordable_crabs)))
            nth_crab += reinforcement_search_backoff
        nth_crab = min(len(affordable_crabs), nth_crab)
        logger.print_ok_blue(f"Crab list: {nth_crab}/{len(affordable_crabs)}")
        return n_or_better_or_none(nth_crab, sorted_affordable_crabs)

    def get_best_high_mp_crab_for_lending(
        self, max_tus: Tus, reinforcement_search_backoff: int
    ) -> T.Optional[CrabForLending]:
        for class_id in [CrabadaClass.PRIME, CrabadaClass.CRABOID]:
            params = {
                "class_ids[]": class_id,
            }
            high_mp_crabs = self.list_high_mp_crabs_for_lending(params=params)
            high_mp_crab = self.get_cheapest_best_crab_from_list_for_lending(
                high_mp_crabs, max_tus, reinforcement_search_backoff, "mine_point"
            )
            if high_mp_crab is not None:
                return high_mp_crab

    def get_best_high_bp_crab_for_lending(
        self, max_tus: Tus, reinforcement_search_backoff: int
    ) -> T.Optional[CrabForLending]:
        params = {
            "class_ids[]": 4,  # bulks
        }
        high_bp_crabs = self.list_high_bp_crabs_for_lending()
        return self.get_cheapest_best_crab_from_list_for_lending(
            high_bp_crabs, max_tus, reinforcement_search_backoff, "battle_point"
        )

    def get_my_best_mp_crab_for_lending(self, user_address: Address) -> T.Optional[CrabForLending]:
        return self.get_my_best_crab_for_lending(user_address, params={"orderBy": "mine_point"})

    def get_my_best_bp_crab_for_lending(self, user_address: Address) -> T.Optional[CrabForLending]:
        return self.get_my_best_crab_for_lending(user_address, params={"orderBy": "battle_point"})

    def get_my_best_crab_for_lending(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.Optional[CrabForLending]:
        my_crabs = self.list_my_available_crabs_for_reinforcement(user_address, params)
        if not my_crabs:
            return None

        sorted_crabs = sorted(my_crabs, key=lambda c: c["battle_point"])
        best_crab = sorted_crabs[0]
        best_crab["price"] = 0
        return best_crab

    def get_reinforcement_crabs(self, mine: IdleGame) -> T.List[int]:
        return [m["crabada_id"] for m in mine.get("defense_team_info", [])][3:]

    def list_crabs_for_lending_raw(self, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = self.BASE_URL + "/crabadas/lending"
        actual_params = {
            "limit": self.CRAB_LIMIT,
            "page": 1,
            "orderBy": "price",
            "order": "asc",
        }
        actual_params.update(params)
        try:
            return requests.request("GET", url, params=actual_params, timeout=5.0).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

    @staticmethod
    def _get_battle_points(mine: IdleGame) -> T.Tuple[int, int]:
        defense_battle_point = get_faction_adjusted_battle_point(
            mine, is_looting=False, verbose=False
        )
        attack_battle_point = get_faction_adjusted_battle_point(
            mine, is_looting=True, verbose=False
        )

        return (defense_battle_point, attack_battle_point)

    @staticmethod
    def _can_loot_reinforcement_win(mine: IdleGame) -> bool:
        defense_battle_point, attack_battle_point = CrabadaWeb2Client()._get_battle_points(mine)
        return attack_battle_point + CrabadaWeb2Client.MAX_BP_NORMAL_CRAB > defense_battle_point

    @staticmethod
    def loot_is_winning(mine: IdleGame) -> bool:
        """
        Determines if attack looter has won the battle
        """
        try:
            if mine.get("winner_team_id", -1) == mine["attack_team_id"]:
                return True
        except KeyboardInterrupt:
            raise
        except:
            return False
        defense_battle_point, attack_battle_point = CrabadaWeb2Client()._get_battle_points(mine)
        return attack_battle_point > defense_battle_point

    @staticmethod
    def mine_is_winning(mine: IdleGame) -> bool:
        """
        Determines if defense miner has won the battle
        """
        try:
            if mine.get("winner_team_id", -1) == mine["team_id"]:
                return True
        except KeyboardInterrupt:
            raise
        except:
            return False
        defense_battle_point, attack_battle_point = CrabadaWeb2Client()._get_battle_points(mine)

        if defense_battle_point is None:
            return False

        if attack_battle_point is None:
            return True

        return defense_battle_point >= attack_battle_point

    @staticmethod
    def mine_has_been_attacked(mine: IdleGame) -> bool:
        """
        Return True if, in the given game, the miner (the defense) has
        been attacked
        """
        if not mine:
            return False

        return mine.get("attack_team_id", None) is not None

    @staticmethod
    def mine_needs_reinforcement(mine: IdleGame) -> bool:
        """
        Return True if, in the given game, the miner (the defense) needs
        to reinforce the mine from an attacker
        """
        if not mine:
            return False

        if not CrabadaWeb2Client.mine_is_open(mine):
            return False

        if CrabadaWeb2Client.mine_is_finished(mine):
            return False

        if CrabadaWeb2Client.mine_is_settled(mine):
            return False

        if not CrabadaWeb2Client.mine_has_been_attacked(mine):
            return False

        process = mine["process"]
        actions = [p["action"] for p in process]
        if actions[-1] not in ["attack", "reinforce-attack"]:
            return False

        if actions.count("reinforce-defense") >= 2:
            return False

        if CrabadaWeb2Client.mine_is_winning(mine):
            return False

        attack_start_time = process[-1]["transaction_time"]
        return time.time() - attack_start_time < CrabadaWeb2Client.REINFORCE_TIME_WINDOW

    @staticmethod
    def loot_needs_reinforcement(mine: IdleGame) -> bool:
        """
        Return True if, in the given game, the looter (the offense) needs
        to attack the mine of a miner
        """
        if not mine:
            return False

        if not CrabadaWeb2Client.mine_is_open(mine):
            return False

        if CrabadaWeb2Client.mine_is_finished(mine):
            return False

        if CrabadaWeb2Client.mine_is_settled(mine):
            return False

        process = mine["process"]
        actions = [p["action"] for p in process]
        if actions[-1] not in ["reinforce-defense"]:
            return False

        if actions.count("reinforce-attack") >= 2:
            return False

        if CrabadaWeb2Client.loot_is_winning(mine):
            return False

        # make sure we don't reinforce to a legendary when we can't win
        if not CrabadaWeb2Client._can_loot_reinforcement_win(mine):
            logger.print_warn(f"Not reinforcing due to LEGENDARY reinforcement")
            return False

        defense_start_time = process[-1]["transaction_time"]
        return time.time() - defense_start_time < CrabadaWeb2Client.REINFORCE_TIME_WINDOW

    @staticmethod
    def mine_is_open(mine: IdleGame) -> bool:
        """
        Return True if the given game is open
        """
        if not mine:
            return False

        return mine.get("status", "") == "open"

    @staticmethod
    def mine_is_settled(mine: IdleGame) -> bool:
        """
        Return True if the given game is settled
        """
        if not mine:
            return False

        return (
            CrabadaWeb2Client.get_remaining_time(mine) < 7000
            or mine.get("winner_team_id", None) is not None
        )

    @staticmethod
    def mine_is_finished(mine: IdleGame) -> bool:
        """
        Return true if the given game is past its end_time
        """
        return CrabadaWeb2Client.get_remaining_time(mine) <= 0

    @staticmethod
    def loot_past_settle_time(mine: IdleGame) -> bool:
        time_since_start = time.time() - mine["start_time"]

        return time_since_start > CrabadaWeb2Client.MIN_LOOT_GAME_TIME

    @staticmethod
    def loot_is_able_to_be_settled(mine: IdleGame) -> bool:
        """
        Return true if the given loot is able to be settled
        """
        if not CrabadaWeb2Client.loot_past_settle_time(mine):
            return False

        if CrabadaWeb2Client.loot_needs_reinforcement(mine):
            return False

        actions = [p["action"] for p in mine["process"]]

        if actions.count("reinforce-attack") >= 2:
            return True

        if actions[-1] in ["attack", "reinforce-attack"]:
            margin = 60.0 * 3
            return (
                CrabadaWeb2Client.get_time_since_last_action(mine)
                > CrabadaWeb2Client.TIME_PER_MINING_ACTION + margin
            )

        return True

    @staticmethod
    def mine_is_closed(mine: IdleGame) -> bool:
        """
        Return true if the given game is closed (meaning the
        game has been settled and the reward has been claimed)
        """
        return mine.get("status", "") == "close"

    @staticmethod
    def get_remaining_time(game: IdleGame) -> int:
        """
        Seconds to the end of the given game
        """
        now = time.time()
        return int(game.get("end_time", now) - now)

    @staticmethod
    def get_total_mine_time(game: IdleGame) -> int:
        """
        Seconds total mine start to end
        """
        return int(game.get("end_time", 0) - game.get("start_time", 0))

    @staticmethod
    def get_total_mine_time_formatted(game: IdleGame) -> int:
        return get_pretty_seconds(CrabadaWeb2Client.get_total_mine_time(game))

    @staticmethod
    def get_remaining_loot_time(game: IdleGame) -> int:
        """
        Seconds to the end of the given loot before can settle
        """
        now = time.time()
        end_time = game.get("start_time", now) + CrabadaWeb2Client.MIN_LOOT_GAME_TIME
        return int(end_time - now)

    @staticmethod
    def get_remaining_loot_time_formatted(game: IdleGame) -> str:
        return get_pretty_seconds(CrabadaWeb2Client.get_remaining_loot_time(game))

    @staticmethod
    def get_time_since_last_action(game: IdleGame) -> int:
        """
        Seconds since last game action
        """
        now = time.time()
        transaction_time = game["process"][-1]["transaction_time"]
        return int(now - transaction_time)

    @staticmethod
    def get_time_since_last_action_formatted(game: IdleGame) -> str:
        """
        Hours, minutes and seconds to the end of the current action
        """
        return get_pretty_seconds(CrabadaWeb2Client.get_time_since_last_action(game))

    @staticmethod
    def get_remaining_time_for_action(game: IdleGame) -> int:
        now = time.time()
        last_transaction_time = game["process"][-1]["transaction_time"]
        return int(last_transaction_time + CrabadaWeb2Client.TIME_PER_MINING_ACTION - now)

    @staticmethod
    def get_remaining_time_for_action_formatted(game: IdleGame) -> str:
        """
        Hours, minutes and seconds to the end of the current action
        """
        return get_pretty_seconds(CrabadaWeb2Client.get_remaining_time_for_action(game))

    @staticmethod
    def get_remaining_time_formatted(game: IdleGame) -> str:
        """
        Hours, minutes and seconds to the end of the given game
        """
        return get_pretty_seconds(CrabadaWeb2Client.get_remaining_time(game))

    @staticmethod
    def get_next_mine_to_finish(games: T.List[IdleGame]) -> IdleGame:
        """Given a list of games, return the mine that is open and
        next to finish; returns None if there are no unfinished games
        (finished=past the 4th our, regardless of whether the reward
        has been claimed)

        If a game is already finished, it won't be considered"""
        unfinished_games = [g for g in games if not mine_is_finished(g)]
        return first_or_none(sorted(unfinished_games, key=lambda g: g.get("end_time", 10e20)))

    @staticmethod
    def get_last_mine_start_time(user_address: Address) -> int:
        last_mine_start = 0
        for mine in CrabadaWeb2Client().list_my_open_mines(user_address):
            last_mine_start = max(last_mine_start, mine.get("start_time", 0))
        return last_mine_start
