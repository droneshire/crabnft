import typing as T
import math
import requests
import time

from eth_typing import Address

from crabada.factional_advantage import get_faction_adjusted_battle_point
from crabada.types import Crab, CrabForLending, IdleGame, LendingCategories, Team
from utils.general import first_or_none, n_or_better_or_none, get_pretty_seconds
from utils import logger
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
    REINFORCE_TIME_WINDOW = 60 * (30 - 2)  # 30 minute window + 2 minute buffer
    N_CRAB_PERCENT = 5.5
    TIME_PER_MINING_ACTION = 60.0 * 30

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
        res = self.list_can_join_game_raw(user_address, params)
        try:
            return [c for c in res["result"]["data"]] or []
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
            "limit": 30,
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
            "limit": 15,
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
        actual_params = {"limit": 20, "page": 1, "user_address": user_address}
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
        if len(affordable_crabs) < 10:
            nth_crab = len(affordable_crabs)
        else:
            nth_crab = int(math.ceil(self.N_CRAB_PERCENT / 100.0 * len(affordable_crabs)))
            nth_crab += reinforcement_search_backoff
        nth_crab = min(len(affordable_crabs), nth_crab)
        logger.print_ok_blue(f"Crab list: {nth_crab}/{len(affordable_crabs)}")
        return n_or_better_or_none(nth_crab, sorted_affordable_crabs)

    def get_best_high_mp_crab_for_lending(
        self, max_tus: Tus, reinforcement_search_backoff: int
    ) -> T.Optional[CrabForLending]:
        high_mp_crabs = self.list_high_mp_crabs_for_lending()
        return self.get_cheapest_best_crab_from_list_for_lending(
            high_mp_crabs, max_tus, reinforcement_search_backoff, "mine_point"
        )

    def get_best_high_bp_crab_for_lending(
        self, max_tus: Tus, reinforcement_search_backoff: int
    ) -> T.Optional[CrabForLending]:
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

    def list_crabs_for_lending_raw(self, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = self.BASE_URL + "/crabadas/lending"
        actual_params = {
            "limit": 100,
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

        user_address = mine["owner"]
        team_id = mine["team_id"]
        teams = CrabadaWeb2Client().list_teams(user_address)
        team = [t for t in teams if t["team_id"] == team_id]
        if len(team) < 1:
            return False
        defense_battle_point = get_faction_adjusted_battle_point(team[0], mine, verbose=False)

        attack_address = mine["attack_team_owner"]
        attack_team_id = mine["attack_team_id"]
        attack_teams = CrabadaWeb2Client().list_teams(attack_address)
        attack_team = [t for t in attack_teams if t["team_id"] == attack_team_id]
        if len(attack_team) < 1:
            return True
        attack_battle_point = get_faction_adjusted_battle_point(attack_team[0], mine, verbose=False)
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
