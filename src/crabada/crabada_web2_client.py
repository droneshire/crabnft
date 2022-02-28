import typing as T

import requests
import time

from eth_typing import Address

from crabada.types import CrabForLending, IdleGame, LendingCategories, Team
from utils.general import first_or_none, third_or_better, get_pretty_seconds
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
    MIN_TIME_LEFT_TO_REINFORCE = 60 * 2

    def get_mine(self, mine_id: int, params: T.Dict[str, T.Any] = {}) -> T.Optional[IdleGame]:
        """Get information from the given mine"""
        res = self.get_mine_raw(mine_id, params)
        return res.get("result", None)

    def get_mine_raw(self, mine_id: int, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = self.BASE_URL + "/mine/" + str(mine_id)
        return requests.request("GET", url, params=params).json()

    def list_mines(self, params: T.Dict[str, T.Any] = {}) -> T.List[IdleGame]:
        """
        Get all mines.

        If you want only the open mines, pass status=open in the params.
        If you want only a certain user's mines, use the user_address param.
        """
        res = self.list_mines_raw(params)
        try:
            return res["result"]["data"] or []
        except:
            return []

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
        return requests.request("GET", url, params=actual_params).json()

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
        return requests.request("GET", url, params=actual_params).json()

    def list_high_mp_crabs_for_lending(
        self, params: T.Dict[str, T.Any] = {}
    ) -> T.List[CrabForLending]:
        params["limit"] = 50
        params["orderBy"] = "mine_point"
        params["order"] = "desc"
        return self.list_crabs_for_lending(params)

    def list_high_bp_crabs_for_lending(
        self, params: T.Dict[str, T.Any] = {}
    ) -> T.List[CrabForLending]:
        params["limit"] = 50
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
        except:
            return []

    def get_cheapest_best_crab_from_list_for_lending(
        self, crabs: T.List[CrabForLending], max_tus: Tus, lending_category: LendingCategories
    ) -> CrabForLending:
        """
        From a list of crabs, pick the one with the best characteristic for the
        cheapest price
        """
        affordable_crabs = [c for c in crabs if wei_to_tus(c["price"]) < max_tus]
        sorted_affordable_crabs = sorted(
            affordable_crabs, key=lambda c: (-c[lending_category], c["price"])
        )
        return third_or_better(sorted_affordable_crabs)

    def get_best_high_mp_crab_for_lending(self, max_tus: Tus) -> CrabForLending:
        high_mp_crabs = self.list_high_mp_crabs_for_lending()
        return self.get_cheapest_best_crab_from_list_for_lending(
            high_mp_crabs, max_tus, "mine_point"
        )

    def get_best_high_bp_crab_for_lending(self, max_tus: Tus) -> CrabForLending:
        high_bp_crabs = self.list_high_bp_crabs_for_lending()
        return self.get_cheapest_best_crab_from_list_for_lending(
            high_bp_crabs, max_tus, "battle_point"
        )

    def list_crabs_for_lending_raw(self, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = self.BASE_URL + "/crabadas/lending"
        actual_params = {
            "limit": 10,
            "page": 1,
            "orderBy": "price",
            "order": "asc",
        }
        actual_params.update(params)
        return requests.request("GET", url, params=actual_params).json()  # type: ignore

    @staticmethod
    def mine_has_been_attacked(mine: IdleGame) -> bool:
        """
        Return True if, in the given game, the miner (the defense) has
        been attacked
        """
        return mine["attack_team_id"] is not None

    @staticmethod
    def mine_needs_reinforcement(mine: IdleGame) -> bool:
        """
        Return True if, in the given game, the miner (the defense) needs
        to reinforce the mine from an attacker
        """
        if not CrabadaWeb2Client.mine_is_open(mine):
            return False

        if CrabadaWeb2Client.mine_is_finished(mine):
            return False

        if CrabadaWeb2Client.mine_is_settled(mine):
            return False

        if not CrabadaWeb2Client.mine_has_been_attacked(mine):
            return False

        action = mine["process"][-1]["action"]
        if action not in ["attack", "reinforce-attack"]:
            return False

        if len(mine["defense_team_info"]) >= 5:
            return False

        # we only indicate that we can reinforce if there's sufficient time
        # to actually reinforce, we assume 60 here for now
        return (
            CrabadaWeb2Client.get_remaining_time(mine)
            > CrabadaWeb2Client.MIN_TIME_LEFT_TO_REINFORCE
        )

    @staticmethod
    def mine_is_open(mine: IdleGame) -> bool:
        """
        Return True if the given game is open
        """
        return mine["status"] == "open"

    @staticmethod
    def mine_is_settled(mine: IdleGame) -> bool:
        """
        Return True if the given game is settled
        """
        # TODO: Update to account for the situation where the looting team has less
        # BP than the mining team since the beginning, in which case you get a weird
        # situation where the mine['winner_team_id'] is None. Maybe use process?
        return (
            CrabadaWeb2Client.get_remaining_time(mine) < 7000 or mine["winner_team_id"] is not None
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
        return mine["status"] == "close"

    @staticmethod
    def get_remaining_time(game: IdleGame) -> int:
        """
        Seconds to the end of the given game
        """
        return int(game["end_time"] - time.time())

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
        return first_or_none(sorted(unfinished_games, key=lambda g: g["end_time"]))
