import typing as T

import requests
import time

from eth_typing import Address

from crabada.types import CrabForLending, IdleGame, LendingCategories, Team
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
    REINFORCE_TIME_WINDOW = 60 * (30 - 2)  # 30 minute window + 2 minute buffer

    @classmethod
    def get_mine(cls, mine_id: int, params: T.Dict[str, T.Any] = {}) -> IdleGame:
        """Get information from the given mine"""
        res = cls.get_mine_raw(mine_id, params)
        if res:
            return res.get("result", None) or {}
        else:
            return {}

    @classmethod
    def get_mine_raw(cls, mine_id: int, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = cls.BASE_URL + "/mine/" + str(mine_id)
        try:
            return requests.request("GET", url, params=params).json()
        except:
            return {}

    @classmethod
    def list_mines(cls, params: T.Dict[str, T.Any] = {}) -> T.List[IdleGame]:
        """
        Get all mines.

        If you want only the open mines, pass status=open in the params.
        If you want only a certain user's mines, use the user_address param.
        """
        res = cls.list_mines_raw(params)
        try:
            return res["result"]["data"] or []
        except:
            return []

    @classmethod
    def list_my_open_mines(
        cls, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.List[IdleGame]:
        """
        Get all mines that belong to the given user address
        and that are open
        """
        params["user_address"] = user_address
        params["status"] = "open"
        return cls.list_mines(params)

    @classmethod
    def list_my_open_loots(
        cls, looter_address: Address, params: [str, T.Any] = {}
    ) -> T.List[IdleGame]:
        """
        Get all mines that are being looted by the given looter address
        and that are open
        """
        params.pop("user_address", None)
        params["looter_address"] = looter_address
        params["status"] = "open"
        return cls.list_mines(params)

    @classmethod
    def list_mines_raw(cls, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = cls.BASE_URL + "/mines"
        actual_params = {
            "limit": 15,
            "page": 1,
        }
        actual_params.update(params)
        try:
            return requests.request("GET", url, params=actual_params).json()
        except:
            return {}

    @classmethod
    def get_team(cls) -> None:
        raise Exception("The team route does not exit on the server!")

    @classmethod
    def list_teams(cls, user_address: Address, params: T.Dict[str, T.Any] = {}) -> T.List[Team]:
        """
        Get all teams of a given user address.

        If you want only the available teams, pass is_team_available=1
        in the params.
        It is currently not possible to list all users' teams, you can
        only see the teams of a specific user.
        """
        res = cls.list_teams_raw(user_address, params)
        try:
            return res["result"]["data"] or []
        except:
            return []

    @classmethod
    def list_available_teams(
        cls, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.List[Team]:
        """
        Get all available teams of a given user address.
        """
        actual_params = {"is_team_available": 1}
        actual_params.update(params)
        return cls.list_teams(user_address, actual_params)

    @classmethod
    def list_teams_raw(cls, user_address: Address, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = cls.BASE_URL + "/teams"
        actual_params = {"limit": 20, "page": 1, "user_address": user_address}
        actual_params.update(params)
        try:
            return requests.request("GET", url, params=actual_params).json()
        except:
            return {}

    @classmethod
    def list_high_mp_crabs_for_lending(
        cls, params: T.Dict[str, T.Any] = {}
    ) -> T.List[CrabForLending]:
        params["limit"] = 100
        params["orderBy"] = "mine_point"
        params["order"] = "desc"
        return cls.list_crabs_for_lending(params)

    @classmethod
    def list_high_bp_crabs_for_lending(
        cls, params: T.Dict[str, T.Any] = {}
    ) -> T.List[CrabForLending]:
        params["limit"] = 100
        params["orderBy"] = "battle_point"
        params["order"] = "desc"
        return cls.list_crabs_for_lending(params)

    @classmethod
    def list_crabs_for_lending(cls, params: T.Dict[str, T.Any] = {}) -> T.List[CrabForLending]:
        """
        Get all crabs available for lending as reinforcements; you can use
        sortBy and sort parameters, default is orderBy": 'price' and
        "order": 'asc'

        IMPORTANT: The price is expressed as the TUS price multiplied by
        10^18 (like with Weis), which means that price=100000000000000000
        (18 zeros) is just 1 TUS
        """
        res = cls.list_crabs_for_lending_raw(params)
        try:
            return res["result"]["data"] or []
        except:
            return []

    @classmethod
    def get_cheapest_best_crab_from_list_for_lending(
        cls,
        crabs: T.List[CrabForLending],
        max_tus: Tus,
        n_crab_from_floor: int,
        lending_category: LendingCategories,
    ) -> CrabForLending:
        """
        From a list of crabs, pick the one with the best characteristic for the
        cheapest price
        """
        affordable_crabs = [c for c in crabs if wei_to_tus(c["price"]) < max_tus]
        sorted_affordable_crabs = sorted(
            affordable_crabs, key=lambda c: (-c[lending_category], c["price"])
        )
        return n_or_better_or_none(n_crab_from_floor, sorted_affordable_crabs)

    @classmethod
    def get_best_high_mp_crab_for_lending(cls, max_tus: Tus) -> CrabForLending:
        high_mp_crabs = cls.list_high_mp_crabs_for_lending()
        return cls.get_cheapest_best_crab_from_list_for_lending(
            high_mp_crabs, max_tus, 10, "mine_point"
        )

    @classmethod
    def get_best_high_bp_crab_for_lending(cls, max_tus: Tus) -> CrabForLending:
        high_bp_crabs = cls.list_high_bp_crabs_for_lending()
        return cls.get_cheapest_best_crab_from_list_for_lending(
            high_bp_crabs, max_tus, 10, "battle_point"
        )

    @staticmethod
    def list_crabs_for_lending_raw(params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = cls.BASE_URL + "/crabadas/lending"
        actual_params = {
            "limit": 100,
            "page": 1,
            "orderBy": "price",
            "order": "asc",
        }
        actual_params.update(params)
        try:
            return requests.request("GET", url, params=actual_params).json()
        except:
            return {}

    @staticmethod
    def mine_has_been_attacked(mine: IdleGame) -> bool:
        """
        Return True if, in the given game, the miner (the defense) has
        been attacked
        """
        if not mine:
            return False

        return mine.get("attack_team_id", None) is not None

    @classmethod
    def mine_needs_reinforcement(cls, mine: IdleGame) -> bool:
        """
        Return True if, in the given game, the miner (the defense) needs
        to reinforce the mine from an attacker
        """
        if not mine:
            return False

        if not cls.mine_is_open(mine):
            return False

        if cls.mine_is_finished(mine):
            return False

        if cls.mine_is_settled(mine):
            return False

        if not cls.mine_has_been_attacked(mine):
            return False

        if len(mine["defense_team_info"]) >= 5:
            return False

        action = mine["process"][-1]["action"]
        if action not in ["attack", "reinforce-attack"]:
            return False

        attack_start_time = mine["process"][-1]["transaction_time"]
        return time.time() - attack_start_time < cls.REINFORCE_TIME_WINDOW

    @staticmethod
    def mine_is_open(mine: IdleGame) -> bool:
        """
        Return True if the given game is open
        """
        if not mine:
            return False

        return mine.get("status", "") == "open"

    @classmethod
    def mine_is_settled(cls, mine: IdleGame) -> bool:
        """
        Return True if the given game is settled
        """
        if not mine:
            return False

        return cls.get_remaining_time(mine) < 7000 or mine.get("winner_team_id", None) is not None

    @classmethod
    def mine_is_finished(cls, mine: IdleGame) -> bool:
        """
        Return true if the given game is past its end_time
        """
        return cls.get_remaining_time(mine) <= 0

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

    @classmethod
    def get_remaining_time_formatted(cls, game: IdleGame) -> str:
        """
        Hours, minutes and seconds to the end of the given game
        """
        return get_pretty_seconds(cls.get_remaining_time(game))

    @staticmethod
    def get_next_mine_to_finish(games: T.List[IdleGame]) -> IdleGame:
        """Given a list of games, return the mine that is open and
        next to finish; returns None if there are no unfinished games
        (finished=past the 4th our, regardless of whether the reward
        has been claimed)

        If a game is already finished, it won't be considered"""
        unfinished_games = [g for g in games if not mine_is_finished(g)]
        return first_or_none(sorted(unfinished_games, key=lambda g: g.get("end_time", 10e20)))
